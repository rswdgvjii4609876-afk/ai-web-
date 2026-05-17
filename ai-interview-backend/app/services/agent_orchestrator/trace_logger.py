from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.services.agent_orchestrator.schemas import AgentTrace


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def save_trace(trace: AgentTrace, out_dir: Path) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{trace.case_id}.trace.json"
    md_path = out_dir / f"{trace.case_id}.trace.md"
    json_path.write_text(_json_dump(trace.model_dump()), encoding="utf-8")
    md_path.write_text(export_trace_markdown(trace), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def load_trace(path: Path) -> AgentTrace:
    return AgentTrace.model_validate(json.loads(path.read_text(encoding="utf-8")))


def export_trace_markdown(trace: AgentTrace) -> str:
    lines = [
        f"# Career-AgentOS Agent Trace：{trace.target_role}",
        "",
        f"- case_id：`{trace.case_id}`",
        f"- sample_origin：`{trace.sample_origin}`",
        f"- for_training：`{str(trace.for_training).lower()}`",
        f"- for_competition_demo：`{str(trace.for_competition_demo).lower()}`",
        "",
        "> 本 Trace 为比赛演示沙盘和 Preview，不代表真实用户样本或真实 OpenAI 微调结果。",
        "",
    ]
    for step in trace.steps:
        lines.extend([f"## Step {step.step}：{step.title}", "", f"- Agent：`{step.agent}`", ""])
        if step.warnings:
            lines.append("**风险提示**")
            lines.append("")
            lines.extend(f"- {item}" for item in step.warnings)
            lines.append("")
        lines.append("```json")
        lines.append(_json_dump(step.output))
        lines.append("```")
        lines.append("")
    if trace.eval_score:
        lines.extend(["## Eval Preview", "", "```json", _json_dump(trace.eval_score.model_dump()), "```", ""])
    return "\n".join(lines)
