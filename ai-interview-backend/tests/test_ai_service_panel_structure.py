import pytest

from app.services.client.ai_service import AIService, PANEL_OUTPUT_VERSION


def _panel_snapshot():
    return {
        "mode": "panel",
        "roles": [
            {
                "key": "technical_deep_dive",
                "name": "Technical Deep Dive",
                "focus": "Probe engineering trade-offs.",
            },
            {
                "key": "project_follow_up",
                "name": "Project Follow-up",
                "focus": "Verify ownership and delivery.",
            },
            {
                "key": "behavior_expression",
                "name": "Behavior & Communication",
                "focus": "Evaluate clarity and communication.",
            },
        ],
    }


@pytest.mark.unit
def test_normalize_panel_question_payload_keeps_structured_contract():
    payload = {
        "panel": [
            {
                "role": "technical",
                "role_key": "technical_deep_dive",
                "focus": "Probe engineering trade-offs.",
                "question_candidates": ["How did you design the cache strategy?"],
                "followup_candidates": ["What broke under pressure?"],
                "evaluation_points": ["technical depth", "trade-offs"],
            }
        ],
        "moderator": {
            "selected_questions": [
                {
                    "index": 0,
                    "selected_question": "Please walk through the cache strategy you designed.",
                    "selected_followups": ["What trade-offs did you accept?"],
                    "reasoning_summary": "Best opening for technical depth.",
                    "lead_role": "technical_deep_dive",
                    "support_roles": ["project_follow_up"],
                    "evaluation_points": ["technical depth", "trade-offs"],
                    "used_slice_ids": [11, 12],
                }
            ],
            "feedback_style": "firm but constructive",
            "difficulty_hint": "medium",
            "reasoning_summary": "Start with the strongest technical thread.",
        },
        "metadata": {
            "mode": "panel",
            "version": PANEL_OUTPUT_VERSION,
            "retrieved_slice_ids": [11, 12],
            "fallback_allowed": True,
        },
    }
    question_plan = [
        {
            "index": 0,
            "stage": "technical",
            "category": "technical",
            "lead_role": "technical_deep_dive",
            "support_roles": ["project_follow_up"],
            "intent": "Validate technical depth.",
            "evaluation_focus": ["technical depth"],
            "selected_slices": [{"slice_id": 11}, {"slice_id": 12}],
        }
    ]

    normalized = AIService._normalize_panel_question_payload(
        payload=payload,
        question_plan=question_plan,
        knowledge_base={"slices": [{"slice_id": 11}, {"slice_id": 12}]},
        panel_snapshot=_panel_snapshot(),
    )

    assert normalized["metadata"]["version"] == PANEL_OUTPUT_VERSION
    assert normalized["questions"][0]["question"] == "Please walk through the cache strategy you designed."
    assert normalized["questions"][0]["selected_followups"] == ["What trade-offs did you accept?"]
    assert normalized["questions"][0]["panel_context"]["metadata"]["retrieved_slice_ids"] == [11, 12]


@pytest.mark.unit
def test_normalize_panel_evaluation_payload_keeps_single_moderator_output():
    payload = {
        "panel": [
            {
                "role": "technical",
                "role_key": "technical_deep_dive",
                "focus": "Probe engineering trade-offs.",
                "followup_candidates": ["What would you optimize next?"],
                "evaluation_points": ["root cause depth", "trade-off clarity"],
            }
        ],
        "moderator": {
            "score": 8.2,
            "feedback": "Good depth, but quantify the trade-offs more clearly.",
            "follow_up": True,
            "next_focus": "Explain capacity planning.",
            "selected_followups": ["How did you estimate capacity?"],
            "next_best_followup": {
                "question": "How did you estimate capacity?",
                "target_gap": "Trade-off quantification",
                "target_evidence": ["Cache failure investigation evidence"],
                "evidence_source_ids": [21],
                "evidence_source_summary": ["Architecture slice matched cache failure recovery"],
                "reason": "Need one more concrete number to verify the trade-off decision.",
            },
            "reasoning_summary": "Strong answer with one missing trade-off detail.",
            "difficulty_hint": "medium",
        },
        "metadata": {
            "mode": "panel",
            "version": PANEL_OUTPUT_VERSION,
            "retrieved_slice_ids": [21],
            "fallback_allowed": True,
        },
        "strengths": ["Clear root cause analysis"],
        "gaps": ["Trade-off quantification"],
    }
    question_meta = {
        "question": "How did you debug the cache failure?",
        "lead_role": "technical_deep_dive",
        "evaluation_focus": ["root cause depth"],
        "selected_slices": [{"slice_id": 21}],
    }

    normalized = AIService._normalize_panel_evaluation_payload(
        payload=payload,
        question_meta=question_meta,
        knowledge_base={"slices": [{"slice_id": 21}]},
        panel_snapshot=_panel_snapshot(),
    )

    assert normalized["score"] == 8.2
    assert normalized["feedback"] == "Good depth, but quantify the trade-offs more clearly."
    assert normalized["moderator"]["selected_followups"] == ["How did you estimate capacity?"]
    assert normalized["moderator"]["next_best_followup"]["target_gap"] == "Trade-off quantification"
    assert normalized["moderator"]["next_best_followup"]["evidence_source_ids"] == [21]
    assert normalized["moderator"]["shared_evidence_ids"] == [21]
    assert normalized["metadata"]["retrieved_slice_ids"] == [21]
    assert normalized["next_best_followup"]["question"] == "How did you estimate capacity?"


