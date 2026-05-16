from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


OPENAI_FINE_TUNING_DATASET_SCHEMA_VERSION = "ai-interview.openai-chat-sft.v1"
DEFAULT_MIN_REAL_AUTHORIZED_SAMPLES = 3
DEFAULT_MIN_TRAINING_SAMPLES = 10
DEFAULT_MIN_EVAL_SAMPLES = 5

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
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
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


def _as_list(value: Any, limit: int = 5) -> List[Any]:
    if isinstance(value, list):
        return value[:limit]
    if value is None:
        return []
    return [value]


def has_direct_identifier(value: Any) -> bool:
    text = _json_dumps(value)
    return any(pattern.search(text) for pattern in DIRECT_IDENTIFIER_PATTERNS)


def load_jsonl_records(content: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for index, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OpenAIFineTuningDataError(f"Invalid JSONL at line {index}: {exc}") from exc
        if isinstance(parsed, dict):
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
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        return [item for item in parsed["items"] if isinstance(item, dict)]
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

    if is_constructed:
        if metadata.get("sample_origin") != "constructed":
            raise OpenAIFineTuningDataError("constructed sample must declare sample_origin=constructed")
    elif metadata.get("data_contribution_consent") is not True:
        raise OpenAIFineTuningDataError("real sample is missing data_contribution_consent=true")
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
    origin_counter = Counter(manifest["sample_origin"] for manifest in manifests)
    train_origin_counter = Counter(manifest["sample_origin"] for manifest in train_manifests)
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
        "validation_manifests": split["validation_manifests"],
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
    train_path.write_text(_jsonl(bundle["train_records"]), encoding="utf-8")
    validation_path.write_text(_jsonl(bundle["validation_records"]), encoding="utf-8")
    manifests = [{**item, "dataset_split": "train"} for item in bundle["train_manifests"]] + [
        {**item, "dataset_split": "validation"} for item in bundle["validation_manifests"]
    ]
    manifest_path.write_text(_jsonl(manifests), encoding="utf-8")
    summary_path.write_text(json.dumps(bundle["summary"], ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    readme_path.write_text(build_dataset_readme(bundle["summary"]), encoding="utf-8")
    return {"train": train_path, "validation": validation_path, "manifest": manifest_path, "summary": summary_path, "readme": readme_path}


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
