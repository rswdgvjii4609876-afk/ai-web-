from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.agent_orchestrator.demo_cases import generate_demo_cases
from app.services.agent_orchestrator.asset_guardrails import resolve_asset_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Career-AgentOS competition demo cases.")
    parser.add_argument("--out", default="", help="Output directory for demo case JSON files.")
    args = parser.parse_args()

    out_dir = resolve_asset_path(args.out, "demo_cases")
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = generate_demo_cases()
    for case in cases:
        path = out_dir / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {path}")
    print(f"demo_cases={len(cases)}")
    print("sample_origin=demo_constructed")
    print("for_training=false")
    print("for_competition_demo=true")


if __name__ == "__main__":
    main()
