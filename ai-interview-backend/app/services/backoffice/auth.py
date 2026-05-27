from typing import Optional, Dict
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta, UTC
from app.models.admin import Admin
from app.models.token import AdminToken
from app.core.security import AuthBase
from app.core.config import settings
from app.db.session import transaction
from app.exceptions.http_exceptions import APIException
from app.utils.email_normalization import normalize_email
import asyncio

logger = logging.getLogger(__name__)


class BackofficeAuthService(AuthBase):
    @staticmethod
    async def authenticate_admin(db: AsyncSession, email: str, password: str) -> Optional[Admin]:
        """管理员认证"""
        admin_query = select(Admin).where(Admin.email == normalize_email(email))
        result = await db.execute(admin_query)
        admin = result.scalar_one_or_none()

        if not admin:
            return None

        try:
            is_valid = await asyncio.to_thread(admin.verify_password, password)
        except Exception as exc:
            logger.exception("Admin password verify component failed")
            raise APIException(status_code=500, message="管理员密码服务暂时不可用") from exc

        if not is_valid:
            return None
        return admin

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> Dict:
        """管理员登录"""
        email = normalize_email(email)
        async with transaction(db):
            admin = await BackofficeAuthService.authenticate_admin(db, email, password)
            if not admin:
                raise APIException(status_code=400, message="Incorrect email or password")
            if not admin.is_active:
                raise APIException(status_code=400, message="Admin account is inactive")

            # 标记旧token为无效
            stmt = update(AdminToken).where(
                (AdminToken.admin_id == admin.id) &
                (AdminToken.is_active == True)
            ).values(is_active=False)
            await db.execute(stmt)

            # 生成新的access token和refresh token
            access_token = AuthBase.create_access_token(
                str(admin.id),
                scope="backoffice",  # 区分客户端和后台
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            refresh_token = AuthBase.create_refresh_token(str(admin.id))

            # 存储新的refresh token
            hashed_token = AuthBase.hash_refresh_token(refresh_token)
            token = AdminToken(
                admin_id=admin.id,
                token=hashed_token,
                expires_at=datetime.now(UTC) + timedelta(days=7),
                is_active=True
            )
            db.add(token)
            await db.flush()

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token: str) -> Dict:
        """刷新管理员token"""
        payload = AuthBase.verify_token(refresh_token, scope="refresh")
        if not payload:
            raise APIException(status_code=401, message="Invalid refresh token")

        try:
            admin_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            raise APIException(status_code=401, message="Invalid refresh token")
        token = await BackofficeAuthService._find_active_refresh_token(db, admin_id, refresh_token)

        if not token:
            raise APIException(status_code=401, message="Invalid or expired refresh token")

        token.last_used_at = datetime.now(UTC)
        await db.commit()

        access_token = AuthBase.create_access_token(
            admin_id,
            scope="backoffice",
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    @staticmethod
    async def logout(db: AsyncSession, refresh_token: str) -> None:
        """管理员登出"""
        payload = AuthBase.verify_token(refresh_token, scope="refresh")
        if not payload:
            return  # 忽略无效token

        try:
            admin_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            return
        token = await BackofficeAuthService._find_active_refresh_token(db, admin_id, refresh_token)

        if token:
            token.is_active = False
            await db.commit()

    @staticmethod
    async def _find_active_refresh_token(
        db: AsyncSession,
        admin_id: int,
        refresh_token: str,
    ) -> Optional[AdminToken]:
        now = datetime.now(UTC)
        hashed_token = AuthBase.hash_refresh_token(refresh_token)
        result = await db.execute(
            select(AdminToken).where(
                AdminToken.admin_id == admin_id,
                AdminToken.token == hashed_token,
                AdminToken.is_active.is_(True),
                AdminToken.expires_at > now,
            )
        )
        token = result.scalar_one_or_none()
        if token:
            return token

        legacy_result = await db.execute(
            select(AdminToken).where(
                AdminToken.admin_id == admin_id,
                AdminToken.is_active.is_(True),
                AdminToken.expires_at > now,
            )
        )
        for candidate in legacy_result.scalars().all():
            try:
                if AuthBase.verify_refresh_token_hash(refresh_token, candidate.token):
                    return candidate
            except Exception:
                logger.warning("Skip invalid legacy admin refresh token hash: token_id=%s", candidate.id)
        return None


backoffice_auth_service = BackofficeAuthService()
