from typing import Any, List, Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class LearningPlanGenerateRequest(BaseSchema):
    target_position: str = Field(min_length=1, max_length=255)
    abilities: List[Any] = Field(default_factory=list)
    mode: str = Field(default="ai_generate")
    allow_web_search: bool = False
    supplemental_materials: Optional[Any] = None
    resume_id: Optional[int] = None
    mature_plan_group: Optional[str] = None
