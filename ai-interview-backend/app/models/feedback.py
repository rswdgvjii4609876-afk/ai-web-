from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Text

from .base import BaseModel


class Feedback(BaseModel):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'replied', 'closed')", name="ck_feedback_status"),
        CheckConstraint("category IN ('issue', 'suggestion', 'other')", name="ck_feedback_category"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(20), nullable=False)
    title = Column(String(80), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    reply = Column(Text, nullable=True)
    replied_by = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
