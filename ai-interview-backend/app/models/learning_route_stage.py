from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import BaseModel


class LearningRouteStage(BaseModel):
    __tablename__ = "learning_route_stages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(100), nullable=True, index=True)
    job_name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    route_source = Column(String(120), nullable=False, index=True)
    route_stage = Column(String(120), nullable=False, index=True)
    stage_title = Column(String(255), nullable=False)
    material_type = Column(String(100), nullable=False)
    task_type = Column(String(80), nullable=False, index=True)
    estimated_minutes = Column(Integer, nullable=True)
    keywords = Column(JSONB, nullable=True)
    learning_material = Column(Text, nullable=True)
    practice_task = Column(Text, nullable=True)
    acceptance_criteria = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
