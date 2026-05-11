from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.client.learning_plan import LearningPlanGenerateRequest
from app.schemas.response import ApiResponse
from app.services.client.learning_plan_service import learning_plan_service

router = APIRouter()


@router.get("/options")
async def learning_plan_options(
    target_position: Optional[str] = Query(default=None),
    resume_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await learning_plan_service.options(
        db=db,
        user=current_user,
        target_position=target_position,
        resume_id=resume_id,
    )
    return ApiResponse.success(data=result)

@router.post("/generate")
async def generate_learning_plan(
    payload: LearningPlanGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await learning_plan_service.generate(
        db=db,
        user=current_user,
        payload=payload.model_dump(exclude_unset=True),
    )
    return ApiResponse.success(data=result)
