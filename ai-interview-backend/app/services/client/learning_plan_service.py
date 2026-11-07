from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.interview import Interview
from app.models.learning_plan import LearningPlan
from app.models.learning_task import LearningTask
from app.models.learning_route_stage import LearningRouteStage
from app.models.resume import Resume
from app.models.user import User
from app.services.backoffice.learning_route_service import learning_route_service
from app.services.client.ai_service import AIService
from app.services.client.learning_task_service import LearningTaskService
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
PLAN_STATUSES = {"draft", "active", "reviewed", "archived"}


class LearningPlanService:
    AI_TASK_OVERRIDE_FIELDS = {
        "title",
        "learning_material",
        "practice_task",
        "acceptance_criteria",
        "resources",
        "sources",
        "description",
        "notes",
    }

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
            evidence_status = value.get("evidence_status") or "needs_verification"
            action_type = cls._text(value.get("action_type"))
            if not action_type and evidence_status == "claimed_only":
                action_type = "interview_verification"
            elif not action_type and evidence_status == "indirect":
                action_type = "evidence_completion"
            elif not action_type:
                action_type = "learning_gap"
            return {
                "ability_id": cls._text(value.get("ability_id") or value.get("id"), f"ability_{index}"),
                "name": name or f"能力项 {index}",
                "missing_keywords": missing_keywords,
                "matched_keywords": cls._string_list(value.get("matched_keywords")),
                "verification_keywords": cls._string_list(value.get("verification_keywords")),
                "priority_score": value.get("priority_score") or value.get("priority") or 70,
                "current_level": value.get("current_level") or 1,
                "required_level": value.get("required_level") or 3,
                "gap": value.get("gap") or 2,
                "evidence_status": evidence_status,
                "action_type": action_type,
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
            "evidence_status": "missing",
            "action_type": "learning_gap",
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
    async def _load_interview_context(
        cls,
        db: AsyncSession,
        user_id: int,
        interview_id: Optional[int],
    ) -> Dict[str, Any]:
        if not interview_id:
            return {}
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
                Interview.user_deleted_at.is_(None),
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在或不属于当前用户")
        report = cls._parse_json(interview.report)
        questions_data = interview.questions_data if isinstance(interview.questions_data, list) else []
        return {
            "interview": interview,
            "report": report,
            "questions_data": questions_data,
            "target_position": interview.target_position or "",
            "resume_id": interview.resume_id,
        }

    @classmethod
    def _ability_options_from_report(cls, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(report, dict):
            return []
        raw_items: List[Any] = []
        snapshot = report.get("resume_evaluation_snapshot")
        if isinstance(snapshot, dict):
            profile = ability_profile_from_payload(snapshot)
            raw_items.extend(profile.get("top_gaps") or profile.get("items") or [])
        for key in ("training_priorities", "common_gaps", "weaknesses", "suggestions"):
            values = report.get(key)
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values[:6], start=1):
                text = cls._text(value)
                if text:
                    raw_items.append(
                        {
                            "ability_id": f"{key}_{index}",
                            "name": text[:80],
                            "evidence_basis": text,
                            "priority_score": 70,
                            "action_type": "learning_gap",
                            "evidence_status": "missing",
                        }
                    )
        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(raw_items[:12], start=1):
            ability = cls._normalize_ability(item, index)
            name = ability.get("name") or ""
            if not name or name in seen:
                continue
            seen.add(name)
            normalized.append(
                {
                    "ability_id": ability["ability_id"],
                    "ability_name": name,
                    "missing_keywords": ability.get("missing_keywords") or [],
                    "matched_keywords": ability.get("matched_keywords") or [],
                    "verification_keywords": ability.get("verification_keywords") or [],
                    "priority_score": ability.get("priority_score") or 70,
                    "evidence_status": ability.get("evidence_status") or "needs_verification",
                    "action_type": ability.get("action_type") or "learning_gap",
                    "recommended_action": (
                        "interview_verification"
                        if ability.get("action_type") == "interview_verification"
                        else "learning_task"
                    ),
                    "evidence_basis": ability.get("evidence_basis") or "",
                }
            )
        return normalized

    @classmethod
    async def build_context_from_report(
        cls,
        db: AsyncSession,
        *,
        user: User,
        resume_id: Optional[int] = None,
        interview_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        interview_context = await cls._load_interview_context(db, user.id, interview_id)
        effective_resume_id = resume_id or interview_context.get("resume_id")
        resume_context = await cls._load_resume_analysis(db, user.id, effective_resume_id)
        analysis = resume_context.get("analysis") or {}
        report = interview_context.get("report") or {}
        resume_obj = resume_context.get("resume")
        target_position = (
            interview_context.get("target_position")
            or analysis.get("target_position")
            or cls._text(resume_obj.target_position if resume_obj else "")
        )
        ability_options = cls._ability_options_from_analysis(analysis)
        existing = {item.get("ability_name") for item in ability_options}
        for item in cls._ability_options_from_report(report):
            if item.get("ability_name") not in existing:
                ability_options.append(item)
                existing.add(item.get("ability_name"))
        return {
            "resume_context": resume_context,
            "interview_context": interview_context,
            "target_position": target_position or "",
            "ability_options": ability_options[:16],
            "report": report,
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
                    "matched_keywords": ability.get("matched_keywords") or [],
                    "verification_keywords": ability.get("verification_keywords") or [],
                    "priority_score": ability["priority_score"],
                    "evidence_status": ability.get("evidence_status") or "needs_verification",
                    "action_type": ability.get("action_type") or (
                        "interview_verification" if ability.get("evidence_status") == "claimed_only" else "learning_gap"
                    ),
                    "recommended_action": (
                        "interview_verification"
                        if (ability.get("action_type") == "interview_verification" or ability.get("evidence_status") == "claimed_only")
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
                "source_action_type": ability.get("action_type") or "learning_gap",
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
    def _merge_ai_task_overrides(
        cls,
        deterministic_tasks: List[Dict[str, Any]],
        ai_tasks: List[Any],
    ) -> List[Dict[str, Any]]:
        if not deterministic_tasks:
            return []

        refined_tasks: List[Dict[str, Any]] = []
        for index, base_task in enumerate(deterministic_tasks):
            task = ai_tasks[index] if index < len(ai_tasks) else {}
            if not isinstance(task, dict):
                task = {}
            base = dict(base_task)
            merged = dict(base)
            for key in cls.AI_TASK_OVERRIDE_FIELDS:
                if key in task and task[key] not in (None, "", []):
                    merged[key] = task[key]
            refined_tasks.append(merged)
        return refined_tasks

    @classmethod
    async def options(
        cls,
        db: AsyncSession,
        *,
        user: User,
        target_position: Optional[str] = None,
        resume_id: Optional[int] = None,
        interview_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            context = await cls.build_context_from_report(
                db,
                user=user,
                resume_id=resume_id,
                interview_id=interview_id,
            )
            position = target_position or context.get("target_position") or ""
            templates = await cls._route_records(db, route_kind="template")
            mature_plans = await cls._route_records(db, route_kind="mature_plan")
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Learning plan options failed: %s", exc)
            raise ValidationError(message=user_facing_db_error(exc)) from exc

        user_summary = deepseek_config_service.summarize_for_profile(user)
        resume_obj = (context.get("resume_context") or {}).get("resume")
        return {
            "version": LEARNING_PLAN_V2,
            "target_position": position,
            "resume_id": resume_id or (resume_obj.id if resume_obj else None),
            "interview_id": interview_id,
            "ability_options": context.get("ability_options") or [],
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
                        refined_tasks = cls._merge_ai_task_overrides(
                            deterministic_plan.get("tasks") or [],
                            payload["tasks"],
                        )
                        if not refined_tasks:
                            web_search_status = "failed_fallback"
                            raise ValueError("web search returned no mergeable learning tasks")
                        refined = {**deterministic_plan, "tasks": refined_tasks}
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
            raw, json_mode_status = await AIService._chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是学习计划生成助手。只返回 JSON，字段为 tasks。"
                            "每个任务必须包含 title、learning_material、practice_task、estimated_minutes、acceptance_criteria。"
                            "任务必须紧扣对应能力和路线阶段，不用通用编程基础替代数据库、并发等专项。"
                            "练习需包含具体输入、实现动作和失败场景，验收标准需能通过运行结果、断言或产出物核对。"
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
            payload = await AIService._extract_or_repair_json(
                raw,
                schema_hint='{"tasks":[{"title":"","learning_material":"","practice_task":"","acceptance_criteria":[]}]}',
                ai_config=ai_config,
                expected_type="object",
                required_keys=["tasks"],
                max_repair_rounds=1,
                parser_label="learning_plan_refine",
            )
            if isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
                refined_tasks = cls._merge_ai_task_overrides(
                    deterministic_plan.get("tasks") or [],
                    payload["tasks"],
                )
                if refined_tasks:
                    return {
                        **deterministic_plan,
                        "tasks": refined_tasks,
                        "web_search_status": web_search_status,
                        "sources": sources,
                        "generation_backend": ai_config.get("provider") or "ai",
                        "json_mode_status": json_mode_status,
                    }
        except Exception as exc:  # noqa: BLE001 - normal AI generation is optional
            logger.warning("Learning plan AI refine fallback: %s", exc)

        return {
            **deterministic_plan,
            "web_search_status": web_search_status,
            "sources": sources,
            "generation_backend": "deterministic_template",
        }

    @staticmethod
    def _plan_progress(tasks: List[LearningTask]) -> Dict[str, Any]:
        total = len(tasks)
        done = sum(1 for task in tasks if task.done)
        pending = max(total - done, 0)
        completion_rate = round(done / total * 100) if total else 0
        return {
            "total": total,
            "done": done,
            "pending": pending,
            "completion_rate": completion_rate,
        }

    @classmethod
    def _next_action(cls, plan: LearningPlan, tasks: List[LearningTask]) -> Dict[str, Any]:
        pending = [task for task in tasks if not task.done]
        if pending:
            task = sorted(pending, key=lambda item: (item.step_order or 9999, item.id or 0))[0]
            return {
                "type": "continue_task",
                "label": "继续下一项任务",
                "task_key": task.task_key,
                "title": task.title,
            }
        if plan.source_interview_id:
            return {
                "type": "training_review",
                "label": "进入训练复盘，整理本轮学习证据",
                "interview_id": plan.source_interview_id,
            }
        return {
            "type": "validation_interview",
            "label": "开始一次验证面试，检查本轮能力提升",
            "target_position": plan.target_position or "",
        }

    @classmethod
    def _serialize_plan(cls, plan: LearningPlan, tasks: Optional[List[LearningTask]] = None) -> Dict[str, Any]:
        task_items = [LearningTaskService._serialize(item) for item in (tasks or [])]
        progress = cls._plan_progress(tasks or [])
        return {
            "id": plan.id,
            "learning_plan_id": plan.id,
            "user_id": plan.user_id,
            "source_resume_id": plan.source_resume_id,
            "source_interview_id": plan.source_interview_id,
            "previous_plan_id": plan.previous_plan_id,
            "target_position": plan.target_position or "",
            "title": plan.title,
            "goal": plan.goal or "",
            "status": plan.status,
            "plan_days": plan.plan_days,
            "daily_minutes": plan.daily_minutes,
            "selected_abilities": plan.selected_abilities or [],
            "plan_json": plan.plan_json or {},
            "sources": plan.sources or [],
            "generation_backend": plan.generation_backend or "",
            "web_search_status": plan.web_search_status or "",
            "tasks": task_items,
            "progress": progress,
            "next_action": cls._next_action(plan, tasks or []),
            "created_at": plan.created_at.isoformat() if plan.created_at else "",
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else "",
        }

    @classmethod
    async def _load_plan_with_tasks(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        plan_id: int,
    ) -> tuple[LearningPlan, List[LearningTask]]:
        result = await db.execute(
            select(LearningPlan).where(LearningPlan.id == plan_id, LearningPlan.user_id == user_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundError(message="学习计划不存在或不属于当前用户")
        task_result = await db.execute(
            select(LearningTask)
            .where(LearningTask.user_id == user_id, LearningTask.learning_plan_id == plan_id)
            .order_by(LearningTask.step_order.asc().nulls_last(), LearningTask.id.asc())
        )
        return plan, list(task_result.scalars().all())

    @classmethod
    async def get_plan(cls, db: AsyncSession, *, user: User, plan_id: int) -> Dict[str, Any]:
        try:
            plan, tasks = await cls._load_plan_with_tasks(db, user_id=user.id, plan_id=plan_id)
            return cls._serialize_plan(plan, tasks)
        except SQLAlchemyError as exc:
            await db.rollback()
            raise ValidationError(message=user_facing_db_error(exc)) from exc

    @classmethod
    async def update_plan(
        cls,
        db: AsyncSession,
        *,
        user: User,
        plan_id: int,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            plan, _ = await cls._load_plan_with_tasks(db, user_id=user.id, plan_id=plan_id)
            if "title" in payload and cls._text(payload.get("title")):
                plan.title = cls._text(payload.get("title"))[:255]
            if "goal" in payload:
                plan.goal = cls._text(payload.get("goal"))
            if "status" in payload:
                status = cls._text(payload.get("status"), plan.status)
                if status not in PLAN_STATUSES:
                    raise ValidationError(message="学习计划状态不合法")
                plan.status = status
            if "plan_json" in payload and isinstance(payload.get("plan_json"), dict):
                plan.plan_json = {
                    **(plan.plan_json or {}),
                    **payload["plan_json"],
                    "user_edited": True,
                }
            await db.commit()
            await db.refresh(plan)
            _, tasks = await cls._load_plan_with_tasks(db, user_id=user.id, plan_id=plan_id)
            return cls._serialize_plan(plan, tasks)
        except SQLAlchemyError as exc:
            await db.rollback()
            raise ValidationError(message=user_facing_db_error(exc)) from exc

    @classmethod
    async def _persist_plan(
        cls,
        db: AsyncSession,
        *,
        user: User,
        plan: Dict[str, Any],
        abilities: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        source_resume_id = payload.get("resume_id")
        source_interview_id = payload.get("interview_id")
        if source_interview_id:
            interview_context = await cls._load_interview_context(db, user.id, source_interview_id)
            source_resume_id = source_resume_id or interview_context.get("resume_id")
        if source_resume_id:
            await cls._load_resume_analysis(db, user.id, source_resume_id)
        previous_plan_id = payload.get("previous_plan_id")
        if previous_plan_id:
            await cls._load_plan_with_tasks(db, user_id=user.id, plan_id=int(previous_plan_id))

        plan_days = payload.get("plan_days") or 14
        daily_minutes = payload.get("daily_minutes") or 45
        title = cls._text(payload.get("title")) or f"{plan.get('target_position') or '岗位能力'}学习计划"
        goal = cls._text(payload.get("goal")) or f"{plan_days} 天内完成核心能力训练，并通过复盘或验证面试检查效果。"
        plan_entity = LearningPlan(
            user_id=user.id,
            source_resume_id=source_resume_id,
            source_interview_id=source_interview_id,
            previous_plan_id=previous_plan_id,
            target_position=plan.get("target_position") or payload.get("target_position"),
            title=title[:255],
            goal=goal,
            status="draft",
            plan_days=int(plan_days),
            daily_minutes=int(daily_minutes),
            selected_abilities=abilities,
            plan_json={
                **plan,
                "plan_days": int(plan_days),
                "daily_minutes": int(daily_minutes),
                "next_actions": [
                    "继续下一项任务",
                    "完成关键任务后进入训练复盘",
                    "用本轮笔记开始验证面试",
                ],
            },
            sources=plan.get("sources") or [],
            generation_backend=plan.get("generation_backend") or "deterministic_template",
            web_search_status=plan.get("web_search_status") or "not_requested",
        )
        db.add(plan_entity)
        await db.flush()

        touched: List[LearningTask] = []
        for index, raw_task in enumerate(plan.get("tasks") or [], start=1):
            task_payload = {
                **raw_task,
                "source_type": "learning_plan",
                "source_id": str(plan_entity.id),
                "resume_id": source_resume_id,
                "interview_id": source_interview_id,
                "learning_plan_id": plan_entity.id,
                "step_order": index,
                "task_key": f"plan_{plan_entity.id}__step_{index}",
                "task_metadata": {
                    **(raw_task.get("task_metadata") or {}),
                    "validation_action": raw_task.get("validation_action")
                    or "完成后用训练复盘或验证面试检查是否真正掌握",
                    "next_action": raw_task.get("next_action") or "完成本步骤后继续下一项任务",
                    "source_gap_ids": [item.get("ability_id") for item in abilities if item.get("ability_id")],
                    "execution_state": "draft",
                },
            }
            normalized = LearningTaskService._normalize_input(task_payload)
            entity = LearningTask(user_id=user.id, **normalized)
            db.add(entity)
            touched.append(entity)

        await db.commit()
        await db.refresh(plan_entity)
        for task in touched:
            await db.refresh(task)
        return cls._serialize_plan(plan_entity, touched)

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

        context = await cls.build_context_from_report(
            db,
            user=user,
            resume_id=payload.get("resume_id"),
            interview_id=payload.get("interview_id"),
        )
        target_position = cls._text(payload.get("target_position") or context.get("target_position"))
        if not target_position:
            raise ValidationError(message="请先选择目标岗位")

        supplemental_text = cls._supplemental_text(payload.get("supplemental_materials"))
        abilities = cls._normalize_abilities(payload.get("selected_abilities") or payload.get("abilities"))
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
                "resume_id": payload.get("resume_id"),
                "interview_id": payload.get("interview_id"),
                "plan_days": payload.get("plan_days") or 14,
                "daily_minutes": payload.get("daily_minutes") or 45,
                "selected_abilities": abilities,
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

        if payload.get("persist"):
            try:
                return await cls._persist_plan(
                    db,
                    user=user,
                    plan=plan,
                    abilities=abilities,
                    payload={**payload, "target_position": target_position},
                )
            except SQLAlchemyError as exc:
                await db.rollback()
                raise ValidationError(message=user_facing_db_error(exc)) from exc

        return plan


learning_plan_service = LearningPlanService()