@pytest.mark.unit
def test_normalize_single_evaluation_payload_keeps_conservative_followup_fields():
    payload = {
        "score": 6.8,
        "feedback": "The answer is directionally correct, but still lacks enough evidence to prove ownership.",
        "strengths": ["Explained the migration sequence clearly"],
        "gaps": ["Ownership boundaries are still vague"],
        "unresolved_gaps": ["Ownership boundaries are still vague"],
        "next_focus": "Clarify what decisions were personally owned.",
        "selected_followups": ["Which migration decisions were made by you personally?"],
        "next_best_followup": {
            "question": "Which migration decisions were made by you personally?",
            "target_gap": "Ownership boundaries are still vague",
            "target_evidence": ["Resume project ownership wording"],
            "reason": "Need direct evidence before concluding the candidate led the migration.",
        },
    }
    question_meta = {
        "question": "Tell me about the migration project.",
        "question_target_gap": "Ownership boundaries are still vague",
        "question_target_evidence": ["Resume project ownership wording"],
        "question_target_evidence_ids": [31],
        "blueprint_high_risk_claims": ["Led the migration"],
        "selected_slices": [{"slice_id": 31}],
    }

    normalized = AIService._normalize_single_evaluation_payload(
        payload=payload,
        question_meta=question_meta,
        knowledge_base={"slices": [{"slice_id": 31}]},
    )

    assert normalized["unresolved_gaps"] == ["Ownership boundaries are still vague"]
    assert normalized["next_best_followup"]["question"] == "Which migration decisions were made by you personally?"
    assert normalized["next_best_followup"]["evidence_source_ids"] == [31]
    assert normalized["next_best_followup"]["target_evidence"] == ["Resume project ownership wording"]
    assert normalized["next_best_followup"]["reason"].startswith("Need direct evidence")


@pytest.mark.unit
def test_grounding_rules_require_conservative_output_without_evidence():
    rules = AIService._build_grounding_rules("evaluation", has_routed_evidence=False)

    assert "did not provide enough evidence/details" in rules
    assert "Do not invent candidate experience" in rules

    report_rules = AIService._build_grounding_rules("report", has_report_evidence=False)
    assert "insufficient evidence" in report_rules


@pytest.mark.unit
def test_extract_json_accepts_code_fence_and_trailing_commas():
    payload = """```json
    {
      "name": "张三",
      "skills": ["Python", "FastAPI",],
      "projects": []
    }
    ```"""

    parsed = AIService._extract_json(payload)

    assert parsed["name"] == "张三"
    assert parsed["skills"] == ["Python", "FastAPI"]


@pytest.mark.unit
def test_extract_json_accepts_python_style_dict_output():
    payload = """分析如下：
    {'overall_score': 7.5, 'strengths': ['基础扎实'], 'weaknesses': ['项目细节不足'], 'suggestions': ['补充量化结果']}"""

    parsed = AIService._extract_json(payload)

    assert parsed["overall_score"] == 7.5
    assert parsed["strengths"] == ["基础扎实"]


@pytest.mark.unit
def test_normalize_resume_evidence_keeps_required_contract():
    payload = {
        "projects": [{"title": "支付平台重构", "evidence": "负责核心链路重构"}],
        "skills": ["Python", {"skill": "FastAPI", "evidence": "简历技能栏明确提及"}],
        "metrics": [{"metric": "30%", "evidence": "性能提升 30%"}],
        "timeline_signals": ["2023-2024"],
        "role_scope": ["负责核心服务设计与上线"],
        "business_domain_terms": ["支付", "风控"],
        "ambiguity_flags": ["参与多个系统优化"],
        "missing_evidence_flags": [],
        "followup_candidates": ["追问支付平台重构中的技术取舍"],
    }

    normalized = AIService._normalize_resume_evidence(payload)

    assert normalized["projects"][0]["title"] == "支付平台重构"
    assert normalized["skills"][0]["skill"] == "Python"
    assert "evidence_summary" in normalized
    assert normalized["evidence_summary"]


@pytest.mark.unit
def test_build_resume_evidence_fallback_returns_grounded_structure():
    parsed_resume = {
        "summary": "负责电商平台订单链路优化，接口耗时下降 35%",
        "skills": ["Python", "FastAPI"],
        "projects": [
            {
                "name": "订单平台升级",
                "description": "主导订单系统改造，支持高峰期稳定运行，性能提升 35%",
            }
        ],
        "experience": ["2023-2024 负责电商订单平台后端开发与优化"],
    }

    evidence = AIService.build_resume_evidence_fallback(parsed_resume)

    assert set(evidence.keys()) == {
        "projects",
        "skills",
        "metrics",
        "timeline_signals",
        "role_scope",
        "business_domain_terms",
        "ambiguity_flags",
        "missing_evidence_flags",
        "followup_candidates",
        "evidence_summary",
    }
    assert evidence["projects"]
    assert evidence["skills"]
    assert evidence["evidence_summary"]


