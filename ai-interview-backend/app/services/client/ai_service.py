import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError as OpenAIAuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)
from app.core.config import settings
from app.exceptions.http_exceptions import ValidationError
from app.services.client.resume_evaluation_snapshot import snapshot_from_payload
logger = logging.getLogger(__name__)
PANEL_OUTPUT_VERSION = "panel_structured_v1"
PANEL_ROLE_ALIAS = {
    "technical_deep_dive": "technical",
    "project_follow_up": "project",
    "business_scenario": "business",
    "behavior_expression": "communication",
    "pressure_challenge": "pressure",
}
DEFAULT_PANEL_ROLES = [
    {
        "role_key": "technical_deep_dive",
        "role": "technical",
        "name": "Technical Deep Dive",
        "focus": "Probe core principles, engineering trade-offs, and technical depth.",
    },
    {
        "role_key": "project_follow_up",
        "role": "project",
        "name": "Project Follow-up",
        "focus": "Verify ownership, decisions, delivery quality, and retrospection.",
    },
    {
        "role_key": "business_scenario",
        "role": "business",
        "name": "Business Scenario",
        "focus": "Test business grounding, scenario reasoning, and practical trade-offs.",
    },
    {
        "role_key": "behavior_expression",
        "role": "communication",
        "name": "Behavior & Communication",
        "focus": "Observe structure, collaboration, clarity, and expression quality.",
    },
    {
        "role_key": "pressure_challenge",
        "role": "pressure",
        "name": "Pressure Challenge",
        "focus": "Test stress handling, risk awareness, and difficult trade-offs.",
    },
]
DEEPSEEK_V4_MODELS = {"deepseek-v4-flash", "deepseek-v4-pro"}
DEEPSEEK_LEGACY_MODEL_ALIASES = {
    "deepseek-chat": ("deepseek-v4-flash", "disabled"),
    "deepseek-reasoner": ("deepseek-v4-flash", "enabled"),
}
RESUME_EVIDENCE_DOMAIN_TERMS = [
    "电商", "支付", "金融", "风控", "营销", "广告", "SaaS", "CRM", "ERP",
    "物流", "供应链", "教育", "医疗", "零售", "客服", "中台", "平台", "数据中台",
    "推荐", "搜索", "内容", "社交", "游戏", "直播", "IoT", "物联网", "制造",
]
RESUME_EVIDENCE_AMBIGUITY_TERMS = [
    "参与", "协助", "支持", "了解", "熟悉", "接触", "配合", "相关", "负责部分", "等",
]
class AIService:
    @staticmethod
    async def test_runtime_connection(ai_config: Optional[Dict] = None) -> Dict[str, Any]:
        client, model, source, provider_label, request_kwargs = AIService._resolve_runtime(ai_config)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Reply with OK only."},
                    {"role": "user", "content": "Connectivity check."},
                ],
                temperature=0,
                max_tokens=8,
                **request_kwargs,
            )
            content = (response.choices[0].message.content or "").strip()
            return {
                "provider": ai_config.get("provider") if ai_config else None,
                "provider_label": provider_label,
                "model": model,
                "base_url": ai_config.get("base_url") if ai_config else None,
                "source": source,
                "message": f"{provider_label} API 连接测试成功",
                "response_preview": content[:32],
            }
        except Exception as exc:
            logger.exception("AI provider connectivity test failed (%s): %s", source, exc)
            translated = AIService._translate_runtime_error(
                exc,
                source=source,
                provider_label=provider_label,
            )
            if translated is exc:
                raise
            raise translated from exc
    @staticmethod
    def _resolve_runtime(ai_config: Optional[Dict] = None):
        if ai_config and ai_config.get("api_key"):
            provider = (ai_config.get("provider") or "deepseek").strip().lower()
            default_base_url = (
                settings.OPENAI_BASE_URL if provider == "openai" else settings.DEEPSEEK_BASE_URL
            )
            default_model = (
                settings.OPENAI_MODEL if provider == "openai" else settings.DEEPSEEK_MODEL
            )
            model, request_kwargs = AIService._normalize_model_request(
                provider=provider,
                model=ai_config.get("model") or default_model,
                ai_config=ai_config,
            )
            return (
                AsyncOpenAI(
                    api_key=ai_config["api_key"],
                    base_url=ai_config.get("base_url") or default_base_url,
                ),
                model,
                ai_config.get("source") or "user",
                ai_config.get("provider_label") or ("ChatGPT / OpenAI" if provider == "openai" else "DeepSeek"),
                request_kwargs,
            )
        raise ValidationError(message="请先在个人中心保存可用的 AI API Key")
    @staticmethod
    def _normalize_model_request(
        provider: str,
        model: str,
        ai_config: Optional[Dict] = None,
    ) -> tuple[str, Dict[str, Any]]:
        normalized_provider = (provider or "deepseek").strip().lower()
        normalized_model = (model or "").strip()
        if normalized_provider != "deepseek":
            return normalized_model, {}

        legacy_thinking = None
        if normalized_model in DEEPSEEK_LEGACY_MODEL_ALIASES:
            normalized_model, legacy_thinking = DEEPSEEK_LEGACY_MODEL_ALIASES[normalized_model]

        if normalized_model not in DEEPSEEK_V4_MODELS:
            return normalized_model, {}

        configured_thinking = (
            (ai_config or {}).get("thinking")
            or legacy_thinking
            or settings.DEEPSEEK_THINKING
            or "disabled"
        )
        thinking = str(configured_thinking).strip().lower()
        if thinking in {"enable", "enabled", "true", "1", "yes", "on"}:
            effort = str(
                (ai_config or {}).get("reasoning_effort")
                or settings.DEEPSEEK_REASONING_EFFORT
                or "high"
            ).strip().lower()
            if effort in {"low", "medium"}:
                effort = "high"
            elif effort in {"xhigh"}:
                effort = "max"
            elif effort not in {"high", "max"}:
                effort = "high"
            return normalized_model, {
                "reasoning_effort": effort,
                "extra_body": {"thinking": {"type": "enabled"}},
            }

        return normalized_model, {"extra_body": {"thinking": {"type": "disabled"}}}
    @staticmethod
    def _translate_runtime_error(
        exc: Exception,
        source: str = "user",
        provider_label: str = "AI",
    ) -> ValidationError:
        if isinstance(exc, ValidationError):
            return exc
        if isinstance(exc, (OpenAIAuthenticationError, PermissionDeniedError)):
            return ValidationError(message=f"{provider_label} API Token 无效或已失效，请检查后重试")
        if isinstance(exc, RateLimitError):
            return ValidationError(message=f"{provider_label} API Token 额度不足或请求过于频繁，请检查后重试")
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return ValidationError(message=f"连接 {provider_label} 失败，请检查网络或 Base URL 后重试")
        if isinstance(exc, BadRequestError):
            return ValidationError(message=f"{provider_label} 请求参数错误，请检查模型名或 Base URL 配置")
        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)
            if status_code in {401, 403}:
                return ValidationError(message=f"{provider_label} API Token 无效或已失效，请检查后重试")
            if status_code in {402, 429}:
                return ValidationError(message=f"{provider_label} API Token 额度不足或请求过于频繁，请检查后重试")
            if status_code in {502, 503, 504}:
                return ValidationError(message=f"连接 {provider_label} 失败，请稍后重试")
        return ValidationError(
            message=(
                f"调用你的 {provider_label} API 失败，请检查 API Token、Base URL 配置，"
                "或稍后再试"
            )
        )
    @staticmethod
    async def _chat(
        messages: list,
        temperature: float = 0.7,
        ai_config: Optional[Dict] = None,
    ) -> str:
        client, model, source, provider_label, request_kwargs = AIService._resolve_runtime(ai_config)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
                **request_kwargs,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.exception("AI provider chat call failed (%s): %s", source, exc)
            translated = AIService._translate_runtime_error(
                exc,
                source=source,
                provider_label=provider_label,
            )
            if translated is exc:
                raise
            raise translated from exc
    @staticmethod
    async def _chat_stream(
        messages: list,
        temperature: float = 0.7,
        ai_config: Optional[Dict] = None,
    ):
        client, model, source, provider_label, request_kwargs = AIService._resolve_runtime(ai_config)
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
                stream=True,
                **request_kwargs,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as exc:
            logger.exception("AI provider stream call failed (%s): %s", source, exc)
            translated = AIService._translate_runtime_error(
                exc,
                source=source,
                provider_label=provider_label,
            )
            if translated is exc:
                raise
            raise translated from exc
    @staticmethod
    def _strip_code_fence(text: str) -> str:
        payload = (text or "").strip()
        if payload.startswith("```"):
            payload = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", payload)
            payload = re.sub(r"\s*```$", "", payload)
        return payload.strip()
    @staticmethod
    def _clean_json_candidate(text: str) -> str:
        cleaned = (text or "").strip()
        replacements = {
            "﻿": "",
            "​": "",
            " ": " ",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
        }
        for source, target in replacements.items():
            cleaned = cleaned.replace(source, target)
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        return cleaned.strip()
    @staticmethod
    def _find_balanced_json_block(text: str) -> Optional[str]:
        payload = text or ""
        for opener, closer in (("{", "}"), ("[", "]")):
            start_index = payload.find(opener)
            if start_index == -1:
                continue
            depth = 0
            in_string = False
            escape = False
            for index in range(start_index, len(payload)):
                char = payload[index]
                if escape:
                    escape = False
                    continue
                if char == "\\" and in_string:
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == opener:
                    depth += 1
                elif char == closer:
                    depth -= 1
                    if depth == 0:
                        return payload[start_index : index + 1]
        return None
    @staticmethod
    def _parse_json_candidate(candidate: str) -> Any:
        cleaned = AIService._clean_json_candidate(candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as first_error:
            python_like = re.sub(r"\btrue\b", "True", cleaned, flags=re.IGNORECASE)
            python_like = re.sub(r"\bfalse\b", "False", python_like, flags=re.IGNORECASE)
            python_like = re.sub(r"\bnull\b", "None", python_like, flags=re.IGNORECASE)
            try:
                parsed = ast.literal_eval(python_like)
            except (SyntaxError, ValueError):
                raise first_error
            if isinstance(parsed, (dict, list)):
                return parsed
            raise first_error
    @staticmethod
    def _extract_json(text: str) -> Any:
        payload = AIService._strip_code_fence(text)
        candidates: List[str] = []
        for candidate in (payload, AIService._find_balanced_json_block(payload)):
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        regex_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", payload)
        if regex_match:
            candidate = regex_match.group(1)
            if candidate not in candidates:
                candidates.append(candidate)
        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                return AIService._parse_json_candidate(candidate)
            except (json.JSONDecodeError, SyntaxError, ValueError) as exc:
                last_error = exc
        preview = payload[:400].replace("\n", "\\n")
        logger.warning("AI JSON extraction failed. preview=%s", preview)
        if isinstance(last_error, json.JSONDecodeError):
            raise last_error
        raise json.JSONDecodeError("Unable to decode JSON response", payload, 0)
    @staticmethod
    async def _extract_or_repair_json(
        raw_text: str,
        schema_hint: str,
        ai_config: Optional[Dict] = None,
    ) -> Any:
        try:
            return AIService._extract_json(raw_text)
        except json.JSONDecodeError:
            logger.warning("AI JSON malformed, attempting one repair round")
            repaired = await AIService._chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You repair malformed structured output. "
                            "Return valid JSON only. "
                            "Do not add commentary or markdown fences."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Repair the following content into valid JSON.\n"
                            f"Required schema hint: {schema_hint}\n"
                            f"Original content:\n{raw_text}"
                        ),
                    },
                ],
                temperature=0,
                ai_config=ai_config,
            )
            return AIService._extract_json(repaired)
    @staticmethod
    def _normalize_panel_roles(panel_snapshot: Optional[Dict]) -> List[Dict]:
        raw_roles = (panel_snapshot or {}).get("roles") or []
        normalized = []
        for raw in raw_roles:
            role_key = raw.get("key") or raw.get("role_key") or raw.get("role")
            if not role_key:
                continue
            normalized.append(
                {
                    "role_key": role_key,
                    "role": PANEL_ROLE_ALIAS.get(role_key, role_key),
                    "name": raw.get("name") or role_key,
                    "focus": raw.get("focus") or raw.get("name") or role_key,
                }
            )
        return normalized or list(DEFAULT_PANEL_ROLES)
    @staticmethod
    def _string_or_empty(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
    @staticmethod
    def _string_list(value: Any, limit: int = 6) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, Sequence):
            items = list(value)
        else:
            items = [value]
        normalized = []
        for item in items:
            text = AIService._string_or_empty(item)
            if text:
                normalized.append(text)
        return normalized[:limit]
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    @staticmethod
    def _safe_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        return default
    @staticmethod
    def _collect_retrieved_slice_ids(
        knowledge_base: Optional[Dict] = None,
        question_plan: Optional[Sequence[Dict]] = None,
        question_meta: Optional[Dict] = None,
    ) -> List[int]:
        ordered_ids: List[int] = []
        def add_id(value: Any):
            try:
                slice_id = int(value)
            except (TypeError, ValueError):
                return
            if slice_id not in ordered_ids:
                ordered_ids.append(slice_id)
        for item in question_plan or []:
            for slice_item in item.get("selected_slices") or []:
                add_id(slice_item.get("slice_id"))
        for slice_item in (question_meta or {}).get("selected_slices") or []:
            add_id(slice_item.get("slice_id"))
        for slice_item in (knowledge_base or {}).get("slices") or []:
            add_id(slice_item.get("slice_id"))
        return ordered_ids
    @staticmethod
    def _build_panel_metadata(
        payload: Optional[Dict] = None,
        knowledge_base: Optional[Dict] = None,
        question_plan: Optional[Sequence[Dict]] = None,
        question_meta: Optional[Dict] = None,
    ) -> Dict:
        raw_metadata = (payload or {}).get("metadata") or {}
        return {
            "mode": raw_metadata.get("mode") or "panel",
            "version": raw_metadata.get("version") or PANEL_OUTPUT_VERSION,
            "retrieved_slice_ids": raw_metadata.get("retrieved_slice_ids")
            or AIService._collect_retrieved_slice_ids(
                knowledge_base=knowledge_base,
                question_plan=question_plan,
                question_meta=question_meta,
            ),
            "fallback_allowed": AIService._safe_bool(
                raw_metadata.get("fallback_allowed"),
                default=True,
            ),
        }

    @staticmethod
    def _build_single_evaluation_metadata(
        payload: Optional[Dict] = None,
        knowledge_base: Optional[Dict] = None,
        question_meta: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        retrieved_slice_ids = AIService._normalize_id_list(
            (payload or {}).get("retrieved_slice_ids")
            or (payload or {}).get("used_slice_ids")
            or (question_meta or {}).get("used_slice_ids")
        )
        if not retrieved_slice_ids:
            retrieved_slice_ids = AIService._collect_retrieved_slice_ids(
                knowledge_base=knowledge_base,
                question_meta=question_meta,
            )
        return {
            "mode": "single",
            "version": "single_evaluation_v1",
            "retrieved_slice_ids": retrieved_slice_ids,
            "fallback_allowed": True,
        }

    @staticmethod
    def _question_target_evidence_summary(question_meta: Optional[Dict]) -> List[str]:
        return AIService._string_list(
            (question_meta or {}).get("question_target_evidence")
            or (question_meta or {}).get("blueprint_evidence_summary")
            or (question_meta or {}).get("evidence_summary"),
            limit=4,
        )

    @staticmethod
    def _question_target_evidence_ids(question_meta: Optional[Dict]) -> List[int]:
        return AIService._normalize_id_list(
            (question_meta or {}).get("question_target_evidence_ids")
            or (question_meta or {}).get("blueprint_evidence_ids")
            or (question_meta or {}).get("used_slice_ids")
            or [
                item.get("slice_id")
                for item in ((question_meta or {}).get("selected_slices") or [])
                if item.get("slice_id")
            ],
            limit=8,
        )

    @staticmethod
    def _normalize_evidence_strength_delta(
        items: Any,
        question_meta: Optional[Dict],
        strengths: Sequence[str],
        gaps: Sequence[str],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        raw_items = items or []
        if isinstance(raw_items, (str, dict)):
            raw_items = [raw_items]

        default_summary = AIService._question_target_evidence_summary(question_meta)
        default_ids = AIService._question_target_evidence_ids(question_meta)
        fallback_evidence = default_summary[:1] or AIService._string_list(
            [
                (question_meta or {}).get("question_target_gap"),
                *((question_meta or {}).get("evaluation_focus") or []),
            ],
            limit=1,
        )

        for item in raw_items:
            if isinstance(item, dict):
                evidence = AIService._string_or_empty(
                    item.get("evidence")
                    or item.get("target")
                    or item.get("focus")
                    or item.get("claim")
                )
                delta = AIService._string_or_empty(item.get("delta") or item.get("change")) or "unchanged"
                reason = AIService._string_or_empty(item.get("reason") or item.get("summary"))
                source_ids = AIService._normalize_id_list(
                    item.get("source_ids") or item.get("evidence_source_ids") or item.get("slice_ids"),
                    limit=8,
                ) or default_ids
                source_summary = AIService._string_list(
                    item.get("source_summary") or item.get("evidence_source_summary"),
                    limit=4,
                ) or default_summary
            else:
                evidence = AIService._string_or_empty(item)
                delta = "unchanged"
                reason = ""
                source_ids = default_ids
                source_summary = default_summary
            if not evidence:
                continue
            normalized.append(
                {
                    "evidence": evidence,
                    "delta": delta,
                    "reason": reason,
                    "source_ids": source_ids,
                    "source_summary": source_summary,
                }
            )
            if len(normalized) >= 4:
                break

        if normalized:
            return normalized

        if not fallback_evidence:
            return []

        if strengths:
            delta = "strengthened"
            reason = strengths[0]
        elif gaps:
            delta = "insufficient"
            reason = gaps[0]
        else:
            delta = "unchanged"
            reason = "This round did not add enough new evidence."

        return [
            {
                "evidence": fallback_evidence[0],
                "delta": delta,
                "reason": reason,
                "source_ids": default_ids,
                "source_summary": default_summary,
            }
        ]

    @staticmethod
    def _normalize_claim_confidence_change(
        items: Any,
        question_meta: Optional[Dict],
        strengths: Sequence[str],
        unresolved_gaps: Sequence[str],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        raw_items = items or []
        if isinstance(raw_items, (str, dict)):
            raw_items = [raw_items]

        for item in raw_items:
            if isinstance(item, dict):
                claim = AIService._string_or_empty(
                    item.get("claim")
                    or item.get("target")
                    or item.get("statement")
                )
                from_level = AIService._string_or_empty(item.get("from_level") or item.get("before"))
                to_level = AIService._string_or_empty(item.get("to_level") or item.get("after"))
                change = AIService._string_or_empty(item.get("change") or item.get("delta"))
                reason = AIService._string_or_empty(item.get("reason") or item.get("summary"))
            else:
                claim = AIService._string_or_empty(item)
                from_level = ""
                to_level = ""
                change = ""
                reason = ""
            if not claim:
                continue
            normalized.append(
                {
                    "claim": claim,
                    "from_level": from_level or "weak",
                    "to_level": to_level or from_level or "weak",
                    "change": change or "unchanged",
                    "reason": reason,
                }
            )
            if len(normalized) >= 4:
                break

        if normalized:
            return normalized

        high_risk_claims = AIService._string_list(
            (question_meta or {}).get("blueprint_high_risk_claims"),
            limit=2,
        )
        if not high_risk_claims:
            return []

        weak_status = AIService._string_or_empty((question_meta or {}).get("blueprint_requirement_status"))
        from_level = "weak" if weak_status in {"weak", "unsupported"} else "moderate"
        if strengths and not unresolved_gaps:
            to_level = "moderate" if from_level == "weak" else "strong"
            change = "increased"
            reason = strengths[0]
        elif unresolved_gaps:
            to_level = from_level
            change = "unchanged"
            reason = unresolved_gaps[0]
        else:
            to_level = from_level
            change = "unchanged"
            reason = "No strong new evidence was added in this round."

        return [
            {
                "claim": high_risk_claims[0],
                "from_level": from_level,
                "to_level": to_level,
                "change": change,
                "reason": reason,
            }
        ]

    @staticmethod
    def _normalize_next_best_followup(
        payload: Any,
        question_meta: Optional[Dict],
        selected_followups: Sequence[str],
        unresolved_gaps: Sequence[str],
    ) -> Optional[Dict[str, Any]]:
        raw = payload or {}
        if isinstance(raw, str):
            raw = {"question": raw}
        if not isinstance(raw, dict):
            raw = {}

        question = AIService._string_or_empty(
            raw.get("question")
            or raw.get("followup")
            or raw.get("selected_question")
        )
        if not question and selected_followups:
            question = AIService._string_or_empty(selected_followups[0])
        if not question:
            return None

        target_gap = AIService._string_or_empty(raw.get("target_gap")) or (
            unresolved_gaps[0]
            if unresolved_gaps
            else AIService._string_or_empty((question_meta or {}).get("question_target_gap"))
        )
        target_evidence = AIService._string_list(raw.get("target_evidence"), limit=4) or AIService._question_target_evidence_summary(question_meta)
        evidence_source_ids = AIService._normalize_id_list(
            raw.get("evidence_source_ids")
            or raw.get("source_ids")
            or raw.get("slice_ids"),
            limit=8,
        ) or AIService._question_target_evidence_ids(question_meta)
        evidence_source_summary = AIService._string_list(
            raw.get("evidence_source_summary") or raw.get("source_summary"),
            limit=4,
        ) or target_evidence
        reason = AIService._string_or_empty(raw.get("reason"))
        if not reason:
            if evidence_source_summary:
                reason = (
                    f"继续围绕“{target_gap or '当前缺口'}”验证，当前主要证据来自："
                    + "；".join(evidence_source_summary[:2])
                )
            else:
                reason = (
                    f"继续围绕“{target_gap or '当前缺口'}”追问，当前证据仍不足，需要更具体的事实支持。"
                )

        return {
            "question": question,
            "reason": reason,
            "target_gap": target_gap or None,
            "target_evidence": target_evidence,
            "evidence_source_ids": evidence_source_ids,
            "evidence_source_summary": evidence_source_summary,
        }

    @staticmethod
    def _normalize_evidence_followup_fields(
        payload: Dict[str, Any],
        question_meta: Optional[Dict],
        selected_followups: Sequence[str],
        strengths: Sequence[str],
        gaps: Sequence[str],
        next_focus: str,
    ) -> Dict[str, Any]:
        unresolved_gaps = AIService._string_list(
            payload.get("unresolved_gaps") or gaps or ([next_focus] if next_focus else []),
            limit=4,
        )
        evidence_strength_delta = AIService._normalize_evidence_strength_delta(
            payload.get("evidence_strength_delta"),
            question_meta=question_meta,
            strengths=strengths,
            gaps=unresolved_gaps or gaps,
        )
        claim_confidence_change = AIService._normalize_claim_confidence_change(
            payload.get("claim_confidence_change"),
            question_meta=question_meta,
            strengths=strengths,
            unresolved_gaps=unresolved_gaps,
        )
        next_best_followup = AIService._normalize_next_best_followup(
            payload.get("next_best_followup")
            or (payload.get("moderator") or {}).get("next_best_followup"),
            question_meta=question_meta,
            selected_followups=selected_followups,
            unresolved_gaps=unresolved_gaps,
        )
        return {
            "evidence_strength_delta": evidence_strength_delta,
            "claim_confidence_change": claim_confidence_change,
            "unresolved_gaps": unresolved_gaps,
            "next_best_followup": next_best_followup,
        }

    @staticmethod
    def _normalize_single_evaluation_payload(
        payload: Dict,
        question_meta: Optional[Dict] = None,
        knowledge_base: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Evaluation payload is not an object")
        feedback = AIService._string_or_empty(payload.get("feedback"))
        if not feedback:
            raise ValueError("Evaluation payload is missing feedback")
        strengths = AIService._string_list(payload.get("strengths"))
        gaps = AIService._string_list(payload.get("gaps"))
        selected_followups = AIService._string_list(
            payload.get("selected_followups")
            or payload.get("followup_candidates")
            or (question_meta or {}).get("selected_followups")
        )
        next_focus = AIService._string_or_empty(payload.get("next_focus"))
        loop_fields = AIService._normalize_evidence_followup_fields(
            payload=payload,
            question_meta=question_meta,
            selected_followups=selected_followups,
            strengths=strengths,
            gaps=gaps,
            next_focus=next_focus,
        )
        return {
            "score": AIService._safe_float(payload.get("score"), default=5.0),
            "feedback": feedback,
            "follow_up": AIService._safe_bool(payload.get("follow_up"), default=bool(selected_followups)),
            "strengths": strengths,
            "gaps": gaps,
            "next_focus": next_focus,
            "selected_followups": selected_followups,
            "metadata": AIService._build_single_evaluation_metadata(
                payload=payload,
                knowledge_base=knowledge_base,
                question_meta=question_meta,
            ),
            **loop_fields,
        }
    @staticmethod
    def _build_panel_role_views(
        payload: Optional[Dict],
        panel_roles: Sequence[Dict],
        default_question_candidates: Optional[Sequence[str]] = None,
        default_followups: Optional[Sequence[str]] = None,
        default_evaluation_points: Optional[Sequence[str]] = None,
    ) -> List[Dict]:
        raw_items = []
        if isinstance(payload, dict):
            if isinstance(payload.get("panel"), list):
                raw_items = payload.get("panel") or []
            elif isinstance(payload.get("panel_views"), list):
                raw_items = payload.get("panel_views") or []
        role_map = {}
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            candidates = {
                raw.get("role"),
                raw.get("role_key"),
                PANEL_ROLE_ALIAS.get(raw.get("role"), raw.get("role")),
                PANEL_ROLE_ALIAS.get(raw.get("role_key"), raw.get("role_key")),
            }
            for candidate in candidates:
                if candidate:
                    role_map[str(candidate)] = raw
        normalized = []
        for role in panel_roles:
            raw = role_map.get(role["role_key"]) or role_map.get(role["role"]) or {}
            normalized.append(
                {
                    "role": role["role"],
                    "role_key": role["role_key"],
                    "focus": AIService._string_or_empty(raw.get("focus")) or role["focus"],
                    "question_candidates": AIService._string_list(
                        raw.get("question_candidates") or default_question_candidates
                    ),
                    "followup_candidates": AIService._string_list(
                        raw.get("followup_candidates") or default_followups
                    ),
                    "evaluation_points": AIService._string_list(
                        raw.get("evaluation_points") or default_evaluation_points
                    ),
                }
            )
        return normalized
    @staticmethod
    def _normalize_panel_question_payload(
        payload: Dict,
        question_plan: Sequence[Dict],
        knowledge_base: Optional[Dict] = None,
        panel_snapshot: Optional[Dict] = None,
    ) -> Dict:
        if not isinstance(payload, dict):
            raise ValueError("Panel payload is not an object")
        panel_roles = AIService._normalize_panel_roles(panel_snapshot)
        raw_moderator = payload.get("moderator") or {}
        raw_decisions = raw_moderator.get("selected_questions")
        if not isinstance(raw_decisions, list):
            raw_decisions = payload.get("questions") or []
        if not isinstance(raw_decisions, list):
            raise ValueError("Panel selected questions payload is not a list")
        base_panel = AIService._build_panel_role_views(
            payload=payload,
            panel_roles=panel_roles,
        )
        moderator_feedback_style = (
            AIService._string_or_empty(raw_moderator.get("feedback_style"))
            or AIService._string_or_empty(payload.get("moderator_style"))
        )
        moderator_difficulty_hint = AIService._string_or_empty(raw_moderator.get("difficulty_hint"))
        moderator_summary = AIService._string_or_empty(raw_moderator.get("reasoning_summary"))
        metadata = AIService._build_panel_metadata(
            payload=payload,
            knowledge_base=knowledge_base,
            question_plan=question_plan,
        )
        questions = []
        moderator_questions = []
        for index, plan in enumerate(question_plan):
            raw = raw_decisions[index] if index < len(raw_decisions) else {}
            if isinstance(raw, str):
                raw = {"selected_question": raw}
            if not isinstance(raw, dict):
                raise ValueError(f"Panel question decision #{index} is invalid")
            question_text = AIService._string_or_empty(
                raw.get("selected_question") or raw.get("question")
            )
            if not question_text:
                raise ValueError(f"Panel question decision #{index} is missing selected_question")
            selected_followups = AIService._string_list(
                raw.get("selected_followups") or raw.get("followup_candidates")
            )
            evaluation_points = AIService._string_list(
                raw.get("evaluation_points") or plan.get("evaluation_focus")
            )
            reasoning_summary = AIService._string_or_empty(
                raw.get("reasoning_summary")
                or raw.get("panel_reasoning_summary")
                or moderator_summary
            )
            used_slice_ids = raw.get("used_slice_ids") or raw.get("retrieved_slice_ids") or [
                item.get("slice_id") for item in (plan.get("selected_slices") or []) if item.get("slice_id")
            ]
            panel_views = AIService._build_panel_role_views(
                payload=payload,
                panel_roles=panel_roles,
                default_question_candidates=[question_text],
                default_followups=selected_followups,
                default_evaluation_points=evaluation_points,
            )
            panel_context = {
                "panel": panel_views,
                "moderator": {
                    "selected_question": question_text,
                    "selected_followups": selected_followups,
                    "reasoning_summary": reasoning_summary,
                    "feedback_style": moderator_feedback_style,
                    "difficulty_hint": AIService._string_or_empty(
                        raw.get("difficulty_hint") or moderator_difficulty_hint
                    ),
                },
                "metadata": {
                    **metadata,
                    "retrieved_slice_ids": used_slice_ids or metadata["retrieved_slice_ids"],
                },
            }
            question_item = {
                "index": index,
                "question": question_text,
                "category": raw.get("category") or plan.get("category"),
                "stage": raw.get("stage") or plan.get("stage"),
                "lead_role": raw.get("lead_role") or plan.get("lead_role"),
                "support_roles": raw.get("support_roles") or plan.get("support_roles") or [],
                "intent": raw.get("intent") or plan.get("intent"),
                "evaluation_focus": evaluation_points or plan.get("evaluation_focus") or [],
                "used_slice_ids": used_slice_ids or [],
                "selected_followups": selected_followups,
                "panel_reasoning_summary": reasoning_summary,
                "difficulty_hint": panel_context["moderator"]["difficulty_hint"],
                "panel_context": panel_context,
            }
            questions.append(question_item)
            moderator_questions.append(
                {
                    "index": index,
                    "selected_question": question_text,
                    "selected_followups": selected_followups,
                    "reasoning_summary": reasoning_summary,
                    "difficulty_hint": panel_context["moderator"]["difficulty_hint"],
                    "used_slice_ids": used_slice_ids or [],
                }
            )
        return {
            "panel": base_panel,
            "moderator": {
                "selected_questions": moderator_questions,
                "reasoning_summary": moderator_summary,
                "feedback_style": moderator_feedback_style,
                "difficulty_hint": moderator_difficulty_hint,
            },
            "metadata": metadata,
            "questions": questions,
            "moderator_style": moderator_feedback_style,
        }
    @staticmethod
    def _normalize_panel_evaluation_payload(
        payload: Dict,
        question_meta: Optional[Dict] = None,
        knowledge_base: Optional[Dict] = None,
        panel_snapshot: Optional[Dict] = None,
    ) -> Dict:
        if not isinstance(payload, dict):
            raise ValueError("Panel evaluation payload is not an object")
        panel_roles = AIService._normalize_panel_roles(panel_snapshot)
        raw_moderator = payload.get("moderator") or {}
        moderator_feedback = AIService._string_or_empty(
            raw_moderator.get("feedback") or payload.get("feedback")
        )
        if not moderator_feedback:
            raise ValueError("Panel evaluation payload is missing feedback")
        metadata = AIService._build_panel_metadata(
            payload=payload,
            knowledge_base=knowledge_base,
            question_meta=question_meta,
        )
        selected_followups = AIService._string_list(
            raw_moderator.get("selected_followups")
            or payload.get("selected_followups")
            or (question_meta or {}).get("selected_followups")
        )
        evaluation_points = AIService._string_list(
            payload.get("evaluation_points")
            or raw_moderator.get("evaluation_points")
            or (question_meta or {}).get("evaluation_focus")
        )
        reasoning_summary = AIService._string_or_empty(raw_moderator.get("reasoning_summary"))
        panel = AIService._build_panel_role_views(
            payload=payload,
            panel_roles=panel_roles,
            default_question_candidates=[(question_meta or {}).get("question")] if (question_meta or {}).get("question") else [],
            default_followups=selected_followups,
            default_evaluation_points=evaluation_points,
        )
        score = AIService._safe_float(raw_moderator.get("score") or payload.get("score"), default=5.0)
        strengths = AIService._string_list(payload.get("strengths"))
        gaps = AIService._string_list(payload.get("gaps"))
        moderator = {
            "selected_question": AIService._string_or_empty((question_meta or {}).get("question")),
            "selected_followups": selected_followups,
            "reasoning_summary": reasoning_summary,
            "feedback_style": AIService._string_or_empty(raw_moderator.get("feedback_style")),
            "difficulty_hint": AIService._string_or_empty(
                raw_moderator.get("difficulty_hint") or (question_meta or {}).get("difficulty_hint")
            ),
            "score": score,
            "feedback": moderator_feedback,
            "follow_up": AIService._safe_bool(
                raw_moderator.get("follow_up") if "follow_up" in raw_moderator else payload.get("follow_up"),
                default=False,
            ),
            "next_focus": AIService._string_or_empty(
                raw_moderator.get("next_focus") or payload.get("next_focus")
            ),
        }
        loop_fields = AIService._normalize_evidence_followup_fields(
            payload=payload,
            question_meta=question_meta,
            selected_followups=selected_followups,
            strengths=strengths,
            gaps=gaps,
            next_focus=moderator["next_focus"],
        )
        moderator["next_best_followup"] = loop_fields.get("next_best_followup")
        moderator["shared_evidence_ids"] = metadata.get("retrieved_slice_ids") or []
        moderator["shared_evidence_summary"] = AIService._question_target_evidence_summary(question_meta)
        return {
            "score": score,
            "feedback": moderator_feedback,
            "follow_up": moderator["follow_up"],
            "strengths": strengths,
            "gaps": gaps,
            "next_focus": moderator["next_focus"],
            "panel_views": [
                {
                    "role": item["role_key"],
                    "title": item.get("name") or item.get("role_key") or item.get("role"),
                    "summary": "; ".join(item["evaluation_points"] or item["followup_candidates"] or [item["focus"]]),
                    "shared_evidence_ids": metadata.get("retrieved_slice_ids") or [],
                    "shared_evidence_summary": AIService._question_target_evidence_summary(question_meta),
                }
                for item in panel
            ],
            "panel": panel,
            "moderator": moderator,
            "metadata": metadata,
            **loop_fields,
        }
    @staticmethod
    def _trim_text(value: Optional[str], limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."
    @staticmethod
    def _resume_snapshot(parsed_resume: dict) -> str:
        compact = {
            "name": parsed_resume.get("name"),
            "education": parsed_resume.get("education"),
            "skills": parsed_resume.get("skills", [])[:12],
            "experience": parsed_resume.get("experience", [])[:4],
            "projects": parsed_resume.get("projects", [])[:4],
            "summary": parsed_resume.get("summary"),
        }
        return json.dumps(compact, ensure_ascii=False)
    @staticmethod
    def _resume_text_chunks(parsed_resume: Optional[dict]) -> List[str]:
        resume = parsed_resume or {}
        chunks: List[str] = []
        for key in ("summary", "education"):
            text = AIService._string_or_empty(resume.get(key))
            if text:
                chunks.append(text)
        for key in ("skills", "experience", "projects"):
            for item in resume.get(key) or []:
                if isinstance(item, dict):
                    text = " ".join(
                        AIService._string_or_empty(value)
                        for value in item.values()
                        if AIService._string_or_empty(value)
                    ).strip()
                else:
                    text = AIService._string_or_empty(item)
                if text:
                    chunks.append(text)
        return chunks
    @staticmethod
    def _normalize_named_evidence_list(
        items: Any,
        name_key: str,
        evidence_key: str,
        limit: int = 8,
    ) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        seen = set()
        raw_items = items or []
        if isinstance(raw_items, (str, dict)):
            raw_items = [raw_items]
        for item in raw_items:
            if isinstance(item, dict):
                name = AIService._string_or_empty(
                    item.get(name_key)
                    or item.get("title")
                    or item.get("name")
                    or item.get("skill")
                    or item.get("metric")
                    or item.get("value")
                )
                evidence = AIService._string_or_empty(
                    item.get(evidence_key)
                    or item.get("evidence")
                    or item.get("description")
                    or item.get("detail")
                    or item.get("summary")
                    or item.get("claim")
                )
            else:
                name = AIService._string_or_empty(item)
                evidence = ""
            if not name:
                continue
            signature = (name, evidence)
            if signature in seen:
                continue
            seen.add(signature)
            normalized.append({name_key: name, evidence_key: evidence or name})
            if len(normalized) >= limit:
                break
        return normalized
    @staticmethod
    def _build_resume_evidence_summary(evidence: Dict[str, Any]) -> List[str]:
        summary: List[str] = []
        if evidence.get("projects"):
            summary.append(f"识别到 {len(evidence['projects'])} 个可追问项目证据点")
        if evidence.get("skills"):
            top_skills = "、".join(item.get("skill", "") for item in evidence["skills"][:3] if item.get("skill"))
            if top_skills:
                summary.append(f"核心技能证据集中在：{top_skills}")
        if evidence.get("metrics"):
            summary.append(f"发现 {len(evidence['metrics'])} 条量化结果或指标证据")
        if evidence.get("business_domain_terms"):
            summary.append("业务领域关键词：" + "、".join((evidence.get("business_domain_terms") or [])[:4]))
        if evidence.get("ambiguity_flags"):
            summary.append(f"存在 {len(evidence['ambiguity_flags'])} 处表述偏模糊，值得重点追问")
        if evidence.get("missing_evidence_flags"):
            summary.append(f"存在 {len(evidence['missing_evidence_flags'])} 个缺证据点，面试时需要重点核实")
        return summary[:6]
    @staticmethod
    def _normalize_resume_evidence(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Resume evidence payload is not an object")
        normalized = {
            "projects": AIService._normalize_named_evidence_list(payload.get("projects"), "title", "evidence", limit=6),
            "skills": AIService._normalize_named_evidence_list(payload.get("skills"), "skill", "evidence", limit=10),
            "metrics": AIService._normalize_named_evidence_list(payload.get("metrics"), "metric", "evidence", limit=8),
            "timeline_signals": AIService._string_list(payload.get("timeline_signals"), limit=8),
            "role_scope": AIService._string_list(payload.get("role_scope"), limit=8),
            "business_domain_terms": AIService._string_list(payload.get("business_domain_terms"), limit=10),
            "ambiguity_flags": AIService._string_list(payload.get("ambiguity_flags"), limit=8),
            "missing_evidence_flags": AIService._string_list(payload.get("missing_evidence_flags"), limit=8),
            "followup_candidates": AIService._string_list(payload.get("followup_candidates"), limit=10),
        }
        normalized["evidence_summary"] = AIService._string_list(payload.get("evidence_summary"), limit=6)
        if not normalized["evidence_summary"]:
            normalized["evidence_summary"] = AIService._build_resume_evidence_summary(normalized)
        return normalized
    @staticmethod
    def _normalize_id_list(values: Any, limit: int = 12) -> List[int]:
        ordered: List[int] = []
        for item in values or []:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value not in ordered:
                ordered.append(value)
            if len(ordered) >= limit:
                break
        return ordered
    @staticmethod
    def _normalize_blueprint_requirement_list(
        items: Any,
        support_level: str,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        raw_items = items or []
        if isinstance(raw_items, (str, dict)):
            raw_items = [raw_items]
        for item in raw_items:
            if isinstance(item, dict):
                requirement = AIService._string_or_empty(
                    item.get("requirement")
                    or item.get("title")
                    or item.get("focus")
                    or item.get("track")
                    or item.get("claim")
                )
                evidence = AIService._string_or_empty(
                    item.get("evidence")
                    or item.get("reason")
                    or item.get("summary")
                    or item.get("support")
                )
                evidence_ids = AIService._normalize_id_list(
                    item.get("evidence_ids") or item.get("slice_ids") or item.get("used_slice_ids")
                )
                source = AIService._string_or_empty(item.get("source")) or "resume_or_kb"
                effective_level = AIService._string_or_empty(item.get("support_level")) or support_level
            else:
                requirement = AIService._string_or_empty(item)
                evidence = ""
                evidence_ids = []
                source = "resume_or_kb"
                effective_level = support_level
            if not requirement:
                continue
            normalized.append(
                {
                    "requirement": requirement,
                    "evidence": evidence,
                    "support_level": effective_level,
                    "source": source,
                    "evidence_ids": evidence_ids,
                }
            )
            if len(normalized) >= limit:
                break
        return normalized
    @staticmethod
    def _normalize_high_risk_claims(items: Any, limit: int = 8) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        raw_items = items or []
        if isinstance(raw_items, (str, dict)):
            raw_items = [raw_items]
        for item in raw_items:
            if isinstance(item, dict):
                claim = AIService._string_or_empty(
                    item.get("claim")
                    or item.get("title")
                    or item.get("requirement")
                    or item.get("summary")
                )
                risk_reason = AIService._string_or_empty(
                    item.get("risk_reason")
                    or item.get("reason")
                    or item.get("why")
                    or item.get("evidence")
                )
                evidence = AIService._string_or_empty(
                    item.get("evidence")
                    or item.get("support")
                    or item.get("quote")
                )
                evidence_ids = AIService._normalize_id_list(
                    item.get("evidence_ids") or item.get("slice_ids") or item.get("used_slice_ids")
                )
            else:
                claim = AIService._string_or_empty(item)
                risk_reason = ""
                evidence = ""
                evidence_ids = []
            if not claim:
                continue
            normalized.append(
                {
                    "claim": claim,
                    "risk_reason": risk_reason,
                    "evidence": evidence,
                    "evidence_ids": evidence_ids,
                }
            )
            if len(normalized) >= limit:
                break
        return normalized
    @staticmethod
    def _normalize_blueprint_track_list(items: Any, limit: int = 6) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        raw_items = items or []
        if isinstance(raw_items, (str, dict)):
            raw_items = [raw_items]
        for item in raw_items:
            if isinstance(item, dict):
                track = AIService._string_or_empty(
                    item.get("track")
                    or item.get("title")
                    or item.get("requirement")
                    or item.get("focus")
                )
                reason = AIService._string_or_empty(
                    item.get("reason")
                    or item.get("why")
                    or item.get("evidence")
                    or item.get("summary")
                )
                requirement_status = AIService._string_or_empty(
                    item.get("requirement_status") or item.get("status")
                ) or "weak"
                evidence_ids = AIService._normalize_id_list(
                    item.get("evidence_ids") or item.get("slice_ids") or item.get("used_slice_ids")
                )
            else:
                track = AIService._string_or_empty(item)
                reason = ""
                requirement_status = "weak"
                evidence_ids = []
            if not track:
                continue
            normalized.append(
                {
                    "track": track,
                    "reason": reason,
                    "requirement_status": requirement_status,
                    "evidence_ids": evidence_ids,
                }
            )
            if len(normalized) >= limit:
                break
        return normalized
    @staticmethod
    def _build_interview_blueprint_summary(blueprint: Dict[str, Any]) -> List[str]:
        summary: List[str] = []
        if blueprint.get("matched_requirements"):
            summary.append(
                f"Matched requirements: {len(blueprint.get('matched_requirements') or [])}"
            )
        if blueprint.get("weakly_supported_requirements"):
            summary.append(
                f"Weak requirements: {len(blueprint.get('weakly_supported_requirements') or [])}"
            )
        if blueprint.get("unsupported_requirements"):
            summary.append(
                f"Unsupported requirements: {len(blueprint.get('unsupported_requirements') or [])}"
            )
        if blueprint.get("high_risk_claims"):
            summary.append(
                f"High-risk claims: {len(blueprint.get('high_risk_claims') or [])}"
            )
        if blueprint.get("training_focus"):
            summary.append(
                "Training focus: " + "; ".join((blueprint.get("training_focus") or [])[:3])
            )
        if blueprint.get("priority_question_tracks"):
            summary.append(
                "Priority tracks: "
                + "; ".join(
                    item.get("track", "")
                    for item in (blueprint.get("priority_question_tracks") or [])[:3]
                    if item.get("track")
                )
            )
        return summary[:6]
    @staticmethod
    def _normalize_interview_blueprint(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Interview blueprint payload is not an object")
        blueprint_evidence = payload.get("blueprint_evidence") or {}
        if not isinstance(blueprint_evidence, dict):
            blueprint_evidence = {}
        normalized = {
            "matched_requirements": AIService._normalize_blueprint_requirement_list(
                payload.get("matched_requirements"),
                support_level="strong",
                limit=8,
            ),
            "weakly_supported_requirements": AIService._normalize_blueprint_requirement_list(
                payload.get("weakly_supported_requirements"),
                support_level="weak",
                limit=8,
            ),
            "unsupported_requirements": AIService._normalize_blueprint_requirement_list(
                payload.get("unsupported_requirements"),
                support_level="unsupported",
                limit=8,
            ),
            "high_risk_claims": AIService._normalize_high_risk_claims(payload.get("high_risk_claims"), limit=8),
            "priority_question_tracks": AIService._normalize_blueprint_track_list(
                payload.get("priority_question_tracks"),
                limit=6,
            ),
            "training_focus": AIService._string_list(payload.get("training_focus"), limit=6),
            "blueprint_evidence": {
                "resume_evidence_summary": AIService._string_list(
                    blueprint_evidence.get("resume_evidence_summary") or blueprint_evidence.get("resume_summary"),
                    limit=6,
                ),
                "resume_followup_candidates": AIService._string_list(
                    blueprint_evidence.get("resume_followup_candidates")
                    or blueprint_evidence.get("followup_candidates"),
                    limit=6,
                ),
                "slice_ids": AIService._normalize_id_list(
                    blueprint_evidence.get("slice_ids") or blueprint_evidence.get("retrieved_slice_ids")
                ),
                "slice_summaries": AIService._string_list(
                    blueprint_evidence.get("slice_summaries") or blueprint_evidence.get("evidence_summary"),
                    limit=6,
                ),
                "knowledge_base_title": AIService._string_or_empty(blueprint_evidence.get("knowledge_base_title")),
                "target_position": AIService._string_or_empty(blueprint_evidence.get("target_position")),
            },
        }
        normalized["evidence_summary"] = AIService._string_list(payload.get("evidence_summary"), limit=6)
        if not normalized["evidence_summary"]:
            normalized["evidence_summary"] = AIService._build_interview_blueprint_summary(normalized)
        return normalized
    @staticmethod
    def build_resume_evidence_fallback(parsed_resume: Optional[dict]) -> Dict[str, Any]:
        resume = parsed_resume or {}
        text_chunks = AIService._resume_text_chunks(resume)
        projects = AIService._normalize_named_evidence_list(resume.get("projects"), "title", "evidence", limit=6)
        skills = AIService._normalize_named_evidence_list(resume.get("skills"), "skill", "evidence", limit=10)
        metrics: List[Dict[str, str]] = []
        seen_metrics = set()
        for chunk in text_chunks:
            for match in re.findall(r"\d+(?:\.\d+)?\s*(?:%|ms|秒|分钟|小时|天|周|月|年|万|千|百万|亿|k|K|w|W)", chunk):
                value = match.strip()
                if value in seen_metrics:
                    continue
                seen_metrics.add(value)
                metrics.append({"metric": value, "evidence": AIService._trim_text(chunk, 120)})
                if len(metrics) >= 8:
                    break
            if len(metrics) >= 8:
                break
        timeline_signals: List[str] = []
        role_scope: List[str] = []
        ambiguity_flags: List[str] = []
        seen_domains = set()
        business_domain_terms: List[str] = []
        for chunk in text_chunks:
            years = re.findall(r"(20\d{2}(?:\s*[-/~至到]\s*20\d{2}|年)?)", chunk)
            for year in years:
                text = year.strip()
                if text and text not in timeline_signals:
                    timeline_signals.append(text)
                    if len(timeline_signals) >= 8:
                        break
            lowered = chunk.lower()
            for term in RESUME_EVIDENCE_DOMAIN_TERMS:
                if term.lower() in lowered and term not in seen_domains:
                    seen_domains.add(term)
                    business_domain_terms.append(term)
            for term in RESUME_EVIDENCE_AMBIGUITY_TERMS:
                if term in chunk:
                    flag = AIService._trim_text(chunk, 120)
                    if flag and flag not in ambiguity_flags:
                        ambiguity_flags.append(flag)
                        if len(ambiguity_flags) >= 8:
                            break
            if any(keyword in chunk for keyword in ("负责", "主导", "带领", "设计", "推进", "落地", "优化")):
                scope = AIService._trim_text(chunk, 120)
                if scope and scope not in role_scope:
                    role_scope.append(scope)
        missing_evidence_flags: List[str] = []
        if not metrics:
            missing_evidence_flags.append("简历中缺少明确的量化结果或指标数据")
        if not projects:
            missing_evidence_flags.append("简历中缺少足够明确的项目证据")
        if not timeline_signals:
            missing_evidence_flags.append("简历中的时间线信号较弱，经历起止时间不够清晰")
        followup_candidates: List[str] = []
        for item in projects[:3]:
            followup_candidates.append(f"追问项目“{item['title']}”中的真实职责、技术决策与交付结果")
        for item in metrics[:2]:
            followup_candidates.append(f"追问指标“{item['metric']}”的口径、基线和候选人实际贡献")
        if ambiguity_flags:
            followup_candidates.append("追问表述模糊的经历，确认候选人是主导、负责还是参与支持")
        evidence = {
            "projects": projects,
            "skills": skills,
            "metrics": metrics,
            "timeline_signals": timeline_signals[:8],
            "role_scope": role_scope[:8],
            "business_domain_terms": business_domain_terms[:10],
            "ambiguity_flags": ambiguity_flags[:8],
            "missing_evidence_flags": missing_evidence_flags[:8],
            "followup_candidates": followup_candidates[:10],
        }
        evidence["evidence_summary"] = AIService._build_resume_evidence_summary(evidence)
        return evidence
    @staticmethod
    async def extract_resume_evidence(
        parsed_resume: dict,
        target_position: str,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a resume evidence extractor. Return pure JSON only. "
                    "Work strictly from the parsed resume JSON provided by the user. "
                    "Do not invent candidate experience, business context, metrics, project responsibilities, or timeline details. "
                    "If evidence is weak or missing, put the uncertainty into ambiguity_flags or missing_evidence_flags instead of filling fake details. "
                    "Schema: "
                    '{"projects":[{"title":"","evidence":""}],"skills":[{"skill":"","evidence":""}],'
                    '"metrics":[{"metric":"","evidence":""}],"timeline_signals":[""],"role_scope":[""],'
                    '"business_domain_terms":[""],"ambiguity_flags":[""],"missing_evidence_flags":[""],'
                    '"followup_candidates":[""],"evidence_summary":[""]}. '
                    "Reply in Simplified Chinese."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target position: {target_position}\n"
                    f"Parsed resume JSON: {AIService._resume_snapshot(parsed_resume)}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.2, ai_config=ai_config)
        payload = await AIService._extract_or_repair_json(
            result,
            'JSON object with keys: projects, skills, metrics, timeline_signals, role_scope, business_domain_terms, ambiguity_flags, missing_evidence_flags, followup_candidates, evidence_summary',
            ai_config=ai_config,
        )
        return AIService._normalize_resume_evidence(payload)
    @staticmethod
    def build_interview_blueprint_fallback(
        parsed_resume: Optional[dict],
        target_position: str,
        resume_evidence: Optional[dict] = None,
        knowledge_base: Optional[dict] = None,
        question_plan: Optional[Sequence[Dict]] = None,
    ) -> Dict[str, Any]:
        evidence = resume_evidence or {}
        matched_requirements: List[Dict[str, Any]] = []
        weak_requirements: List[Dict[str, Any]] = []
        unsupported_requirements: List[Dict[str, Any]] = []
        high_risk_claims: List[Dict[str, Any]] = []
        priority_question_tracks: List[Dict[str, Any]] = []

        slice_ids: List[int] = []
        slice_summaries: List[str] = []
        for item in question_plan or []:
            for slice_item in (item.get("selected_slices") or [])[:2]:
                try:
                    slice_id = int(slice_item.get("slice_id"))
                except (TypeError, ValueError):
                    slice_id = None
                if slice_id and slice_id not in slice_ids:
                    slice_ids.append(slice_id)
                title = AIService._string_or_empty(slice_item.get("title"))
                reason = AIService._string_list(slice_item.get("routing_reasons"), limit=2)
                if title:
                    summary = title if not reason else f"{title}: {'; '.join(reason)}"
                    if summary not in slice_summaries:
                        slice_summaries.append(summary)

        for item in (evidence.get("skills") or [])[:3]:
            matched_requirements.append(
                {
                    "requirement": f"Demonstrate {item.get('skill')} in role-relevant scenarios",
                    "evidence": item.get("evidence") or item.get("skill"),
                    "support_level": "strong",
                    "source": "resume_evidence",
                    "evidence_ids": slice_ids[:2],
                }
            )
        for item in (evidence.get("projects") or [])[:2]:
            matched_requirements.append(
                {
                    "requirement": f"Explain project delivery around {item.get('title')}",
                    "evidence": item.get("evidence") or item.get("title"),
                    "support_level": "strong",
                    "source": "resume_evidence",
                    "evidence_ids": slice_ids[:2],
                }
            )
        for item in (evidence.get("ambiguity_flags") or [])[:3]:
            weak_requirements.append(
                {
                    "requirement": item,
                    "evidence": "Resume evidence exists but is ambiguous and needs verification.",
                    "support_level": "weak",
                    "source": "resume_evidence",
                    "evidence_ids": slice_ids[:2],
                }
            )
            high_risk_claims.append(
                {
                    "claim": item,
                    "risk_reason": "The resume wording is ambiguous and can be challenged in follow-up questions.",
                    "evidence": item,
                    "evidence_ids": slice_ids[:2],
                }
            )
        for item in (evidence.get("missing_evidence_flags") or [])[:4]:
            unsupported_requirements.append(
                {
                    "requirement": item,
                    "evidence": "",
                    "support_level": "unsupported",
                    "source": "resume_gap",
                    "evidence_ids": [],
                }
            )
        for item in (evidence.get("followup_candidates") or [])[:4]:
            priority_question_tracks.append(
                {
                    "track": item,
                    "reason": "Resume evidence suggests this is worth probing early.",
                    "requirement_status": "weak",
                    "evidence_ids": slice_ids[:2],
                }
            )

        training_focus = AIService._string_list(
            [
                *(item.get("track") for item in priority_question_tracks if item.get("track")),
                *(item.get("requirement") for item in unsupported_requirements if item.get("requirement")),
                *(item.get("claim") for item in high_risk_claims if item.get("claim")),
            ],
            limit=6,
        )
        blueprint = {
            "matched_requirements": matched_requirements[:6],
            "weakly_supported_requirements": weak_requirements[:6],
            "unsupported_requirements": unsupported_requirements[:6],
            "high_risk_claims": high_risk_claims[:6],
            "priority_question_tracks": priority_question_tracks[:5],
            "training_focus": training_focus,
            "blueprint_evidence": {
                "resume_evidence_summary": AIService._string_list(
                    evidence.get("evidence_summary"),
                    limit=6,
                ),
                "resume_followup_candidates": AIService._string_list(
                    evidence.get("followup_candidates"),
                    limit=6,
                ),
                "slice_ids": slice_ids[:8],
                "slice_summaries": slice_summaries[:6],
                "knowledge_base_title": AIService._string_or_empty((knowledge_base or {}).get("title")),
                "target_position": target_position,
            },
        }
        blueprint["evidence_summary"] = AIService._build_interview_blueprint_summary(blueprint)
        return AIService._normalize_interview_blueprint(blueprint)
    @staticmethod
    async def extract_interview_blueprint(
        parsed_resume: dict,
        target_position: str,
        resume_evidence: Optional[dict] = None,
        knowledge_base: Optional[dict] = None,
        question_plan: Optional[Sequence[Dict]] = None,
        ai_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an interview blueprint planner for a mock interview system. "
                    "Return pure JSON only. "
                    "Stay grounded in the parsed resume, resume evidence, routed knowledge slices, and target position. "
                    "Do not invent candidate experience, ownership, metrics, or JD requirements that are unsupported. "
                    "If evidence is weak, put it into weakly_supported_requirements or unsupported_requirements. "
                    "Schema: "
                    '{"matched_requirements":[{"requirement":"","evidence":"","support_level":"strong","source":"resume_or_kb","evidence_ids":[1]}],'
                    '"weakly_supported_requirements":[{"requirement":"","evidence":"","support_level":"weak","source":"resume_or_kb","evidence_ids":[1]}],'
                    '"unsupported_requirements":[{"requirement":"","evidence":"","support_level":"unsupported","source":"resume_or_kb","evidence_ids":[]}],'
                    '"high_risk_claims":[{"claim":"","risk_reason":"","evidence":"","evidence_ids":[1]}],'
                    '"priority_question_tracks":[{"track":"","reason":"","requirement_status":"weak","evidence_ids":[1]}],'
                    '"training_focus":[""],'
                    '"blueprint_evidence":{"resume_evidence_summary":[""],"resume_followup_candidates":[""],"slice_ids":[1],"slice_summaries":[""],"knowledge_base_title":"","target_position":""},'
                    '"evidence_summary":[""]}. '
                    "Reply in Simplified Chinese."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target position: {target_position}\n"
                    f"Resume JSON: {AIService._resume_snapshot(parsed_resume)}\n"
                    f"Resume evidence JSON: {json.dumps(resume_evidence or {}, ensure_ascii=False)}\n"
                    f"{AIService._build_knowledge_base_context(knowledge_base)}\n"
                    f"{AIService._build_question_plan_context(question_plan)}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.25, ai_config=ai_config)
        payload = await AIService._extract_or_repair_json(
            result,
            "JSON object with matched_requirements, weakly_supported_requirements, unsupported_requirements, high_risk_claims, priority_question_tracks, training_focus, blueprint_evidence, evidence_summary",
            ai_config=ai_config,
        )
        return AIService._normalize_interview_blueprint(payload)
    @staticmethod
    def _history_text(chat_history: Sequence[Dict], limit: int = 6) -> str:
        lines = []
        for item in list(chat_history or [])[-limit:]:
            role = "Interviewer" if item.get("role") == "interviewer" else "Candidate"
            lines.append(f"{role}: {item.get('content', '')}")
        return "\n".join(lines)
    @staticmethod
    def _slice_line(item: Dict, limit: int = 220) -> str:
        stage = "/".join((item.get("stage_tags") or [])[:2]) or "-"
        role = "/".join((item.get("role_tags") or [])[:2]) or "-"
        scene = "/".join((item.get("scene_tags") or [])[:2]) or "-"
        confidence = item.get("grounding_confidence") or "unknown"
        warnings = ",".join((item.get("grounding_warnings") or [])[:2]) or "-"
        return (
            f"[slice#{item.get('slice_id', '?')}] "
            f"[{item.get('source_section') or item.get('slice_type') or 'knowledge'}] "
            f"[stage={stage}] [role={role}] [scene={scene}] "
            f"[grounding={confidence}] [warnings={warnings}] "
            f"{AIService._trim_text(item.get('content'), limit)}"
        )
    @staticmethod
    def _build_knowledge_base_context(
        knowledge_base: Optional[dict],
        selected_slices: Optional[Sequence[Dict]] = None,
        max_slices: int = 4,
    ) -> str:
        if not knowledge_base:
            return "No knowledge base selected. Rely on resume and target position only."
        lines = [
            "Knowledge base context is available. Use it to calibrate interview focus, but do not copy it verbatim.",
            f"Knowledge base title: {knowledge_base.get('title') or 'Untitled'}",
            f"Target position: {knowledge_base.get('target_position') or '-'}",
            f"Source scope: {knowledge_base.get('scope') or 'private'}",
        ]
        slices = list(selected_slices or [])
        if not slices:
            slices = list((knowledge_base.get("slices") or [])[:max_slices])
        if slices:
            lines.append("Top routed knowledge slices:")
            for item in slices[:max_slices]:
                lines.append(f"- {AIService._slice_line(item)}")
            return "\n".join(lines)
        knowledge_content = AIService._trim_text(knowledge_base.get("knowledge_content"), 2200)
        focus_points = AIService._trim_text(knowledge_base.get("focus_points"), 1200)
        interviewer_prompt = AIService._trim_text(knowledge_base.get("interviewer_prompt"), 1200)
        if knowledge_content:
            lines.append(f"Knowledge content: {knowledge_content}")
        if focus_points:
            lines.append(f"Focus points: {focus_points}")
        if interviewer_prompt:
            lines.append(f"Interviewer guidance: {interviewer_prompt}")
        return "\n".join(lines)
    @staticmethod
    def _build_grounding_rules(
        task: str,
        has_routed_evidence: bool = False,
        has_report_evidence: bool = False,
    ) -> str:
        rules = [
            "Grounding rules:",
            "- Do not invent candidate experience, metrics, incidents, architecture details, business impact, or project facts.",
            "- Treat the resume, routed slices, chat history, and answer content as the only trusted evidence sources.",
            "- Position knowledge and routed RAG slices calibrate what to ask; they are not proof that the candidate has that experience or skill.",
            "- Low-confidence routed evidence must be phrased as a verification target, not as a factual conclusion.",
        ]
        if task in {"question", "panel_question"}:
            rules.extend(
                [
                    "- If evidence is insufficient, ask a broader but still realistic interview question instead of a highly specific one.",
                    "- Prefer clarification or scoped follow-up over pretending you already know hidden details.",
                ]
            )
            if has_routed_evidence:
                rules.append("- Use routed evidence as the first calibration source for topic, depth, and follow-up direction.")
            else:
                rules.append("- No routed evidence is guaranteed. Avoid assuming project details not clearly present in the resume.")
        elif task in {"evaluation", "panel_evaluation"}:
            rules.extend(
                [
                    "- Distinguish 'the candidate did not provide enough evidence/details' from 'the candidate definitely lacks this ability'.",
                    "- If the answer lacks proof, score and feedback should say the evidence is insufficient instead of making hard claims.",
                    "- Do not correct the candidate with invented implementation details that are absent from the answer or routed evidence.",
                    "- When evidence is still weak, keep unresolved_gaps and next_best_followup conservative, and prefer clarification over hard judgment.",
                ]
            )
            if has_routed_evidence:
                rules.append("- When routed evidence exists, use it to judge relevance, but do not claim the candidate said more than they actually said.")
        elif task in {"report", "panel_report"}:
            rules.extend(
                [
                    "- Summarize only what can be supported by interview records and aggregated evidence signals.",
                    "- If evidence is weak, explicitly describe it as insufficient evidence instead of giving overconfident conclusions.",
                    "- Training advice should stay close to repeated gaps, routed evidence, and actual interview performance.",
                ]
            )
            if has_report_evidence:
                rules.append("- Preserve evidence-backed highlights and keep them consistent with the retrieved evidence summary.")
            else:
                rules.append("- If report evidence is sparse, keep conclusions conservative and avoid over-specific diagnosis.")
        return "\n".join(rules)
    @staticmethod
    def _build_question_plan_context(question_plan: Optional[Sequence[Dict]]) -> str:
        if not question_plan:
            return ""
        lines = ["Question plan and routed slices:"]
        for item in question_plan:
            lines.append(
                f"- Plan #{item.get('index', 0)}: "
                f"stage={item.get('stage')}, category={item.get('category')}, "
                f"lead_role={item.get('lead_role')}, support_roles={','.join(item.get('support_roles') or []) or '-'}"
            )
            lines.append(f"  intent: {item.get('intent')}")
            evaluation_focus = item.get("evaluation_focus") or []
            if evaluation_focus:
                lines.append(f"  evaluation_focus: {', '.join(evaluation_focus)}")
            if item.get("blueprint_track"):
                lines.append(
                    f"  blueprint_track: {item.get('blueprint_track')} ({item.get('blueprint_requirement_status') or 'weak'})"
                )
            if item.get("blueprint_evidence_summary"):
                lines.append(
                    "  blueprint_evidence: "
                    + " | ".join((item.get("blueprint_evidence_summary") or [])[:2])
                )
            for slice_item in (item.get("selected_slices") or [])[:3]:
                lines.append(f"  routed_slice: {AIService._slice_line(slice_item, limit=180)}")
        return "\n".join(lines)
    @staticmethod
    def _build_interview_blueprint_context(interview_blueprint: Optional[Dict]) -> str:
        if not interview_blueprint:
            return ""
        lines = ["Interview blueprint:"]
        training_focus = AIService._string_list((interview_blueprint or {}).get("training_focus"), limit=4)
        if training_focus:
            lines.append(f"- Training focus: {', '.join(training_focus)}")
        for key, label in (
            ("matched_requirements", "Matched requirements"),
            ("weakly_supported_requirements", "Weakly supported requirements"),
            ("unsupported_requirements", "Unsupported requirements"),
        ):
            items = (interview_blueprint or {}).get(key) or []
            if items:
                formatted = []
                for item in items[:3]:
                    if isinstance(item, dict):
                        requirement = AIService._string_or_empty(item.get("requirement"))
                        evidence = AIService._string_or_empty(item.get("evidence"))
                        if requirement:
                            formatted.append(requirement if not evidence else f"{requirement} ({evidence})")
                    else:
                        text = AIService._string_or_empty(item)
                        if text:
                            formatted.append(text)
                if formatted:
                    lines.append(f"- {label}: {'; '.join(formatted)}")
        high_risk_claims = []
        for item in (interview_blueprint or {}).get("high_risk_claims") or []:
            if isinstance(item, dict):
                text = AIService._string_or_empty(item.get("claim"))
            else:
                text = AIService._string_or_empty(item)
            if text:
                high_risk_claims.append(text)
        if high_risk_claims:
            lines.append(f"- High-risk claims: {', '.join(high_risk_claims[:3])}")
        priority_tracks = []
        for item in (interview_blueprint or {}).get("priority_question_tracks") or []:
            if isinstance(item, dict):
                text = AIService._string_or_empty(item.get("track"))
            else:
                text = AIService._string_or_empty(item)
            if text:
                priority_tracks.append(text)
        if priority_tracks:
            lines.append(f"- Priority tracks: {', '.join(priority_tracks[:3])}")
        blueprint_evidence = (interview_blueprint or {}).get("blueprint_evidence") or {}
        if blueprint_evidence.get("slice_ids"):
            lines.append(
                "- Blueprint slice ids: "
                + ", ".join(str(item) for item in blueprint_evidence.get("slice_ids")[:6])
            )
        if blueprint_evidence.get("slice_summaries"):
            lines.append("- Blueprint evidence highlights:")
            for item in blueprint_evidence.get("slice_summaries")[:3]:
                lines.append(f"  - {item}")
        return "\n".join(lines)
    @staticmethod
    def _build_question_blueprint_context(question_meta: Optional[Dict]) -> str:
        if not question_meta:
            return ""
        lines = []
        track = AIService._string_or_empty((question_meta or {}).get("blueprint_track"))
        if track:
            lines.append(f"Blueprint track: {track}")
        status = AIService._string_or_empty((question_meta or {}).get("blueprint_requirement_status"))
        if status:
            lines.append(f"Requirement status: {status}")
        evidence_summary = AIService._string_list((question_meta or {}).get("blueprint_evidence_summary"), limit=3)
        if evidence_summary:
            lines.append(f"Blueprint evidence: {'; '.join(evidence_summary)}")
        target_gap = AIService._string_or_empty((question_meta or {}).get("question_target_gap"))
        if target_gap:
            lines.append(f"Question target gap: {target_gap}")
        target_evidence = AIService._string_list((question_meta or {}).get("question_target_evidence"), limit=3)
        if target_evidence:
            lines.append(f"Question target evidence: {'; '.join(target_evidence)}")
        question_reason = AIService._string_or_empty((question_meta or {}).get("question_reason"))
        if question_reason:
            lines.append(f"Question reason: {question_reason}")
        return "\n".join(lines)
    @staticmethod
    def _build_panel_context(panel_snapshot: Optional[Dict]) -> str:
        if not panel_snapshot or panel_snapshot.get("mode") != "panel":
            return "Single interviewer mode."
        lines = [
            "Internal panel mode is enabled.",
            f"Moderator name: {panel_snapshot.get('moderator_name') or '主持人'}",
            "Internal roles:",
        ]
        for role in panel_snapshot.get("roles") or []:
            lines.append(
                f"- {role.get('key')}: {role.get('name')} | focus={role.get('focus')}"
            )
        return "\n".join(lines)
    @staticmethod
    def _build_report_signal_context(report_signals: Optional[Dict]) -> str:
        if not report_signals:
            return ""
        lines = ["Aggregated interview signals:"]
        if report_signals.get("common_gaps"):
            lines.append(f"- Common gaps: {', '.join(report_signals.get('common_gaps') or [])}")
        if report_signals.get("common_strengths"):
            lines.append(f"- Common strengths: {', '.join(report_signals.get('common_strengths') or [])}")
        if report_signals.get("training_priorities"):
            lines.append(
                f"- Training priorities: {', '.join(report_signals.get('training_priorities') or [])}"
            )
        if report_signals.get("followup_loop_summary"):
            lines.append("- Follow-up loop highlights:")
            for item in report_signals.get("followup_loop_summary") or []:
                lines.append(f"- {item}")
        if report_signals.get("claim_confidence_summary"):
            lines.append("- Claim confidence changes:")
            for item in report_signals.get("claim_confidence_summary") or []:
                lines.append(f"- {item}")
        if report_signals.get("retrieved_slice_ids"):
            lines.append(
                f"- Retrieved slice ids: {', '.join(str(item) for item in report_signals.get('retrieved_slice_ids') or [])}"
            )
        if report_signals.get("grounding_confidence_summary"):
            summary = report_signals.get("grounding_confidence_summary") or {}
            counts = summary.get("counts") or {}
            warnings = summary.get("warnings") or []
            lines.append(
                "- Grounding confidence: "
                f"high={counts.get('high', 0)}, medium={counts.get('medium', 0)}, "
                f"low={counts.get('low', 0)}"
            )
            if warnings:
                lines.append(f"- Grounding warnings: {', '.join(warnings[:4])}")
        if report_signals.get("evidence_stats"):
            stats = report_signals.get("evidence_stats") or {}
            lines.append(
                "- Evidence coverage: "
                f"{stats.get('questions_with_evidence', 0)}/{stats.get('total_questions', 0)} questions, "
                f"{stats.get('retrieved_slice_count', 0)} unique slices"
            )
        if report_signals.get("evidence_summary"):
            lines.append("Evidence highlights:")
            for item in report_signals.get("evidence_summary") or []:
                lines.append(f"- {item}")
        if report_signals.get("panel_summary"):
            lines.append("Panel summaries:")
            for item in report_signals.get("panel_summary") or []:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('role')}: {item.get('summary') or item.get('title') or ''}"
                    )
        return "\n".join(lines)
    @staticmethod
    def _normalize_question_array(payload: Any) -> List[Dict]:
        if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
            payload = payload["questions"]
        if not isinstance(payload, list):
            raise ValueError("Question payload is not a list")
        normalized = []
        for index, item in enumerate(payload):
            if isinstance(item, str):
                normalized.append({"index": index, "question": item, "category": "technical"})
                continue
            if isinstance(item, dict):
                normalized.append(item)
        if not normalized:
            raise ValueError("Question payload is empty")
        return normalized
    @staticmethod
    async def parse_resume(resume_text: str, ai_config: Optional[Dict] = None) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert resume parser. Return pure JSON only. "
                    "Extract: name, education, skills, experience, projects, summary. "
                    "Keep skills/experience/projects as arrays. "
                    "Do not invent candidate experience, metrics, project details, or business context that are absent from the resume text. "
                    "If the source text is ambiguous, preserve the ambiguity instead of making it more specific. "
                    "Reply in Simplified Chinese when text needs summarization."
                ),
            },
            {
                "role": "user",
                "content": f"Resume text:\n{resume_text}",
            },
        ]
        result = await AIService._chat(messages, temperature=0.2, ai_config=ai_config)
        try:
            payload = await AIService._extract_or_repair_json(
                result,
                'JSON object with keys: name, education, skills, experience, projects, summary',
                ai_config=ai_config,
            )
        except json.JSONDecodeError as exc:
            logger.warning("Resume parse JSON malformed after repair, using deterministic fallback: %s", exc)
            return AIService.build_resume_parse_fallback(resume_text)
        return AIService._normalize_parsed_resume(payload, source_text=resume_text)

    @staticmethod
    def _resume_value_to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            preferred_keys = (
                "title",
                "name",
                "school",
                "major",
                "degree",
                "company",
                "role",
                "position",
                "skill",
                "evidence",
                "description",
                "summary",
                "content",
                "details",
                "technologies",
                "result",
            )
            parts = [
                AIService._resume_value_to_text(value.get(key))
                for key in preferred_keys
                if value.get(key) is not None
            ]
            if not parts:
                parts = [AIService._resume_value_to_text(item) for item in list(value.values())[:8]]
            return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()
        if isinstance(value, (list, tuple, set)):
            return re.sub(
                r"\s+",
                " ",
                " ".join(
                    part
                    for part in (AIService._resume_value_to_text(item) for item in value)
                    if part
                ),
            ).strip()
        return str(value).strip()

    @staticmethod
    def _normalize_resume_list(value: Any, limit: int = 8) -> List[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        normalized: List[str] = []
        seen = set()
        for item in raw_items:
            text = AIService._resume_value_to_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
            if len(normalized) >= limit:
                break
        return normalized

    @staticmethod
    def _normalize_parsed_resume(payload: Any, source_text: str = "") -> Dict[str, Any]:
        if not isinstance(payload, dict):
            fallback = AIService.build_resume_parse_fallback(source_text)
            fallback["summary"] = fallback.get("summary") or "AI 返回的简历解析结果不是对象结构，已使用文本兜底解析。"
            return fallback

        fallback = AIService.build_resume_parse_fallback(source_text) if source_text else {}
        normalized = {
            "name": AIService._resume_value_to_text(payload.get("name")) or fallback.get("name", ""),
            "education": AIService._resume_value_to_text(payload.get("education")) or fallback.get("education", ""),
            "skills": AIService._normalize_resume_list(payload.get("skills"), limit=16) or fallback.get("skills", []),
            "experience": AIService._normalize_resume_list(payload.get("experience"), limit=8)
            or fallback.get("experience", []),
            "projects": AIService._normalize_resume_list(payload.get("projects"), limit=8)
            or fallback.get("projects", []),
            "summary": AIService._resume_value_to_text(payload.get("summary")) or fallback.get("summary", ""),
        }
        if not normalized["summary"]:
            evidence_parts = [normalized["education"], *normalized["skills"][:5], *normalized["projects"][:2]]
            normalized["summary"] = AIService._trim_text("；".join(part for part in evidence_parts if part), 260)
        return normalized

    @staticmethod
    def _extract_resume_section(text: str, start_markers: Sequence[str], end_markers: Sequence[str]) -> str:
        start_index = -1
        for marker in start_markers:
            index = text.find(marker)
            if index >= 0 and (start_index < 0 or index < start_index):
                start_index = index + len(marker)
        if start_index < 0:
            return ""
        end_index = len(text)
        for marker in end_markers:
            index = text.find(marker, start_index)
            if index >= 0:
                end_index = min(end_index, index)
        return text[start_index:end_index].strip()

    @staticmethod
    def _split_resume_section_items(section: str, limit: int = 6) -> List[str]:
        if not section:
            return []
        lines = [line.strip(" ｜|/-\t") for line in section.splitlines() if line.strip(" ｜|/-\t")]
        items: List[str] = []
        current: List[str] = []
        date_pattern = re.compile(r"(?:19|20)\d{2}\.\d{1,2}\s*[-~至到]\s*(?:19|20)\d{2}\.\d{1,2}|(?:19|20)\d{2}")
        for line in lines:
            starts_new = bool(date_pattern.search(line)) and current
            if starts_new:
                items.append(AIService._trim_text(" ".join(current), 360))
                current = [line]
            else:
                current.append(line)
        if current:
            items.append(AIService._trim_text(" ".join(current), 360))
        if not items:
            compact = re.sub(r"\s+", " ", section).strip()
            return [AIService._trim_text(compact, 360)] if compact else []
        return [item for item in items if item][:limit]

    @staticmethod
    def build_resume_parse_fallback(resume_text: str) -> Dict[str, Any]:
        text = (resume_text or "").replace("\r", "\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        compact = re.sub(r"\s+", " ", text).strip()

        name = ""
        for line in lines[:8]:
            if "@" in line or re.search(r"\d{5,}", line):
                continue
            if 1 < len(line) <= 24:
                name = line
                break

        education_section = AIService._extract_resume_section(
            text,
            ("教育经历", "教育背景"),
            ("项目经历", "工作经历", "实习经历", "获奖经历", "技能", "校园经历"),
        )
        project_section = AIService._extract_resume_section(
            text,
            ("项目经历", "项目经验"),
            ("获奖经历", "工作经历", "实习经历", "技能", "校园经历", "教育经历"),
        )
        experience_section = AIService._extract_resume_section(
            text,
            ("工作经历", "实习经历", "校园经历"),
            ("项目经历", "获奖经历", "技能", "教育经历"),
        )

        skill_terms = [
            "Python",
            "Java",
            "JavaScript",
            "TypeScript",
            "SQL",
            "MySQL",
            "PostgreSQL",
            "Redis",
            "Docker",
            "FastAPI",
            "Django",
            "Flask",
            "Streamlit",
            "JSON",
            "OCR",
            "pypdf",
            "python-docx",
            "pytesseract",
            "pdf2image",
            "Pillow",
            "Excel",
            "产品",
            "需求拆解",
            "流程梳理",
            "规则设计",
            "数据整理",
        ]
        lowered = compact.lower()
        skills = []
        for term in skill_terms:
            if term.lower() in lowered and term not in skills:
                skills.append(term)

        projects = AIService._split_resume_section_items(project_section, limit=6)
        experience = AIService._split_resume_section_items(experience_section, limit=6)
        education = AIService._trim_text(re.sub(r"\s+", " ", education_section).strip(), 260)

        summary_parts = []
        if education:
            summary_parts.append(education)
        if skills:
            summary_parts.append("技能线索：" + "、".join(skills[:8]))
        if projects:
            summary_parts.append("项目线索：" + projects[0])

        return {
            "name": name,
            "education": education,
            "skills": skills[:16],
            "experience": experience,
            "projects": projects,
            "summary": AIService._trim_text("；".join(summary_parts) or compact, 360),
        }

    @staticmethod
    async def analyze_resume(
        parsed_resume: dict,
        target_position: str,
        resume_evidence: Optional[dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        evidence_snapshot = json.dumps(
            {
                "evidence_summary": (resume_evidence or {}).get("evidence_summary", []),
                "ambiguity_flags": (resume_evidence or {}).get("ambiguity_flags", []),
                "missing_evidence_flags": (resume_evidence or {}).get("missing_evidence_flags", []),
                "followup_candidates": (resume_evidence or {}).get("followup_candidates", []),
            },
            ensure_ascii=False,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior recruiter and interview coach. "
                    "Analyze the resume for the target role and return pure JSON only. "
                    "Stay grounded in the parsed resume and resume evidence only. "
                    "Do not invent candidate experience, project ownership, metrics, or business outcomes. "
                    "If evidence is weak, describe it as insufficient or ambiguous instead of making hard claims. "
                    "Schema: "
                    '{"overall_score":7.5,"strengths":[""],"weaknesses":[""],'
                    '"suggestions":[""],"keyword_match":[""],"missing_keywords":[""],"summary":""}. '
                    "Reply in Simplified Chinese."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target position: {target_position}\n"
                    f"Parsed resume JSON: {json.dumps(parsed_resume, ensure_ascii=False)}\n"
                    f"Resume evidence JSON: {evidence_snapshot}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.4, ai_config=ai_config)
        return await AIService._extract_or_repair_json(
            result,
            'JSON object with keys: overall_score, strengths, weaknesses, suggestions, keyword_match, missing_keywords, summary',
            ai_config=ai_config,
        )

    @staticmethod
    def _normalize_resume_polish_payload(
        payload: Any,
        target_position: str,
        analysis: Optional[Dict],
        polish_mode: str,
        knowledge_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        analysis = analysis or {}
        knowledge_context = knowledge_context if isinstance(knowledge_context, dict) else {}
        knowledge_sources = []
        for source in knowledge_context.get("sources") or []:
            if not isinstance(source, dict):
                continue
            knowledge_sources.append(
                {
                    "title": AIService._string_or_empty(source.get("title")),
                    "target_position": AIService._string_or_empty(source.get("target_position")),
                    "scope": AIService._string_or_empty(source.get("scope")),
                    "is_member_submission": bool(source.get("is_member_submission")),
                }
            )
            if len(knowledge_sources) >= 3:
                break
        evaluation_snapshot = snapshot_from_payload(analysis)
        metrics = analysis.get("matching_metrics") or {}
        ability_profile = evaluation_snapshot.get("ability_profile") or analysis.get("ability_gap_profile") or metrics.get("ability_gap_profile") or {}
        top_gaps = ability_profile.get("top_gaps") or ability_profile.get("items") or []
        if not isinstance(top_gaps, list):
            top_gaps = []

        baseline = data.get("baseline") if isinstance(data.get("baseline"), dict) else {}
        baseline.update(
            {
                "target_position": target_position,
                "final_score": (evaluation_snapshot.get("scores") or {}).get("final_score", metrics.get("final_score", analysis.get("final_score"))),
                "keyword_coverage": (evaluation_snapshot.get("scores") or {}).get("keyword_coverage", metrics.get("keyword_coverage", analysis.get("keyword_coverage"))),
                "semantic_score": (evaluation_snapshot.get("scores") or {}).get("semantic_score", metrics.get("semantic_score", analysis.get("semantic_score"))),
                "rule_score": (evaluation_snapshot.get("scores") or {}).get("rule_score", metrics.get("rule_score", analysis.get("rule_score"))),
            }
        )

        suggestions: List[Dict[str, Any]] = []
        raw_suggestions = (
            data.get("section_suggestions")
            or data.get("suggestions")
            or data.get("polish_suggestions")
            or []
        )
        if isinstance(raw_suggestions, dict):
            raw_suggestions = [raw_suggestions]
        if isinstance(raw_suggestions, str):
            raw_suggestions = [{"section": "整体表达", "issue": raw_suggestions}]

        for item in raw_suggestions or []:
            if isinstance(item, str):
                item = {"section": "整体表达", "issue": item}
            if not isinstance(item, dict):
                continue
            section = AIService._string_or_empty(item.get("section") or item.get("title")) or "简历表达"
            issue = AIService._string_or_empty(item.get("issue") or item.get("problem") or item.get("reason"))
            rewritten = AIService._string_or_empty(
                item.get("rewritten_text")
                or item.get("rewrite")
                or item.get("polished_text")
                or item.get("suggestion")
            )
            if not issue and not rewritten:
                continue
            suggestions.append(
                {
                    "section": section,
                    "issue": issue,
                    "evidence_basis": AIService._string_or_empty(
                        item.get("evidence_basis") or item.get("evidence") or item.get("basis")
                    ),
                    "rewrite_strategy": AIService._string_or_empty(
                        item.get("rewrite_strategy") or item.get("strategy")
                    ),
                    "rewritten_text": rewritten,
                    "risk_level": AIService._string_or_empty(item.get("risk_level")) or "medium",
                    "risk_note": AIService._string_or_empty(item.get("risk_note") or item.get("warning")),
                }
            )
            if len(suggestions) >= 8:
                break

        if not suggestions:
            for gap in top_gaps[:5]:
                if not isinstance(gap, dict):
                    continue
                ability_name = AIService._string_or_empty(gap.get("name") or gap.get("ability_name")) or "岗位能力"
                evidence_status = AIService._string_or_empty(gap.get("evidence_status")) or "missing"
                suggestions.append(
                    {
                        "section": ability_name,
                        "issue": "当前简历对该岗位能力的证据不足。",
                        "evidence_basis": AIService._string_or_empty(gap.get("evidence_basis")),
                        "rewrite_strategy": "补充可验证项目、职责边界、产出和指标；没有真实经历时只能写待补充证据。",
                        "rewritten_text": f"- {ability_name}：[补充真实项目/课程/实习中的具体做法、工具、结果或数据，不能虚构经历]",
                        "risk_level": "high" if evidence_status in {"missing", "claimed_only"} else "medium",
                        "risk_note": "该能力需要进一步补充真实证据或通过面试验证。",
                    }
                )

        warnings = AIService._string_list(
            data.get("risk_warnings") or data.get("warnings") or data.get("do_not_add_claims"),
            limit=8,
        )
        default_warning = "不得新增原简历中不存在的公司、项目、时间、技术栈、指标或职责。"
        if default_warning not in warnings:
            warnings.insert(0, default_warning)
        knowledge_warning = (
            "岗位知识库只用于岗位要求和表达方向，不能写成候选人的真实经历。"
        )
        if knowledge_sources and knowledge_warning not in warnings:
            warnings.insert(1, knowledge_warning)

        keyword_alignment = data.get("keyword_alignment")
        if not isinstance(keyword_alignment, list):
            keyword_alignment = []

        polished_markdown = AIService._string_or_empty(
            data.get("polished_resume_markdown")
            or data.get("final_resume_markdown")
            or data.get("markdown")
        )
        if not polished_markdown:
            lines = [
                f"# 面向「{target_position}」的简历润色稿",
                "",
                "> 说明：以下内容只基于原简历和岗位要求改写；方括号内容需要用户补充真实证据后才能使用。",
                "",
            ]
            for item in suggestions:
                lines.append(f"## {item['section']}")
                if item.get("rewritten_text"):
                    lines.append(item["rewritten_text"])
                if item.get("risk_note"):
                    lines.append(f"> 风险提示：{item['risk_note']}")
                lines.append("")
            polished_markdown = "\n".join(lines).strip()

        return {
            "version": "resume_polish_v1",
            "polish_mode": polish_mode or "job_aligned",
            "target_position": target_position,
            "baseline": baseline,
            "overall_strategy": AIService._string_or_empty(data.get("overall_strategy"))
            or "围绕岗位评分逻辑强化证据表达，并保留待验证能力的边界。",
            "section_suggestions": suggestions,
            "keyword_alignment": keyword_alignment[:12],
            "knowledge_context_summary": {
                "source_count": len(knowledge_sources),
                "source_titles": [item.get("title") for item in knowledge_sources if item.get("title")],
                "member_submission_used": any(item.get("is_member_submission") for item in knowledge_sources),
                "usage_rule": knowledge_context.get("usage_rule")
                or "岗位知识库只用于岗位要求和表达方向，不能写成候选人真实经历。",
            },
            "knowledge_sources": knowledge_sources,
            "risk_warnings": warnings[:8],
            "missing_evidence_to_prepare": AIService._string_list(
                data.get("missing_evidence_to_prepare") or data.get("missing_evidence"),
                limit=8,
            ),
            "polished_resume_markdown": polished_markdown,
        }

    @staticmethod
    async def polish_resume(
        parsed_resume: dict,
        analysis: dict,
        target_position: str,
        resume_evidence: Optional[dict] = None,
        knowledge_context: Optional[dict] = None,
        polish_mode: str = "job_aligned",
        user_notes: Optional[str] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        evaluation_snapshot = snapshot_from_payload(analysis or {})
        metrics = (analysis or {}).get("matching_metrics") or {}
        ability_profile = evaluation_snapshot.get("ability_profile") or (analysis or {}).get("ability_gap_profile") or metrics.get("ability_gap_profile") or {}
        keyword_evidence = evaluation_snapshot.get("keyword_evidence") or {}
        scores = evaluation_snapshot.get("scores") or {}
        compact_context = {
            "analysis_summary": {
                "final_score": scores.get("final_score", metrics.get("final_score", (analysis or {}).get("final_score"))),
                "keyword_coverage": scores.get("keyword_coverage", metrics.get("keyword_coverage", (analysis or {}).get("keyword_coverage"))),
                "semantic_score": scores.get("semantic_score", metrics.get("semantic_score", (analysis or {}).get("semantic_score"))),
                "strengths": (analysis or {}).get("strengths") or [],
                "weaknesses": (analysis or {}).get("weaknesses") or [],
                "suggestions": (analysis or {}).get("suggestions") or [],
            },
            "ability_gap_profile": {
                "overall_match_score": ability_profile.get("overall_match_score"),
                "top_gaps": (ability_profile.get("top_gaps") or ability_profile.get("items") or [])[:6],
            },
            "matching_evidence": {
                "direct_matches": keyword_evidence.get("direct_matches") or [],
                "related_matches": keyword_evidence.get("related_matches") or [],
                "verification_needed": keyword_evidence.get("verification_needed") or [],
                "missing_keywords": keyword_evidence.get("missing") or [],
                "evidence_statuses": keyword_evidence.get("evidence_statuses") or [],
            },
            "resume_evaluation_snapshot": evaluation_snapshot,
            "resume_evidence": {
                "evidence_summary": (resume_evidence or {}).get("evidence_summary") or [],
                "ambiguity_flags": (resume_evidence or {}).get("ambiguity_flags") or [],
                "missing_evidence_flags": (resume_evidence or {}).get("missing_evidence_flags") or [],
            },
            "knowledge_context": knowledge_context or {},
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是严格证据约束的中文简历教练。请基于岗位评分逻辑润色简历，返回纯 JSON。"
                    "只能改写表达、重排重点、提示需要补充的真实证据；不得编造公司、项目、职责、指标、技术栈、证书或时间。"
                    "如果简历只有声明型能力，必须标记为待验证，不能写成已经熟练掌握。"
                    "如果需要用户补充信息，用 [补充真实数据/项目细节] 这样的占位符。"
                    "JSON Schema: {"
                    '"overall_strategy":"","section_suggestions":[{"section":"","issue":"","evidence_basis":"","rewrite_strategy":"","rewritten_text":"","risk_level":"low|medium|high","risk_note":""}],'
                    '"keyword_alignment":[{"keyword":"","status":"direct|indirect|claimed_only|missing","action":""}],'
                    '"risk_warnings":[""],"missing_evidence_to_prepare":[""],"polished_resume_markdown":""'
                    "}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"目标岗位：{target_position}\n"
                    f"润色模式：{polish_mode}\n"
                    f"用户补充说明：{AIService._trim_text(user_notes or '', 1200)}\n"
                    f"原简历结构化 JSON：{AIService._resume_snapshot(parsed_resume or {})}\n"
                    f"评分与证据上下文：{json.dumps(compact_context, ensure_ascii=False)}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.25, ai_config=ai_config)
        payload = await AIService._extract_or_repair_json(
            result,
            "JSON object with resume polish fields",
            ai_config=ai_config,
        )
        return AIService._normalize_resume_polish_payload(
            payload=payload,
            target_position=target_position,
            analysis=analysis,
            polish_mode=polish_mode,
            knowledge_context=knowledge_context,
        )
    @staticmethod
    async def generate_questions(
        parsed_resume: dict,
        target_position: str,
        difficulty: str,
        count: int,
        knowledge_base: Optional[dict] = None,
        question_plan: Optional[Sequence[Dict]] = None,
        interview_blueprint: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> list:
        difficulty_desc = {
            "easy": "junior-friendly, focus on fundamentals and clear project narration",
            "medium": "balanced, cover project depth and practical engineering decisions",
            "hard": "senior-level, include architecture trade-offs, performance and risk handling",
        }.get(difficulty, "balanced")
        knowledge_context = AIService._build_knowledge_base_context(knowledge_base)
        plan_context = AIService._build_question_plan_context(question_plan)
        blueprint_context = AIService._build_interview_blueprint_context(interview_blueprint)
        has_routed_evidence = any((item.get("selected_slices") or []) for item in question_plan or [])
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior interviewer designing a realistic mock interview. "
                    "Reply in Simplified Chinese. "
                    f"Target role: {target_position}. Difficulty: {difficulty_desc}. "
                    f"Generate exactly {count} interview questions. "
                    "The first question must be self-introduction. "
                    "If question plan is provided, strictly follow the stage/category/intent order. "
                    "Use the routed knowledge slices as the primary calibration source. "
                    "Return pure JSON array only with schema: "
                    '[{"index":0,"question":"...","category":"self-intro|project|technical|system-design|behavior"}].\n'
                    f"{AIService._build_grounding_rules('question', has_routed_evidence=has_routed_evidence)}\n"
                    f"{knowledge_context}\n{blueprint_context}\n{plan_context}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Candidate resume JSON: {AIService._resume_snapshot(parsed_resume)}\n"
                    f"Target position: {target_position}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.65, ai_config=ai_config)
        return AIService._normalize_question_array(AIService._extract_json(result))
    @staticmethod
    async def generate_panel_questions(
        parsed_resume: dict,
        target_position: str,
        difficulty: str,
        count: int,
        question_plan: Sequence[Dict],
        knowledge_base: Optional[dict] = None,
        panel_snapshot: Optional[Dict] = None,
        interview_blueprint: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        difficulty_desc = {
            "easy": "keep the bar realistic and training-oriented",
            "medium": "balance challenge and coaching value",
            "hard": "challenge the candidate with depth and pressure, but stay fair",
        }.get(difficulty, "balance challenge and coaching value")
        has_routed_evidence = any((item.get("selected_slices") or []) for item in question_plan or [])
        blueprint_context = AIService._build_interview_blueprint_context(interview_blueprint)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are simulating one internal interview panel with multiple roles, but only one moderator speaks outwardly. "
                    "Use a single model call and return strict JSON only. "
                    "Do not output chain-of-thought. Keep reasoning summaries brief. "
                    "Every panel role must think from its own focus, propose candidates, then the moderator selects the final question. "
                    "Return an object with this schema: "
                    '{"panel":[{"role":"technical","role_key":"technical_deep_dive","focus":"",'
                    '"question_candidates":[""],"followup_candidates":[""],"evaluation_points":[""]}],'
                    '"moderator":{"selected_questions":[{"index":0,"selected_question":"",'
                    '"selected_followups":[""],"reasoning_summary":"",'
                    '"lead_role":"technical_deep_dive","support_roles":["project_follow_up"],'
                    '"evaluation_points":[""],"used_slice_ids":[1,2]}],'
                    '"reasoning_summary":"","feedback_style":"","difficulty_hint":""},'
                    '"metadata":{"mode":"panel","version":"panel_structured_v1",'
                    '"retrieved_slice_ids":[1,2],"fallback_allowed":true}}. '
                    f"Generate exactly {count} selected questions. "
                    f"Target role: {target_position}. Difficulty guidance: {difficulty_desc}. "
                    "If routed slices exist, prefer them and reference the used slice ids in moderator.selected_questions[].used_slice_ids.\n"
                    f"{AIService._build_grounding_rules('panel_question', has_routed_evidence=has_routed_evidence)}\n"
                    f"{AIService._build_panel_context(panel_snapshot)}\n"
                    f"{blueprint_context}\n"
                    f"{AIService._build_knowledge_base_context(knowledge_base)}\n"
                    f"{AIService._build_question_plan_context(question_plan)}"
                ),
            },
            {
                "role": "user",
                "content": f"Candidate resume JSON: {AIService._resume_snapshot(parsed_resume)}",
            },
        ]
        result = await AIService._chat(messages, temperature=0.5, ai_config=ai_config)
        payload = AIService._extract_json(result)
        normalized = AIService._normalize_panel_question_payload(
            payload=payload,
            question_plan=question_plan,
            knowledge_base=knowledge_base,
            panel_snapshot=panel_snapshot,
        )
        logger.info(
            "Panel structured question generation succeeded: roles=%s questions=%s",
            len(normalized.get("panel") or []),
            len(normalized.get("questions") or []),
        )
        return normalized
    @staticmethod
    async def evaluate_answer(
        question: str,
        answer: str,
        resume_context: dict,
        chat_history: list,
        next_question: Optional[str] = None,
        knowledge_base: Optional[dict] = None,
        question_meta: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        selected_slices = (question_meta or {}).get("selected_slices") or None
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior interviewer and interview coach. "
                    "Evaluate the candidate answer and return pure JSON only. "
                    "Reply in Simplified Chinese. "
                    'Schema: {"score":7.5,"feedback":"","follow_up":false,"strengths":[""],"gaps":[""],'
                    '"unresolved_gaps":[""],"next_focus":"","selected_followups":[""],'
                    '"evidence_strength_delta":[{"evidence":"","delta":"strengthened|unchanged|weakened|insufficient","reason":"","source_ids":[1],"source_summary":[""]}],'
                    '"claim_confidence_change":[{"claim":"","from_level":"weak","to_level":"moderate","change":"increased|unchanged|decreased","reason":""}],'
                    '"next_best_followup":{"question":"","reason":"","target_gap":"","target_evidence":[""],"evidence_source_ids":[1],"evidence_source_summary":[""]}}. '
                    "Score range is 1-10. Feedback should be concise and actionable."
                    f"\n{AIService._build_grounding_rules('evaluation', has_routed_evidence=bool(selected_slices))}"
                    f"\n{AIService._build_knowledge_base_context(knowledge_base, selected_slices=selected_slices)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Resume JSON: {AIService._resume_snapshot(resume_context)}\n"
                    f"Chat history:\n{AIService._history_text(chat_history)}\n"
                    f"Question: {question}\n"
                    f"Candidate answer: {answer}\n"
                    f"Question intent: {(question_meta or {}).get('intent') or '-'}\n"
                    f"Evaluation focus: {', '.join((question_meta or {}).get('evaluation_focus') or []) or '-'}\n"
                    f"{AIService._build_question_blueprint_context(question_meta)}\n"
                    f"Next question: {next_question or '-'}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.35, ai_config=ai_config)
        payload = AIService._extract_json(result)
        return AIService._normalize_single_evaluation_payload(
            payload=payload,
            question_meta=question_meta,
            knowledge_base=knowledge_base,
        )
    @staticmethod
    async def evaluate_answer_with_panel(
        question: str,
        answer: str,
        resume_context: dict,
        chat_history: list,
        knowledge_base: Optional[dict] = None,
        question_meta: Optional[Dict] = None,
        panel_snapshot: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        selected_slices = (question_meta or {}).get("selected_slices") or None
        messages = [
            {
                "role": "system",
                "content": (
                    "You are simulating one internal collaborative interview panel. "
                    "Only the moderator speaks outwardly to the candidate. "
                    "Return strict JSON only and reply in Simplified Chinese. "
                    "Each panel role should assess the answer from its own focus, suggest follow-ups, and list evaluation points. "
                    "All panel roles must share the same routed evidence pool. "
                    "The moderator must link the next_best_followup to explicit evidence_source_ids or evidence_source_summary. "
                    'Return schema: {"panel":[{"role":"technical","role_key":"technical_deep_dive","focus":"",'
                    '"question_candidates":[""],"followup_candidates":[""],"evaluation_points":[""]}],'
                    '"moderator":{"score":7.8,"feedback":"","follow_up":false,"next_focus":"",'
                    '"selected_followups":[""],"reasoning_summary":"","feedback_style":"","difficulty_hint":"",'
                    '"next_best_followup":{"question":"","reason":"","target_gap":"","target_evidence":[""],"evidence_source_ids":[1],"evidence_source_summary":[""]}},'
                    '"metadata":{"mode":"panel","version":"panel_structured_v1",'
                    '"retrieved_slice_ids":[1,2],"fallback_allowed":true},'
                    '"strengths":[""],"gaps":[""],"unresolved_gaps":[""],'
                    '"evidence_strength_delta":[{"evidence":"","delta":"strengthened|unchanged|weakened|insufficient","reason":"","source_ids":[1],"source_summary":[""]}],'
                    '"claim_confidence_change":[{"claim":"","from_level":"weak","to_level":"moderate","change":"increased|unchanged|decreased","reason":""}],'
                    '"next_best_followup":{"question":"","reason":"","target_gap":"","target_evidence":[""],"evidence_source_ids":[1],"evidence_source_summary":[""]}}. '
                    "The outward feedback must remain one moderator voice and be concise."
                    f"\n{AIService._build_grounding_rules('panel_evaluation', has_routed_evidence=bool(selected_slices))}"
                    f"\n{AIService._build_panel_context(panel_snapshot)}\n"
                    f"{AIService._build_knowledge_base_context(knowledge_base, selected_slices=selected_slices)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Resume JSON: {AIService._resume_snapshot(resume_context)}\n"
                    f"Chat history:\n{AIService._history_text(chat_history)}\n"
                    f"Current question: {question}\n"
                    f"Candidate answer: {answer}\n"
                    f"Lead role: {(question_meta or {}).get('lead_role') or '-'}\n"
                    f"Support roles: {', '.join((question_meta or {}).get('support_roles') or []) or '-'}\n"
                    f"Intent: {(question_meta or {}).get('intent') or '-'}\n"
                    f"Evaluation focus: {', '.join((question_meta or {}).get('evaluation_focus') or []) or '-'}\n"
                    f"{AIService._build_question_blueprint_context(question_meta)}\n"
                    f"Suggested followups: {', '.join((question_meta or {}).get('selected_followups') or []) or '-'}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.3, ai_config=ai_config)
        payload = AIService._extract_json(result)
        normalized = AIService._normalize_panel_evaluation_payload(
            payload=payload,
            question_meta=question_meta,
            knowledge_base=knowledge_base,
            panel_snapshot=panel_snapshot,
        )
        logger.info(
            "Panel structured evaluation succeeded: lead_role=%s",
            (question_meta or {}).get("lead_role") or "-",
        )
        return normalized
    @staticmethod
    async def evaluate_answer_stream(
        question: str,
        answer: str,
        resume_context: dict,
        chat_history: list,
        knowledge_base: Optional[dict] = None,
        question_meta: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ):
        result = await AIService.evaluate_answer(
            question=question,
            answer=answer,
            resume_context=resume_context,
            chat_history=chat_history,
            knowledge_base=knowledge_base,
            question_meta=question_meta,
            ai_config=ai_config,
        )
        feedback = result.get("feedback", "")
        if feedback:
            yield feedback
        yield f'\n```json\n{{"score": {result.get("score", 5.0)}}}\n```'
    @staticmethod
    def _qa_text(questions_and_scores: Sequence[Dict]) -> str:
        lines = []
        for item in questions_and_scores:
            lines.append(f"Question: {item.get('question')}")
            lines.append(f"Answer: {item.get('answer') or '未回答'}")
            lines.append(f"Score: {item.get('score')}")
            if item.get("category"):
                lines.append(f"Category: {item.get('category')}")
            if item.get("lead_role"):
                lines.append(f"Lead role: {item.get('lead_role')}")
            if item.get("evaluation_focus"):
                lines.append(f"Evaluation focus: {', '.join(item.get('evaluation_focus') or [])}")
            if item.get("selected_followups"):
                lines.append(f"Selected followups: {', '.join(item.get('selected_followups') or [])}")
            if item.get("used_slice_ids"):
                lines.append(
                    f"Retrieved slice ids: {', '.join(str(v) for v in item.get('used_slice_ids') or [])}"
                )
            if item.get("question_target_gap"):
                lines.append(f"Question target gap: {item.get('question_target_gap')}")
            if item.get("question_target_evidence"):
                lines.append(
                    f"Question target evidence: {', '.join(item.get('question_target_evidence') or [])}"
                )
            if item.get("question_reason"):
                lines.append(f"Question reason: {item.get('question_reason')}")
            evaluation = item.get("evaluation") or {}
            if evaluation.get("strengths"):
                lines.append(f"Strengths: {', '.join(evaluation.get('strengths') or [])}")
            if evaluation.get("gaps"):
                lines.append(f"Gaps: {', '.join(evaluation.get('gaps') or [])}")
            if evaluation.get("unresolved_gaps"):
                lines.append(f"Unresolved gaps: {', '.join(evaluation.get('unresolved_gaps') or [])}")
            if evaluation.get("next_focus"):
                lines.append(f"Next focus: {evaluation.get('next_focus')}")
            for delta in evaluation.get("evidence_strength_delta") or []:
                if isinstance(delta, dict) and delta.get("evidence"):
                    line = f"Evidence delta: {delta.get('evidence')} -> {delta.get('delta') or 'unchanged'}"
                    if delta.get("reason"):
                        line = f"{line} ({delta.get('reason')})"
                    lines.append(line)
            for change in evaluation.get("claim_confidence_change") or []:
                if isinstance(change, dict) and change.get("claim"):
                    line = (
                        f"Claim confidence: {change.get('claim')} "
                        f"{change.get('from_level') or '-'} -> {change.get('to_level') or '-'}"
                    )
                    if change.get("reason"):
                        line = f"{line} ({change.get('reason')})"
                    lines.append(line)
            next_best_followup = evaluation.get("next_best_followup") or {}
            if isinstance(next_best_followup, dict) and next_best_followup.get("question"):
                lines.append(f"Next best follow-up: {next_best_followup.get('question')}")
                if next_best_followup.get("reason"):
                    lines.append(f"Follow-up reason: {next_best_followup.get('reason')}")
            for panel_view in evaluation.get("panel_views") or []:
                if isinstance(panel_view, dict):
                    lines.append(
                        f"Panel view [{panel_view.get('role') or '-'}]: {panel_view.get('summary') or ''}"
                    )
            lines.append("")
        return "\n".join(lines)
    @staticmethod
    async def generate_report(
        parsed_resume: dict,
        target_position: str,
        questions_and_scores: list,
        knowledge_base: Optional[dict] = None,
        panel_snapshot: Optional[Dict] = None,
        report_signals: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior interviewer writing a final mock-interview report. "
                    "Reply in Simplified Chinese and return pure JSON only. "
                    'Schema: {"summary":"","strengths":[""],"weaknesses":[""],'
                    '"suggestions":[""],"hire_recommendation":"","training_priorities":[""],'
                    '"common_gaps":[""],"common_strengths":[""],"evidence_summary":[""],'
                    '"followup_loop_summary":[""],"claim_confidence_summary":[""]}. '
                    f"\n{AIService._build_grounding_rules('report', has_report_evidence=bool((report_signals or {}).get('evidence_summary') or (report_signals or {}).get('retrieved_slice_ids')))}"
                    f"\n{AIService._build_interview_blueprint_context((panel_snapshot or {}).get('interview_blueprint'))}\n"
                    f"\n{AIService._build_knowledge_base_context(knowledge_base)}\n"
                    f"{AIService._build_report_signal_context(report_signals)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target position: {target_position}\n"
                    f"Resume JSON: {AIService._resume_snapshot(parsed_resume)}\n"
                    f"Interview records:\n{AIService._qa_text(questions_and_scores)}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.35, ai_config=ai_config)
        return AIService._extract_json(result)
    @staticmethod
    async def generate_panel_report(
        parsed_resume: dict,
        target_position: str,
        questions_and_scores: list,
        knowledge_base: Optional[dict] = None,
        panel_snapshot: Optional[Dict] = None,
        report_signals: Optional[Dict] = None,
        ai_config: Optional[Dict] = None,
    ) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are summarizing a collaborative internal interview panel while keeping one unified outward report. "
                    "Reply in Simplified Chinese and return pure JSON only. "
                    'Schema: {"summary":"","strengths":[""],"weaknesses":[""],"suggestions":[""],'
                    '"hire_recommendation":"","training_priorities":[""],'
                    '"common_gaps":[""],"common_strengths":[""],'
                    '"evidence_summary":[""],'
                    '"followup_loop_summary":[""],"claim_confidence_summary":[""],'
                    '"panel_summary":[{"role":"technical_deep_dive","title":"技术深挖","summary":""}]}. '
                    f"\n{AIService._build_grounding_rules('panel_report', has_report_evidence=bool((report_signals or {}).get('evidence_summary') or (report_signals or {}).get('retrieved_slice_ids')))}"
                    f"\n{AIService._build_panel_context(panel_snapshot)}\n"
                    f"{AIService._build_interview_blueprint_context((panel_snapshot or {}).get('interview_blueprint'))}\n"
                    f"{AIService._build_knowledge_base_context(knowledge_base)}\n"
                    f"{AIService._build_report_signal_context(report_signals)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target position: {target_position}\n"
                    f"Resume JSON: {AIService._resume_snapshot(parsed_resume)}\n"
                    f"Interview records:\n{AIService._qa_text(questions_and_scores)}"
                ),
            },
        ]
        result = await AIService._chat(messages, temperature=0.3, ai_config=ai_config)
        return AIService._extract_json(result)
