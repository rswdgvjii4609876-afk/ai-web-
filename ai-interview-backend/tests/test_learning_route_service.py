import pytest

from app.exceptions.http_exceptions import ValidationError
from app.models.learning_route_stage import LearningRouteStage
from app.services.backoffice.learning_route_service import LearningRouteService


@pytest.mark.unit
def test_learning_route_quality_hints_detect_missing_fields():
    hints = LearningRouteService.quality_hints(
        {
            "practice_task": "",
            "acceptance_criteria": [],
            "estimated_minutes": None,
            "keywords": [],
        }
    )

    assert "缺少练习任务" in hints
    assert "缺少验收方式" in hints
    assert "缺少预计耗时" in hints
    assert "缺少关键词" in hints


@pytest.mark.unit
def test_learning_route_quality_summary_counts_levels():
    summary = LearningRouteService.quality_summary(
        [
            {
                "practice_task": "完成练习",
                "acceptance_criteria": ["可验收"],
                "estimated_minutes": 60,
                "keywords": ["api"],
            },
            {
                "practice_task": "",
                "acceptance_criteria": ["可验收"],
                "estimated_minutes": 60,
                "keywords": ["prd"],
            },
            {
                "practice_task": "完成练习",
                "acceptance_criteria": ["可验收"],
                "estimated_minutes": None,
                "keywords": ["redis"],
            },
        ]
    )

    assert summary["complete_total"] == 1
    assert summary["not_recommended_total"] == 1
    assert summary["needs_improvement_total"] == 1
    assert summary["missing_practice_total"] == 1
    assert summary["missing_minutes_total"] == 1


@pytest.mark.unit
def test_learning_route_import_identity_rejects_missing_key_fields():
    with pytest.raises(ValidationError):
        LearningRouteService._import_identity({"stage_title": "缺少阶段编码", "task_type": "case_practice"})


@pytest.mark.unit
def test_learning_route_duplicate_payload_is_inactive_copy():
    item = LearningRouteStage(
        id=7,
        job_id="python_backend",
        job_name="Python后端开发工程师",
        category="技术岗",
        route_source="db_route",
        route_stage="fastapi",
        stage_title="FastAPI 接口",
        material_type="route",
        task_type="project_practice",
        estimated_minutes=120,
        keywords=["FastAPI"],
        learning_material="学习 FastAPI",
        practice_task="完成接口练习",
        acceptance_criteria=["能说明接口设计"],
        is_active=True,
        sort_order=3,
    )

    payload = LearningRouteService._duplicate_payload(item)

    assert payload["route_stage"] == "fastapi_copy_7"
    assert payload["stage_title"] == "FastAPI 接口 副本"
    assert payload["is_active"] is False
    assert payload["sort_order"] == 4


@pytest.mark.unit
def test_learning_route_preview_task_uses_route_content():
    route = {
        "route_source": "db_python_route",
        "route_stage": "fastapi",
        "title": "FastAPI 接口",
        "material_type": "route",
        "task_type": "project_practice",
        "estimated_minutes": 120,
        "keywords": ["FastAPI"],
        "material": "学习 FastAPI",
        "practice_task": "完成一个 FastAPI 接口练习",
        "acceptance_criteria": ["能说明接口设计", "能完成异常处理"],
    }

    task = LearningRouteService.preview_task_from_route(
        route,
        target_position="Python后端开发工程师",
        job_id="python_backend",
        category="技术岗",
        ability_name="接口设计能力",
        missing_keywords=["FastAPI"],
    )

    assert task["route_source"] == "db_python_route"
    assert task["route_stage"] == "fastapi"
    assert task["practice_task"] == "完成一个 FastAPI 接口练习"
    assert task["acceptance_criteria"] == ["能说明接口设计", "能完成异常处理"]
    assert task["estimated_minutes"] == 120


