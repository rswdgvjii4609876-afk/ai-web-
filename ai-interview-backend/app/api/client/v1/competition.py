from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.schemas.response import ApiResponse
from app.services.agent_orchestrator.asset_guardrails import (
    resolve_asset_path,
    sort_demo_cases,
    validate_demo_preview_asset,
    validate_sft_preview_record,
    validate_sft_preview_summary,
    validate_trace_preview_asset,
)
from app.services.agent_orchestrator.demo_cases import build_demo_case_index, generate_demo_cases
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
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
            for case in cases:
                validate_demo_preview_asset(case, label=f"demo case {case.get('case_id')}")
            if cases:
                return sort_demo_cases(cases)
        except ValueError as exc:
            raise _asset_error(exc) from exc
    return generate_demo_cases()


def _load_agent_trace_data(case_id: str) -> Dict[str, Any]:
    trace_dir = _trace_dir()
    if trace_dir:
        trace_path = trace_dir / f"{case_id}.trace.json"
        if trace_path.exists():
            payload = load_trace(trace_path).model_dump()
            try:
                validate_trace_preview_asset(payload, label=str(trace_path))
            except ValueError as exc:
                raise _asset_error(exc) from exc
            return payload

    cases = build_demo_case_index()
    if case_id not in cases:
        raise HTTPException(status_code=404, detail=f"Unknown demo case: {case_id}")
    payload = run_demo_pipeline(cases[case_id]).model_dump()
    validate_trace_preview_asset(payload, label=f"generated trace {case_id}")
    return payload


def _load_sft_preview() -> Dict[str, Any]:
    sft_dir = _sft_dir()
    if sft_dir and (sft_dir / "summary.preview.json").exists():
        try:
            summary = _read_json(sft_dir / "summary.preview.json")
            validate_sft_preview_summary(summary, label=str(sft_dir / "summary.preview.json"))
            train_path = sft_dir / "train.preview.jsonl"
            preview_records = []
            if train_path.exists():
                for line in train_path.read_text(encoding="utf-8-sig").splitlines():
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    validate_sft_preview_record(record, label=f"{train_path.name}:{len(preview_records) + 1}")
                    preview_records.append(record)
            return {"summary": summary, "preview_records": preview_records[:6]}
        except ValueError as exc:
            raise _asset_error(exc) from exc

    bundle = build_sft_preview_bundle(_load_demo_cases())
    validate_sft_preview_summary(bundle["summary"], label="generated sft summary")
    for record in bundle["train"]:
        validate_sft_preview_record(record, label=f"generated record {record.get('record_id')}")
    return {"summary": bundle["summary"], "preview_records": bundle["train"][:6]}


@router.get("/demo-cases")
async def list_demo_cases():
    return ApiResponse.success(
        data={
            "items": _load_demo_cases(),
            "preview": True,
            "sample_origin": "demo_constructed",
            "for_training": False,
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
    eval_dir = _eval_dir()
    trace = _load_agent_trace_data(case_id)
    if eval_dir and (eval_dir / "eval_summary.md").exists():
        summary = (eval_dir / "eval_summary.md").read_text(encoding="utf-8-sig")
    else:
        summary = (
            "Eval Preview：规则评分，仅用于比赛演示沙盘；"
            "baseline_prompt_preview 不是实际模型调用结果。"
        )
    return ApiResponse.success(
        data={
            "case_id": case_id,
            "eval_score": trace.get("eval_score"),
            "summary": summary,
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
