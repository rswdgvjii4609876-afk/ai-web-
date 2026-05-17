from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.schemas.response import ApiResponse
from app.services.agent_orchestrator.asset_guardrails import (
    resolve_asset_path,
    validate_case_id,
    validate_demo_case_set,
    validate_eval_preview_summary,
    validate_eval_score_rows,
    validate_sft_preview_bundle,
    validate_trace_preview_asset,
)
from app.services.agent_orchestrator.demo_cases import build_demo_case_index, generate_demo_cases
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.evaluator import BASELINE_PROMPT_PREVIEW
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle
from app.services.agent_orchestrator.trace_logger import load_trace

router = APIRouter()

CLAIM_BOUNDARY = (
    "三岗位案例为 demo_constructed 比赛演示沙盘；for_training=false；"
    "仅用于 Agent Trace、Eval Preview 和 SFT Preview 展示，不代表真实用户训练样本或真实 OpenAI 微调结果。"
)


def _asset_error(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"Invalid competition preview asset: {error}",
    )


def _require_case_id(case_id: str) -> str:
    try:
        return validate_case_id(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _asset_dir(default_relative: str) -> Path | None:
    path = resolve_asset_path("", default_relative)
    return path if path.exists() else None


def _demo_case_dir() -> Path | None:
    return _asset_dir("demo_cases")


def _trace_dir() -> Path | None:
    return _asset_dir("artifacts/agent_trace")


def _eval_dir() -> Path | None:
    return _asset_dir("artifacts/eval")


def _sft_dir() -> Path | None:
    return _asset_dir("artifacts/sft_preview")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_demo_cases() -> List[Dict[str, Any]]:
    case_dir = _demo_case_dir()
    if case_dir:
        try:
            cases = [_read_json(path) for path in sorted(case_dir.glob("*.json"))]
            if cases:
                return validate_demo_case_set(cases)
        except Exception as exc:
            raise _asset_error(exc) from exc
    return generate_demo_cases()


def _load_agent_trace_data(case_id: str) -> Dict[str, Any]:
    case_id = _require_case_id(case_id)
    trace_dir = _trace_dir()
    if trace_dir:
        trace_path = trace_dir / f"{case_id}.trace.json"
        if trace_path.exists():
            try:
                payload = load_trace(trace_path).model_dump()
                if payload.get("case_id") != case_id:
                    raise ValueError(f"{trace_path} case_id does not match requested case_id={case_id}")
                validate_trace_preview_asset(payload, label=str(trace_path))
            except Exception as exc:
                raise _asset_error(exc) from exc
            return payload

    cases = build_demo_case_index()
    payload = run_demo_pipeline(cases[case_id]).model_dump()
    if payload.get("case_id") != case_id:
        raise _asset_error(ValueError(f"generated trace case_id does not match requested case_id={case_id}"))
    validate_trace_preview_asset(payload, label=f"generated trace {case_id}")
    return payload


def _load_eval_summary() -> str:
    eval_dir = _eval_dir()
    if eval_dir and (eval_dir / "eval_summary.md").exists():
        summary = (eval_dir / "eval_summary.md").read_text(encoding="utf-8-sig")
    else:
        summary = (
            "# Eval Preview Summary\n\n"
            "- 样本类型：`demo_constructed`\n"
            "- 评估类型：`preview/demo`\n"
            "- 评分规则：七维规则评分，满分 `35`\n"
            "- 说明：本结果仅用于比赛沙盘展示；`baseline_prompt_preview` 是规则基线，"
            "不是真实模型实测；不代表真实 holdout eval 或 fine-tuned model 结果。\n"
        )
    try:
        validate_eval_preview_summary(summary)
    except ValueError as exc:
        raise _asset_error(exc) from exc
    return summary


def _fallback_eval_score_rows(case_id: str, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    return validate_eval_score_rows(
        case_id,
        [
            {
                "case_id": case_id,
                "target_role": trace.get("target_role"),
                "sample_origin": trace.get("sample_origin", "demo_constructed"),
                "for_training": trace.get("for_training", False),
                "for_competition_demo": trace.get("for_competition_demo", True),
                "preview": True,
                "model_variant": "baseline_prompt_preview",
                **BASELINE_PROMPT_PREVIEW.model_dump(),
            },
            {
                "case_id": case_id,
                "target_role": trace.get("target_role"),
                "sample_origin": trace.get("sample_origin", "demo_constructed"),
                "for_training": trace.get("for_training", False),
                "for_competition_demo": trace.get("for_competition_demo", True),
                "preview": True,
                "model_variant": "agent_optimized",
                **(trace.get("eval_score") or {}),
            },
        ],
        label=f"generated eval score rows for {case_id}",
    )


def _load_eval_score_rows(case_id: str, trace: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    eval_dir = _eval_dir()
    if not eval_dir or not (eval_dir / "eval_score_table.csv").exists():
        return _fallback_eval_score_rows(case_id, trace or _load_agent_trace_data(case_id))
    try:
        with (eval_dir / "eval_score_table.csv").open("r", encoding="utf-8-sig", newline="") as file:
            rows = [row for row in csv.DictReader(file) if row.get("case_id") == case_id]
        return validate_eval_score_rows(case_id, rows, label=str(eval_dir / "eval_score_table.csv"))
    except Exception as exc:
        raise _asset_error(exc) from exc


def _load_sft_preview() -> Dict[str, Any]:
    sft_dir = _sft_dir()
    if sft_dir and (sft_dir / "summary.preview.json").exists():
        try:
            summary = _read_json(sft_dir / "summary.preview.json")
            train_path = sft_dir / "train.preview.jsonl"
            if not train_path.exists():
                raise ValueError(f"{train_path} is required when summary.preview.json exists")
            preview_records = []
            for line in train_path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                preview_records.append(json.loads(line))
            validate_sft_preview_bundle(summary, preview_records, label=str(sft_dir))
            return {"summary": summary, "preview_records": preview_records}
        except Exception as exc:
            raise _asset_error(exc) from exc

    bundle = build_sft_preview_bundle(_load_demo_cases())
    validate_sft_preview_bundle(bundle["summary"], bundle["train"], label="generated sft preview")
    return {"summary": bundle["summary"], "preview_records": bundle["train"]}


@router.get("/demo-cases")
async def list_demo_cases():
    return ApiResponse.success(
        data={
            "items": _load_demo_cases(),
            "preview": True,
            "sample_origin": "demo_constructed",
            "for_training": False,
            "for_competition_demo": True,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    )


@router.get("/agent-trace/{case_id}")
async def get_agent_trace(case_id: str):
    payload = _load_agent_trace_data(case_id)
    payload["claim_boundary"] = CLAIM_BOUNDARY
    return ApiResponse.success(data=payload)


@router.get("/eval-preview/{case_id}")
async def get_eval_preview(case_id: str):
    case_id = _require_case_id(case_id)
    trace = _load_agent_trace_data(case_id)
    return ApiResponse.success(
        data={
            "case_id": case_id,
            "sample_origin": trace.get("sample_origin", "demo_constructed"),
            "for_training": trace.get("for_training", False),
            "for_competition_demo": trace.get("for_competition_demo", True),
            "eval_score": trace.get("eval_score"),
            "score_rows": _load_eval_score_rows(case_id, trace),
            "summary": _load_eval_summary(),
            "preview": True,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    )


@router.get("/sft-preview")
async def get_sft_preview():
    payload = _load_sft_preview()
    payload["preview"] = True
    payload["claim_boundary"] = CLAIM_BOUNDARY
    return ApiResponse.success(data=payload)
