from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator


class FeedbackCreate(BaseModel):
    category: Literal["issue", "suggestion", "other"]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class FeedbackUpdate(BaseModel):
    status: Literal["replied", "closed"]
    reply: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None

    @model_validator(mode="after")
    def require_reply(self):
        if self.status == "replied" and not self.reply:
            raise ValueError("回复内容不能为空")
        return self
