from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.agent_orchestrator.asset_guardrails import (
    resolve_asset_path,
    validate_demo_preview_asset,
)
from app.services.agent_orchestrator.demo_cases import build_demo_case_index
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.trace_logger import save_trace


def _load_case(case_arg: str) -> dict:
    candidate = Path(case_arg)
    if candidate.exists():
        case = json.loads(candidate.read_text(encoding="utf-8"))
        validate_demo_preview_asset(case, label=str(candidate))
        return case
    case_id = case_arg.replace(".json", "")
    case_path = resolve_asset_path("", "demo_cases") / f"{case_id}.json"
    if case_path.exists():
        case = json.loads(case_path.read_text(encoding="utf-8"))
        validate_demo_preview_asset(case, label=str(case_path))
        return case
    cases = build_demo_case_index()
    if case_id in cases:
        return cases[case_id]
    raise SystemExit(f"Unknown demo case: {case_arg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a Career-AgentOS Agent Trace for one demo case.")
    parser.add_argument("--case", required=True, help="Demo case path or case id, e.g. python_backend.")
    parser.add_argument("--out", default="", help="Output directory for trace files.")
    args = parser.parse_args()

    case = _load_case(args.case)
    trace = run_demo_pipeline(case)
    paths = save_trace(trace, resolve_asset_path(args.out, "artifacts/agent_trace"))
    print(f"case_id={trace.case_id}")
    print(f"trace_json={paths['json']}")
    print(f"trace_markdown={paths['markdown']}")
    print("contains_resume_polish=true")
    print("preview=true")


if __name__ == "__main__":
    main()
