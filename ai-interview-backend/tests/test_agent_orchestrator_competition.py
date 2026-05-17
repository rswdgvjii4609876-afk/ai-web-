import json

import pytest

from app.services.agent_orchestrator.asset_guardrails import (
    sort_demo_cases,
    validate_demo_preview_asset,
)
from app.services.agent_orchestrator.demo_cases import (
    DEMO_CASES,
    generate_demo_cases,
    validate_no_direct_identifiers,
)
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.evaluator import build_eval_rows, evaluate_trace
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle


def test_generate_demo_cases_are_marked_as_preview_only():
    cases = generate_demo_cases()

    assert {case["case_id"] for case in cases} == {
        "python_backend",
        "product_assistant",
        "hr_specialist",
    }
    assert all(case["sample_origin"] == "demo_constructed" for case in cases)
    assert all(case["for_training"] is False for case in cases)
    assert all(case["for_competition_demo"] is True for case in cases)


def test_demo_case_rejects_direct_identifier():
    case = json.loads(json.dumps(DEMO_CASES[0], ensure_ascii=False))
    case["resume_summary"]["projects"][0]["description"] += " 邮箱：demo@example.com"

    with pytest.raises(ValueError, match="direct identifier"):
        validate_no_direct_identifiers(case)


def test_agent_trace_contains_resume_polish_and_eval_dimensions():
    trace = run_demo_pipeline(generate_demo_cases()[0])

    agents = [step.agent for step in trace.steps]
    assert "ResumePolishAgent" in agents
    assert trace.for_training is False
    assert trace.sample_origin == "demo_constructed"
    assert trace.eval_score is not None

    score = evaluate_trace(trace)
    assert score.total_score == sum(
        [
            score.focus_score,
            score.evidence_score,
            score.depth_score,
            score.polish_score,
            score.role_fit_score,
            score.format_score,
            score.report_score,
        ]
    )
    assert score.total_score <= 35


def test_sft_preview_never_marks_demo_records_as_real_training():
    bundle = build_sft_preview_bundle(generate_demo_cases())

    assert bundle["summary"]["ready_for_real_training"] is False
    assert bundle["summary"]["counts"]["demo_constructed"] == 3
    assert bundle["summary"]["counts"]["real_authorized"] == 0
    assert bundle["train"]
    assert all(record["sample_origin"] == "demo_constructed" for record in bundle["train"])
    assert all(record["for_training"] is False for record in bundle["train"])
    assert any(record["task_type"] == "evidence_bound_resume_polish_preview" for record in bundle["train"])


def test_preview_asset_guardrails_reject_non_demo_or_training_assets():
    case = json.loads(json.dumps(generate_demo_cases()[0], ensure_ascii=False))

    case["sample_origin"] = "real_user"
    with pytest.raises(ValueError, match="sample_origin=demo_constructed"):
        validate_demo_preview_asset(case)

    case = json.loads(json.dumps(generate_demo_cases()[0], ensure_ascii=False))
    case["for_training"] = True
    with pytest.raises(ValueError, match="for_training=false"):
        validate_demo_preview_asset(case)

    case = json.loads(json.dumps(generate_demo_cases()[0], ensure_ascii=False))
    case["resume_summary"]["projects"][0]["description"] += " 联系电话：13800138000"
    with pytest.raises(ValueError, match="direct identifier"):
        validate_demo_preview_asset(case)

    case = json.loads(json.dumps(generate_demo_cases()[0], ensure_ascii=False))
    case["resume_summary"]["projects"][0]["description"] += " 学号 2020123456"
    with pytest.raises(ValueError, match="direct identifier"):
        validate_demo_preview_asset(case)

    case = json.loads(json.dumps(generate_demo_cases()[0], ensure_ascii=False))
    case["resume_summary"]["projects"][0]["description"] += " 身份证号 11010119900101123X"
    with pytest.raises(ValueError, match="direct identifier"):
        validate_demo_preview_asset(case)


def test_eval_rows_include_baseline_and_agent_variant_for_each_case():
    traces = [run_demo_pipeline(case) for case in generate_demo_cases()]
    rows = build_eval_rows(traces)

    assert len(rows) == len(traces) * 2
    variants_by_case = {}
    for row in rows:
        variants_by_case.setdefault(row["case_id"], []).append(row["model_variant"])
    for variants in variants_by_case.values():
        assert variants == ["baseline_prompt_preview", "agent_optimized"]
    assert all(row["total_score"] == 19 for row in rows if row["model_variant"] == "baseline_prompt_preview")
    assert all(row["total_score"] == 34 for row in rows if row["model_variant"] == "agent_optimized")


def test_demo_case_order_is_c1_c2_c3():
    cases = sort_demo_cases(
        [
            {"case_id": "hr_specialist"},
            {"case_id": "product_assistant"},
            {"case_id": "python_backend"},
        ]
    )

    assert [case["case_id"] for case in cases] == [
        "python_backend",
        "product_assistant",
        "hr_specialist",
    ]
