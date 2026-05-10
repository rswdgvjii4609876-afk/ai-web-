from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import NotFoundError
from app.models.interview import Interview
from app.models.training_review import TrainingReview


class TrainingReviewService:
    @staticmethod
    def _clean(value: Any, max_length: int | None = None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:max_length] if max_length else text

    @staticmethod
    async def _ensure_interview_owner(db: AsyncSession, user_id: int, interview_id: int) -> Interview:
        result = await db.execute(
            select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")
        return interview

    @staticmethod
    def _empty(interview_id: int) -> Dict[str, Any]:
        return {
            "interview_id": interview_id,
            "self_rating": "",
            "notes": "",
            "next_goal": "",
            "updated_at": "",
        }

    @staticmethod
    def _serialize(item: TrainingReview) -> Dict[str, Any]:
        return {
            "interview_id": item.interview_id,
            "self_rating": item.self_rating or "",
            "notes": item.notes or "",
            "next_goal": item.next_goal or "",
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        }

    @staticmethod
    async def get_review(db: AsyncSession, user_id: int, interview_id: int) -> Dict[str, Any]:
        await TrainingReviewService._ensure_interview_owner(db, user_id, interview_id)
        result = await db.execute(
            select(TrainingReview).where(
                TrainingReview.user_id == user_id,
                TrainingReview.interview_id == interview_id,
            )
        )
        item = result.scalar_one_or_none()
        return TrainingReviewService._serialize(item) if item else TrainingReviewService._empty(interview_id)

    @staticmethod
    async def upsert_review(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        await TrainingReviewService._ensure_interview_owner(db, user_id, interview_id)
        result = await db.execute(
            select(TrainingReview).where(
                TrainingReview.user_id == user_id,
                TrainingReview.interview_id == interview_id,
            )
        )
        item = result.scalar_one_or_none()
        payload = {
            "self_rating": TrainingReviewService._clean(data.get("self_rating"), 20),
            "notes": TrainingReviewService._clean(data.get("notes")),
            "next_goal": TrainingReviewService._clean(data.get("next_goal")),
        }
        if item is None:
            item = TrainingReview(user_id=user_id, interview_id=interview_id, **payload)
            db.add(item)
        else:
            for key, value in payload.items():
                setattr(item, key, value)

        await db.commit()
        await db.refresh(item)
        return TrainingReviewService._serialize(item)


training_review_service = TrainingReviewService()
