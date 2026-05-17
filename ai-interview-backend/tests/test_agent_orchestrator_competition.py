import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.agent_orchestrator.asset_guardrails import (
    sort_demo_cases,
    validate_case_id,
    validate_demo_case_set,
    validate_demo_preview_asset,
    validate_eval_preview_summary,
    validate_eval_score_rows,
    validate_sft_preview_bundle,
    validate_sft_preview_record,
    validate_trace_preview_asset,
)
from app.api.client.v1 import competition as competition_api
from app.configs.client_swagger_config import CLIENT_OPENAPI_TAGS
from app.services.agent_orchestrator.demo_cases import (
    DEMO_CASES,
    generate_demo_cases,
    validate_no_direct_identifiers,
)
from app.services.agent_orchestrator.demo_pipeline import run_demo_pipeline
from app.services.agent_orchestrator.evaluator import build_eval_rows, evaluate_trace
from app.services.agent_orchestrator.sft_preview import build_sft_preview_bundle


EVAL_DIMENSIONS = [
    "focus_score",
    "evidence_score",
    "depth_score",
    "polish_score",
    "role_fit_score",
    "format_score",
    "report_score",
]
BASELINE_SCORES = {
    "focus_score": 3,
    "evidence_score": 2,
    "depth_score": 3,
    "polish_score": 2,
    "role_fit_score": 3,
    "format_score": 3,
    "report_score": 3,
    "total_score": 19,
}
AGENT_SCORES = {
    "focus_score": 5,
    "evidence_score": 5,
    "depth_score": 5,
    "polish_score": 5,
    "role_fit_score": 4,
    "format_score": 5,
    "report_score": 5,
    "total_score": 34,
}


def _eval_row(case_id, variant, scores, note):
    return {
        "case_id": case_id,
        "target_role": "Python 后端开发工程师",
        "sample_origin": "demo_constructed",
        "for_training": False,
        "for_competition_demo": True,
        "preview": True,
        "model_variant": variant,
        **scores,
        "judge_note": note,
    }


def _eval_csv_row(case_id, variant, scores, note):
    values = [
        case_id,
        "Python 后端开发工程师",
        "demo_constructed",
        "False",
        "True",
        "True",
        variant,
        *[str(scores[dimension]) for dimension in EVAL_DIMENSIONS],
        str(scores["total_score"]),
        note,
    ]
    return ",".join(values) + "\n"


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
    assert agents == [
        "ResumeEvidenceAgent",
        "RoleProfileAgent",
        "GapAnalysisAgent",
        "ResumePolishAgent",
        "InterviewFollowupAgent",
        "ReportAgent",
        "LearningTaskAgent",
        "DataGovernanceAgent",
        "EvalAgent",
        "SFTPreviewAgent",
    ]
    assert trace.for_training is False
    assert trace.sample_origin == "demo_constructed"
    assert trace.eval_score is not None
    validate_trace_preview_asset(trace.model_dump())

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
    assert all(row["sample_origin"] == "demo_constructed" for row in rows)
    assert all(row["for_training"] is False for row in rows)
    assert all(row["for_competition_demo"] is True for row in rows)
    assert all(row["preview"] is True for row in rows)
    for row in rows:
        assert row["total_score"] == sum(row[dimension] for dimension in EVAL_DIMENSIONS)


