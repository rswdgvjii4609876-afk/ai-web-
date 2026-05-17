from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

from app.core.config import settings
from app.services.client.openai_fine_tuning_service import (
    DEFAULT_OUTPUT_ROOT,
    OpenAIFineTuningDataError,
    assert_job_record_matches,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an OpenAI fine-tuning job and store status locally.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_OUTPUT_ROOT / "latest"))
    parser.add_argument("--job-id", default="")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    try:
        preflight = validate_openai_fine_tuning_dataset_dir(dataset_dir, require_ready=True)
        record, job_id = assert_job_record_matches(dataset_dir, args.job_id, preflight=preflight)
        base_url = validate_official_openai_base_url(os.getenv("OPENAI_BASE_URL", settings.OPENAI_BASE_URL))
        api_key = openai_api_key_from_env()
    except OpenAIFineTuningDataError as exc:
        raise SystemExit(str(exc)) from exc

    client = OpenAI(api_key=api_key, base_url=base_url)
    job = client.fine_tuning.jobs.retrieve(job_id)
    job_payload = _sdk_dump(job)
    retrieved_job_id = str(getattr(job, "id", "") or job_payload.get("id") or "")
    if retrieved_job_id and retrieved_job_id != job_id:
        raise SystemExit(f"Retrieved job id does not match requested job id: retrieved={retrieved_job_id}, expected={job_id}")
    status = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "provenance": build_openai_sft_provenance(
            dataset_dir,
            preflight=preflight,
            base_model=str(record.get("base_model") or ""),
            suffix=str(record.get("suffix") or ""),
            base_url=base_url,
        ),
        "fine_tuning_job": job_payload,
    }
    _write_json(dataset_dir / "job_status.json", status)
    print(f"job_id={job_id}")
    print(f"status={getattr(job, 'status', '')}")
    print(f"fine_tuned_model={getattr(job, 'fine_tuned_model', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
