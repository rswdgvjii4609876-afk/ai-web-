from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import BaseModel


class LearningTask(BaseModel):
    __tablename__ = "learning_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "task_key", name="uq_learning_tasks_user_task_key"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_key = Column(String(160), nullable=False)
    title = Column(String(255), nullable=False)
    ability_name = Column(String(255), nullable=True)
    target_position = Column(String(255), nullable=True)
    source_type = Column(String(50), nullable=True)
    source_id = Column(String(255), nullable=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="SET NULL"), nullable=True)
    priority_score = Column(String(50), nullable=True)
    route_source = Column(String(100), nullable=True)
    route_stage = Column(String(100), nullable=True)
    task_type = Column(String(50), nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    due_date = Column(String(20), nullable=True)
    learning_material = Column(Text, nullable=True)
    practice_task = Column(Text, nullable=True)
    acceptance_criteria = Column(JSONB, nullable=True)
    task_metadata = Column(JSONB, nullable=True)
    evidence_basis = Column(Text, nullable=True)
    done = Column(Boolean, nullable=False, default=False, server_default="false")
    note = Column(Text, nullable=True)
    weak_change = Column(Text, nullable=True)

    user = relationship("User", backref="learning_tasks")
    resume = relationship("Resume", backref="learning_tasks")
    interview = relationship("Interview", backref="learning_tasks")
