import pytest

from app.services.client.learning_task_service import LearningTaskService


@pytest.mark.unit
def test_learning_task_normalize_accepts_legacy_task_id():
    payload = LearningTaskService._normalize_input(
        {
            "task_id": "resume-1__python",
            "title": "补强 FastAPI 项目证据",
            "ability_name": "Python 后端开发",
            "target_position": "Python后端开发工程师",
            "acceptance_criteria": "能讲清一个接口设计练习",
            "priority_score": 88,
            "route_source": "project_builtin_python_backend_route",
            "route_stage": "fastapi_framework",
            "task_type": "demo_practice",
            "estimated_minutes": 120,
            "task_metadata": {"route_stage_title": "FastAPI 框架与工程结构"},
        }
    )

    assert payload["task_key"] == "resume-1__python"
    assert payload["title"] == "补强 FastAPI 项目证据"
    assert payload["priority_score"] == "88"
    assert payload["acceptance_criteria"] == ["能讲清一个接口设计练习"]
    assert payload["done"] is None
    assert payload["route_stage"] == "fastapi_framework"
    assert payload["estimated_minutes"] == 120
    assert payload["task_metadata"]["route_stage_title"] == "FastAPI 框架与工程结构"


@pytest.mark.unit
def test_learning_task_normalize_generates_stable_task_key():
    payload = LearningTaskService._normalize_input(
        {
            "title": "整理产品需求分析案例",
            "ability_name": "需求分析",
            "target_position": "产品助理",
            "source_type": "ability_gap",
            "source_id": "resume-9",
        }
    )

    assert payload["task_key"].startswith("ability_gap__resume-9")
    assert len(payload["task_key"]) <= 160
