"""Validate stage 138 C1/C2/C3 real closed-loop completion.

This checker is narrower than validate_real_closed_loop_records.py. The
generic checker validates the full CSV schema and long-term thresholds. This
script answers the stage 138 release question: have the three representative
server cases actually completed the product loop and human scoring?
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path("docs/competition/datasets/真实闭环验收记录模板.csv")
DEFAULT_REQUIRED_CASES = {
    "R1": "产品助理/产品经理实习生",
    "R2": "Python后端开发工程师",
    "R3": "人力资源专员",
}

DATA_CONSENT_COLUMN = "data_contribution_consent_status"

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
HUMAN_SCORE_COLUMNS = ["human_score_1", "human_score_2", "human_avg"]
REQUIRED_COLUMNS = [
    "case_id",
    "run_id",
    "target_position",
    "top_gaps",
    "learning_tasks_added",
    "interview_rounds",
    "status",
    *FLOW_COLUMNS,
    *HUMAN_SCORE_COLUMNS,
]

PENDING_MARKERS = ("待", "未", "pending", "PENDING", "")
FAIL_MARKERS = ("失败", "报错", "不通过", "error", "fail", "FAIL", "Error")
PASS_MARKERS = ("成功", "通过", "空态", "有样本", "pass", "PASS", "success", "SUCCESS")


@dataclass(frozen=True)
class CaseCheck:
    case_id: str
    expected_position: str
    run_id: str
    target_position: str
    result: str
    reason: str
    flow_complete: bool
    data_consent_ok: bool
    learning_tasks_ok: bool
    interview_rounds_ok: bool
    human_scored: bool
    row: dict[str, str]


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def is_pending(value: str | None) -> bool:
    normalized = (value or "").strip()
    if not normalized:
        return True
    return any(normalized.startswith(marker) for marker in PENDING_MARKERS if marker)


def is_failed(value: str | None) -> bool:
    normalized = (value or "").strip()
    return any(marker in normalized for marker in FAIL_MARKERS)


def is_pass_like(value: str | None) -> bool:
    normalized = (value or "").strip()
    return bool(normalized) and any(marker in normalized for marker in PASS_MARKERS)


def parse_number(value: str | None) -> float | None:
    normalized = (value or "").strip()
    if not normalized or is_pending(normalized):
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    return int(number)


def latest_case_row(rows: list[dict[str, str]], case_id: str) -> dict[str, str] | None:
    candidates = [row for row in rows if row.get("case_id") == case_id]
    if not candidates:
        return None

    def key(row: dict[str, str]) -> tuple[int, int]:
        try:
            run_id = int(row.get("run_id", "0"))
        except ValueError:
            run_id = 0
        return (run_id, candidates.index(row))

    return sorted(candidates, key=key)[-1]


def check_case(case_id: str, expected_position: str, rows: list[dict[str, str]]) -> CaseCheck:
    row = latest_case_row(rows, case_id)
    if row is None:
        return CaseCheck(
            case_id=case_id,
            expected_position=expected_position,
            run_id="missing",
            target_position="",
            result="FAIL",
            reason="缺少该案例记录",
            flow_complete=False,
            data_consent_ok=False,
            learning_tasks_ok=False,
            interview_rounds_ok=False,
            human_scored=False,
            row={},
        )

    flow_complete = all(is_pass_like(row.get(column)) for column in FLOW_COLUMNS)
    data_consent_ok = is_pass_like(row.get(DATA_CONSENT_COLUMN)) and not is_failed(
        row.get(DATA_CONSENT_COLUMN)
    )
    learning_tasks_ok = (parse_int(row.get("learning_tasks_added")) or 0) >= 1
    interview_rounds_ok = (parse_int(row.get("interview_rounds")) or 0) >= 3
    human_scored = all(parse_number(row.get(column)) is not None for column in HUMAN_SCORE_COLUMNS)
    top_gaps_recorded = not is_pending(row.get("top_gaps")) and not is_failed(row.get("top_gaps"))
    status_ok = is_pass_like(row.get("status")) and not is_failed(row.get("status"))
    target_position = row.get("target_position", "")
    position_ok = bool(target_position) and (
        expected_position in target_position or target_position in expected_position
    )
    has_failure_marker = any(is_failed(value) for value in row.values())

    failures: list[str] = []
    if not position_ok:
        failures.append(f"目标岗位不匹配：{target_position or '空'}")
    if not flow_complete:
        bad_columns = [
            column
            for column in FLOW_COLUMNS
            if not is_pass_like(row.get(column)) or is_failed(row.get(column))
        ]
        failures.append("流程字段未完成：" + ", ".join(bad_columns))
    if not top_gaps_recorded:
        failures.append("未记录能力差距 top_gaps")
    if not learning_tasks_ok:
        failures.append("学习任务数量小于 1")
    if not interview_rounds_ok:
        failures.append("面试轮数小于 3")
    if not human_scored:
        failures.append("人工评分不完整")
    if not status_ok:
        failures.append(f"案例状态未通过：{row.get('status') or '空'}")
    if has_failure_marker:
        failures.append("记录中包含失败标记")

    result = "FAIL" if failures else "PASS"
    return CaseCheck(
        case_id=case_id,
        expected_position=expected_position,
        run_id=row.get("run_id", ""),
        target_position=target_position,
        result=result,
        reason="；".join(failures) if failures else "完整闭环和人工评分已记录",
        flow_complete=flow_complete,
        data_consent_ok=data_consent_ok,
        learning_tasks_ok=learning_tasks_ok,
        interview_rounds_ok=interview_rounds_ok,
        human_scored=human_scored,
        row=row,
    )


def build_checks(rows: list[dict[str, str]]) -> list[CaseCheck]:
    return [
        check_case(case_id, expected_position, rows)
        for case_id, expected_position in DEFAULT_REQUIRED_CASES.items()
    ]


def first_failure(checks: list[CaseCheck]) -> str:
    for item in checks:
        if item.result != "PASS":
            return f"{item.case_id}: {item.reason}"
    return ""


def build_metrics(checks: list[CaseCheck]) -> dict[str, Any]:
    return {
        "required_cases": len(checks),
        "passed_cases": sum(1 for item in checks if item.result == "PASS"),
        "flow_complete_cases": sum(1 for item in checks if item.flow_complete),
        "data_consent_cases": sum(1 for item in checks if item.data_consent_ok),
        "human_scored_cases": sum(1 for item in checks if item.human_scored),
        "result": "PASS" if all(item.result == "PASS" for item in checks) else "FAIL",
        "first_failure": first_failure(checks),
    }


def render_markdown(csv_path: Path, checks: list[CaseCheck], metrics: dict[str, Any]) -> str:
    lines = [
        "# 阶段 138 三岗位真实闭环检查报告",
        "",
        f"- 来源 CSV：`{csv_path.as_posix()}`",
        f"- 自动结论：`{metrics['result']}`",
        f"- 必需案例：`{metrics['required_cases']}`",
        f"- 通过案例：`{metrics['passed_cases']}`",
        f"- 完整流程案例：`{metrics['flow_complete_cases']}`",
        f"- 已完成本次案例数据贡献授权案例：`{metrics['data_consent_cases']}`",
        f"- 已完成人工评分案例：`{metrics['human_scored_cases']}`",
    ]
    if metrics["first_failure"]:
        lines.append(f"- 第一条失败：{metrics['first_failure']}")
    lines.extend(
        [
            "",
            "## 案例检查",
            "",
            "| 案例 | 目标岗位 | 最新 run | 流程 | 数据授权 | 学习任务 | 面试轮数 | 人工评分 | 结论 | 说明 |",
            "|---|---|---:|---|---|---|---|---|---|---|",
        ]
    )
    for item in checks:
        row = item.row
        lines.append(
            "| "
            f"{item.case_id} | {item.target_position or item.expected_position} | {item.run_id} | "
            f"{'PASS' if item.flow_complete else 'FAIL'} | "
            f"{'PASS' if item.data_consent_ok else 'FAIL'} | "
            f"{row.get('learning_tasks_added', '') if row else '-'} | "
            f"{row.get('interview_rounds', '') if row else '-'} | "
            f"{'PASS' if item.human_scored else 'FAIL'} | "
            f"{item.result} | {item.reason} |"
        )
    lines.extend(
        [
            "",
            "## 通过口径",
            "",
            "- R1/R2/R3 必须分别覆盖产品助理、Python 后端开发工程师、人力资源专员。",
            "- 上传、能力诊断、开始面试、报告、训练复盘、本次案例数据贡献授权、后台标注、评测样本状态必须是成功/通过/空态等通过口径。",
            "- 每个案例至少加入 1 项学习任务、完成至少 3 轮面试，并填写两个人工分与人工均分。",
            "- 如果失败，只处理第一条失败原因，不新增功能绕开真实验收。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stage 138 C1/C2/C3 closed-loop records.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Closed-loop CSV path.")
    parser.add_argument("--summary", type=Path, help="Optional Markdown summary path.")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}")
        return 2

    fieldnames, rows = read_rows(args.csv)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        print("result=FAIL")
        print("ERROR: Missing required columns: " + ", ".join(missing_columns))
        return 2

    checks = build_checks(rows)
    metrics = build_metrics(checks)
    print(f"csv={args.csv}")
    print(f"result={metrics['result']}")
    print(f"required_cases={metrics['required_cases']}")
    print(f"passed_cases={metrics['passed_cases']}")
    print(f"flow_complete_cases={metrics['flow_complete_cases']}")
    print(f"data_consent_cases={metrics['data_consent_cases']}")
    print(f"human_scored_cases={metrics['human_scored_cases']}")
    if metrics["first_failure"]:
        print(f"first_failure={metrics['first_failure']}")
    for item in checks:
        print(f"{item.case_id}={item.result} run_id={item.run_id} reason={item.reason}")

    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(render_markdown(args.csv, checks, metrics), encoding="utf-8")
        print(f"summary_written={args.summary}")

    return 0 if metrics["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
