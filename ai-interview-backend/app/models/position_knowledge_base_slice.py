from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import BaseModel


class PositionKnowledgeBaseSlice(BaseModel):
    __tablename__ = "position_knowledge_base_slices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    knowledge_base_id = Column(
        Integer,
        ForeignKey("position_knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    slice_type = Column(String(50), nullable=False, default="knowledge", index=True)
    source_section = Column(String(50), nullable=True)
    source_scope = Column(String(20), nullable=False, default="private", index=True)
    difficulty = Column(String(20), nullable=False, default="general", index=True)
    priority = Column(Integer, nullable=False, default=5)
    sort_order = Column(Integer, nullable=False, default=0)
    stage_tags = Column(JSONB, nullable=True)
    role_tags = Column(JSONB, nullable=True)
    topic_tags = Column(JSONB, nullable=True)
    skill_tags = Column(JSONB, nullable=True)
    scene_tags = Column(JSONB, nullable=True)
    keywords = Column(JSONB, nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)

    knowledge_base = relationship("PositionKnowledgeBase", back_populates="slices")
