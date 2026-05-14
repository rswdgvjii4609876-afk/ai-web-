"""Validate and import curated member knowledge packages.

Default behavior merges member submissions into the canonical public job profile
for the same target position. The older separate-profile import remains
available for audit-only rollback use.

Usage:
python -m app.scripts.import_member_knowledge_packages --check-only
python -m app.scripts.import_member_knowledge_packages --dry-run
python -m app.scripts.import_member_knowledge_packages
python -m app.scripts.import_member_knowledge_packages --mode separate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import and_, not_, select

from app.db.session import async_session
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = APP_DIR / "data" / "knowledge_packages" / "member_submissions" / "2026-05-12"
PACKAGE_VERSION = "knowledge_package_v1"
MEMBER_TITLE_PREFIX = "成员资料补充："
MERGED_HISTORY_PREFIX = "历史补充资料（已合并）："
CANONICAL_TITLE_PREFIX = "职启智评岗位画像："
ALLOWED_AUDIT_STATUSES = {"可入库", "仅参考", "待核验", "不采用"}
REQUIRED_SECTIONS = ("job_requirements", "ability_model", "followup_rules")

SECTION_KEYS = ("job_requirements", "interview_experience", "ability_model", "followup_rules", "legacy_content")
SECTION_TITLES = {
    "job_requirements": "岗位要求",
    "interview_experience": "问答经验",
    "ability_model": "能力模型",
    "followup_rules": "面试追问",
    "legacy_content": "其他内容",
}
SECTION_TITLE_TO_KEY = {value: key for key, value in SECTION_TITLES.items()}


class PackageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ImportPlan:
    package_path: Path
    target_position: str
    source_title: str
    db_title: str
    canonical_title: str
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
    question = _clean_text(experience.get("question")) or f"结构化面经{index}"
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


def split_knowledge_sections(content: str) -> dict[str, str]:
    text = _clean_text(content)
    result = {key: "" for key in SECTION_KEYS}
    if not text:
        return result

    matches = list(
        re.finditer(
            r"^#{1,4}\s*(岗位要求|问答经验|真实面试经验|面试经验|能力模型|岗位能力图谱|能力图谱|面试追问|追问规则|评分追问|其他内容)\s*$",
            text,
            flags=re.MULTILINE,
        )
    )
    if not matches:
        result["legacy_content"] = text
        return result

    before_first = text[: matches[0].start()].strip()
    if before_first:
        result["legacy_content"] = before_first

    title_aliases = {
        "真实面试经验": "问答经验",
        "面试经验": "问答经验",
        "岗位能力图谱": "能力模型",
        "能力图谱": "能力模型",
        "追问规则": "面试追问",
        "评分追问": "面试追问",
    }
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = title_aliases.get(match.group(1), match.group(1))
        key = SECTION_TITLE_TO_KEY.get(title)
        value = text[start:end].strip()
        if key:
            result[key] = "\n\n".join(part for part in [result.get(key, ""), value] if part).strip()
    return result


def compose_knowledge_sections(sections: dict[str, str]) -> str:
    parts = []
    for key in ("job_requirements", "interview_experience", "ability_model", "followup_rules"):
        content = _clean_text(sections.get(key))
        if content:
            parts.append(f"## {SECTION_TITLES[key]}\n{content}")
    legacy = _clean_text(sections.get("legacy_content"))
    if legacy:
        parts.append(f"## {SECTION_TITLES['legacy_content']}\n{legacy}")
    return "\n\n".join(parts).strip()


def _interview_blocks(text: str) -> list[str]:
    matches = list(re.finditer(r"^#{3,5}\s*(?:面经|问答|问题)\s*\d*[：:、\-\s]*(.*?)\s*$", text or "", re.MULTILINE))
    if not matches:
        return [_clean_text(text)] if _clean_text(text) else []
    blocks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append(text[match.start():end].strip())
    return [block for block in blocks if block]


def _experience_identity(block: str) -> str:
    question_match = re.search(r"真实问题[：:]\s*(.+?)\s*$", block, re.MULTILINE)
    source_match = re.search(r"来源说明[：:]\s*(.+?)\s*$", block, re.MULTILINE)
    heading_match = re.search(r"^#{3,5}\s*(?:面经|问答|问题)\s*\d*[：:、\-\s]*(.*?)\s*$", block, re.MULTILINE)
    question = _clean_text(question_match.group(1) if question_match else (heading_match.group(1) if heading_match else block[:80]))
    source = _clean_text(source_match.group(1) if source_match else "")
    normalized = re.sub(r"\s+", "", f"{question}|{source}").lower()
    return normalized


def merge_interview_experience_section(existing: str, supplement: str) -> tuple[str, int]:
    existing_blocks = _interview_blocks(existing)
    existing_ids = {_experience_identity(block) for block in existing_blocks}
    added = []
    for block in _interview_blocks(supplement):
        identity = _experience_identity(block)
        if identity and identity in existing_ids:
            continue
        existing_ids.add(identity)
        added.append(block)
    merged = "\n\n".join([*_interview_blocks(existing), *added]).strip()
    return merged, len(added)


def merge_text_section(existing: str, supplement: str, source_title: str) -> tuple[str, bool]:
    supplement = _clean_text(supplement)
    existing = _clean_text(existing)
    if not supplement:
        return existing, False
    if supplement in existing:
        return existing, False
    block = f"### 成员资料补充：{source_title}\n{supplement}"
    return "\n\n".join(part for part in [existing, block] if part).strip(), True


def merge_knowledge_content(existing_content: str, supplement_content: str, source_title: str) -> tuple[str, dict[str, int]]:
    existing = split_knowledge_sections(existing_content)
    supplement = split_knowledge_sections(supplement_content)
    stats = {"sections_added": 0, "interview_experiences_added": 0}

    for key in ("job_requirements", "ability_model", "followup_rules"):
        merged, added = merge_text_section(existing.get(key, ""), supplement.get(key, ""), source_title)
        existing[key] = merged
        if added:
            stats["sections_added"] += 1

    merged_experiences, added_count = merge_interview_experience_section(
        existing.get("interview_experience", ""),
        supplement.get("interview_experience", ""),
    )
    existing["interview_experience"] = merged_experiences
    stats["interview_experiences_added"] = added_count

    legacy, added = merge_text_section(existing.get("legacy_content", ""), supplement.get("legacy_content", ""), source_title)
    existing["legacy_content"] = legacy
    if added:
        stats["sections_added"] += 1
    return compose_knowledge_sections(existing), stats


def merge_optional_text(existing: str | None, supplement: str | None, source_title: str) -> tuple[str | None, bool]:
    existing_text = _clean_text(existing)
    supplement_text = _clean_text(supplement)
    if not supplement_text:
        return existing_text or None, False
    if supplement_text in existing_text:
        return existing_text or None, False
    block = f"成员资料补充：{source_title}\n{supplement_text}"
    return "\n\n".join(part for part in [existing_text, block] if part).strip(), True


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
                    db_title=f"{MEMBER_TITLE_PREFIX}{target_position}",
                    canonical_title=f"{CANONICAL_TITLE_PREFIX}{target_position}",
                    knowledge_content=build_knowledge_content(item),
                    focus_points=_clean_text(item.get("focus_points")),
                    interviewer_prompt=_clean_text(item.get("interviewer_prompt")),
                    total_experiences=len(experiences),
                    enabled_experiences=enabled_count,
                )
            )
    return plans


def print_plan(plans: list[ImportPlan], mode: str = "merge") -> None:
    print(f"import_mode={mode}")
    print(f"validated_packages={len({plan.package_path for plan in plans})}")
    print(f"validated_positions={len(plans)}")
    for plan in plans:
        target_title = plan.canonical_title if mode == "merge" else plan.db_title
        print(
            " - "
            f"{plan.target_position}: target_title={target_title}, "
            f"legacy_separate_title={plan.db_title}, "
            f"experiences={plan.enabled_experiences}/{plan.total_experiences}, "
            f"source={plan.package_path}"
        )


async def _find_canonical_public_profile(db, plan: ImportPlan) -> PositionKnowledgeBase | None:
    result = await db.execute(
        select(PositionKnowledgeBase)
        .where(
            PositionKnowledgeBase.scope == "public",
            PositionKnowledgeBase.target_position == plan.target_position,
            not_(PositionKnowledgeBase.title.like(f"{MEMBER_TITLE_PREFIX}%")),
            not_(PositionKnowledgeBase.title.like(f"{MERGED_HISTORY_PREFIX}%")),
        )
        .order_by(PositionKnowledgeBase.is_active.desc(), PositionKnowledgeBase.updated_at.desc())
    )
    return result.scalars().first()


async def _import_plan_as_separate_profile(db, plan: ImportPlan) -> tuple[str, int]:
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
    action = "updated"
    if item:
        for key, value in payload.items():
            setattr(item, key, value)
    else:
        item = PositionKnowledgeBase(user_id=None, admin_id=None, **payload)
        db.add(item)
        action = "created"
    await db.flush()
    await db.refresh(item)
    slices = await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)
    return action, len(slices)


async def _merge_plan_into_canonical_profile(db, plan: ImportPlan) -> tuple[str, int, dict[str, int]]:
    item = await _find_canonical_public_profile(db, plan)
    action = "merged"
    if item is None:
        item = PositionKnowledgeBase(
            user_id=None,
            admin_id=None,
            scope="public",
            title=plan.canonical_title,
            target_position=plan.target_position,
            knowledge_content="",
            focus_points=None,
            interviewer_prompt=None,
            is_active=True,
        )
        db.add(item)
        action = "created_and_merged"
        await db.flush()
        await db.refresh(item)

    merged_content, stats = merge_knowledge_content(
        existing_content=item.knowledge_content or "",
        supplement_content=plan.knowledge_content,
        source_title=plan.source_title,
    )
    item.knowledge_content = merged_content
    item.focus_points, focus_added = merge_optional_text(item.focus_points, plan.focus_points, plan.source_title)
    item.interviewer_prompt, prompt_added = merge_optional_text(
        item.interviewer_prompt,
        plan.interviewer_prompt,
        plan.source_title,
    )
    stats["focus_points_added"] = int(focus_added)
    stats["interviewer_prompt_added"] = int(prompt_added)
    item.is_active = True

    await db.flush()
    await db.refresh(item)
    slices = await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)
    return action, len(slices), stats


async def import_plans(plans: list[ImportPlan], mode: str = "merge") -> None:
    async with async_session() as db:
        created = 0
        updated = 0
        merged = 0
        total_slices = 0
        for plan in plans:
            if mode == "separate":
                action, slice_count = await _import_plan_as_separate_profile(db, plan)
                if action == "created":
                    created += 1
                else:
                    updated += 1
                print(f"imported_separate={plan.target_position}, action={action}, slices={slice_count}")
            else:
                action, slice_count, stats = await _merge_plan_into_canonical_profile(db, plan)
                if action == "created_and_merged":
                    created += 1
                else:
                    merged += 1
                print(
                    f"merged_into_canonical={plan.target_position}, action={action}, "
                    f"slices={slice_count}, stats={stats}"
                )
            total_slices += slice_count
        await db.commit()
    print(
        "member_knowledge_packages_imported: "
        f"mode={mode}, created={created}, updated={updated}, merged={merged}, slices={total_slices}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import curated member knowledge packages into public job profiles.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="JSON file or directory containing knowledge_package_v1 files.",
    )
    parser.add_argument(
        "--mode",
        choices=("merge", "separate"),
        default="merge",
        help="merge=merge into canonical profiles; separate=legacy separate supplemental profiles.",
    )
    parser.add_argument(
        "--legacy-separate",
        action="store_true",
        help="Alias for --mode separate, kept for explicit rollback/audit workflows.",
    )
    parser.add_argument("--check-only", action="store_true", help="Validate packages without connecting to database.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print import plan without database writes.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "separate" if args.legacy_separate else args.mode
    try:
        package_paths = _package_paths(Path(args.source))
        plans = build_import_plans(package_paths)
        print_plan(plans, mode=mode)
        if args.check_only:
            print("result=CHECK_PASS")
            return 0
        if args.dry_run:
            print("result=DRY_RUN_PASS")
            return 0
        asyncio.run(import_plans(plans, mode=mode))
        print("result=IMPORT_PASS")
        return 0
    except Exception as exc:
        print(f"result=FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
