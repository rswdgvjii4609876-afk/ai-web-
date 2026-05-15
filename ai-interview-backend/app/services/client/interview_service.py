from collections import Counter
from datetime import datetime, timezone
import io
import json
import logging
import zipfile
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete as sql_delete
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.interview import Interview
from app.models.interview_message import InterviewMessage
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.models.resume import Resume
from app.services.client.ai_service import AIService
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)
from app.services.client.resume_evaluation_snapshot import (
    ensure_resume_evaluation_snapshot,
    matching_metrics_from_payload,
)
from app.services.client.resume_normalizer import normalize_parsed_resume

logger = logging.getLogger(__name__)

TRAINING_SAMPLE_QUALITY_TIERS = {"needs_review", "low", "medium", "high"}
TRAINING_SAMPLE_DATASET_SPLITS = {"", "train", "validation", "test", "holdout", "demo"}
EVALUATION_DATASET_SCHEMA_VERSION = "ai-interview.evaluation-dataset.v1"
EVALUATION_DATASET_DEFINITIONS = (
    {
        "dataset_type": "golden_cases",
        "filename": "golden_cases.jsonl",
        "label": "黄金样本集",
        "description": "高质量、无幻觉且高分的稳定训练样本。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.is_high_quality=true",
            "training_sample_review.has_hallucination=false",
            "overall_score>=7.5",
        ],
    },
    {
        "dataset_type": "hallucination_cases",
        "filename": "hallucination_cases.jsonl",
        "label": "幻觉问题集",
        "description": "人工判定存在幻觉或无依据强答的案例。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.has_hallucination=true",
        ],
    },
    {
        "dataset_type": "followup_quality_cases",
        "filename": "followup_quality_cases.jsonl",
        "label": "追问质量集",
        "description": "追问值得保留，且本轮存在可复用的 evidence-driven follow-up 信号。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.followup_worthy=true",
            "training_sample_review.has_hallucination=false",
            "overall_score>=6.0",
            "followup_signal_present=true",
        ],
    },
    {
        "dataset_type": "report_quality_cases",
        "filename": "report_quality_cases.jsonl",
        "label": "报告质量集",
        "description": "报告建议具有可执行性，且报告聚合信号完整。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.report_actionable=true",
            "training_sample_review.has_hallucination=false",
            "overall_score>=6.0",
            "report_signal_present=true",
        ],
    },
)

START_INTERVIEW_DB_ERROR_MESSAGE = (
    "开始面试失败：数据库写入异常，可能是服务器数据库迁移未完成。"
    "请管理员执行 alembic upgrade head，并查看后端日志中的第一条数据库异常。"
)


PANEL_ROLE_SPECS = [
    {
        "key": "technical_deep_dive",
        "name": "Technical Deep Dive",
        "focus": "Probe core principles, technical trade-offs, and hard engineering details.",
    },
    {
        "key": "project_follow_up",
        "name": "Project Follow-up",
        "focus": "Verify ownership, real contribution, trade-offs, and project retrospection.",
    },
    {
        "key": "business_scenario",
        "name": "Business Scenario",
        "focus": "Test whether technical thinking can be grounded in realistic business context.",
    },
    {
        "key": "behavior_expression",
        "name": "Behavior & Communication",
        "focus": "Observe structure, collaboration, growth mindset, and communication quality.",
    },
    {
        "key": "pressure_challenge",
        "name": "Pressure Challenge",
        "focus": "Test boundary handling, risk awareness, pressure response, and decision trade-offs.",
    },
]

QUESTION_TEMPLATES = {
    "opening_intro": {
        "stage": "opening",
        "category": "self-intro",
        "lead_role": "behavior_expression",
        "support_roles": ["project_follow_up"],
        "intent": "Use the self-introduction to quickly assess background fit, clarity, and motivation.",
        "evaluation_focus": ["structured expression", "role motivation", "background highlights"],
    },
    "project_core": {
        "stage": "project",
        "category": "project",
        "lead_role": "project_follow_up",
        "support_roles": ["technical_deep_dive"],
        "intent": "Deep-dive the most important project to verify ownership, trade-offs, and retrospection quality.",
        "evaluation_focus": ["ownership", "solution trade-offs", "project retrospection"],
    },
    "technical_core": {
        "stage": "technical",
        "category": "technical",
        "lead_role": "technical_deep_dive",
        "support_roles": ["project_follow_up"],
        "intent": "Validate mastery of core knowledge and depth of understanding.",
        "evaluation_focus": ["core principles", "accuracy", "technical depth"],
    },
    "business_scenario": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "business_scenario",
        "support_roles": ["technical_deep_dive"],
        "intent": "Place the candidate in a realistic business scenario to test execution quality.",
        "evaluation_focus": ["business understanding", "solution landing", "stability awareness"],
    },
    "behavior_growth": {
        "stage": "behavior",
        "category": "behavior",
        "lead_role": "behavior_expression",
        "support_roles": ["project_follow_up"],
        "intent": "Evaluate collaboration, communication, reflection, and growth potential.",
        "evaluation_focus": ["communication", "collaboration reflection", "growth potential"],
    },
    "pressure_tradeoff": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "pressure_challenge",
        "support_roles": ["technical_deep_dive", "business_scenario"],
        "intent": "Assess boundary awareness and trade-offs under pressure.",
        "evaluation_focus": ["risk trade-offs", "stability", "pressure response"],
    },
    "technical_debug": {
        "stage": "technical",
        "category": "technical",
        "lead_role": "technical_deep_dive",
        "support_roles": ["pressure_challenge"],
        "intent": "Use debugging or optimization questions to verify diagnosis and engineering experience.",
        "evaluation_focus": ["debugging approach", "engineering experience", "optimization ability"],
    },
    "project_ownership": {
        "stage": "project",
        "category": "project",
        "lead_role": "project_follow_up",
        "support_roles": ["behavior_expression"],
        "intent": "Further verify role boundaries, leadership level, and delivery outcomes in projects.",
        "evaluation_focus": ["role boundary", "result orientation", "retrospective quality"],
    },
    "scenario_tradeoff": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "business_scenario",
        "support_roles": ["pressure_challenge"],
        "intent": "Use business changes and resource limits to validate solution trade-offs.",
        "evaluation_focus": ["scenario fit", "priority judgment", "resource trade-offs"],
    },
    "closing_reflection": {
        "stage": "closing",
        "category": "behavior",
        "lead_role": "behavior_expression",
        "support_roles": ["pressure_challenge"],
        "intent": "Close the interview by checking self-awareness and most urgent training priorities.",
        "evaluation_focus": ["self-awareness", "summary ability", "training direction"],
    },
}

QUESTION_ORDERS = {
    "easy": [
        "opening_intro",
        "project_core",
        "technical_core",
        "behavior_growth",
        "project_ownership",
        "technical_debug",
        "business_scenario",
        "scenario_tradeoff",
        "closing_reflection",
        "closing_reflection",
    ],
    "medium": [
        "opening_intro",
        "project_core",
        "technical_core",
        "business_scenario",
        "behavior_growth",
        "pressure_tradeoff",
        "technical_debug",
        "project_ownership",
        "scenario_tradeoff",
        "closing_reflection",
    ],
    "hard": [
        "opening_intro",
        "project_core",
        "technical_core",
        "pressure_tradeoff",
        "business_scenario",
        "technical_debug",
        "project_ownership",
        "scenario_tradeoff",
        "technical_core",
        "closing_reflection",
    ],
}

PANEL_ROLE_TITLES = {
    "technical_deep_dive": "Technical Deep Dive",
    "project_follow_up": "Project Follow-up",
    "business_scenario": "Business Scenario",
    "behavior_expression": "Behavior & Communication",
    "pressure_challenge": "Pressure Challenge",
}


