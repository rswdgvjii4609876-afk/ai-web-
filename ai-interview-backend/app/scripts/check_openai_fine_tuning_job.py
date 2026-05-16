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


def _job_id_from_record(dataset_dir: Path) -> str:
    record_path = dataset_dir / "job_record.json"
    if not record_path.exists():
        return ""
    job = (_read_json(record_path).get("fine_tuning_job") or {})
    return str(job.get("id") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an OpenAI fine-tuning job and store status locally.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_OUTPUT_ROOT / "latest"))
    parser.add_argument("--job-id", default="")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    job_id = args.job_id or _job_id_from_record(dataset_dir)
    if not job_id:
        raise SystemExit("Job id is required via --job-id or dataset_dir/job_record.json.")
    key = (settings.OPENAI_API_KEY or "").strip()
    if not key or key == "your-openai-api-key":
        raise SystemExit("OPENAI_API_KEY is required and must not be the placeholder value.")

    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    job = client.fine_tuning.jobs.retrieve(job_id)
    status = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "fine_tuning_job": _sdk_dump(job),
    }
    _write_json(dataset_dir / "job_status.json", status)
    print(f"job_id={job_id}")
    print(f"status={getattr(job, 'status', '')}")
    print(f"fine_tuned_model={getattr(job, 'fine_tuned_model', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
