import json

import pytest

from app.scripts.summarize_semi_synthetic_run import build_sanitized_summary, write_summary_files


@pytest.mark.unit
def test_summarize_semi_synthetic_run_excludes_file_names_and_full_payload(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "mode": "actual",
                "total_files": 1,
                "completed": 1,
                "failed": 0,
                "blocked": 0,
                "semi_synthetic_data_contribution": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "run_result.json").write_text(
        json.dumps(
            [
                {
                    "file_name": "张三_13800000000.docx",
                    "sha256": "abcdef1234567890",
                    "target_position": "产品助理",
                    "status": "completed",
                    "resume_id": 11,
                    "interview_id": 22,
                    "rounds": 3,
                    "metadata": {
                        "sample_origin": "simulated_from_resume",
                        "candidate_answer_source": "ai_simulated",
                        "data_contribution_consent": True,
                        "for_real_sft": False,
                        "for_training": False,
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_sanitized_summary(run_dir)
    _, md_path = write_summary_files(run_dir, payload)
    md_text = md_path.read_text(encoding="utf-8")

    assert payload["records"][0]["source_sha256_prefix"] == "abcdef123456"
    assert "file_name" not in json.dumps(payload, ensure_ascii=False)
    assert "张三" not in md_text
    assert "13800000000" not in md_text
    assert "simulated_from_resume" in md_text
    assert "ai_simulated" in md_text
