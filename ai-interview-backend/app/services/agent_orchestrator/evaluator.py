from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.services.agent_orchestrator.schemas import AgentTrace, EvalScore


BASELINE_PROMPT_PREVIEW = EvalScore(
    focus_score=3,
    evidence_score=2,
    depth_score=3,
    polish_score=2,
    role_fit_score=3,
    format_score=3,
    report_score=3,
    total_score=19,
    judge_note=(
        "Preview baseline rule score for a generic prompt; "
        "not a real model run, not a holdout eval, and not a fine-tuned model result."
    ),
)


def _collect_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_collect_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_collect_text(v) for v in value)
    return str(value)


def _has_any(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)


def evaluate_trace(trace: AgentTrace) -> EvalScore:
    text = _collect_text([step.output for step in trace.steps])
    agent_names = {step.agent for step in trace.steps}

    focus_score = 5 if _has_any(text, ["能力", "缺口", "目标岗位", "target_ability"]) else 3
    evidence_score = 5 if _has_any(text, ["证据", "缺失", "仅声明", "不得", "不能写成"]) else 3
    depth_score = 5 if _has_any(text, ["场景", "负责", "行动", "结果", "指标"]) else 3
    polish_score = 5 if "ResumePolishAgent" in agent_names or _has_any(text, ["润色", "风险", "补证据", "evidence_constraint"]) else 2
    role_fit_score = 4 if trace.target_role else 3
    format_score = 5 if all(step.agent and isinstance(step.output, dict) for step in trace.steps) else 3
    report_score = 5 if "ReportAgent" in agent_names or _has_any(text, ["报告", "学习任务", "next_actions"]) else 3
    total = sum(
        [
            focus_score,
            evidence_score,
            depth_score,
            polish_score,
            role_fit_score,
            format_score,
            report_score,
        ]
    )
    return EvalScore(
        focus_score=focus_score,
        evidence_score=evidence_score,
        depth_score=depth_score,
        polish_score=polish_score,
        role_fit_score=role_fit_score,
        format_score=format_score,
        report_score=report_score,
        total_score=total,
        judge_note=(
            "Preview rule score for competition demo only; "
            "not a real model run, not a holdout eval, and not a fine-tuned model result."
        ),
    )


def build_eval_rows(traces: List[AgentTrace]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for trace in traces:
        rows.append(
            {
                "case_id": trace.case_id,
                "target_role": trace.target_role,
                "model_variant": "baseline_prompt_preview",
                **BASELINE_PROMPT_PREVIEW.model_dump(),
            }
        )
        score = trace.eval_score or evaluate_trace(trace)
        rows.append(
            {
                "case_id": trace.case_id,
                "target_role": trace.target_role,
                "model_variant": "agent_optimized",
                **score.model_dump(),
            }
        )
    return rows
