"""Append a real closed-loop validation record.

The script appends one standard row to docs/competition/datasets/真实闭环验收记录模板.csv.
It is intentionally dependency-free and uses the existing CSV header as the
source of truth, so new columns can be added later without changing this script.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path


DEFAULT_CSV = Path("docs/competition/datasets/真实闭环验收记录模板.csv")

DEFAULTS = {
    "run_date": lambda: date.today().isoformat(),
    "environment": "server",
    "git_commit": "待填",
    "user_account": "待填",
    "resume_source": "待填",
    "target_position": "待填",
    "model_provider": "待填",
    "model_name": "待填",
    "upload_status": "待跑测",
    "ability_diagnosis_status": "待跑测",
    "top_gaps": "待跑测",
    "learning_tasks_added": "待跑测",
    "interview_start_status": "待跑测",
    "interview_rounds": "待跑测",
    "report_status": "待跑测",
    "training_review_status": "待跑测",
    "admin_interview_record": "待跑测",
    "evaluation_dataset_status": "待跑测",
    "ai_final_score": "待跑测",
    "human_score_1": "待评分",
    "human_score_2": "待评分",
    "human_avg": "待计算",
    "score_delta": "待计算",
    "main_issue": "待分析",
    "log_or_screenshot": "待补链接",
    "status": "待跑测",
}


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def next_run_id(rows: list[dict[str, str]], case_id: str) -> str:
    max_run = 0
    for row in rows:
        if row.get("case_id", "").strip() != case_id:
            continue
        try:
            max_run = max(max_run, int(row.get("run_id", "0").strip()))
        except ValueError:
            continue
    return str(max_run + 1)


def parse_setters(values: list[str], fieldnames: list[str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    valid_fields = set(fieldnames)
    for item in values:
        if "=" not in item:
            raise ValueError(f"--set requires column=value, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if key not in valid_fields:
            raise ValueError(f"Unknown CSV column: {key}")
        updates[key] = value.strip()
    return updates


def build_row(
    fieldnames: list[str],
    rows: list[dict[str, str]],
    case_id: str,
    run_id: str | None,
    updates: dict[str, str],
) -> dict[str, str]:
    row = {field: "" for field in fieldnames}
    for field in fieldnames:
        default = DEFAULTS.get(field, "待填")
        row[field] = default() if callable(default) else default

    row["case_id"] = case_id
    row["run_id"] = run_id or next_run_id(rows, case_id)
    row.update(updates)
    return row


def append_row(path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a real closed-loop validation record.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV file to append to.")
    parser.add_argument("--case-id", required=True, help="Case id, for example R1.")
    parser.add_argument("--run-id", help="Run id. Defaults to next run for the case.")
    parser.add_argument(
        "--set",
        dest="setters",
        action="append",
        default=[],
        help="Set a CSV column value, for example --set target_position=产品助理.",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}")
        return 2

    fieldnames, rows = read_rows(args.csv)
    if not fieldnames:
        print(f"ERROR: CSV header is missing: {args.csv}")
        return 2
    if "case_id" not in fieldnames or "run_id" not in fieldnames:
        print("ERROR: CSV must contain case_id and run_id columns.")
        return 2

    try:
        updates = parse_setters(args.setters, fieldnames)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    row = build_row(fieldnames, rows, args.case_id.strip(), args.run_id, updates)
    append_row(args.csv, fieldnames, row)

    print(f"appended=1")
    print(f"csv={args.csv}")
    print(f"case_id={row['case_id']}")
    print(f"run_id={row['run_id']}")
    print(f"status={row.get('status', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
