from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from app.db.session import async_session
from app.services.client.interview_service import interview_service
from app.services.client.openai_fine_tuning_service import (
    DEFAULT_CONSTRUCTED_SAMPLES_PATH,
    DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES,
    DEFAULT_MIN_TRAINING_SAMPLES,
    DEFAULT_OUTPUT_ROOT,
    build_openai_fine_tuning_dataset,
    load_constructed_seed_records,
    load_json_records,
    load_jsonl_records,
    write_openai_fine_tuning_bundle,
)


async def _load_real_records_from_db(limit: int | None = None) -> List[Dict[str, Any]]:
    async with async_session() as db:
        samples = await interview_service.get_completed_training_samples(
            db=db,
            include_user_email=False,
            limit=limit,
        )
    bundle = interview_service.build_fine_tuning_dataset_bundle(samples)
    return load_jsonl_records(bundle["files"].get("fine_tuning_sft.jsonl") or "")


def _print_summary(summary: Dict[str, Any], output_dir: Path) -> None:
    counts = summary.get("counts") or {}
    print("# OpenAI SFT dataset preparation")
    print(f"output_dir={output_dir}")
    print(f"ready_for_openai_job={summary.get('ready_for_openai_job')}")
    print(f"real_authorized_samples={counts.get('real_authorized_samples', 0)}")
    print(f"constructed_samples={counts.get('constructed_samples', 0)}")
    print(f"train_samples={counts.get('train_samples', 0)}")
    print(f"validation_samples={counts.get('validation_samples', 0)}")
    if summary.get("blockers"):
        print("blockers:")
        for item in summary["blockers"]:
            print(f"- {item}")
    if summary.get("warnings"):
        print("warnings:")
        for item in summary["warnings"]:
            print(f"- {item}")


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare OpenAI chat fine-tuning JSONL from reviewed authorized samples and constructed seeds."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT / "latest"))
    parser.add_argument("--constructed-path", default=str(DEFAULT_CONSTRUCTED_SAMPLES_PATH))
    parser.add_argument("--real-jsonl", default="", help="Optional existing internal fine_tuning_sft.jsonl file.")
    parser.add_argument("--skip-db", action="store_true", help="Do not read real samples from the database.")
    parser.add_argument("--no-constructed", action="store_true", help="Do not include constructed seed samples.")
    parser.add_argument("--db-limit", type=int, default=None)
    parser.add_argument("--min-real-samples", type=int, default=DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES)
    parser.add_argument("--min-train-samples", type=int, default=DEFAULT_MIN_TRAINING_SAMPLES)
    parser.add_argument("--dry-run", action="store_true", help="Generate local files and print readiness only.")
    args = parser.parse_args()

    real_records: List[Dict[str, Any]] = []
    if args.real_jsonl:
        real_records.extend(load_json_records(Path(args.real_jsonl)))
    if not args.skip_db:
        try:
            real_records.extend(await _load_real_records_from_db(limit=args.db_limit))
        except Exception as exc:
            print(f"WARN: failed to load DB fine-tuning samples; continuing with file/constructed samples only: {exc}")

    constructed_records = []
    if not args.no_constructed:
        constructed_records = load_constructed_seed_records(Path(args.constructed_path))

    bundle = build_openai_fine_tuning_dataset(
        real_records=real_records,
        constructed_records=constructed_records,
        min_real_authorized_samples=args.min_real_samples,
        min_training_samples=args.min_train_samples,
    )
    output_dir = Path(args.output_dir)
    paths = write_openai_fine_tuning_bundle(bundle, output_dir)
    _print_summary(bundle["summary"], output_dir)
    print("files=" + json.dumps({key: str(path) for key, path in paths.items()}, ensure_ascii=False))
    if args.dry_run:
        print("dry_run=true; no OpenAI API call was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
