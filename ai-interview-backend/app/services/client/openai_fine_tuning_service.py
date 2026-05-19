from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


OPENAI_FINE_TUNING_DATASET_SCHEMA_VERSION = "ai-interview.openai-chat-sft.v1"
OPENAI_SFT_PREFLIGHT_VERSION = "ai-interview.openai-sft-preflight.v1"
OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES = 3
DEFAULT_MIN_TRAINING_SAMPLES = 10
DEFAULT_MIN_EVAL_SAMPLES = 5
REAL_SAMPLE_QUALITY_KEYS = ("is_high_quality", "followup_worthy", "report_actionable")

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONSTRUCTED_SAMPLES_PATH = (
    BACKEND_ROOT / "app" / "data" / "fine_tuning" / "constructed_followup_seed_samples.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "docs" / "competition" / "openai_fine_tuning_runs"

SYSTEM_PROMPT = (
    "你是职启智评就业能力诊断平台的面试追问模型。必须围绕岗位画像、简历证据状态和能力缺口追问；"
    "不得把岗位知识库写成候选人真实经历；优先要求候选人给出具体场景、行动和结果；输出必须是 JSON。"
)

DIRECT_IDENTIFIER_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"[\w\u4e00-\u9fff-]{2,}\.(?:pdf|doc|docx)", re.IGNORECASE),
    re.compile(r"\b(?:qq|wechat|weixin|github|linkedin)\s*[:：=]\s*[\w@./-]{2,}", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?(?:github|linkedin|gitee)\.com/[^\s\"'，,；;]+", re.IGNORECASE),
    re.compile(
        r"(?:姓名|名字|真实姓名|手机号|手机|电话|邮箱|电子邮箱|学号|证件号|身份证|微信|住址|地址|详细住址|文件名|name|phone|mobile|email|student_id|id_number|address)\s*[:：=]\s*[^,，；;\n]{2,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:姓名|手机号|手机|电话|邮箱|电子邮箱|学号|证件号|身份证|详细住址|家庭住址|住址|文件名)\s*[:：]\s*[^,，;；\n]{2,}"
    ),
)


class OpenAIFineTuningDataError(ValueError):
    """Raised when a local sample cannot enter the OpenAI SFT dataset."""


def _json_dumps(value: Any, *, sort_keys: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys, default=str)


