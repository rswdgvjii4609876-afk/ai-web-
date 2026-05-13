"""Shared resume evaluation snapshot helpers.

This module keeps resume scoring, ability gaps, interview verification,
learning plans, and resume polishing on the same data contract while preserving
the legacy fields that older pages and reports already read.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


RESUME_EVALUATION_VERSION = "resume_evaluation_v1"


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _score(metrics: Dict[str, Any], analysis: Dict[str, Any], key: str) -> Any:
    return metrics.get(key, analysis.get(key))


def _keyword_coverage(metrics: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    coverage = _dict(metrics.get("keyword_coverage") or analysis.get("keyword_coverage"))
    return coverage


def _keyword_evidence(metrics: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    coverage = _keyword_coverage(metrics, analysis)
    return {
        "matched": _list(coverage.get("matched") or metrics.get("matched_keywords")),
        "missing": _list(coverage.get("missing") or metrics.get("missing_keywords") or analysis.get("missing_keywords")),
        "direct_matches": _list(coverage.get("direct_matches") or metrics.get("direct_matches")),
        "related_matches": _list(coverage.get("related_matches") or metrics.get("related_matches")),
        "verification_needed": _list(coverage.get("verification_needed") or metrics.get("verification_needed")),
        "evidence_statuses": _list(coverage.get("evidence_statuses") or metrics.get("evidence_statuses")),
    }


def _ability_profile(metrics: Dict[str, Any], analysis: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return _dict(
        snapshot.get("ability_profile")
        or analysis.get("ability_gap_profile")
        or metrics.get("ability_gap_profile")
    )


def _learning_plan(metrics: Dict[str, Any], analysis: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return _dict(
        snapshot.get("learning_plan")
        or analysis.get("learning_plan")
        or metrics.get("learning_plan")
    )


def _learning_priority(metrics: Dict[str, Any], analysis: Dict[str, Any], snapshot: Dict[str, Any]) -> List[Any]:
    return _list(
        snapshot.get("learning_priority_summary")
        or analysis.get("learning_priority_summary")
        or metrics.get("learning_priority_summary")
    )


def _verification_targets(ability_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = _list(ability_profile.get("top_gaps")) or _list(ability_profile.get("items"))
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    targets: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence_status = item.get("evidence_status") or "needs_verification"
        keywords = [
            str(value).strip()
            for value in [
                *(_list(item.get("verification_keywords"))),
                *(_list(item.get("related_matches"))),
                *(_list(item.get("missing_keywords"))),
            ]
            if str(value).strip()
        ]
        should_verify = (
            evidence_status in {"claimed_only", "indirect", "missing", "needs_verification"}
            or bool(keywords)
        )
        if not should_verify:
            continue
        targets.append(
            {
                "ability_id": item.get("ability_id"),
                "ability_name": item.get("name") or item.get("ability_name") or "岗位关键能力",
                "evidence_status": evidence_status,
                "verification_priority": item.get("verification_priority") or "medium",
                "priority_score": item.get("priority_score") or 0,
                "reason": item.get("interview_probe_reason") or item.get("evidence_basis") or "",
                "keywords": keywords[:8],
                "learning_task_recommended": evidence_status in {"missing", "indirect"},
            }
        )
    return sorted(
        targets,
        key=lambda item: (
            priority_rank.get(str(item.get("verification_priority") or "medium"), 1),
            -float(item.get("priority_score") or 0),
        ),
    )[:12]


def build_resume_evaluation_snapshot(
    *,
    analysis: Optional[Dict[str, Any]] = None,
    matching_metrics: Optional[Dict[str, Any]] = None,
    target_position: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical evaluation snapshot from old and new payload shapes."""

    analysis_payload = _dict(analysis)
    metrics = _dict(matching_metrics or analysis_payload.get("matching_metrics"))
    existing = _dict(analysis_payload.get("resume_evaluation_snapshot"))
    ability_profile = _ability_profile(metrics, analysis_payload, existing)
    learning_plan = _learning_plan(metrics, analysis_payload, existing)
    keyword_coverage = _keyword_coverage(metrics, analysis_payload)
    snapshot = {
        "version": RESUME_EVALUATION_VERSION,
        "target_position": target_position
        or existing.get("target_position")
        or metrics.get("target_position")
        or analysis_payload.get("target_position"),
        "generated_at": existing.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "engine_version": metrics.get("engine_version") or existing.get("engine_version"),
        "matched_profile": _dict(metrics.get("matched_profile") or existing.get("matched_profile")),
        "scores": {
            "final_score": _score(metrics, analysis_payload, "final_score"),
            "keyword_coverage": keyword_coverage,
            "semantic_score": _score(metrics, analysis_payload, "semantic_score"),
            "tfidf_semantic_score": _score(metrics, analysis_payload, "tfidf_semantic_score"),
            "rule_score": _score(metrics, analysis_payload, "rule_score"),
            "llm_score_reference": metrics.get("llm_score_reference"),
        },
        "keyword_evidence": _keyword_evidence(metrics, analysis_payload),
        "ability_profile": ability_profile,
        "learning_priority_summary": _learning_priority(metrics, analysis_payload, existing),
        "learning_plan": learning_plan,
        "verification_targets": _verification_targets(ability_profile),
        "compatibility_fields": [
            "matching_metrics",
            "ability_gap_profile",
            "learning_plan",
        ],
    }
    return snapshot


