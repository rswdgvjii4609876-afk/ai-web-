import asyncio
import io
import json
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError

import app.services.client.ai_service as ai_service_module
import app.services.client.interview_service as interview_service_module
from app.core.config import settings
from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.schemas.client.interview import AnswerSubmit, InterviewStartResponse
from app.services.client.ai_service import AIService
from app.services.client.interview_service import InterviewService
from app.services.client.training_review_service import TrainingReviewService


@pytest.mark.unit
def test_answer_submit_requires_question_index():
    with pytest.raises(PydanticValidationError):
        AnswerSubmit(answer="I handled the rollout.")

    payload = AnswerSubmit(answer="I handled the rollout.", question_index=0)
    assert payload.question_index == 0


@pytest.mark.unit
def test_interview_start_response_accepts_panel_start_metadata():
    payload = InterviewStartResponse(
        interview_id=1,
        first_question="请做一个自我介绍。",
        question_index=0,
        total_questions=3,
        requested_interview_mode="panel",
        effective_interview_mode="panel",
        panel_status="active_fallback",
        fallback_reason="panel_question_generation_failed",
        generation_strategy="deterministic_start_fallback",
    )

    assert payload.requested_interview_mode == "panel"
    assert payload.generation_strategy == "deterministic_start_fallback"


@pytest.mark.unit
def test_deterministic_question_fallback_generates_normalizable_questions():
    question_plan = InterviewService._build_question_plan(total_questions=3, difficulty="medium")
    parsed_resume = {
        "projects": [{"title": "Career-AgentOS", "evidence": "multi-agent interview workflow"}],
        "skills": [{"skill": "Python"}],
    }

    raw_questions = InterviewService._build_deterministic_question_fallback(
        question_plan=question_plan,
        parsed_resume=parsed_resume,
        target_position="产品助理/产品经理实习生",
        total_questions=3,
    )
    normalized = InterviewService._normalize_questions(
        raw_questions=raw_questions,
        question_plan=question_plan,
        interview_mode="single",
    )

    assert len(raw_questions) == 3
    assert len(normalized) == 3
    assert "Career-AgentOS" in raw_questions[1]["question"]
    assert normalized[0]["panel_context"]["metadata"]["fallback_reason"] == "question_generation_failed"


@pytest.mark.unit
def test_question_plan_uses_distinct_difficulty_profiles():
    easy_plan = InterviewService._build_question_plan(total_questions=5, difficulty="easy")
    medium_plan = InterviewService._build_question_plan(total_questions=5, difficulty="unknown")
    hard_plan = InterviewService._build_question_plan(total_questions=5, difficulty="hard")

    assert medium_plan[0]["difficulty_level"] == "medium"
    assert easy_plan[1]["template_key"] == "basic_knowledge"
    assert hard_plan[2]["template_key"] == "system_design_depth"
    assert hard_plan[4]["template_key"] == "rag_optimization"
    assert easy_plan[0]["routing_top_k"] < hard_plan[0]["routing_top_k"]
    assert easy_plan[0]["followup_depth"] == "basic"
    assert hard_plan[0]["followup_depth"] == "pressure"


@pytest.mark.unit
def test_hard_rag_question_is_gated_by_resume_or_role_signal():
    hard_plan = InterviewService._build_question_plan(total_questions=5, difficulty="hard")

    routed_without_rag = InterviewService._route_question_plan(
        question_plan=hard_plan,
        knowledge_base={
            "title": "Generic backend knowledge base",
            "knowledge_content": "RAG embedding rerank retrieval augmented generation",
            "focus_points": "Use knowledge-base slices only as reference material.",
            "slices": [
                {
                    "slice_id": 1,
                    "content": "RAG embedding rerank retrieval augmented generation",
                    "priority": 10,
                    "stage_tags": ["technical"],
                    "role_tags": ["technical_deep_dive"],
                    "scene_tags": ["technical_depth"],
                    "topic_tags": ["RAG"],
                    "skill_tags": ["rag", "embedding"],
                    "keywords": ["rerank", "retrieval"],
                    "source_section": "interview_experience",
                    "difficulty": "hard",
                    "is_enabled": True,
                }
            ],
        },
        parsed_resume={
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "projects": [{"title": "Backend API", "description": "REST API and database work"}],
        },
        target_position="Python Backend Engineer",
        difficulty="hard",
    )

    assert routed_without_rag[4]["template_key"] == "system_design_depth"
    assert routed_without_rag[4]["rag_gate_replaced"] is True
    assert routed_without_rag[4]["rag_signal_present"] is False

    routed_with_rag = InterviewService._route_question_plan(
        question_plan=hard_plan,
        knowledge_base=None,
        parsed_resume={
            "skills": ["Python", "RAG", "embedding", "rerank"],
            "projects": [{"title": "LLM knowledge base", "description": "Built retrieval and reranking"}],
        },
        target_position="RAG Engineer",
        difficulty="hard",
    )

    assert routed_with_rag[4]["template_key"] == "rag_optimization"
    assert routed_with_rag[4]["rag_signal_present"] is True


@pytest.mark.unit
def test_deterministic_fallback_keeps_difficulty_metadata():
    question_plan = InterviewService._build_question_plan(total_questions=5, difficulty="hard")
    routed_plan = InterviewService._route_question_plan(
        question_plan=question_plan,
        knowledge_base=None,
        parsed_resume={
            "skills": ["Python", "RAG", "embedding"],
            "projects": [{"title": "LLM search service"}],
        },
        target_position="RAG Engineer",
        difficulty="hard",
    )

    raw_questions = InterviewService._build_deterministic_question_fallback(
        question_plan=routed_plan,
        parsed_resume={"projects": [{"title": "LLM search service"}]},
        target_position="RAG Engineer",
        total_questions=5,
    )

    assert len(raw_questions) == 5
    assert raw_questions[0]["difficulty_level"] == "hard"
    assert raw_questions[0]["routing_top_k"] == 4
    assert raw_questions[0]["panel_context"]["metadata"]["difficulty_profile"]["level"] == "hard"
    assert raw_questions[4]["category"] == "system-design"
    assert not InterviewService._question_has_internal_prompt_leak(raw_questions[4]["question"])


@pytest.mark.unit
def test_hard_short_deterministic_fallback_keeps_system_design_depth():
    question_plan = InterviewService._build_question_plan(total_questions=3, difficulty="hard")

    raw_questions = InterviewService._build_deterministic_question_fallback(
        question_plan=question_plan,
        parsed_resume={"projects": [{"title": "Backend API"}], "skills": ["Python", "FastAPI"]},
        target_position="Python Backend Engineer",
        total_questions=3,
    )

    assert len(raw_questions) == 3
    assert raw_questions[2]["category"] == "system-design"
    assert raw_questions[2]["difficulty_level"] == "hard"
    assert not InterviewService._question_has_internal_prompt_leak(raw_questions[2]["question"])


@pytest.mark.unit
def test_medium_short_deterministic_fallback_keeps_technical_core():
    question_plan = InterviewService._build_question_plan(total_questions=3, difficulty="medium")

    raw_questions = InterviewService._build_deterministic_question_fallback(
        question_plan=question_plan,
        parsed_resume={"projects": [{"title": "Backend API"}], "skills": ["Python", "FastAPI"]},
        target_position="Python Backend Engineer",
        total_questions=3,
    )

    assert raw_questions[2]["category"] == "technical"
    assert raw_questions[2]["difficulty_level"] == "medium"
    assert not InterviewService._question_has_internal_prompt_leak(raw_questions[2]["question"])


@pytest.mark.unit
def test_panel_start_falls_back_without_single_question_llm(monkeypatch):
    resume = SimpleNamespace(
        id=10,
        user_id=3,
        status="completed",
        parsed_content=json.dumps(
            {
                "name": "Demo",
                "skills": ["Python", "FastAPI"],
                "projects": [{"title": "Backend API", "description": "Built APIs"}],
            }
        ),
        analysis=json.dumps({"overall_score": 7, "resume_evidence": {"evidence_summary": ["Built APIs"]}}),
        target_position="Python backend engineer",
    )

    class _Result:
        def __init__(self, value=None):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

        def first(self):
            return self.value

    class _Db:
        def __init__(self):
            self.results = [_Result(resume), _Result(None), _Result(None)]
            self.added = []
            self.commit_count = 0

        async def execute(self, _statement):
            return self.results.pop(0)

        def add(self, item):
            if item.__class__.__name__ == "Interview":
                item.id = 123
            self.added.append(item)

        async def commit(self):
            self.commit_count += 1

        async def rollback(self):
            return None

        async def refresh(self, item):
            item.id = item.id or 123

    async def _blueprint_should_not_run(**kwargs):
        raise AssertionError("panel start should use local blueprint fallback")

    async def _panel_questions(**kwargs):
        assert kwargs.get("allow_json_repair") is False
        raise ValueError("bad panel json")

    async def _single_questions_should_not_run(**kwargs):
        raise AssertionError("panel fallback must not call single question LLM")

    monkeypatch.setattr(AIService, "extract_interview_blueprint", _blueprint_should_not_run)
    monkeypatch.setattr(AIService, "generate_panel_questions", _panel_questions)
    monkeypatch.setattr(AIService, "generate_questions", _single_questions_should_not_run)

    async def _run():
        return await InterviewService.start_interview(
            db=_Db(),
            user_id=3,
            resume_id=10,
            target_position="Python backend engineer",
            knowledge_base_id=None,
            difficulty="medium",
            total_questions=3,
            multi_interviewer_enabled=True,
            ai_config={"api_key": "test", "provider": "deepseek"},
        )

    result = asyncio.run(_run())

    assert result["interview_mode"] == "panel"
    assert result["effective_interview_mode"] == "panel"
    assert result["requested_interview_mode"] == "panel"
    assert result["generation_strategy"] == "deterministic_start_fallback"
    assert result["panel_status"] == "active_fallback"
    assert result["fallback_reason"] == "panel_question_generation_failed"
    assert result["difficulty_profile"]["level"] == "medium"
    assert result["company_archetype"] == result["difficulty_profile"]["company_archetype"]
    assert result["question_strategy_summary"]
    assert result["rubric_summary"]
    assert result["first_question"]


@pytest.mark.unit
def test_blueprint_priority_stays_out_of_question_intent():
    question_plan = InterviewService._build_question_plan(total_questions=4, difficulty="medium")
    enriched = InterviewService._apply_blueprint_to_question_plan(
        question_plan=question_plan,
        interview_blueprint={
            "priority_question_tracks": [
                {
                    "track": "追问表述模糊的经历，确认候选人是主导、负责还是参与支持",
                    "requirement_status": "weak",
                    "reason": "candidate ownership needs verification",
                    "evidence_ids": [1],
                }
            ],
            "training_focus": ["验证项目主导程度"],
            "blueprint_evidence": {"resume_evidence_summary": ["HireMate project"]},
        },
    )

    assert enriched[0]["blueprint_track"]
    assert "Blueprint priority" not in enriched[0]["intent"]


