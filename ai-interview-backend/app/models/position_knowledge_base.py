from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from .base import BaseModel


class PositionKnowledgeBase(BaseModel):
    __tablename__ = "position_knowledge_bases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=True, index=True)
    scope = Column(String(20), nullable=False, default="private", index=True)
    title = Column(String(255), nullable=False)
    target_position = Column(String(255), nullable=False, index=True)
    knowledge_content = Column(Text, nullable=False)
    focus_points = Column(Text, nullable=True)
    interviewer_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    user = relationship("User", backref="position_knowledge_bases")
    admin = relationship("Admin", backref="managed_position_knowledge_bases")
    interviews = relationship("Interview", back_populates="knowledge_base")
    slices = relationship(
        "PositionKnowledgeBaseSlice",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        order_by="PositionKnowledgeBaseSlice.sort_order"
    )
