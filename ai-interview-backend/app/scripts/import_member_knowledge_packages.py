"""Validate and import curated member knowledge packages.

Usage:
python -m app.scripts.import_member_knowledge_packages --check-only
python -m app.scripts.import_member_knowledge_packages --dry-run
python -m app.scripts.import_member_knowledge_packages
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from app.db.session import async_session
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = APP_DIR / "data" / "knowledge_packages" / "member_submissions" / "2026-05-12"
PACKAGE_VERSION = "knowledge_package_v1"
ALLOWED_AUDIT_STATUSES = {"可入库", "仅参考", "待核验", "不采用"}
REQUIRED_SECTIONS = ("job_requirements", "ability_model", "followup_rules")


class PackageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ImportPlan:
    package_path: Path
    target_position: str
    source_title: str
    db_title: str
    knowledge_content: str
    focus_points: str
    interviewer_prompt: str
    total_experiences: int
    enabled_experiences: int


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise PackageValidationError(f"{path}: JSON 格式错误：{exc}") from exc


def _package_paths(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.exists():
        raise PackageValidationError(f"资料包路径不存在：{source}")
    paths = sorted(path for path in source.glob("*_knowledge_package.json") if path.is_file())
    if not paths:
        raise PackageValidationError(f"目录中没有 *_knowledge_package.json 资料包：{source}")
    return paths


def _validate_experience(path: Path, item_index: int, exp_index: int, experience: dict[str, Any]) -> str:
    question = _clean_text(experience.get("question"))
    answer_points = _clean_text(experience.get("answer_points"))
    audit_status = _clean_text(experience.get("audit_status")) or "待核验"
    if not question:
        raise PackageValidationError(f"{path}: items[{item_index}].interview_experiences[{exp_index}] 缺少 question")
    if not answer_points:
        raise PackageValidationError(
            f"{path}: items[{item_index}].interview_experiences[{exp_index}] 缺少 answer_points"
        )
    if audit_status not in ALLOWED_AUDIT_STATUSES:
        raise PackageValidationError(
            f"{path}: items[{item_index}].interview_experiences[{exp_index}] 审核状态无效：{audit_status}"
        )
    return audit_status


def _format_experience(experience: dict[str, Any], index: int) -> str:
    question = _clean_text(experience.get("question")) or f"结构化面经 {index}"
    fields = [
        ("真实问题", question),
        ("参考回答要点", _clean_text(experience.get("answer_points"))),
        ("复盘反思", _clean_text(experience.get("reflection"))),
        ("公司/场景", _clean_text(experience.get("company_context"))),
        ("考察能力", _clean_text(experience.get("ability"))),
        ("难度", _clean_text(experience.get("difficulty"))),
        ("来源说明", _clean_text(experience.get("source"))),
        ("审核状态", _clean_text(experience.get("audit_status")) or "待核验"),
    ]
    lines = [f"### 面经 {index}：{question}"]
    lines.extend(f"- {label}：{value}" for label, value in fields if value)
    return "\n".join(lines)


def build_knowledge_content(item: dict[str, Any]) -> str:
    sections = item.get("sections") or {}
    experiences = item.get("interview_experiences") or []
    experience_blocks = [
        _format_experience(experience, index)
        for index, experience in enumerate(experiences, start=1)
    ]
    if not experience_blocks:
        experience_blocks = ["- 暂无可入库结构化面经，后续需补充真实问题、参考回答、复盘反思和来源说明。"]
    return "\n\n".join(
        [
            "## 岗位要求\n" + _clean_text(sections.get("job_requirements")),
            "## 问答经验\n" + "\n\n".join(experience_blocks),
            "## 能力模型\n" + _clean_text(sections.get("ability_model")),
            "## 面试追问\n" + _clean_text(sections.get("followup_rules")),
        ]
    ).strip()


def build_import_plans(package_paths: Iterable[Path]) -> list[ImportPlan]:
    plans: list[ImportPlan] = []
    seen_positions: set[str] = set()
    for path in package_paths:
        package = _read_json(path)
        if package.get("version") != PACKAGE_VERSION:
            raise PackageValidationError(f"{path}: version 必须为 {PACKAGE_VERSION}")
        items = package.get("items")
        if not isinstance(items, list) or not items:
            raise PackageValidationError(f"{path}: items 不能为空")
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                raise PackageValidationError(f"{path}: items[{item_index}] 必须是对象")
            target_position = _clean_text(item.get("target_position"))
            source_title = _clean_text(item.get("title")) or target_position
            if not target_position:
                raise PackageValidationError(f"{path}: items[{item_index}] 缺少 target_position")
            sections = item.get("sections")
            if not isinstance(sections, dict):
                raise PackageValidationError(f"{path}: items[{item_index}] 缺少 sections")
            for section_name in REQUIRED_SECTIONS:
                if not _clean_text(sections.get(section_name)):
                    raise PackageValidationError(f"{path}: items[{item_index}] 缺少 sections.{section_name}")
            experiences = item.get("interview_experiences") or []
            if not isinstance(experiences, list):
                raise PackageValidationError(f"{path}: items[{item_index}].interview_experiences 必须是数组")
            enabled_count = 0
            for exp_index, experience in enumerate(experiences):
                if not isinstance(experience, dict):
                    raise PackageValidationError(
                        f"{path}: items[{item_index}].interview_experiences[{exp_index}] 必须是对象"
                    )
                audit_status = _validate_experience(path, item_index, exp_index, experience)
                if audit_status != "不采用":
                    enabled_count += 1
            if target_position in seen_positions:
                raise PackageValidationError(f"同一批资料包中岗位重复：{target_position}")
            seen_positions.add(target_position)
            plans.append(
                ImportPlan(
                    package_path=path,
                    target_position=target_position,
                    source_title=source_title,
                    db_title=f"成员资料补充：{target_position}",
                    knowledge_content=build_knowledge_content(item),
                    focus_points=_clean_text(item.get("focus_points")),
                    interviewer_prompt=_clean_text(item.get("interviewer_prompt")),
                    total_experiences=len(experiences),
                    enabled_experiences=enabled_count,
                )
            )
    return plans


def print_plan(plans: list[ImportPlan]) -> None:
    print(f"validated_packages={len({plan.package_path for plan in plans})}")
    print(f"validated_positions={len(plans)}")
    for plan in plans:
        print(
            " - "
            f"{plan.target_position}: title={plan.db_title}, "
            f"experiences={plan.enabled_experiences}/{plan.total_experiences}, "
            f"source={plan.package_path}"
        )


async def import_plans(plans: list[ImportPlan]) -> None:
    async with async_session() as db:
        created = 0
        updated = 0
        total_slices = 0
        for plan in plans:
            result = await db.execute(
                select(PositionKnowledgeBase).where(
                    PositionKnowledgeBase.scope == "public",
                    PositionKnowledgeBase.title == plan.db_title,
                )
            )
            item = result.scalar_one_or_none()
            payload = {
                "scope": "public",
                "title": plan.db_title,
                "target_position": plan.target_position,
                "knowledge_content": plan.knowledge_content,
                "focus_points": plan.focus_points,
                "interviewer_prompt": plan.interviewer_prompt,
                "is_active": True,
            }
            if item:
                for key, value in payload.items():
                    setattr(item, key, value)
                updated += 1
            else:
                item = PositionKnowledgeBase(user_id=None, admin_id=None, **payload)
                db.add(item)
                created += 1
            await db.flush()
            await db.refresh(item)
            slices = await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)
            total_slices += len(slices)
            print(f"imported={plan.target_position}, slices={len(slices)}")
        await db.commit()
    print(f"member_knowledge_packages_imported: created={created}, updated={updated}, slices={total_slices}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import curated member knowledge packages into public job profiles.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="JSON file or directory containing knowledge_package_v1 files.",
    )
    parser.add_argument("--check-only", action="store_true", help="Validate packages without connecting to database.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print import plan without database writes.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        package_paths = _package_paths(Path(args.source))
        plans = build_import_plans(package_paths)
        print_plan(plans)
        if args.check_only:
            print("result=CHECK_PASS")
            return 0
        if args.dry_run:
            print("result=DRY_RUN_PASS")
            return 0
        asyncio.run(import_plans(plans))
        print("result=IMPORT_PASS")
        return 0
    except Exception as exc:
        print(f"result=FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
