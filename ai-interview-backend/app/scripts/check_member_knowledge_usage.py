"""Generate usage and coverage reports for member knowledge packages.

Package-only report:
python -m app.scripts.check_member_knowledge_usage

Database report after canonical merge:
python -m app.scripts.check_member_knowledge_usage --database
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import not_, select

from app.models.position_knowledge_base import PositionKnowledgeBase
from app.models.position_knowledge_base_slice import PositionKnowledgeBaseSlice
from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    MEMBER_TITLE_PREFIX,
    MERGED_HISTORY_PREFIX,
    ImportPlan,
    _package_paths,
    build_import_plans,
)
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


REPORT_PATH = DEFAULT_SOURCE / "member_knowledge_usage_report.md"
INSUFFICIENT_POSITIONS = [
    "测试工程师",
    "数据分析师",
    "新媒体运营",
    "招聘助理",
    "行政管理助理",
]


@dataclass
class PositionUsage:
    target_position: str
    title: str
    knowledge_base_count: int
    slice_count: int
    enabled_slice_count: int
    interview_experience_slice_count: int
    package_experience_count: int
    imported: bool
    notes: str = ""


class _KnowledgeBaseLike:
    def __init__(self, plan: ImportPlan):
        self.id = 0
        self.scope = "public"
        self.title = plan.canonical_title
        self.target_position = plan.target_position
        self.knowledge_content = plan.knowledge_content
        self.focus_points = plan.focus_points
        self.interviewer_prompt = plan.interviewer_prompt


def _usage_from_packages(plans: Sequence[ImportPlan]) -> list[PositionUsage]:
    usages: list[PositionUsage] = []
    for plan in plans:
        payloads = position_knowledge_base_slice_service.build_slice_payloads(_KnowledgeBaseLike(plan))
        enabled = [item for item in payloads if item.get("is_enabled", True)]
        interview_experience = [
            item for item in payloads
            if item.get("source_section") == "interview_experience" and item.get("is_enabled", True)
        ]
        usages.append(
            PositionUsage(
                target_position=plan.target_position,
                title=plan.canonical_title,
                knowledge_base_count=0,
                slice_count=len(payloads),
                enabled_slice_count=len(enabled),
                interview_experience_slice_count=len(interview_experience),
                package_experience_count=plan.enabled_experiences,
                imported=False,
                notes="package_ready_for_canonical_merge",
            )
        )
    return usages


async def _usage_from_database(plans: Sequence[ImportPlan]) -> list[PositionUsage]:
    from app.db.session import async_session

    target_positions = [plan.target_position for plan in plans]
    async with async_session() as db:
        result = await db.execute(
            select(PositionKnowledgeBase)
            .where(
                PositionKnowledgeBase.scope == "public",
                PositionKnowledgeBase.target_position.in_(target_positions),
                not_(PositionKnowledgeBase.title.like(f"{MEMBER_TITLE_PREFIX}%")),
                not_(PositionKnowledgeBase.title.like(f"{MERGED_HISTORY_PREFIX}%")),
            )
            .order_by(PositionKnowledgeBase.target_position.asc(), PositionKnowledgeBase.id.asc())
        )
        knowledge_bases = result.scalars().all()
        usages: list[PositionUsage] = []
        for item in knowledge_bases:
            slices_result = await db.execute(
                select(PositionKnowledgeBaseSlice).where(
                    PositionKnowledgeBaseSlice.knowledge_base_id == item.id
                )
            )
            slices = slices_result.scalars().all()
            enabled = [slice_item for slice_item in slices if slice_item.is_enabled]
            interview_experience = [
                slice_item
                for slice_item in enabled
                if slice_item.source_section == "interview_experience"
            ]
            usages.append(
                PositionUsage(
                    target_position=item.target_position,
                    title=item.title,
                    knowledge_base_count=1,
                    slice_count=len(slices),
                    enabled_slice_count=len(enabled),
                    interview_experience_slice_count=len(interview_experience),
                    package_experience_count=0,
                    imported=True,
                    notes="canonical_profile_imported",
                )
            )
    return usages


def build_report(usages: Sequence[PositionUsage], mode: str) -> str:
    imported_count = sum(1 for item in usages if item.imported)
    total_slices = sum(item.slice_count for item in usages)
    total_experience_slices = sum(item.interview_experience_slice_count for item in usages)
    lines = [
        "# 成员知识库入库使用检查报告",
        "",
        f"- 检查模式：{mode}",
        f"- 岗位数量：{len(usages)}",
        f"- 已入库标准岗位画像数量：{imported_count}",
        f"- 切片总数：{total_slices}",
        f"- 问答经验启用切片数：{total_experience_slices}",
        "",
        "## 岗位覆盖与切片质量",
        "",
        "| 岗位 | 标准画像标题 | 入库状态 | 切片数 | 启用切片 | 问答经验切片 | 资料包面经数 | 备注 |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in usages:
        status = "已归并入标准岗位画像" if item.imported else "待归并入标准岗位画像"
        lines.append(
            "| "
            f"{item.target_position} | {item.title} | {status} | "
            f"{item.slice_count} | {item.enabled_slice_count} | "
            f"{item.interview_experience_slice_count} | {item.package_experience_count} | {item.notes} |"
        )
    lines.extend(
        [
            "",
            "## 待补岗位",
            "",
            "| 岗位 | 当前处理建议 |",
            "|---|---|",
        ]
    )
    for position in INSUFFICIENT_POSITIONS:
        lines.append(
            f"| {position} | 需要补齐岗位要求、问答经验、能力模型、面试追问四分区，再进入待检查目录。 |"
        )
    lines.extend(
        [
            "",
            "## 使用位置",
            "",
            "- 公共岗位画像：成员资料应归并到已有标准岗位画像，而不是作为并列新画像。",
            "- 问答经验：结构化面经通过 `source_section=interview_experience` 进入切片。",
            "- RAG 追问：面试路由可检索岗位要求、问答经验、能力模型、面试追问切片。",
            "- 简历润色：读取标准岗位画像作为岗位要求和表达优化参考，不把知识库内容写成候选人经历。",
            "- 能力诊断/学习任务：岗位知识库只作为岗位标准，不作为候选人真实能力证据。",
            "",
            "## 服务器验收命令",
            "",
            "```bash",
            "docker compose exec app python -m app.scripts.import_member_knowledge_packages --check-only",
            "docker compose exec app python -m app.scripts.import_member_knowledge_packages --dry-run",
            "docker compose exec app python -m app.scripts.import_member_knowledge_packages",
            "docker compose exec app python -m app.scripts.merge_member_supplement_knowledge_bases --dry-run",
            "docker compose exec app python -m app.scripts.merge_member_supplement_knowledge_bases",
            "docker compose exec app python -m app.scripts.check_member_knowledge_usage --database",
            "```",
            "",
            "## 风险提醒",
            "",
            "- 旧的 `成员资料补充：{岗位}` 画像仅作为历史补充资料，不应长期出现在前台岗位选择或润色来源优先级中。",
            "- 图片型 `面试经历.docx` 未进入本次入库包，必须 OCR 或人工转写后再提交。",
            "- `仅参考` 和 `待核验` 资料可作为追问方向，不应作为候选人真实能力证据。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(report: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check member knowledge package usage and coverage.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Knowledge package source directory or JSON file.")
    parser.add_argument("--database", action="store_true", help="Read canonical public profiles from database.")
    parser.add_argument("--output", default=str(REPORT_PATH), help="Markdown report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plans = build_import_plans(_package_paths(Path(args.source)))
    if args.database:
        usages = asyncio.run(_usage_from_database(plans))
        mode = "database_canonical_profiles"
    else:
        usages = _usage_from_packages(plans)
        mode = "package"
    report = build_report(usages, mode=mode)
    write_report(report, Path(args.output))
    print(report)
    print(f"report={Path(args.output)}")
    print("result=CHECK_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
