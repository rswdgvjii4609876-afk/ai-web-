from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.backoffice.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
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
async def get_public_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await position_knowledge_base_service.list_public_items(db)
    return ApiResponse.success(data=result)


@router.post("")
async def create_public_knowledge_base(
    data: PositionKnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await position_knowledge_base_service.create_public_item(
        db=db,
        admin_id=current_admin.id,
        data=data.model_dump(),
    )
    return ApiResponse.success(data=result)


@router.get("/{knowledge_base_id}/slices")
async def get_public_knowledge_base_slices(
    knowledge_base_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await position_knowledge_base_service.list_public_item_slices(
        db=db,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResponse.success(data=result)


@router.post("/{knowledge_base_id}/slices/rebuild")
async def rebuild_public_knowledge_base_slices(
    knowledge_base_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await position_knowledge_base_service.rebuild_public_item_slices(
        db=db,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResponse.success(data=result)


@router.put("/{knowledge_base_id}")
async def update_public_knowledge_base(
    knowledge_base_id: int,
    data: PositionKnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await position_knowledge_base_service.update_public_item(
        db=db,
        knowledge_base_id=knowledge_base_id,
        data=data.model_dump(exclude_unset=True),
    )
    return ApiResponse.success(data=result)


@router.delete("/{knowledge_base_id}")
async def delete_public_knowledge_base(
    knowledge_base_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    result = await position_knowledge_base_service.delete_public_item(
        db=db,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResponse.success(data=result)
