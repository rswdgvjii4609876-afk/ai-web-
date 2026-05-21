import pytest

from app.services.client.learning_plan_service import LearningPlanService


@pytest.mark.unit
def test_learning_plan_builds_editable_tasks_from_route_records():
    records = [
        {
            "job_id": "python_backend",
            "category": "技术岗",
            "route_source": "test_template",
            "route_stage": "fastapi_framework",
            "route_kind": "template",
            "plan_group": "python-backend-30d",
            "stage_title": "FastAPI 接口训练",
            "title": "FastAPI 接口训练",
            "material_type": "backend_route",
            "task_type": "project_practice",
            "estimated_minutes": 90,
            "keywords": ["FastAPI", "接口"],
            "learning_material": "阅读 FastAPI 路由、依赖注入和异常处理资料。",
            "material": "阅读 FastAPI 路由、依赖注入和异常处理资料。",
            "practice_task": "完成一个用户信息查询接口，并记录异常处理方式。",
            "acceptance_criteria": ["能说明接口设计取舍", "能展示可运行代码"],
            "is_active": True,
            "sort_order": 1,
        }
    ]
    abilities = [
        {
            "ability_id": "api_design",
            "name": "接口设计能力",
            "missing_keywords": ["FastAPI", "接口"],
            "matched_keywords": [],
            "priority_score": 88,
            "current_level": 1,
            "required_level": 3,
            "gap": 2,
            "evidence_basis": "简历缺少后端接口项目证据。",
        }
    ]

    plan = LearningPlanService._build_tasks_from_records(
        records=records,
        abilities=abilities,
        target_position="Python后端开发工程师",
    )

    assert plan["version"] == "learning_plan_v2"
    assert plan["task_count"] == 1
    task = plan["tasks"][0]
    assert task["source_type"] == "generated_learning_plan"
    assert task["target_position"] == "Python后端开发工程师"
    assert task["route_stage"] == "fastapi_framework"
    assert task["estimated_minutes"] == 90
    assert task["task_metadata"]["plan_group"] == "python-backend-30d"


@pytest.mark.unit
def test_learning_plan_preserves_interview_verification_action_type():
    abilities = LearningPlanService._normalize_abilities(
        [
            {
                "ability_id": "api_design",
                "name": "接口设计能力",
                "evidence_status": "claimed_only",
                "verification_keywords": ["FastAPI"],
                "missing_keywords": ["接口压测"],
                "matched_keywords": ["FastAPI"],
                "priority_score": 80,
            }
        ]
    )

    assert abilities[0]["action_type"] == "interview_verification"
    assert abilities[0]["verification_keywords"] == ["FastAPI"]

    plan = LearningPlanService._build_tasks_from_records(
        records=[],
        abilities=abilities,
        target_position="Python后端开发工程师",
    )

    task = plan["tasks"][0]
    assert task["task_metadata"]["action_type"] == "interview_verification"
    assert task["task_metadata"]["source_action_type"] == "interview_verification"
    assert task["title"].startswith("准备验证")
    assert "FastAPI" in task["practice_task"]
    assert "接口压测" not in task["practice_task"]


@pytest.mark.unit
def test_learning_plan_legacy_indirect_defaults_to_evidence_completion():
    abilities = LearningPlanService._normalize_abilities(
        [
            {
                "ability_id": "api_design",
                "name": "接口设计能力",
                "evidence_status": "indirect",
                "matched_keywords": ["REST API"],
                "missing_keywords": ["异常处理"],
            }
        ]
    )

    assert abilities[0]["action_type"] == "evidence_completion"


@pytest.mark.unit
def test_learning_plan_ai_refinement_preserves_route_metadata():
    deterministic_tasks = [
        {
            "title": "API practice",
            "learning_material": "Read local route notes",
            "practice_task": "Build one endpoint",
            "acceptance_criteria": ["endpoint works"],
            "estimated_minutes": 90,
            "route_stage": "fastapi_framework",
            "route_source": "template_route",
            "task_metadata": {"route_stage_title": "FastAPI"},
        }
    ]
    ai_tasks = [
        {
            "title": "Refined API practice",
            "learning_material": "Read official FastAPI docs",
            "practice_task": "Build and document one endpoint",
            "acceptance_criteria": ["endpoint works", "docs included"],
            "estimated_minutes": 10,
            "route_stage": "overwritten_stage",
            "route_source": "web_search",
            "task_metadata": {"lost": True},
        }
    ]

    merged = LearningPlanService._merge_ai_task_overrides(deterministic_tasks, ai_tasks)

    assert merged[0]["title"] == "Refined API practice"
    assert merged[0]["learning_material"] == "Read official FastAPI docs"
    assert merged[0]["estimated_minutes"] == 90
    assert merged[0]["route_stage"] == "fastapi_framework"
    assert merged[0]["route_source"] == "template_route"
    assert merged[0]["task_metadata"] == {"route_stage_title": "FastAPI"}


@pytest.mark.unit
def test_learning_plan_ai_refinement_keeps_base_tasks_when_ai_returns_partial_list():
    deterministic_tasks = [
        {
            "title": "API practice",
            "learning_material": "Read local route notes",
            "practice_task": "Build one endpoint",
            "acceptance_criteria": ["endpoint works"],
            "estimated_minutes": 90,
            "route_stage": "fastapi_framework",
            "route_source": "template_route",
            "task_metadata": {"route_stage_title": "FastAPI"},
        },
        {
            "title": "Redis practice",
            "learning_material": "Read Redis notes",
            "practice_task": "Explain cache invalidation",
            "acceptance_criteria": ["explanation is concrete"],
            "estimated_minutes": 60,
            "route_stage": "redis_cache",
            "route_source": "template_route",
            "task_metadata": {"route_stage_title": "Redis"},
        },
    ]

    merged = LearningPlanService._merge_ai_task_overrides(
        deterministic_tasks,
        [{"title": "Refined API practice"}],
    )

    assert len(merged) == 2
    assert merged[0]["title"] == "Refined API practice"
    assert merged[1]["title"] == "Redis practice"
    assert merged[1]["route_stage"] == "redis_cache"
