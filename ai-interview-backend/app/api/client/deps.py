from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.db.session import get_db
from app.core.security import AuthBase
from app.constants.privacy import BASE_PRIVACY_CONSENT_ERROR
from app.exceptions.http_exceptions import ValidationError
from app.models.user import User
from app.services.client.privacy_consent_service import privacy_consent_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前登录用户"""
    payload = AuthBase.verify_token(token, scope="client")
    if not payload:
        raise HTTPException(
            status_code=403,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    user_query = select(User).where(User.id == int(user_id))
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=403, detail="无效的认证凭据")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="用户已被禁用")
    return user


async def require_base_privacy_consent(
    current_user: User = Depends(get_current_user),
) -> User:
    if not privacy_consent_service.has_base_consent(current_user):
        raise ValidationError(message=BASE_PRIVACY_CONSENT_ERROR)
    return current_user
