from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.learning_route_stage import LearningRouteStage
from app.models.resume import Resume
from app.models.user import User
from app.services.backoffice.learning_route_service import learning_route_service
from app.services.client.ai_service import AIService
from app.services.client.matching_engine import MatchingEngine
from app.services.client.resume_evaluation_snapshot import (
    ability_profile_from_payload,
    ensure_resume_evaluation_snapshot,
)
from app.services.common.deepseek_config_service import deepseek_config_service
from app.utils.db_error_messages import user_facing_db_error

logger = logging.getLogger(__name__)

LEARNING_PLAN_V2 = "learning_plan_v2"
MAX_SUPPLEMENTAL_CHARS = 6000


class LearningPlanService:
    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        if value is None:
            return fallback
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            for key in ("name", "title", "ability_name", "summary", "text"):
                if value.get(key):
                    return str(value[key]).strip()
        return str(value).strip()

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        if value is None:
            return []
        raw = value if isinstance(value, list) else str(value).replace("\n", ",").split(",")
        result: List[str] = []
        for item in raw:
            text = LearningPlanService._text(item)
            if text and text not in result:
                result.append(text)
        return result

    @staticmethod
    def _parse_json(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    @classmethod
    def _normalize_ability(cls, value: Any, index: int) -> Dict[str, Any]:
        if isinstance(value, dict):
            name = cls._text(value.get("ability_name") or value.get("name") or value.get("title"))
            missing_keywords = cls._string_list(value.get("missing_keywords") or value.get("keywords"))
            return {
                "ability_id": cls._text(value.get("ability_id") or value.get("id"), f"ability_{index}"),
                "name": name or f"能力项 {index}",
                "missing_keywords": missing_keywords,
                "matched_keywords": cls._string_list(value.get("matched_keywords")),
                "priority_score": value.get("priority_score") or value.get("priority") or 70,
                "current_level": value.get("current_level") or 1,
                "required_level": value.get("required_level") or 3,
                "gap": value.get("gap") or 2,
                "evidence_status": value.get("evidence_status") or "needs_verification",
                "verification_priority": value.get("verification_priority") or "medium",
                "evidence_basis": cls._text(value.get("evidence_basis") or value.get("reason")),
            }
        text = cls._text(value)
        return {
            "ability_id": f"ability_{index}",
            "name": text or f"能力项 {index}",
            "missing_keywords": [text] if text else [],
            "matched_keywords": [],
            "priority_score": 70,
            "current_level": 1,
            "required_level": 3,
            "gap": 2,
            "evidence_basis": "用户在学习任务页手动选择的待提升能力。",
        }

    @classmethod
    def _normalize_abilities(cls, values: Any) -> List[Dict[str, Any]]:
        raw = values if isinstance(values, list) else cls._string_list(values)
        abilities = [cls._normalize_ability(item, index) for index, item in enumerate(raw, start=1)]
        return [item for item in abilities if item.get("name")]

    @classmethod
    def _supplemental_text(cls, value: Any) -> str:
        if not value:
            return ""
        if isinstance(value, list):
            text = "\n".join(cls._text(item) for item in value if cls._text(item))
        elif isinstance(value, dict):
            text = "\n".join(f"{key}: {cls._text(val)}" for key, val in value.items() if cls._text(val))
        else:
            text = cls._text(value)
        if len(text) > MAX_SUPPLEMENTAL_CHARS:
            raise ValidationError(message="补充学习资料过长，请压缩成摘要、链接或小段文本后再生成。")
        return text

    @classmethod
    async def _load_resume_analysis(
        cls,
        db: AsyncSession,
        user_id: int,
        resume_id: Optional[int],
    ) -> Dict[str, Any]:
        if not resume_id:
            return {}
        result = await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
        resume = result.scalar_one_or_none()
        if not resume:
            raise NotFoundError(message="简历不存在或不属于当前用户")
        return {
            "resume": resume,
            "analysis": ensure_resume_evaluation_snapshot(
                cls._parse_json(resume.analysis),
                target_position=resume.target_position,
            ),
            "parsed_resume": cls._parse_json(resume.parsed_content),
        }

    @classmethod
    def _ability_options_from_analysis(cls, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        gap = ability_profile_from_payload(analysis or {})
        items = gap.get("top_gaps") or gap.get("items") or []
        options: List[Dict[str, Any]] = []
        for index, item in enumerate(items[:12], start=1):
            ability = cls._normalize_ability(item, index)
            options.append(
                {
                    "ability_id": ability["ability_id"],
                    "ability_name": ability["name"],
                    "missing_keywords": ability["missing_keywords"],
                    "priority_score": ability["priority_score"],
                    "evidence_status": ability.get("evidence_status") or "needs_verification",
                    "recommended_action": (
                        "interview_verification"
                        if ability.get("evidence_status") == "claimed_only"
                        else "learning_task"
                    ),
                    "evidence_basis": ability["evidence_basis"],
                }
            )
        return options

    @classmethod
    async def _route_records(
        cls,
        db: AsyncSession,
        *,
        route_kind: Optional[str] = None,
        plan_group: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await learning_route_service.ensure_seeded_from_builtins(db)
        query = select(LearningRouteStage).where(LearningRouteStage.is_active.is_(True))
        if route_kind:
            query = query.where(LearningRouteStage.route_kind == route_kind)
        group = cls._text(plan_group)
        if group:
            query = query.where(LearningRouteStage.plan_group == group)
        query = query.order_by(LearningRouteStage.sort_order.asc(), LearningRouteStage.id.asc())
        result = await db.execute(query)
        return [
            {
                **learning_route_service.serialize(item),
                "job_id": item.job_id,
                "category": item.category,
                "sort_order": item.sort_order,
            }
            for item in result.scalars().all()
        ]

    @classmethod
    def _resolver_from_records(cls, records: List[Dict[str, Any]]):
        def resolver(job_id: str, text: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
            return learning_route_service.match_loaded_routes(records=records, job_id=job_id, text=text, category=category)

        return resolver

    @classmethod
    def _build_tasks_from_records(
        cls,
        *,
        records: List[Dict[str, Any]],
        abilities: List[Dict[str, Any]],
        target_position: str,
    ) -> Dict[str, Any]:
        profile = MatchingEngine._resolve_profile(target_position)
        tasks: List[Dict[str, Any]] = []
        resolver = cls._resolver_from_records(records)
        plan_groups = sorted(
            {
                cls._text(route.get("plan_group"))
                for route in records
                if cls._text(route.get("plan_group"))
            }
        )
        for index, ability in enumerate(abilities[:8], start=1):
            task = MatchingEngine._build_learning_task(
                item=ability,
                profile=profile,
                target_position=target_position,
                rank=index,
                route_stage_resolver=resolver,
            )
            task["source_type"] = "generated_learning_plan"
            task["target_position"] = target_position
            task["task_metadata"] = {
                **(task.get("task_metadata") or {}),
                "learning_plan_version": LEARNING_PLAN_V2,
                "route_kind": "mature_plan" if any(route.get("route_kind") == "mature_plan" for route in records) else "template",
                "plan_group": plan_groups[0] if len(plan_groups) == 1 else "",
                "source_evidence_status": ability.get("evidence_status") or "needs_verification",
                "source_verification_priority": ability.get("verification_priority") or "medium",
            }
            tasks.append(task)
        return {
            "version": LEARNING_PLAN_V2,
            "target_position": target_position,
            "matched_profile": {
                "job_id": profile.get("job_id"),
                "job_name": profile.get("job_name") or target_position,
                "category": profile.get("category"),
            },
            "task_count": len(tasks),
            "tasks": tasks,
        }

    @classmethod
    async def options(
        cls,
        db: AsyncSession,
        *,
        user: User,
        target_position: Optional[str] = None,
        resume_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            resume_context = await cls._load_resume_analysis(db, user.id, resume_id)
            analysis = resume_context.get("analysis") or {}
            position = target_position or analysis.get("target_position") or ""
            templates = await cls._route_records(db, route_kind="template")
            mature_plans = await cls._route_records(db, route_kind="mature_plan")
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Learning plan options failed: %s", exc)
            raise ValidationError(message=user_facing_db_error(exc)) from exc

        user_summary = deepseek_config_service.summarize_for_profile(user)
        return {
            "version": LEARNING_PLAN_V2,
            "target_position": position,
            "ability_options": cls._ability_options_from_analysis(analysis),
            "templates": templates,
            "mature_plans": mature_plans,
            "web_search_available": bool(user_summary.get("openai_has_personal_api_key")),
            "web_search_note": "仅在保存 OpenAI API Key 后，AI 生成计划才会尝试联网搜索。",
        }

    @classmethod
    async def _try_ai_refine(
        cls,
        *,
        user: User,
        target_position: str,
        abilities: List[Dict[str, Any]],
        deterministic_plan: Dict[str, Any],
        supplemental_text: str,
        allow_web_search: bool,
    ) -> Dict[str, Any]:
        web_search_status = "not_requested"
        sources: List[Dict[str, str]] = []

        if allow_web_search:
            openai_config = None
            try:
                openai_config = deepseek_config_service.build_runtime_config(user, require_personal_key=True, provider="openai")
            except ValidationError:
                web_search_status = "unavailable_no_openai_key"
            if openai_config:
                try:
                    client, model, *_ = AIService._resolve_runtime(openai_config)
                    prompt = (
                        "你是就业能力提升学习教练。请基于目标岗位、待提升能力和已有任务草稿，"
                        "搜索近期公开学习资料方向，返回 JSON：{\"tasks\": [...], \"sources\": [...]}。"
                        "不要要求上传大型文件，只允许链接、摘要和小段文本。\n"
                        f"目标岗位：{target_position}\n"
                        f"待提升能力：{json.dumps(abilities, ensure_ascii=False)}\n"
                        f"任务草稿：{json.dumps(deterministic_plan.get('tasks', []), ensure_ascii=False)}\n"
                        f"用户补充资料：{supplemental_text or '无'}"
                    )
                    response = await client.responses.create(
                        model=model,
                        input=prompt,
                        tools=[{"type": "web_search_preview"}],
                    )
                    raw = getattr(response, "output_text", "") or str(response)
                    payload = AIService._extract_json(raw)
                    if isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
                        refined = {**deterministic_plan, "tasks": payload["tasks"][:8]}
                        sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
                        refined["web_search_status"] = "used"
                        refined["sources"] = sources[:8]
                        return refined
                    web_search_status = "failed_fallback"
                except Exception as exc:  # noqa: BLE001 - web search is optional
                    logger.warning("Learning plan web search fallback: %s", exc)
                    web_search_status = "failed_fallback"

        try:
            ai_config = deepseek_config_service.build_runtime_config(user, require_personal_key=True)
            raw = await AIService._chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是学习计划生成助手。只返回 JSON，字段为 tasks。"
                            "每个任务必须包含 title、learning_material、practice_task、estimated_minutes、acceptance_criteria。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"目标岗位：{target_position}\n"
                            f"待提升能力：{json.dumps(abilities, ensure_ascii=False)}\n"
                            f"后台路线任务草稿：{json.dumps(deterministic_plan.get('tasks', []), ensure_ascii=False)}\n"
                            f"用户补充资料：{supplemental_text or '无'}\n"
                            "请保留任务可执行性，不要要求上传大型文件。"
                        ),
                    },
                ],
                temperature=0.3,
                ai_config=ai_config,
            )
            payload = AIService._extract_json(raw)
            if isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
                refined_tasks = []
                for index, task in enumerate(payload["tasks"][:8], start=1):
                    if not isinstance(task, dict):
                        continue
                    base = deterministic_plan["tasks"][min(index - 1, len(deterministic_plan["tasks"]) - 1)]
                    refined_tasks.append({**base, **task})
                if refined_tasks:
                    return {
                        **deterministic_plan,
                        "tasks": refined_tasks,
                        "web_search_status": web_search_status,
                        "sources": sources,
                        "generation_backend": ai_config.get("provider") or "ai",
                    }
        except Exception as exc:  # noqa: BLE001 - normal AI generation is optional
            logger.warning("Learning plan AI refine fallback: %s", exc)

        return {
            **deterministic_plan,
            "web_search_status": web_search_status,
            "sources": sources,
            "generation_backend": "deterministic_template",
        }

    @classmethod
    async def generate(
        cls,
        db: AsyncSession,
        *,
        user: User,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        mode = cls._text(payload.get("mode"), "ai_generate")
        if mode not in {"ai_generate", "mature_plan"}:
            raise ValidationError(message="学习计划生成方式必须是 ai_generate 或 mature_plan")

        target_position = cls._text(payload.get("target_position"))
        if not target_position:
            raise ValidationError(message="请先选择目标岗位")

        supplemental_text = cls._supplemental_text(payload.get("supplemental_materials"))
        abilities = cls._normalize_abilities(payload.get("abilities"))
        if not abilities:
            raise ValidationError(message="请至少选择 1 个缺失能力后再生成学习计划")

        try:
            route_kind = "mature_plan" if mode == "mature_plan" else "template"
            mature_plan_group = cls._text(payload.get("mature_plan_group")) if mode == "mature_plan" else ""
            records = await cls._route_records(
                db,
                route_kind=route_kind,
                plan_group=mature_plan_group or None,
            )
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Learning plan route lookup failed: %s", exc)
            raise ValidationError(message=user_facing_db_error(exc)) from exc

        if mode == "mature_plan" and not records:
            if cls._text(payload.get("mature_plan_group")):
                raise ValidationError(message="所选成熟学习计划暂无启用阶段，请重新选择计划或联系管理员。")
            raise ValidationError(message="后台暂无启用的成熟学习计划，请先选择 AI 生成，或让管理员复制模板为成熟计划。")
        if not records:
            records = []

        plan = cls._build_tasks_from_records(
            records=records,
            abilities=abilities,
            target_position=target_position,
        )
        plan.update(
            {
                "mode": mode,
                "allow_web_search": bool(payload.get("allow_web_search")),
                "mature_plan_group": cls._text(payload.get("mature_plan_group")),
                "supplemental_materials_used": bool(supplemental_text),
                "resource_requirement": "只支持轻量文本、链接和摘要；不要上传大型文件。",
            }
        )

        if mode == "ai_generate":
            plan = await cls._try_ai_refine(
                user=user,
                target_position=target_position,
                abilities=abilities,
                deterministic_plan=plan,
                supplemental_text=supplemental_text,
                allow_web_search=bool(payload.get("allow_web_search")),
            )
        else:
            plan["web_search_status"] = "not_requested"
            plan["generation_backend"] = "mature_plan"
            plan["sources"] = []

        return plan


learning_plan_service = LearningPlanService()