@pytest.mark.unit
def test_deterministic_question_fallback_does_not_expose_internal_intent():
    question_plan = InterviewService._build_question_plan(total_questions=5, difficulty="hard")
    question_plan[3]["intent"] = (
        "Assess boundary awareness and trade-offs under pressure. "
        "Blueprint priority: 追问表述模糊的经历。"
    )
    question_plan[4]["intent"] = (
        "Place the candidate in a realistic business scenario to test execution quality."
    )

    raw_questions = InterviewService._build_deterministic_question_fallback(
        question_plan=question_plan,
        parsed_resume={"projects": [{"title": "HireMate"}]},
        target_position="Python后端开发工程师",
        total_questions=5,
    )
    visible_text = "\n".join(item["question"] for item in raw_questions)

    assert "Blueprint priority" not in visible_text
    assert "Assess boundary awareness" not in visible_text
    assert "Place the candidate" not in visible_text


@pytest.mark.unit
def test_all_question_template_intents_are_treated_as_internal_prompt_text():
    from app.services.client.interview_service import QUESTION_TEMPLATES

    for item in QUESTION_TEMPLATES.values():
        assert InterviewService._question_has_internal_prompt_leak(item["intent"])


@pytest.mark.unit
def test_normalize_questions_redacts_internal_prompt_leak():
    question_plan = InterviewService._build_question_plan(total_questions=2, difficulty="medium")
    raw_questions = [
        {
            "question": "Blueprint priority: 追问表述模糊的经历，确认候选人是主导、负责还是参与支持。",
            "category": "scenario",
        },
        {
            "question": "Place the candidate in a realistic business scenario to test execution quality.",
            "category": "scenario",
        },
    ]

    normalized = InterviewService._normalize_questions(
        raw_questions=raw_questions,
        question_plan=question_plan,
        interview_mode="single",
    )

    for item in normalized:
        assert "Blueprint priority" not in item["question"]
        assert "Place the candidate" not in item["question"]
        assert item["panel_context"]["metadata"]["question_sanitized_reason"] == "internal_prompt_leak"
        assert item["panel_context"]["metadata"]["original_question_redacted"] is True


@pytest.mark.unit
def test_normalize_questions_redacts_chinese_internal_prompt_leak():
    question_plan = InterviewService._build_question_plan(total_questions=1, difficulty="medium")
    raw_questions = [
        {
            "question": "题目计划：按评估重点验证候选人证据，主持人推理不要展示。",
            "category": "scenario",
        }
    ]

    normalized = InterviewService._normalize_questions(
        raw_questions=raw_questions,
        question_plan=question_plan,
        interview_mode="single",
    )

    assert normalized[0]["question"] != raw_questions[0]["question"]
    assert normalized[0]["panel_context"]["metadata"]["question_sanitized_reason"] == "internal_prompt_leak"


@pytest.mark.unit
def test_normalize_questions_redacts_new_routing_context_labels():
    question_plan = InterviewService._build_question_plan(total_questions=2, difficulty="medium")
    raw_questions = [
        {
            "question": (
                "Plan #1: step=scenario, type=system-design, lead_role=interviewer, "
                "assessment_points: boundary awareness, priority: verify ownership."
            ),
            "question_target_gap": "goal: hidden routing objective",
            "question_reason": "Interview routing context: internal plan",
            "selected_followups": ["used_slice_ids=[1,2]", "Please describe one concrete example."],
        },
        {
            "question": "Internal panel mode enabled. Moderator name: chief interviewer. focus=ownership.",
            "panel_context": {
                "moderator": {
                    "selected_question": "Internal roles: Lead role: coach. Support roles: evaluator.",
                    "selected_followups": ["selected_questions: hidden", "Please continue with specifics."],
                }
            },
        },
    ]

    normalized = InterviewService._normalize_questions(
        raw_questions=raw_questions,
        question_plan=question_plan,
        interview_mode="panel",
    )

    for item in normalized:
        assert not InterviewService._question_has_internal_prompt_leak(item["question"])
        assert not InterviewService._question_has_internal_prompt_leak(item.get("question_target_gap"))
        assert not InterviewService._question_has_internal_prompt_leak(item.get("question_reason"))
        assert item["panel_context"]["metadata"]["question_sanitized_reason"] == "internal_prompt_leak"
    assert normalized[0]["selected_followups"] == ["Please describe one concrete example."]
    assert normalized[1]["panel_context"]["moderator"]["selected_followups"] == ["Please continue with specifics."]
    assert not InterviewService._question_has_internal_prompt_leak(
        normalized[1]["panel_context"]["moderator"]["selected_question"]
    )


@pytest.mark.unit
def test_normalize_questions_sanitizes_derived_visible_fields_and_panel_context():
    question_plan = InterviewService._build_question_plan(total_questions=1, difficulty="medium")
    question_plan[0]["intent"] = "Assess boundary awareness and trade-offs under pressure."
    raw_questions = [
        {
            "question": "请介绍一个你主导的项目。",
            "question_target_gap": "evaluation_focus: hidden internal rubric",
            "question_reason": "Question plan: internal moderator note",
            "selected_followups": [
                "Blueprint priority: verify ambiguous ownership claims.",
                "请补充一个具体取舍。",
            ],
            "panel_context": {
                "moderator": {
                    "selected_question": "Place the candidate in a realistic business scenario.",
                    "selected_followups": ["selected_followups: hidden", "请继续说明。"],
                }
            },
        }
    ]

    normalized = InterviewService._normalize_questions(
        raw_questions=raw_questions,
        question_plan=question_plan,
        interview_mode="panel",
    )
    item = normalized[0]

    assert not InterviewService._question_has_internal_prompt_leak(item["question"])
    assert not InterviewService._question_has_internal_prompt_leak(item.get("question_target_gap"))
    assert not InterviewService._question_has_internal_prompt_leak(item.get("question_reason"))
    assert item["selected_followups"] == ["请补充一个具体取舍。"]
    assert not InterviewService._question_has_internal_prompt_leak(
        item["panel_context"]["moderator"]["selected_question"]
    )
    assert item["panel_context"]["moderator"]["selected_followups"] == ["请继续说明。"]
    assert item["panel_context"]["metadata"]["question_sanitized_reason"] == "internal_prompt_leak"


@pytest.mark.unit
def test_round_evaluation_public_fields_sanitize_raw_next_best_followup():
    evaluation = {
        "selected_followups": [
            "Blueprint priority: verify ambiguous ownership claims.",
            "请补充一个具体取舍。",
        ],
        "next_best_followup": {
            "question": "Assess boundary awareness and trade-offs under pressure.",
            "reason": "Question plan: internal moderator note",
            "target_gap": "evaluation_focus: hidden internal rubric",
            "target_evidence": ["schema: hidden", "候选人提到了项目取舍。"],
        },
        "moderator": {
            "selected_followups": ["selected_followups: hidden", "请继续说明。"],
            "next_best_followup": {
                "question": "Place the candidate in a realistic business scenario.",
                "reason": "Question reason: hidden",
            },
        },
        "unresolved_gaps": ["evaluation_focus: hidden", "缺少量化结果"],
    }

    cleaned = InterviewService._sanitize_round_evaluation_public_fields(
        evaluation,
        fallback_question="请补充一个具体例子。",
    )

    assert cleaned["selected_followups"] == ["请补充一个具体取舍。"]
    assert cleaned["next_best_followup"]["question"] == "请补充一个具体例子。"
    assert cleaned["next_best_followup"].get("reason") is None
    assert cleaned["next_best_followup"].get("target_gap") is None
    assert cleaned["next_best_followup"]["target_evidence"] == ["候选人提到了项目取舍。"]
    assert cleaned["moderator"]["selected_followups"] == ["请继续说明。"]
    assert cleaned["moderator"]["next_best_followup"]["question"] == "请补充一个具体例子。"
    assert cleaned["unresolved_gaps"] == ["缺少量化结果"]


@pytest.mark.unit
def test_merge_report_defaults_diagnoses_non_object_report_payload():
    report = InterviewService._merge_report_defaults(
        report=["bad"],
        report_signals={
            "common_gaps": ["缺少量化结果"],
            "common_strengths": ["表达结构清晰"],
            "training_priorities": ["补充 STAR 案例"],
        },
        interview_mode="single",
    )

    assert report["weaknesses"] == ["缺少量化结果"]
    assert report["strengths"] == ["表达结构清晰"]
    assert report["report_diagnostics"][0]["reason"] == "invalid_report_payload_type"


@pytest.mark.unit
def test_apply_followup_to_next_question_rewrites_next_round_with_moderator_choice():
    current_question_meta = {
        "index": 1,
        "question": "Tell me about the cache architecture.",
        "intent": "Assess system design depth.",
        "question_target_gap": "Trade-off clarity",
        "question_target_evidence": ["Cache degradation design evidence"],
        "question_target_evidence_ids": [21],
        "panel_context": {
            "moderator": {
                "selected_question": "Tell me about the cache architecture.",
                "selected_followups": [],
            }
        },
    }
    next_question_meta = {
        "index": 2,
        "question": "Original next question",
        "intent": "Assess trade-offs.",
        "evaluation_focus": ["trade-offs"],
        "category": "technical_depth",
    }
    evaluation = {
        "gaps": ["trade-off clarity"],
        "next_focus": "Explain failover and degradation.",
        "moderator": {
            "selected_followups": [
                "If Redis is unavailable, how do you degrade gracefully?",
                "What metrics would you watch first?",
            ],
            "next_best_followup": {
                "question": "If Redis is unavailable, how do you degrade gracefully?",
                "target_gap": "Trade-off clarity",
                "target_evidence": ["Cache degradation design evidence"],
                "evidence_source_ids": [21],
                "evidence_source_summary": ["Architecture slice matched degradation strategy"],
                "reason": "Need to verify whether the candidate can explain the degradation decision in concrete terms.",
            },
            "reasoning_summary": "Continue the strongest thread with a tighter follow-up.",
            "difficulty_hint": "medium",
        },
    }

    rewritten = InterviewService._apply_followup_to_next_question(
        current_question_meta=current_question_meta,
        next_question_meta=next_question_meta,
        evaluation=evaluation,
    )

    assert rewritten["question"] == "If Redis is unavailable, how do you degrade gracefully?"
    assert rewritten["selected_followups"] == ["What metrics would you watch first?"]
    assert rewritten["followup_source_question_index"] == 1
    assert rewritten["is_dynamic_followup"] is True
    assert rewritten["intent"] == "Explain failover and degradation."
    assert rewritten["evaluation_focus"] == ["trade-off clarity"]
    assert rewritten["question_target_gap"] == "Trade-off clarity"
    assert rewritten["question_target_evidence"] == ["Cache degradation design evidence"]
    assert rewritten["question_target_evidence_ids"] == [21]
    assert rewritten["question_reason"] == "Need to verify whether the candidate can explain the degradation decision in concrete terms."
    assert rewritten["panel_context"]["moderator"]["next_best_followup"]["evidence_source_ids"] == [21]
    assert rewritten["panel_context"]["moderator"]["selected_question"] == rewritten["question"]


