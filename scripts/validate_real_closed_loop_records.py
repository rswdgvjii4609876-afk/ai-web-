"""Validate real closed-loop case records for Zhiqi Zhice.

The script is intentionally dependency-free so it can run on Windows locally
and on the Ubuntu server with the system Python.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CSV = Path("docs/competition/datasets/真实闭环验收记录模板.csv")
DATA_CONSENT_COLUMN = "data_contribution_consent_status"

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
    DATA_CONSENT_COLUMN,
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
    DATA_CONSENT_COLUMN,
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


def build_summary(
    fieldnames: list[str], rows: list[dict[str, str]]
) -> tuple[list[str], list[str], dict[str, Any]]:
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
    data_consent_rows = 0
    missing_human_score_rows = 0
    human_scored_rows = 0

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
        if is_pass_like(row.get(DATA_CONSENT_COLUMN)):
            data_consent_rows += 1
        if row_has_pending(row, HUMAN_SCORE_COLUMNS):
            missing_human_score_rows += 1
        else:
            human_scored_rows += 1

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
        f"data_consent_rows={data_consent_rows}",
        f"pending_rows={pending_rows}",
        f"failed_rows={failed_rows}",
        f"missing_human_score_rows={missing_human_score_rows}",
        f"human_scored_rows={human_scored_rows}",
        f"cases_with_3_or_more_runs={len(repeated_cases)}",
        "status_counts=" + ", ".join(f"{key}:{value}" for key, value in status_counts.items()),
    ]

    if pending_cases:
        warnings.append("Pending cases: " + ", ".join(pending_cases[:20]))
    if repeated_cases:
        warnings.append("Cases with repeated runs: " + ", ".join(repeated_cases))
    else:
        warnings.append("No case has 3 repeated runs yet.")

    metrics = {
        "records": len(rows),
        "cases": len(case_runs),
        "complete_flow_rows": complete_flow_rows,
        "data_consent_rows": data_consent_rows,
        "pending_rows": pending_rows,
        "failed_rows": failed_rows,
        "missing_human_score_rows": missing_human_score_rows,
        "human_scored_rows": human_scored_rows,
        "cases_with_3_or_more_runs": len(repeated_cases),
    }

    return errors, summary + warnings, metrics


def build_strict_errors(
    metrics: dict[str, Any],
    min_cases: int,
    min_complete_flows: int,
    min_human_scored_rows: int,
    min_repeated_cases: int,
) -> list[str]:
    errors: list[str] = []

    if metrics["cases"] < min_cases:
        errors.append(f"cases={metrics['cases']} is below required {min_cases}.")
    if metrics["complete_flow_rows"] < min_complete_flows:
        errors.append(
            f"complete_flow_rows={metrics['complete_flow_rows']} is below required {min_complete_flows}."
        )
    if metrics["human_scored_rows"] < min_human_scored_rows:
        errors.append(
            f"human_scored_rows={metrics['human_scored_rows']} is below required {min_human_scored_rows}."
        )
    if metrics["cases_with_3_or_more_runs"] < min_repeated_cases:
        errors.append(
            "cases_with_3_or_more_runs="
            f"{metrics['cases_with_3_or_more_runs']} is below required {min_repeated_cases}."
        )
    if metrics["pending_rows"] > 0:
        errors.append(f"pending_rows={metrics['pending_rows']} must be 0 for strict validation.")
    if metrics["failed_rows"] > 0:
        errors.append(f"failed_rows={metrics['failed_rows']} must be 0 for strict validation.")

    return errors


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
    parser.add_argument("--strict", action="store_true", help="Apply acceptance thresholds.")
    parser.add_argument("--min-cases", type=int, default=5, help="Minimum case count for strict mode.")
    parser.add_argument(
        "--min-complete-flows",
        type=int,
        default=5,
        help="Minimum complete closed-loop rows for strict mode.",
    )
    parser.add_argument(
        "--min-human-scored-rows",
        type=int,
        default=5,
        help="Minimum rows with complete human scores for strict mode.",
    )
    parser.add_argument(
        "--min-repeated-cases",
        type=int,
        default=1,
        help="Minimum cases with at least 3 repeated runs for strict mode.",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}")
        return 2

    fieldnames, rows = read_rows(args.csv)
    errors, lines, metrics = build_summary(fieldnames, rows)
    strict_errors: list[str] = []
    if args.strict and not errors:
        strict_errors = build_strict_errors(
            metrics=metrics,
            min_cases=args.min_cases,
            min_complete_flows=args.min_complete_flows,
            min_human_scored_rows=args.min_human_scored_rows,
            min_repeated_cases=args.min_repeated_cases,
        )

    print(f"CSV: {args.csv}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("schema=PASS")
    if args.strict:
        print(
            "strict_targets="
            f"min_cases:{args.min_cases}, "
            f"min_complete_flows:{args.min_complete_flows}, "
            f"min_human_scored_rows:{args.min_human_scored_rows}, "
            f"min_repeated_cases:{args.min_repeated_cases}"
        )
        if strict_errors:
            for error in strict_errors:
                print(f"STRICT_ERROR: {error}")
        else:
            print("strict=PASS")

    for line in lines:
        print(line)

    if args.summary:
        write_markdown_summary(args.summary, args.csv, errors + strict_errors, lines)
        print(f"summary_written={args.summary}")

    if errors:
        return 2
    if strict_errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
