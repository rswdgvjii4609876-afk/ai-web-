from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.backoffice.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.schemas.backoffice.learning_route import (
    LearningRouteBulkUpsert,
    LearningRoutePreviewTask,
    LearningRouteStageCreate,
    LearningRouteStageUpdate,
)
from app.schemas.response import ApiResponse
from app.services.backoffice.learning_route_service import learning_route_service

router = APIRouter()


@router.get("")
async def list_learning_routes(
    job_id: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    route_kind: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.list_routes(
        db=db,
        job_id=job_id,
        category=category,
        task_type=task_type,
        route_kind=route_kind,
        is_active=is_active,
        keyword=keyword,
    )
    return ApiResponse.success(data=result)


@router.post("")
async def create_learning_route(
    data: LearningRouteStageCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.create_route(db=db, data=data.model_dump())
    return ApiResponse.success(data=result)


@router.post("/bulk-upsert")
async def bulk_upsert_learning_routes(
    data: LearningRouteBulkUpsert,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.bulk_upsert_routes(db=db, payload=data.model_dump())
    return ApiResponse.success(data=result)


@router.post("/preview-task")
async def preview_learning_route_task(
    data: LearningRoutePreviewTask,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.preview_task(db=db, data=data.model_dump())
    return ApiResponse.success(data=result)


@router.get("/coverage")
async def learning_route_coverage(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.route_coverage(db=db)
    return ApiResponse.success(data=result)


@router.put("/{route_id}")
async def update_learning_route(
    route_id: int,
    data: LearningRouteStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.update_route(
        db=db,
        route_id=route_id,
        data=data.model_dump(exclude_unset=True),
    )
    return ApiResponse.success(data=result)


@router.post("/{route_id}/duplicate")
async def duplicate_learning_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.duplicate_route(db=db, route_id=route_id)
    return ApiResponse.success(data=result)


@router.delete("/{route_id}")
async def delete_learning_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await learning_route_service.delete_route(db=db, route_id=route_id)
    return ApiResponse.success(data=result)