@pytest.mark.unit
def test_apply_followup_to_next_question_redacts_internal_prompt_leaks():
    current_question_meta = {
        "index": 3,
        "question": "Describe your project ownership.",
        "intent": "Assess ownership.",
        "panel_context": {"moderator": {}},
    }
    next_question_meta = {
        "index": 4,
        "question": "Original next question",
        "category": "scenario",
    }
    evaluation = {
        "moderator": {
            "selected_followups": [
                "Blueprint priority: verify ambiguous ownership claims.",
                "Please describe one concrete implementation trade-off.",
                "Which production signal would you watch first?",
            ],
            "next_best_followup": {
                "question": "Assess boundary awareness and trade-offs under pressure.",
                "target_gap": "evaluation_focus: hidden internal rubric",
                "reason": "Question plan: internal moderator note",
            },
        }
    }

    rewritten = InterviewService._apply_followup_to_next_question(
        current_question_meta=current_question_meta,
        next_question_meta=next_question_meta,
        evaluation=evaluation,
    )

    assert rewritten["question"] == "Please describe one concrete implementation trade-off."
    assert rewritten["selected_followups"] == ["Which production signal would you watch first?"]
    assert not InterviewService._question_has_internal_prompt_leak(rewritten["question"])
    assert not InterviewService._question_has_internal_prompt_leak(
        rewritten["panel_context"]["moderator"]["next_best_followup"]["question"]
    )
    assert not InterviewService._question_has_internal_prompt_leak(rewritten.get("question_target_gap"))
    assert not InterviewService._question_has_internal_prompt_leak(rewritten.get("question_reason"))
    assert (
        rewritten["panel_context"]["metadata"]["question_sanitized_reason"]
        == "internal_prompt_leak"
    )
    assert rewritten["panel_context"]["metadata"]["original_question_redacted"] is True


@pytest.mark.unit
def test_reroute_question_slices_and_report_signals_capture_round_metadata():
    question_meta = {
        "index": 1,
        "question": "How would you design the cache and database access path?",
        "stage": "technical",
        "lead_role": "technical_deep_dive",
        "category": "technical_depth",
        "intent": "Probe technical depth.",
        "evaluation_focus": ["system design", "trade-offs"],
    }
    knowledge_base = {
        "slices": [
            {
                "slice_id": 11,
                "title": "High concurrency cache design",
                "content": "Focus on cache breakdown, graceful degradation, SQL hotspots, and Redis trade-offs.",
                "priority": 9,
                "stage_tags": ["technical", "scenario"],
                "role_tags": ["technical_deep_dive"],
                "scene_tags": ["technical_depth", "pressure_case"],
                "topic_tags": ["Python Backend Engineer", "system_design"],
                "skill_tags": ["fastapi", "redis", "postgres"],
                "keywords": ["cache_breakdown", "sql_hotspot", "graceful_degradation"],
                "source_section": "focus_points",
                "difficulty": "medium",
                "is_enabled": True,
            },
            {
                "slice_id": 12,
                "title": "Communication basics",
                "content": "Focus on self-introduction and communication structure.",
                "priority": 3,
                "stage_tags": ["opening"],
                "role_tags": ["behavior_expression"],
                "scene_tags": ["self_intro"],
                "topic_tags": ["communication"],
                "skill_tags": [],
                "keywords": ["communication"],
                "source_section": "overview",
                "difficulty": "easy",
                "is_enabled": True,
            },
        ]
    }
    parsed_resume = {
        "skills": ["fastapi", "redis"],
        "projects": ["cache platform", "task scheduler"],
    }

    routed = InterviewService._reroute_question_slices(
        question_meta=question_meta,
        knowledge_base=knowledge_base,
        parsed_resume=parsed_resume,
        target_position="Python Backend Engineer",
        difficulty="medium",
        context_terms=["graceful degradation", "sql hotspot"],
    )

    selected_ids = [item["slice_id"] for item in routed["selected_slices"]]
    assert selected_ids[0] == 11
    assert 11 in selected_ids
    assert 11 in routed["used_slice_ids"]
    assert 11 in routed["panel_context"]["metadata"]["retrieved_slice_ids"]
    assert routed["selected_slices"][0]["grounding_confidence"] in {"high", "medium"}
    assert routed["selected_slices"][0]["routing_heads"]["skill_topic"] > 0
    assert routed["panel_context"]["metadata"]["grounding_confidence_summary"]["counts"]["high"] >= 1
    assert routed["evidence_summary"]
    assert routed["evidence_trace"]
    assert routed["evidence_trace"][0]["reason_summary"]
    assert routed["evidence_trace"][0]["grounding_confidence"] in {"high", "medium"}

    questions = [
        {
            **routed,
            "evaluation": {
                "gaps": ["trade-off clarity", "trade-off clarity"],
                "unresolved_gaps": ["trade-off clarity"],
                "strengths": ["technical depth"],
                "next_focus": "quantify degradation strategy",
                "evidence_strength_delta": [
                    {
                        "evidence": "Cache degradation design evidence",
                        "delta": "strengthened",
                        "reason": "The answer clarified the degradation sequence.",
                    }
                ],
                "claim_confidence_change": [
                    {
                        "claim": "Led the cache redesign",
                        "from_level": "medium",
                        "to_level": "high",
                        "change": "increased",
                        "reason": "The answer added direct ownership details.",
                    }
                ],
                "next_best_followup": {
                    "question": "How did you quantify the degradation budget?",
                    "target_gap": "trade-off clarity",
                    "reason": "Need one more concrete metric for the degradation path.",
                },
                "panel_views": [
                    {"role": "technical_deep_dive", "summary": "Strong architecture depth."},
                    {"role": "project_follow_up", "summary": "Need clearer ownership boundaries."},
                ],
            },
        },
        {
            "question": "How did you coordinate rollout?",
            "used_slice_ids": [11, 15],
            "evaluation": {
                "gaps": ["ownership clarity"],
                "unresolved_gaps": ["ownership clarity"],
                "strengths": ["clear communication"],
                "next_focus": "describe rollout metrics",
                "evidence_strength_delta": [
                    {
                        "evidence": "Rollout ownership evidence",
                        "delta": "insufficient",
                        "reason": "The answer still lacked measurable rollout ownership.",
                    }
                ],
                "next_best_followup": {
                    "question": "Which rollout metrics did you personally monitor?",
                    "target_gap": "ownership clarity",
                    "reason": "Need direct proof of operational ownership.",
                },
                "panel_views": [
                    {"role": "project_follow_up", "summary": "Need clearer ownership boundaries."}
                ],
            },
        },
    ]

    report_signals = InterviewService._build_report_signals(questions)
    merged_report = InterviewService._merge_report_defaults({}, report_signals, "panel")

    assert report_signals["common_gaps"][0] == "trade-off clarity"
    assert report_signals["retrieved_slice_ids"][0] == 11
    assert set(report_signals["retrieved_slice_ids"]) == {11, 12, 15}
    assert "quantify degradation strategy" in report_signals["training_priorities"]
    assert "trade-off clarity" in report_signals["training_priorities"]
    assert any(item["role"] == "technical_deep_dive" for item in report_signals["panel_summary"])
    assert report_signals["common_strengths"][0] == "technical depth"
    assert report_signals["evidence_summary"]
    assert report_signals["grounding_confidence_summary"]["counts"]["high"] >= 1
    assert report_signals["followup_loop_summary"]
    assert report_signals["claim_confidence_summary"]
    assert merged_report["evidence_summary"] == report_signals["evidence_summary"]
    assert merged_report["common_gaps"] == report_signals["common_gaps"]
    assert merged_report["common_strengths"] == report_signals["common_strengths"]
    assert merged_report["followup_loop_summary"] == report_signals["followup_loop_summary"]
    assert merged_report["claim_confidence_summary"] == report_signals["claim_confidence_summary"]
    assert merged_report["grounding_confidence_summary"] == report_signals["grounding_confidence_summary"]
    assert merged_report["panel_summary"] == report_signals["panel_summary"]


@pytest.mark.unit
def test_reroute_question_slices_sanitizes_rederived_public_fields():
    question_meta = {
        "index": 1,
        "question": "Please describe one concrete backend trade-off.",
        "stage": "scenario",
        "lead_role": "technical_deep_dive",
        "category": "system-design",
        "intent": "Plan #1: step=scenario, type=system-design, lead_role=technical_deep_dive",
        "evaluation_focus": ["Interview routing context: internal assessment_points"],
        "question_target_gap": "Candidate evidence target: hidden routing objective",
        "question_reason": "Lead role: hidden internal role",
    }
    knowledge_base = {
        "slices": [
            {
                "slice_id": 21,
                "title": "Backend trade-off",
                "content": "Discuss latency, reliability, async tasks, Redis, and PostgreSQL trade-offs.",
                "priority": 8,
                "stage_tags": ["scenario"],
                "role_tags": ["technical_deep_dive"],
                "scene_tags": ["system-design"],
                "topic_tags": ["Python Backend Engineer"],
                "skill_tags": ["redis", "postgresql"],
                "keywords": ["latency", "reliability", "async"],
                "difficulty": "medium",
                "is_enabled": True,
            }
        ]
    }

    routed = InterviewService._reroute_question_slices(
        question_meta=question_meta,
        knowledge_base=knowledge_base,
        parsed_resume={"skills": ["redis"], "projects": ["backend service"]},
        target_position="Python Backend Engineer",
        difficulty="medium",
        context_terms=["latency"],
    )

    assert not InterviewService._question_has_internal_prompt_leak(routed["question"])
    assert not InterviewService._question_has_internal_prompt_leak(routed.get("question_target_gap"))
    assert not InterviewService._question_has_internal_prompt_leak(routed.get("question_reason"))
    assert 21 in routed["used_slice_ids"]


@pytest.mark.unit
def test_internal_evaluation_labels_are_treated_as_prompt_leaks():
    leaked_values = [
        "candidate_evidence_or_verification_reason: hidden",
        "Requirement status: weak",
        "Candidate evidence / verification reason: hidden",
        "Candidate evidence target: ownership",
        "Suggested followups: ask about the private plan",
    ]

    for value in leaked_values:
        assert InterviewService._question_has_internal_prompt_leak(value)


@pytest.mark.unit
def test_route_question_plan_accepts_structured_resume_sections():
    question_plan = InterviewService._build_question_plan(total_questions=2, difficulty="medium")
    knowledge_base = {
        "slices": [
            {
                "slice_id": 21,
                "title": "Python backend API design",
                "content": "FastAPI SQLAlchemy PostgreSQL Redis Docker system design troubleshooting",
                "priority": 8,
                "stage_tags": ["technical", "scenario"],
                "role_tags": ["technical_deep_dive"],
                "scene_tags": ["technical_depth"],
                "topic_tags": ["Python Backend Engineer", "FastAPI"],
                "skill_tags": ["python", "fastapi", "postgresql", "redis"],
                "keywords": ["api", "sqlalchemy", "docker"],
                "source_section": "focus_points",
                "difficulty": "medium",
                "is_enabled": True,
            }
        ]
    }
    parsed_resume = {
        "summary": {"content": "Computer science student with backend project experience."},
        "education": {"school": "Harvard", "major": "Computer Science"},
        "skills": [
            {"skill": "Python", "evidence": "listed in skills"},
            {"skill": "SQL", "evidence": "database coursework"},
        ],
        "projects": [
            {"title": "Firewall Network", "evidence": "P4 packet filtering project"},
            {"title": "Website Backend", "technologies": ["Python", "SQL"]},
        ],
        "experience": [
            {"company": "Microsoft", "role": "Software Engineering Intern"},
        ],
    }

    routed = InterviewService._route_question_plan(
        question_plan=question_plan,
        knowledge_base=knowledge_base,
        parsed_resume=parsed_resume,
        target_position="Python Backend Engineer",
        difficulty="medium",
    )

    assert len(routed) == 2
    assert all("selected_slices" in item for item in routed)
    route_text = InterviewService._resume_route_text(parsed_resume)
    assert "Firewall Network" in route_text
    assert "Python" in route_text
    assert "Microsoft" in route_text


