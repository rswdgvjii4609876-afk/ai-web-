from __future__ import annotations

import argparse
from pathlib import Path

from app.services.agent_orchestrator.demo_cases import generate_demo_cases
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle
from app.services.agent_orchestrator.trace_logger import save_trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all Career-AgentOS competition demo assets.")
    parser.add_argument("--demo-out", default="../demo_cases")
    parser.add_argument("--trace-out", default="../artifacts/agent_trace")
    parser.add_argument("--eval-out", default="../artifacts/eval")
    parser.add_argument("--sft-out", default="../artifacts/sft_preview")
    args = parser.parse_args()

    cases = generate_demo_cases()
    demo_out = Path(args.demo_out)
    demo_out.mkdir(parents=True, exist_ok=True)
    for case in cases:
        (demo_out / f"{case['case_id']}.json").write_text(
            __import__("json").dumps(case, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    trace_out = Path(args.trace_out)
    traces = [run_demo_pipeline(case) for case in cases]
    for trace in traces:
        save_trace(trace, trace_out)

    from app.scripts.run_interview_eval_preview import main as eval_main
    from app.scripts.build_sft_preview import main as sft_main
    import sys

    sys.argv = ["run_interview_eval_preview", "--input", str(trace_out), "--out", args.eval_out]
    eval_main()
    sys.argv = ["build_sft_preview", "--input", str(demo_out), "--out", args.sft_out]
    sft_main()

    print("competition_assets=ready")
    print(f"demo_cases={len(cases)}")
    print("preview=true")


if __name__ == "__main__":
    main()
