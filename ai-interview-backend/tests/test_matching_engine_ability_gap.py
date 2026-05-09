import pytest

from app.constants.competition import POSITION_PROFILES
from app.services.client.matching_engine import matching_engine


@pytest.mark.unit
def test_all_position_profiles_have_ability_model():
    assert len(POSITION_PROFILES) >= 12
    for profile in POSITION_PROFILES:
        ability_model = profile.get("ability_model") or []
        assert len(ability_model) >= 6, profile.get("job_name")
        for ability in ability_model:
            assert ability.get("name")
            assert 1 <= float(ability.get("required_level", 0)) <= 5
            assert 0 < float(ability.get("weight", 0)) <= 1
            assert ability.get("keywords")
            assert ability.get("evidence_hints")


@pytest.mark.unit
def test_python_backend_ability_gap_profile_has_priority_items():
    metrics = matching_engine.evaluate(
        parsed_resume={
            "skills": ["Python"],
            "projects": [
                {
                    "name": "Course project",
                    "description": "Used Python scripts to process CSV data.",
                }
            ],
        },
        target_position="Python后端开发工程师",
        llm_analysis={"overall_score": 6},
        resume_evidence={"projects": ["Python course project"]},
    )

    profile = metrics["ability_gap_profile"]
    assert profile["matched_profile"]["job_id"] == "python_backend"
    assert len(profile["items"]) >= 6
    assert profile["top_gaps"]
    assert 0 <= profile["overall_match_score"] <= 100
    assert metrics["learning_priority_summary"]
    assert all(0 <= item["match_score"] <= 100 for item in profile["items"])
    assert all(item["priority_score"] >= 0 for item in profile["items"])


@pytest.mark.unit
def test_product_assistant_ability_gap_profile_has_priority_items():
    metrics = matching_engine.evaluate(
        parsed_resume={
            "skills": ["Excel", "research"],
            "projects": [
                {
                    "name": "Campus activity",
                    "description": "Collected student feedback and summarized issues.",
                }
            ],
        },
        target_position="产品助理",
        llm_analysis={"overall_score": 6},
        resume_evidence={"projects": ["feedback summary"]},
    )

    profile = metrics["ability_gap_profile"]
    assert profile["matched_profile"]["job_id"] == "product_assistant"
    assert len(profile["items"]) >= 6
    assert profile["top_gaps"]
    assert 0 <= profile["overall_match_score"] <= 100
    assert metrics["learning_priority_summary"]
