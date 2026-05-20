from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_prefix(item: dict[str, Any]) -> str | None:
    value = item.get("sha256") or item.get("metadata", {}).get("source_file_sha256")
    if not value:
        return None
    return str(value)[:12]


def _safe_record(item: dict[str, Any], index: int) -> dict[str, Any]:
    metadata = item.get("metadata") or {}
    return {
        "index": index,
        "source_sha256_prefix": _hash_prefix(item),
        "target_position": item.get("target_position") or metadata.get("target_position"),
        "status": item.get("status"),
        "blocked_reason": item.get("blocked_reason"),
        "resume_id": item.get("resume_id"),
        "interview_id": item.get("interview_id"),
        "rounds": item.get("rounds"),
        "sample_origin": metadata.get("sample_origin"),
        "candidate_answer_source": metadata.get("candidate_answer_source"),
        "data_contribution_consent": metadata.get("data_contribution_consent"),
        "for_real_sft": metadata.get("for_real_sft"),
        "for_training": metadata.get("for_training"),
    }


def load_run_records(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actual_summary = run_dir / "summary.json"
    actual_records = run_dir / "run_result.json"
    dry_summary = run_dir / "summary.preview.json"
    dry_records = run_dir / "manifest.preview.json"

    if actual_summary.exists() and actual_records.exists():
        return _load_json(actual_summary), _load_json(actual_records)
    if dry_summary.exists() and dry_records.exists():
        return _load_json(dry_summary), _load_json(dry_records)
    raise FileNotFoundError(
        f"No supported semi-synthetic run files found in {run_dir}. "
        "Expected summary.json/run_result.json or summary.preview.json/manifest.preview.json."
    )


def build_sanitized_summary(run_dir: Path) -> dict[str, Any]:
    summary, records = load_run_records(run_dir)
    safe_records = [_safe_record(item, index + 1) for index, item in enumerate(records)]
    return {
        "source_run_dir": str(run_dir),
        "mode": summary.get("mode"),
        "total_files": summary.get("total_files"),
        "ready_files": summary.get("ready_files"),
        "blocked_files": summary.get("blocked_files") or summary.get("blocked"),
        "completed": summary.get("completed"),
        "failed": summary.get("failed"),
        "semi_synthetic_data_contribution": summary.get("semi_synthetic_data_contribution"),
        "boundary": (
            "真实简历驱动 + AI 模拟候选人回答 + 待人工复核的前期实例；"
            "不能改标为真人完整面试数据，不能进入真实 OpenAI SFT。"
        ),
        "records": safe_records,
    }


def write_summary_files(run_dir: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    json_path = run_dir / "sanitized_summary.json"
    md_path = run_dir / "sanitized_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 半合成简历闭环跑批脱敏摘要",
        "",
        f"- mode: `{payload.get('mode')}`",
        f"- total_files: `{payload.get('total_files')}`",
        f"- ready_files: `{payload.get('ready_files')}`",
        f"- blocked_files: `{payload.get('blocked_files')}`",
        f"- completed: `{payload.get('completed')}`",
        f"- failed: `{payload.get('failed')}`",
        f"- semi_synthetic_data_contribution: `{payload.get('semi_synthetic_data_contribution')}`",
        "",
        "## 边界",
        "",
        payload["boundary"],
        "",
        "## 脱敏记录",
        "",
        "| # | hash | 岗位 | 状态 | blocked | resume_id | interview_id | rounds | origin | answer_source | real_sft | training |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in payload["records"]:
        lines.append(
            "| {index} | {source_sha256_prefix} | {target_position} | {status} | {blocked_reason} | "
            "{resume_id} | {interview_id} | {rounds} | {sample_origin} | {candidate_answer_source} | "
            "{for_real_sft} | {for_training} |".format(**{key: "" if value is None else value for key, value in item.items()})
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a sanitized summary for a semi-synthetic resume run.")
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()
    return args


def main() -> int:
    args = parse_args()
    payload = build_sanitized_summary(args.run_dir)
    json_path, md_path = write_summary_files(args.run_dir, payload)
    print(f"sanitized_json={json_path}")
    print(f"sanitized_md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
