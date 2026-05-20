import json
import subprocess
import sys

import pytest

from app.scripts.run_resume_closed_loop_batch import (
    build_preview_record,
    dry_run,
    recommend_target_position,
    semi_synthetic_metadata,
)


@pytest.mark.unit
def test_recommend_target_position_matches_product_resume():
    result = recommend_target_position(
        "我负责 PRD、需求分析、竞品调研和原型设计。",
        "resume.docx",
    )

    assert result["target_position"] == "产品助理/产品经理实习生"
    assert result["source"] == "heuristic"


@pytest.mark.unit
def test_recommend_target_position_uses_filename_signal_for_product_resume():
    result = recommend_target_position(
        "Python FastAPI PostgreSQL Docker API 项目经历",
        "简历_AI产品经历版_20260510.docx",
    )

    assert result["target_position"] == "产品助理/产品经理实习生"


@pytest.mark.unit
def test_semi_synthetic_metadata_is_blocked_from_real_sft(tmp_path):
    source = tmp_path / "resume.docx"
    source.write_text("demo", encoding="utf-8")

    metadata = semi_synthetic_metadata(source, "abc123", "产品助理/产品经理实习生")

    assert metadata["sample_origin"] == "simulated_from_resume"
    assert metadata["candidate_answer_source"] == "ai_simulated"
    assert metadata["for_real_sft"] is False
    assert metadata["for_training"] is False
    assert metadata["data_contribution_consent"] is False
    assert metadata["semi_synthetic_data_contribution"] is False
    assert metadata["for_competition_demo"] is True


@pytest.mark.unit
def test_semi_synthetic_metadata_can_be_contributed_without_becoming_real_sft(tmp_path):
    source = tmp_path / "resume.docx"
    source.write_text("demo", encoding="utf-8")

    metadata = semi_synthetic_metadata(
        source,
        "abc123",
        "产品助理/产品经理实习生",
        data_contribution_consent=True,
    )

    assert metadata["sample_origin"] == "simulated_from_resume"
    assert metadata["candidate_answer_source"] == "ai_simulated"
    assert metadata["data_contribution_consent"] is True
    assert metadata["semi_synthetic_data_contribution"] is True
    assert metadata["for_semi_synthetic_training"] is True
    assert metadata["for_real_sft"] is False
    assert metadata["for_training"] is False


@pytest.mark.unit
def test_dry_run_extracts_docx_and_blocks_image(tmp_path):
    from docx import Document

    resume_dir = tmp_path / "resumes"
    out_dir = tmp_path / "out"
    resume_dir.mkdir()

    document = Document()
    document.add_paragraph("教育经历 北京大学 产品管理")
    document.add_paragraph("项目经历 PRD 需求分析 用户访谈 原型设计")
    document.add_paragraph("专业技能 SQL Python 数据分析")
    document.save(resume_dir / "product_resume.docx")
    (resume_dir / "scan.jpg").write_bytes(b"\xff\xd8\xffdemo")

    result = dry_run(resume_dir, out_dir, target_position=None, limit=None)

    assert result["summary"]["total_files"] == 2
    assert result["summary"]["ready_files"] == 1
    assert result["summary"]["blocked_files"] == 1

    manifest = json.loads((out_dir / "manifest.preview.json").read_text(encoding="utf-8"))
    docx_item = next(item for item in manifest if item["file_name"] == "product_resume.docx")
    image_item = next(item for item in manifest if item["file_name"] == "scan.jpg")
    assert docx_item["metadata"]["sample_origin"] == "simulated_from_resume"
    assert docx_item["metadata"]["candidate_answer_source"] == "ai_simulated"
    assert docx_item["metadata"]["for_real_sft"] is False
    assert image_item["status"] == "blocked"


@pytest.mark.unit
def test_preview_record_keeps_non_training_boundary(tmp_path):
    source = tmp_path / "resume.pdf"
    source.write_bytes(b"demo")
    item = {
        "metadata": semi_synthetic_metadata(source, "hash", "Python后端开发工程师"),
        "resume_id": 1,
        "file_name": "resume.pdf",
        "target_position": "Python后端开发工程师",
        "parse_quality": {"status": "usable"},
        "interview_id": 2,
        "rounds": 3,
        "interview_status": "completed",
        "overall_score": 7.5,
        "polish_result": {"generated": True},
        "report": True,
        "training_review": {"notes": "ok"},
    }

    record = build_preview_record(item)

    assert record["metadata"]["sample_origin"] == "simulated_from_resume"
    assert record["metadata"]["for_real_sft"] is False
    assert record["metadata"]["record_type"] == "semi_synthetic_closed_loop_preview"


@pytest.mark.unit
def test_actual_run_requires_explicit_confirm_cost(tmp_path):
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.scripts.run_resume_closed_loop_batch",
            "--resume-dir",
            str(resume_dir),
        ],
        cwd=".",
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "--confirm-api-cost" in completed.stderr
