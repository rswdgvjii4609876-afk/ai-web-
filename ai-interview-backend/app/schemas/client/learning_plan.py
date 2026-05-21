from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class LearningPlanGenerateRequest(BaseSchema):
    target_position: str = Field(min_length=1, max_length=255)
    abilities: List[Any] = Field(default_factory=list)
    selected_abilities: Optional[List[Any]] = None
    mode: str = Field(default="ai_generate")
    allow_web_search: bool = False
    supplemental_materials: Optional[Any] = None
    resume_id: Optional[int] = None
    interview_id: Optional[int] = None
    previous_plan_id: Optional[int] = None
    mature_plan_group: Optional[str] = None
    plan_days: Optional[int] = Field(default=14, ge=1, le=180)
    daily_minutes: Optional[int] = Field(default=45, ge=5, le=480)
    persist: bool = False


class LearningPlanUpdateRequest(BaseSchema):
    title: Optional[str] = Field(default=None, max_length=255)
    goal: Optional[str] = None
    status: Optional[str] = None
    plan_json: Optional[Dict[str, Any]] = None
