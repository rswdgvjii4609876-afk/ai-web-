from typing import Optional

from pydantic import Field

from ..base import BaseSchema


class TrainingSampleReviewUpdate(BaseSchema):
    quality_tier: Optional[str] = Field(default="needs_review", max_length=32)
    is_high_quality: bool = False
    has_hallucination: bool = False
    followup_worthy: bool = False
    report_actionable: bool = False
    notes: Optional[str] = Field(default="", max_length=2000)
    case_id: Optional[str] = Field(default="", max_length=64)
    resume_source: Optional[str] = Field(default="", max_length=255)
    human_overall_score: Optional[float] = Field(default=None, ge=0, le=10)
    evidence_alignment_score: Optional[float] = Field(default=None, ge=0, le=10)
    question_quality_score: Optional[float] = Field(default=None, ge=0, le=10)
    report_actionability_score: Optional[float] = Field(default=None, ge=0, le=10)
    learning_task_actionability_score: Optional[float] = Field(default=None, ge=0, le=10)
    human_score_notes: Optional[str] = Field(default="", max_length=2000)
    dataset_split: Optional[str] = Field(default="", max_length=32)