def _stable_hash(value: Any) -> str:
    return sha256(_json_dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _sha256_text(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def normalize_openai_base_url(base_url: str) -> str:
    return (base_url or OFFICIAL_OPENAI_BASE_URL).strip().rstrip("/")


def validate_official_openai_base_url(base_url: str) -> str:
    normalized = normalize_openai_base_url(base_url)
    if normalized != OFFICIAL_OPENAI_BASE_URL:
        raise OpenAIFineTuningDataError(
            f"official OpenAI base_url required for real SFT; got {normalized or '<empty>'}"
        )
    return normalized


def openai_api_key_from_env() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "your-openai-api-key":
        raise OpenAIFineTuningDataError("OPENAI_API_KEY is required from environment and must not be the placeholder value.")
    return key


def _current_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _as_list(value: Any, limit: int = 5) -> List[Any]:
    if isinstance(value, list):
        return value[:limit]
    if value is None:
        return []
    return [value]


def has_direct_identifier(value: Any) -> bool:
    text = _json_dumps(value)
    return any(pattern.search(text) for pattern in DIRECT_IDENTIFIER_PATTERNS)


def _has_real_quality_signal(metadata: Dict[str, Any]) -> bool:
    return any(bool(metadata.get(key)) for key in REAL_SAMPLE_QUALITY_KEYS)


def _validate_source_metadata(metadata: Dict[str, Any], *, origin: str) -> None:
    declared_origin = metadata.get("sample_origin")
    if origin == "constructed":
        if declared_origin != "constructed":
            raise OpenAIFineTuningDataError("constructed sample must declare sample_origin=constructed")
        if metadata.get("data_contribution_consent") is True:
            raise OpenAIFineTuningDataError("constructed sample must not claim real-user data consent")
        return

    if origin != "real_authorized":
        raise OpenAIFineTuningDataError(f"unsupported sample_origin={origin}")
    if declared_origin and declared_origin != "real_authorized":
        raise OpenAIFineTuningDataError("real sample must not be marked as constructed or another origin")
    if metadata.get("data_contribution_consent") is not True:
        raise OpenAIFineTuningDataError("real sample is missing data_contribution_consent=true")
    if metadata.get("review_status") != "reviewed":
        raise OpenAIFineTuningDataError("real sample is missing review_status=reviewed")
    if not metadata.get("reviewed_at"):
        raise OpenAIFineTuningDataError("real sample is missing reviewed_at")
    if not metadata.get("reviewer_present"):
        raise OpenAIFineTuningDataError("real sample is missing reviewer_present=true")
    if not metadata.get("reviewer_hash"):
        raise OpenAIFineTuningDataError("real sample is missing reviewer_hash")
    if not _has_real_quality_signal(metadata):
        raise OpenAIFineTuningDataError("real sample is missing a human quality signal")


def validate_real_authorized_records(records: Sequence[Dict[str, Any]], *, source_label: str = "real-jsonl") -> None:
    for index, record in enumerate(records, start=1):
        try:
            convert_internal_record_to_openai_chat(record, sample_origin="real_authorized")
        except OpenAIFineTuningDataError as exc:
            raise OpenAIFineTuningDataError(f"{source_label} record {index} failed strict real-sample validation: {exc}") from exc


def load_jsonl_records(content: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for index, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OpenAIFineTuningDataError(f"Invalid JSONL at line {index}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise OpenAIFineTuningDataError(f"Invalid JSONL at line {index}: expected object")
        records.append(parsed)
    return records


def load_json_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return []
    if path.suffix.lower() == ".jsonl":
        return load_jsonl_records(content)
    parsed = json.loads(content)
    if isinstance(parsed, list):
        for index, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                raise OpenAIFineTuningDataError(f"Invalid JSON sample at index {index}: expected object")
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        for index, item in enumerate(parsed["items"], start=1):
            if not isinstance(item, dict):
                raise OpenAIFineTuningDataError(f"Invalid JSON sample at items[{index}]: expected object")
        return parsed["items"]
    raise OpenAIFineTuningDataError(f"Unsupported sample file shape: {path}")


def load_constructed_seed_records(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return load_json_records(path or DEFAULT_CONSTRUCTED_SAMPLES_PATH)


def _build_user_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    input_payload = record.get("input") or {}
    if not isinstance(input_payload, dict):
        input_payload = {"raw_input": input_payload}
    return {
        "task_type": record.get("task_type") or "followup_generation",
        "target_position": input_payload.get("target_position") or (record.get("metadata") or {}).get("target_position"),
        "ability_gap": input_payload.get("ability_gap"),
        "evidence_status": input_payload.get("evidence_status"),
        "question_reason": input_payload.get("question_reason"),
        "evidence_summary": _as_list(input_payload.get("evidence_summary")),
        "rag_context": _as_list(input_payload.get("rag_context")),
        "previous_question": input_payload.get("previous_question"),
        "candidate_answer": input_payload.get("candidate_answer"),
        "feedback": input_payload.get("feedback"),
        "report_gaps": _as_list(input_payload.get("report_gaps")),
        "report_training_priorities": _as_list(input_payload.get("report_training_priorities")),
    }


def _build_assistant_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    output = record.get("output") or {}
    if not isinstance(output, dict):
        output = {"question": str(output)}
    question = str(output.get("question") or "").strip()
    if not question:
        raise OpenAIFineTuningDataError("missing assistant question")
    return {
        "question": question,
        "verification_target": output.get("verification_target") or "",
        "expected_constraints": _as_list(
            output.get("expected_constraints")
            or [
                "不得把岗位知识库写成候选人真实经历",
                "必须围绕证据不足或待验证能力追问",
                "优先要求候选人给出具体场景、行动和结果",
            ],
            limit=6,
        ),
    }


def convert_internal_record_to_openai_chat(
    record: Dict[str, Any],
    *,
    sample_origin: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    origin = sample_origin or metadata.get("sample_origin") or "real_authorized"
    is_constructed = origin == "constructed"

    _validate_source_metadata(metadata, origin=origin)
    if metadata.get("has_hallucination"):
        raise OpenAIFineTuningDataError("hallucination counterexample cannot enter positive OpenAI SFT set")

    user_payload = _build_user_payload(record)
    assistant_payload = _build_assistant_payload(record)
    pii_screen_payload = {
        "instruction": record.get("instruction"),
        "input": user_payload,
        "output": assistant_payload,
        "metadata": metadata,
    }
    if has_direct_identifier(pii_screen_payload):
        raise OpenAIFineTuningDataError("sample contains direct personal identifier")

    upload_record = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _json_dumps(
                    {
                        "instruction": record.get("instruction")
                        or "根据岗位画像、简历证据和候选人回答生成面试追问。",
                        "input": user_payload,
                    }
                ),
            },
            {"role": "assistant", "content": _json_dumps(assistant_payload)},
        ]
    }
    manifest_record = {
        "schema_version": OPENAI_FINE_TUNING_DATASET_SCHEMA_VERSION,
        "sample_hash": _stable_hash(upload_record),
        "sample_origin": origin,
        "target_position": metadata.get("target_position") or user_payload.get("target_position") or "未填写岗位",
        "quality_tier": metadata.get("quality_tier"),
        "data_contribution_consent": bool(metadata.get("data_contribution_consent")),
        "review_status": metadata.get("review_status") if not is_constructed else "",
        "reviewed_at": metadata.get("reviewed_at") if not is_constructed else "",
        "reviewer_present": bool(metadata.get("reviewer_present")) if not is_constructed else False,
        "reviewer_hash": metadata.get("reviewer_hash") if not is_constructed else "",
        "quality_signals": [key for key in REAL_SAMPLE_QUALITY_KEYS if metadata.get(key)],
        "is_high_quality": bool(metadata.get("is_high_quality")),
        "followup_worthy": bool(metadata.get("followup_worthy")),
        "report_actionable": bool(metadata.get("report_actionable")),
        "has_hallucination": bool(metadata.get("has_hallucination")),
        "source_metadata": {
            key: metadata.get(key)
            for key in ("interview_id", "case_id", "dataset_split", "human_overall_score", "constructed_for")
            if key in metadata
        },
        "upload_record": upload_record,
    }
    return upload_record, manifest_record


def _split_train_validation(
    records: Sequence[Dict[str, Any]],
    manifests: Sequence[Dict[str, Any]],
    *,
    min_training_samples: int,
    min_eval_samples: int,
) -> Dict[str, List[Dict[str, Any]]]:
    if len(records) < min_training_samples + min_eval_samples:
        return {
            "train_records": list(records),
            "validation_records": [],
            "train_manifests": list(manifests),
            "validation_manifests": [],
        }
    validation_count = min(max(min_eval_samples, len(records) // 5), len(records) - min_training_samples)
    validation_indices = set(range(len(records) - validation_count, len(records)))
    train_records: List[Dict[str, Any]] = []
    validation_records: List[Dict[str, Any]] = []
    train_manifests: List[Dict[str, Any]] = []
    validation_manifests: List[Dict[str, Any]] = []
    for index, (record, manifest) in enumerate(zip(records, manifests)):
        if index in validation_indices:
            validation_records.append(record)
            validation_manifests.append(manifest)
        else:
            train_records.append(record)
            train_manifests.append(manifest)
    return {
        "train_records": train_records,
        "validation_records": validation_records,
        "train_manifests": train_manifests,
        "validation_manifests": validation_manifests,
    }


def build_openai_fine_tuning_dataset(
    real_records: Sequence[Dict[str, Any]],
    constructed_records: Sequence[Dict[str, Any]],
    *,
    min_real_authorized_samples: int = DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES,
    min_training_samples: int = DEFAULT_MIN_TRAINING_SAMPLES,
    min_eval_samples: int = DEFAULT_MIN_EVAL_SAMPLES,
) -> Dict[str, Any]:
    min_real_authorized_samples = max(min_real_authorized_samples, DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES)
    min_training_samples = max(min_training_samples, DEFAULT_MIN_TRAINING_SAMPLES)
    converted_records: List[Dict[str, Any]] = []
    manifests: List[Dict[str, Any]] = []
    rejected: List[Dict[str, str]] = []
    for origin, records in (("real_authorized", real_records), ("constructed", constructed_records)):
        for index, record in enumerate(records, start=1):
            try:
                upload_record, manifest = convert_internal_record_to_openai_chat(record, sample_origin=origin)
            except OpenAIFineTuningDataError as exc:
                rejected.append({"sample_origin": origin, "index": str(index), "reason": str(exc)})
                continue
            converted_records.append(upload_record)
            manifests.append(manifest)

    split = _split_train_validation(
        converted_records,
        manifests,
        min_training_samples=min_training_samples,
        min_eval_samples=min_eval_samples,
    )
    train_records = split["train_records"]
    validation_records = split["validation_records"]
    train_manifests = split["train_manifests"]
    validation_manifests = split["validation_manifests"]
    origin_counter = Counter(manifest["sample_origin"] for manifest in manifests)
    train_origin_counter = Counter(manifest["sample_origin"] for manifest in train_manifests)
    validation_origin_counter = Counter(manifest["sample_origin"] for manifest in validation_manifests)
    position_counter = Counter(str(manifest.get("target_position") or "未填写岗位") for manifest in manifests)

    real_authorized_total = origin_counter.get("real_authorized", 0)
    blockers: List[str] = []
    warnings: List[str] = []
    if real_authorized_total < min_real_authorized_samples:
        blockers.append(f"真实授权样本不足：当前 {real_authorized_total} 条，最低需要 {min_real_authorized_samples} 条。")
    if len(train_records) < min_training_samples:
        blockers.append(f"训练样本不足：当前 train={len(train_records)} 条，最低需要 {min_training_samples} 条。")
    if not validation_records:
        warnings.append("当前样本不足以拆出 5 条 holdout/eval；可创建训练集前继续补样本。")
    if validation_origin_counter.get("real_authorized", 0) < min_eval_samples:
        blockers.append(
            f"validation real_authorized samples are below minimum: {validation_origin_counter.get('real_authorized', 0)} < {min_eval_samples}"
        )
    if origin_counter.get("constructed", 0):
        blockers.append(
            "Real OpenAI fine-tuning jobs must not include constructed samples; use them only for preview or format validation."
        )
    if rejected:
        warnings.append(f"已有 {len(rejected)} 条样本因未授权、未复核、含直接标识或反例原因被剔除。")

    summary = {
        "schema_version": OPENAI_FINE_TUNING_DATASET_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "upload_format": "OpenAI chat fine-tuning JSONL; upload files only contain messages.",
        "minimum_requirements": {
            "min_real_authorized_samples": min_real_authorized_samples,
            "min_training_samples": min_training_samples,
            "min_eval_samples_for_comparison": min_eval_samples,
        },
        "counts": {
            "real_authorized_samples": real_authorized_total,
            "constructed_samples": origin_counter.get("constructed", 0),
            "total_accepted_samples": len(converted_records),
            "train_samples": len(train_records),
            "validation_samples": len(validation_records),
            "train_real_authorized_samples": train_origin_counter.get("real_authorized", 0),
            "train_constructed_samples": train_origin_counter.get("constructed", 0),
            "validation_real_authorized_samples": validation_origin_counter.get("real_authorized", 0),
            "validation_constructed_samples": validation_origin_counter.get("constructed", 0),
            "rejected_samples": len(rejected),
            "positions": dict(position_counter),
        },
        "ready_for_openai_job": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "files": {
            "train": "train_openai.jsonl",
            "validation": "validation_openai.jsonl" if validation_records else "",
            "manifest": "sample_manifest.jsonl",
            "summary": "summary.json",
        },
        "rejected_samples": rejected,
        "competition_claim_rule": (
            "只有 create job 成功并在 OpenAI 返回 fine_tuned_model 后，答辩材料才可写“已完成一次 OpenAI SFT 微调实验”。"
        ),
    }
    return {
        "summary": summary,
        "train_records": train_records,
        "validation_records": validation_records,
        "train_manifests": train_manifests,
        "validation_manifests": validation_manifests,
    }


def _jsonl(records: Iterable[Dict[str, Any]]) -> str:
    lines = [_json_dumps(record) for record in records]
    return "\n".join(lines) + ("\n" if lines else "")


def write_openai_fine_tuning_bundle(bundle: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train_openai.jsonl"
    validation_path = output_dir / "validation_openai.jsonl"
    manifest_path = output_dir / "sample_manifest.jsonl"
    summary_path = output_dir / "summary.json"
    readme_path = output_dir / "README.md"
    train_content = _jsonl(bundle["train_records"])
    validation_content = _jsonl(bundle["validation_records"])
    manifests = [{**item, "dataset_split": "train"} for item in bundle["train_manifests"]] + [
        {**item, "dataset_split": "validation"} for item in bundle["validation_manifests"]
    ]
    manifest_content = _jsonl(manifests)
    summary = dict(bundle["summary"])
    summary["dataset_fingerprint"] = {
        "preflight_version": OPENAI_SFT_PREFLIGHT_VERSION,
        "train_sha256": _sha256_text(train_content),
        "validation_sha256": _sha256_text(validation_content),
        "manifest_sha256": _sha256_text(manifest_content),
        "train_records": len(bundle["train_records"]),
        "validation_records": len(bundle["validation_records"]),
        "manifest_records": len(manifests),
    }
    bundle["summary"] = summary
    train_path.write_text(train_content, encoding="utf-8")
    validation_path.write_text(validation_content, encoding="utf-8")
    manifest_path.write_text(manifest_content, encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    readme_path.write_text(build_dataset_readme(bundle["summary"]), encoding="utf-8")
    return {"train": train_path, "validation": validation_path, "manifest": manifest_path, "summary": summary_path, "readme": readme_path}


def _read_json_file(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_upload_record(record: Dict[str, Any], *, label: str) -> None:
    if set(record.keys()) != {"messages"}:
        raise OpenAIFineTuningDataError(f"{label} must contain only messages")
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        raise OpenAIFineTuningDataError(f"{label} messages must be a non-empty chat transcript")
    roles = []
    for message_index, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            raise OpenAIFineTuningDataError(f"{label} message {message_index} must be an object")
        role = message.get("role")
        if role not in {"system", "developer", "user", "assistant"}:
            raise OpenAIFineTuningDataError(f"{label} message {message_index} has unsupported role={role}")
        if not isinstance(message.get("content"), str) or not message.get("content"):
            raise OpenAIFineTuningDataError(f"{label} message {message_index} content must be a non-empty string")
        roles.append(role)
    if "user" not in roles or "assistant" not in roles:
        raise OpenAIFineTuningDataError(f"{label} must contain at least one user and assistant message")
    if roles[-1] != "assistant":
        raise OpenAIFineTuningDataError(f"{label} final message must be assistant")
    if has_direct_identifier(record):
        raise OpenAIFineTuningDataError(f"{label} contains a direct personal identifier")


def _validate_manifest_record(
    manifest: Dict[str, Any],
    upload_record: Dict[str, Any],
    *,
    split: str,
    index: int,
) -> None:
    label = f"manifest {split} record {index}"
    if manifest.get("schema_version") != OPENAI_FINE_TUNING_DATASET_SCHEMA_VERSION:
        raise OpenAIFineTuningDataError(f"{label} has unexpected schema_version")
    if manifest.get("dataset_split") != split:
        raise OpenAIFineTuningDataError(f"{label} has wrong dataset_split")
    if manifest.get("upload_record") != upload_record:
        raise OpenAIFineTuningDataError(f"{label} upload_record does not match JSONL record")
    if manifest.get("sample_hash") != _stable_hash(upload_record):
        raise OpenAIFineTuningDataError(f"{label} sample_hash does not match upload_record")
    if has_direct_identifier(manifest):
        raise OpenAIFineTuningDataError(f"{label} contains a direct personal identifier")

    origin = manifest.get("sample_origin")
    if origin == "constructed":
        if manifest.get("data_contribution_consent") is True:
            raise OpenAIFineTuningDataError(f"{label} constructed sample claims data consent")
        source_metadata = manifest.get("source_metadata") or {}
        if not source_metadata.get("constructed_for"):
            raise OpenAIFineTuningDataError(f"{label} constructed sample is missing constructed_for")
        return
    if origin != "real_authorized":
        raise OpenAIFineTuningDataError(f"{label} has unsupported sample_origin={origin}")
    if manifest.get("data_contribution_consent") is not True:
        raise OpenAIFineTuningDataError(f"{label} real sample is missing data_contribution_consent=true")
    if manifest.get("review_status") != "reviewed":
        raise OpenAIFineTuningDataError(f"{label} real sample is missing review_status=reviewed")
    if not manifest.get("reviewed_at"):
        raise OpenAIFineTuningDataError(f"{label} real sample is missing reviewed_at")
    if manifest.get("reviewer_present") is not True:
        raise OpenAIFineTuningDataError(f"{label} real sample is missing reviewer_present=true")
    if not manifest.get("reviewer_hash"):
        raise OpenAIFineTuningDataError(f"{label} real sample is missing reviewer_hash")
    if not _has_real_quality_signal(manifest):
        raise OpenAIFineTuningDataError(f"{label} real sample is missing a human quality signal")
    if manifest.get("has_hallucination"):
        raise OpenAIFineTuningDataError(f"{label} hallucination sample cannot enter positive SFT set")


def _dataset_fingerprint(train_content: str, validation_content: str, manifest_content: str) -> Dict[str, Any]:
    train_records = load_jsonl_records(train_content)
    validation_records = load_jsonl_records(validation_content)
    manifest_records = load_jsonl_records(manifest_content)
    return {
        "preflight_version": OPENAI_SFT_PREFLIGHT_VERSION,
        "train_sha256": _sha256_text(train_content),
        "validation_sha256": _sha256_text(validation_content),
        "manifest_sha256": _sha256_text(manifest_content),
        "train_records": len(train_records),
        "validation_records": len(validation_records),
        "manifest_records": len(manifest_records),
    }


def validate_openai_fine_tuning_dataset_dir(
    dataset_dir: Path,
    *,
    require_ready: bool = True,
    require_validation: bool = False,
    min_eval_samples: int = DEFAULT_MIN_EVAL_SAMPLES,
) -> Dict[str, Any]:
    dataset_dir = Path(dataset_dir)
    summary_path = dataset_dir / "summary.json"
    train_path = dataset_dir / "train_openai.jsonl"
    validation_path = dataset_dir / "validation_openai.jsonl"
    manifest_path = dataset_dir / "sample_manifest.jsonl"
    errors: List[str] = []

    for path in (summary_path, train_path, manifest_path):
        if not path.exists():
            errors.append(f"missing required file: {path.name}")
    if errors:
        raise OpenAIFineTuningDataError("OpenAI SFT preflight failed: " + "; ".join(errors))

    summary = _read_json_file(summary_path)
    train_content = train_path.read_text(encoding="utf-8")
    validation_content = validation_path.read_text(encoding="utf-8") if validation_path.exists() else ""
    manifest_content = manifest_path.read_text(encoding="utf-8")
    train_records = load_jsonl_records(train_content)
    validation_records = load_jsonl_records(validation_content)
    manifest_records = load_jsonl_records(manifest_content)

    if require_ready and not summary.get("ready_for_openai_job"):
        errors.append("summary.ready_for_openai_job is false: " + "; ".join(summary.get("blockers") or []))
    if not train_records:
        errors.append("train_openai.jsonl is empty")

    for index, record in enumerate(train_records, start=1):
        try:
            _validate_upload_record(record, label=f"train record {index}")
        except OpenAIFineTuningDataError as exc:
            errors.append(str(exc))
    for index, record in enumerate(validation_records, start=1):
        try:
            _validate_upload_record(record, label=f"validation record {index}")
        except OpenAIFineTuningDataError as exc:
            errors.append(str(exc))

    train_manifests = [item for item in manifest_records if item.get("dataset_split") == "train"]
    validation_manifests = [item for item in manifest_records if item.get("dataset_split") == "validation"]
    if len(train_manifests) != len(train_records):
        errors.append("sample_manifest train count does not match train_openai.jsonl")
    if len(validation_manifests) != len(validation_records):
        errors.append("sample_manifest validation count does not match validation_openai.jsonl")
    if len(manifest_records) != len(train_records) + len(validation_records):
        errors.append("sample_manifest total count does not match upload JSONL files")

    for split, records, manifests in (
        ("train", train_records, train_manifests),
        ("validation", validation_records, validation_manifests),
    ):
        for index, (record, manifest) in enumerate(zip(records, manifests), start=1):
            try:
                _validate_manifest_record(manifest, record, split=split, index=index)
            except OpenAIFineTuningDataError as exc:
                errors.append(str(exc))

    train_hashes = {item.get("sample_hash") for item in train_manifests}
    validation_hashes = {item.get("sample_hash") for item in validation_manifests}
    all_hashes = [item.get("sample_hash") for item in manifest_records]
    if len(set(all_hashes)) != len([item for item in all_hashes if item]):
        errors.append("sample_manifest contains duplicate or missing sample_hash values")
    if train_hashes & validation_hashes:
        errors.append("train and validation splits overlap by sample_hash")

    actual_counts = Counter(item.get("sample_origin") for item in manifest_records)
    counts = summary.get("counts") or {}
    expected_count_pairs = {
        "train_samples": len(train_records),
        "validation_samples": len(validation_records),
        "total_accepted_samples": len(train_records) + len(validation_records),
        "real_authorized_samples": actual_counts.get("real_authorized", 0),
        "constructed_samples": actual_counts.get("constructed", 0),
    }
    for key, actual in expected_count_pairs.items():
        if counts.get(key) != actual:
            errors.append(f"summary.counts.{key}={counts.get(key)} does not match actual={actual}")

    minimums = summary.get("minimum_requirements") or {}
    min_train = max(
        int(minimums.get("min_training_samples") or DEFAULT_MIN_TRAINING_SAMPLES),
        DEFAULT_MIN_TRAINING_SAMPLES,
    )
    min_real = max(
        int(minimums.get("min_real_authorized_samples") or DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES),
        DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES,
    )
    if len(train_records) < min_train:
        errors.append(f"train sample count is below minimum: {len(train_records)} < {min_train}")
    if actual_counts.get("real_authorized", 0) < min_real:
        errors.append(f"real authorized sample count is below minimum: {actual_counts.get('real_authorized', 0)} < {min_real}")
    if require_ready and actual_counts.get("constructed", 0):
        errors.append(
            f"constructed samples are not allowed for real OpenAI fine-tuning jobs: {actual_counts.get('constructed', 0)}"
        )
    if require_validation and len(validation_records) < min_eval_samples:
        errors.append(f"validation sample count is below minimum for eval: {len(validation_records)} < {min_eval_samples}")
    if require_validation:
        validation_counts = Counter(item.get("sample_origin") for item in validation_manifests)
        if validation_counts.get("real_authorized", 0) < min_eval_samples:
            errors.append(
                f"validation real_authorized sample count is below minimum for eval: {validation_counts.get('real_authorized', 0)} < {min_eval_samples}"
            )
        if validation_counts.get("constructed", 0):
            errors.append(
                f"validation split contains constructed samples that cannot prove real-model eval readiness: {validation_counts.get('constructed', 0)}"
            )

    actual_fingerprint = _dataset_fingerprint(train_content, validation_content, manifest_content)
    expected_fingerprint = summary.get("dataset_fingerprint") or {}
    if not expected_fingerprint:
        errors.append("summary.dataset_fingerprint is missing")
    else:
        for key, actual in actual_fingerprint.items():
            if expected_fingerprint.get(key) != actual:
                errors.append(f"summary.dataset_fingerprint.{key} does not match actual dataset")

    if errors:
        raise OpenAIFineTuningDataError("OpenAI SFT preflight failed: " + "; ".join(errors))

    return {
        "preflight_version": OPENAI_SFT_PREFLIGHT_VERSION,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(dataset_dir),
        "schema_version": summary.get("schema_version"),
        "summary_generated_at_utc": summary.get("generated_at_utc"),
        "ready_for_openai_job": bool(summary.get("ready_for_openai_job")),
        "counts": counts,
        "dataset_fingerprint": actual_fingerprint,
    }


def build_openai_sft_provenance(
    dataset_dir: Path,
    *,
    preflight: Dict[str, Any],
    base_model: str = "",
    suffix: str = "",
    base_url: str = "",
) -> Dict[str, Any]:
    return {
        "provenance_version": OPENAI_SFT_PREFLIGHT_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(Path(dataset_dir)),
        "schema_version": preflight.get("schema_version"),
        "summary_generated_at_utc": preflight.get("summary_generated_at_utc"),
        "dataset_fingerprint": preflight.get("dataset_fingerprint"),
        "counts": preflight.get("counts"),
        "base_model": base_model,
        "suffix": suffix,
        "base_url": normalize_openai_base_url(base_url),
        "git_commit": _current_git_commit(),
    }


def read_openai_sft_job_record(dataset_dir: Path) -> Dict[str, Any]:
    record_path = Path(dataset_dir) / "job_record.json"
    if not record_path.exists():
        raise OpenAIFineTuningDataError(f"job_record.json is required: {record_path}")
    record = _read_json_file(record_path)
    job = record.get("fine_tuning_job") or {}
    job_id = str(record.get("job_id") or job.get("id") or "")
    if not job_id:
        raise OpenAIFineTuningDataError("job_record.json does not contain a fine-tuning job id")
    return record


def job_id_from_record(record: Dict[str, Any]) -> str:
    job = record.get("fine_tuning_job") or {}
    return str(record.get("job_id") or job.get("id") or "")


def assert_job_record_matches(
    dataset_dir: Path,
    requested_job_id: str = "",
    *,
    preflight: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    record = read_openai_sft_job_record(dataset_dir)
    job_id = job_id_from_record(record)
    if requested_job_id and requested_job_id != job_id:
        raise OpenAIFineTuningDataError(
            f"--job-id does not match dataset_dir/job_record.json: requested={requested_job_id}, recorded={job_id}"
        )
    if preflight is not None:
        recorded_fingerprint = record.get("dataset_fingerprint") or {}
        current_fingerprint = preflight.get("dataset_fingerprint") or {}
        if not recorded_fingerprint:
            raise OpenAIFineTuningDataError("job_record.json is missing dataset_fingerprint")
        for key, value in current_fingerprint.items():
            if recorded_fingerprint.get(key) != value:
                raise OpenAIFineTuningDataError(
                    f"job_record.json dataset_fingerprint does not match current dataset: {key}"
                )
    return record, job_id


def resolve_fine_tuned_model_for_eval(
    dataset_dir: Path,
    *,
    requested_model: str = "",
    requested_job_id: str = "",
    require_succeeded: bool = True,
    preflight: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record, job_id = assert_job_record_matches(dataset_dir, requested_job_id, preflight=preflight)
    status_path = Path(dataset_dir) / "job_status.json"
    if not status_path.exists():
        if require_succeeded:
            raise OpenAIFineTuningDataError("job_status.json is required before running eval")
        return {"job_record": record, "job_status": {}, "job_id": job_id, "fine_tuned_model": requested_model}

    status = _read_json_file(status_path)
    if preflight is not None:
        status_fingerprint = ((status.get("provenance") or {}).get("dataset_fingerprint") or {})
        current_fingerprint = preflight.get("dataset_fingerprint") or {}
        if not status_fingerprint:
            raise OpenAIFineTuningDataError("job_status.json is missing provenance.dataset_fingerprint")
        for key, value in current_fingerprint.items():
            if status_fingerprint.get(key) != value:
                raise OpenAIFineTuningDataError(
                    f"job_status.json provenance dataset_fingerprint does not match current dataset: {key}"
                )
    status_job = status.get("fine_tuning_job") or {}
    status_job_id = str(status.get("job_id") or status_job.get("id") or "")
    if status_job_id != job_id:
        raise OpenAIFineTuningDataError(
            f"job_status.json job id does not match job_record.json: status={status_job_id}, recorded={job_id}"
        )
    status_value = str(status_job.get("status") or "")
    fine_tuned_model = str(status_job.get("fine_tuned_model") or "")
    if require_succeeded and status_value != "succeeded":
        raise OpenAIFineTuningDataError(f"fine-tuning job must be succeeded before eval; current status={status_value}")
    if require_succeeded and not fine_tuned_model:
        raise OpenAIFineTuningDataError("job_status.json is missing fine_tuned_model")
    if requested_model and fine_tuned_model and requested_model != fine_tuned_model:
        raise OpenAIFineTuningDataError(
            f"--fine-tuned-model does not match job_status.json: requested={requested_model}, recorded={fine_tuned_model}"
        )
    return {
        "job_record": record,
        "job_status": status,
        "job_id": job_id,
        "fine_tuned_model": fine_tuned_model or requested_model,
    }


def build_dataset_readme(summary: Dict[str, Any]) -> str:
    counts = summary.get("counts") or {}
    blockers = summary.get("blockers") or []
    warnings = summary.get("warnings") or []
    blocker_lines = "\n".join(f"- {item}" for item in blockers) or "- 无"
    warning_lines = "\n".join(f"- {item}" for item in warnings) or "- 无"
    positions = counts.get("positions") or {}
    position_lines = "\n".join(f"| {position} | {count} |" for position, count in positions.items()) or "| 暂无 | 0 |"
    return f"""# 职启智评 OpenAI SFT 数据集

生成时间 UTC：`{summary.get("generated_at_utc")}`
Schema：`{summary.get("schema_version")}`

## 当前结论

- 是否达到创建 OpenAI fine-tuning job 门槛：`{summary.get("ready_for_openai_job")}`
- 真实授权样本：`{counts.get("real_authorized_samples", 0)}` 条
- 构造样本：`{counts.get("constructed_samples", 0)}` 条
- 训练集：`{counts.get("train_samples", 0)}` 条
- 验证集：`{counts.get("validation_samples", 0)}` 条

## 岗位覆盖

| 岗位 | 样本数 |
|---|---:|
{position_lines}

## 阻塞项

{blocker_lines}

## 风险提示

{warning_lines}

## 竞赛口径

{summary.get("competition_claim_rule")}

`train_openai.jsonl` 和 `validation_openai.jsonl` 仅包含 OpenAI chat fine-tuning 上传所需的 `messages`。
本地 `sample_manifest.jsonl` 保存样本来源、岗位、授权状态和质量标签，不用于 assistant 目标输出。
"""
