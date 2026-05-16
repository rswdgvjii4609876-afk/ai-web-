from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

from app.core.config import settings
from app.services.client.openai_fine_tuning_service import DEFAULT_OUTPUT_ROOT


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _sdk_dump(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return json.loads(json.dumps(obj, default=str))


def _has_real_openai_key() -> bool:
    key = (settings.OPENAI_API_KEY or "").strip()
    return bool(key and key != "your-openai-api-key")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload prepared JSONL files and create an OpenAI SFT job.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_OUTPUT_ROOT / "latest"))
    parser.add_argument("--model", default=settings.OPENAI_FINE_TUNE_BASE_MODEL)
    parser.add_argument("--suffix", default=settings.OPENAI_FINE_TUNE_SUFFIX)
    parser.add_argument("--confirm-cost", action="store_true", help="Required for real OpenAI upload/job creation.")
    parser.add_argument("--dry-run", action="store_true", help="Run local preflight only; do not call OpenAI.")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    summary_path = dataset_dir / "summary.json"
    train_path = dataset_dir / "train_openai.jsonl"
    validation_path = dataset_dir / "validation_openai.jsonl"
    if not summary_path.exists():
        raise SystemExit(f"summary.json not found: {summary_path}")
    summary = _read_json(summary_path)
    if not summary.get("ready_for_openai_job"):
        raise SystemExit("Dataset is not ready for OpenAI job: " + "; ".join(summary.get("blockers") or []))
    if not train_path.exists() or not train_path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"Training file is empty or missing: {train_path}")
    if not args.model:
        raise SystemExit("OPENAI_FINE_TUNE_BASE_MODEL or --model is required.")

    preflight = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(dataset_dir),
        "base_model": args.model,
        "suffix": args.suffix,
        "counts": summary.get("counts"),
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        _write_json(dataset_dir / "job_preflight.json", preflight)
        print("PASS: create job preflight passed; dry_run=true, no OpenAI API call was made.")
        return 0
    if not args.confirm_cost:
        raise SystemExit("Refusing to create paid OpenAI fine-tuning job without --confirm-cost.")
    if not _has_real_openai_key():
        raise SystemExit("OPENAI_API_KEY is required and must not be the placeholder value.")

    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    with train_path.open("rb") as train_file:
        training_file = client.files.create(file=train_file, purpose="fine-tune")

    validation_file_id = None
    if validation_path.exists() and validation_path.read_text(encoding="utf-8").strip():
        with validation_path.open("rb") as validation_file:
            validation_file = client.files.create(file=validation_file, purpose="fine-tune")
            validation_file_id = validation_file.id

    job_kwargs: Dict[str, Any] = {"model": args.model, "training_file": training_file.id, "suffix": args.suffix}
    if validation_file_id:
        job_kwargs["validation_file"] = validation_file_id
    job = client.fine_tuning.jobs.create(**job_kwargs)
    record = {
        **preflight,
        "dry_run": False,
        "training_file_id": training_file.id,
        "validation_file_id": validation_file_id,
        "fine_tuning_job": _sdk_dump(job),
    }
    _write_json(dataset_dir / "job_record.json", record)
    print(f"PASS: OpenAI fine-tuning job created: {getattr(job, 'id', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
