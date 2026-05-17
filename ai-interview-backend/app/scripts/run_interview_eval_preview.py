from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.agent_orchestrator.asset_guardrails import (
    CASE_ORDER,
    resolve_asset_path,
    validate_case_id,
    validate_eval_preview_summary,
    validate_eval_score_rows,
    validate_trace_preview_asset,
)
from app.services.agent_orchestrator.evaluator import build_eval_rows, evaluate_trace
from app.services.agent_orchestrator.trace_logger import load_trace


FIELDNAMES = [
    "case_id",
    "target_role",
    "sample_origin",
    "for_training",
    "for_competition_demo",
    "preview",
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
        validate_case_id(input_path.name.replace(".trace.json", ""))
        return [input_path]
    order = {case_id: index for index, case_id in enumerate(CASE_ORDER)}
    paths = list(input_path.glob("*.trace.json"))
    case_ids = [path.name.replace(".trace.json", "") for path in paths]
    for case_id in case_ids:
        validate_case_id(case_id)
    missing = [case_id for case_id in CASE_ORDER if case_id not in case_ids]
    if missing or len(paths) != len(CASE_ORDER):
        raise SystemExit(f"Trace directory must contain exactly {', '.join(CASE_ORDER)}; missing={missing}")
    return sorted(paths, key=lambda path: order[path.name.replace(".trace.json", "")])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Eval Preview from Agent Trace JSON files.")
    parser.add_argument("--input", default="", help="Trace file or directory.")
    parser.add_argument("--trace", default="", help="Alias for --input when a single trace file is used.")
    parser.add_argument("--out", default="", help="Output directory for eval preview.")
    args = parser.parse_args()

    input_path = Path(args.trace).resolve() if args.trace else resolve_asset_path(args.input, "artifacts/agent_trace")
    traces = [load_trace(path) for path in _trace_paths(input_path)]
    if not traces:
        raise SystemExit(f"No trace files found: {input_path}")
    for trace in traces:
        validate_trace_preview_asset(trace.model_dump(), label=f"trace {trace.case_id}")
        trace.eval_score = trace.eval_score or evaluate_trace(trace)

    rows = build_eval_rows(traces)
    for trace in traces:
        case_rows = [row for row in rows if row.get("case_id") == trace.case_id]
        validate_eval_score_rows(trace.case_id, case_rows, label=f"eval rows {trace.case_id}")
    out_dir = resolve_asset_path(args.out, "artifacts/eval")
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
        "- 评分规则：七维规则评分，满分 `35`",
        "- 说明：本结果仅用于比赛沙盘展示；`baseline_prompt_preview` 是规则基线，不是真实模型实测；不代表真实 holdout eval 或 fine-tuned model 结果。",
        "",
        "| case_id | target_role | model_variant | total_score | judge_note |",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['target_role']} | {row['model_variant']} | "
            f"{row['total_score']}/35 | {row['judge_note']} |"
        )
    summary = "\n".join(lines) + "\n"
    validate_eval_preview_summary(summary, label=str(md_path))
    md_path.write_text(summary, encoding="utf-8")

    print(f"eval_score_table={csv_path}")
    print(f"eval_summary={md_path}")
    print(f"cases={len(traces)}")
    print(f"rows={len(rows)}")
    print("dimensions=7")
    print("preview=true")


if __name__ == "__main__":
    main()
