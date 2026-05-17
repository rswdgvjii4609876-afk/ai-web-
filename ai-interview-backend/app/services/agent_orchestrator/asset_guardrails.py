from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


CASE_ORDER = ("python_backend", "product_assistant", "hr_specialist")
CASE_ID_SET = set(CASE_ORDER)
EVAL_DIMENSIONS = (
    "focus_score",
    "evidence_score",
    "depth_score",
    "polish_score",
    "role_fit_score",
    "format_score",
    "report_score",
)
EXPECTED_EVAL_SCORES = {
    "baseline_prompt_preview": {
        "focus_score": 3,
        "evidence_score": 2,
        "depth_score": 3,
        "polish_score": 2,
        "role_fit_score": 3,
        "format_score": 3,
        "report_score": 3,
        "total_score": 19,
    },
    "agent_optimized": {
        "focus_score": 5,
        "evidence_score": 5,
        "depth_score": 5,
        "polish_score": 5,
        "role_fit_score": 4,
        "format_score": 5,
        "report_score": 5,
        "total_score": 34,
    },
}
TRACE_AGENT_ORDER = (
    "ResumeEvidenceAgent",
    "RoleProfileAgent",
    "GapAnalysisAgent",
    "ResumePolishAgent",
    "InterviewFollowupAgent",
    "ReportAgent",
    "LearningTaskAgent",
    "DataGovernanceAgent",
    "EvalAgent",
    "SFTPreviewAgent",
)

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


def validate_case_id(case_id: str, *, label: str = "case_id") -> str:
    normalized = str(case_id or "").strip()
    if normalized not in CASE_ID_SET:
        raise ValueError(f"{label} must be one of {', '.join(CASE_ORDER)}")
    return normalized


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
    metadata = asset.get("metadata") or {}
    validate_case_id(str(asset.get("case_id") or metadata.get("case_id") or ""), label=f"{label}.case_id")
    if asset.get("sample_origin") != "demo_constructed":
        raise ValueError(f"{label} must use sample_origin=demo_constructed")
    if asset.get("for_training") is not False:
        raise ValueError(f"{label} must use for_training=false")
    if asset.get("for_competition_demo") is not True:
        raise ValueError(f"{label} must use for_competition_demo=true")
    validate_no_direct_identifiers(asset, label=label)


def validate_demo_case_set(cases: Iterable[Dict[str, Any]], *, label: str = "demo cases") -> List[Dict[str, Any]]:
    items = list(cases)
    for case in items:
        validate_demo_preview_asset(case, label=f"{label}.{case.get('case_id')}")
    case_ids = [str(case.get("case_id", "")) for case in items]
    duplicate_ids = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicate_ids:
        raise ValueError(f"{label} contains duplicate case_id: {', '.join(duplicate_ids)}")
    missing = [case_id for case_id in CASE_ORDER if case_id not in case_ids]
    extra = sorted(case_id for case_id in case_ids if case_id not in CASE_ID_SET)
    if missing or extra:
        raise ValueError(
            f"{label} must contain exactly {', '.join(CASE_ORDER)}; "
            f"missing={missing or []}; extra={extra or []}"
        )
    return sort_demo_cases(items)


