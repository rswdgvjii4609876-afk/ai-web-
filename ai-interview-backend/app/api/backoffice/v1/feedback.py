from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.backoffice.deps import require_content_manager_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackUpdate
from app.services.feedback import feedback_response, serialize_feedback

router = APIRouter()


@router.get("")
async def list_feedback(
    status: Literal["pending", "replied", "closed"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(require_content_manager_admin),
):
    query = select(Feedback)
    if status:
        query = query.where(Feedback.status == status)
    query = query.order_by(Feedback.id.desc()).offset(offset).limit(limit + 1)
    rows = (await db.execute(query)).scalars().all()
    return feedback_response({
        "items": [serialize_feedback(item, admin=True) for item in rows[:limit]],
        "has_more": len(rows) > limit,
    })


@router.patch("/{feedback_id}")
async def update_feedback(
    feedback_id: int,
    payload: FeedbackUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(require_content_manager_admin),
):
    query = select(Feedback).where(Feedback.id == feedback_id).with_for_update()
    item = (await db.execute(query)).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="留言不存在")
    item.status = payload.status
    if payload.reply:
        item.reply = payload.reply
        item.replied_by = current_admin.id
    await db.commit()
    await db.refresh(item)
    return feedback_response(serialize_feedback(item, admin=True))
