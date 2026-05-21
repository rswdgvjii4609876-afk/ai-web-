from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import BaseModel


class LearningPlan(BaseModel):
    __tablename__ = "learning_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True)
    source_interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="SET NULL"), nullable=True, index=True)
    previous_plan_id = Column(Integer, ForeignKey("learning_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    target_position = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    goal = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft", server_default="draft", index=True)
    plan_days = Column(Integer, nullable=True)
    daily_minutes = Column(Integer, nullable=True)
    selected_abilities = Column(JSONB, nullable=True)
    plan_json = Column(JSONB, nullable=True)
    sources = Column(JSONB, nullable=True)
    generation_backend = Column(String(80), nullable=True)
    web_search_status = Column(String(80), nullable=True)

    user = relationship("User", backref="learning_plans")
    source_resume = relationship("Resume", foreign_keys=[source_resume_id])
    source_interview = relationship("Interview", foreign_keys=[source_interview_id])
    previous_plan = relationship("LearningPlan", remote_side=[id])
    tasks = relationship("LearningTask", back_populates="learning_plan")
