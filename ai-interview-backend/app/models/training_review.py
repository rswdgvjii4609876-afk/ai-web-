from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import BaseModel


class TrainingReview(BaseModel):
    __tablename__ = "training_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "interview_id", name="uq_training_reviews_user_interview"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    self_rating = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    next_goal = Column(Text, nullable=True)

    user = relationship("User", backref="training_reviews")
    interview = relationship("Interview", backref="training_reviews")
