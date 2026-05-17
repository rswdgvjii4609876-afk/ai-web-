from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.agent_orchestrator.demo_cases import generate_demo_cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Career-AgentOS competition demo cases.")
    parser.add_argument("--out", default="../demo_cases", help="Output directory for demo case JSON files.")
    args = parser.parse_args()

    out_dir = Path(args.out)
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
