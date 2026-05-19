"""Audit production public job profiles before/after member supplement merge.

This is a read-only server-side check. It does not export resumes, interviews,
users, or raw evaluation samples.

Usage:
python -m app.scripts.audit_position_knowledge_sync
python -m app.scripts.audit_position_knowledge_sync --strict
python -m app.scripts.audit_position_knowledge_sync --output /app/logs/position_knowledge_audit.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.session import async_session
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.models.position_knowledge_base_slice import PositionKnowledgeBaseSlice
from app.scripts.import_member_knowledge_packages import (
    CANONICAL_TITLE_PREFIX,
    MEMBER_TITLE_PREFIX,
    MERGED_HISTORY_PREFIX,
    normalize_target_position,
)


def _is_member_supplement(item: PositionKnowledgeBase) -> bool:
    return bool(item.title and item.title.startswith(MEMBER_TITLE_PREFIX))


def _is_history_supplement(item: PositionKnowledgeBase) -> bool:
    return bool(item.title and item.title.startswith(MERGED_HISTORY_PREFIX))


def _is_standard_public_profile(item: PositionKnowledgeBase) -> bool:
    return not _is_member_supplement(item) and not _is_history_supplement(item)


async def audit_position_knowledge_sync() -> dict[str, Any]:
    async with async_session() as db:
        result = await db.execute(
            select(PositionKnowledgeBase)
            .where(PositionKnowledgeBase.scope == "public")
            .order_by(PositionKnowledgeBase.target_position.asc(), PositionKnowledgeBase.id.asc())
        )
        items = result.scalars().all()

        slice_result = await db.execute(select(PositionKnowledgeBaseSlice))
        slices = slice_result.scalars().all()

    slice_counts: dict[int, dict[str, int]] = {}
    for slice_item in slices:
        counts = slice_counts.setdefault(
            slice_item.knowledge_base_id,
            {"total": 0, "enabled": 0, "interview_experience": 0},
        )
        counts["total"] += 1
        if slice_item.is_enabled:
            counts["enabled"] += 1
            if slice_item.source_section == "interview_experience":
                counts["interview_experience"] += 1

    standard_by_position: dict[str, list[PositionKnowledgeBase]] = {}
    active_member_supplements: list[PositionKnowledgeBase] = []
    history_supplements: list[PositionKnowledgeBase] = []
    rows: list[dict[str, Any]] = []

    for item in items:
        counts = slice_counts.get(item.id, {"total": 0, "enabled": 0, "interview_experience": 0})
        category = "standard"
        if _is_member_supplement(item):
            category = "member_supplement"
            if item.is_active:
                active_member_supplements.append(item)
        elif _is_history_supplement(item):
            category = "history_supplement"
            history_supplements.append(item)
        elif item.is_active:
            standard_by_position.setdefault(normalize_target_position(item.target_position), []).append(item)

        rows.append(
            {
                "id": item.id,
                "title": item.title,
                "target_position": item.target_position,
                "normalized_target_position": normalize_target_position(item.target_position),
                "is_active": bool(item.is_active),
                "category": category,
                "slice_count": counts["total"],
                "enabled_slice_count": counts["enabled"],
                "interview_experience_slice_count": counts["interview_experience"],
            }
        )

    duplicate_active_standard_profiles = [
        {
            "normalized_target_position": target_position,
            "profile_count": len(profiles),
            "profiles": [{"id": item.id, "title": item.title} for item in profiles],
        }
        for target_position, profiles in sorted(standard_by_position.items())
        if len(profiles) > 1
    ]

    canonical_mismatches = [
        {
            "id": item.id,
            "title": item.title,
            "target_position": item.target_position,
            "expected_title": f"{CANONICAL_TITLE_PREFIX}{normalize_target_position(item.target_position)}",
        }
        for profiles in standard_by_position.values()
        for item in profiles
        if item.title != f"{CANONICAL_TITLE_PREFIX}{normalize_target_position(item.target_position)}"
    ]

    blockers = []
    if active_member_supplements:
        blockers.append(
            {
                "type": "active_member_supplements",
                "count": len(active_member_supplements),
                "items": [{"id": item.id, "title": item.title} for item in active_member_supplements],
            }
        )
    if duplicate_active_standard_profiles:
        blockers.append(
            {
                "type": "duplicate_active_standard_profiles",
                "count": len(duplicate_active_standard_profiles),
                "items": duplicate_active_standard_profiles,
            }
        )
    if canonical_mismatches:
        blockers.append(
            {
                "type": "canonical_title_mismatch",
                "count": len(canonical_mismatches),
                "items": canonical_mismatches,
            }
        )

    return {
        "version": "position_knowledge_sync_audit_v1",
        "summary": {
            "public_profile_count": len(items),
            "active_standard_profile_count": sum(1 for item in items if item.is_active and _is_standard_public_profile(item)),
            "active_member_supplement_count": len(active_member_supplements),
            "history_supplement_count": len(history_supplements),
            "blocker_count": len(blockers),
        },
        "blockers": blockers,
        "rows": rows,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit public position knowledge profile synchronization.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when blockers are found.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = asyncio.run(audit_position_knowledge_sync())
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        print(f"report={output_path}")
    if args.strict and report["summary"]["blocker_count"]:
        print("result=AUDIT_FAIL")
        return 1
    print("result=AUDIT_PASS" if not report["summary"]["blocker_count"] else "result=AUDIT_WARN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
