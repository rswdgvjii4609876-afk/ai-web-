import json
from types import SimpleNamespace

import pytest

from app.exceptions.http_exceptions import ValidationError
from app.services.client.interview_service import InterviewService
from app.services.client.resume_normalizer import normalize_parsed_resume


@pytest.mark.unit
def test_resume_normalizer_accepts_mixed_ai_project_shapes():
    payload = {
        "name": "Yiyu",
        "education": {"school": "Example University", "major": "CS"},
        "skills": [{"skill": "Python", "evidence": "listed"}, "PostgreSQL"],
        "projects": [
            {"title": "HireMate AI 招聘审核", "evidence": "PDF/DOCX parsing, OCR, Streamlit"},
            "Chrome extension with JavaScript",
        ],
        "experience": [{"company": "Example Inc", "role": "Backend Intern"}],
    }
    source_text = "联系方式 yiyu@example.com 13800138000\n项目经历\nHireMate AI 招聘审核\n使用 Python Streamlit OCR PDF DOCX 解析链路"

    normalized = normalize_parsed_resume(payload, source_text=source_text)
    stable = normalized["normalized_resume"]

    assert normalized["name"] == "Yiyu"
    assert stable["profile"]["email"] == "yiyu@example.com"
    assert stable["profile"]["phone"] == "13800138000"
    assert stable["projects"][0]["title"] == "HireMate AI 招聘审核"
    assert "Streamlit" in stable["projects"][0]["technologies"]
    assert any(item["name"] == "PostgreSQL" for item in stable["skills"])
    assert stable["completeness"]["has_projects"] is True


@pytest.mark.unit
def test_interview_load_resume_payload_normalizes_old_resume_and_rejects_empty_content():
    parsed = {
        "skills": ["Python", "SQL"],
        "projects": [{"title": "Backend API", "evidence": "FastAPI SQL project"}],
    }
    resume = SimpleNamespace(parsed_content=json.dumps(parsed, ensure_ascii=False))

    loaded = InterviewService._load_resume_payload(resume)

    assert loaded["normalized_resume"]["completeness"]["has_skills"] is True
    assert "Backend API" in InterviewService._resume_route_text(loaded)

    empty_resume = SimpleNamespace(parsed_content=json.dumps({"name": "Only Name"}, ensure_ascii=False))
    with pytest.raises(ValidationError) as exc:
        InterviewService._load_resume_payload(empty_resume)
    assert "缺少技能" in str(exc.value.detail)
