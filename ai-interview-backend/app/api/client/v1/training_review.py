from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import require_base_privacy_consent
from app.db.session import get_db
from app.models.user import User
from app.schemas.client.training_review import TrainingReviewUpdate
from app.schemas.response import ApiResponse
from app.services.client.training_review_service import training_review_service

router = APIRouter()


@router.get("/{interview_id}")
async def get_training_review(
    interview_id: int,
    current_user: User = Depends(require_base_privacy_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await training_review_service.get_review(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
    )
    return ApiResponse.success(data=result)


@router.put("/{interview_id}")
async def save_training_review(
    interview_id: int,
    payload: TrainingReviewUpdate,
    current_user: User = Depends(require_base_privacy_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await training_review_service.upsert_review(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
        data=payload.model_dump(exclude_unset=True),
    )
    return ApiResponse.success(data=result)
