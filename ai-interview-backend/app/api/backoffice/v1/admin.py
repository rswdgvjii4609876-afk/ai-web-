from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, transaction
from app.schemas.backoffice.admin import AdminCreate, AdminResponse, AdminUpdate, AdminChangePassword, ResetPassword
from app.services.backoffice.admin import admin_service
from app.api.backoffice.deps import get_current_admin
from app.models.admin import Admin, ROOT_ADMIN_EMAIL
from app.schemas.response import ApiResponse
from app.schemas.paginator import Paginator
from typing import List
from app.exceptions.http_exceptions import APIException


router = APIRouter()

ADMIN_PERMISSION_FIELDS = {
    "can_manage_admins",
    "can_review_cases",
    "can_export_datasets",
    "can_delete_records",
}


def _can_manage_admins(admin: Admin) -> bool:
    return bool(getattr(admin, "can_manage_admins", False)) or bool(getattr(admin, "is_root_admin", False))


def _require_admin_manager(current_admin: Admin) -> None:
    if not _can_manage_admins(current_admin):
        raise APIException(status_code=403, message="Not enough permissions")


def _require_root_admin(current_admin: Admin) -> None:
    if not getattr(current_admin, "is_root_admin", False):
        raise APIException(status_code=403, message="Only the root admin can change admin-management permission")


def _is_reserved_root_email(email: str | None) -> bool:
    return (email or "").strip().lower() == ROOT_ADMIN_EMAIL


def _permission_payload_requests_grant(payload: dict) -> bool:
    return any(bool(payload.get(field)) for field in ADMIN_PERMISSION_FIELDS if field in payload)


@router.post("", response_model=AdminResponse)
async def create_admin(
    admin_data: AdminCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Create new admin (admin-management permission required)"""
    _require_admin_manager(current_admin)
    if _is_reserved_root_email(admin_data.email) and not current_admin.is_root_admin:
        raise APIException(status_code=403, message="Only root admin can create or claim the reserved root email")
    if _permission_payload_requests_grant(admin_data.model_dump()):
        _require_root_admin(current_admin)
    
    async with transaction(db):
        result = await admin_service.create_admin(db, admin_data)
        return ApiResponse.success(data=result)


@router.get("", response_model=List[AdminResponse])
async def list_admins(
    page: int = 1,
    per_page: int = 10,
    email: str = None,
    sort_by: str = None,
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get all admin list (admin-management permission required)

    Args:
        page: Page number, starting from 1
        per_page: Number of items per page
        email: Optional email filter
        sort_by: Sort field, supports email or created_at
        sort_order: Sort direction, asc or desc
    """
    _require_admin_manager(current_admin)
    
    query = await admin_service.get_admins_query(db, email=email, sort_by=sort_by, sort_order=sort_order)

    paginator = Paginator(query, db)
    result = await paginator.paginate(page, per_page)
    result = result.map(AdminResponse)
        
    return result.response()


@router.get("/{admin_id}", response_model=AdminResponse)
async def get_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Get admin details (superadmin or the admin themselves)"""
    # Admin managers can view any admin, regular admin can only view themselves.
    if not _can_manage_admins(current_admin) and current_admin.id != admin_id:
        raise APIException(
            status_code=403,
            message="Not enough permissions"
        )
    
    result = await admin_service.get_admin(db, admin_id)
    if not result:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Admin not found"
        )
    
    return ApiResponse.success(data=result)


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: int,
    admin_data: AdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Update admin information (admin managers or the admin themselves)"""
    if not _can_manage_admins(current_admin) and current_admin.id != admin_id:
        raise APIException(
            status_code=403,
            message="Not enough permissions"
        )

    target = await admin_service.get_admin_model(db, admin_id)
    if not target:
        raise APIException(status_code=status.HTTP_404_NOT_FOUND, message="Admin not found")

    update_payload = admin_data.model_dump(exclude_unset=True)
    if (
        "email" in update_payload
        and _is_reserved_root_email(update_payload.get("email"))
        and not target.is_root_admin
        and not current_admin.is_root_admin
    ):
        raise APIException(status_code=403, message="Only root admin can assign the reserved root email")
    if any(field in update_payload for field in ADMIN_PERMISSION_FIELDS):
        _require_root_admin(current_admin)
        if target.is_root_admin and any(update_payload.get(field) is False for field in ADMIN_PERMISSION_FIELDS):
            raise APIException(status_code=403, message="Cannot revoke root admin permission")

    if target.is_root_admin:
        if update_payload.get("is_active") is False:
            raise APIException(status_code=403, message="Cannot disable root admin")
        if "email" in update_payload and update_payload["email"].lower() != target.email.lower():
            raise APIException(status_code=403, message="Cannot change root admin email")
    
    async with transaction(db):
        result = await admin_service.update_admin(db, admin_id, update_payload)
        if not result:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Admin not found"
            )
        
        return ApiResponse.success_without_data()


@router.delete("/{admin_id}")
async def delete_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Delete admin (admin-management permission required)"""
    _require_admin_manager(current_admin)
    
    # Cannot delete yourself
    if current_admin.id == admin_id:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Cannot delete yourself"
        )
    
    target = await admin_service.get_admin_model(db, admin_id)
    if not target:
        raise APIException(status_code=status.HTTP_404_NOT_FOUND, message="Admin not found")
    if target.is_root_admin:
        raise APIException(status_code=status.HTTP_403_FORBIDDEN, message="Cannot delete root admin")

    async with transaction(db):
        result = await admin_service.delete_admin(db, admin_id)
        if not result:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Admin not found"
            )
        
        return ApiResponse.success_without_data()


@router.post("/{admin_id}/change-password")
async def change_password(
    admin_id: int,
    password_data: AdminChangePassword,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Change admin password (admin themselves only)"""
    # Can only change your own password
    if current_admin.id != admin_id:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            message="Can only change your own password"
        )
    
    async with transaction(db):
        result = await admin_service.change_password(
            db, 
            admin_id, 
            password_data.current_password, 
            password_data.new_password
        )
        
        return ApiResponse.success_without_data()


@router.post("/{admin_id}/reset-password")
async def reset_password(
    admin_id: int,
    password_data: ResetPassword,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Reset admin password (admin themselves or superadmin)"""
    if not _can_manage_admins(current_admin) and current_admin.id != admin_id:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            message="Can only change your own password"
        )
    target = await admin_service.get_admin_model(db, admin_id)
    if not target:
        raise APIException(status_code=status.HTTP_404_NOT_FOUND, message="Admin not found")
    if target.is_root_admin and current_admin.id != admin_id:
        raise APIException(status_code=status.HTTP_403_FORBIDDEN, message="Cannot reset root admin password")
    
    async with transaction(db):
        result = await admin_service.reset_password(
            db, 
            admin_id, 
            password_data.password
        )
        
        return ApiResponse.success_without_data()