@pytest.mark.unit
def test_route_question_plan_prioritizes_declared_but_unproven_ability():
    question_plan = InterviewService._build_question_plan(total_questions=2, difficulty="medium")
    knowledge_base = {
        "slices": [
            {
                "slice_id": 31,
                "title": "Redis verification",
                "content": "Redis cache consistency distributed lock troubleshooting",
                "priority": 8,
                "stage_tags": ["technical"],
                "role_tags": ["technical_deep_dive"],
                "scene_tags": ["technical_depth"],
                "topic_tags": ["Redis", "cache"],
                "skill_tags": ["redis", "cache"],
                "keywords": ["redis", "cache"],
                "source_section": "interview_experience",
                "difficulty": "medium",
                "is_enabled": True,
            }
        ]
    }
    matching_metrics = {
        "ability_gap_profile": {
            "top_gaps": [
                {
                    "ability_id": "backend_cache",
                    "name": "缓存与 Redis 应用",
                    "evidence_status": "claimed_only",
                    "verification_priority": "high",
                    "priority_score": 18,
                    "verification_keywords": ["Redis"],
                    "interview_probe_reason": "简历只声明熟悉 Redis，但缺少项目证据。",
                }
            ]
        }
    }

    routed = InterviewService._route_question_plan(
        question_plan=question_plan,
        knowledge_base=knowledge_base,
        parsed_resume={"skills": ["熟悉 Redis"], "projects": []},
        target_position="Python后端开发工程师",
        difficulty="medium",
        matching_metrics=matching_metrics,
    )

    assert routed[0]["verification_target"]["ability_name"] == "缓存与 Redis 应用"
    assert routed[0]["verification_target"]["evidence_status"] == "claimed_only"
    assert "验证缓存与 Redis 应用掌握程度" in routed[0]["evaluation_focus"]
    assert "Redis" in routed[0]["question_target_gap"]
    qa_data = InterviewService._build_qa_data([{**routed[0], "question": "How have you used Redis?", "answer": "I used it in cache."}])
    assert qa_data[0]["verification_target"]["ability_name"] == "缓存与 Redis 应用"


@pytest.mark.unit
def test_apply_blueprint_to_question_plan_adds_track_and_traceable_fields():
    question_plan = [
        {
            "index": 0,
            "question": "Please introduce yourself.",
            "stage": "opening",
            "category": "self-intro",
            "intent": "Assess fit.",
            "evaluation_focus": ["communication"],
            "selected_followups": [],
        },
        {
            "index": 1,
            "question": "Tell me about your core project.",
            "stage": "project",
            "category": "project",
            "intent": "Assess ownership.",
            "evaluation_focus": ["ownership"],
            "selected_followups": [],
        },
    ]
    blueprint = {
        "training_focus": ["Clarify ownership boundaries", "Quantify trade-offs"],
        "high_risk_claims": [{"claim": "Led a platform rebuild"}],
        "priority_question_tracks": [
            {
                "track": "Project ownership verification",
                "reason": "Need to verify whether the rebuild was led or supported by the candidate",
                "requirement_status": "weak",
                "evidence_ids": [31, 32],
            }
        ],
        "blueprint_evidence": {
            "slice_ids": [31, 32],
            "slice_summaries": ["Architecture slice matched project depth"],
        },
        "evidence_summary": ["Weak support around rebuild ownership"],
    }

    enriched = InterviewService._apply_blueprint_to_question_plan(question_plan, blueprint)

    assert enriched[0]["blueprint_track"] == "Project ownership verification"
    assert enriched[0]["blueprint_requirement_status"] == "weak"
    assert enriched[0]["blueprint_evidence_ids"] == [31, 32]
    assert enriched[0]["blueprint_evidence_summary"]
    assert "Project ownership verification" not in enriched[0]["intent"]
    assert "Project ownership verification" in enriched[0]["evaluation_focus"]
    assert "Led a platform rebuild" in enriched[0]["selected_followups"]


@pytest.mark.unit
def test_apply_blueprint_keeps_role_calibration_out_of_candidate_evidence_summary():
    question_plan = [{"index": 0, "question": "Describe Redis failure handling."}]
    blueprint = {
        "priority_question_tracks": [
            {
                "track": "Redis failure handling",
                "reason": "Knowledge base slice requires Redis failure handling",
                "evidence_ids": [],
                "role_requirement_source_ids": [94],
            }
        ],
        "blueprint_evidence": {
            "resume_evidence_summary": ["Resume says Redis only as a skill"],
            "slice_summaries": ["Knowledge base slice #94: Redis failure handling"],
        },
    }

    enriched = InterviewService._apply_blueprint_to_question_plan(question_plan, blueprint)

    assert enriched[0]["blueprint_evidence_ids"] == []
    assert enriched[0]["blueprint_role_calibration_ids"] == [94]
    assert "Knowledge base slice requires Redis failure handling" not in enriched[0]["blueprint_evidence_summary"]
    assert "Knowledge base slice requires Redis failure handling" in enriched[0]["blueprint_role_calibration_summary"]


@pytest.mark.unit
def test_apply_blueprint_does_not_add_role_reference_high_risk_to_candidate_followups():
    question_plan = [{"index": 0, "question": "Describe Redis failure handling.", "selected_followups": []}]
    blueprint = {
        "high_risk_claims": [
            {
                "claim": "Knowledge base requires Redis incident handling",
                "risk_reason": "Knowledge base slice requires Redis incident handling",
                "source": "knowledge_base",
                "role_requirement_source_ids": [94],
            }
        ],
        "priority_question_tracks": [
            {
                "track": "Redis failure handling",
                "reason": "Knowledge base slice requires Redis failure handling",
                "role_requirement_source_ids": [94],
            }
        ],
    }

    enriched = InterviewService._apply_blueprint_to_question_plan(question_plan, blueprint)

    assert "Knowledge base requires Redis incident handling" not in enriched[0].get("selected_followups", [])
    assert enriched[0]["blueprint_evidence_ids"] == []
    assert enriched[0]["blueprint_role_calibration_ids"] == [94]


@pytest.mark.unit
def test_rag_slice_ids_do_not_become_candidate_question_target_evidence_ids():
    fields = InterviewService._derive_question_target_fields(
        {
            "question_target_gap": "Redis failure handling",
            "selected_slices": [{"slice_id": 94, "summary": "Role profile asks for Redis failover"}],
            "used_slice_ids": [94],
            "evidence_summary": ["Role profile asks for Redis failover"],
        }
    )

    assert fields["question_target_evidence_ids"] == []
    assert fields["question_target_evidence"] == []


@pytest.mark.unit
def test_followup_evidence_source_ids_are_limited_to_candidate_evidence_ids():
    next_meta = InterviewService._apply_followup_to_next_question(
        current_question_meta={
            "question_target_gap": "Redis failure handling",
            "question_target_evidence_ids": [12],
            "used_slice_ids": [101],
            "selected_slices": [{"slice_id": 101}],
        },
        next_question_meta={"question": "Next question"},
        evaluation={
            "selected_followups": ["请继续说明。"],
            "next_best_followup": {
                "question": "请说明真实 Redis 故障处理经历。",
                "target_gap": "Redis failure handling",
                "evidence_source_ids": [101, 12],
            }
        },
    )

    assert next_meta["question_target_evidence_ids"] == [12]


@pytest.mark.unit
def test_report_signals_exclude_role_reference_claim_confidence_items():
    signals = InterviewService._build_report_signals(
        [
            {
                "evaluation": {
                    "claim_confidence_change": [
                        {
                            "claim": "Redis incident handling needs verification",
                            "reason": "Knowledge base slice requires this role capability",
                            "source": "knowledge_base",
                            "role_requirement_source_ids": [101],
                        },
                        {
                            "claim": "Candidate led API integration",
                            "reason": "Resume says they owned API integration",
                            "source": "resume",
                        },
                    ]
                }
            }
        ]
    )

    assert len(signals["claim_confidence_summary"]) == 1
    assert "Candidate led API integration" in signals["claim_confidence_summary"][0]
    assert "Redis incident handling" not in "\n".join(signals["claim_confidence_summary"])


def test_evaluate_round_falls_back_to_single_when_panel_evaluation_fails(monkeypatch):
    async def _raise_panel(**kwargs):
        raise json.JSONDecodeError("Expecting ',' delimiter", "", 85)

    async def _single_eval(**kwargs):
        return {
            "score": 6.5,
            "feedback": "Need more concrete ownership evidence.",
            "unresolved_gaps": ["ownership clarity"],
            "next_best_followup": {
                "question": "Which decisions were made by you personally?",
                "target_gap": "ownership clarity",
                "evidence_source_ids": [31],
            },
        }

    monkeypatch.setattr(AIService, "evaluate_answer_with_panel", _raise_panel)
    monkeypatch.setattr(AIService, "evaluate_answer", _single_eval)

    async def _run():
        return await InterviewService._evaluate_round(
            interview_mode="panel",
            question="Tell me about the migration project.",
            answer="I helped drive the migration.",
            resume_context={},
            chat_history=[],
            knowledge_base=None,
            question_meta={"question_target_gap": "ownership clarity", "question_target_evidence_ids": [31]},
            panel_snapshot={"mode": "panel"},
            ai_config=None,
        )

    mode, evaluation = asyncio.run(_run())

    assert mode == "single_fallback"
    assert evaluation["feedback"] == "Need more concrete ownership evidence."
    assert evaluation["next_best_followup"]["target_gap"] == "ownership clarity"


def test_evaluate_round_uses_deterministic_fallback_when_single_json_fails(monkeypatch):
    async def _raise_single(**kwargs):
        raise json.JSONDecodeError("Expecting ',' delimiter", "", 85)

    monkeypatch.setattr(AIService, "evaluate_answer", _raise_single)

    async def _run():
        return await InterviewService._evaluate_round(
            interview_mode="single",
            question="Tell me about the migration project.",
            answer="I designed the rollout, implemented the API changes, and reviewed the result after launch.",
            resume_context={},
            chat_history=[],
            knowledge_base=None,
            question_meta={
                "question_target_gap": "ownership clarity",
                "question_target_evidence": ["migration project"],
                "question_target_evidence_ids": [31],
            },
            panel_snapshot=None,
            ai_config=None,
        )

    mode, evaluation = asyncio.run(_run())

    assert mode == "deterministic_fallback"
    assert evaluation["metadata"]["fallback_reason"] == "answer_evaluation_json_malformed"
    assert evaluation["metadata"]["evaluation_fallback"] is True
    assert evaluation["score"] >= 5.0
    assert "ownership clarity" in evaluation["next_best_followup"]["target_gap"]