def ensure_resume_evaluation_snapshot(
    analysis: Optional[Dict[str, Any]],
    *,
    target_position: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a copy of analysis with canonical and legacy fields aligned."""

    payload = deepcopy(_dict(analysis))
    metrics = _dict(payload.get("matching_metrics"))
    snapshot = build_resume_evaluation_snapshot(
        analysis=payload,
        matching_metrics=metrics,
        target_position=target_position,
    )
    payload["resume_evaluation_snapshot"] = snapshot

    ability_profile = _dict(snapshot.get("ability_profile"))
    learning_plan = _dict(snapshot.get("learning_plan"))
    if ability_profile:
        payload.setdefault("ability_gap_profile", ability_profile)
        if metrics and not metrics.get("ability_gap_profile"):
            metrics["ability_gap_profile"] = ability_profile
    if learning_plan:
        payload.setdefault("learning_plan", learning_plan)
        if metrics and not metrics.get("learning_plan"):
            metrics["learning_plan"] = learning_plan
    if snapshot.get("learning_priority_summary"):
        payload.setdefault("learning_priority_summary", snapshot["learning_priority_summary"])
        if metrics and not metrics.get("learning_priority_summary"):
            metrics["learning_priority_summary"] = snapshot["learning_priority_summary"]

    if metrics:
        metrics.setdefault("resume_evaluation_snapshot", snapshot)
        payload["matching_metrics"] = metrics
    return payload


def snapshot_from_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = _dict(payload)
    existing = _dict(data.get("resume_evaluation_snapshot"))
    if existing.get("version") == RESUME_EVALUATION_VERSION:
        return existing
    return build_resume_evaluation_snapshot(analysis=data)


def ability_profile_from_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return _dict(snapshot_from_payload(payload).get("ability_profile"))


def learning_plan_from_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return _dict(snapshot_from_payload(payload).get("learning_plan"))


def matching_metrics_from_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = _dict(payload)
    metrics = deepcopy(_dict(data.get("matching_metrics")))
    snapshot = snapshot_from_payload(data)
    if snapshot:
        metrics.setdefault("resume_evaluation_snapshot", snapshot)
        metrics.setdefault("ability_gap_profile", _dict(snapshot.get("ability_profile")))
        metrics.setdefault("learning_plan", _dict(snapshot.get("learning_plan")))
        metrics.setdefault("learning_priority_summary", _list(snapshot.get("learning_priority_summary")))
    return metrics
