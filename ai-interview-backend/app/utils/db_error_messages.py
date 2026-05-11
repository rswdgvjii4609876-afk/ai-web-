from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError


MIGRATION_HINT = "数据库迁移未完成，请执行 alembic upgrade head 后重启服务。"


def is_schema_error(exc: Exception) -> bool:
    text = " ".join(
        str(part)
        for part in (
            exc,
            getattr(exc, "orig", ""),
            getattr(exc, "statement", ""),
        )
        if part
    ).lower()
    return any(
        marker in text
        for marker in (
            "undefinedcolumn",
            "undefinedtable",
            "does not exist",
            "no such table",
            "no such column",
            "learning_tasks",
            "training_reviews",
            "learning_route_stages",
        )
    )


def user_facing_db_error(exc: SQLAlchemyError) -> str:
    if is_schema_error(exc):
        return MIGRATION_HINT
    return "数据库读写失败，请管理员查看后端日志中的第一条数据库异常。"
