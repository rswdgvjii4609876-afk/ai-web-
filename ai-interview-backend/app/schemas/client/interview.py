from typing import Any, Dict, Literal, Optional

from pydantic import Field

from app.constants.competition import DEFAULT_TARGET_POSITION

from ..base import BaseSchema


class InterviewStart(BaseSchema):
    resume_id: int
    target_position: str = DEFAULT_TARGET_POSITION
    knowledge_base_id: Optional[int] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    total_questions: int = Field(default=5, ge=3, le=10)
    multi_interviewer_enabled: bool = False


class InterviewStartResponse(BaseSchema):
    interview_id: int
    first_question: str
    question_index: int
    total_questions: int
    knowledge_base_title: Optional[str] = None
    interview_mode: str = "single"
    training_focus: Optional[list[str]] = None
    high_risk_claims: Optional[list[str]] = None
    blueprint_evidence_summary: Optional[list[str]] = None
    interview_blueprint: Optional[Dict[str, Any]] = None


class AnswerSubmit(BaseSchema):
    answer: str = Field(..., min_length=1, max_length=5000)


class AnswerResponse(BaseSchema):
    score: float
    feedback: str
    next_question: Optional[str] = None
    next_question_target_gap: Optional[str] = None
    next_question_reason: Optional[str] = None
    question_index: int
    is_finished: bool
    evidence_summary: Optional[list[str]] = None
    used_slice_ids: Optional[list[int]] = None
    question_target_gap: Optional[str] = None
    question_target_evidence: Optional[list[str]] = None
    question_reason: Optional[str] = None
    evidence_strength_delta: Optional[list[Dict[str, Any]]] = None
    claim_confidence_change: Optional[list[Dict[str, Any]]] = None
    unresolved_gaps: Optional[list[str]] = None
    next_best_followup: Optional[Dict[str, Any]] = None


class QuestionScore(BaseSchema):
    question: str
    score: float
    feedback: str


class InterviewReport(BaseSchema):
    interview_id: int
    overall_score: float
    total_questions: int
    interview_mode: Optional[str] = None
    report: Dict[str, Any]


class InterviewListItem(BaseSchema):
    interview_id: int
    target_position: str
    difficulty: str
    interview_mode: str = "single"
    overall_score: Optional[float] = None
    total_questions: int
    status: str
    created_at: Optional[str] = None