def test_competition_api_rejects_incomplete_or_wrong_eval_rows(monkeypatch, tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    csv_path = eval_dir / "eval_score_table.csv"
    header = (
        "case_id,target_role,sample_origin,for_training,for_competition_demo,preview,model_variant,"
        "focus_score,evidence_score,depth_score,polish_score,role_fit_score,format_score,report_score,total_score,judge_note\n"
    )
    baseline_note = "Preview baseline rule score; not a real model run; not a holdout eval; not a fine-tuned model result."
    agent_note = "Preview rule score; not a real model run; not a holdout eval; not a fine-tuned model result."

    monkeypatch.setattr(competition_api, "_eval_dir", lambda: eval_dir)

    csv_path.write_text(
        header + _eval_csv_row("python_backend", "baseline_prompt_preview", BASELINE_SCORES, baseline_note),
        encoding="utf-8",
    )
    with pytest.raises(HTTPException) as missing_exc:
        competition_api._load_eval_score_rows("python_backend")
    assert missing_exc.value.status_code == 500

    csv_path.write_text(
        header
        + _eval_csv_row("python_backend", "baseline_prompt_preview", BASELINE_SCORES, baseline_note)
        + _eval_csv_row("python_backend", "agent_optimized", {**AGENT_SCORES, "total_score": 33}, agent_note),
        encoding="utf-8",
    )
    with pytest.raises(HTTPException) as score_exc:
        competition_api._load_eval_score_rows("python_backend")
    assert score_exc.value.status_code == 500

    csv_path.write_text(
        header
        + _eval_csv_row("python_backend", "baseline_prompt_preview", BASELINE_SCORES, baseline_note)
        + _eval_csv_row("python_backend", "agent_optimized", AGENT_SCORES, agent_note),
        encoding="utf-8",
    )
    rows = competition_api._load_eval_score_rows("python_backend")
    assert [row["model_variant"] for row in rows] == ["baseline_prompt_preview", "agent_optimized"]


def test_competition_api_eval_rows_fallback_when_csv_missing(monkeypatch, tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    trace = run_demo_pipeline(generate_demo_cases()[0]).model_dump()

    monkeypatch.setattr(competition_api, "_eval_dir", lambda: eval_dir)

    rows = competition_api._load_eval_score_rows("python_backend", trace)

    assert [row["model_variant"] for row in rows] == ["baseline_prompt_preview", "agent_optimized"]
    assert [row["total_score"] for row in rows] == [19, 34]


def test_competition_api_rejects_trace_filename_case_mismatch(monkeypatch, tmp_path):
    trace_dir = tmp_path / "agent_trace"
    trace_dir.mkdir()
    wrong_trace = run_demo_pipeline(generate_demo_cases()[1]).model_dump()
    (trace_dir / "python_backend.trace.json").write_text(json.dumps(wrong_trace, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(competition_api, "_trace_dir", lambda: trace_dir)

    with pytest.raises(HTTPException) as exc_info:
        competition_api._load_agent_trace_data("python_backend")
    assert exc_info.value.status_code == 500


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


def test_case_id_allowlist_rejects_unknown_or_path_traversal():
    assert validate_case_id("python_backend") == "python_backend"

    with pytest.raises(ValueError, match="must be one of"):
        validate_case_id("java_backend")

    with pytest.raises(ValueError, match="must be one of"):
        validate_case_id("../python_backend")

    with pytest.raises(HTTPException) as exc_info:
        competition_api._load_agent_trace_data("../python_backend")
    assert exc_info.value.status_code == 404


def test_demo_case_set_rejects_extra_or_missing_cases():
    cases = generate_demo_cases()
    assert [case["case_id"] for case in validate_demo_case_set(cases)] == [
        "python_backend",
        "product_assistant",
        "hr_specialist",
    ]

    extra = json.loads(json.dumps(cases[0], ensure_ascii=False))
    extra["case_id"] = "java_backend"
    with pytest.raises(ValueError, match="case_id"):
        validate_demo_case_set([*cases, extra])

    with pytest.raises(ValueError, match="exactly"):
        validate_demo_case_set(cases[:2])


def test_sft_preview_record_guardrails_reject_training_or_fake_real_claims():
    bundle = build_sft_preview_bundle(generate_demo_cases())
    record = json.loads(json.dumps(bundle["train"][0], ensure_ascii=False))
    validate_sft_preview_record(record)

    training_record = json.loads(json.dumps(record, ensure_ascii=False))
    training_record["for_training"] = True
    with pytest.raises(ValueError, match="for_training=false"):
        validate_sft_preview_record(training_record)

    task_record = json.loads(json.dumps(record, ensure_ascii=False))
    task_record["task_type"] = "interview_followup"
    with pytest.raises(ValueError, match="preview"):
        validate_sft_preview_record(task_record)

    pii_record = json.loads(json.dumps(record, ensure_ascii=False))
    pii_record["messages"][1]["content"] += " 邮箱：demo@example.com"
    with pytest.raises(ValueError, match="direct identifier"):
        validate_sft_preview_record(pii_record)

    fake_real_record = json.loads(json.dumps(record, ensure_ascii=False))
    fake_real_record["metadata"]["sample_origin"] = "real_authorized"
    with pytest.raises(ValueError, match="real sample origin"):
        validate_sft_preview_record(fake_real_record)


def test_sft_preview_bundle_rejects_record_count_mismatch():
    bundle = build_sft_preview_bundle(generate_demo_cases())
    with pytest.raises(ValueError, match="count mismatch"):
        validate_sft_preview_bundle(bundle["summary"], bundle["train"][:1])


def test_eval_preview_summary_guardrails_reject_pii_or_missing_boundary():
    valid_summary = (
        "# Eval Preview Summary\n"
        "- 样本类型：`demo_constructed`\n"
        "- 评估类型：`preview/demo`\n"
        "- 评分规则：七维规则评分，满分 `35`\n"
        "- 说明：`baseline_prompt_preview` 是规则基线，不是真实模型实测；"
        "不代表真实 holdout eval 或 fine-tuned model 结果。\n"
    )
    validate_eval_preview_summary(valid_summary)

    with pytest.raises(ValueError, match="direct identifier"):
        validate_eval_preview_summary(valid_summary + " 联系电话：13800138000")

    with pytest.raises(ValueError, match="clearly mark"):
        validate_eval_preview_summary("# Eval Preview Summary\nbaseline_prompt_preview\n")


def test_eval_score_row_guardrails_reject_missing_boundary():
    rows = [
        _eval_row("python_backend", "baseline_prompt_preview", BASELINE_SCORES, "preview only"),
        _eval_row("python_backend", "agent_optimized", AGENT_SCORES, "preview only"),
    ]
    with pytest.raises(ValueError, match="non-real-model boundary"):
        validate_eval_score_rows("python_backend", rows)


def test_eval_score_row_guardrails_reject_missing_dimension_or_wrong_sum():
    note = "Preview rule score; not a real model run; not a holdout eval; not a fine-tuned model result."
    missing_dimension = _eval_row("python_backend", "baseline_prompt_preview", BASELINE_SCORES, note)
    missing_dimension.pop("polish_score")
    rows = [
        missing_dimension,
        _eval_row("python_backend", "agent_optimized", AGENT_SCORES, note),
    ]
    with pytest.raises(ValueError, match="polish_score"):
        validate_eval_score_rows("python_backend", rows)

    wrong_sum = _eval_row("python_backend", "agent_optimized", {**AGENT_SCORES, "total_score": 33}, note)
    rows = [
        _eval_row("python_backend", "baseline_prompt_preview", BASELINE_SCORES, note),
        wrong_sum,
    ]
    with pytest.raises(ValueError, match="7-dimension sum"):
        validate_eval_score_rows("python_backend", rows)


def test_trace_guardrails_reject_incomplete_agent_order():
    trace = run_demo_pipeline(generate_demo_cases()[0]).model_dump()
    trace["steps"] = [step for step in trace["steps"] if step["agent"] != "SFTPreviewAgent"]

    with pytest.raises(ValueError, match="complete Agent order"):
        validate_trace_preview_asset(trace)


def test_competition_eval_preview_api_includes_demo_flags():
    response = asyncio.run(competition_api.get_eval_preview("python_backend"))
    payload = json.loads(response.body)["data"]

    assert payload["sample_origin"] == "demo_constructed"
    assert payload["for_training"] is False
    assert payload["for_competition_demo"] is True
    assert payload["preview"] is True
    assert [row["model_variant"] for row in payload["score_rows"]] == ["baseline_prompt_preview", "agent_optimized"]
    assert all(row["sample_origin"] == "demo_constructed" for row in payload["score_rows"])
    assert all(row["for_training"] in (False, "False", "false") for row in payload["score_rows"])


def test_competition_demo_cases_api_includes_top_level_demo_flags():
    response = asyncio.run(competition_api.list_demo_cases())
    payload = json.loads(response.body)["data"]

    assert payload["preview"] is True
    assert payload["sample_origin"] == "demo_constructed"
    assert payload["for_training"] is False
    assert payload["for_competition_demo"] is True
    assert [case["case_id"] for case in payload["items"]] == [
        "python_backend",
        "product_assistant",
        "hr_specialist",
    ]


def test_competition_sft_preview_api_returns_all_validated_records():
    response = asyncio.run(competition_api.get_sft_preview())
    payload = json.loads(response.body)["data"]

    assert payload["preview"] is True
    expected = payload["summary"]["counts"]["train_preview_records"]
    assert len(payload["preview_records"]) == expected
    assert all(record["sample_origin"] == "demo_constructed" for record in payload["preview_records"])
    assert all(record["for_training"] is False for record in payload["preview_records"])


def test_sft_preview_record_guardrails_require_case_ownership():
    bundle = build_sft_preview_bundle(generate_demo_cases())
    valid = bundle["train"][0]
    validate_sft_preview_record(valid)

    missing_case = json.loads(json.dumps(valid, ensure_ascii=False))
    missing_case["metadata"].pop("case_id", None)
    with pytest.raises(ValueError, match="metadata.case_id"):
        validate_sft_preview_record(missing_case)

    mismatched_case = json.loads(json.dumps(valid, ensure_ascii=False))
    mismatched_case["case_id"] = "hr_specialist"
    with pytest.raises(ValueError, match="case_id must match"):
        validate_sft_preview_record(mismatched_case)

    missing_record_id = json.loads(json.dumps(valid, ensure_ascii=False))
    missing_record_id.pop("record_id", None)
    with pytest.raises(ValueError, match="record_id is required"):
        validate_sft_preview_record(missing_record_id)

    wrong_prefix = json.loads(json.dumps(valid, ensure_ascii=False))
    wrong_prefix["record_id"] = "hr_specialist_followup_preview"
    with pytest.raises(ValueError, match="record_id must start"):
        validate_sft_preview_record(wrong_prefix)


def test_sft_preview_summary_guardrails_require_competition_demo_counts():
    bundle = build_sft_preview_bundle(generate_demo_cases())
    validate_sft_preview_bundle(bundle["summary"], bundle["train"])

    missing_created_for = {**bundle["summary"], "created_for": "other"}
    with pytest.raises(ValueError, match="created_for=competition_demo"):
        validate_sft_preview_bundle(missing_created_for, bundle["train"])

    wrong_count = json.loads(json.dumps(bundle["summary"], ensure_ascii=False))
    wrong_count["counts"]["demo_constructed"] = 2
    with pytest.raises(ValueError, match="three demo_constructed cases"):
        validate_sft_preview_bundle(wrong_count, bundle["train"])


def test_client_openapi_tags_include_competition_preview():
    tag_names = {item["name"] for item in CLIENT_OPENAPI_TAGS}
    assert "client-competition" in tag_names


def test_legacy_demo_api_route_is_not_registered():
    registry_path = Path(__file__).resolve().parents[1] / "app" / "route" / "router_registry.py"

    assert "app.api.client.v1.demo" not in registry_path.read_text(encoding="utf-8")


def test_generate_competition_assets_restores_sys_argv(monkeypatch, tmp_path):
    from app.scripts import generate_competition_assets

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_competition_assets",
            "--demo-out",
            str(tmp_path / "demo_cases"),
            "--trace-out",
            str(tmp_path / "agent_trace"),
            "--eval-out",
            str(tmp_path / "eval"),
            "--sft-out",
            str(tmp_path / "sft_preview"),
        ],
    )

    generate_competition_assets.main()

    assert sys.argv == [
        "generate_competition_assets",
        "--demo-out",
        str(tmp_path / "demo_cases"),
        "--trace-out",
        str(tmp_path / "agent_trace"),
        "--eval-out",
        str(tmp_path / "eval"),
        "--sft-out",
        str(tmp_path / "sft_preview"),
    ]
    assert (tmp_path / "eval" / "eval_score_table.csv").exists()
    assert (tmp_path / "sft_preview" / "train.preview.jsonl").exists()
