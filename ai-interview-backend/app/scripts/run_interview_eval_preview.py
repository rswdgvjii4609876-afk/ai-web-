from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.services.agent_orchestrator.evaluator import build_eval_rows, evaluate_trace
from app.services.agent_orchestrator.trace_logger import load_trace


FIELDNAMES = [
    "case_id",
    "target_role",
    "model_variant",
    "focus_score",
    "evidence_score",
    "depth_score",
    "polish_score",
    "role_fit_score",
    "format_score",
    "report_score",
    "total_score",
    "judge_note",
]


def _trace_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.trace.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Eval Preview from Agent Trace JSON files.")
    parser.add_argument("--input", default="../artifacts/agent_trace", help="Trace file or directory.")
    parser.add_argument("--trace", default="", help="Alias for --input when a single trace file is used.")
    parser.add_argument("--out", default="../artifacts/eval", help="Output directory for eval preview.")
    args = parser.parse_args()

    input_path = Path(args.trace or args.input)
    traces = [load_trace(path) for path in _trace_paths(input_path)]
    if not traces:
        raise SystemExit(f"No trace files found: {input_path}")
    for trace in traces:
        trace.eval_score = trace.eval_score or evaluate_trace(trace)

    rows = build_eval_rows(traces)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "eval_score_table.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    md_path = out_dir / "eval_summary.md"
    lines = [
        "# Eval Preview Summary",
        "",
        "- 样本类型：`demo_constructed`",
        "- 评估类型：`preview/demo`",
        "- 满分：`35`",
        "- 说明：本结果只用于比赛沙盘展示，不代表真实 holdout eval。",
        "",
        "| case_id | target_role | total_score | judge_note |",
        "|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['case_id']} | {row['target_role']} | {row['total_score']}/35 | {row['judge_note']} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"eval_score_table={csv_path}")
    print(f"eval_summary={md_path}")
    print(f"cases={len(rows)}")
    print("dimensions=7")
    print("preview=true")


if __name__ == "__main__":
    main()
