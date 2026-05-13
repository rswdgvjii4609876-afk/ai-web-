import asyncio
import json

import pytest

from app.services.client.ai_service import AIService
from app.services.client.resume_service import resume_service
from app.exceptions.http_exceptions import ValidationError
from app.models.resume import Resume


class _FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, value):
        self.value = value

    async def execute(self, query):
        return _FakeScalarResult(self.value)


@pytest.mark.unit
def test_resume_polish_requires_completed_resume():
    resume = Resume(id=1, user_id=8, status="queued", file_name="resume.pdf")

    async def _run():
        with pytest.raises(ValidationError) as exc:
            await resume_service.polish_resume(
                db=_FakeDb(resume),
                resume_id=1,
                user_id=8,
                ai_config={"provider": "test"},
            )
        assert "完成分析" in exc.value.detail

    asyncio.run(_run())


@pytest.mark.unit
def test_resume_polish_keeps_evidence_constraints(monkeypatch):
    async def _fake_chat(*args, **kwargs):
        return json.dumps(
            {
                "overall_strategy": "强化岗位相关证据，但不新增不存在的经历。",
                "section_suggestions": [
                    {
                        "section": "项目经历",
                        "issue": "Redis 只有技能声明，没有项目证据。",
                        "evidence_basis": "简历技能栏出现 Redis，但项目经历未说明使用场景。",
                        "rewrite_strategy": "保留为待验证能力，并提示补充真实场景。",
                        "rewritten_text": "- Redis：[补充真实项目中的缓存场景、数据一致性处理和排障结果]",
                        "risk_level": "high",
                        "risk_note": "不能写成已主导 Redis 缓存项目。",
                    }
                ],
                "keyword_alignment": [
                    {"keyword": "Redis", "status": "claimed_only", "action": "面试验证"},
                ],
                "risk_warnings": ["不要编造项目指标"],
                "missing_evidence_to_prepare": ["Redis 实际使用场景"],
                "polished_resume_markdown": "## 项目经历\n- Redis：[补充真实项目中的缓存场景]",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(AIService, "_chat", _fake_chat)

    result = asyncio.run(
        AIService.polish_resume(
            parsed_resume={
                "skills": ["Python", "Redis"],
                "projects": [{"name": "课程项目", "description": "Python 数据处理"}],
            },
            analysis={
                "matching_metrics": {
                    "final_score": 62,
                    "keyword_coverage": 45,
                    "verification_needed": ["Redis"],
                },
                "ability_gap_profile": {
                    "top_gaps": [
                        {
                            "name": "缓存与 Redis",
                            "evidence_status": "claimed_only",
                            "evidence_basis": "只有技能声明",
                        }
                    ]
                },
            },
            target_position="Python后端开发工程师",
            resume_evidence={"evidence_summary": ["技能栏声明 Redis"]},
            knowledge_context={
                "sources": [
                    {
                        "title": "成员资料补充：Python后端开发工程师",
                        "target_position": "Python后端开发工程师",
                        "scope": "public",
                        "is_member_submission": True,
                    }
                ],
                "usage_rule": "岗位知识库只用于岗位要求和表达方向，不能写成候选人真实经历。",
            },
            ai_config={"provider": "test"},
        )
    )

    assert result["version"] == "resume_polish_v1"
    assert result["baseline"]["final_score"] == 62
    assert result["section_suggestions"][0]["risk_level"] == "high"
    assert "补充真实项目" in result["polished_resume_markdown"]
    assert "不得新增原简历中不存在" in result["risk_warnings"][0]
    assert result["knowledge_context_summary"]["member_submission_used"] is True
    assert result["knowledge_sources"][0]["title"] == "成员资料补充：Python后端开发工程师"
    assert any("岗位知识库只用于岗位要求" in item for item in result["risk_warnings"])
    assert "已熟练掌握" not in result["polished_resume_markdown"]


@pytest.mark.unit
def test_resume_polish_fallback_uses_ability_gaps_when_ai_payload_sparse():
    result = AIService._normalize_resume_polish_payload(
        payload={},
        target_position="产品助理",
        polish_mode="job_aligned",
        analysis={
            "matching_metrics": {"final_score": 55, "keyword_coverage": 40},
            "ability_gap_profile": {
                "top_gaps": [
                    {
                        "name": "需求分析",
                        "evidence_status": "missing",
                        "evidence_basis": "简历没有 PRD 或需求拆解证据。",
                    }
                ]
            },
        },
    )

    assert result["section_suggestions"]
    assert result["section_suggestions"][0]["section"] == "需求分析"
    assert result["section_suggestions"][0]["risk_level"] == "high"
    assert "[补充真实项目/课程/实习" in result["polished_resume_markdown"]


@pytest.mark.unit
def test_resume_polish_ranks_member_submission_before_generic_public_source():
    member_source = type(
        "KnowledgeSource",
        (),
        {
            "id": 1,
            "user_id": None,
            "scope": "public",
            "title": "成员资料补充：人力资源专员",
            "target_position": "人力资源专员",
            "knowledge_content": "招聘漏斗与候选人沟通面经",
            "focus_points": "",
            "interviewer_prompt": "",
            "updated_at": None,
        },
    )()
    generic_source = type(
        "KnowledgeSource",
        (),
        {
            "id": 2,
            "user_id": None,
            "scope": "public",
            "title": "公共画像：人力资源专员",
            "target_position": "人力资源专员",
            "knowledge_content": "通用岗位要求",
            "focus_points": "",
            "interviewer_prompt": "",
            "updated_at": None,
        },
    )()

    ranked = resume_service._rank_polish_knowledge_sources(
        [generic_source, member_source],
        user_id=8,
        target_position="人力资源专员",
    )

    assert ranked[0].title == "成员资料补充：人力资源专员"
