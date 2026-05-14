"""Merge legacy member supplemental public profiles into canonical job profiles.

This script fixes the temporary stage-126 import strategy where member
submissions were stored as parallel public profiles named
``成员资料补充：{岗位}``. It backs up affected rows, merges their four Markdown
sections into the canonical profile for the same target position, rebuilds
slices, and deactivates the legacy supplemental row.

Usage:
python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run
python -m app.scripts.merge_member_supplement_knowledge_bases
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import not_, select

from app.db.session import async_session
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    CANONICAL_TITLE_PREFIX,
    MEMBER_TITLE_PREFIX,
    MERGED_HISTORY_PREFIX,
    merge_knowledge_content,
    merge_optional_text,
)
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


BACKUP_DIR = DEFAULT_SOURCE / "backups"


def _serialize_kb(item: PositionKnowledgeBase) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "target_position": item.target_position,
        "scope": item.scope,
        "is_active": item.is_active,
        "knowledge_content": item.knowledge_content,
        "focus_points": item.focus_points,
        "interviewer_prompt": item.interviewer_prompt,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


async def _find_canonical(db, supplement: PositionKnowledgeBase) -> PositionKnowledgeBase | None:
    result = await db.execute(
        select(PositionKnowledgeBase)
        .where(
            PositionKnowledgeBase.scope == "public",
            PositionKnowledgeBase.target_position == supplement.target_position,
            not_(PositionKnowledgeBase.title.like(f"{MEMBER_TITLE_PREFIX}%")),
            not_(PositionKnowledgeBase.title.like(f"{MERGED_HISTORY_PREFIX}%")),
            PositionKnowledgeBase.id != supplement.id,
        )
        .order_by(PositionKnowledgeBase.is_active.desc(), PositionKnowledgeBase.updated_at.desc())
    )
    return result.scalars().first()


async def merge_legacy_supplements(dry_run: bool = False) -> dict[str, Any]:
    async with async_session() as db:
        result = await db.execute(
            select(PositionKnowledgeBase)
            .where(
                PositionKnowledgeBase.scope == "public",
                PositionKnowledgeBase.title.like(f"{MEMBER_TITLE_PREFIX}%"),
            )
            .order_by(PositionKnowledgeBase.target_position.asc(), PositionKnowledgeBase.id.asc())
        )
        supplements = result.scalars().all()
        operations: list[dict[str, Any]] = []
        backup_rows: list[dict[str, Any]] = []

        for supplement in supplements:
            canonical = await _find_canonical(db, supplement)
            created_canonical = False
            if canonical is None:
                canonical = PositionKnowledgeBase(
                    user_id=None,
                    admin_id=None,
                    scope="public",
                    title=f"{CANONICAL_TITLE_PREFIX}{supplement.target_position}",
                    target_position=supplement.target_position,
                    knowledge_content="",
                    focus_points=None,
                    interviewer_prompt=None,
                    is_active=True,
                )
                if not dry_run:
                    db.add(canonical)
                    await db.flush()
                    await db.refresh(canonical)
                created_canonical = True

            operation = {
                "supplement_id": supplement.id,
                "supplement_title": supplement.title,
                "target_position": supplement.target_position,
                "canonical_id": canonical.id,
                "canonical_title": canonical.title,
                "created_canonical": created_canonical,
            }
            backup_rows.extend([_serialize_kb(supplement), _serialize_kb(canonical)])

            if not dry_run:
                merged_content, stats = merge_knowledge_content(
                    existing_content=canonical.knowledge_content or "",
                    supplement_content=supplement.knowledge_content or "",
                    source_title=supplement.title or supplement.target_position,
                )
                canonical.knowledge_content = merged_content
                canonical.focus_points, focus_added = merge_optional_text(
                    canonical.focus_points,
                    supplement.focus_points,
                    supplement.title or supplement.target_position,
                )
                canonical.interviewer_prompt, prompt_added = merge_optional_text(
                    canonical.interviewer_prompt,
                    supplement.interviewer_prompt,
                    supplement.title or supplement.target_position,
                )
                canonical.is_active = True
                supplement.is_active = False
                supplement.title = f"{MERGED_HISTORY_PREFIX}{supplement.target_position}"
                await db.flush()
                await db.refresh(canonical)
                await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, canonical)
                operation["stats"] = {
                    **stats,
                    "focus_points_added": int(focus_added),
                    "interviewer_prompt_added": int(prompt_added),
                }
            operations.append(operation)

        if not dry_run and operations:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            backup_path = BACKUP_DIR / f"member_supplement_merge_{datetime.now():%Y%m%d_%H%M%S}.json"
            backup_path.write_text(
                json.dumps(
                    {
                        "version": "member_supplement_merge_backup_v1",
                        "generated_at": datetime.now().isoformat(),
                        "rows": backup_rows,
                        "operations": operations,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            await db.commit()
        elif not dry_run:
            await db.commit()

        return {
            "dry_run": dry_run,
            "supplement_count": len(supplements),
            "operation_count": len(operations),
            "operations": operations,
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge legacy member supplemental profiles into canonical profiles.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned merge operations without database writes.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = asyncio.run(merge_legacy_supplements(dry_run=args.dry_run))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("result=DRY_RUN_PASS" if args.dry_run else "result=MERGE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