@pytest.mark.unit
def test_normalize_interview_blueprint_keeps_required_contract():
    payload = {
        "matched_requirements": [
            {"requirement": "Python async service delivery", "evidence": "Resume lists FastAPI and Celery", "evidence_ids": [11]}
        ],
        "weakly_supported_requirements": [
            {"requirement": "Architecture trade-offs", "reason": "Resume mentions optimization but not design details"}
        ],
        "unsupported_requirements": ["Large-scale capacity planning"],
        "high_risk_claims": [
            {"claim": "Led a platform rebuild", "risk_reason": "Ownership is not quantified", "evidence": "Resume wording is broad"}
        ],
        "priority_question_tracks": [
            {"track": "Project ownership verification", "reason": "Need to verify rebuild ownership", "requirement_status": "weak"}
        ],
        "training_focus": ["Clarify ownership boundaries", "Quantify impact"],
        "blueprint_evidence": {
            "resume_evidence_summary": ["Found 2 project evidence points"],
            "slice_ids": [11, 12],
            "slice_summaries": ["Architecture slice matched technical depth"],
            "knowledge_base_title": "Python Backend Engineer",
            "target_position": "Python Backend Engineer",
        },
    }

    normalized = AIService._normalize_interview_blueprint(payload)

    assert normalized["matched_requirements"][0]["support_level"] == "strong"
    assert normalized["weakly_supported_requirements"][0]["support_level"] == "weak"
    assert normalized["unsupported_requirements"][0]["support_level"] == "unsupported"
    assert normalized["high_risk_claims"][0]["claim"] == "Led a platform rebuild"
    assert normalized["priority_question_tracks"][0]["track"] == "Project ownership verification"
    assert normalized["blueprint_evidence"]["slice_ids"] == [11, 12]
    assert normalized["evidence_summary"]


@pytest.mark.unit
def test_build_interview_blueprint_fallback_returns_grounded_structure():
    parsed_resume = {
        "summary": "Built backend services for an e-commerce order system and improved latency by 35%",
        "skills": ["Python", "FastAPI", "Redis"],
        "projects": [{"name": "Order platform rebuild", "description": "Improved order throughput and degraded gracefully under pressure"}],
    }
    resume_evidence = {
        "projects": [{"title": "Order platform rebuild", "evidence": "Candidate claims rebuild ownership"}],
        "skills": [{"skill": "Python", "evidence": "Explicitly listed in resume"}],
        "ambiguity_flags": ["Participated in multiple system optimizations"],
        "missing_evidence_flags": ["No clear capacity planning evidence"],
        "followup_candidates": ["Ask about rebuild ownership and rollout metrics"],
        "evidence_summary": ["Found one high-value project evidence point"],
    }
    question_plan = [
        {
            "selected_slices": [
                {"slice_id": 21, "title": "Backend architecture", "routing_reasons": ["matched stage", "matched skill tags"]},
                {"slice_id": 22, "title": "Pressure scenario", "routing_reasons": ["matched scene"]},
            ]
        }
    ]

    blueprint = AIService.build_interview_blueprint_fallback(
        parsed_resume=parsed_resume,
        target_position="Python Backend Engineer",
        resume_evidence=resume_evidence,
        knowledge_base={"title": "Python Backend Engineer"},
        question_plan=question_plan,
    )

    assert set(blueprint.keys()) == {
        "matched_requirements",
        "weakly_supported_requirements",
        "unsupported_requirements",
        "high_risk_claims",
        "priority_question_tracks",
        "training_focus",
        "blueprint_evidence",
        "evidence_summary",
    }
    assert blueprint["matched_requirements"]
    assert blueprint["priority_question_tracks"]
    assert blueprint["blueprint_evidence"]["slice_ids"] == [21, 22]
    assert blueprint["evidence_summary"]


@pytest.mark.unit
def test_deepseek_v4_model_request_defaults_to_non_thinking_mode():
    model, kwargs = AIService._normalize_model_request(
        provider="deepseek",
        model="deepseek-v4-flash",
        ai_config={},
    )

    assert model == "deepseek-v4-flash"
    assert kwargs == {"extra_body": {"thinking": {"type": "disabled"}}}


@pytest.mark.unit
def test_deepseek_legacy_reasoner_maps_to_v4_thinking_mode():
    model, kwargs = AIService._normalize_model_request(
        provider="deepseek",
        model="deepseek-reasoner",
        ai_config={},
    )

    assert model == "deepseek-v4-flash"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert kwargs["reasoning_effort"] in {"high", "max"}
