from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import require_base_privacy_consent
from app.db.session import get_db
from app.models.user import User
from app.schemas.client.learning_task import LearningTaskBulkUpsert, LearningTaskPatch
from app.schemas.response import ApiResponse
from app.services.client.learning_task_service import learning_task_service

router = APIRouter()


@router.get("")
async def list_learning_tasks(
    current_user: User = Depends(require_base_privacy_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await learning_task_service.list_tasks(db=db, user_id=current_user.id)
    return ApiResponse.success(data=result)


@router.post("/bulk-upsert")
async def bulk_upsert_learning_tasks(
    payload: LearningTaskBulkUpsert,
    current_user: User = Depends(require_base_privacy_consent),
    db: AsyncSession = Depends(get_db),
):
    tasks = [item.model_dump(exclude_unset=True) for item in payload.tasks]
    result = await learning_task_service.bulk_upsert(
        db=db,
        user_id=current_user.id,
        tasks=tasks,
        replace_progress=payload.replace_progress,
    )
    return ApiResponse.success(data=result)


@router.patch("/{task_key}")
async def patch_learning_task(
    task_key: str,
    payload: LearningTaskPatch,
    current_user: User = Depends(require_base_privacy_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await learning_task_service.patch_task(
        db=db,
        user_id=current_user.id,
        task_key=task_key,
        data=payload.model_dump(exclude_unset=True),
    )
    return ApiResponse.success(data=result)


@router.delete("/{task_key}")
async def delete_learning_task(
    task_key: str,
    current_user: User = Depends(require_base_privacy_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await learning_task_service.delete_task(db=db, user_id=current_user.id, task_key=task_key)
    return ApiResponse.success(data=result)
