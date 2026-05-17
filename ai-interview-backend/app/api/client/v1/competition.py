from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.schemas.response import ApiResponse
from app.services.agent_orchestrator.demo_cases import build_demo_case_index, generate_demo_cases
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle
from app.services.agent_orchestrator.trace_logger import load_trace

router = APIRouter()


def _candidate_roots() -> List[Path]:
    cwd = Path.cwd()
    here = Path(__file__).resolve()
    return [
        cwd,
        cwd.parent,
        here.parents[5] if len(here.parents) > 5 else cwd,
    ]


def _first_existing(paths: List[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def _demo_case_dir() -> Path | None:
    return _first_existing([root / "demo_cases" for root in _candidate_roots()])


def _trace_dir() -> Path | None:
    return _first_existing([root / "artifacts" / "agent_trace" for root in _candidate_roots()])


def _eval_dir() -> Path | None:
    return _first_existing([root / "artifacts" / "eval" for root in _candidate_roots()])


def _sft_dir() -> Path | None:
    return _first_existing([root / "artifacts" / "sft_preview" for root in _candidate_roots()])


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_demo_cases() -> List[Dict[str, Any]]:
    case_dir = _demo_case_dir()
    if case_dir:
        cases = [_read_json(path) for path in sorted(case_dir.glob("*.json"))]
        if cases:
            return cases
    return generate_demo_cases()


@router.get("/demo-cases")
async def list_demo_cases():
    return ApiResponse.success(
        data={
            "items": _load_demo_cases(),
            "claim_boundary": "三岗位案例为 demo_constructed 比赛演示沙盘，for_training=false，不代表真实用户训练样本。",
        }
    )


@router.get("/agent-trace/{case_id}")
async def get_agent_trace(case_id: str):
    return ApiResponse.success(data=_load_agent_trace_data(case_id))


def _load_agent_trace_data(case_id: str) -> Dict[str, Any]:
    trace_dir = _trace_dir()
    if trace_dir:
        trace_path = trace_dir / f"{case_id}.trace.json"
        if trace_path.exists():
            return load_trace(trace_path).model_dump()

    cases = build_demo_case_index()
    if case_id not in cases:
        raise HTTPException(status_code=404, detail=f"Unknown demo case: {case_id}")
    return run_demo_pipeline(cases[case_id]).model_dump()


@router.get("/eval-preview/{case_id}")
async def get_eval_preview(case_id: str):
    eval_dir = _eval_dir()
    trace = _load_agent_trace_data(case_id)
    if eval_dir and (eval_dir / "eval_summary.md").exists():
        summary = (eval_dir / "eval_summary.md").read_text(encoding="utf-8")
    else:
        summary = "Eval Preview：规则评分，仅用于比赛演示沙盘。"
    return ApiResponse.success(
        data={
            "case_id": case_id,
            "eval_score": trace.get("eval_score"),
            "summary": summary,
            "preview": True,
        }
    )


@router.get("/sft-preview")
async def get_sft_preview():
    sft_dir = _sft_dir()
    if sft_dir and (sft_dir / "summary.preview.json").exists():
        summary = _read_json(sft_dir / "summary.preview.json")
        train_path = sft_dir / "train.preview.jsonl"
        preview_records = [
            json.loads(line)
            for line in train_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][:6] if train_path.exists() else []
    else:
        bundle = build_sft_preview_bundle(_load_demo_cases())
        summary = bundle["summary"]
        preview_records = bundle["train"][:6]
    return ApiResponse.success(data={"summary": summary, "preview_records": preview_records})
