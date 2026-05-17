from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    ability: str
    resume_evidence: str
    evidence_status: str
    risk: str
    interview_focus: str


class RoleAbility(BaseModel):
    ability: str
    required_level: str
    why_important: str


class GapItem(BaseModel):
    ability: str
    required_level: str
    evidence_status: str
    gap_level: str
    diagnosis: str
    next_question_focus: str


class ResumePolishSuggestion(BaseModel):
    section: str
    original_issue: str
    polish_suggestion: str
    evidence_constraint: str
    missing_evidence_to_prepare: List[str] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    question: str
    target_ability: str
    evidence_focus: str
    reason: str
    expected_answer_elements: List[str]


class EvalScore(BaseModel):
    focus_score: int
    evidence_score: int
    depth_score: int
    polish_score: int
    role_fit_score: int
    format_score: int
    report_score: int
    total_score: int
    judge_note: str


class SFTPreviewRecord(BaseModel):
    record_id: str
    task_type: str
    sample_origin: str = "demo_constructed"
    for_training: bool = False
    for_competition_demo: bool = True
    messages: List[Dict[str, str]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentStep(BaseModel):
    step: int
    agent: str
    title: str
    output: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    trace_id: str
    case_id: str
    target_role: str
    sample_origin: str = "demo_constructed"
    for_training: bool = False
    for_competition_demo: bool = True
    steps: List[AgentStep]
    eval_score: Optional[EvalScore] = None
    sft_preview_summary: Dict[str, Any] = Field(default_factory=dict)
