from typing import Any, List, Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class LearningTaskUpsert(BaseSchema):
    task_key: Optional[str] = None
    task_id: Optional[str] = None
    title: str = Field(min_length=1, max_length=255)
    ability_name: Optional[str] = None
    target_position: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    resume_id: Optional[int] = None
    interview_id: Optional[int] = None
    priority_score: Optional[Any] = None
    route_source: Optional[str] = None
    route_stage: Optional[str] = None
    task_type: Optional[str] = None
    estimated_minutes: Optional[int] = None
    due_date: Optional[str] = None
    learning_material: Optional[str] = None
    practice_task: Optional[str] = None
    acceptance_criteria: Optional[Any] = None
    task_metadata: Optional[Any] = None
    evidence_basis: Optional[str] = None
    done: Optional[bool] = None
    note: Optional[str] = None
    weak_change: Optional[str] = None


class LearningTaskPatch(BaseSchema):
    title: Optional[str] = None
    ability_name: Optional[str] = None
    target_position: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    resume_id: Optional[int] = None
    interview_id: Optional[int] = None
    priority_score: Optional[Any] = None
    route_source: Optional[str] = None
    route_stage: Optional[str] = None
    task_type: Optional[str] = None
    estimated_minutes: Optional[int] = None
    due_date: Optional[str] = None
    learning_material: Optional[str] = None
    practice_task: Optional[str] = None
    acceptance_criteria: Optional[Any] = None
    task_metadata: Optional[Any] = None
    evidence_basis: Optional[str] = None
    done: Optional[bool] = None
    note: Optional[str] = None
    weak_change: Optional[str] = None


class LearningTaskBulkUpsert(BaseSchema):
    tasks: List[LearningTaskUpsert]
    replace_progress: bool = False
