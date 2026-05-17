from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.agent_orchestrator.asset_guardrails import (
    resolve_asset_path,
    sort_demo_cases,
    validate_demo_preview_asset,
)
from app.services.agent_orchestrator.demo_cases import generate_demo_cases
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle


def _load_cases(input_dir: Path) -> list[dict]:
    if input_dir.exists():
        cases = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(input_dir.glob("*.json"))
        ]
        if cases:
            for case in cases:
                validate_demo_preview_asset(case, label=f"demo case {case.get('case_id')}")
            return sort_demo_cases(cases)
    return generate_demo_cases()


def _jsonl(records: list[dict]) -> str:
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SFT Preview JSONL from demo cases.")
    parser.add_argument("--input", default="", help="Demo cases directory.")
    parser.add_argument("--out", default="", help="Output directory for preview JSONL.")
    args = parser.parse_args()

    cases = _load_cases(resolve_asset_path(args.input, "demo_cases"))
    bundle = build_sft_preview_bundle(cases)
    out_dir = resolve_asset_path(args.out, "artifacts/sft_preview")
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "train.preview.jsonl"
    validation_path = out_dir / "validation.preview.jsonl"
    summary_path = out_dir / "summary.preview.json"
    train_path.write_text(_jsonl(bundle["train"]) + "\n", encoding="utf-8")
    validation_path.write_text(_jsonl(bundle["validation"]), encoding="utf-8")
    summary_path.write_text(json.dumps(bundle["summary"], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"train_preview={train_path}")
    print(f"validation_preview={validation_path}")
    print(f"summary_preview={summary_path}")
    print("ready_for_real_training=false")
    print("sample_origin=demo_constructed")


if __name__ == "__main__":
    main()
