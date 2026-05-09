import logging
from typing import Dict, Optional

from sqlalchemy import and_, inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


logger = logging.getLogger(__name__)


class PositionKnowledgeBaseService:
    @staticmethod
    def _clean_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _serialize(
        item: PositionKnowledgeBase,
        current_user_id: Optional[int] = None,
        admin_view: bool = False,
    ) -> Dict:
        preview = item.knowledge_content.strip()
        if len(preview) > 140:
            preview = preview[:140].rstrip() + "..."

        scope = item.scope or "private"
        is_public = scope == "public"
        editable = admin_view or (
            current_user_id is not None and not is_public and item.user_id == current_user_id
        )

        state = inspect(item)
        slice_count = len(item.slices) if "slices" not in state.unloaded else None

        return {
            "knowledge_base_id": item.id,
            "title": item.title,
            "target_position": item.target_position,
            "knowledge_content": item.knowledge_content,
            "scope": scope,
            "source_label": "后台公共知识库" if is_public else "用户私有知识库",
            "editable": editable,
            "focus_points": item.focus_points,
            "interviewer_prompt": item.interviewer_prompt,
            "is_active": item.is_active,
            "preview": preview,
            "slice_count": slice_count,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    @staticmethod
    async def _safe_rebuild_slices(db: AsyncSession, item: PositionKnowledgeBase) -> None:
        try:
            async with db.begin_nested():
                await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)
        except Exception as exc:
            logger.warning("Slice rebuild skipped for knowledge_base=%s: %s", item.id, exc)

    @staticmethod
    async def _get_user_visible_item(
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int,
    ) -> PositionKnowledgeBase:
        result = await db.execute(
            select(PositionKnowledgeBase).where(
                PositionKnowledgeBase.id == knowledge_base_id,
                or_(
                    PositionKnowledgeBase.user_id == user_id,
                    PositionKnowledgeBase.scope == "public",
                ),
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(message="知识库不存在")
        return item

    @staticmethod
    async def _get_private_item(
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int,
    ) -> PositionKnowledgeBase:
        result = await db.execute(
            select(PositionKnowledgeBase).where(
                PositionKnowledgeBase.id == knowledge_base_id,
                PositionKnowledgeBase.user_id == user_id,
                PositionKnowledgeBase.scope == "private",
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(message="知识库不存在")
        return item

    @staticmethod
    async def _get_public_item(
        db: AsyncSession,
        knowledge_base_id: int,
    ) -> PositionKnowledgeBase:
        result = await db.execute(
            select(PositionKnowledgeBase).where(
                PositionKnowledgeBase.id == knowledge_base_id,
                PositionKnowledgeBase.scope == "public",
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(message="公共知识库不存在")
        return item

    @staticmethod
    async def list_items(
        db: AsyncSession,
        user_id: int,
        target_position: Optional[str] = None,
    ) -> Dict:
        query = select(PositionKnowledgeBase).options(selectinload(PositionKnowledgeBase.slices)).where(
            or_(
                PositionKnowledgeBase.user_id == user_id,
                and_(
                    PositionKnowledgeBase.scope == "public",
                    PositionKnowledgeBase.is_active.is_(True),
                ),
            )
        )

        if target_position and target_position.strip():
            query = query.where(
                PositionKnowledgeBase.target_position.ilike(f"%{target_position.strip()}%")
            )

        query = query.order_by(PositionKnowledgeBase.updated_at.desc())
        result = await db.execute(query)
        items = result.scalars().all()
        items = sorted(
            items,
            key=lambda item: (
                0 if (item.scope or "private") == "private" and item.user_id == user_id else 1,
                0 if item.is_active else 1,
                -(item.updated_at.timestamp() if item.updated_at else 0),
            ),
        )

        return {
            "total": len(items),
            "items": [PositionKnowledgeBaseService._serialize(item, current_user_id=user_id) for item in items],
        }

    @staticmethod
    async def create_item(
        db: AsyncSession,
        user_id: int,
        data: Dict,
    ) -> Dict:
        title = data["title"].strip()
        target_position = data["target_position"].strip()
        knowledge_content = data["knowledge_content"].strip()
        if not title or not target_position or not knowledge_content:
            raise ValidationError(message="标题、目标岗位和知识库正文不能为空")

        item = PositionKnowledgeBase(
            user_id=user_id,
            admin_id=None,
            scope="private",
            title=title,
            target_position=target_position,
            knowledge_content=knowledge_content,
            focus_points=PositionKnowledgeBaseService._clean_optional_text(data.get("focus_points")),
            interviewer_prompt=PositionKnowledgeBaseService._clean_optional_text(
                data.get("interviewer_prompt")
            ),
            is_active=data.get("is_active", True),
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        await PositionKnowledgeBaseService._safe_rebuild_slices(db, item)
        await db.commit()
        await db.refresh(item)
        return PositionKnowledgeBaseService._serialize(item, current_user_id=user_id)

    @staticmethod
    async def update_item(
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int,
        data: Dict,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_private_item(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )

        update_data = data.copy()
        if "title" in update_data and update_data["title"] is not None:
            update_data["title"] = update_data["title"].strip()
        if "target_position" in update_data and update_data["target_position"] is not None:
            update_data["target_position"] = update_data["target_position"].strip()
        if "knowledge_content" in update_data and update_data["knowledge_content"] is not None:
            update_data["knowledge_content"] = update_data["knowledge_content"].strip()
        if "focus_points" in update_data:
            update_data["focus_points"] = PositionKnowledgeBaseService._clean_optional_text(
                update_data["focus_points"]
            )
        if "interviewer_prompt" in update_data:
            update_data["interviewer_prompt"] = PositionKnowledgeBaseService._clean_optional_text(
                update_data["interviewer_prompt"]
            )

        if "title" in update_data and update_data["title"] == "":
            raise ValidationError(message="标题不能为空")
        if "target_position" in update_data and update_data["target_position"] == "":
            raise ValidationError(message="目标岗位不能为空")
        if "knowledge_content" in update_data and update_data["knowledge_content"] == "":
            raise ValidationError(message="知识库正文不能为空")

        for key, value in update_data.items():
            setattr(item, key, value)

        await PositionKnowledgeBaseService._safe_rebuild_slices(db, item)
        await db.commit()
        await db.refresh(item)
        return PositionKnowledgeBaseService._serialize(item, current_user_id=user_id)

    @staticmethod
    async def delete_item(
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_private_item(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )

        await db.delete(item)
        await db.commit()
        return {"message": "知识库已删除"}

    @staticmethod
    async def list_public_items(db: AsyncSession) -> Dict:
        query = (
            select(PositionKnowledgeBase)
            .options(selectinload(PositionKnowledgeBase.slices))
            .where(PositionKnowledgeBase.scope == "public")
            .order_by(PositionKnowledgeBase.updated_at.desc())
        )
        result = await db.execute(query)
        items = result.scalars().all()
        return {
            "total": len(items),
            "items": [PositionKnowledgeBaseService._serialize(item, admin_view=True) for item in items],
        }

    @staticmethod
    async def create_public_item(
        db: AsyncSession,
        admin_id: int,
        data: Dict,
    ) -> Dict:
        title = data["title"].strip()
        target_position = data["target_position"].strip()
        knowledge_content = data["knowledge_content"].strip()
        if not title or not target_position or not knowledge_content:
            raise ValidationError(message="标题、目标岗位和知识库正文不能为空")

        item = PositionKnowledgeBase(
            user_id=None,
            admin_id=admin_id,
            scope="public",
            title=title,
            target_position=target_position,
            knowledge_content=knowledge_content,
            focus_points=PositionKnowledgeBaseService._clean_optional_text(data.get("focus_points")),
            interviewer_prompt=PositionKnowledgeBaseService._clean_optional_text(
                data.get("interviewer_prompt")
            ),
            is_active=data.get("is_active", True),
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        await PositionKnowledgeBaseService._safe_rebuild_slices(db, item)
        await db.commit()
        await db.refresh(item)
        return PositionKnowledgeBaseService._serialize(item, admin_view=True)

    @staticmethod
    async def update_public_item(
        db: AsyncSession,
        knowledge_base_id: int,
        data: Dict,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_public_item(
            db=db,
            knowledge_base_id=knowledge_base_id,
        )

        update_data = data.copy()
        if "title" in update_data and update_data["title"] is not None:
            update_data["title"] = update_data["title"].strip()
        if "target_position" in update_data and update_data["target_position"] is not None:
            update_data["target_position"] = update_data["target_position"].strip()
        if "knowledge_content" in update_data and update_data["knowledge_content"] is not None:
            update_data["knowledge_content"] = update_data["knowledge_content"].strip()
        if "focus_points" in update_data:
            update_data["focus_points"] = PositionKnowledgeBaseService._clean_optional_text(
                update_data["focus_points"]
            )
        if "interviewer_prompt" in update_data:
            update_data["interviewer_prompt"] = PositionKnowledgeBaseService._clean_optional_text(
                update_data["interviewer_prompt"]
            )

        if "title" in update_data and update_data["title"] == "":
            raise ValidationError(message="标题不能为空")
        if "target_position" in update_data and update_data["target_position"] == "":
            raise ValidationError(message="目标岗位不能为空")
        if "knowledge_content" in update_data and update_data["knowledge_content"] == "":
            raise ValidationError(message="知识库正文不能为空")

        for key, value in update_data.items():
            setattr(item, key, value)

        await PositionKnowledgeBaseService._safe_rebuild_slices(db, item)
        await db.commit()
        await db.refresh(item)
        return PositionKnowledgeBaseService._serialize(item, admin_view=True)

    @staticmethod
    async def delete_public_item(
        db: AsyncSession,
        knowledge_base_id: int,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_public_item(
            db=db,
            knowledge_base_id=knowledge_base_id,
        )

        await db.delete(item)
        await db.commit()
        return {"message": "公共知识库已删除"}

    @staticmethod
    async def list_item_slices(
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_user_visible_item(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )
        slices = await position_knowledge_base_slice_service.list_for_knowledge_base(db, item.id)
        return {
            "knowledge_base_id": item.id,
            "title": item.title,
            "scope": item.scope or "private",
            "total": len(slices),
            "items": slices,
        }

    @staticmethod
    async def rebuild_item_slices(
        db: AsyncSession,
        user_id: int,
        knowledge_base_id: int,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_private_item(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )
        try:
            async with db.begin_nested():
                rebuilt = await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning("Manual private slice rebuild failed for knowledge_base=%s: %s", item.id, exc)
            raise ValidationError(message="切片重建失败，请稍后重试") from exc

        return {
            "knowledge_base_id": item.id,
            "title": item.title,
            "scope": item.scope or "private",
            "rebuilt": True,
            "total": len(rebuilt),
            "items": rebuilt,
        }

    @staticmethod
    async def list_public_item_slices(
        db: AsyncSession,
        knowledge_base_id: int,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_public_item(
            db=db,
            knowledge_base_id=knowledge_base_id,
        )
        slices = await position_knowledge_base_slice_service.list_for_knowledge_base(db, item.id)
        return {
            "knowledge_base_id": item.id,
            "title": item.title,
            "scope": item.scope or "public",
            "total": len(slices),
            "items": slices,
        }

    @staticmethod
    async def rebuild_public_item_slices(
        db: AsyncSession,
        knowledge_base_id: int,
    ) -> Dict:
        item = await PositionKnowledgeBaseService._get_public_item(
            db=db,
            knowledge_base_id=knowledge_base_id,
        )
        try:
            async with db.begin_nested():
                rebuilt = await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning("Manual public slice rebuild failed for knowledge_base=%s: %s", item.id, exc)
            raise ValidationError(message="公共知识库切片重建失败，请稍后重试") from exc

        return {
            "knowledge_base_id": item.id,
            "title": item.title,
            "scope": item.scope or "public",
            "rebuilt": True,
            "total": len(rebuilt),
            "items": rebuilt,
        }


position_knowledge_base_service = PositionKnowledgeBaseService()
