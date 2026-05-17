import json
import sys

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
)
from app.api.client.v1 import competition as competition_api
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


def test_competition_api_rejects_incomplete_or_wrong_eval_rows(monkeypatch, tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    csv_path = eval_dir / "eval_score_table.csv"
    header = "case_id,target_role,model_variant,total_score,judge_note\n"
    baseline_note = "Preview baseline rule score; not a real model run; not a holdout eval; not a fine-tuned model result."
    agent_note = "Preview rule score; not a real model run; not a holdout eval; not a fine-tuned model result."

    monkeypatch.setattr(competition_api, "_eval_dir", lambda: eval_dir)

    csv_path.write_text(
        header + f"python_backend,Python 后端开发工程师,baseline_prompt_preview,19,{baseline_note}\n",
        encoding="utf-8",
    )
    with pytest.raises(HTTPException) as missing_exc:
        competition_api._load_eval_score_rows("python_backend")
    assert missing_exc.value.status_code == 500

    csv_path.write_text(
        header
        + f"python_backend,Python 后端开发工程师,baseline_prompt_preview,19,{baseline_note}\n"
        + f"python_backend,Python 后端开发工程师,agent_optimized,33,{agent_note}\n",
        encoding="utf-8",
    )
    with pytest.raises(HTTPException) as score_exc:
        competition_api._load_eval_score_rows("python_backend")
    assert score_exc.value.status_code == 500

    csv_path.write_text(
        header
        + f"python_backend,Python 后端开发工程师,baseline_prompt_preview,19,{baseline_note}\n"
        + f"python_backend,Python 后端开发工程师,agent_optimized,34,{agent_note}\n",
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
        {
            "case_id": "python_backend",
            "target_role": "Python 后端开发工程师",
            "model_variant": "baseline_prompt_preview",
            "total_score": 19,
            "judge_note": "preview only",
        },
        {
            "case_id": "python_backend",
            "target_role": "Python 后端开发工程师",
            "model_variant": "agent_optimized",
            "total_score": 34,
            "judge_note": "preview only",
        },
    ]
    with pytest.raises(ValueError, match="non-real-model boundary"):
        validate_eval_score_rows("python_backend", rows)


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
