from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.competition import POSITION_PROFILES
from app.constants.learning_routes import iter_builtin_learning_route_stage_records
from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.learning_route_stage import LearningRouteStage

logger = logging.getLogger(__name__)

RouteResolver = Callable[[str, str, Optional[str]], Optional[Dict[str, Any]]]


class LearningRouteService:
    @staticmethod
    def _text(value: Any, max_length: Optional[int] = None) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:max_length] if max_length else text

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            raw = value
        else:
            raw = str(value).replace("，", ",").replace("\n", ",").split(",")
        result: List[str] = []
        for item in raw:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result

    @classmethod
    def _normalize_payload(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": cls._text(data.get("job_id"), 100),
            "job_name": cls._text(data.get("job_name"), 255),
            "category": cls._text(data.get("category"), 100),
            "route_source": cls._text(data.get("route_source"), 120) or "backoffice_learning_route",
            "route_stage": cls._text(data.get("route_stage"), 120) or "custom_stage",
            "stage_title": cls._text(data.get("stage_title") or data.get("title"), 255) or "学习路线阶段",
            "material_type": cls._text(data.get("material_type"), 100) or "custom_route",
            "task_type": cls._text(data.get("task_type"), 80) or "case_practice",
            "estimated_minutes": cls._positive_int(data.get("estimated_minutes")),
            "keywords": cls._string_list(data.get("keywords")),
            "learning_material": cls._text(data.get("learning_material") or data.get("material")),
            "practice_task": cls._text(data.get("practice_task")),
            "acceptance_criteria": cls._string_list(data.get("acceptance_criteria")),
            "is_active": bool(data.get("is_active", True)),
            "sort_order": cls._int_or_zero(data.get("sort_order")),
        }

    @staticmethod
    def _positive_int(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _int_or_zero(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def quality_hints(item: LearningRouteStage | Dict[str, Any]) -> List[str]:
        getter = item.get if isinstance(item, dict) else lambda key, default=None: getattr(item, key, default)
        hints: List[str] = []
        if not getter("practice_task"):
            hints.append("缺少练习任务")
        if not getter("acceptance_criteria"):
            hints.append("缺少验收方式")
        if not getter("estimated_minutes"):
            hints.append("缺少预计耗时")
        if not getter("keywords"):
            hints.append("缺少关键词")
        return hints

    @classmethod
    def quality_level(cls, item: LearningRouteStage | Dict[str, Any]) -> Dict[str, str]:
        hints = cls.quality_hints(item)
        if not hints:
            return {"level": "complete", "label": "完整"}
        if "缺少练习任务" in hints or "缺少验收方式" in hints:
            return {"level": "not_recommended", "label": "不建议启用"}
        return {"level": "needs_improvement", "label": "需补充"}

    @classmethod
    def quality_summary(cls, items: Iterable[LearningRouteStage | Dict[str, Any]]) -> Dict[str, int]:
        summary = {
            "complete_total": 0,
            "needs_improvement_total": 0,
            "not_recommended_total": 0,
            "missing_practice_total": 0,
            "missing_acceptance_total": 0,
            "missing_minutes_total": 0,
            "missing_keywords_total": 0,
        }
        for item in items:
            hints = cls.quality_hints(item)
            level = cls.quality_level(item)["level"]
            if level == "complete":
                summary["complete_total"] += 1
            elif level == "not_recommended":
                summary["not_recommended_total"] += 1
            else:
                summary["needs_improvement_total"] += 1
            if "缺少练习任务" in hints:
                summary["missing_practice_total"] += 1
            if "缺少验收方式" in hints:
                summary["missing_acceptance_total"] += 1
            if "缺少预计耗时" in hints:
                summary["missing_minutes_total"] += 1
            if "缺少关键词" in hints:
                summary["missing_keywords_total"] += 1
        return summary

    @classmethod
    def _route_dict(cls, item: LearningRouteStage | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(item, dict):
            return {
                "route_source": item.get("route_source") or "backoffice_learning_route",
                "route_stage": item.get("route_stage") or "custom_stage",
                "title": item.get("stage_title") or item.get("title") or "学习路线阶段",
                "material_type": item.get("material_type") or "custom_route",
                "task_type": item.get("task_type") or "case_practice",
                "estimated_minutes": cls._positive_int(item.get("estimated_minutes")) or 120,
                "keywords": cls._string_list(item.get("keywords")),
                "material": item.get("learning_material") or item.get("material") or "后台维护学习路线",
                "practice_task": item.get("practice_task") or "",
                "acceptance_criteria": cls._string_list(item.get("acceptance_criteria")),
            }
        return {
            "route_source": item.route_source,
            "route_stage": item.route_stage,
            "title": item.stage_title,
            "material_type": item.material_type,
            "task_type": item.task_type,
            "estimated_minutes": item.estimated_minutes or 120,
            "keywords": cls._string_list(item.keywords),
            "material": item.learning_material or "后台维护学习路线",
            "practice_task": item.practice_task or "",
            "acceptance_criteria": cls._string_list(item.acceptance_criteria),
        }

    @classmethod
    def serialize(cls, item: LearningRouteStage) -> Dict[str, Any]:
        route = cls._route_dict(item)
        return {
            "id": item.id,
            "route_id": item.id,
            "job_id": item.job_id or "",
            "job_name": item.job_name or "",
            "category": item.category or "",
            "route_source": route["route_source"],
            "route_stage": route["route_stage"],
            "stage_title": route["title"],
            "title": route["title"],
            "material_type": route["material_type"],
            "task_type": route["task_type"],
            "estimated_minutes": route["estimated_minutes"],
            "keywords": route["keywords"],
            "learning_material": route["material"],
            "material": route["material"],
            "practice_task": route["practice_task"],
            "acceptance_criteria": route["acceptance_criteria"],
            "is_active": bool(item.is_active),
            "sort_order": item.sort_order,
            "quality_hints": cls.quality_hints(item),
            "quality_level": cls.quality_level(item)["level"],
            "quality_label": cls.quality_level(item)["label"],
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        }

    @classmethod
    def _import_identity(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = cls._normalize_payload(data)
        missing_fields: List[str] = []
        if not cls._text(data.get("route_stage")):
            missing_fields.append("route_stage")
        if not cls._text(data.get("stage_title") or data.get("title")):
            missing_fields.append("stage_title")
        if not cls._text(data.get("task_type")):
            missing_fields.append("task_type")
        if missing_fields:
            raise ValidationError(message=f"学习路线导入失败：缺少关键字段 {', '.join(missing_fields)}")
        return {
            "job_id": normalized.get("job_id"),
            "category": normalized.get("category"),
            "route_stage": normalized.get("route_stage"),
            "task_type": normalized.get("task_type"),
            "normalized": normalized,
        }

    @classmethod
    def _duplicate_payload(cls, item: LearningRouteStage) -> Dict[str, Any]:
        data = cls.serialize(item)
        return cls._normalize_payload(
            {
                **data,
                "route_stage": f"{data.get('route_stage') or 'route'}_copy_{item.id}",
                "stage_title": f"{data.get('stage_title') or '学习路线阶段'} 副本",
                "is_active": False,
                "sort_order": (data.get("sort_order") or 0) + 1,
            }
        )

    @classmethod
    def match_loaded_routes(
        cls,
        records: Iterable[Dict[str, Any]],
        job_id: str,
        text: str,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        match = cls._match_loaded_route_record(records=records, job_id=job_id, text=text, category=category)
        return cls._route_dict(match) if match else None

    @classmethod
    def _match_loaded_route_record(
        cls,
        records: Iterable[Dict[str, Any]],
        job_id: str,
        text: str,
        category: Optional[str] = None,
        *,
        allow_fallback: bool = True,
    ) -> Optional[Dict[str, Any]]:
        items = list(records)
        if not items:
            return None

        def _matches_job(item: Dict[str, Any]) -> bool:
            return bool(job_id) and item.get("job_id") == job_id

        def _matches_category(item: Dict[str, Any]) -> bool:
            return bool(category) and not item.get("job_id") and item.get("category") == category

        candidates = [item for item in items if _matches_job(item)]
        if not candidates:
            candidates = [item for item in items if _matches_category(item)]
        if not candidates:
            return None

        normalized = (text or "").lower()
        for item in sorted(candidates, key=lambda row: row.get("sort_order") or 0):
            keywords = cls._string_list(item.get("keywords"))
            if any(keyword.lower() in normalized for keyword in keywords):
                return item
        if not allow_fallback:
            return None
        return sorted(candidates, key=lambda row: row.get("sort_order") or 0)[-1]

    @classmethod
    def coverage_matrix(cls, records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        items = [dict(item) for item in records]
        active_items = [item for item in items if item.get("is_active")]
        rows: List[Dict[str, Any]] = []

        for profile in POSITION_PROFILES:
            ability_model = profile.get("ability_model") or []
            job_id = profile.get("job_id") or ""
            category = profile.get("category") or ""
            related_routes = [
                item for item in active_items
                if item.get("job_id") == job_id or (not item.get("job_id") and item.get("category") == category)
            ]
            ability_matches: List[Dict[str, Any]] = []
            for ability in ability_model:
                text = " ".join(
                    [
                        str(ability.get("name") or ""),
                        " ".join(cls._string_list(ability.get("keywords"))),
                        " ".join(cls._string_list(ability.get("evidence_hints"))),
                    ]
                )
                match = cls._match_loaded_route_record(
                    records=active_items,
                    job_id=job_id,
                    text=text,
                    category=category,
                    allow_fallback=False,
                )
                ability_matches.append(
                    {
                        "ability_id": ability.get("ability_id") or "",
                        "ability_name": ability.get("name") or "",
                        "matched": bool(match),
                        "route_id": match.get("route_id") if match else None,
                        "route_stage": match.get("route_stage") if match else "",
                        "stage_title": match.get("stage_title") or match.get("title") if match else "",
                        "quality_level": match.get("quality_level") if match else "",
                        "quality_label": match.get("quality_label") if match else "待补路线",
                        "quality_hints": match.get("quality_hints") if match else [],
                    }
                )

            quality = cls.quality_summary(related_routes)
            ability_total = len(ability_model)
            matched_ability_total = len([item for item in ability_matches if item["matched"]])
            coverage_rate = round((matched_ability_total / ability_total) * 100) if ability_total else 0
            if quality["not_recommended_total"]:
                status = {"value": "not_recommended", "label": "不建议上线"}
            elif coverage_rate >= 80 and related_routes:
                status = {"value": "good", "label": "覆盖良好"}
            else:
                status = {"value": "needs_route", "label": "需补路线"}

            rows.append(
                {
                    "job_id": job_id,
                    "job_name": profile.get("job_name") or job_id,
                    "category": category,
                    "ability_total": ability_total,
                    "matched_ability_total": matched_ability_total,
                    "unmatched_ability_total": ability_total - matched_ability_total,
                    "active_route_total": len(related_routes),
                    "complete_route_total": quality["complete_total"],
                    "missing_practice_total": quality["missing_practice_total"],
                    "missing_acceptance_total": quality["missing_acceptance_total"],
                    "missing_keywords_total": quality["missing_keywords_total"],
                    "coverage_rate": coverage_rate,
                    "status": status["value"],
                    "status_label": status["label"],
                    "ability_matches": ability_matches,
                }
            )

        return {
            "total_positions": len(rows),
            "good_total": len([item for item in rows if item["status"] == "good"]),
            "needs_route_total": len([item for item in rows if item["status"] == "needs_route"]),
            "not_recommended_total": len([item for item in rows if item["status"] == "not_recommended"]),
            "average_coverage_rate": round(sum(item["coverage_rate"] for item in rows) / len(rows)) if rows else 0,
            "items": rows,
        }

    @classmethod
    async def ensure_seeded_from_builtins(cls, db: AsyncSession) -> int:
        total = await db.scalar(select(func.count()).select_from(LearningRouteStage))
        if total:
            return 0

        created = 0
        for record in iter_builtin_learning_route_stage_records():
            data = cls._normalize_payload(
                {
                    **record,
                    "stage_title": record.get("title"),
                    "learning_material": record.get("material"),
                }
            )
            db.add(LearningRouteStage(**data))
            created += 1
        await db.commit()
        return created

    @classmethod
    async def list_routes(
        cls,
        db: AsyncSession,
        *,
        job_id: Optional[str] = None,
        category: Optional[str] = None,
        task_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        seeded = await cls.ensure_seeded_from_builtins(db)
        all_result = await db.execute(select(LearningRouteStage))
        all_items = list(all_result.scalars().all())

        query = select(LearningRouteStage)
        if job_id:
            query = query.where(LearningRouteStage.job_id == job_id)
        if category:
            query = query.where(LearningRouteStage.category == category)
        if task_type:
            query = query.where(LearningRouteStage.task_type == task_type)
        if is_active is not None:
            query = query.where(LearningRouteStage.is_active.is_(is_active))
        if keyword:
            pattern = f"%{keyword}%"
            query = query.where(
                or_(
                    LearningRouteStage.job_name.ilike(pattern),
                    LearningRouteStage.stage_title.ilike(pattern),
                    LearningRouteStage.route_stage.ilike(pattern),
                    LearningRouteStage.learning_material.ilike(pattern),
                )
            )
        query = query.order_by(
            LearningRouteStage.job_id.asc(),
            LearningRouteStage.category.asc(),
            LearningRouteStage.sort_order.asc(),
            LearningRouteStage.id.asc(),
        )
        result = await db.execute(query)
        items = list(result.scalars().all())
        return {
            "total": len(all_items),
            "active_total": len([item for item in all_items if item.is_active]),
            "job_coverage_total": len({item.job_id for item in all_items if item.job_id}),
            "category_coverage_total": len({item.category for item in all_items if item.category}),
            "seeded_total": seeded,
            "quality_summary": cls.quality_summary(all_items),
            "items": [cls.serialize(item) for item in items],
            "filters": {
                "job_ids": sorted({item.job_id for item in all_items if item.job_id}),
                "categories": sorted({item.category for item in all_items if item.category}),
                "task_types": sorted({item.task_type for item in all_items if item.task_type}),
            },
        }

    @classmethod
    async def route_coverage(cls, db: AsyncSession) -> Dict[str, Any]:
        await cls.ensure_seeded_from_builtins(db)
        result = await db.execute(
            select(LearningRouteStage).order_by(
                LearningRouteStage.job_id.asc(),
                LearningRouteStage.category.asc(),
                LearningRouteStage.sort_order.asc(),
                LearningRouteStage.id.asc(),
            )
        )
        records = [cls.serialize(item) for item in result.scalars().all()]
        return cls.coverage_matrix(records)

    @classmethod
    async def create_route(cls, db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        item = LearningRouteStage(**cls._normalize_payload(data))
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return cls.serialize(item)

    @classmethod
    async def update_route(cls, db: AsyncSession, route_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        item = await db.get(LearningRouteStage, route_id)
        if not item:
            raise NotFoundError(message="学习路线阶段不存在")
        normalized = cls._normalize_payload({**cls.serialize(item), **data})
        for key, value in normalized.items():
            setattr(item, key, value)
        await db.commit()
        await db.refresh(item)
        return cls.serialize(item)

    @classmethod
    async def delete_route(cls, db: AsyncSession, route_id: int) -> Dict[str, Any]:
        item = await db.get(LearningRouteStage, route_id)
        if not item:
            raise NotFoundError(message="学习路线阶段不存在")
        await db.delete(item)
        await db.commit()
        return {"deleted": True, "route_id": route_id}

    @classmethod
    async def bulk_upsert_routes(cls, db: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("version") not in (None, "learning_routes_v1"):
            raise ValidationError(message="学习路线导入失败：JSON 版本必须是 learning_routes_v1")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValidationError(message="学习路线导入失败：items 不能为空")

        created = 0
        updated = 0
        imported_items: List[LearningRouteStage] = []
        for index, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                raise ValidationError(message=f"学习路线导入失败：第 {index} 条不是对象")
            try:
                identity = cls._import_identity(raw)
            except ValidationError as exc:
                raise ValidationError(message=f"学习路线导入失败：第 {index} 条 {exc.detail}") from exc

            query = select(LearningRouteStage).where(
                LearningRouteStage.route_stage == identity["route_stage"],
                LearningRouteStage.task_type == identity["task_type"],
            )
            if identity["job_id"]:
                query = query.where(LearningRouteStage.job_id == identity["job_id"])
            else:
                query = query.where(LearningRouteStage.job_id.is_(None))
            if identity["category"]:
                query = query.where(LearningRouteStage.category == identity["category"])
            else:
                query = query.where(LearningRouteStage.category.is_(None))

            result = await db.execute(query)
            item = result.scalars().first()
            if item:
                for key, value in identity["normalized"].items():
                    setattr(item, key, value)
                updated += 1
            else:
                item = LearningRouteStage(**identity["normalized"])
                db.add(item)
                created += 1
            imported_items.append(item)

        await db.commit()
        for item in imported_items:
            await db.refresh(item)
        return {
            "version": "learning_routes_v1",
            "created_total": created,
            "updated_total": updated,
            "total": created + updated,
            "items": [cls.serialize(item) for item in imported_items],
        }

    @classmethod
    async def duplicate_route(cls, db: AsyncSession, route_id: int) -> Dict[str, Any]:
        item = await db.get(LearningRouteStage, route_id)
        if not item:
            raise NotFoundError(message="学习路线阶段不存在")
        copy = LearningRouteStage(**cls._duplicate_payload(item))
        db.add(copy)
        await db.commit()
        await db.refresh(copy)
        return cls.serialize(copy)

    @classmethod
    def preview_task_from_route(
        cls,
        route: Dict[str, Any],
        *,
        target_position: str,
        job_id: Optional[str],
        category: Optional[str],
        ability_name: str,
        missing_keywords: List[str],
    ) -> Dict[str, Any]:
        from app.services.client.matching_engine import MatchingEngine

        profile = {
            "job_id": job_id or "preview_position",
            "job_name": target_position or "目标岗位",
            "category": category or "预览岗位",
        }
        ability_item = {
            "ability_id": "preview_ability",
            "name": ability_name or "岗位能力",
            "missing_keywords": missing_keywords,
            "matched_keywords": [],
            "priority_score": 80,
            "current_level": 1,
            "required_level": 3,
            "gap": 2,
            "evidence_basis": "后台学习路线预览，不写入用户学习任务。",
        }

        def resolver(_: str, __: str, ___: Optional[str] = None) -> Dict[str, Any]:
            return route

        return MatchingEngine._build_learning_task(
            item=ability_item,
            profile=profile,
            target_position=target_position or "目标岗位",
            rank=1,
            route_stage_resolver=resolver,
        )

    @classmethod
    async def preview_task(cls, db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        await cls.ensure_seeded_from_builtins(db)
        route_id = cls._positive_int(data.get("route_id"))
        include_inactive = bool(data.get("include_inactive"))
        target_position = cls._text(data.get("target_position"), 255) or "目标岗位"
        job_id = cls._text(data.get("job_id"), 100)
        category = cls._text(data.get("category"), 100)
        ability_name = cls._text(data.get("ability_name"), 120) or "岗位能力"
        missing_keywords = cls._string_list(data.get("missing_keywords"))

        if route_id:
            item = await db.get(LearningRouteStage, route_id)
            if not item:
                raise NotFoundError(message="学习路线阶段不存在")
            if not item.is_active and not include_inactive:
                raise ValidationError(message="该路线已停用，如需预览请勾选预览停用路线")
            route = cls._route_dict(item)
            selected = cls.serialize(item)
        else:
            result = await db.execute(
                select(LearningRouteStage)
                .where(LearningRouteStage.is_active.is_(True))
                .order_by(LearningRouteStage.sort_order.asc(), LearningRouteStage.id.asc())
            )
            records = [cls.serialize(item) for item in result.scalars().all()]
            text = " ".join([target_position, ability_name, *missing_keywords])
            route = cls.match_loaded_routes(records=records, job_id=job_id or "", text=text, category=category)
            if not route:
                raise ValidationError(message="未找到可用于预览的启用学习路线")
            selected = route

        task = cls.preview_task_from_route(
            route,
            target_position=target_position,
            job_id=job_id,
            category=category,
            ability_name=ability_name,
            missing_keywords=missing_keywords,
        )
        return {
            "route": selected,
            "task": task,
        }

    @classmethod
    async def build_route_stage_resolver(cls, db: AsyncSession) -> Optional[RouteResolver]:
        try:
            result = await db.execute(
                select(LearningRouteStage)
                .where(LearningRouteStage.is_active.is_(True))
                .order_by(LearningRouteStage.sort_order.asc(), LearningRouteStage.id.asc())
            )
            records = [
                {
                    **cls.serialize(item),
                    "job_id": item.job_id,
                    "category": item.category,
                    "sort_order": item.sort_order,
                }
                for item in result.scalars().all()
            ]
        except SQLAlchemyError as exc:
            logger.warning("Learning route DB lookup failed, falling back to built-in routes: %s", exc)
            await db.rollback()
            return None

        if not records:
            return None

        def resolver(job_id: str, text: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
            return cls.match_loaded_routes(records=records, job_id=job_id, text=text, category=category)

        return resolver


learning_route_service = LearningRouteService()
