from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

from app.core.config import settings
from app.services.client.openai_fine_tuning_service import (
    DEFAULT_OUTPUT_ROOT,
    OpenAIFineTuningDataError,
    build_openai_sft_provenance,
    openai_api_key_from_env,
    validate_official_openai_base_url,
    validate_openai_fine_tuning_dataset_dir,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _sdk_dump(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return json.loads(json.dumps(obj, default=str))


def _existing_job_id(record: Dict[str, Any]) -> str:
    job = record.get("fine_tuning_job") or {}
    return str(record.get("job_id") or job.get("id") or "")


def _archive_existing_job_record(job_record_path: Path) -> Dict[str, str]:
    if not job_record_path.exists():
        return {"previous_job_id": "", "previous_job_record_path": ""}
    old_record = json.loads(job_record_path.read_text(encoding="utf-8"))
    old_job_id = _existing_job_id(old_record) or "unknown"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = job_record_path.with_name(f"job_record.{old_job_id}.{timestamp}.json")
    job_record_path.replace(archive_path)
    return {"previous_job_id": old_job_id, "previous_job_record_path": str(archive_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload prepared JSONL files and create an OpenAI SFT job.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_OUTPUT_ROOT / "latest"))
    parser.add_argument("--model", default=settings.OPENAI_FINE_TUNE_BASE_MODEL)
    parser.add_argument("--suffix", default=settings.OPENAI_FINE_TUNE_SUFFIX)
    parser.add_argument("--confirm-cost", action="store_true", help="Required for real OpenAI upload/job creation.")
    parser.add_argument("--dry-run", action="store_true", help="Run local preflight only; do not call OpenAI.")
    parser.add_argument("--force-new-job", action="store_true", help="Allow creating a new job when job_record.json already exists.")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    train_path = dataset_dir / "train_openai.jsonl"
    validation_path = dataset_dir / "validation_openai.jsonl"
    if not args.model:
        raise SystemExit("OPENAI_FINE_TUNE_BASE_MODEL or --model is required.")
    job_record_path = dataset_dir / "job_record.json"
    job_intent_path = dataset_dir / "job_intent.json"
    if job_record_path.exists() and not args.force_new_job:
        raise SystemExit(f"Refusing to create another OpenAI fine-tuning job because job_record.json already exists: {job_record_path}")
    if job_intent_path.exists() and not args.force_new_job and not job_record_path.exists():
        raise SystemExit(
            f"Refusing to create OpenAI fine-tuning job because a previous creation intent exists without job_record.json: {job_intent_path}. "
            "Check OpenAI dashboard/status first, then remove the intent manually if no job was created."
        )
    existing_job_info = {"previous_job_id": "", "previous_job_record_path": ""}
    if job_record_path.exists() and args.force_new_job:
        old_record = json.loads(job_record_path.read_text(encoding="utf-8"))
        existing_job_info = {"previous_job_id": _existing_job_id(old_record), "previous_job_record_path": str(job_record_path)}

    try:
        base_url = validate_official_openai_base_url(os.getenv("OPENAI_BASE_URL", settings.OPENAI_BASE_URL))
        preflight = validate_openai_fine_tuning_dataset_dir(dataset_dir, require_ready=True, require_validation=True)
    except OpenAIFineTuningDataError as exc:
        raise SystemExit(str(exc)) from exc

    provenance = build_openai_sft_provenance(
        dataset_dir,
        preflight=preflight,
        base_model=args.model,
        suffix=args.suffix,
        base_url=base_url,
    )
    preflight_record = {
        **provenance,
        "dry_run": bool(args.dry_run),
        "force_new_job": bool(args.force_new_job),
        **existing_job_info,
    }
    if args.dry_run:
        _write_json(dataset_dir / "job_preflight.json", preflight_record)
        print("PASS: create job preflight passed; dry_run=true, no OpenAI API call was made.")
        return 0
    if not args.confirm_cost:
        raise SystemExit("Refusing to create paid OpenAI fine-tuning job without --confirm-cost.")
    try:
        api_key = openai_api_key_from_env()
    except OpenAIFineTuningDataError as exc:
        raise SystemExit(str(exc)) from exc

    _write_json(
        job_intent_path,
        {
            **preflight_record,
            "dry_run": False,
            "status": "creating",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    client = OpenAI(api_key=api_key, base_url=base_url)
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
    archived_job_info = (
        _archive_existing_job_record(job_record_path)
        if job_record_path.exists() and args.force_new_job
        else existing_job_info
    )
    record = {
        **provenance,
        "dry_run": False,
        "force_new_job": bool(args.force_new_job),
        **archived_job_info,
        "job_id": getattr(job, "id", ""),
        "job_kwargs": {**job_kwargs, "training_file": training_file.id, "validation_file": validation_file_id},
        "training_file_id": training_file.id,
        "validation_file_id": validation_file_id,
        "fine_tuning_job": _sdk_dump(job),
    }
    _write_json(dataset_dir / "job_record.json", record)
    _write_json(
        job_intent_path,
        {
            **preflight_record,
            "dry_run": False,
            "status": "created",
            "job_id": getattr(job, "id", ""),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    print(f"PASS: OpenAI fine-tuning job created: {getattr(job, 'id', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