class InterviewService:
    @staticmethod
    def _load_resume_analysis_payload(resume: Resume) -> Dict[str, Any]:
        payload = (resume.analysis or "").strip()
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Resume analysis payload is not valid JSON: resume_id=%s", resume.id)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _load_resume_evidence(resume: Resume) -> Dict[str, Any]:
        analysis_payload = InterviewService._load_resume_analysis_payload(resume)
        evidence = analysis_payload.get("resume_evidence") or {}
        return evidence if isinstance(evidence, dict) else {}

    @staticmethod
    def _load_resume_payload(resume: Resume) -> Dict[str, Any]:
        payload = (resume.parsed_content or "").strip()
        if not payload:
            raise ValidationError(message="开始面试失败：简历解析结果为空，请重新解析后再试")
        try:
            parsed_resume = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                message="开始面试失败：简历解析结果异常，请重新上传简历或重新解析"
            ) from exc
        if not isinstance(parsed_resume, dict):
            raise ValidationError(
                message="开始面试失败：简历解析结果异常，请重新上传简历或重新解析"
            )
        if not isinstance(parsed_resume.get("normalized_resume"), dict):
            parsed_resume = normalize_parsed_resume(parsed_resume)
        completeness = (parsed_resume.get("normalized_resume") or {}).get("completeness") or {}
        has_skill = bool(completeness.get("has_skills") or parsed_resume.get("skills"))
        has_project_signal = bool(
            completeness.get("has_projects")
            or completeness.get("has_experience")
            or parsed_resume.get("projects")
            or parsed_resume.get("experience")
            or parsed_resume.get("campus_experience")
        )
        if not has_skill and not has_project_signal:
            raise ValidationError(
                message=(
                    "开始面试失败：当前简历解析结果缺少技能、项目或经历信息，"
                    "无法稳定生成面试问题。请重新上传文字版 PDF，或在简历中补充项目/技能后再试。"
                )
            )
        return parsed_resume

    @staticmethod
    def _format_start_interview_error(detail: Optional[str]) -> str:
        message = (detail or "").strip()
        if not message:
            return "开始面试失败：题目生成服务异常，请稍后重试"
        if message.startswith("开始面试失败："):
            return message
        if "题目生成数量不足" in message:
            return "开始面试失败：当前模型返回的题目数量不足，请切换模型或稍后重试"
        if "题目生成失败" in message:
            return "开始面试失败：AI 题目生成失败，请更换模型或稍后重试"
        if (
            "API Key" in message
            or "API Token" in message
            or "Base URL" in message
            or "模型名" in message
            or "连接 " in message
            or "请求参数错误" in message
        ):
            return f"开始面试失败：{message}"
        if "岗位知识库" in message or "简历" in message:
            return message if message.startswith("开始面试失败：") else f"开始面试失败：{message}"
        return f"开始面试失败：{message}"

    @staticmethod
    def _serialize_knowledge_base(knowledge_base: Optional[PositionKnowledgeBase]) -> Optional[Dict]:
        if not knowledge_base:
            return None
        scope = knowledge_base.scope or "private"
        return {
            "id": knowledge_base.id,
            "title": knowledge_base.title,
            "target_position": knowledge_base.target_position,
            "knowledge_content": knowledge_base.knowledge_content,
            "focus_points": knowledge_base.focus_points,
            "interviewer_prompt": knowledge_base.interviewer_prompt,
            "is_active": knowledge_base.is_active,
            "scope": scope,
            "source_label": "后台公共知识库" if scope == "public" else "我的知识库",
        }

    @staticmethod
    def _build_panel_snapshot(
        mode: str,
        requested_panel: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> Dict:
        snapshot = {
            "mode": mode,
            "requested_panel": requested_panel or mode == "panel",
            "display_name": "内部多面试官协同" if mode == "panel" else "单面试官模式",
            "moderator_name": "主持人面试官",
        }
        if mode == "panel":
            snapshot["roles"] = PANEL_ROLE_SPECS
        if fallback_reason:
            snapshot["fallback_reason"] = fallback_reason
        return snapshot

    @staticmethod
    def _blueprint_claim_strings(interview_blueprint: Optional[Dict], limit: int = 4) -> List[str]:
        claims: List[str] = []
        for item in (interview_blueprint or {}).get("high_risk_claims") or []:
            text = ""
            if isinstance(item, dict):
                text = str(item.get("claim") or "").strip()
            else:
                text = str(item).strip()
            if text and text not in claims:
                claims.append(text)
            if len(claims) >= limit:
                break
        return claims

    @staticmethod
    def _question_target_evidence_ids(question_meta: Optional[Dict]) -> List[int]:
        ordered: List[int] = []
        for source in (
            (question_meta or {}).get("question_target_evidence_ids") or [],
            (question_meta or {}).get("blueprint_evidence_ids") or [],
            (question_meta or {}).get("used_slice_ids") or [],
            InterviewService._question_slice_ids(question_meta),
        ):
            for value in source:
                try:
                    slice_id = int(value)
                except (TypeError, ValueError):
                    continue
                if slice_id not in ordered:
                    ordered.append(slice_id)
        return ordered[:8]

    @staticmethod
    def _question_target_evidence_summary(question_meta: Optional[Dict]) -> List[str]:
        summary = InterviewService._unique_strings(
            [
                *((question_meta or {}).get("question_target_evidence") or []),
                *((question_meta or {}).get("blueprint_evidence_summary") or []),
                *((question_meta or {}).get("evidence_summary") or []),
                *[
                    InterviewService._slice_label(item)
                    for item in ((question_meta or {}).get("selected_slices") or [])[:2]
                    if item
                ],
            ],
            limit=4,
        )
        return summary

    @staticmethod
    def _derive_question_target_fields(question_meta: Optional[Dict]) -> Dict[str, Any]:
        meta = dict(question_meta or {})
        target_gap = (
            str(meta.get("question_target_gap") or "").strip()
            or str(meta.get("blueprint_track") or "").strip()
            or next(
                (
                    str(item).strip()
                    for item in (meta.get("evaluation_focus") or [])
                    if str(item).strip()
                ),
                "",
            )
            or str(meta.get("intent") or "").strip()
            or str(meta.get("category") or "").strip()
        )
        target_evidence = InterviewService._question_target_evidence_summary(meta)
        target_evidence_ids = InterviewService._question_target_evidence_ids(meta)
        reason = str(meta.get("question_reason") or "").strip()
        requirement_status = str(meta.get("blueprint_requirement_status") or "").strip()
        if not reason:
            if meta.get("is_dynamic_followup"):
                reason = (
                    f"继续验证上一轮暴露的薄弱证据：{target_gap}"
                    if target_gap
                    else "继续验证上一轮回答里尚未被补强的关键证据。"
                )
            elif requirement_status == "unsupported":
                reason = (
                    f"当前几乎没有直接证据支持“{target_gap}”，需要先做保守验证。"
                    if target_gap
                    else "当前直接证据很弱，需要先做保守验证。"
                )
            elif requirement_status == "weak":
                reason = (
                    f"当前只有弱证据支持“{target_gap}”，需要通过本题继续核实。"
                    if target_gap
                    else "当前只有弱证据支持这一能力，需要通过本题继续核实。"
                )
            elif target_evidence:
                reason = (
                    f"围绕已命中的简历/知识库证据继续核实“{target_gap}”是否真实成立。"
                    if target_gap
                    else "围绕已命中的简历/知识库证据继续核实候选人的真实能力边界。"
                )
            else:
                reason = (
                    f"围绕“{target_gap}”补齐更具体的事实和证据。"
                    if target_gap
                    else "补齐更具体的事实和证据，避免只停留在泛化表述。"
                )

        return {
            "question_target_gap": target_gap or None,
            "question_target_evidence": target_evidence,
            "question_target_evidence_ids": target_evidence_ids,
            "question_reason": reason,
        }

    @staticmethod
    def _slice_ids_for_blueprint(question_plan: Sequence[Dict]) -> List[int]:
        ordered: List[int] = []
        for item in question_plan or []:
            for slice_item in item.get("selected_slices") or []:
                try:
                    slice_id = int(slice_item.get("slice_id"))
                except (TypeError, ValueError):
                    continue
                if slice_id not in ordered:
                    ordered.append(slice_id)
        return ordered

    @staticmethod
    def _apply_blueprint_to_question_plan(
        question_plan: Sequence[Dict],
        interview_blueprint: Optional[Dict],
    ) -> List[Dict]:
        if not interview_blueprint:
            return [dict(item) for item in question_plan]

        tracks = list((interview_blueprint or {}).get("priority_question_tracks") or [])
        training_focus = InterviewService._unique_strings(
            (interview_blueprint or {}).get("training_focus") or [],
            limit=4,
        )
        high_risk_claims = InterviewService._blueprint_claim_strings(interview_blueprint, limit=4)
        blueprint_evidence = (interview_blueprint or {}).get("blueprint_evidence") or {}
        global_evidence_ids = []
        for value in blueprint_evidence.get("slice_ids") or []:
            try:
                slice_id = int(value)
            except (TypeError, ValueError):
                continue
            if slice_id not in global_evidence_ids:
                global_evidence_ids.append(slice_id)
        global_evidence_summary = InterviewService._unique_strings(
            [
                *(interview_blueprint.get("evidence_summary") or []),
                *(blueprint_evidence.get("slice_summaries") or []),
            ],
            limit=4,
        )

        enriched_plan: List[Dict] = []
        for index, item in enumerate(question_plan or []):
            next_item = dict(item)
            track_item = tracks[min(index, len(tracks) - 1)] if tracks else None
            if isinstance(track_item, dict):
                track_name = str(track_item.get("track") or "").strip()
                track_status = str(track_item.get("requirement_status") or "weak").strip() or "weak"
                track_reason = str(track_item.get("reason") or "").strip()
                track_ids = []
                for value in track_item.get("evidence_ids") or []:
                    try:
                        slice_id = int(value)
                    except (TypeError, ValueError):
                        continue
                    if slice_id not in track_ids:
                        track_ids.append(slice_id)
            else:
                track_name = ""
                track_status = "weak"
                track_reason = ""
                track_ids = []

            if not track_name and training_focus:
                track_name = training_focus[min(index, len(training_focus) - 1)]
            if track_name:
                base_intent = str(next_item.get("intent") or "").strip()
                next_item["blueprint_track"] = track_name
                next_item["blueprint_requirement_status"] = track_status
                next_item["blueprint_evidence_ids"] = track_ids[:4] or global_evidence_ids[:4]
                next_item["blueprint_evidence_summary"] = InterviewService._unique_strings(
                    [track_reason, *global_evidence_summary],
                    limit=3,
                )
                next_item["intent"] = (
                    f"{base_intent} Blueprint priority: {track_name}."
                    if base_intent
                    else f"Blueprint priority: {track_name}."
                )
                next_item["evaluation_focus"] = InterviewService._unique_strings(
                    [
                        *(next_item.get("evaluation_focus") or []),
                        track_name,
                        *training_focus[:1],
                    ],
                    limit=6,
                )

            if high_risk_claims and index < 2:
                high_risk_claim = high_risk_claims[min(index, len(high_risk_claims) - 1)]
                next_item["blueprint_high_risk_claims"] = high_risk_claims[:3]
                next_item["selected_followups"] = InterviewService._unique_strings(
                    [*(next_item.get("selected_followups") or []), high_risk_claim],
                    limit=3,
                )

            enriched_plan.append(next_item)
        return enriched_plan

    @staticmethod
    def _compact_slice(item: Dict) -> Dict:
        return {
            "slice_id": item.get("slice_id"),
            "title": item.get("title"),
            "content": item.get("content"),
            "slice_type": item.get("slice_type"),
            "source_section": item.get("source_section"),
            "source_scope": item.get("source_scope"),
            "difficulty": item.get("difficulty"),
            "priority": item.get("priority"),
            "stage_tags": item.get("stage_tags") or [],
            "role_tags": item.get("role_tags") or [],
            "topic_tags": item.get("topic_tags") or [],
            "skill_tags": item.get("skill_tags") or [],
            "scene_tags": item.get("scene_tags") or [],
            "keywords": item.get("keywords") or [],
            "routing_score": item.get("routing_score"),
            "routing_reasons": item.get("routing_reasons") or [],
            "routing_heads": item.get("routing_heads") or {},
            "grounding_confidence": item.get("grounding_confidence"),
            "grounding_warnings": item.get("grounding_warnings") or [],
        }

    @staticmethod
    def _grounding_confidence_summary(selected_slices: Sequence[Dict]) -> Dict:
        counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        warnings: List[str] = []
        low_confidence_slice_ids: List[int] = []
        for item in selected_slices or []:
            confidence = str(item.get("grounding_confidence") or "unknown").lower()
            if confidence not in counts:
                confidence = "unknown"
            counts[confidence] += 1
            if confidence == "low":
                try:
                    low_confidence_slice_ids.append(int(item.get("slice_id")))
                except (TypeError, ValueError):
                    pass
            for warning in item.get("grounding_warnings") or []:
                warning_text = str(warning).strip()
                if warning_text and warning_text not in warnings:
                    warnings.append(warning_text)
        ordered = ["low", "medium", "high", "unknown"]
        lowest_confidence = next((key for key in ordered if counts.get(key)), "unknown")
        return {
            "counts": counts,
            "lowest_confidence": lowest_confidence,
            "warnings": warnings[:6],
            "low_confidence_slice_ids": low_confidence_slice_ids[:6],
        }

    @staticmethod
    def _slice_label(item: Dict) -> str:
        title = str(item.get("title") or "").strip()
        if title:
            return title
        slice_id = item.get("slice_id")
        if slice_id:
            return f"切片 #{slice_id}"
        return "知识切片"

    @staticmethod
    def _build_evidence_trace(selected_slices: Sequence[Dict], used_slice_ids: Optional[Sequence[int]] = None) -> List[Dict]:
        selected_ids = set()
        for value in used_slice_ids or []:
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                continue

        trace = []
        for item in selected_slices or []:
            try:
                slice_id = int(item.get("slice_id"))
            except (TypeError, ValueError):
                slice_id = None
            reasons = [str(reason).strip() for reason in (item.get("routing_reasons") or []) if str(reason).strip()]
            trace.append(
                {
                    "slice_id": slice_id,
                    "title": InterviewService._slice_label(item),
                    "source_section": item.get("source_section") or item.get("slice_type"),
                    "reason_summary": "；".join(reasons[:3]),
                    "reasons": reasons[:4],
                    "routing_heads": item.get("routing_heads") or {},
                    "grounding_confidence": item.get("grounding_confidence"),
                    "grounding_warnings": item.get("grounding_warnings") or [],
                    "quote": str(item.get("content") or "").strip()[:120],
                    "is_selected": bool(slice_id and slice_id in selected_ids) if selected_ids else True,
                }
            )
        return trace

    @staticmethod
    def _build_evidence_summary(selected_slices: Sequence[Dict], used_slice_ids: Optional[Sequence[int]] = None) -> List[str]:
        trace = InterviewService._build_evidence_trace(selected_slices, used_slice_ids=used_slice_ids)
        summary = []
        for item in trace[:3]:
            label = item.get("title") or "知识切片"
            reason = item.get("reason_summary") or "已命中相关岗位证据"
            summary.append(f"{label}：{reason}")
        return summary

    @staticmethod
    def _route_item_to_text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            preferred_keys = (
                "title",
                "name",
                "project",
                "role",
                "company",
                "position",
                "skill",
                "evidence",
                "description",
                "summary",
                "content",
                "details",
                "result",
                "technologies",
            )
            parts = [
                InterviewService._route_item_to_text(value.get(key))
                for key in preferred_keys
                if value.get(key) is not None
            ]
            if not parts:
                parts = [InterviewService._route_item_to_text(item) for item in list(value.values())[:6]]
            return " ".join(part for part in parts if part)
        if isinstance(value, (list, tuple, set)):
            return " ".join(
                part
                for part in (InterviewService._route_item_to_text(item) for item in value)
                if part
            )
        return str(value).strip()

    @staticmethod
    def _route_values_to_texts(values, limit: int) -> List[str]:
        if values is None:
            return []
        if isinstance(values, (str, dict)):
            values = [values]
        cleaned = []
        for item in values:
            text = InterviewService._route_item_to_text(item)
            if text:
                cleaned.append(text)
            if len(cleaned) >= limit:
                break
        return cleaned

    @staticmethod
    def _resume_route_text(parsed_resume: Dict) -> str:
        parts = []
        normalized = parsed_resume.get("normalized_resume") if isinstance(parsed_resume, dict) else None
        if isinstance(normalized, dict):
            profile = normalized.get("profile") or {}
            if profile:
                parts.append(InterviewService._route_item_to_text(profile))
            for key in (
                "education",
                "skills",
                "projects",
                "experience",
                "awards",
                "campus_experience",
            ):
                value = normalized.get(key)
                if value:
                    parts.append(InterviewService._route_item_to_text(value))
        if parsed_resume.get("summary"):
            parts.append(InterviewService._route_item_to_text(parsed_resume["summary"]))
        if parsed_resume.get("education"):
            parts.append(InterviewService._route_item_to_text(parsed_resume["education"]))
        if parsed_resume.get("skills"):
            parts.append(" ".join(InterviewService._route_values_to_texts(parsed_resume.get("skills"), 12)))
        if parsed_resume.get("projects"):
            parts.append(" ".join(InterviewService._route_values_to_texts(parsed_resume.get("projects"), 4)))
        if parsed_resume.get("experience"):
            parts.append(" ".join(InterviewService._route_values_to_texts(parsed_resume.get("experience"), 4)))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _ability_verification_targets(matching_metrics: Optional[Dict]) -> List[Dict]:
        snapshot = (matching_metrics or {}).get("resume_evaluation_snapshot") or {}
        profile = snapshot.get("ability_profile") or (matching_metrics or {}).get("ability_gap_profile") or {}
        snapshot_targets = snapshot.get("verification_targets") or []
        if isinstance(snapshot_targets, list) and snapshot_targets:
            return snapshot_targets[:8]
        raw_items = profile.get("top_gaps") or profile.get("items") or []
        if not isinstance(raw_items, list):
            return []
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        targets: List[Dict] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            evidence_status = item.get("evidence_status") or "needs_verification"
            verification_keywords = item.get("verification_keywords") or []
            related_matches = item.get("related_matches") or []
            missing_keywords = item.get("missing_keywords") or []
            should_verify = (
                evidence_status in {"claimed_only", "indirect", "missing", "needs_verification"}
                or verification_keywords
                or related_matches
                or missing_keywords
            )
            if not should_verify:
                continue
            keywords = [
                str(value).strip()
                for value in [*verification_keywords, *related_matches, *missing_keywords]
                if str(value).strip()
            ]
            targets.append(
                {
                    "ability_id": item.get("ability_id"),
                    "ability_name": item.get("name") or item.get("ability_name") or "岗位关键能力",
                    "evidence_status": evidence_status,
                    "verification_priority": item.get("verification_priority") or "medium",
                    "priority_score": item.get("priority_score") or 0,
                    "reason": item.get("interview_probe_reason") or item.get("evidence_basis") or "",
                    "keywords": keywords[:8],
                }
            )
        return sorted(
            targets,
            key=lambda item: (
                priority_rank.get(str(item.get("verification_priority") or "medium"), 1),
                -float(item.get("priority_score") or 0),
            ),
        )[:8]

    @staticmethod
    def _build_question_plan(total_questions: int, difficulty: str) -> List[Dict]:
        order = QUESTION_ORDERS.get(difficulty, QUESTION_ORDERS["medium"])
        plan = []
        for index, key in enumerate(order[:total_questions]):
            item = QUESTION_TEMPLATES[key].copy()
            item["index"] = index
            plan.append(item)
        return plan

    @staticmethod
    def _route_question_plan(
        question_plan: List[Dict],
        knowledge_base: Optional[Dict],
        parsed_resume: Dict,
        target_position: str,
        difficulty: str,
        matching_metrics: Optional[Dict] = None,
    ) -> List[Dict]:
        verification_targets = InterviewService._ability_verification_targets(matching_metrics)

        def target_for(index: int) -> Optional[Dict]:
            if not verification_targets:
                return None
            return verification_targets[index % len(verification_targets)]

        def enrich_item(item: Dict, index: int, selected: Optional[List[Dict]] = None) -> Dict:
            verification_target = target_for(index)
            evaluation_focus = list(item.get("evaluation_focus") or [])
            if verification_target:
                ability_name = verification_target.get("ability_name") or "岗位关键能力"
                focus_text = f"验证{ability_name}掌握程度"
                if focus_text not in evaluation_focus:
                    evaluation_focus.append(focus_text)
            return {
                **item,
                "evaluation_focus": evaluation_focus,
                "verification_target": verification_target,
                "question_target_gap": (verification_target or {}).get("reason") or item.get("question_target_gap"),
                "question_reason": (verification_target or {}).get("reason") or item.get("question_reason"),
                "selected_slices": selected or [],
            }

        if not knowledge_base:
            return [enrich_item(item, index) for index, item in enumerate(question_plan)]

        slices = knowledge_base.get("slices") or []
        if not slices:
            return [enrich_item(item, index) for index, item in enumerate(question_plan)]

        routed = []
        top_k = 2 if len(question_plan) >= 7 else 3
        resume_text = InterviewService._resume_route_text(parsed_resume)
        resume_skills = InterviewService._route_values_to_texts(parsed_resume.get("skills"), 12)
        resume_projects = InterviewService._route_values_to_texts(parsed_resume.get("projects"), 6)
        for index, item in enumerate(question_plan):
            verification_target = target_for(index)
            verification_text = ""
            if verification_target:
                verification_text = "\n".join(
                    [
                        str(verification_target.get("ability_name") or ""),
                        str(verification_target.get("evidence_status") or ""),
                        str(verification_target.get("reason") or ""),
                        " ".join(verification_target.get("keywords") or []),
                    ]
                )
            query_text = "\n".join(
                [
                    target_position,
                    resume_text,
                    verification_text,
                    item.get("intent") or "",
                    " ".join(item.get("evaluation_focus") or []),
                ]
            )
            try:
                selected = position_knowledge_base_slice_service.rank_slices(
                    slices=slices,
                    query_text=query_text,
                    stage=item.get("stage"),
                    role=item.get("lead_role"),
                    scene=item.get("category") or item.get("stage"),
                    difficulty=difficulty,
                    skills=resume_skills[:8],
                    topics=[target_position, *(resume_projects[:2])],
                    top_k=top_k,
                )
                if not selected:
                    selected = position_knowledge_base_slice_service.rank_slices(
                        slices=slices,
                        query_text=query_text,
                        difficulty=difficulty,
                        skills=resume_skills[:6],
                        topics=[target_position],
                        top_k=2,
                    )
            except Exception as exc:
                logger.warning("Knowledge slice routing failed for stage=%s: %s", item.get("stage"), exc)
                knowledge_base["slices"] = []
                knowledge_base["slice_count"] = 0
                knowledge_base["routing_strategy"] = "full_text_fallback"
                selected = []
            routed.append(enrich_item(item, index, [InterviewService._compact_slice(slice_item) for slice_item in selected]))
        return routed

    @staticmethod
    def _normalize_questions(
        raw_questions: List[Dict],
        question_plan: List[Dict],
        interview_mode: str,
    ) -> List[Dict]:
        if len(raw_questions) < len(question_plan):
            raise ValidationError(message="AI 题目生成数量不足，请稍后重试")

        normalized = []
        for index, plan in enumerate(question_plan):
            raw = raw_questions[index] or {}
            if isinstance(raw, str):
                raw = {"question": raw}
            question_text = (raw.get("question") or "").strip()
            if not question_text:
                raise ValidationError(message="AI 题目生成失败，请稍后重试")

            support_roles = raw.get("support_roles") or plan.get("support_roles") or []
            if isinstance(support_roles, str):
                support_roles = [support_roles]

            evaluation_focus = raw.get("evaluation_focus") or plan.get("evaluation_focus") or []
            if isinstance(evaluation_focus, str):
                evaluation_focus = [evaluation_focus]

            selected_slices = plan.get("selected_slices") or []
            requested_ids = raw.get("used_slice_ids") or raw.get("selected_slice_ids") or []
            if requested_ids:
                matched = [
                    item for item in selected_slices if item.get("slice_id") in set(requested_ids)
                ]
                if matched:
                    selected_slices = matched
            panel_context = dict(raw.get("panel_context") or {})
            metadata = dict(panel_context.get("metadata") or {})
            if selected_slices:
                metadata["grounding_confidence_summary"] = InterviewService._grounding_confidence_summary(
                    selected_slices
                )
                if requested_ids:
                    metadata["retrieved_slice_ids"] = requested_ids
                panel_context["metadata"] = metadata

            question_item = {
                "index": index,
                "question": question_text,
                "category": raw.get("category") or plan.get("category"),
                "stage": raw.get("stage") or plan.get("stage"),
                "lead_role": raw.get("lead_role") or plan.get("lead_role"),
                "support_roles": support_roles,
                "intent": raw.get("intent") or plan.get("intent"),
                "evaluation_focus": evaluation_focus,
                "selected_slices": selected_slices,
                "used_slice_ids": requested_ids or [],
                "evidence_trace": InterviewService._build_evidence_trace(
                    selected_slices,
                    used_slice_ids=requested_ids or [],
                ),
                "evidence_summary": InterviewService._build_evidence_summary(
                    selected_slices,
                    used_slice_ids=requested_ids or [],
                ),
                "blueprint_track": raw.get("blueprint_track") or plan.get("blueprint_track"),
                "blueprint_requirement_status": raw.get("blueprint_requirement_status")
                or plan.get("blueprint_requirement_status"),
                "blueprint_evidence_ids": raw.get("blueprint_evidence_ids")
                or plan.get("blueprint_evidence_ids")
                or [],
                "blueprint_evidence_summary": raw.get("blueprint_evidence_summary")
                or plan.get("blueprint_evidence_summary")
                or [],
                "blueprint_high_risk_claims": raw.get("blueprint_high_risk_claims")
                or plan.get("blueprint_high_risk_claims")
                or [],
                "selected_followups": raw.get("selected_followups") or [],
                "difficulty_hint": raw.get("difficulty_hint"),
                "panel_context": panel_context,
                "panel_reasoning_summary": raw.get("panel_reasoning_summary"),
                "verification_target": raw.get("verification_target") or plan.get("verification_target"),
                "question_target_gap": raw.get("question_target_gap") or plan.get("question_target_gap"),
                "question_target_evidence": raw.get("question_target_evidence") or [],
                "question_target_evidence_ids": raw.get("question_target_evidence_ids") or [],
                "question_reason": raw.get("question_reason") or plan.get("question_reason"),
                "interview_mode": interview_mode,
                "answer": None,
                "score": None,
                "feedback": None,
                "evaluation": None,
            }
            question_item.update(InterviewService._derive_question_target_fields(question_item))
            normalized.append(question_item)
        return normalized

    @staticmethod
    def _serialize_questions(questions: Any) -> List[Dict]:
        if not questions:
            return []
        parsed = questions
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                logger.warning("Interview questions_data is not valid JSON text")
                return []
        if isinstance(parsed, dict):
            for key in ("questions", "items", "data"):
                value = parsed.get(key)
                if isinstance(value, list):
                    parsed = value
                    break
            else:
                parsed = [parsed]
        if not isinstance(parsed, list):
            logger.warning("Interview questions_data is not a list: %s", type(parsed).__name__)
            return []
        cleaned = [item for item in parsed if isinstance(item, dict)]
        return json.loads(json.dumps(cleaned, ensure_ascii=False, default=InterviewService._json_safe))

    @staticmethod
    def _build_question_scores(questions: List[Dict]) -> List[Dict]:
        items = []
        for question in questions:
            items.append(
                {
                    "question": question.get("question"),
                    "score": float(question.get("score") or 0),
                    "feedback": question.get("feedback") or "",
                    "category": question.get("category"),
                    "lead_role": question.get("lead_role"),
                }
            )
        return items

    @staticmethod
    def _build_qa_data(questions: List[Dict]) -> List[Dict]:
        qa_data = []
        for question in questions:
            qa_data.append(
                {
                    "question": question.get("question"),
                    "answer": question.get("answer") or "未回答",
                    "score": float(question.get("score") or 0),
                    "feedback": question.get("feedback") or "",
                    "category": question.get("category"),
                    "stage": question.get("stage"),
                    "lead_role": question.get("lead_role"),
                    "support_roles": question.get("support_roles") or [],
                    "intent": question.get("intent"),
                    "evaluation_focus": question.get("evaluation_focus") or [],
                    "selected_slices": question.get("selected_slices") or [],
                    "used_slice_ids": question.get("used_slice_ids") or [],
                    "evidence_trace": question.get("evidence_trace") or [],
                    "evidence_summary": question.get("evidence_summary") or [],
                    "question_target_gap": question.get("question_target_gap"),
                    "verification_target": question.get("verification_target"),
                    "question_target_evidence": question.get("question_target_evidence") or [],
                    "question_target_evidence_ids": question.get("question_target_evidence_ids") or [],
                    "question_reason": question.get("question_reason"),
                    "blueprint_track": question.get("blueprint_track"),
                    "blueprint_requirement_status": question.get("blueprint_requirement_status"),
                    "blueprint_evidence_ids": question.get("blueprint_evidence_ids") or [],
                    "blueprint_evidence_summary": question.get("blueprint_evidence_summary") or [],
                    "blueprint_high_risk_claims": question.get("blueprint_high_risk_claims") or [],
                    "selected_followups": question.get("selected_followups") or [],
                    "panel_context": question.get("panel_context") or {},
                    "evaluation": question.get("evaluation") or {},
                }
            )
        return qa_data

    @staticmethod
    def _unique_strings(values: Sequence[Any], limit: int = 8) -> List[str]:
        ordered: List[str] = []
        for value in values or []:
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in ordered:
                ordered.append(text)
            if len(ordered) >= limit:
                break
        return ordered

    @staticmethod
    def _question_slice_ids(question_meta: Optional[Dict]) -> List[int]:
        ordered: List[int] = []
        for item in (question_meta or {}).get("selected_slices") or []:
            try:
                slice_id = int(item.get("slice_id"))
            except (TypeError, ValueError):
                continue
            if slice_id not in ordered:
                ordered.append(slice_id)
        for value in (question_meta or {}).get("used_slice_ids") or []:
            try:
                slice_id = int(value)
            except (TypeError, ValueError):
                continue
            if slice_id not in ordered:
                ordered.append(slice_id)
        return ordered

    @staticmethod
    def _extract_weakness_terms(
        current_question_meta: Dict,
        evaluation: Optional[Dict],
    ) -> List[str]:
        terms: List[str] = []
        if current_question_meta.get("evaluation_focus"):
            terms.extend(current_question_meta.get("evaluation_focus") or [])
        if current_question_meta.get("selected_followups"):
            terms.extend(current_question_meta.get("selected_followups") or [])
        if evaluation:
            terms.extend(evaluation.get("gaps") or [])
            terms.extend(evaluation.get("unresolved_gaps") or [])
            if evaluation.get("next_focus"):
                terms.append(evaluation.get("next_focus"))
            next_best_followup = evaluation.get("next_best_followup") or {}
            if isinstance(next_best_followup, dict):
                if next_best_followup.get("target_gap"):
                    terms.append(next_best_followup.get("target_gap"))
                terms.extend(next_best_followup.get("target_evidence") or [])
            for item in evaluation.get("panel_views") or []:
                if isinstance(item, dict) and item.get("summary"):
                    terms.append(item.get("summary"))
        return InterviewService._unique_strings(terms, limit=10)

    @staticmethod
    def _extract_followup_candidates(
        current_question_meta: Dict,
        evaluation: Optional[Dict],
    ) -> List[str]:
        ordered: List[str] = []

        def add_many(values):
            for value in values or []:
                if value is None:
                    continue
                text = str(value).strip()
                if text and text not in ordered:
                    ordered.append(text)

        moderator_evaluation = (evaluation or {}).get("moderator") or {}
        next_best_followup = (
            (evaluation or {}).get("next_best_followup")
            or moderator_evaluation.get("next_best_followup")
            or {}
        )
        if isinstance(next_best_followup, dict):
            add_many([next_best_followup.get("question")])
        add_many(moderator_evaluation.get("selected_followups") or [])
        add_many((evaluation or {}).get("selected_followups") or [])
        for item in (evaluation or {}).get("panel") or []:
            if isinstance(item, dict):
                add_many(item.get("followup_candidates") or [])
        add_many(current_question_meta.get("selected_followups") or [])
        return ordered[:5]

    @staticmethod
    def _apply_followup_to_next_question(
        current_question_meta: Dict,
        next_question_meta: Dict,
        evaluation: Optional[Dict],
    ) -> Dict:
        moderator_evaluation = (evaluation or {}).get("moderator") or {}
        next_best_followup = (
            (evaluation or {}).get("next_best_followup")
            or moderator_evaluation.get("next_best_followup")
            or {}
        )
        followups = InterviewService._extract_followup_candidates(current_question_meta, evaluation)
        if not followups:
            return next_question_meta

        next_meta = dict(next_question_meta)
        next_meta["question"] = followups[0]
        next_meta["stage"] = current_question_meta.get("stage") or next_meta.get("stage")
        next_meta["category"] = current_question_meta.get("category") or next_meta.get("category")
        next_meta["lead_role"] = current_question_meta.get("lead_role") or next_meta.get("lead_role")
        next_meta["support_roles"] = (
            current_question_meta.get("support_roles") or next_meta.get("support_roles") or []
        )
        next_meta["intent"] = (
            (evaluation or {}).get("next_focus")
            or current_question_meta.get("intent")
            or next_meta.get("intent")
        )
        next_meta["evaluation_focus"] = (
            (evaluation or {}).get("gaps")
            or current_question_meta.get("evaluation_focus")
            or next_meta.get("evaluation_focus")
            or []
        )
        next_meta["selected_followups"] = followups[1:]
        next_meta["followup_source_question_index"] = current_question_meta.get("index")
        next_meta["is_dynamic_followup"] = True
        next_meta["blueprint_track"] = (
            current_question_meta.get("blueprint_track") or next_meta.get("blueprint_track")
        )
        next_meta["blueprint_requirement_status"] = (
            current_question_meta.get("blueprint_requirement_status")
            or next_meta.get("blueprint_requirement_status")
        )
        next_meta["blueprint_evidence_ids"] = (
            current_question_meta.get("blueprint_evidence_ids")
            or next_meta.get("blueprint_evidence_ids")
            or []
        )
        next_meta["blueprint_evidence_summary"] = InterviewService._unique_strings(
            [
                *(current_question_meta.get("blueprint_evidence_summary") or []),
                *(next_meta.get("blueprint_evidence_summary") or []),
            ],
            limit=4,
        )
        next_meta["blueprint_high_risk_claims"] = InterviewService._unique_strings(
            [
                *(current_question_meta.get("blueprint_high_risk_claims") or []),
                *(next_meta.get("blueprint_high_risk_claims") or []),
            ],
            limit=4,
        )
        if isinstance(next_best_followup, dict):
            next_meta["question_target_gap"] = (
                str(next_best_followup.get("target_gap") or "").strip()
                or current_question_meta.get("question_target_gap")
                or next_meta.get("question_target_gap")
            )
            next_meta["question_target_evidence"] = InterviewService._unique_strings(
                [
                    *(next_best_followup.get("target_evidence") or []),
                    *(current_question_meta.get("question_target_evidence") or []),
                ],
                limit=4,
            )
            next_meta["question_target_evidence_ids"] = InterviewService._question_target_evidence_ids(
                {
                    **next_meta,
                    "question_target_evidence_ids": [
                        *(next_best_followup.get("evidence_source_ids") or []),
                        *(current_question_meta.get("question_target_evidence_ids") or []),
                    ],
                }
            )
            next_meta["question_reason"] = (
                str(next_best_followup.get("reason") or "").strip()
                or current_question_meta.get("question_reason")
                or next_meta.get("question_reason")
            )

        panel_context = dict(current_question_meta.get("panel_context") or {})
        moderator = dict(panel_context.get("moderator") or {})
        moderator["selected_question"] = followups[0]
        moderator["selected_followups"] = followups[1:]
        if isinstance(next_best_followup, dict) and next_best_followup:
            moderator["next_best_followup"] = next_best_followup
        if (evaluation or {}).get("moderator", {}).get("reasoning_summary"):
            moderator["reasoning_summary"] = evaluation["moderator"]["reasoning_summary"]
        if (evaluation or {}).get("moderator", {}).get("difficulty_hint"):
            moderator["difficulty_hint"] = evaluation["moderator"]["difficulty_hint"]
        if moderator:
            panel_context["moderator"] = moderator
            next_meta["panel_context"] = panel_context

        next_meta.update(InterviewService._derive_question_target_fields(next_meta))
        return next_meta

    @staticmethod
    def _reroute_question_slices(
        question_meta: Dict,
        knowledge_base: Optional[Dict],
        parsed_resume: Dict,
        target_position: str,
        difficulty: str,
        context_terms: Optional[Sequence[str]] = None,
    ) -> Dict:
        if not knowledge_base or not (knowledge_base.get("slices") or []):
            return question_meta

        resume_text = InterviewService._resume_route_text(parsed_resume)
        resume_skills = InterviewService._route_values_to_texts(parsed_resume.get("skills"), 12)
        resume_projects = InterviewService._route_values_to_texts(parsed_resume.get("projects"), 6)
        query_parts = [
            target_position,
            resume_text,
            question_meta.get("question") or "",
            question_meta.get("intent") or "",
            " ".join(question_meta.get("evaluation_focus") or []),
            " ".join(context_terms or []),
        ]
        try:
            selected = position_knowledge_base_slice_service.rank_slices(
                slices=knowledge_base.get("slices") or [],
                query_text="\n".join(part for part in query_parts if part),
                stage=question_meta.get("stage"),
                role=question_meta.get("lead_role"),
                scene=question_meta.get("category") or question_meta.get("stage"),
                difficulty=difficulty,
                skills=resume_skills[:8],
                topics=[target_position, *(resume_projects[:2])],
                weakness_terms=context_terms or [],
                top_k=2,
            )
        except Exception as exc:
            logger.warning("Question slice reroute failed for question index=%s: %s", question_meta.get("index"), exc)
            return question_meta

        if not selected:
            return question_meta

        next_meta = dict(question_meta)
        next_meta["selected_slices"] = [
            InterviewService._compact_slice(slice_item) for slice_item in selected
        ]
        next_meta["used_slice_ids"] = [
            item.get("slice_id") for item in next_meta["selected_slices"] if item.get("slice_id")
        ]
        next_meta["evidence_trace"] = InterviewService._build_evidence_trace(
            next_meta["selected_slices"],
            used_slice_ids=next_meta["used_slice_ids"],
        )
        next_meta["evidence_summary"] = InterviewService._build_evidence_summary(
            next_meta["selected_slices"],
            used_slice_ids=next_meta["used_slice_ids"],
        )
        panel_context = dict(next_meta.get("panel_context") or {})
        metadata = dict(panel_context.get("metadata") or {})
        metadata["retrieved_slice_ids"] = next_meta["used_slice_ids"]
        metadata["grounding_confidence_summary"] = InterviewService._grounding_confidence_summary(
            next_meta["selected_slices"]
        )
        if metadata:
            panel_context["metadata"] = metadata
            next_meta["panel_context"] = panel_context
        next_meta.update(InterviewService._derive_question_target_fields(next_meta))
        return next_meta

    @staticmethod
    async def _evaluate_round(
        interview_mode: str,
        question: str,
        answer: str,
        resume_context: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
        knowledge_base: Optional[Dict[str, Any]],
        question_meta: Dict[str, Any],
        panel_snapshot: Optional[Dict[str, Any]],
        ai_config: Optional[Dict[str, Any]],
    ) -> tuple[str, Dict[str, Any]]:
        evaluation_mode = interview_mode
        try:
            if interview_mode == "panel":
                evaluation = await AIService.evaluate_answer_with_panel(
                    question=question,
                    answer=answer,
                    resume_context=resume_context,
                    chat_history=chat_history,
                    knowledge_base=knowledge_base,
                    question_meta=question_meta,
                    panel_snapshot=panel_snapshot,
                    ai_config=ai_config,
                )
            else:
                evaluation = await AIService.evaluate_answer(
                    question=question,
                    answer=answer,
                    resume_context=resume_context,
                    chat_history=chat_history,
                    knowledge_base=knowledge_base,
                    question_meta=question_meta,
                    ai_config=ai_config,
                )
        except Exception as exc:
            if interview_mode != "panel":
                raise
            logger.warning("Panel evaluation failed, fallback to single mode: %s", exc)
            evaluation_mode = "single_fallback"
            evaluation = await AIService.evaluate_answer(
                question=question,
                answer=answer,
                resume_context=resume_context,
                chat_history=chat_history,
                knowledge_base=knowledge_base,
                question_meta=question_meta,
                ai_config=ai_config,
            )
        return evaluation_mode, evaluation

    @staticmethod
    def _build_report_signals(questions: List[Dict]) -> Dict:
        gap_counter: Counter = Counter()
        strength_counter: Counter = Counter()
        slice_ids: List[int] = []
        training_priorities: List[str] = []
        panel_notes: Dict[str, List[str]] = {}
        evidence_summary: List[str] = []
        followup_loop_summary: List[str] = []
        claim_confidence_summary: List[str] = []
        grounding_counts: Counter = Counter()
        grounding_warnings: List[str] = []
        low_confidence_slice_ids: List[int] = []
        evidence_question_count = 0

        for question in questions:
            evaluation = question.get("evaluation") or {}
            unresolved_gaps = InterviewService._unique_strings(
                [
                    *(evaluation.get("unresolved_gaps") or []),
                    *(evaluation.get("gaps") or []),
                ],
                limit=5,
            )
            for item in unresolved_gaps:
                text = str(item).strip()
                if text:
                    gap_counter[text] += 1
            for item in evaluation.get("strengths") or []:
                text = str(item).strip()
                if text:
                    strength_counter[text] += 1
            for item in evaluation.get("evidence_strength_delta") or []:
                if not isinstance(item, dict):
                    continue
                evidence_text = str(item.get("evidence") or "").strip()
                delta = str(item.get("delta") or "").strip()
                reason = str(item.get("reason") or "").strip()
                if evidence_text and delta in {"strengthened", "increased"}:
                    strength_counter[evidence_text] += 1
                elif evidence_text and delta in {"weakened", "insufficient"}:
                    gap_counter[evidence_text] += 1
                if evidence_text:
                    summary_text = f"{evidence_text}：{delta or 'unchanged'}"
                    if reason:
                        summary_text = f"{summary_text}（{reason}）"
                    if summary_text not in followup_loop_summary:
                        followup_loop_summary.append(summary_text)
            for item in evaluation.get("claim_confidence_change") or []:
                if not isinstance(item, dict):
                    continue
                claim = str(item.get("claim") or "").strip()
                if not claim:
                    continue
                before_level = str(item.get("from_level") or "").strip()
                after_level = str(item.get("to_level") or "").strip()
                reason = str(item.get("reason") or "").strip()
                summary_text = f"“{claim}”置信度 {before_level or '-'} -> {after_level or '-'}"
                if reason:
                    summary_text = f"{summary_text}（{reason}）"
                if summary_text not in claim_confidence_summary:
                    claim_confidence_summary.append(summary_text)
            next_focus = str(evaluation.get("next_focus") or "").strip()
            if next_focus:
                training_priorities.append(next_focus)
            next_best_followup = evaluation.get("next_best_followup") or {}
            if isinstance(next_best_followup, dict):
                if next_best_followup.get("target_gap"):
                    training_priorities.append(str(next_best_followup.get("target_gap")).strip())
                followup_reason = str(next_best_followup.get("reason") or "").strip()
                followup_question = str(next_best_followup.get("question") or "").strip()
                if followup_question:
                    summary_text = f"建议继续追问：{followup_question}"
                    if followup_reason:
                        summary_text = f"{summary_text}（{followup_reason}）"
                    if summary_text not in followup_loop_summary:
                        followup_loop_summary.append(summary_text)

            for value in question.get("used_slice_ids") or []:
                try:
                    slice_id = int(value)
                except (TypeError, ValueError):
                    continue
                if slice_id not in slice_ids:
                    slice_ids.append(slice_id)

            question_evidence_summary = InterviewService._unique_strings(
                question.get("evidence_summary") or [],
                limit=3,
            )
            if question_evidence_summary:
                evidence_question_count += 1
                for item in question_evidence_summary:
                    if item not in evidence_summary:
                        evidence_summary.append(item)
            grounding_summary = InterviewService._grounding_confidence_summary(
                question.get("selected_slices") or []
            )
            for level, count in (grounding_summary.get("counts") or {}).items():
                if count:
                    grounding_counts[level] += count
            for warning in grounding_summary.get("warnings") or []:
                if warning not in grounding_warnings:
                    grounding_warnings.append(warning)
            for slice_id in grounding_summary.get("low_confidence_slice_ids") or []:
                if slice_id not in low_confidence_slice_ids:
                    low_confidence_slice_ids.append(slice_id)

            for item in evaluation.get("panel_views") or []:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "").strip()
                summary = str(item.get("summary") or "").strip()
                if role and summary:
                    panel_notes.setdefault(role, []).append(summary)

        panel_summary = []
        for role, summaries in panel_notes.items():
            panel_summary.append(
                {
                    "role": role,
                    "title": PANEL_ROLE_TITLES.get(role, role),
                    "summary": " ".join(InterviewService._unique_strings(summaries, limit=3)),
                }
            )

        return {
            "common_gaps": [item for item, _ in gap_counter.most_common(5)],
            "common_strengths": [item for item, _ in strength_counter.most_common(5)],
            "training_priorities": InterviewService._unique_strings(
                [*training_priorities, *[item for item, _ in gap_counter.most_common(3)]],
                limit=5,
            ),
            "panel_summary": panel_summary,
            "retrieved_slice_ids": slice_ids,
            "evidence_summary": evidence_summary[:6],
            "followup_loop_summary": followup_loop_summary[:6],
            "claim_confidence_summary": claim_confidence_summary[:6],
            "grounding_confidence_summary": {
                "counts": dict(grounding_counts),
                "warnings": grounding_warnings[:6],
                "low_confidence_slice_ids": low_confidence_slice_ids[:6],
            },
            "evidence_stats": {
                "questions_with_evidence": evidence_question_count,
                "total_questions": len(questions),
                "retrieved_slice_count": len(slice_ids),
            },
        }

    @staticmethod
    def _merge_report_defaults(
        report: Dict,
        report_signals: Dict,
        interview_mode: str,
    ) -> Dict:
        merged = dict(report or {})
        if not merged.get("weaknesses") and report_signals.get("common_gaps"):
            merged["weaknesses"] = report_signals["common_gaps"]
        if not merged.get("strengths") and report_signals.get("common_strengths"):
            merged["strengths"] = report_signals["common_strengths"]
        if not merged.get("training_priorities") and report_signals.get("training_priorities"):
            merged["training_priorities"] = report_signals["training_priorities"]
        if not merged.get("common_gaps") and report_signals.get("common_gaps"):
            merged["common_gaps"] = report_signals["common_gaps"]
        if not merged.get("common_strengths") and report_signals.get("common_strengths"):
            merged["common_strengths"] = report_signals["common_strengths"]
        if interview_mode == "panel" and not merged.get("panel_summary") and report_signals.get("panel_summary"):
            merged["panel_summary"] = report_signals["panel_summary"]
        if not merged.get("evidence_summary") and report_signals.get("evidence_summary"):
            merged["evidence_summary"] = report_signals["evidence_summary"]
        if not merged.get("followup_loop_summary") and report_signals.get("followup_loop_summary"):
            merged["followup_loop_summary"] = report_signals["followup_loop_summary"]
        if not merged.get("claim_confidence_summary") and report_signals.get("claim_confidence_summary"):
            merged["claim_confidence_summary"] = report_signals["claim_confidence_summary"]
        if not merged.get("grounding_confidence_summary") and report_signals.get("grounding_confidence_summary"):
            merged["grounding_confidence_summary"] = report_signals["grounding_confidence_summary"]
        if not merged.get("evidence_stats") and report_signals.get("evidence_stats"):
            merged["evidence_stats"] = report_signals["evidence_stats"]
        return merged

    @staticmethod
    def _json_dict_from_text(value: Optional[str]) -> Dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            return str(value)

    @staticmethod
    def _normalize_training_sample_review(review: Any) -> Dict[str, Any]:
        raw = review if isinstance(review, dict) else {}
        quality_tier = str(raw.get("quality_tier") or "needs_review").strip().lower()
        if quality_tier not in TRAINING_SAMPLE_QUALITY_TIERS:
            quality_tier = "needs_review"

        notes = str(raw.get("notes") or "").strip()
        if len(notes) > 2000:
            notes = notes[:2000]
        human_score_notes = str(raw.get("human_score_notes") or "").strip()
        if len(human_score_notes) > 2000:
            human_score_notes = human_score_notes[:2000]

        dataset_split = str(raw.get("dataset_split") or "").strip().lower()
        if dataset_split not in TRAINING_SAMPLE_DATASET_SPLITS:
            dataset_split = ""

        def clean_text(key: str, limit: int) -> str:
            value = str(raw.get(key) or "").strip()
            return value[:limit] if len(value) > limit else value

        def clean_score(key: str) -> Optional[float]:
            value = raw.get(key)
            if value in (None, ""):
                return None
            try:
                score = float(value)
            except (TypeError, ValueError):
                return None
            return max(0.0, min(10.0, round(score, 1)))

        normalized = {
            "quality_tier": quality_tier,
            "is_high_quality": bool(raw.get("is_high_quality")),
            "has_hallucination": bool(raw.get("has_hallucination")),
            "followup_worthy": bool(raw.get("followup_worthy")),
            "report_actionable": bool(raw.get("report_actionable")),
            "notes": notes,
            "case_id": clean_text("case_id", 64),
            "resume_source": clean_text("resume_source", 255),
            "human_overall_score": clean_score("human_overall_score"),
            "evidence_alignment_score": clean_score("evidence_alignment_score"),
            "question_quality_score": clean_score("question_quality_score"),
            "report_actionability_score": clean_score("report_actionability_score"),
            "learning_task_actionability_score": clean_score("learning_task_actionability_score"),
            "human_score_notes": human_score_notes,
            "dataset_split": dataset_split,
            "reviewed_at": raw.get("reviewed_at"),
            "reviewer_email": raw.get("reviewer_email"),
        }
        normalized["review_status"] = "reviewed" if normalized.get("reviewed_at") else "pending"
        normalized["export_recommended"] = bool(
            normalized["is_high_quality"] and not normalized["has_hallucination"]
        )
        return normalized

    @staticmethod
    def get_training_sample_review(panel_snapshot: Any) -> Dict[str, Any]:
        snapshot = panel_snapshot if isinstance(panel_snapshot, dict) else {}
        return InterviewService._normalize_training_sample_review(snapshot.get("training_sample_review") or {})

    @staticmethod
    async def update_training_sample_review(
        db: AsyncSession,
        interview_id: int,
        review_data: Dict[str, Any],
        reviewer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        interview = await db.get(Interview, interview_id)
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        panel_snapshot = interview.panel_snapshot if isinstance(interview.panel_snapshot, dict) else {}
        next_review = InterviewService._normalize_training_sample_review(review_data)
        next_review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        next_review["reviewer_email"] = reviewer_email or next_review.get("reviewer_email")
        next_review["review_status"] = "reviewed"
        next_review["export_recommended"] = bool(
            next_review["is_high_quality"] and not next_review["has_hallucination"]
        )

        interview.panel_snapshot = {
            **panel_snapshot,
            "training_sample_review": next_review,
        }
        await db.commit()
        await db.refresh(interview)
        return next_review

    @staticmethod
    def build_training_sample(
        interview: Interview,
        messages: Optional[Sequence[InterviewMessage]] = None,
        user_email: Optional[str] = None,
        include_user_email: bool = False,
    ) -> Dict[str, Any]:
        questions = InterviewService._serialize_questions(interview.questions_data or [])
        report = InterviewService._json_dict_from_text(interview.report)
        panel_snapshot = interview.panel_snapshot if isinstance(interview.panel_snapshot, dict) else {}
        knowledge_base_snapshot = (
            interview.knowledge_base_snapshot
            if isinstance(interview.knowledge_base_snapshot, dict)
            else {}
        )
        interview_blueprint = panel_snapshot.get("interview_blueprint") or {}
        training_sample_review = InterviewService.get_training_sample_review(panel_snapshot)
        answer_by_index: Dict[int, InterviewMessage] = {}
        for item in messages or []:
            if item.role == "candidate" and item.question_index is not None:
                answer_by_index[int(item.question_index)] = item

        rounds = []
        retrieved_slice_ids: List[int] = []
        for index, question in enumerate(questions):
            question_index = int(question.get("index") if question.get("index") is not None else index)
            message = answer_by_index.get(question_index)
            evaluation = question.get("evaluation") or {}
            used_slice_ids = []
            for value in question.get("used_slice_ids") or []:
                try:
                    slice_id = int(value)
                except (TypeError, ValueError):
                    continue
                used_slice_ids.append(slice_id)
                if slice_id not in retrieved_slice_ids:
                    retrieved_slice_ids.append(slice_id)
            round_score = question.get("score")
            if round_score is None and message and message.score is not None:
                round_score = float(message.score)

            answer = question.get("answer") or (message.content if message else "")
            feedback = question.get("feedback") or (message.feedback if message else "")
            round_item = {
                "question_index": question_index,
                "question": question.get("question"),
                "answer": answer,
                "score": float(round_score) if round_score is not None else None,
                "feedback": feedback or "",
                "category": question.get("category"),
                "stage": question.get("stage"),
                "lead_role": question.get("lead_role"),
                "interview_mode": question.get("interview_mode") or interview.interview_mode,
                "question_target_gap": question.get("question_target_gap"),
                "question_target_evidence": question.get("question_target_evidence") or [],
                "question_target_evidence_ids": question.get("question_target_evidence_ids") or [],
                "question_reason": question.get("question_reason"),
                "used_slice_ids": used_slice_ids,
                "evidence_trace": question.get("evidence_trace") or [],
                "evidence_summary": question.get("evidence_summary") or [],
                "blueprint_track": question.get("blueprint_track"),
                "blueprint_requirement_status": question.get("blueprint_requirement_status"),
                "selected_followups": question.get("selected_followups") or [],
                "evaluation": {
                    "strengths": evaluation.get("strengths") or [],
                    "gaps": evaluation.get("gaps") or [],
                    "unresolved_gaps": evaluation.get("unresolved_gaps") or [],
                    "evidence_strength_delta": evaluation.get("evidence_strength_delta") or [],
                    "claim_confidence_change": evaluation.get("claim_confidence_change") or [],
                    "next_best_followup": evaluation.get("next_best_followup"),
                    "panel_views": evaluation.get("panel_views") or [],
                    "evaluation_mode": evaluation.get("evaluation_mode"),
                },
                "sample_flags": {
                    "has_answer": bool((answer or "").strip()),
                    "has_evidence": bool(question.get("evidence_trace") or question.get("evidence_summary")),
                    "has_followup_loop": bool(
                        evaluation.get("next_best_followup")
                        or evaluation.get("evidence_strength_delta")
                        or evaluation.get("claim_confidence_change")
                    ),
                    "high_score_candidate": bool(round_score is not None and float(round_score) >= 8),
                },
            }
            rounds.append(round_item)

        report_summary = {
            "overall_score": float(interview.overall_score) if interview.overall_score is not None else None,
            "common_gaps": report.get("common_gaps") or [],
            "common_strengths": report.get("common_strengths") or [],
            "training_priorities": report.get("training_priorities") or [],
            "followup_loop_summary": report.get("followup_loop_summary") or [],
            "claim_confidence_summary": report.get("claim_confidence_summary") or [],
            "evidence_summary": report.get("evidence_summary") or [],
        }
        interview_meta = {
            "id": interview.id,
            "target_position": interview.target_position,
            "difficulty": interview.difficulty,
            "interview_mode": interview.interview_mode,
            "status": interview.status,
            "total_questions": interview.total_questions,
            "overall_score": float(interview.overall_score) if interview.overall_score is not None else None,
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
        }
        if include_user_email and user_email:
            interview_meta["user_email"] = user_email

        sample = {
            "sample_version": "ai-interview.training-sample.v1",
            "interview": interview_meta,
            "evidence_context": {
                "knowledge_base_id": interview.knowledge_base_id,
                "knowledge_base_title": knowledge_base_snapshot.get("title"),
                "interview_blueprint": interview_blueprint,
                "retrieved_slice_ids": retrieved_slice_ids,
                "blueprint_evidence_summary": (interview_blueprint.get("evidence_summary") or [])[:6]
                if isinstance(interview_blueprint, dict)
                else [],
            },
            "rounds": rounds,
            "report_summary": report_summary,
            "training_sample_review": training_sample_review,
            "export_notes": {
                "pii_included": bool(include_user_email and user_email),
                "review_status": training_sample_review.get("review_status"),
                "export_recommended": training_sample_review.get("export_recommended"),
                "intended_use": "offline review, hallucination analysis, follow-up quality review, and future fine-tuning preparation",
            },
        }
        return json.loads(json.dumps(sample, ensure_ascii=False, default=InterviewService._json_safe))

    @staticmethod
    async def get_completed_training_samples(
        db: AsyncSession,
        include_user_email: bool = False,
        min_score: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            select(Interview, User.email)
            .join(User, Interview.user_id == User.id)
            .where(Interview.status == "completed")
            .order_by(Interview.created_at.desc())
        )
        if min_score is not None:
            query = query.where(Interview.overall_score >= min_score)
        if limit is not None:
            query = query.limit(limit)

        result = await db.execute(query)
        rows = result.all()
        interview_ids = [interview.id for interview, _ in rows]
        messages_by_interview = {interview_id: [] for interview_id in interview_ids}

        if interview_ids:
            msg_result = await db.execute(
                select(InterviewMessage)
                .where(InterviewMessage.interview_id.in_(interview_ids))
                .order_by(InterviewMessage.interview_id, InterviewMessage.id)
            )
            for message in msg_result.scalars().all():
                messages_by_interview.setdefault(message.interview_id, []).append(message)

        samples: List[Dict[str, Any]] = []
        for interview, email in rows:
            try:
                samples.append(
                    InterviewService.build_training_sample(
                        interview=interview,
                        messages=messages_by_interview.get(interview.id, []),
                        user_email=email,
                        include_user_email=include_user_email,
                    )
                )
            except Exception as exc:
                logger.warning("Skip malformed training sample interview_id=%s: %s", interview.id, exc)
        return samples

    @staticmethod
    def _sample_has_followup_signal(sample: Dict[str, Any]) -> bool:
        for round_item in sample.get("rounds") or []:
            evaluation = round_item.get("evaluation") or {}
            if (
                evaluation.get("next_best_followup")
                or evaluation.get("evidence_strength_delta")
                or evaluation.get("claim_confidence_change")
            ):
                return True
        return False

    @staticmethod
    def _sample_has_report_signal(sample: Dict[str, Any]) -> bool:
        report = sample.get("report_summary") or {}
        return bool(
            report.get("common_gaps")
            or report.get("common_strengths")
            or report.get("training_priorities")
        )

    @staticmethod
    def _match_evaluation_datasets(sample: Dict[str, Any]) -> Dict[str, List[str]]:
        interview = sample.get("interview") or {}
        review = sample.get("training_sample_review") or {}
        try:
            overall_score = float(interview.get("overall_score") or 0)
        except (TypeError, ValueError):
            overall_score = 0.0
        base_rules = [
            "status=completed",
            "training_sample_review.review_status=reviewed",
        ]
        if interview.get("status") != "completed" or review.get("review_status") != "reviewed":
            return {}

        matched: Dict[str, List[str]] = {}
        if review.get("is_high_quality") and not review.get("has_hallucination") and overall_score >= 7.5:
            matched["golden_cases"] = [
                *base_rules,
                "training_sample_review.is_high_quality=true",
                "training_sample_review.has_hallucination=false",
                "overall_score>=7.5",
            ]
        if review.get("has_hallucination"):
            matched["hallucination_cases"] = [
                *base_rules,
                "training_sample_review.has_hallucination=true",
            ]
        if (
            review.get("followup_worthy")
            and not review.get("has_hallucination")
            and overall_score >= 6.0
            and InterviewService._sample_has_followup_signal(sample)
        ):
            matched["followup_quality_cases"] = [
                *base_rules,
                "training_sample_review.followup_worthy=true",
                "training_sample_review.has_hallucination=false",
                "overall_score>=6.0",
                "followup_signal_present=true",
            ]
        if (
            review.get("report_actionable")
            and not review.get("has_hallucination")
            and overall_score >= 6.0
            and InterviewService._sample_has_report_signal(sample)
        ):
            matched["report_quality_cases"] = [
                *base_rules,
                "training_sample_review.report_actionable=true",
                "training_sample_review.has_hallucination=false",
                "overall_score>=6.0",
                "report_signal_present=true",
            ]
        return matched

    @staticmethod
    def build_evaluation_dataset_bundle(
        samples: Sequence[Dict[str, Any]],
        include_user_email: bool = False,
    ) -> Dict[str, Any]:
        exported_at = datetime.now(timezone.utc).isoformat()
        dataset_entries: Dict[str, List[Dict[str, Any]]] = {
            item["dataset_type"]: [] for item in EVALUATION_DATASET_DEFINITIONS
        }
        example_ids: Dict[str, List[int]] = {
            item["dataset_type"]: [] for item in EVALUATION_DATASET_DEFINITIONS
        }
        reviewed_samples = 0

        for sample in samples:
            review = sample.get("training_sample_review") or {}
            if review.get("review_status") == "reviewed":
                reviewed_samples += 1

            membership = InterviewService._match_evaluation_datasets(sample)
            interview_id = int((sample.get("interview") or {}).get("id") or 0)
            for dataset_type, matched_rules in membership.items():
                dataset_sample = json.loads(
                    json.dumps(sample, ensure_ascii=False, default=InterviewService._json_safe)
                )
                dataset_sample["dataset_membership"] = {
                    "dataset_type": dataset_type,
                    "matched_rules": matched_rules,
                }
                dataset_entries[dataset_type].append(dataset_sample)
                if interview_id and interview_id not in example_ids[dataset_type] and len(example_ids[dataset_type]) < 5:
                    example_ids[dataset_type].append(interview_id)

        preview_datasets = []
        manifest_datasets = []
        files: Dict[str, str] = {}
        for definition in EVALUATION_DATASET_DEFINITIONS:
            dataset_type = definition["dataset_type"]
            filename = definition["filename"]
            items = dataset_entries[dataset_type]
            files[filename] = "\n".join(
                json.dumps(item, ensure_ascii=False) for item in items
            )
            dataset_preview = {
                "dataset_type": dataset_type,
                "filename": filename,
                "label": definition["label"],
                "description": definition["description"],
                "count": len(items),
                "example_interview_ids": example_ids[dataset_type],
                "rules": definition["rules"],
            }
            preview_datasets.append(dataset_preview)
            manifest_datasets.append(dataset_preview)

        filters = {
            "base_requirements": [
                "status=completed",
                "training_sample_review.review_status=reviewed",
            ],
            "thresholds": {
                "golden_cases_min_score": 7.5,
                "followup_quality_cases_min_score": 6.0,
                "report_quality_cases_min_score": 6.0,
            },
            "overlap_allowed": True,
            "pii_included": include_user_email,
        }

        preview = {
            "schema_version": EVALUATION_DATASET_SCHEMA_VERSION,
            "generated_at": exported_at,
            "filters": filters,
            "stats": {
                "completed_samples": len(samples),
                "reviewed_samples": reviewed_samples,
                "dataset_assignments": sum(len(items) for items in dataset_entries.values()),
            },
            "datasets": preview_datasets,
        }
        manifest = {
            "schema_version": EVALUATION_DATASET_SCHEMA_VERSION,
            "exported_at": exported_at,
            "filters": filters,
            "datasets": manifest_datasets,
            "counts": {
                definition["filename"]: len(dataset_entries[definition["dataset_type"]])
                for definition in EVALUATION_DATASET_DEFINITIONS
            },
            "pii_included": include_user_email,
        }
        return {
            "preview": preview,
            "manifest": manifest,
            "files": files,
        }

    @staticmethod
    def build_evaluation_dataset_zip(bundle: Dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(bundle.get("manifest") or {}, ensure_ascii=False, indent=2),
            )
            for filename, content in (bundle.get("files") or {}).items():
                archive.writestr(filename, content or "")
        return buffer.getvalue()

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 28) -> List[str]:
        content = text or ""
        if not content:
            return [""]
        return [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]

    @staticmethod
    async def _resolve_knowledge_base(
        db: AsyncSession,
        user_id: int,
        target_position: str,
        knowledge_base_id: Optional[int] = None,
    ) -> Optional[Dict]:
        if knowledge_base_id:
            result = await db.execute(
                select(PositionKnowledgeBase).where(
                    PositionKnowledgeBase.id == knowledge_base_id,
                    or_(
                        PositionKnowledgeBase.user_id == user_id,
                        PositionKnowledgeBase.scope == "public",
                    ),
                )
            )
            knowledge_base = result.scalar_one_or_none()
            if not knowledge_base:
                raise NotFoundError(message="岗位知识库不存在")
            if not knowledge_base.is_active:
                raise ValidationError(message="所选岗位知识库已停用，请重新选择")
        else:
            normalized_target = (target_position or "").strip()
            if not normalized_target:
                return None
            result = await db.execute(
                select(PositionKnowledgeBase)
                .where(
                    PositionKnowledgeBase.user_id == user_id,
                    PositionKnowledgeBase.scope == "private",
                    PositionKnowledgeBase.is_active.is_(True),
                    PositionKnowledgeBase.target_position.ilike(f"%{normalized_target}%"),
                )
                .order_by(PositionKnowledgeBase.updated_at.desc())
            )
            knowledge_base = result.scalars().first()
            if not knowledge_base:
                result = await db.execute(
                    select(PositionKnowledgeBase)
                    .where(
                        PositionKnowledgeBase.scope == "public",
                        PositionKnowledgeBase.is_active.is_(True),
                        PositionKnowledgeBase.target_position.ilike(f"%{normalized_target}%"),
                    )
                    .order_by(PositionKnowledgeBase.updated_at.desc())
                )
                knowledge_base = result.scalars().first()

        payload = InterviewService._serialize_knowledge_base(knowledge_base)
        if not payload:
            return None
        try:
            slices = await position_knowledge_base_slice_service.list_for_knowledge_base(db, knowledge_base.id)
            payload["slices"] = [InterviewService._compact_slice(item) for item in slices]
            payload["slice_count"] = len(payload["slices"])
            payload["routing_strategy"] = (
                "structured_slice_routing_v1" if payload["slices"] else "full_text_fallback"
            )
        except Exception as exc:
            logger.warning("Knowledge slice loading failed for knowledge_base=%s: %s", knowledge_base.id, exc)
            payload["slices"] = []
            payload["slice_count"] = 0
            payload["routing_strategy"] = "full_text_fallback"
        return payload

    @staticmethod
    async def start_interview(
        db: AsyncSession,
        user_id: int,
        resume_id: int,
        target_position: str,
        knowledge_base_id: Optional[int],
        difficulty: str,
        total_questions: int,
        multi_interviewer_enabled: bool = False,
        ai_config: Optional[Dict] = None,
    ) -> Dict:
        result = await db.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.user_id == user_id,
            )
        )
        resume = result.scalar_one_or_none()
        if not resume:
            raise NotFoundError(message="简历不存在")
        if resume.status != "completed":
            raise ValidationError(message="简历尚未解析完成")

        parsed_resume = InterviewService._load_resume_payload(resume)
        resume_analysis = ensure_resume_evaluation_snapshot(
            InterviewService._load_resume_analysis_payload(resume),
            target_position=target_position or resume.target_position,
        )
        matching_metrics = matching_metrics_from_payload(resume_analysis)
        knowledge_base_context = await InterviewService._resolve_knowledge_base(
            db=db,
            user_id=user_id,
            target_position=target_position,
            knowledge_base_id=knowledge_base_id,
        )
        question_plan = InterviewService._route_question_plan(
            question_plan=InterviewService._build_question_plan(total_questions, difficulty),
            knowledge_base=knowledge_base_context,
            parsed_resume=parsed_resume,
            target_position=target_position,
            difficulty=difficulty,
            matching_metrics=matching_metrics,
        )
        resume_evidence = InterviewService._load_resume_evidence(resume)
        try:
            interview_blueprint = await AIService.extract_interview_blueprint(
                parsed_resume=parsed_resume,
                target_position=target_position,
                resume_evidence=resume_evidence,
                knowledge_base=knowledge_base_context,
                question_plan=question_plan,
                ai_config=ai_config,
            )
        except Exception as exc:
            logger.warning("Interview blueprint generation failed, using fallback: %s", exc)
            interview_blueprint = AIService.build_interview_blueprint_fallback(
                parsed_resume=parsed_resume,
                target_position=target_position,
                resume_evidence=resume_evidence,
                knowledge_base=knowledge_base_context,
                question_plan=question_plan,
            )
        question_plan = InterviewService._apply_blueprint_to_question_plan(
            question_plan=question_plan,
            interview_blueprint=interview_blueprint,
        )

        interview_mode = "panel" if multi_interviewer_enabled else "single"
        panel_snapshot = InterviewService._build_panel_snapshot(interview_mode)
        if interview_blueprint:
            panel_snapshot["interview_blueprint"] = interview_blueprint

        try:
            if interview_mode == "panel":
                panel_payload = await AIService.generate_panel_questions(
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    difficulty=difficulty,
                    count=total_questions,
                    question_plan=question_plan,
                    knowledge_base=knowledge_base_context,
                    panel_snapshot=panel_snapshot,
                    interview_blueprint=interview_blueprint,
                    ai_config=ai_config,
                )
                if panel_payload.get("moderator_style"):
                    panel_snapshot["moderator_style"] = panel_payload["moderator_style"]
                if panel_payload.get("metadata"):
                    panel_snapshot["structured_output"] = {
                        "version": panel_payload["metadata"].get("version"),
                        "retrieved_slice_ids": panel_payload["metadata"].get("retrieved_slice_ids") or [],
                    }
                if panel_payload.get("moderator", {}).get("reasoning_summary"):
                    panel_snapshot["moderator_reasoning_summary"] = panel_payload["moderator"]["reasoning_summary"]
                questions = InterviewService._normalize_questions(
                    raw_questions=panel_payload.get("questions") or [],
                    question_plan=question_plan,
                    interview_mode="panel",
                )
            else:
                raw_questions = await AIService.generate_questions(
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    difficulty=difficulty,
                    count=total_questions,
                    knowledge_base=knowledge_base_context,
                    question_plan=question_plan,
                    interview_blueprint=interview_blueprint,
                    ai_config=ai_config,
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="single",
                )
        except ValidationError as exc:
            raise ValidationError(
                message=InterviewService._format_start_interview_error(exc.detail)
            ) from exc
        except Exception as exc:
            if interview_mode == "panel":
                logger.warning("Panel question generation failed, fallback to single mode: %s", exc)
                try:
                    raw_questions = await AIService.generate_questions(
                        parsed_resume=parsed_resume,
                        target_position=target_position,
                        difficulty=difficulty,
                        count=total_questions,
                        knowledge_base=knowledge_base_context,
                        question_plan=question_plan,
                        interview_blueprint=interview_blueprint,
                        ai_config=ai_config,
                    )
                    questions = InterviewService._normalize_questions(
                        raw_questions=raw_questions,
                        question_plan=question_plan,
                        interview_mode="single",
                    )
                    interview_mode = "single"
                    panel_snapshot = InterviewService._build_panel_snapshot(
                        mode="single",
                        requested_panel=True,
                        fallback_reason="panel_generation_failed",
                    )
                    if interview_blueprint:
                        panel_snapshot["interview_blueprint"] = interview_blueprint
                except ValidationError as inner_exc:
                    raise ValidationError(
                        message=InterviewService._format_start_interview_error(inner_exc.detail)
                    ) from inner_exc
                except Exception as inner_exc:
                    logger.exception("Single question fallback failed: %s", inner_exc)
                    raise ValidationError(
                        message="开始面试失败：题目生成服务异常，请稍后重试"
                    ) from inner_exc
            else:
                logger.exception("Question generation failed: %s", exc)
                raise ValidationError(message="开始面试失败：题目生成服务异常，请稍后重试") from exc

        questions = InterviewService._serialize_questions(questions)
        interview = Interview(
            user_id=user_id,
            resume_id=resume_id,
            knowledge_base_id=knowledge_base_context["id"] if knowledge_base_context else None,
            target_position=target_position,
            difficulty=difficulty,
            total_questions=total_questions,
            current_question_index=0,
            interview_mode=interview_mode,
            questions_data=questions,
            knowledge_base_snapshot=knowledge_base_context,
            panel_snapshot=panel_snapshot,
            status="in_progress",
        )
        db.add(interview)
        try:
            await db.commit()
            await db.refresh(interview)
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Start interview record creation failed: %s", exc)
            raise ValidationError(message=START_INTERVIEW_DB_ERROR_MESSAGE) from exc

        first_question = questions[0]["question"]
        db.add(
            InterviewMessage(
                interview_id=interview.id,
                role="interviewer",
                content=first_question,
                question_index=0,
            )
        )
        try:
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Start interview first message creation failed: %s", exc)
            try:
                await db.execute(sql_delete(Interview).where(Interview.id == interview.id))
                await db.commit()
            except SQLAlchemyError as cleanup_exc:
                await db.rollback()
                logger.warning(
                    "Failed to clean incomplete interview after first message error: interview_id=%s error=%s",
                    interview.id,
                    cleanup_exc,
                )
            raise ValidationError(message=START_INTERVIEW_DB_ERROR_MESSAGE) from exc

        return {
            "interview_id": interview.id,
            "first_question": first_question,
            "question_index": 0,
            "total_questions": total_questions,
            "knowledge_base_title": knowledge_base_context["title"] if knowledge_base_context else None,
            "interview_mode": interview_mode,
            "training_focus": interview_blueprint.get("training_focus") or [],
            "high_risk_claims": InterviewService._blueprint_claim_strings(interview_blueprint),
            "blueprint_evidence_summary": interview_blueprint.get("evidence_summary") or [],
            "interview_blueprint": interview_blueprint,
        }

    @staticmethod
    async def submit_answer(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
        answer: str,
        ai_config: Optional[Dict] = None,
    ) -> Dict:
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")
        if interview.status == "completed":
            raise ValidationError(message="面试已结束")

        resume_result = await db.execute(select(Resume).where(Resume.id == interview.resume_id))
        resume = resume_result.scalar_one_or_none()
        parsed_resume = json.loads(resume.parsed_content) if resume and resume.parsed_content else {}
        knowledge_base_context = interview.knowledge_base_snapshot or None

        messages_result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.interview_id == interview_id)
            .order_by(InterviewMessage.id)
        )
        messages = messages_result.scalars().all()
        chat_history = [{"role": item.role, "content": item.content} for item in messages]

        current_index = interview.current_question_index
        questions = InterviewService._serialize_questions(interview.questions_data or [])
        current_question_meta = dict(questions[current_index])
        current_question = current_question_meta["question"]

        candidate_msg = InterviewMessage(
            interview_id=interview_id,
            role="candidate",
            content=answer,
            question_index=current_index,
        )
        db.add(candidate_msg)

        evaluation_mode, evaluation = await InterviewService._evaluate_round(
            interview_mode=interview.interview_mode,
            question=current_question,
            answer=answer,
            resume_context=parsed_resume,
            chat_history=chat_history,
            knowledge_base=knowledge_base_context,
            question_meta=current_question_meta,
            panel_snapshot=interview.panel_snapshot,
            ai_config=ai_config,
        )

        score = float(evaluation.get("score", 5.0))
        feedback = (evaluation.get("feedback") or "").strip()
        if not feedback:
            feedback = "本轮回答已记录，建议进一步补充关键细节和落地场景。"

        candidate_msg.score = Decimal(str(score))
        candidate_msg.feedback = feedback[:500]

        current_question_meta["used_slice_ids"] = (
            (evaluation.get("metadata") or {}).get("retrieved_slice_ids")
            or current_question_meta.get("used_slice_ids")
            or InterviewService._question_slice_ids(current_question_meta)
        )
        current_question_meta["evidence_trace"] = InterviewService._build_evidence_trace(
            current_question_meta.get("selected_slices") or [],
            used_slice_ids=current_question_meta.get("used_slice_ids") or [],
        )
        current_question_meta["evidence_summary"] = InterviewService._build_evidence_summary(
            current_question_meta.get("selected_slices") or [],
            used_slice_ids=current_question_meta.get("used_slice_ids") or [],
        )
        current_question_meta.update(InterviewService._derive_question_target_fields(current_question_meta))
        current_question_meta["selected_followups"] = (
            (evaluation.get("moderator") or {}).get("selected_followups")
            or evaluation.get("selected_followups")
            or current_question_meta.get("selected_followups")
            or []
        )
        if (evaluation.get("moderator") or {}).get("difficulty_hint"):
            current_question_meta["difficulty_hint"] = evaluation["moderator"]["difficulty_hint"]
        current_question_meta["answer"] = answer
        current_question_meta["score"] = score
        current_question_meta["feedback"] = feedback
        current_question_meta["evaluation"] = {
            **evaluation,
            "evaluation_mode": evaluation_mode,
        }
        questions[current_index] = current_question_meta

        next_index = current_index + 1
        is_finished = next_index >= interview.total_questions
        response = {
            "score": score,
            "feedback": feedback,
            "question_index": current_index,
            "is_finished": is_finished,
            "next_question": None,
            "evidence_summary": current_question_meta.get("evidence_summary") or [],
            "used_slice_ids": current_question_meta.get("used_slice_ids") or [],
            "question_target_gap": current_question_meta.get("question_target_gap"),
            "question_target_evidence": current_question_meta.get("question_target_evidence") or [],
            "question_reason": current_question_meta.get("question_reason"),
            "evidence_strength_delta": evaluation.get("evidence_strength_delta") or [],
            "claim_confidence_change": evaluation.get("claim_confidence_change") or [],
            "unresolved_gaps": evaluation.get("unresolved_gaps") or [],
            "next_best_followup": evaluation.get("next_best_followup"),
        }

        if is_finished:
            interview.questions_data = InterviewService._serialize_questions(questions)
            interview.status = "completed"
            interview.current_question_index = next_index
            scored_values = [
                float(item.get("score"))
                for item in questions
                if item.get("score") is not None
            ]
            overall = round(sum(scored_values) / len(scored_values), 1) if scored_values else 0
            interview.overall_score = Decimal(str(overall))

            qa_data = InterviewService._build_qa_data(questions)
            report_signals = InterviewService._build_report_signals(questions)
            try:
                if interview.interview_mode == "panel":
                    report = await AIService.generate_panel_report(
                        parsed_resume=parsed_resume,
                        target_position=interview.target_position,
                        questions_and_scores=qa_data,
                        knowledge_base=knowledge_base_context,
                        panel_snapshot=interview.panel_snapshot,
                        report_signals=report_signals,
                        ai_config=ai_config,
                    )
                else:
                    report = await AIService.generate_report(
                        parsed_resume=parsed_resume,
                        target_position=interview.target_position,
                        questions_and_scores=qa_data,
                        knowledge_base=knowledge_base_context,
                        panel_snapshot=interview.panel_snapshot,
                        report_signals=report_signals,
                        ai_config=ai_config,
                    )
            except Exception as exc:
                logger.warning("Primary report generation failed, fallback to single report: %s", exc)
                report = await AIService.generate_report(
                    parsed_resume=parsed_resume,
                    target_position=interview.target_position,
                    questions_and_scores=qa_data,
                    knowledge_base=knowledge_base_context,
                    panel_snapshot=interview.panel_snapshot,
                    report_signals=report_signals,
                    ai_config=ai_config,
                )
                report["fallback_mode"] = "single_report_fallback"

            report = InterviewService._merge_report_defaults(
                report=report,
                report_signals=report_signals,
                interview_mode=interview.interview_mode,
            )
            resume_analysis = ensure_resume_evaluation_snapshot(
                InterviewService._load_resume_analysis_payload(resume) if resume else {},
                target_position=interview.target_position,
            )
            if resume_analysis.get("matching_metrics") and not report.get("matching_metrics"):
                report["matching_metrics"] = resume_analysis["matching_metrics"]
            if resume_analysis.get("resume_evaluation_snapshot") and not report.get("resume_evaluation_snapshot"):
                report["resume_evaluation_snapshot"] = resume_analysis["resume_evaluation_snapshot"]
            if resume_analysis.get("ability_gap_profile") and not report.get("ability_gap_profile"):
                report["ability_gap_profile"] = resume_analysis["ability_gap_profile"]
            if resume_analysis.get("learning_plan") and not report.get("learning_plan"):
                report["learning_plan"] = resume_analysis["learning_plan"]
            report["question_scores"] = InterviewService._build_question_scores(questions)
            report["mode_label"] = (
                "内部多面试官协同 + 单主持人输出"
                if interview.interview_mode == "panel"
                else "单面试官模式"
            )
            interview.report = json.dumps(report, ensure_ascii=False)
        else:
            next_question_meta = dict(questions[next_index])
            if interview.interview_mode == "panel":
                next_question_meta = InterviewService._apply_followup_to_next_question(
                    current_question_meta=current_question_meta,
                    next_question_meta=next_question_meta,
                    evaluation=evaluation,
                )
            next_question_meta = InterviewService._reroute_question_slices(
                question_meta=next_question_meta,
                knowledge_base=knowledge_base_context,
                parsed_resume=parsed_resume,
                target_position=interview.target_position,
                difficulty=interview.difficulty,
                context_terms=InterviewService._extract_weakness_terms(current_question_meta, evaluation),
            )
            questions[next_index] = next_question_meta
            interview.questions_data = InterviewService._serialize_questions(questions)
            interview.current_question_index = next_index
            next_question = next_question_meta["question"]
            response["next_question"] = next_question
            response["next_question_target_gap"] = next_question_meta.get("question_target_gap")
            response["next_question_reason"] = next_question_meta.get("question_reason")
            db.add(
                InterviewMessage(
                    interview_id=interview_id,
                    role="interviewer",
                    content=next_question,
                    question_index=next_index,
                )
            )

        await db.commit()
        return response

    @staticmethod
    async def submit_answer_stream(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
        answer: str,
        ai_config: Optional[Dict] = None,
    ):
        try:
            result = await InterviewService.submit_answer(
                db=db,
                user_id=user_id,
                interview_id=interview_id,
                answer=answer,
                ai_config=ai_config,
            )
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n"
            return

        for chunk in InterviewService._chunk_text(result.get("feedback", "")):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', **result}, ensure_ascii=False)}\n\n"

    @staticmethod
    async def get_report(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
    ) -> Dict:
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")
        if interview.status != "completed":
            raise ValidationError(message="面试尚未完成")

        report = {}
        if interview.report:
            try:
                report = json.loads(interview.report)
            except json.JSONDecodeError:
                report = {}
        if interview.resume_id and not report.get("resume_evaluation_snapshot"):
            resume = await db.get(Resume, interview.resume_id)
            if resume:
                resume_analysis = ensure_resume_evaluation_snapshot(
                    InterviewService._load_resume_analysis_payload(resume),
                    target_position=interview.target_position,
                )
                if resume_analysis.get("resume_evaluation_snapshot"):
                    report["resume_evaluation_snapshot"] = resume_analysis["resume_evaluation_snapshot"]
                if resume_analysis.get("matching_metrics") and not report.get("matching_metrics"):
                    report["matching_metrics"] = resume_analysis["matching_metrics"]
                if resume_analysis.get("ability_gap_profile") and not report.get("ability_gap_profile"):
                    report["ability_gap_profile"] = resume_analysis["ability_gap_profile"]
                if resume_analysis.get("learning_plan") and not report.get("learning_plan"):
                    report["learning_plan"] = resume_analysis["learning_plan"]

        return {
            "interview_id": interview.id,
            "overall_score": float(interview.overall_score) if interview.overall_score else 0,
            "total_questions": interview.total_questions,
            "interview_mode": interview.interview_mode,
            "knowledge_base": interview.knowledge_base_snapshot,
            "panel_snapshot": interview.panel_snapshot,
            "report": report,
        }

    @staticmethod
    async def get_interviews(
        db: AsyncSession,
        user_id: int,
    ) -> Dict:
        result = await db.execute(
            select(Interview)
            .where(Interview.user_id == user_id)
            .order_by(Interview.created_at.desc())
        )
        interviews = result.scalars().all()
        items = [
            {
                "interview_id": item.id,
                "target_position": item.target_position,
                "difficulty": item.difficulty,
                "interview_mode": item.interview_mode or "single",
                "overall_score": float(item.overall_score) if item.overall_score else None,
                "total_questions": item.total_questions,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in interviews
        ]
        return {"total": len(items), "items": items}

    @staticmethod
    async def get_interview_messages(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
    ) -> List[Dict]:
        interview_result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
            )
        )
        interview = interview_result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.interview_id == interview_id)
            .order_by(InterviewMessage.id)
        )
        messages = result.scalars().all()
        return [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "question_index": item.question_index,
                "score": float(item.score) if item.score else None,
                "feedback": item.feedback,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in messages
        ]

    @staticmethod
    async def delete_interview(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
    ) -> Dict:
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        await db.execute(
            sql_delete(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
        )
        await db.delete(interview)
        await db.commit()
        return {"message": "面试记录已删除"}

    @staticmethod
    async def delete_interview_admin(
        db: AsyncSession,
        interview_id: int,
    ) -> Dict:
        interview = await db.get(Interview, interview_id)
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        await db.execute(
            sql_delete(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
        )
        await db.delete(interview)
        await db.commit()
        return {"message": "面试记录已删除"}


interview_service = InterviewService()
