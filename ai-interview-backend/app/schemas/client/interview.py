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
    privacy_agreed: Optional[bool] = None
    data_contribution_consent: Optional[bool] = None


class CaseDataContributionConsentUpdate(BaseSchema):
    data_contribution_consent: bool = Field(
        ...,
        description="是否同意将当前面试案例的去标识化数据用于系统评测、比赛材料、质量改进和数据集沉淀。",
    )


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
    data_contribution_consent: bool = False


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
    resume_id: Optional[int] = None
    target_position: Optional[str] = None
    overall_score: float
    total_questions: int
    interview_mode: Optional[str] = None
    data_contribution_consent: bool = False
    privacy_consent_snapshot: Optional[Dict[str, Any]] = None
    report: Dict[str, Any]


class InterviewListItem(BaseSchema):
    interview_id: int
    target_position: str
    difficulty: str
    interview_mode: str = "single"
    overall_score: Optional[float] = None
    total_questions: int
    status: str
    data_contribution_consent: bool = False
    created_at: Optional[str] = None
