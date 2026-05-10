from typing import Optional

from app.schemas.base import BaseSchema


class TrainingReviewUpdate(BaseSchema):
    self_rating: Optional[str] = None
    notes: Optional[str] = None
    next_goal: Optional[str] = None
