"""Generate usage and coverage reports for imported member knowledge packages.

Package-only report:
python -m app.scripts.check_member_knowledge_usage

Database report after import:
python -m app.scripts.check_member_knowledge_usage --database
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import select

from app.models.position_knowledge_base import PositionKnowledgeBase
from app.models.position_knowledge_base_slice import PositionKnowledgeBaseSlice
from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    ImportPlan,
    _package_paths,
    build_import_plans,
)
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


REPORT_PATH = DEFAULT_SOURCE / "member_knowledge_usage_report.md"
MEMBER_TITLE_PREFIX = "成员资料补充："
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
        self.title = plan.db_title
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
                title=plan.db_title,
                knowledge_base_count=0,
                slice_count=len(payloads),
                enabled_slice_count=len(enabled),
                interview_experience_slice_count=len(interview_experience),
                package_experience_count=plan.enabled_experiences,
                imported=False,
                notes="package_ready",
            )
        )
    return usages


async def _usage_from_database() -> list[PositionUsage]:
    from app.db.session import async_session

    async with async_session() as db:
        result = await db.execute(
            select(PositionKnowledgeBase)
            .where(
                PositionKnowledgeBase.scope == "public",
                PositionKnowledgeBase.title.like(f"{MEMBER_TITLE_PREFIX}%"),
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
                    notes="database_imported",
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
        f"- 已入库岗位数量：{imported_count}",
        f"- 切片总数：{total_slices}",
        f"- 问答经验启用切片数：{total_experience_slices}",
        "",
        "## 岗位覆盖与切片质量",
        "",
        "| 岗位 | 画像标题 | 入库状态 | 切片数 | 启用切片 | 问答经验切片 | 资料包面经数 | 备注 |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in usages:
        status = "已入库" if item.imported else "待正式入库"
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
            "- 公共岗位画像：后台可查看 `成员资料补充：{岗位}`。",
            "- RAG 追问：面试路由可检索岗位要求、问答经验、能力模型、面试追问切片。",
            "- 简历润色：可读取同岗位公共知识库作为岗位要求和表达优化参考。",
            "- 能力诊断/学习任务：只把岗位知识库作为岗位标准，不把它当作候选人真实经历。",
            "",
            "## 服务器验收命令",
            "",
            "```bash",
            "docker compose exec app python -m app.scripts.import_member_knowledge_packages --check-only",
            "docker compose exec app python -m app.scripts.import_member_knowledge_packages --dry-run",
            "docker compose exec app python -m app.scripts.import_member_knowledge_packages",
            "docker compose exec app python -m app.scripts.check_member_knowledge_usage --database",
            "```",
            "",
            "## 风险提醒",
            "",
            "- 图片型 `面试经历.docx` 未进入本次入库包，必须 OCR 或人工转写后再提交。",
            "- 本批资料是第一批成员资料补充，不覆盖原有公共岗位画像。",
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
    parser.add_argument("--database", action="store_true", help="Read imported member knowledge bases from database.")
    parser.add_argument("--output", default=str(REPORT_PATH), help="Markdown report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.database:
        usages = asyncio.run(_usage_from_database())
        mode = "database"
    else:
        plans = build_import_plans(_package_paths(Path(args.source)))
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
