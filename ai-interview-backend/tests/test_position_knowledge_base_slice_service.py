import pytest

from app.models.position_knowledge_base import PositionKnowledgeBase
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


def _mock_knowledge_base() -> PositionKnowledgeBase:
    return PositionKnowledgeBase(
        id=101,
        scope="private",
        title="Python Backend Interview KB",
        target_position="Python Backend Engineer",
        knowledge_content=(
            "Project experience: designed and shipped FastAPI, PostgreSQL, and Redis APIs.\n"
            "Key focus: slow SQL diagnosis, cache breakdown handling, async task flows, and incident review."
        ),
        focus_points="Focus on system design, database optimization, async tasks, and high concurrency stability.",
        interviewer_prompt="Keep pushing on project delivery, technical depth, and pressure scenarios.",
        is_active=True,
    )


@pytest.mark.unit
def test_build_slice_payloads_include_structured_metadata():
    knowledge_base = _mock_knowledge_base()

    payloads = position_knowledge_base_slice_service.build_slice_payloads(knowledge_base)

    assert payloads
    assert any(item["source_section"] == "overview" for item in payloads)
    assert any(item["scene_tags"] for item in payloads)
    assert any(item["stage_tags"] for item in payloads)
    assert any(item["role_tags"] for item in payloads)
    assert all("knowledge_base_id" in item for item in payloads)


@pytest.mark.unit
def test_build_slice_payloads_recognize_markdown_sections():
    knowledge_base = PositionKnowledgeBase(
        id=202,
        scope="public",
        title="Python backend structured KB",
        target_position="Python backend engineer",
        knowledge_content=(
            "## 岗位要求\n"
            "- Python / FastAPI / PostgreSQL / Redis.\n"
            "## 问答经验\n"
            "- 问：如何排查接口变慢？答：先看日志、SQL 和缓存命中。\n"
            "## 能力模型\n"
            "- 数据库建模：要求 4 级，关注索引、事务和慢查询。\n"
            "## 面试追问\n"
            "- 简历没有直接证据时，继续追问项目细节和排障过程。\n"
        ),
        focus_points="Focus on evidence.",
        interviewer_prompt="Probe for evidence.",
        is_active=True,
    )

    payloads = position_knowledge_base_slice_service.build_slice_payloads(knowledge_base)
    sections = {item["source_section"] for item in payloads}

    assert {"job_requirements", "interview_experience", "ability_model", "followup_rules"}.issubset(sections)
    assert any(item["source_section"] == "ability_model" and "technical" in item["stage_tags"] for item in payloads)
    assert any(item["source_section"] == "followup_rules" and item["slice_type"] == "prompt" for item in payloads)


@pytest.mark.unit
def test_rank_slices_prefers_stage_role_and_scene_matches():
    slices = [
        {
            "slice_id": 1,
            "content": "Keep probing system design, database optimization, and high-concurrency trade-offs.",
            "priority": 8,
            "stage_tags": ["technical", "scenario"],
            "role_tags": ["technical_deep_dive"],
            "scene_tags": ["technical_depth", "pressure_case"],
            "topic_tags": ["Python Backend Engineer", "system_design"],
            "skill_tags": ["fastapi", "postgres", "redis"],
            "keywords": ["system_design", "high_concurrency", "database_optimization"],
            "source_section": "focus_points",
            "difficulty": "medium",
            "is_enabled": True,
        },
        {
            "slice_id": 2,
            "content": "Focus on self-introduction clarity and communication structure.",
            "priority": 9,
            "stage_tags": ["opening", "behavior"],
            "role_tags": ["behavior_expression"],
            "scene_tags": ["self_intro", "behavior_case"],
            "topic_tags": ["communication"],
            "skill_tags": [],
            "keywords": ["self_intro", "communication"],
            "source_section": "interviewer_prompt",
            "difficulty": "easy",
            "is_enabled": True,
        },
    ]

    ranked = position_knowledge_base_slice_service.rank_slices(
        slices=slices,
        query_text="Keep probing the candidate on high concurrency system design and database trade-offs",
        stage="technical",
        role="technical_deep_dive",
        scene="technical_depth",
        difficulty="medium",
        skills=["fastapi", "redis"],
        topics=["Python Backend Engineer", "system_design"],
        top_k=1,
    )

    assert ranked
    assert ranked[0]["slice_id"] == 1
    assert ranked[0]["routing_score"] > 0
    assert ranked[0]["routing_reasons"]
    assert any("匹配阶段" in item for item in ranked[0]["routing_reasons"])
