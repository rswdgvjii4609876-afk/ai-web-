from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


CASE_ORDER = ("python_backend", "product_assistant", "hr_specialist")

DIRECT_IDENTIFIER_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"(?:学号|student[_ -]?id|school[_ -]?id)\s*[:：]?\s*[A-Za-z0-9-]{6,}", re.IGNORECASE),
    re.compile(r"(?:身份证|身份证号|证件号)\s*[:：]?\s*\d{15,17}[\dXx]?", re.IGNORECASE),
    re.compile(r"(?:student[_ -]?id|school[_ -]?id)\s*[:：]?\s*\d{6,}", re.IGNORECASE),
    re.compile(r"(?:姓名|手机号|电话|邮箱|学号|身份证|详细住址)\s*[:：]\s*[^,，；;\n]{2,}"),
)


def project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [Path.cwd().resolve(), *Path.cwd().resolve().parents, *here.parents]
    for candidate in candidates:
        if (candidate / "ai-interview-backend" / "app").exists():
            return candidate
    return here.parents[3]


def resolve_asset_path(value: str | None, default_relative: str) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return (project_root() / default_relative).resolve()


def sort_demo_cases(cases: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    order = {case_id: index for index, case_id in enumerate(CASE_ORDER)}
    return sorted(cases, key=lambda item: order.get(str(item.get("case_id")), len(order)))


def _text_for_scan(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def direct_identifier_hits(value: Any) -> List[str]:
    text = _text_for_scan(value)
    return [pattern.pattern for pattern in DIRECT_IDENTIFIER_PATTERNS if pattern.search(text)]


def validate_no_direct_identifiers(value: Any, *, label: str = "asset") -> None:
    hits = direct_identifier_hits(value)
    if hits:
        raise ValueError(f"{label} contains direct identifier pattern: {hits[0]}")


def validate_demo_preview_asset(asset: Dict[str, Any], *, label: str = "asset") -> None:
    if asset.get("sample_origin") != "demo_constructed":
        raise ValueError(f"{label} must use sample_origin=demo_constructed")
    if asset.get("for_training") is not False:
        raise ValueError(f"{label} must use for_training=false")
    if asset.get("for_competition_demo") is not True:
        raise ValueError(f"{label} must use for_competition_demo=true")
    validate_no_direct_identifiers(asset, label=label)


def validate_trace_preview_asset(trace: Dict[str, Any], *, label: str = "trace") -> None:
    validate_demo_preview_asset(trace, label=label)
    if trace.get("eval_score", {}).get("total_score", 0) > 35:
        raise ValueError(f"{label} eval_score.total_score must be <= 35")
    steps = trace.get("steps") or []
    if not any(step.get("agent") == "ResumePolishAgent" for step in steps):
        raise ValueError(f"{label} must include ResumePolishAgent")


def validate_sft_preview_summary(summary: Dict[str, Any], *, label: str = "sft summary") -> None:
    if summary.get("dataset_type") != "sft_preview":
        raise ValueError(f"{label} must use dataset_type=sft_preview")
    if summary.get("ready_for_real_training") is not False:
        raise ValueError(f"{label} must use ready_for_real_training=false")
    counts = summary.get("counts") or {}
    if counts.get("real_authorized", 0) != 0:
        raise ValueError(f"{label} must not claim real_authorized samples")
    validate_no_direct_identifiers(summary, label=label)


def validate_sft_preview_record(record: Dict[str, Any], *, label: str = "sft preview record") -> None:
    validate_demo_preview_asset(record, label=label)
    if "preview" not in str(record.get("task_type", "")):
        raise ValueError(f"{label} task_type must be marked as preview")
