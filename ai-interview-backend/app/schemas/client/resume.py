from typing import Optional, Dict, Any
from pydantic import Field
from ..base import BaseSchema


class ResumeUploadResponse(BaseSchema):
    resume_id: int
    status: str
    message: str


class ResumeDetail(BaseSchema):
    resume_id: int
    status: str
    file_name: Optional[str] = None
    target_position: Optional[str] = None
    parsed_content: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    resume_evidence: Optional[Dict[str, Any]] = None
    evidence_summary: Optional[list[str]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
