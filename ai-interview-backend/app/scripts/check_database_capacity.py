"""Read-only PostgreSQL capacity check for deployment and concurrency tuning.

Usage:
    python -m app.scripts.check_database_capacity
    python -m app.scripts.check_database_capacity --output /tmp/db_capacity.md
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import async_session


KEY_TABLES = [
    "users",
    "resumes",
    "interviews",
    "interview_messages",
    "position_knowledge_bases",
    "position_knowledge_base_slices",
    "learning_tasks",
    "training_reviews",
    "learning_route_stages",
    "admins",
]


@dataclass(frozen=True)
class CapacityReport:
    generated_at: str
    database_name: str
    max_connections: int
    current_connections: int
    active_connections: int
    connection_usage_ratio: float
    configured_pool_capacity: int
    app_pool_capacity: int
    celery_pool_capacity: int
    scheduler_pool_capacity: int
    connection_states: list[dict[str, Any]]
    key_table_counts: list[dict[str, Any]]
    largest_tables: list[dict[str, Any]]
    long_running_queries: list[dict[str, Any]]
    warnings: list[str]
    suggestions: list[str]


def _row_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in rows]


async def _scalar(db, query: str) -> Any:
    result = await db.execute(text(query))
    return result.scalar()


async def _fetch_all(db, query: str) -> list[dict[str, Any]]:
    result = await db.execute(text(query))
    return _row_dicts(result.fetchall())


async def _table_exists(db, table_name: str) -> bool:
    result = await db.execute(text("select to_regclass(:table_name)"), {"table_name": table_name})
    return result.scalar() is not None


async def _key_table_counts(db) -> list[dict[str, Any]]:
    counts: list[dict[str, Any]] = []
    for table_name in KEY_TABLES:
        if not await _table_exists(db, table_name):
            counts.append({"table_name": table_name, "row_count": "missing"})
            continue
        result = await db.execute(text(f"select count(*) from {table_name}"))
        counts.append({"table_name": table_name, "row_count": int(result.scalar() or 0)})
    return counts


def _build_warnings_and_suggestions(
    *,
    max_connections: int,
    current_connections: int,
    active_connections: int,
    configured_pool_capacity: int,
    long_running_queries: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    suggestions: list[str] = []
    usage_ratio = current_connections / max_connections if max_connections else 0

    if configured_pool_capacity >= max_connections * 0.8:
        warnings.append(
            "应用理论连接池容量接近或超过数据库 max_connections 的 80%，高并发时可能抢占连接。"
        )
        suggestions.append("优先降低 UVICORN_WORKERS、CELERY_WORKER_CONCURRENCY、DB_POOL_SIZE 或 DB_MAX_OVERFLOW。")
    if usage_ratio >= 0.8:
        warnings.append("当前数据库连接数已超过 max_connections 的 80%。")
        suggestions.append("短期降低连接池和 worker；长期考虑 PgBouncer 或云数据库连接池。")
    elif usage_ratio >= 0.6:
        warnings.append("当前数据库连接数已超过 max_connections 的 60%，需要持续观察。")
        suggestions.append("压测前先确认 Celery、app workers 和后台脚本不会同时放大连接数。")
    if active_connections > max(5, current_connections // 2):
        warnings.append("活跃连接占比较高，可能存在慢查询或长事务。")
        suggestions.append("查看长运行查询并优化对应业务链路。")
    if long_running_queries:
        warnings.append("检测到运行超过 5 秒的非空闲查询。")
        suggestions.append("优先分析长查询来源，再决定是否补索引或拆分任务。")
    if not warnings:
        suggestions.append("当前连接容量未见明显风险；多人测试前保持小连接池并观察日志。")
    return warnings, suggestions


async def collect_capacity_report() -> CapacityReport:
    per_process_pool_capacity = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    app_pool_capacity = settings.UVICORN_WORKERS * per_process_pool_capacity
    celery_pool_capacity = (
        settings.CELERY_WORKER_REPLICAS
        * settings.CELERY_WORKER_CONCURRENCY
        * per_process_pool_capacity
    )
    scheduler_pool_capacity = settings.DB_SCHEDULER_POOL_SIZE + settings.DB_SCHEDULER_MAX_OVERFLOW
    configured_pool_capacity = app_pool_capacity + celery_pool_capacity + scheduler_pool_capacity

    async with async_session() as db:
        database_name = await _scalar(db, "select current_database()")
        max_connections = int(await _scalar(db, "show max_connections") or 0)
        current_connections = int(
            await _scalar(
                db,
                "select count(*) from pg_stat_activity where datname = current_database()",
            )
            or 0
        )
        active_connections = int(
            await _scalar(
                db,
                """
                select count(*)
                from pg_stat_activity
                where datname = current_database()
                  and state = 'active'
                """,
            )
            or 0
        )
        connection_states = await _fetch_all(
            db,
            """
            select coalesce(state, 'unknown') as state, count(*)::int as count
            from pg_stat_activity
            where datname = current_database()
            group by coalesce(state, 'unknown')
            order by count desc, state asc
            """,
        )
        long_running_queries = await _fetch_all(
            db,
            """
            select pid,
                   coalesce(state, 'unknown') as state,
                   round(extract(epoch from (now() - query_start)))::int as duration_seconds,
                   left(regexp_replace(query, '\\s+', ' ', 'g'), 160) as query_preview
            from pg_stat_activity
            where datname = current_database()
              and query_start is not null
              and state <> 'idle'
              and now() - query_start > interval '5 seconds'
            order by query_start asc
            limit 10
            """,
        )
        largest_tables = await _fetch_all(
            db,
            """
            select relname as table_name,
                   pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                   n_live_tup::bigint as estimated_live_rows,
                   n_dead_tup::bigint as estimated_dead_rows,
                   seq_scan::bigint as seq_scan,
                   idx_scan::bigint as idx_scan
            from pg_stat_user_tables
            order by pg_total_relation_size(relid) desc
            limit 10
            """,
        )
        key_table_counts = await _key_table_counts(db)

    usage_ratio = current_connections / max_connections if max_connections else 0
    warnings, suggestions = _build_warnings_and_suggestions(
        max_connections=max_connections,
        current_connections=current_connections,
        active_connections=active_connections,
        configured_pool_capacity=configured_pool_capacity,
        long_running_queries=long_running_queries,
    )
    return CapacityReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        database_name=str(database_name),
        max_connections=max_connections,
        current_connections=current_connections,
        active_connections=active_connections,
        connection_usage_ratio=usage_ratio,
        configured_pool_capacity=configured_pool_capacity,
        app_pool_capacity=app_pool_capacity,
        celery_pool_capacity=celery_pool_capacity,
        scheduler_pool_capacity=scheduler_pool_capacity,
        connection_states=connection_states,
        key_table_counts=key_table_counts,
        largest_tables=largest_tables,
        long_running_queries=long_running_queries,
        warnings=warnings,
        suggestions=suggestions,
    )


def _table(headers: list[str], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_无数据_\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines) + "\n"


def render_markdown(report: CapacityReport) -> str:
    percent = f"{report.connection_usage_ratio * 100:.1f}%"
    lines = [
        "# PostgreSQL 数据库容量自检报告",
        "",
        f"- 生成时间 UTC：`{report.generated_at}`",
        f"- 数据库：`{report.database_name}`",
        f"- PostgreSQL max_connections：`{report.max_connections}`",
        f"- 当前连接数：`{report.current_connections}`（{percent}）",
        f"- 当前 active 连接数：`{report.active_connections}`",
        f"- 当前配置的应用理论连接容量：`{report.configured_pool_capacity}`",
        f"- Uvicorn workers：`{settings.UVICORN_WORKERS}`",
        f"- App connection budget: `{report.app_pool_capacity}`",
        f"- Celery connection budget: `replicas={settings.CELERY_WORKER_REPLICAS}`, `concurrency={settings.CELERY_WORKER_CONCURRENCY}`, `connections={report.celery_pool_capacity}`",
        f"- 主连接池：`pool_size={settings.DB_POOL_SIZE}`，`max_overflow={settings.DB_MAX_OVERFLOW}`",
        f"- Scheduler connection budget: `{report.scheduler_pool_capacity}`",
        f"- 调度连接池：`pool_size={settings.DB_SCHEDULER_POOL_SIZE}`，`max_overflow={settings.DB_SCHEDULER_MAX_OVERFLOW}`",
        "",
        "## 连接状态",
        "",
        _table(["state", "count"], report.connection_states),
        "## 核心表行数",
        "",
        _table(["table_name", "row_count"], report.key_table_counts),
        "## 最大表概览",
        "",
        _table(
            [
                "table_name",
                "total_size",
                "estimated_live_rows",
                "estimated_dead_rows",
                "seq_scan",
                "idx_scan",
            ],
            report.largest_tables,
        ),
        "## 长运行查询（超过 5 秒）",
        "",
        _table(["pid", "state", "duration_seconds", "query_preview"], report.long_running_queries),
        "## 风险提示",
        "",
    ]
    if report.warnings:
        lines.extend(f"- {item}" for item in report.warnings)
    else:
        lines.append("- 未发现明显数据库连接容量风险。")
    lines.extend(["", "## 建议", ""])
    lines.extend(f"- {item}" for item in report.suggestions)
    lines.append("")
    return "\n".join(lines)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Read-only PostgreSQL capacity check.")
    parser.add_argument("--output", type=str, default="", help="Optional markdown output path.")
    args = parser.parse_args()
    try:
        report = await collect_capacity_report()
    except ModuleNotFoundError as exc:
        missing_name = getattr(exc, "name", "") or str(exc)
        print("数据库容量检查失败：当前 Python 环境缺少数据库驱动依赖。")
        print(f"缺少模块：{missing_name}")
        print("建议：在后端虚拟环境安装 requirements.txt，或在 Docker app 容器内执行该脚本。")
        return 1
    except SQLAlchemyError as exc:
        print("数据库容量检查失败：无法连接或读取 PostgreSQL。")
        print(f"建议：确认数据库容器正常、环境变量正确，并已执行 alembic upgrade head。")
        print(f"原始错误：{exc.__class__.__name__}: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - protects CLI readability.
        print("数据库容量检查失败：出现未预期错误。")
        print(f"原始错误：{exc.__class__.__name__}: {exc}")
        return 1

    output = render_markdown(report)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"数据库容量报告已写入：{output_path}")
    else:
        print(output)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
