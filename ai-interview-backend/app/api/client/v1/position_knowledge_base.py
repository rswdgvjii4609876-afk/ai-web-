from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.client.position_knowledge_base import (
    PositionKnowledgeBaseCreate,
    PositionKnowledgeBaseUpdate,
)
from app.schemas.response import ApiResponse
from app.services.client.position_knowledge_base_service import (
    position_knowledge_base_service,
)

router = APIRouter()


@router.get("")
async def get_position_knowledge_bases(
    target_position: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await position_knowledge_base_service.list_items(
        db=db,
        user_id=current_user.id,
        target_position=target_position,
    )
    return ApiResponse.success(data=result)


@router.post("")
async def create_position_knowledge_base(
    data: PositionKnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await position_knowledge_base_service.create_item(
        db=db,
        user_id=current_user.id,
        data=data.model_dump(),
    )
    return ApiResponse.success(data=result)


@router.get("/{knowledge_base_id}/slices")
async def get_position_knowledge_base_slices(
    knowledge_base_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await position_knowledge_base_service.list_item_slices(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResponse.success(data=result)


@router.post("/{knowledge_base_id}/slices/rebuild")
async def rebuild_position_knowledge_base_slices(
    knowledge_base_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await position_knowledge_base_service.rebuild_item_slices(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResponse.success(data=result)


@router.put("/{knowledge_base_id}")
async def update_position_knowledge_base(
    knowledge_base_id: int,
    data: PositionKnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await position_knowledge_base_service.update_item(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
        data=data.model_dump(exclude_unset=True),
    )
    return ApiResponse.success(data=result)


@router.delete("/{knowledge_base_id}")
async def delete_position_knowledge_base(
    knowledge_base_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await position_knowledge_base_service.delete_item(
        db=db,
        user_id=current_user.id,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResponse.success(data=result)
