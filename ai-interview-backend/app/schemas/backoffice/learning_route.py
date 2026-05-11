from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class LearningRouteStageCreate(BaseSchema):
    job_id: Optional[str] = Field(default=None, max_length=100)
    job_name: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    route_source: str = Field(min_length=1, max_length=120)
    route_stage: str = Field(min_length=1, max_length=120)
    route_kind: str = Field(default="template", max_length=30)
    plan_group: Optional[str] = Field(default=None, max_length=120)
    stage_title: str = Field(min_length=1, max_length=255)
    material_type: str = Field(min_length=1, max_length=100)
    task_type: str = Field(min_length=1, max_length=80)
    estimated_minutes: Optional[int] = Field(default=None, ge=1)
    keywords: Optional[List[str]] = None
    learning_material: Optional[str] = None
    practice_task: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    resource_requirement: Optional[str] = None
    generation_prompt: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class LearningRouteStageUpdate(BaseSchema):
    job_id: Optional[str] = Field(default=None, max_length=100)
    job_name: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    route_source: Optional[str] = Field(default=None, max_length=120)
    route_stage: Optional[str] = Field(default=None, max_length=120)
    route_kind: Optional[str] = Field(default=None, max_length=30)
    plan_group: Optional[str] = Field(default=None, max_length=120)
    stage_title: Optional[str] = Field(default=None, max_length=255)
    material_type: Optional[str] = Field(default=None, max_length=100)
    task_type: Optional[str] = Field(default=None, max_length=80)
    estimated_minutes: Optional[int] = Field(default=None, ge=1)
    keywords: Optional[List[str]] = None
    learning_material: Optional[str] = None
    practice_task: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    resource_requirement: Optional[str] = None
    generation_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class LearningRouteStageListQuery(BaseSchema):
    job_id: Optional[str] = None
    category: Optional[str] = None
    task_type: Optional[str] = None
    route_kind: Optional[str] = None
    is_active: Optional[bool] = None
    keyword: Optional[str] = None


class LearningRouteBulkUpsert(BaseSchema):
    version: str = "learning_routes_v1"
    items: List[Dict[str, Any]]


class LearningRoutePreviewTask(BaseSchema):
    route_id: Optional[int] = None
    target_position: Optional[str] = None
    job_id: Optional[str] = None
    category: Optional[str] = None
    ability_name: str = "岗位能力"
    missing_keywords: Optional[List[str]] = None
    include_inactive: bool = False
