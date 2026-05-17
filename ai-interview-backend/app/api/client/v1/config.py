from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from app.schemas.response import ApiResponse
from app.common.release import RELEASE_CONFIG
from app.services.common.redis import redis_client
from app.db.session import get_db
from sqlalchemy import text

router = APIRouter()

_BACKEND_ROOT = Path(__file__).resolve().parents[4]


def _get_expected_alembic_heads() -> set[str]:
    alembic_config = AlembicConfig(str(_BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    return set(ScriptDirectory.from_config(alembic_config).get_heads())


def _build_migration_check(current_revisions: set[str]) -> dict:
    expected_heads = _get_expected_alembic_heads()
    missing_heads = expected_heads - current_revisions
    unexpected_revisions = current_revisions - expected_heads
    is_current = bool(expected_heads) and not missing_heads and not unexpected_revisions
    return {
        "status": "up" if is_current else "down",
        "current": sorted(current_revisions),
        "expected": sorted(expected_heads),
        "missing": sorted(missing_heads),
        "unexpected": sorted(unexpected_revisions),
    }


@router.get("/health")
async def health_check():
    """
    健康检查端点
    检查应用状态、数据库连接和Redis连接
    """
    health_status = {
        "status": "healthy",
        "services": {
            "api": "up",
            "database": "unknown",
            "redis": "unknown",
            "migrations": "unknown",
        },
        "checks": {},
    }

    # 检查数据库连接
    try:
        async for db in get_db():
            result = await db.execute(text("SELECT 1"))
            if result.scalar() == 1:
                health_status["services"]["database"] = "up"
            else:
                health_status["services"]["database"] = "down"
                health_status["status"] = "unhealthy"

            try:
                revision_result = await db.execute(text("select version_num from alembic_version"))
                current_revisions = {row[0] for row in revision_result.fetchall()}
                migration_check = _build_migration_check(current_revisions)
                health_status["checks"]["alembic"] = migration_check
                health_status["services"]["migrations"] = migration_check["status"]
                if migration_check["status"] != "up":
                    health_status["status"] = "unhealthy"
            except Exception as exc:
                health_status["checks"]["alembic"] = {
                    "status": "down",
                    "error": exc.__class__.__name__,
                    "message": "Database migrations are not at Alembic head",
                }
                health_status["services"]["migrations"] = "down"
                health_status["status"] = "unhealthy"
            break
    except Exception:
        health_status["services"]["database"] = "down"
        health_status["status"] = "unhealthy"

    # 检查Redis连接
    try:
        # 使用Redis PING命令测试连接
        await redis_client.redis.ping()
        health_status["services"]["redis"] = "up"
    except Exception:
        health_status["services"]["redis"] = "down"
        health_status["status"] = "unhealthy"

    # 如果任何服务不健康，返回503状态码
    if health_status["status"] == "unhealthy":
        return ApiResponse.failed(
            message="Service unhealthy",
            body_code=503,
            http_code=503,
            data=health_status
        )

    return ApiResponse.success(data=health_status)


@router.get("/release")
async def get_release_config():
    return ApiResponse.success(data=RELEASE_CONFIG)
    

