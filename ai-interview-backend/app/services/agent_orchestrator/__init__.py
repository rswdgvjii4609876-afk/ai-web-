"""Competition demo orchestration utilities for Career-AgentOS."""

from app.services.agent_orchestrator.demo_cases import (
    DEMO_CASES,
    build_demo_case_index,
    generate_demo_cases,
)
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.evaluator import evaluate_trace
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle
from app.services.agent_orchestrator.trace_logger import (
    export_trace_markdown,
    load_trace,
    save_trace,
)

__all__ = [
    "DEMO_CASES",
    "build_demo_case_index",
    "generate_demo_cases",
    "run_demo_pipeline",
    "evaluate_trace",
    "build_sft_preview_bundle",
    "export_trace_markdown",
    "load_trace",
    "save_trace",
]
