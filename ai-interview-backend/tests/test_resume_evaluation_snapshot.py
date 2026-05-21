import pytest

from app.services.client.resume_evaluation_snapshot import (
    RESUME_EVALUATION_VERSION,
    ability_profile_from_payload,
    build_resume_evaluation_snapshot,
    ensure_resume_evaluation_snapshot,
    learning_plan_from_payload,
    matching_metrics_from_payload,
)


@pytest.mark.unit
def test_resume_evaluation_snapshot_builds_from_matching_metrics():
    metrics = {
        "engine_version": "test_engine",
        "target_position": "Python后端开发工程师",
        "final_score": 72,
        "semantic_score": 68,
        "rule_score": 70,
        "skill_presence_score": 66,
        "evidence_depth_score": 38,
        "declared_skill_score_floor": 58,
        "keyword_coverage": {
            "score": 0.6,
            "matched": ["Python"],
            "missing": ["Redis"],
            "direct_matches": ["Python"],
            "related_matches": ["SQL"],
            "verification_needed": ["Redis"],
            "skill_presence_score": 66,
            "evidence_depth_score": 38,
            "evidence_statuses": [{"keyword": "Redis", "status": "claimed_only"}],
        },
        "ability_gap_profile": {
            "top_gaps": [
                {
                    "ability_id": "redis",
                    "name": "缓存与 Redis 应用",
                    "evidence_status": "claimed_only",
                    "priority_score": 82,
                    "verification_priority": "high",
                    "verification_keywords": ["Redis"],
                    "evidence_basis": "技能栏有声明，但缺少项目证据。",
                }
            ],
        },
        "learning_priority_summary": ["优先验证 Redis 使用场景"],
        "verification_priority_summary": ["Redis：已声明，需要面试验证深度"],
        "learning_gap_summary": ["SQL：需要补充项目细节"],
        "learning_plan": {"version": "learning_plan_v1", "tasks": [{"title": "Redis 场景练习"}]},
    }

    snapshot = build_resume_evaluation_snapshot(matching_metrics=metrics)

    assert snapshot["version"] == RESUME_EVALUATION_VERSION
    assert snapshot["scores"]["final_score"] == 72
    assert snapshot["scores"]["skill_presence_score"] == 66
    assert snapshot["scores"]["evidence_depth_score"] == 38
    assert snapshot["keyword_evidence"]["verification_needed"] == ["Redis"]
    assert snapshot["ability_profile"]["top_gaps"][0]["evidence_status"] == "claimed_only"
    assert snapshot["verification_priority_summary"] == ["Redis：已声明，需要面试验证深度"]
    assert snapshot["learning_gap_summary"] == ["SQL：需要补充项目细节"]
    assert snapshot["verification_targets"][0]["ability_name"] == "缓存与 Redis 应用"
    assert snapshot["learning_plan"]["tasks"][0]["title"] == "Redis 场景练习"


@pytest.mark.unit
def test_ensure_snapshot_keeps_legacy_fields_aligned():
    analysis = {
        "matching_metrics": {
            "final_score": 61,
            "keyword_coverage": {"score": 0.4, "missing": ["SQL"]},
            "ability_gap_profile": {"top_gaps": [{"name": "数据库", "evidence_status": "missing"}]},
            "learning_plan": {"tasks": [{"title": "SQL 练习"}]},
        }
    }

    aligned = ensure_resume_evaluation_snapshot(analysis, target_position="数据分析师")

    assert aligned["resume_evaluation_snapshot"]["target_position"] == "数据分析师"
    assert aligned["ability_gap_profile"]["top_gaps"][0]["name"] == "数据库"
    assert aligned["learning_plan"]["tasks"][0]["title"] == "SQL 练习"
    assert aligned["matching_metrics"]["resume_evaluation_snapshot"]["version"] == RESUME_EVALUATION_VERSION


@pytest.mark.unit
def test_old_payload_without_snapshot_can_be_read_through_helpers():
    old_payload = {
        "ability_gap_profile": {"items": [{"name": "需求分析", "evidence_status": "indirect"}]},
        "learning_plan": {"tasks": [{"title": "PRD 复盘"}]},
        "matching_metrics": {"final_score": 75, "keyword_coverage": {"score": 0.7}},
    }

    profile = ability_profile_from_payload(old_payload)
    plan = learning_plan_from_payload(old_payload)
    metrics = matching_metrics_from_payload(old_payload)

    assert profile["items"][0]["name"] == "需求分析"
    assert plan["tasks"][0]["title"] == "PRD 复盘"
    assert metrics["ability_gap_profile"]["items"][0]["evidence_status"] == "indirect"
    assert metrics["resume_evaluation_snapshot"]["scores"]["final_score"] == 75


@pytest.mark.unit
def test_matching_metrics_helper_backfills_new_snapshot_fields():
    payload = {
        "resume_evaluation_snapshot": {
            "version": RESUME_EVALUATION_VERSION,
            "scores": {
                "final_score": 62,
                "skill_presence_score": 70,
                "evidence_depth_score": 35,
                "declared_skill_score_floor": 58,
            },
            "ability_profile": {"items": []},
            "learning_plan": {"tasks": []},
            "learning_priority_summary": ["优先验证 FastAPI"],
            "verification_priority_summary": ["FastAPI：已声明，待验证项目证据"],
            "learning_gap_summary": ["Celery：需要补强"],
        }
    }

    metrics = matching_metrics_from_payload(payload)

    assert metrics["skill_presence_score"] == 70
    assert metrics["evidence_depth_score"] == 35
    assert metrics["declared_skill_score_floor"] == 58
    assert metrics["verification_priority_summary"] == ["FastAPI：已声明，待验证项目证据"]
    assert metrics["learning_gap_summary"] == ["Celery：需要补强"]
