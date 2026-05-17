from __future__ import annotations

import argparse
import json

from app.services.agent_orchestrator.asset_guardrails import resolve_asset_path
from app.services.agent_orchestrator.demo_cases import generate_demo_cases
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.trace_logger import save_trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all Career-AgentOS competition demo assets.")
    parser.add_argument("--demo-out", default="")
    parser.add_argument("--trace-out", default="")
    parser.add_argument("--eval-out", default="")
    parser.add_argument("--sft-out", default="")
    args = parser.parse_args()

    cases = generate_demo_cases()
    demo_out = resolve_asset_path(args.demo_out, "demo_cases")
    demo_out.mkdir(parents=True, exist_ok=True)
    for case in cases:
        (demo_out / f"{case['case_id']}.json").write_text(
            json.dumps(case, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    trace_out = resolve_asset_path(args.trace_out, "artifacts/agent_trace")
    traces = [run_demo_pipeline(case) for case in cases]
    for trace in traces:
        save_trace(trace, trace_out)

    from app.scripts.run_interview_eval_preview import main as eval_main
    from app.scripts.build_sft_preview import main as sft_main
    import sys

    eval_out = resolve_asset_path(args.eval_out, "artifacts/eval")
    sft_out = resolve_asset_path(args.sft_out, "artifacts/sft_preview")
    sys.argv = ["run_interview_eval_preview", "--input", str(trace_out), "--out", str(eval_out)]
    eval_main()
    sys.argv = ["build_sft_preview", "--input", str(demo_out), "--out", str(sft_out)]
    sft_main()

    print("competition_assets=ready")
    print(f"demo_cases={len(cases)}")
    print("preview=true")


if __name__ == "__main__":
    main()
