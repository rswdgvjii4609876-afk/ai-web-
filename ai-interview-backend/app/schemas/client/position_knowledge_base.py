from typing import Optional
from pydantic import Field
from ..base import BaseSchema


class PositionKnowledgeBaseCreate(BaseSchema):
    title: str = Field(..., min_length=2, max_length=255)
    target_position: str = Field(..., min_length=2, max_length=255)
    knowledge_content: str = Field(..., min_length=10, max_length=12000)
    focus_points: Optional[str] = Field(default=None, max_length=6000)
    interviewer_prompt: Optional[str] = Field(default=None, max_length=6000)
    is_active: bool = True


class PositionKnowledgeBaseUpdate(BaseSchema):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    target_position: Optional[str] = Field(default=None, min_length=2, max_length=255)
    knowledge_content: Optional[str] = Field(default=None, min_length=10, max_length=12000)
    focus_points: Optional[str] = Field(default=None, max_length=6000)
    interviewer_prompt: Optional[str] = Field(default=None, max_length=6000)
    is_active: Optional[bool] = None


class PositionKnowledgeBaseItem(BaseSchema):
    knowledge_base_id: int
    title: str
    target_position: str
    knowledge_content: str
    scope: str
    source_label: str
    editable: bool
    focus_points: Optional[str] = None
    interviewer_prompt: Optional[str] = None
    is_active: bool
    preview: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