def _as_int(value: Any, *, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc


def _is_bool_flag(value: Any, expected: bool) -> bool:
    if isinstance(value, bool):
        return value is expected
    normalized = str(value).strip().lower()
    return normalized in {str(expected).lower(), "1" if expected else "0"}


def _validate_eval_score_row(case_id: str, row: Dict[str, Any], *, label: str) -> None:
    if str(row.get("case_id")) != case_id:
        raise ValueError(f"{label} row case_id must match {case_id}")
    if row.get("sample_origin") != "demo_constructed":
        raise ValueError(f"{label} for {case_id} must use sample_origin=demo_constructed")
    if not _is_bool_flag(row.get("for_training"), False):
        raise ValueError(f"{label} for {case_id} must use for_training=false")
    if not _is_bool_flag(row.get("for_competition_demo"), True):
        raise ValueError(f"{label} for {case_id} must use for_competition_demo=true")
    if not _is_bool_flag(row.get("preview"), True):
        raise ValueError(f"{label} for {case_id} must use preview=true")
    variant = str(row.get("model_variant"))
    expected = EXPECTED_EVAL_SCORES.get(variant)
    if expected is None:
        raise ValueError(f"{label} uses unsupported model_variant={variant}")

    dimension_values = {}
    for dimension in EVAL_DIMENSIONS:
        if dimension not in row:
            raise ValueError(f"{label} for {case_id}/{variant} must include {dimension}")
        value = _as_int(row.get(dimension), label=f"{label}.{dimension}")
        if not 1 <= value <= 5:
            raise ValueError(f"{label} for {case_id}/{variant} {dimension} must be between 1 and 5")
        if value != expected[dimension]:
            raise ValueError(f"{label} for {case_id}/{variant} {dimension} must be {expected[dimension]}")
        dimension_values[dimension] = value

    total_score = _as_int(row.get("total_score"), label=f"{label}.total_score")
    if total_score != sum(dimension_values.values()):
        raise ValueError(f"{label} for {case_id}/{variant} total_score must equal the 7-dimension sum")
    if total_score != expected["total_score"]:
        raise ValueError(f"{label} for {case_id}/{variant} must use total_score={expected['total_score']}")

    judge_note = str(row.get("judge_note", ""))
    required_note_fragments = (
        "not a real model run",
        "not a holdout eval",
        "not a fine-tuned model result",
    )
    if any(fragment not in judge_note for fragment in required_note_fragments):
        raise ValueError(f"{label} for {case_id}/{variant} must include non-real-model boundary")


def validate_trace_preview_asset(trace: Dict[str, Any], *, label: str = "trace") -> None:
    validate_demo_preview_asset(trace, label=label)
    steps = trace.get("steps") or []
    step_agents = [step.get("agent") for step in steps]
    if tuple(step_agents) != TRACE_AGENT_ORDER:
        raise ValueError(f"{label} must include the complete Agent order: {', '.join(TRACE_AGENT_ORDER)}")
    for index, step in enumerate(steps, start=1):
        if int(step.get("step", -1)) != index:
            raise ValueError(f"{label} step numbers must be continuous from 1 to {len(TRACE_AGENT_ORDER)}")
        if not isinstance(step.get("output"), dict):
            raise ValueError(f"{label} step {index} output must be an object")

    data_governance = steps[7].get("output") or {}
    validate_demo_preview_asset(
        {
            "case_id": trace.get("case_id"),
            "sample_origin": data_governance.get("sample_origin"),
            "for_training": data_governance.get("for_training"),
            "for_competition_demo": data_governance.get("for_competition_demo"),
        },
        label=f"{label}.DataGovernanceAgent",
    )
    if "不作为真实训练样本" not in str(data_governance.get("claim", "")):
        raise ValueError(f"{label}.DataGovernanceAgent must state the non-training claim boundary")

    eval_score = trace.get("eval_score") or {}
    eval_row = {
        "case_id": trace.get("case_id"),
        "target_role": trace.get("target_role"),
        "sample_origin": trace.get("sample_origin"),
        "for_training": trace.get("for_training"),
        "for_competition_demo": trace.get("for_competition_demo"),
        "preview": True,
        "model_variant": "agent_optimized",
        **eval_score,
    }
    _validate_eval_score_row(str(trace.get("case_id")), eval_row, label=f"{label}.eval_score")
    if steps[8].get("output") != eval_score:
        raise ValueError(f"{label}.EvalAgent output must match trace.eval_score")

    sft_summary = trace.get("sft_preview_summary") or {}
    validate_sft_preview_summary(sft_summary, label=f"{label}.sft_preview_summary")
    if steps[9].get("output") != sft_summary:
        raise ValueError(f"{label}.SFTPreviewAgent output must match trace.sft_preview_summary")


def validate_sft_preview_summary(summary: Dict[str, Any], *, label: str = "sft summary") -> None:
    if summary.get("dataset_type") != "sft_preview":
        raise ValueError(f"{label} must use dataset_type=sft_preview")
    if summary.get("created_for") != "competition_demo":
        raise ValueError(f"{label} must use created_for=competition_demo")
    if summary.get("ready_for_real_training") is not False:
        raise ValueError(f"{label} must use ready_for_real_training=false")
    counts = summary.get("counts") or {}
    if counts.get("real_authorized", 0) != 0:
        raise ValueError(f"{label} must not claim real_authorized samples")
    demo_count = _as_int(counts.get("demo_constructed"), label=f"{label}.counts.demo_constructed")
    if demo_count != len(CASE_ORDER):
        raise ValueError(f"{label} must cover the three demo_constructed cases")
    train_preview_count = _as_int(
        counts.get("train_preview_records"),
        label=f"{label}.counts.train_preview_records",
    )
    if train_preview_count < demo_count:
        raise ValueError(f"{label} must include at least one preview record per demo case")
    validate_no_direct_identifiers(summary, label=label)


def validate_sft_preview_record(record: Dict[str, Any], *, label: str = "sft preview record") -> None:
    validate_demo_preview_asset(record, label=label)
    if "preview" not in str(record.get("task_type", "")):
        raise ValueError(f"{label} task_type must be marked as preview")
    metadata = record.get("metadata") or {}
    if metadata.get("sample_origin") not in (None, "demo_constructed"):
        raise ValueError(f"{label} metadata must not claim real sample origin")
    if metadata.get("for_training") is True or metadata.get("real_authorized") is True:
        raise ValueError(f"{label} metadata must not claim real training authorization")


def validate_sft_preview_bundle(summary: Dict[str, Any], records: List[Dict[str, Any]], *, label: str = "sft preview") -> None:
    validate_sft_preview_summary(summary, label=f"{label}.summary")
    expected = (summary.get("counts") or {}).get("train_preview_records")
    if expected is not None and int(expected) != len(records):
        raise ValueError(f"{label} train record count mismatch: summary={expected}, records={len(records)}")
    for index, record in enumerate(records, start=1):
        validate_sft_preview_record(record, label=f"{label}.record[{index}]")


def validate_eval_preview_summary(summary: str, *, label: str = "eval summary") -> None:
    validate_no_direct_identifiers(summary, label=label)
    required_fragments = (
        "baseline_prompt_preview",
        "demo_constructed",
        "preview",
        "35",
    )
    missing = [fragment for fragment in required_fragments if fragment not in summary]
    boundary_ok = (
        "不代表真实 holdout eval" in summary
        or "not a real holdout eval" in summary
        or "not a holdout eval" in summary
    )
    model_run_ok = "不是真实模型实测" in summary or "not a real model run" in summary
    fine_tune_ok = "fine-tuned model" in summary or "真实微调" in summary
    dimension_ok = "七维" in summary or "7维" in summary or "7 维" in summary or "dimensions=7" in summary
    if missing or not boundary_ok or not model_run_ok or not fine_tune_ok or not dimension_ok:
        raise ValueError(f"{label} must clearly mark demo/preview baseline, 7-dimension score, and non-real-eval boundary")


def validate_eval_score_rows(case_id: str, rows: List[Dict[str, Any]], *, label: str = "eval score rows") -> List[Dict[str, Any]]:
    validate_case_id(case_id)
    validate_no_direct_identifiers(rows, label=label)
    if len(rows) != 2:
        raise ValueError(f"{label} for {case_id} must contain exactly 2 rows")
    variants = [row.get("model_variant") for row in rows]
    if variants != ["baseline_prompt_preview", "agent_optimized"]:
        raise ValueError(f"{label} for {case_id} must use baseline_prompt_preview then agent_optimized")
    for row in rows:
        _validate_eval_score_row(case_id, row, label=label)
    return rows
