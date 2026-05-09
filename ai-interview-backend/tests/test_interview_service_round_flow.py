import asyncio
import io
import json
import zipfile
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions.http_exceptions import ValidationError
from app.services.client.ai_service import AIService
from app.services.client.interview_service import InterviewService


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
    assert routed["evidence_summary"]
    assert routed["evidence_trace"]
    assert routed["evidence_trace"][0]["reason_summary"]

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
    assert report_signals["followup_loop_summary"]
    assert report_signals["claim_confidence_summary"]
    assert merged_report["evidence_summary"] == report_signals["evidence_summary"]
    assert merged_report["common_gaps"] == report_signals["common_gaps"]
    assert merged_report["common_strengths"] == report_signals["common_strengths"]
    assert merged_report["followup_loop_summary"] == report_signals["followup_loop_summary"]
    assert merged_report["claim_confidence_summary"] == report_signals["claim_confidence_summary"]
    assert merged_report["panel_summary"] == report_signals["panel_summary"]


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
    assert "Project ownership verification" in enriched[0]["intent"]
    assert "Led a platform rebuild" in enriched[0]["selected_followups"]


@pytest.mark.asyncio
async def test_evaluate_round_falls_back_to_single_when_panel_evaluation_fails(monkeypatch):
    async def _raise_panel(**kwargs):
        raise RuntimeError("panel failed")

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

    mode, evaluation = await InterviewService._evaluate_round(
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

    assert mode == "single_fallback"
    assert evaluation["feedback"] == "Need more concrete ownership evidence."
    assert evaluation["next_best_followup"]["target_gap"] == "ownership clarity"


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
    assert "user_email" not in sample["interview"]
    assert sample["evidence_context"]["retrieved_slice_ids"] == [11]
    assert sample["training_sample_review"]["quality_tier"] == "high"
    assert sample["training_sample_review"]["export_recommended"] is True
    assert sample["rounds"][0]["answer"] == "I owned the rollout plan and monitored cache hit rate."
    assert sample["rounds"][0]["question_target_gap"] == "ownership clarity"
    assert sample["rounds"][0]["evaluation"]["next_best_followup"]["target_gap"] == "ownership clarity"
    assert sample["rounds"][0]["sample_flags"]["has_followup_loop"] is True
    assert sample["report_summary"]["common_gaps"] == ["ownership clarity"]

    sample_with_pii = InterviewService.build_training_sample(
        interview=interview,
        messages=messages,
        user_email="candidate@example.com",
        include_user_email=True,
    )
    assert sample_with_pii["interview"]["user_email"] == "candidate@example.com"


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
        followup_signal=False,
        report_signal=False,
    ):
        return {
            "interview": {
                "id": interview_id,
                "status": "completed",
                "overall_score": score,
                "target_position": "Python Backend Engineer",
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
    ]

    bundle = InterviewService.build_evaluation_dataset_bundle(samples)
    preview = bundle["preview"]
    datasets = {item["dataset_type"]: item for item in preview["datasets"]}
    manifest = bundle["manifest"]

    assert preview["stats"]["completed_samples"] == 3
    assert preview["stats"]["reviewed_samples"] == 2
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

        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["schema_version"] == "ai-interview.evaluation-dataset.v1"
        assert manifest["counts"]["golden_cases.jsonl"] == 0
        assert archive.read("golden_cases.jsonl").decode("utf-8") == ""
