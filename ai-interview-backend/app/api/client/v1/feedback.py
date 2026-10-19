from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreate
from app.services.feedback import feedback_response, serialize_feedback

router = APIRouter()


@router.post("")
async def create_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = Feedback(user_id=current_user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return feedback_response(serialize_feedback(item))


@router.get("")
async def list_feedback(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Feedback)
        .where(Feedback.user_id == current_user.id)
        .order_by(Feedback.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    rows = (await db.execute(query)).scalars().all()
    return feedback_response({
        "items": [serialize_feedback(item) for item in rows[:limit]],
        "has_more": len(rows) > limit,
    })


@router.get("/{feedback_id}")
async def get_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Feedback).where(
        Feedback.id == feedback_id, Feedback.user_id == current_user.id
    )
    item = (await db.execute(query)).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="留言不存在")
    return feedback_response(serialize_feedback(item))
