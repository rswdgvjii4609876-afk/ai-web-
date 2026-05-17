from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import AuthBase
from app.models.admin import Admin
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/backoffice/auth/login")


async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Admin:
    payload = AuthBase.verify_token(token, scope="backoffice")
    if not payload:
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin_id = payload.get("sub")
    admin_query = select(Admin).where(Admin.id == int(admin_id))
    result = await db.execute(admin_query)
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=403, detail="Inactive admin")
    return admin


def _has_admin_permission(admin: Admin, permission: str) -> bool:
    return bool(getattr(admin, "is_root_admin", False)) or bool(getattr(admin, permission, False))


def _forbid(message: str) -> None:
    raise HTTPException(status_code=403, detail=message)


async def require_case_reviewer_admin(
    current_admin: Admin = Depends(get_current_admin),
) -> Admin:
    if not _has_admin_permission(current_admin, "can_review_cases"):
        _forbid("Not enough permissions to review cases")
    return current_admin


async def require_dataset_export_admin(
    current_admin: Admin = Depends(get_current_admin),
) -> Admin:
    if not _has_admin_permission(current_admin, "can_export_datasets"):
        _forbid("Not enough permissions to export datasets")
    return current_admin


async def require_record_delete_admin(
    current_admin: Admin = Depends(get_current_admin),
) -> Admin:
    if not _has_admin_permission(current_admin, "can_delete_records"):
        _forbid("Not enough permissions to delete records")
    return current_admin
