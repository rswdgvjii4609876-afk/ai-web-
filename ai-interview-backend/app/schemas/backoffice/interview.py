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
