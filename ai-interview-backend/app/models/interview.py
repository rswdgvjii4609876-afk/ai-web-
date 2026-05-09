from sqlalchemy import Column, DECIMAL, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import BaseModel


class Interview(BaseModel):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("position_knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_position = Column(String(255), nullable=True)
    difficulty = Column(String(20), default="medium")
    total_questions = Column(Integer, default=5)
    status = Column(String(20), default="in_progress")
    current_question_index = Column(Integer, default=0)
    interview_mode = Column(String(20), nullable=False, default="single", index=True)
    questions_data = Column(JSONB, nullable=True)
    knowledge_base_snapshot = Column(JSONB, nullable=True)
    panel_snapshot = Column(JSONB, nullable=True)
    overall_score = Column(DECIMAL(3, 1), nullable=True)
    report = Column(Text, nullable=True)

    user = relationship("User", backref="interviews")
    resume = relationship("Resume", back_populates="interviews")
    knowledge_base = relationship("PositionKnowledgeBase", back_populates="interviews")
    messages = relationship(
        "InterviewMessage",
        back_populates="interview",
        order_by="InterviewMessage.id",
    )
