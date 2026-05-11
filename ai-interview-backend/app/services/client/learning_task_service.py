import re
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.interview import Interview
from app.models.learning_task import LearningTask
from app.models.resume import Resume
from app.utils.db_error_messages import user_facing_db_error


LEARNING_TASKS_VERSION = "learning_tasks_v1"


class LearningTaskService:
    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        if value is None:
            return fallback
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            for key in ("summary", "title", "name", "focus", "reason"):
                if value.get(key):
                    return str(value[key]).strip()
        return str(value).strip()

    @staticmethod
    def _compact(value: Any) -> str:
        text = LearningTaskService._text(value, "task").lower()
        text = re.sub(r"\s+", "-", text)
        text = re.sub(r"[^\w\u4e00-\u9fa5-]", "", text)
        return text[:80] or "task"

    @staticmethod
    def _clean_optional(value: Any, max_length: Optional[int] = None) -> Optional[str]:
        text = LearningTaskService._text(value)
        if not text:
            return None
        return text[:max_length] if max_length else text

    @staticmethod
    def _normalize_task_key(data: Dict[str, Any]) -> str:
        key = LearningTaskService._text(data.get("task_key") or data.get("task_id") or data.get("id"))
        if key:
            return key[:160]
        pieces = [
            data.get("source_type") or "manual",
            data.get("source_id") or data.get("resume_id") or data.get("interview_id") or "local",
            data.get("target_position") or "position",
            data.get("ability_name") or data.get("title") or "ability",
            data.get("title") or "task",
        ]
        return "__".join(LearningTaskService._compact(piece) for piece in pieces)[:160]

    @staticmethod
    def _normalize_criteria(value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, list):
            return [LearningTaskService._text(item) for item in value if LearningTaskService._text(item)]
        text = LearningTaskService._text(value)
        return [text] if text else None

    @staticmethod
    def _int_or_none(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _json_or_none(value: Any) -> Any:
        return value if isinstance(value, (dict, list)) else None

    @staticmethod
    def _normalize_input(data: Dict[str, Any]) -> Dict[str, Any]:
        title = LearningTaskService._text(data.get("title"))
        ability_name = LearningTaskService._clean_optional(
            data.get("ability_name") or data.get("name") or data.get("ability_id"),
            255,
        )
        if not title:
            title = f"补强：{ability_name or '岗位能力'}"
        return {
            "task_key": LearningTaskService._normalize_task_key(data),
            "title": title[:255],
            "ability_name": ability_name,
            "target_position": LearningTaskService._clean_optional(
                data.get("target_position") or data.get("targetPosition"),
                255,
            ),
            "source_type": LearningTaskService._clean_optional(
                data.get("source_type") or data.get("sourceType") or "manual",
                50,
            ),
            "source_id": LearningTaskService._clean_optional(
                data.get("source_id") or data.get("sourceId") or data.get("resume_id") or data.get("interview_id"),
                255,
            ),
            "resume_id": LearningTaskService._int_or_none(data.get("resume_id")),
            "interview_id": LearningTaskService._int_or_none(data.get("interview_id")),
            "priority_score": LearningTaskService._clean_optional(data.get("priority_score") or data.get("priority"), 50),
            "route_source": LearningTaskService._clean_optional(data.get("route_source") or data.get("routeSource"), 100),
            "route_stage": LearningTaskService._clean_optional(data.get("route_stage") or data.get("routeStage"), 100),
            "task_type": LearningTaskService._clean_optional(data.get("task_type") or data.get("taskType") or data.get("material_type"), 50),
            "estimated_minutes": LearningTaskService._int_or_none(
                data.get("estimated_minutes") or data.get("estimatedMinutes")
            ),
            "due_date": LearningTaskService._clean_optional(data.get("due_date") or data.get("dueDate"), 20),
            "learning_material": LearningTaskService._clean_optional(data.get("learning_material") or data.get("material")),
            "practice_task": LearningTaskService._clean_optional(data.get("practice_task") or data.get("practice")),
            "acceptance_criteria": LearningTaskService._normalize_criteria(
                data.get("acceptance_criteria") or data.get("acceptance") or data.get("deliverable")
            ),
            "task_metadata": LearningTaskService._json_or_none(data.get("task_metadata") or data.get("taskMetadata")),
            "evidence_basis": LearningTaskService._clean_optional(
                data.get("evidence_basis") or data.get("evidence") or data.get("reason")
            ),
            "done": bool(data.get("done")) if "done" in data and data.get("done") is not None else None,
            "note": LearningTaskService._clean_optional(data.get("note")),
            "weak_change": LearningTaskService._clean_optional(data.get("weak_change")),
        }

    @staticmethod
    async def _validate_sources(db: AsyncSession, user_id: int, data: Dict[str, Any]) -> None:
        resume_id = data.get("resume_id")
        if resume_id:
            result = await db.execute(select(Resume.id).where(Resume.id == resume_id, Resume.user_id == user_id))
            if result.scalar_one_or_none() is None:
                raise ValidationError(message="学习任务来源简历不属于当前用户")

        interview_id = data.get("interview_id")
        if interview_id:
            result = await db.execute(
                select(Interview.id).where(Interview.id == interview_id, Interview.user_id == user_id)
            )
            if result.scalar_one_or_none() is None:
                raise ValidationError(message="学习任务来源面试不属于当前用户")

    @staticmethod
    def _serialize(item: LearningTask) -> Dict[str, Any]:
        task_key = item.task_key
        return {
            "id": item.id,
            "task_key": task_key,
            "task_id": task_key,
            "title": item.title,
            "ability_name": item.ability_name or "",
            "target_position": item.target_position or "",
            "source_type": item.source_type or "manual",
            "source_id": item.source_id or "",
            "resume_id": item.resume_id or "",
            "interview_id": item.interview_id or "",
            "priority_score": item.priority_score or "",
            "route_source": item.route_source or "",
            "route_stage": item.route_stage or "",
            "task_type": item.task_type or "",
            "estimated_minutes": item.estimated_minutes or "",
            "due_date": item.due_date or "",
            "learning_material": item.learning_material or "",
            "practice_task": item.practice_task or "",
            "acceptance_criteria": item.acceptance_criteria or [],
            "task_metadata": item.task_metadata or {},
            "evidence_basis": item.evidence_basis or "",
            "done": bool(item.done),
            "note": item.note or "",
            "weak_change": item.weak_change or "",
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        }

    @staticmethod
    def _list_response(items: Iterable[LearningTask]) -> Dict[str, Any]:
        serialized = [LearningTaskService._serialize(item) for item in items]
        return {
            "version": LEARNING_TASKS_VERSION,
            "total": len(serialized),
            "items": serialized,
            "tasks": serialized,
        }

    @staticmethod
    async def list_tasks(db: AsyncSession, user_id: int) -> Dict[str, Any]:
        try:
            result = await db.execute(
                select(LearningTask)
                .where(LearningTask.user_id == user_id)
                .order_by(LearningTask.done.asc(), LearningTask.updated_at.desc())
            )
            return LearningTaskService._list_response(result.scalars().all())
        except SQLAlchemyError as exc:
            await db.rollback()
            raise ValidationError(message=user_facing_db_error(exc)) from exc

    @staticmethod
    async def bulk_upsert(
        db: AsyncSession,
        user_id: int,
        tasks: List[Dict[str, Any]],
        replace_progress: bool = False,
    ) -> Dict[str, Any]:
        try:
            normalized_items = [LearningTaskService._normalize_input(item) for item in tasks]
            for item in normalized_items:
                await LearningTaskService._validate_sources(db, user_id, item)

            touched: List[LearningTask] = []
            for item in normalized_items:
                result = await db.execute(
                    select(LearningTask).where(
                        LearningTask.user_id == user_id,
                        LearningTask.task_key == item["task_key"],
                    )
                )
                entity = result.scalar_one_or_none()
                if entity is None:
                    if item.get("done") is None:
                        item["done"] = False
                    entity = LearningTask(user_id=user_id, **item)
                    db.add(entity)
                else:
                    for key, value in item.items():
                        if key in {"done", "note", "weak_change"} and not replace_progress:
                            continue
                        if key in {"done", "note", "weak_change"} and value in (None, ""):
                            continue
                        setattr(entity, key, value)
                touched.append(entity)

            await db.commit()
            for item in touched:
                await db.refresh(item)
            return LearningTaskService._list_response(touched)
        except SQLAlchemyError as exc:
            await db.rollback()
            raise ValidationError(message=user_facing_db_error(exc)) from exc

    @staticmethod
    async def patch_task(db: AsyncSession, user_id: int, task_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await db.execute(
                select(LearningTask).where(LearningTask.user_id == user_id, LearningTask.task_key == task_key)
            )
            item = result.scalar_one_or_none()
            if not item:
                raise NotFoundError(message="学习任务不存在")

            patch = LearningTaskService._normalize_input({"title": item.title, "task_key": task_key, **data})
            await LearningTaskService._validate_sources(db, user_id, patch)

            allowed_fields = {
                "title",
                "ability_name",
                "target_position",
                "source_type",
                "source_id",
                "resume_id",
                "interview_id",
                "priority_score",
                "route_source",
                "route_stage",
                "task_type",
                "estimated_minutes",
                "due_date",
                "learning_material",
                "practice_task",
                "acceptance_criteria",
                "task_metadata",
                "evidence_basis",
                "done",
                "note",
                "weak_change",
            }
            for key in allowed_fields:
                if key in data:
                    setattr(item, key, patch.get(key))

            await db.commit()
            await db.refresh(item)
            return LearningTaskService._serialize(item)
        except SQLAlchemyError as exc:
            await db.rollback()
            raise ValidationError(message=user_facing_db_error(exc)) from exc

    @staticmethod
    async def delete_task(db: AsyncSession, user_id: int, task_key: str) -> Dict[str, Any]:
        try:
            result = await db.execute(
                select(LearningTask).where(LearningTask.user_id == user_id, LearningTask.task_key == task_key)
            )
            item = result.scalar_one_or_none()
            if not item:
                raise NotFoundError(message="学习任务不存在")
            await db.delete(item)
            await db.commit()
            return {"deleted": True, "task_key": task_key}
        except SQLAlchemyError as exc:
            await db.rollback()
            raise ValidationError(message=user_facing_db_error(exc)) from exc


learning_task_service = LearningTaskService()
