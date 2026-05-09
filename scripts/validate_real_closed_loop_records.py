"""Validate real closed-loop case records for Zhiqi Zhice.

The script is intentionally dependency-free so it can run on Windows locally
and on the Ubuntu server with the system Python.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


DEFAULT_CSV = Path("docs/competition/datasets/真实闭环验收记录模板.csv")

REQUIRED_COLUMNS = [
    "case_id",
    "run_id",
    "run_date",
    "environment",
    "git_commit",
    "resume_source",
    "target_position",
    "upload_status",
    "ability_diagnosis_status",
    "learning_tasks_added",
    "interview_start_status",
    "interview_rounds",
    "report_status",
    "training_review_status",
    "admin_interview_record",
    "evaluation_dataset_status",
    "ai_final_score",
    "human_score_1",
    "human_score_2",
    "human_avg",
    "score_delta",
    "main_issue",
    "status",
]

FLOW_COLUMNS = [
    "upload_status",
    "ability_diagnosis_status",
    "interview_start_status",
    "report_status",
    "training_review_status",
    "admin_interview_record",
    "evaluation_dataset_status",
]

HUMAN_SCORE_COLUMNS = ["human_score_1", "human_score_2", "human_avg", "score_delta"]

PENDING_PREFIXES = ("待",)
FAIL_KEYWORDS = ("失败", "报错", "不通过", "error", "fail", "FAIL", "Error")
PASS_KEYWORDS = ("通过", "成功", "有样本", "空态", "pass", "PASS", "success", "SUCCESS")


def is_pending(value: str | None) -> bool:
    value = (value or "").strip()
    if not value:
        return True
    return value.startswith(PENDING_PREFIXES)


def is_failed(value: str | None) -> bool:
    value = (value or "").strip()
    return any(keyword in value for keyword in FAIL_KEYWORDS)


def is_pass_like(value: str | None) -> bool:
    value = (value or "").strip()
    return any(keyword in value for keyword in PASS_KEYWORDS)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def row_has_pending(row: dict[str, str], columns: Iterable[str]) -> bool:
    return any(is_pending(row.get(column)) for column in columns)


def row_has_failure(row: dict[str, str]) -> bool:
    return any(is_failed(value) for value in row.values())


def row_flow_complete(row: dict[str, str]) -> bool:
    return all(is_pass_like(row.get(column)) for column in FLOW_COLUMNS)


def build_summary(fieldnames: list[str], rows: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")

    case_runs: dict[str, int] = defaultdict(int)
    status_counts: Counter[str] = Counter()
    pending_rows = 0
    failed_rows = 0
    complete_flow_rows = 0
    missing_human_score_rows = 0

    for index, row in enumerate(rows, start=2):
        case_id = row.get("case_id", "").strip() or f"row-{index}"
        case_runs[case_id] += 1
        status = row.get("status", "").strip() or "missing"
        status_counts[status] += 1

        if row_has_pending(row, REQUIRED_COLUMNS):
            pending_rows += 1
        if row_has_failure(row):
            failed_rows += 1
            warnings.append(f"Row {index} ({case_id}) contains a failure marker.")
        if row_flow_complete(row):
            complete_flow_rows += 1
        if row_has_pending(row, HUMAN_SCORE_COLUMNS):
            missing_human_score_rows += 1

    repeated_cases = sorted(case_id for case_id, count in case_runs.items() if count >= 3)
    pending_cases = sorted(
        row.get("case_id", "").strip() or f"row-{index}"
        for index, row in enumerate(rows, start=2)
        if row_has_pending(row, FLOW_COLUMNS + HUMAN_SCORE_COLUMNS)
    )

    summary = [
        f"records={len(rows)}",
        f"cases={len(case_runs)}",
        f"complete_flow_rows={complete_flow_rows}",
        f"pending_rows={pending_rows}",
        f"failed_rows={failed_rows}",
        f"missing_human_score_rows={missing_human_score_rows}",
        f"cases_with_3_or_more_runs={len(repeated_cases)}",
        "status_counts=" + ", ".join(f"{key}:{value}" for key, value in status_counts.items()),
    ]

    if pending_cases:
        warnings.append("Pending cases: " + ", ".join(pending_cases[:20]))
    if repeated_cases:
        warnings.append("Cases with repeated runs: " + ", ".join(repeated_cases))
    else:
        warnings.append("No case has 3 repeated runs yet.")

    return errors, summary + warnings


def write_markdown_summary(path: Path, csv_path: Path, errors: list[str], lines: list[str]) -> None:
    content = [
        "# 真实闭环验收摘要",
        "",
        f"来源 CSV：`{csv_path.as_posix()}`",
        "",
        "## 检查结果",
        "",
    ]
    if errors:
        content.extend(f"- ERROR: {line}" for line in errors)
    else:
        content.append("- schema: PASS")
    content.extend(f"- {line}" for line in lines)
    content.append("")
    path.write_text("\n".join(content), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real closed-loop case records.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV file to validate.")
    parser.add_argument("--summary", type=Path, help="Optional Markdown summary output path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when records are pending or failed.")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}")
        return 2

    fieldnames, rows = read_rows(args.csv)
    errors, lines = build_summary(fieldnames, rows)

    print(f"CSV: {args.csv}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("schema=PASS")

    for line in lines:
        print(line)

    if args.summary:
        write_markdown_summary(args.summary, args.csv, errors, lines)
        print(f"summary_written={args.summary}")

    if errors:
        return 2
    if args.strict and any("pending_rows=0" not in line for line in lines if line.startswith("pending_rows=")):
        return 1
    if args.strict and any("failed_rows=0" not in line for line in lines if line.startswith("failed_rows=")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