@pytest.mark.unit
def test_learning_route_coverage_matrix_returns_all_position_profiles():
    matrix = LearningRouteService.coverage_matrix(
        [
            {
                "route_id": 1,
                "job_id": "python_backend",
                "job_name": "Python后端开发工程师",
                "category": "技术岗",
                "route_source": "db_python_route",
                "route_stage": "fastapi",
                "stage_title": "FastAPI 接口",
                "material_type": "route",
                "task_type": "project_practice",
                "estimated_minutes": 120,
                "keywords": ["Python", "FastAPI", "接口"],
                "learning_material": "学习 FastAPI",
                "practice_task": "完成接口练习",
                "acceptance_criteria": ["能说明接口设计"],
                "quality_hints": [],
                "quality_level": "complete",
                "quality_label": "完整",
                "is_active": True,
                "sort_order": 1,
            }
        ]
    )

    python_row = next(item for item in matrix["items"] if item["job_id"] == "python_backend")

    assert matrix["total_positions"] == 12
    assert python_row["ability_total"] >= 6
    assert python_row["active_route_total"] == 1
    assert python_row["complete_route_total"] == 1
    assert python_row["matched_ability_total"] >= 1
    assert python_row["unmatched_ability_total"] >= 1


@pytest.mark.unit
def test_learning_route_coverage_matrix_ignores_inactive_routes_and_flags_bad_quality():
    matrix = LearningRouteService.coverage_matrix(
        [
            {
                "route_id": 1,
                "job_id": "python_backend",
                "category": "技术岗",
                "route_stage": "python_inactive",
                "stage_title": "停用 Python 路线",
                "task_type": "project_practice",
                "estimated_minutes": 120,
                "keywords": ["Python"],
                "practice_task": "完成练习",
                "acceptance_criteria": ["可验收"],
                "is_active": False,
                "sort_order": 1,
            },
            {
                "route_id": 2,
                "job_id": "product_assistant",
                "category": "产品岗",
                "route_stage": "prd_missing",
                "stage_title": "PRD 路线",
                "task_type": "document_output",
                "estimated_minutes": 90,
                "keywords": ["PRD"],
                "practice_task": "",
                "acceptance_criteria": [],
                "is_active": True,
                "sort_order": 1,
            },
        ]
    )

    python_row = next(item for item in matrix["items"] if item["job_id"] == "python_backend")
    product_row = next(item for item in matrix["items"] if item["job_id"] == "product_assistant")

    assert python_row["active_route_total"] == 0
    assert python_row["matched_ability_total"] == 0
    assert product_row["status"] == "not_recommended"
    assert product_row["missing_practice_total"] == 1
    assert product_row["missing_acceptance_total"] == 1


@pytest.mark.unit
def test_match_loaded_routes_prefers_job_specific_route():
    records = [
        {
            "job_id": None,
            "category": "技术岗",
            "route_source": "category_route",
            "route_stage": "tech_general",
            "stage_title": "技术通用",
            "material_type": "category",
            "task_type": "theory_demo",
            "estimated_minutes": 60,
            "keywords": ["api"],
            "learning_material": "category material",
            "sort_order": 1,
        },
        {
            "job_id": "python_backend",
            "category": "技术岗",
            "route_source": "db_python_route",
            "route_stage": "fastapi_db",
            "stage_title": "FastAPI 后台路线",
            "material_type": "db",
            "task_type": "project_practice",
            "estimated_minutes": 120,
            "keywords": ["fastapi"],
            "learning_material": "python material",
            "practice_task": "build api",
            "acceptance_criteria": ["run api"],
            "sort_order": 1,
        },
    ]

    route = LearningRouteService.match_loaded_routes(
        records=records,
        job_id="python_backend",
        text="need FastAPI project evidence",
        category="技术岗",
    )

    assert route["route_source"] == "db_python_route"
    assert route["route_stage"] == "fastapi_db"
    assert route["practice_task"] == "build api"
    assert route["acceptance_criteria"] == ["run api"]


@pytest.mark.unit
def test_match_loaded_routes_uses_category_when_job_missing():
    route = LearningRouteService.match_loaded_routes(
        records=[
            {
                "job_id": None,
                "category": "产品岗",
                "route_source": "db_product_route",
                "route_stage": "prd_case",
                "stage_title": "PRD 练习",
                "material_type": "db",
                "task_type": "document_output",
                "estimated_minutes": 90,
                "keywords": ["prd"],
                "learning_material": "product material",
                "sort_order": 1,
            }
        ],
        job_id="custom_position",
        text="write PRD and prototype",
        category="产品岗",
    )

    assert route["route_source"] == "db_product_route"
    assert route["route_stage"] == "prd_case"