def test_evaluate_round_uses_deterministic_fallback_when_panel_and_single_json_fail(monkeypatch):
    async def _raise_json(**kwargs):
        raise json.JSONDecodeError("Expecting ',' delimiter", "", 85)

    monkeypatch.setattr(AIService, "evaluate_answer_with_panel", _raise_json)
    monkeypatch.setattr(AIService, "evaluate_answer", _raise_json)

    async def _run():
        return await InterviewService._evaluate_round(
            interview_mode="panel",
            question="Tell me about the migration project.",
            answer="I drove the migration and summarized the rollback plan.",
            resume_context={},
            chat_history=[],
            knowledge_base=None,
            question_meta={"question_target_gap": "risk awareness"},
            panel_snapshot={"mode": "panel"},
            ai_config=None,
        )

    mode, evaluation = asyncio.run(_run())

    assert mode == "deterministic_fallback"
    assert evaluation["metadata"]["fallback_reason"] == "panel_and_single_evaluation_json_malformed"
    assert evaluation["unresolved_gaps"]


def test_evaluate_round_timeout_uses_deterministic_fallback(monkeypatch):
    async def _raise_timeout(**kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(AIService, "evaluate_answer", _raise_timeout)

    async def _run():
        return await InterviewService._evaluate_round(
            interview_mode="single",
            question="Tell me about the migration project.",
            answer="I owned the rollout plan, implemented the API, and reviewed the launch metrics.",
            resume_context={},
            chat_history=[],
            knowledge_base=None,
            question_meta={"question_target_gap": "execution evidence"},
            panel_snapshot=None,
            ai_config=None,
        )

    mode, evaluation = asyncio.run(_run())

    assert mode == "deterministic_fallback"
    assert evaluation["metadata"]["fallback_reason"] == "answer_evaluation_timeout"
    assert evaluation["metadata"]["evaluation_fallback"] is True


@pytest.mark.unit
def test_runtime_client_uses_explicit_http_timeout(monkeypatch):
    captured = {}

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(ai_service_module, "AsyncOpenAI", _FakeAsyncOpenAI)
    monkeypatch.setattr(settings, "USER_LLM_HTTP_TIMEOUT_SECONDS", 33.0)

    AIService._resolve_runtime(
        {
            "api_key": "test-key",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "base_url": "https://api.deepseek.com",
        }
    )

    assert captured["timeout"] == 33.0


@pytest.mark.unit
def test_submit_answer_stream_emits_version_status_and_heartbeat(monkeypatch):
    class _PrecheckResult:
        def first(self):
            return SimpleNamespace(
                current_question_index=0,
                total_questions=2,
                questions_data=[{"question": "q1"}, {"question": "q2"}],
            )

    class _Db:
        def __init__(self):
            self.rolled_back = False

        async def execute(self, _statement):
            return _PrecheckResult()

        async def rollback(self):
            self.rolled_back = True

    async def _slow_submit_answer(**_kwargs):
        await asyncio.sleep(1)

    def _payload(event: str):
        assert event.startswith("data: ")
        return json.loads(event.removeprefix("data: ").strip())

    monkeypatch.setattr(interview_service_module, "ANSWER_STREAM_HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr(interview_service_module, "ANSWER_STREAM_TOTAL_TIMEOUT_SECONDS", 0.04)
    monkeypatch.setattr(InterviewService, "submit_answer", staticmethod(_slow_submit_answer))

    async def _run():
        events = []
        async for event in InterviewService.submit_answer_stream(
            db=_Db(),
            user_id=7,
            interview_id=1,
            answer="A long answer",
            question_index=0,
            ai_config=None,
        ):
            events.append(_payload(event))
            if events[-1]["type"] == "error":
                break
        return events

    events = asyncio.run(_run())

    assert events[0]["type"] == "stream_version"
    assert events[0]["version"] == "answer_stream_v2"
    assert any(item["type"] == "status" and item["stage"] == "received" for item in events)
    assert any(item["type"] == "heartbeat" and item["stage"] == "evaluating" for item in events)
    assert events[-1]["type"] == "error"
    assert "Expecting" not in events[-1]["content"]


@pytest.mark.unit
def test_long_answer_compaction_preserves_raw_signal_without_full_replay():
    long_answer = (
        "Opening context: I was responsible for the migration design. "
        + "I implemented retry handling, wrote the rollout checklist, and measured error rates. " * 80
        + "Closing context: the release finished with a documented rollback plan."
    )

    compact = AIService._compact_answer_for_llm(long_answer, limit=1200)

    assert len(compact) < len(long_answer)
    assert str(len(long_answer)) in compact
    assert "Opening context" in compact
    assert "Closing context" in compact
    assert "implemented retry handling" in compact


@pytest.mark.unit
def test_history_text_compacts_long_candidate_messages():
    long_answer = "I owned the project. " + ("I implemented the parser and measured latency. " * 90)
    history = [
        {"role": "interviewer", "content": "Describe the project."},
        {"role": "candidate", "content": long_answer},
    ]

    text = AIService._history_text(history)

    assert "Describe the project" in text
    assert "Candidate:" in text
    assert len(text) < len(long_answer)
    assert str(len(long_answer.strip())) in text


def test_evaluate_round_does_not_swallow_ai_config_validation_error(monkeypatch):
    async def _raise_validation(**kwargs):
        raise ValidationError(message="请先在个人中心保存可用的 AI API Key")

    monkeypatch.setattr(AIService, "evaluate_answer", _raise_validation)

    async def _run():
        await InterviewService._evaluate_round(
            interview_mode="single",
            question="Tell me about the migration project.",
            answer="I handled it.",
            resume_context={},
            chat_history=[],
            knowledge_base=None,
            question_meta={},
            panel_snapshot=None,
            ai_config=None,
        )

    with pytest.raises(ValidationError, match="API Key"):
        asyncio.run(_run())


class _FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeListResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class _FakeSubmitAnswerDb:
    def __init__(self, interview, resume, messages=None):
        self.results = [_FakeScalarResult(interview), _FakeScalarResult(resume), _FakeListResult(messages or [])]
        self.added = []
        self.committed = False

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True


class _FakeDeleteInterviewDb:
    def __init__(self, interview):
        self.interview = interview
        self.execute_calls = 0
        self.deleted = []
        self.committed = False

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _FakeScalarResult(self.interview)
        return _FakeListResult([])

    async def delete(self, item):
        self.deleted.append(item)

    async def commit(self):
        self.committed = True


class _FakeAdminConsentDb:
    def __init__(self, interview):
        self.interview = interview
        self.committed = False
        self.refreshed = False

    async def get(self, _model, _item_id):
        return self.interview

    async def commit(self):
        self.committed = True

    async def refresh(self, _item):
        self.refreshed = True

    async def rollback(self):
        self.rolled_back = True


class _FakeTrainingReviewDb:
    def __init__(self, interview, review=None):
        self.results = [_FakeScalarResult(interview), _FakeScalarResult(review)]

    async def execute(self, _statement):
        return self.results.pop(0)

    async def commit(self):
        self.committed = True

    async def refresh(self, _item):
        self.refreshed = True


@pytest.mark.unit
def test_training_review_rejects_user_deleted_and_incomplete_interviews():
    deleted_completed = SimpleNamespace(
        id=1,
        user_id=7,
        status="completed",
        user_deleted_at=datetime.now(timezone.utc),
    )
    in_progress = SimpleNamespace(
        id=2,
        user_id=7,
        status="in_progress",
        user_deleted_at=None,
    )
    completed = SimpleNamespace(
        id=3,
        user_id=7,
        status="completed",
        user_deleted_at=None,
    )

    async def _run():
        with pytest.raises(NotFoundError):
            await TrainingReviewService.get_review(
                db=_FakeTrainingReviewDb(deleted_completed),
                user_id=7,
                interview_id=1,
            )

        with pytest.raises(ValidationError, match="尚未完成"):
            await TrainingReviewService.get_review(
                db=_FakeTrainingReviewDb(in_progress),
                user_id=7,
                interview_id=2,
            )

        review = await TrainingReviewService.get_review(
            db=_FakeTrainingReviewDb(completed),
            user_id=7,
            interview_id=3,
        )
        assert review["interview_id"] == 3

    asyncio.run(_run())


@pytest.mark.unit
def test_user_delete_completed_interview_soft_deletes_for_admin_review():
    interview = SimpleNamespace(
        id=12,
        user_id=7,
        status="completed",
        user_deleted_at=None,
        user_deleted_reason=None,
    )
    db = _FakeDeleteInterviewDb(interview)

    async def _run():
        result = await InterviewService.delete_interview(db=db, user_id=7, interview_id=12)
        assert result["retained_for_review"] is True
        assert interview.user_deleted_at is not None
        assert interview.user_deleted_reason == "user_deleted_completed_interview_retained_for_review"
        assert db.deleted == []
        assert db.committed is True

    asyncio.run(_run())


@pytest.mark.unit
def test_user_delete_in_progress_interview_hard_deletes():
    interview = SimpleNamespace(
        id=13,
        user_id=7,
        status="in_progress",
        user_deleted_at=None,
        user_deleted_reason=None,
    )
    db = _FakeDeleteInterviewDb(interview)

    async def _run():
        result = await InterviewService.delete_interview(db=db, user_id=7, interview_id=13)
        assert result["message"] == "面试记录已删除"
        assert db.deleted == [interview]
        assert db.committed is True

    asyncio.run(_run())


@pytest.mark.unit
def test_admin_backfill_consent_requires_completed_case_and_writes_audit_snapshot():
    completed = SimpleNamespace(
        id=21,
        resume_id=31,
        target_position="Python后端开发工程师",
        status="completed",
        data_contribution_consent=False,
        privacy_consent_snapshot={},
    )
    in_progress = SimpleNamespace(
        id=22,
        resume_id=32,
        target_position="产品助理",
        status="in_progress",
        data_contribution_consent=False,
        privacy_consent_snapshot={},
    )

    async def _run():
        result = await InterviewService.set_case_data_contribution_consent_admin(
            db=_FakeAdminConsentDb(completed),
            interview_id=21,
            data_contribution_consent=True,
            reason="前期实例补授权",
            admin_email="admin@example.com",
        )
        assert result["data_contribution_consent"] is True
        assert completed.data_contribution_consent is True
        snapshot = completed.privacy_consent_snapshot
        assert snapshot["source"] == "admin_case_consent_override"
        assert snapshot["admin_override"] is True
        assert snapshot["admin_email"] == "admin@example.com"
        assert snapshot["sample_origin"] == "real_authorized"
        assert snapshot["candidate_answer_source"] == "human"

        with pytest.raises(ValidationError, match="已完成"):
            await InterviewService.set_case_data_contribution_consent_admin(
                db=_FakeAdminConsentDb(in_progress),
                interview_id=22,
                data_contribution_consent=True,
                reason="不应允许",
                admin_email="admin@example.com",
            )

        completed.data_contribution_consent = False
        completed.privacy_consent_snapshot = {}
        with pytest.raises(ValidationError, match="必须填写原因"):
            await InterviewService.set_case_data_contribution_consent_admin(
                db=_FakeAdminConsentDb(completed),
                interview_id=21,
                data_contribution_consent=True,
                reason="",
                admin_email="admin@example.com",
            )

    asyncio.run(_run())


@pytest.mark.unit
def test_submit_answer_requires_index_and_handles_dirty_total_questions(monkeypatch):
    interview = SimpleNamespace(
        id=1,
        user_id=7,
        resume_id=3,
        knowledge_base_snapshot=None,
        status="in_progress",
        current_question_index=0,
        questions_data=[{"index": 0, "question": "Describe the rollout."}],
        total_questions=5,
        interview_mode="single",
        panel_snapshot=None,
        target_position="Python Backend Engineer",
        difficulty="medium",
        overall_score=None,
        report=None,
    )
    resume = SimpleNamespace(id=3)

    async def fake_evaluate_round(**_kwargs):
        return "single", {"score": 8.0, "feedback": "Good evidence."}

    async def fake_report(**_kwargs):
        return {"overall": "ok"}

    monkeypatch.setattr(InterviewService, "_load_resume_payload", staticmethod(lambda _resume: {"skills": ["Python"]}))
    monkeypatch.setattr(InterviewService, "_load_resume_analysis_payload", staticmethod(lambda _resume: {}))
    monkeypatch.setattr(InterviewService, "_evaluate_round", staticmethod(fake_evaluate_round))
    monkeypatch.setattr(AIService, "generate_report", staticmethod(fake_report))

    async def _run():
        with pytest.raises(ValidationError, match="question_index"):
            await InterviewService.submit_answer(
                db=_FakeSubmitAnswerDb(interview, resume),
                user_id=7,
                interview_id=1,
                answer="I handled the rollout.",
                question_index=None,
            )

        db = _FakeSubmitAnswerDb(interview, resume)
        result = await InterviewService.submit_answer(
            db=db,
            user_id=7,
            interview_id=1,
            answer="I handled the rollout.",
            question_index=0,
        )

        assert result["is_finished"] is True
        assert result["next_question"] is None
        assert interview.status == "completed"
        assert interview.current_question_index == 1
        assert db.committed is True

    asyncio.run(_run())


@pytest.mark.unit
def test_get_report_returns_interview_difficulty_profile():
    interview = SimpleNamespace(
        id=88,
        user_id=7,
        resume_id=None,
        target_position="Python Backend Engineer",
        difficulty="hard",
        total_questions=3,
        interview_mode="single",
        status="completed",
        overall_score=Decimal("7.5"),
        report="{}",
        questions_data=[
            {
                "index": 0,
                "question": "Describe a backend project.",
                "score": 7.5,
                "feedback": "ok",
            }
        ],
        data_contribution_consent=True,
        privacy_consent_snapshot=None,
        knowledge_base_snapshot=None,
        panel_snapshot=None,
        user_deleted_at=None,
    )

    class _Result:
        def scalar_one_or_none(self):
            return interview

    class _Db:
        async def execute(self, _statement):
            return _Result()

    result = asyncio.run(
        InterviewService.get_report(db=_Db(), user_id=7, interview_id=88)
    )

    assert result["difficulty"] == "hard"
    assert result["difficulty_profile"]["level"] == "hard"
    assert result["report"]["difficulty_profile"]["level"] == "hard"


@pytest.mark.unit
def test_get_interview_messages_returns_difficulty_profile_for_direct_entry():
    interview = SimpleNamespace(
        id=89,
        user_id=7,
        difficulty="easy",
        interview_mode="panel",
        status="in_progress",
        current_question_index=1,
        total_questions=3,
        user_deleted_at=None,
    )
    messages = [
        SimpleNamespace(
            id=1,
            role="interviewer",
            content="Describe yourself.",
            question_index=0,
            score=None,
            feedback=None,
            created_at=None,
        )
    ]

    class _InterviewResult:
        def scalar_one_or_none(self):
            return interview

    class _MessagesResult:
        def scalars(self):
            return self

        def all(self):
            return messages

    class _Db:
        def __init__(self):
            self.results = [_InterviewResult(), _MessagesResult()]

        async def execute(self, _statement):
            return self.results.pop(0)

    result = asyncio.run(
        InterviewService.get_interview_messages(db=_Db(), user_id=7, interview_id=89)
    )

    assert result["difficulty"] == "easy"
    assert result["difficulty_profile"]["level"] == "easy"
    assert result["interview_mode"] == "panel"
    assert result["items"][0]["content"] == "Describe yourself."


def test_start_interview_returns_business_error_when_record_commit_fails(monkeypatch):
    resume = SimpleNamespace(
        id=10,
        user_id=3,
        status="completed",
        parsed_content=json.dumps({"name": "Demo", "skills": ["Python"]}),
        analysis="{}",
    )

    class _Result:
        def scalar_one_or_none(self):
            return resume

        def scalars(self):
            return self

        def first(self):
            return None

    class _CommitFailingDb:
        def __init__(self):
            self.rollback_called = False

        async def execute(self, query):
            return _Result()

        def add(self, item):
            self.added = item

        async def commit(self):
            raise SQLAlchemyError("column interviews.panel_snapshot does not exist")

        async def rollback(self):
            self.rollback_called = True

        async def refresh(self, item):
            return None

    async def _blueprint(**kwargs):
        return {}

    async def _questions(**kwargs):
        return [
            {"index": 0, "question": "请先做一个自我介绍。", "category": "self-intro"},
            {"index": 1, "question": "介绍一个 Python 项目。", "category": "project"},
            {"index": 2, "question": "说说数据库索引。", "category": "technical"},
        ]

    monkeypatch.setattr(AIService, "extract_interview_blueprint", _blueprint)
    monkeypatch.setattr(AIService, "generate_questions", _questions)

    db = _CommitFailingDb()
    async def _run():
        await InterviewService.start_interview(
            db=db,
            user_id=3,
            resume_id=10,
            target_position="Python后端开发工程师",
            knowledge_base_id=None,
            difficulty="medium",
            total_questions=3,
            multi_interviewer_enabled=False,
            ai_config={"api_key": "test", "provider": "deepseek"},
        )

    with pytest.raises(ValidationError) as exc:
        asyncio.run(_run())

    assert db.rollback_called is True
    assert "数据库写入异常" in exc.value.detail
    assert "alembic upgrade head" in exc.value.detail


def test_start_interview_does_not_inherit_resume_contribution_consent(monkeypatch):
    resume = SimpleNamespace(
        id=10,
        user_id=3,
        status="completed",
        parsed_content=json.dumps({"name": "Demo", "skills": ["Python"]}),
        analysis="{}",
        target_position="Python后端开发工程师",
        data_contribution_consent=True,
        privacy_consent_snapshot={"source": "resume_upload", "data_contribution_consent": True},
    )

    class _Result:
        def scalar_one_or_none(self):
            return resume

        def scalars(self):
            return self

        def first(self):
            return None

    class _CommitFailingDb:
        def __init__(self):
            self.added = None

        async def execute(self, query):
            return _Result()

        def add(self, item):
            self.added = item

        async def commit(self):
            raise SQLAlchemyError("stop after interview construction")

        async def rollback(self):
            return None

        async def refresh(self, item):
            return None

    async def _blueprint(**kwargs):
        return {}

    async def _questions(**kwargs):
        return [
            {"index": 0, "question": "请先做一个自我介绍。", "category": "self-intro"},
            {"index": 1, "question": "介绍一个 Python 项目。", "category": "project"},
            {"index": 2, "question": "说说数据库索引。", "category": "technical"},
        ]

    monkeypatch.setattr(AIService, "extract_interview_blueprint", _blueprint)
    monkeypatch.setattr(AIService, "generate_questions", _questions)

    db = _CommitFailingDb()

    async def _run():
        await InterviewService.start_interview(
            db=db,
            user_id=3,
            resume_id=10,
            target_position="Python后端开发工程师",
            knowledge_base_id=None,
            difficulty="medium",
            total_questions=3,
            multi_interviewer_enabled=False,
            ai_config={"api_key": "test", "provider": "deepseek"},
        )

    with pytest.raises(ValidationError):
        asyncio.run(_run())

    assert db.added.data_contribution_consent is False
    assert db.added.privacy_consent_snapshot["source"] == "interview_start"
    assert db.added.privacy_consent_snapshot["data_contribution_consent"] is False


@pytest.mark.unit
def test_set_case_data_contribution_consent_updates_current_interview_only():
    interview = SimpleNamespace(
        id=88,
        user_id=3,
        resume_id=10,
        target_position="Python后端开发工程师",
        data_contribution_consent=False,
        privacy_consent_snapshot=None,
    )
    user = SimpleNamespace(
        id=3,
        privacy_policy_version="2026-05-15",
        privacy_agreed_at=datetime(2026, 5, 15, 8, 0, 0),
    )

    class _Result:
        def scalar_one_or_none(self):
            return interview

    class _Db:
        def __init__(self):
            self.committed = False
            self.refreshed = False
            self.rollback_called = False

        async def execute(self, query):
            return _Result()

        async def commit(self):
            self.committed = True

        async def refresh(self, item):
            self.refreshed = item is interview

        async def rollback(self):
            self.rollback_called = True

    db = _Db()
    result = asyncio.run(
        InterviewService.set_case_data_contribution_consent(
            db=db,
            current_user=user,
            interview_id=88,
            data_contribution_consent=True,
        )
    )

    assert db.committed is True
    assert db.refreshed is True
    assert interview.data_contribution_consent is True
    assert interview.privacy_consent_snapshot["source"] == "case_data_contribution"
    assert interview.privacy_consent_snapshot["interview_id"] == 88
    assert result["data_contribution_consent"] is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "snapshot",
    [
        {
            "sample_origin": "simulated_from_resume",
            "candidate_answer_source": "ai_simulated",
            "for_real_sft": False,
        },
        {
            "sample_origin": "constructed",
            "candidate_answer_source": "constructed",
            "for_real_sft": False,
        },
    ],
)
def test_set_case_data_contribution_consent_rejects_non_real_sft_case(snapshot):
    interview = SimpleNamespace(
        id=89,
        user_id=3,
        resume_id=10,
        target_position="产品助理/产品经理实习生",
        data_contribution_consent=False,
        privacy_consent_snapshot=snapshot,
    )
    user = SimpleNamespace(
        id=3,
        privacy_policy_version="2026-05-15",
        privacy_agreed_at=datetime(2026, 5, 15, 12, 0, 0),
    )

    class _Result:
        def scalar_one_or_none(self):
            return interview

    class _Db:
        async def execute(self, query):
            return _Result()

    with pytest.raises(ValidationError, match="不是真实授权训练样本"):
        asyncio.run(
            InterviewService.set_case_data_contribution_consent(
                db=_Db(),
                current_user=user,
                interview_id=89,
                data_contribution_consent=True,
            )
        )

    assert interview.data_contribution_consent is False


@pytest.mark.unit
def test_build_training_sample_export_keeps_evidence_loop_and_hides_pii_by_default():
    interview = SimpleNamespace(
        id=99,
        user_id=1,
        resume_id=2,
        knowledge_base_id=7,
        target_position="Python Backend Engineer",
        difficulty="medium",
        total_questions=1,
        status="completed",
        current_question_index=1,
        interview_mode="panel",
        overall_score=Decimal("8.2"),
        data_contribution_consent=True,
        privacy_consent_snapshot={"source": "unit_test", "data_contribution_consent": True},
        created_at=datetime(2026, 4, 18, 12, 0, 0),
        knowledge_base_snapshot={"title": "Python Backend KB"},
        panel_snapshot={
            "interview_blueprint": {
                "training_focus": ["Verify ownership"],
                "evidence_summary": ["Blueprint evidence"],
            },
            "training_sample_review": {
                "quality_tier": "high",
                "is_high_quality": True,
                "has_hallucination": False,
                "followup_worthy": True,
                "report_actionable": True,
                "notes": "Good ownership evidence and useful follow-up loop.",
                "case_id": "R1",
                "resume_source": "Harvard public tech resume",
                "human_overall_score": 8.5,
                "evidence_alignment_score": 8,
                "question_quality_score": 9,
                "report_actionability_score": 8,
                "learning_task_actionability_score": 7.5,
                "human_score_notes": "Human score is close to the AI score.",
                "dataset_split": "validation",
                "reviewed_at": "2026-04-18T12:30:00+00:00",
                "reviewer_email": "reviewer@example.com",
            },
        },
        questions_data=[
            {
                "index": 0,
                "question": "Tell me about the cache rollout.",
                "category": "project",
                "stage": "project_followup",
                "lead_role": "project_follow_up",
                "interview_mode": "panel",
                "question_target_gap": "ownership clarity",
                "question_target_evidence": ["Cache rollout evidence"],
                "question_target_evidence_ids": [31],
                "question_reason": "Verify whether the candidate owned the rollout.",
                "used_slice_ids": [11],
                "evidence_trace": [{"slice_id": 11, "reason_summary": "Matched cache rollout"}],
                "evidence_summary": ["Slice #11 matched cache rollout"],
                "blueprint_track": "Project ownership verification",
                "blueprint_requirement_status": "weak",
                "selected_followups": ["Which rollout decision was yours?"],
                "evaluation": {
                    "strengths": ["clear architecture"],
                    "gaps": ["ownership clarity"],
                    "unresolved_gaps": ["ownership clarity"],
                    "evidence_strength_delta": [
                        {
                            "evidence": "Cache rollout evidence",
                            "delta": "strengthened",
                            "reason": "Answer added rollout details.",
                        }
                    ],
                    "claim_confidence_change": [
                        {
                            "claim": "Led cache rollout",
                            "change": "increased",
                            "reason": "Answer named direct decisions.",
                        }
                    ],
                    "next_best_followup": {
                        "question": "Which rollout decision was yours?",
                        "target_gap": "ownership clarity",
                        "evidence_source_ids": [31],
                    },
                    "panel_views": [{"role": "project_follow_up", "summary": "Need ownership proof."}],
                    "evaluation_mode": "panel",
                },
            }
        ],
        report='{"common_gaps":["ownership clarity"],"common_strengths":["clear architecture"],'
        '"training_priorities":["verify ownership"],"followup_loop_summary":["Ask ownership"],'
        '"claim_confidence_summary":["claim confidence increased"],"evidence_summary":["slice #11"]}',
    )
    messages = [
        SimpleNamespace(
            role="candidate",
            question_index=0,
            content="I owned the rollout plan and monitored cache hit rate.",
            score=Decimal("8.0"),
            feedback="Good concrete detail.",
        )
    ]

    sample = InterviewService.build_training_sample(
        interview=interview,
        messages=messages,
        user_email="candidate@example.com",
    )

    assert sample["sample_version"] == "ai-interview.training-sample.v1"
    assert sample["sample_boundary"]["sample_origin"] == "real_authorized"
    assert sample["sample_boundary"]["candidate_answer_source"] == "human"
    assert sample["sample_boundary"]["for_real_sft"] is True
    assert "user_email" not in sample["interview"]
    assert sample["evidence_context"]["retrieved_slice_ids"] == [11]
    assert sample["training_sample_review"]["quality_tier"] == "high"
    assert sample["training_sample_review"]["export_recommended"] is True
    assert sample["training_sample_review"]["case_id"] == "R1"
    assert sample["training_sample_review"]["human_overall_score"] == 8.5
    assert sample["training_sample_review"]["dataset_split"] == "validation"
    assert sample["rounds"][0]["answer"] == "I owned the rollout plan and monitored cache hit rate."
    assert sample["rounds"][0]["question_target_gap"] == "ownership clarity"
    assert sample["rounds"][0]["evaluation"]["next_best_followup"]["target_gap"] == "ownership clarity"
    assert sample["rounds"][0]["sample_flags"]["has_followup_loop"] is True
    assert sample["report_summary"]["common_gaps"] == ["ownership clarity"]
    assert InterviewService.is_export_ready_training_sample(sample) is True

    sample_with_pii = InterviewService.build_training_sample(
        interview=interview,
        messages=messages,
        user_email="candidate@example.com",
        include_user_email=True,
    )
    assert sample_with_pii["interview"]["user_email"] == "candidate@example.com"
    assert sample["training_sample_review"]["reviewer_email"] == "[REDACTED_EMAIL]"
    assert sample["export_notes"]["pii_redaction"]["redacted"] is True


@pytest.mark.unit
def test_build_fine_tuning_record_rejects_semi_synthetic_even_if_reviewed():
    sample = {
        "sample_version": "ai-interview.training-sample.v1",
        "sample_boundary": {
            "sample_origin": "simulated_from_resume",
            "candidate_answer_source": "ai_simulated",
            "for_real_sft": False,
            "for_training": False,
        },
        "interview": {
            "id": 501,
            "target_position": "产品助理/产品经理实习生",
            "status": "completed",
            "data_contribution_consent": True,
            "overall_score": 8.0,
        },
        "rounds": [
            {
                "question": "请介绍一个需求分析项目。",
                "answer": "这是 AI 模拟回答。",
                "question_target_gap": "需求分析",
                "feedback": "ok",
                "evaluation": {"next_best_followup": {"question": "继续追问", "target_gap": "需求分析"}},
            }
        ],
        "report_summary": {"common_gaps": ["需求分析"], "training_priorities": ["补 PRD"]},
        "training_sample_review": {
            "review_status": "reviewed",
            "reviewed_at": "2026-05-20T00:00:00+00:00",
            "reviewer_email": "reviewer@example.com",
            "is_high_quality": True,
            "has_hallucination": False,
            "followup_worthy": True,
            "report_actionable": True,
        },
        "export_notes": {"data_contribution_consent": True},
    }

    assert InterviewService.is_export_ready_training_sample(sample) is False
    assert InterviewService._build_fine_tuning_record(sample) is None


@pytest.mark.unit
def test_build_training_sample_redacts_free_text_direct_identifiers():
    interview = SimpleNamespace(
        id=101,
        user_id=1,
        resume_id=2,
        knowledge_base_id=None,
        target_position="测试工程师",
        difficulty="medium",
        total_questions=1,
        status="completed",
        current_question_index=1,
        interview_mode="single",
        overall_score=Decimal("8.0"),
        created_at=datetime(2026, 5, 17, 10, 0, 0),
        knowledge_base_snapshot=None,
        panel_snapshot={
            "training_sample_review": {
                "is_high_quality": True,
                "has_hallucination": False,
                "reviewed_at": "2026-05-17T10:10:00+00:00",
                "notes": "候选人邮箱 candidate@example.com，手机号 13812345678。",
                "resume_source": "2590603008詹已誉简历.pdf",
            }
        },
        questions_data=[
            {
                "index": 0,
                "question": "请介绍测试项目。",
                "answer": "我的邮箱是 candidate@example.com，手机号 13812345678。",
                "feedback": "文件名：2590603008詹已誉简历.pdf",
            }
        ],
        report="",
        data_contribution_consent=True,
        privacy_consent_snapshot=None,
    )

    sample = InterviewService.build_training_sample(interview=interview, messages=[])
    payload = json.dumps(sample, ensure_ascii=False)

    assert "candidate@example.com" not in payload
    assert "13812345678" not in payload
    assert "2590603008詹已誉简历.pdf" not in payload
    assert "[REDACTED_EMAIL]" in payload
    assert sample["export_notes"]["pii_redaction"]["redaction_count"] >= 3


@pytest.mark.unit
def test_build_training_sample_handles_legacy_questions_payload_shapes():
    interview = SimpleNamespace(
        id=100,
        user_id=1,
        resume_id=2,
        knowledge_base_id=None,
        target_position="产品助理",
        difficulty="medium",
        total_questions=1,
        status="completed",
        current_question_index=1,
        interview_mode="single",
        overall_score=Decimal("6.8"),
        created_at=datetime(2026, 5, 8, 20, 0, 0),
        knowledge_base_snapshot=None,
        panel_snapshot={},
        questions_data=json.dumps({
            "questions": [
                {
                    "index": 0,
                    "question": "请说明你如何拆解一个校园活动的用户增长目标。",
                    "answer": "我会先定义目标人群，再拆渠道和转化指标。",
                    "score": Decimal("6.8"),
                    "feedback": "有拆解意识，但证据还不够具体。",
                }
            ]
        }, ensure_ascii=False, default=str),
        report="",
    )

    sample = InterviewService.build_training_sample(interview=interview, messages=[])

    assert sample["interview"]["id"] == 100
    assert sample["rounds"][0]["question"].startswith("请说明")
    assert sample["rounds"][0]["score"] == 6.8


@pytest.mark.unit
def test_build_evaluation_dataset_bundle_classifies_samples_and_allows_overlap():
    def make_sample(
        interview_id,
        *,
        score,
        is_high_quality=False,
        has_hallucination=False,
        followup_worthy=False,
        report_actionable=False,
        reviewed=True,
        consent=True,
        followup_signal=False,
        report_signal=False,
    ):
        return {
            "interview": {
                "id": interview_id,
                "status": "completed",
                "overall_score": score,
                "target_position": "Python Backend Engineer",
                "data_contribution_consent": consent,
            },
            "rounds": [
                {
                    "evaluation": {
                        "next_best_followup": {"question": "next"} if followup_signal else None,
                        "evidence_strength_delta": [{"delta": "strengthened"}] if followup_signal else [],
                        "claim_confidence_change": [{"change": "increased"}] if followup_signal else [],
                    }
                }
            ],
            "report_summary": {
                "common_gaps": ["ownership clarity"] if report_signal else [],
                "common_strengths": ["system design"] if report_signal else [],
                "training_priorities": ["ownership"] if report_signal else [],
            },
            "training_sample_review": {
                "review_status": "reviewed" if reviewed else "pending",
                "quality_tier": "high" if is_high_quality else "medium",
                "is_high_quality": is_high_quality,
                "has_hallucination": has_hallucination,
                "followup_worthy": followup_worthy,
                "report_actionable": report_actionable,
            },
        }

    samples = [
        make_sample(
            101,
            score=8.3,
            is_high_quality=True,
            followup_worthy=True,
            report_actionable=True,
            followup_signal=True,
            report_signal=True,
        ),
        make_sample(
            102,
            score=5.1,
            has_hallucination=True,
        ),
        make_sample(
            103,
            score=7.0,
            is_high_quality=True,
            reviewed=False,
            followup_worthy=True,
            report_actionable=True,
            followup_signal=True,
            report_signal=True,
        ),
        make_sample(
            104,
            score=9.0,
            is_high_quality=True,
            reviewed=True,
            consent=False,
        ),
    ]

    bundle = InterviewService.build_evaluation_dataset_bundle(samples)
    preview = bundle["preview"]
    datasets = {item["dataset_type"]: item for item in preview["datasets"]}
    manifest = bundle["manifest"]

    assert preview["stats"]["completed_samples"] == 4
    assert preview["stats"]["reviewed_samples"] == 3
    assert "data_contribution_consent=true" in preview["filters"]["base_requirements"]
    assert datasets["golden_cases"]["count"] == 1
    assert datasets["golden_cases"]["example_interview_ids"] == [101]
    assert datasets["hallucination_cases"]["count"] == 1
    assert datasets["hallucination_cases"]["example_interview_ids"] == [102]
    assert datasets["followup_quality_cases"]["count"] == 1
    assert datasets["report_quality_cases"]["count"] == 1
    assert manifest["counts"]["golden_cases.jsonl"] == 1
    assert manifest["counts"]["hallucination_cases.jsonl"] == 1
    assert manifest["counts"]["followup_quality_cases.jsonl"] == 1
    assert manifest["counts"]["report_quality_cases.jsonl"] == 1

    golden_lines = [line for line in bundle["files"]["golden_cases.jsonl"].splitlines() if line.strip()]
    followup_lines = [line for line in bundle["files"]["followup_quality_cases.jsonl"].splitlines() if line.strip()]
    report_lines = [line for line in bundle["files"]["report_quality_cases.jsonl"].splitlines() if line.strip()]
    hallucination_lines = [line for line in bundle["files"]["hallucination_cases.jsonl"].splitlines() if line.strip()]

    assert len(golden_lines) == 1
    assert json.loads(golden_lines[0])["dataset_membership"]["dataset_type"] == "golden_cases"
    assert len(followup_lines) == 1
    assert json.loads(followup_lines[0])["dataset_membership"]["dataset_type"] == "followup_quality_cases"
    assert len(report_lines) == 1
    assert json.loads(report_lines[0])["dataset_membership"]["dataset_type"] == "report_quality_cases"
    assert len(hallucination_lines) == 1
    assert json.loads(hallucination_lines[0])["dataset_membership"]["dataset_type"] == "hallucination_cases"


@pytest.mark.unit
def test_build_fine_tuning_dataset_bundle_exports_sft_and_counterexamples():
    def make_sample(
        interview_id,
        *,
        has_hallucination=False,
        reviewed=True,
        consent=True,
        status="completed",
    ):
        return {
            "interview": {
                "id": interview_id,
                "status": status,
                "overall_score": 8.4,
                "target_position": "Python Backend Engineer",
                "data_contribution_consent": consent,
            },
            "rounds": [
                {
                    "question": "Tell me how you handled cache consistency.",
                    "answer": "I compared Redis hit rate and database writes, then added delayed double delete.",
                    "feedback": "Concrete enough for a follow-up.",
                    "question_target_gap": "cache consistency",
                    "question_reason": "Verify whether Redis knowledge is project-backed.",
                    "blueprint_requirement_status": "claimed_only",
                    "evidence_summary": ["Resume only claims Redis familiarity."],
                    "evaluation": {
                        "next_best_followup": {
                            "question": "Which consistency failure did you observe first, and how did you prove the root cause?",
                            "target_gap": "cache consistency troubleshooting",
                        },
                    },
                }
            ],
            "evidence_context": {
                "blueprint_evidence_summary": ["Redis consistency is required by the target position."],
            },
            "report_summary": {
                "common_gaps": ["cache consistency"],
                "training_priorities": ["Redis troubleshooting"],
            },
            "training_sample_review": {
                "review_status": "reviewed" if reviewed else "pending",
                "quality_tier": "high",
                "is_high_quality": not has_hallucination,
                "has_hallucination": has_hallucination,
                "followup_worthy": True,
                "report_actionable": True,
                "case_id": f"R{interview_id}",
                "human_overall_score": 8.5,
                "dataset_split": "validation",
            },
        }

    bundle = InterviewService.build_fine_tuning_dataset_bundle(
        [
            make_sample(201),
            make_sample(202, has_hallucination=True),
            make_sample(203, consent=False),
            make_sample(204, reviewed=False),
            make_sample(205, status="in_progress"),
        ]
    )

    preview = bundle["preview"]
    stats = preview["stats"]
    sft_lines = [line for line in bundle["files"]["fine_tuning_sft.jsonl"].splitlines() if line.strip()]
    counterexample_lines = [
        line for line in bundle["files"]["fine_tuning_counterexamples.jsonl"].splitlines() if line.strip()
    ]

    assert stats["authorized_samples"] == 3
    assert stats["reviewed_samples"] == 3
    assert stats["sft_ready_samples"] == 1
    assert stats["hallucination_counterexamples"] == 1
    assert "status=completed" in preview["base_requirements"]
    assert "data_contribution_consent=true" in preview["base_requirements"]

    record = json.loads(sft_lines[0])
    assert record["schema_version"] == "ai-interview.fine-tuning-sample.v1"
    assert record["task_type"] == "followup_generation"
    assert set(record.keys()) == {"schema_version", "task_type", "instruction", "input", "output", "metadata"}
    assert record["output"]["question"].startswith("Which consistency failure")
    assert record["output"]["verification_target"] == "cache consistency troubleshooting"
    assert record["metadata"]["data_contribution_consent"] is True
    assert record["metadata"]["has_hallucination"] is False

    counterexample = json.loads(counterexample_lines[0])
    assert counterexample["metadata"]["has_hallucination"] is True


@pytest.mark.unit
def test_build_fine_tuning_readiness_report_summarizes_readiness_without_training_claims():
    samples = [
        {
            "interview": {
                "id": 301,
                "status": "completed",
                "overall_score": 8.6,
                "target_position": "Python Backend Engineer",
                "data_contribution_consent": True,
            },
            "rounds": [
                {
                    "question": "How did you design the Redis retry path?",
                    "answer": "I traced failed writes and added a retry queue.",
                    "question_target_gap": "Redis reliability",
                    "blueprint_requirement_status": "indirect",
                    "evaluation": {
                        "next_best_followup": {
                            "question": "Which metric proved the retry queue reduced failed writes?",
                            "target_gap": "Redis reliability evidence",
                        },
                    },
                }
            ],
            "training_sample_review": {
                "review_status": "reviewed",
                "quality_tier": "high",
                "is_high_quality": True,
                "has_hallucination": False,
                "followup_worthy": True,
                "report_actionable": True,
                "human_overall_score": 8.6,
            },
            "report_summary": {
                "common_gaps": ["Redis reliability"],
                "training_priorities": ["failure diagnosis"],
            },
        },
        {
            "interview": {
                "id": 302,
                "status": "in_progress",
                "overall_score": 8.1,
                "target_position": "Python Backend Engineer",
                "data_contribution_consent": True,
            },
            "rounds": [
                {
                    "question": "Draft question",
                    "answer": "Draft answer",
                    "evaluation": {
                        "next_best_followup": {
                            "question": "Draft follow-up?",
                        },
                    },
                }
            ],
            "training_sample_review": {
                "review_status": "reviewed",
                "quality_tier": "high",
                "is_high_quality": True,
                "has_hallucination": False,
                "followup_worthy": True,
                "report_actionable": True,
            },
        }
    ]

    report = InterviewService.build_fine_tuning_readiness_report(samples)
    markdown = report["markdown"]
    preview = report["preview"]

    assert preview["schema_version"] == "ai-interview.fine-tuning-readiness-report.v1"
    assert preview["stats"]["sft_ready_samples"] == 1
    assert preview["stats"]["reviewed_authorized_samples"] == 1
    assert preview["top_positions"] == [{"target_position": "Python Backend Engineer", "count": 1}]
    assert "可用于 SFT 的正向样本：`1` 条" in markdown
    assert "当前完成的是微调准备数据链路" in markdown
    assert "不代表已经完成真实 SFT/LoRA 训练" in markdown
    assert "已完成大模型微调" not in markdown
    assert "C1/C2/C3 真实闭环仍需后续服务器跑测" in markdown


@pytest.mark.unit
def test_build_fine_tuning_readiness_report_redacts_direct_identifiers():
    samples = [
        {
            "interview": {
                "id": 401,
                "status": "completed",
                "overall_score": 8.6,
                "target_position": "Python Backend Engineer candidate@example.com +86 138-1234-5678",
                "data_contribution_consent": True,
            },
            "rounds": [
                {
                    "question": "How did you handle Redis failover?",
                    "answer": "I described the retry queue.",
                    "evaluation": {
                        "next_best_followup": {"question": "Which metric proved it worked?"},
                    },
                }
            ],
            "training_sample_review": {
                "review_status": "reviewed",
                "quality_tier": "high",
                "is_high_quality": True,
                "has_hallucination": False,
                "followup_worthy": True,
                "report_actionable": True,
            },
        }
    ]

    report = InterviewService.build_fine_tuning_readiness_report(samples)

    assert "candidate@example.com" not in report["markdown"]
    assert "138-1234-5678" not in report["markdown"]
    assert "[REDACTED_EMAIL]" in report["markdown"]
    assert "[REDACTED_PHONE]" in report["markdown"]
    assert report["preview"]["top_positions"][0]["target_position"].count("[REDACTED") >= 2


@pytest.mark.unit
def test_build_evaluation_dataset_zip_includes_manifest_and_empty_files():
    bundle = InterviewService.build_evaluation_dataset_bundle([])
    zip_bytes = InterviewService.build_evaluation_dataset_zip(bundle)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "golden_cases.jsonl" in names
        assert "hallucination_cases.jsonl" in names
        assert "followup_quality_cases.jsonl" in names
        assert "report_quality_cases.jsonl" in names
        assert "fine_tuning_sft.jsonl" in names
        assert "fine_tuning_counterexamples.jsonl" in names

        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["schema_version"] == "ai-interview.evaluation-dataset.v1"
        assert manifest["counts"]["golden_cases.jsonl"] == 0
        assert manifest["fine_tuning"]["schema_version"] == "ai-interview.fine-tuning-sample.v1"
        assert archive.read("golden_cases.jsonl").decode("utf-8") == ""
        assert archive.read("fine_tuning_sft.jsonl").decode("utf-8") == ""


@pytest.mark.unit
def test_evaluation_dataset_zip_redacts_direct_identifiers_from_files_and_manifest():
    sample = {
        "interview": {
            "id": 401,
            "status": "completed",
            "overall_score": 8.4,
            "target_position": "Python Backend Engineer",
            "data_contribution_consent": True,
            "user_email": "candidate@example.com",
        },
        "rounds": [
            {
                "question": "How did you debug Redis?",
                "answer": "My phone is 13812345678 and source file was zhangsan_resume.pdf",
                "evaluation": {
                    "next_best_followup": {"question": "Which metric changed?"},
                },
            }
        ],
        "training_sample_review": {
            "review_status": "reviewed",
            "quality_tier": "high",
            "is_high_quality": True,
            "has_hallucination": False,
            "followup_worthy": True,
            "report_actionable": True,
            "human_overall_score": 8.4,
            "reviewer_email": "reviewer@example.com",
            "notes": "候选人邮箱 candidate@example.com，身份证 110101199003077777",
        },
        "report_summary": {
            "common_gaps": ["Redis reliability"],
            "training_priorities": ["failure diagnosis"],
        },
        "export_notes": {
            "data_contribution_consent": True,
            "privacy_consent_snapshot": {"source_file": "zhangsan_resume.pdf"},
        },
    }

    bundle = InterviewService.build_evaluation_dataset_bundle([sample])
    zip_bytes = InterviewService.build_evaluation_dataset_zip(bundle)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        combined = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist())

    assert "candidate@example.com" not in combined
    assert "reviewer@example.com" not in combined
    assert "13812345678" not in combined
    assert "110101199003077777" not in combined
    assert "zhangsan_resume.pdf" not in combined
    assert "[REDACTED_EMAIL]" in combined
