import pytest

from app.constants.competition import POSITION_PROFILES
from app.constants.learning_routes import match_learning_route_stage
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


@pytest.mark.unit
def test_python_backend_learning_plan_uses_local_python_routes():
    python_profile = next(profile for profile in POSITION_PROFILES if profile.get("job_id") == "python_backend")
    metrics = matching_engine.evaluate(
        parsed_resume={
            "skills": ["Python"],
            "projects": [
                {
                    "name": "Data script",
                    "description": "Used Python to clean CSV files, but no FastAPI, Redis, Docker, or SQL evidence.",
                }
            ],
        },
        target_position=python_profile.get("job_name"),
        llm_analysis={"overall_score": 6},
        resume_evidence={"projects": ["Python CSV script"]},
    )

    plan = metrics["learning_plan"]
    assert plan["version"] == "learning_plan_v1"
    assert plan["source_ability_gap_engine"] == "ability_gap_v1"
    assert len(plan["tasks"]) >= 3
    assert any(
        "python后端学习路线.md" in task["learning_material"]
        or "python基础学习路线.md" in task["learning_material"]
        for task in plan["tasks"]
    )
    assert any(task.get("route_stage") for task in plan["tasks"])
    assert any(task.get("route_source", "").startswith("project_builtin_python") for task in plan["tasks"])
    for task in plan["tasks"]:
        assert task["task_id"]
        assert task["ability_name"]
        assert task["practice_task"]
        assert task["deliverable"]
        assert task["acceptance_criteria"]
        assert task["task_type"]
        assert task["estimated_minutes"] > 0
        assert 0 <= task["priority_score"] <= 100


@pytest.mark.unit
def test_learning_plan_falls_back_to_general_template_for_custom_position():
    metrics = matching_engine.evaluate(
        parsed_resume={
            "skills": ["communication"],
            "projects": [{"name": "Volunteer project", "description": "Coordinated campus event workflow."}],
        },
        target_position="校园项目协调员",
        llm_analysis={"overall_score": 5},
        resume_evidence={"projects": ["campus event"]},
    )

    plan = metrics["learning_plan"]
    assert plan["version"] == "learning_plan_v1"
    assert len(plan["tasks"]) >= 3
    assert all(task["route_stage"] for task in plan["tasks"])
    assert all(task["route_source"].startswith("project_builtin_") for task in plan["tasks"])


@pytest.mark.unit
@pytest.mark.parametrize(
    ("job_id", "category", "text", "route_source"),
    [
        ("java_backend", "技术岗", "Java Spring Boot MySQL Redis JVM 线程", "project_builtin_java_backend_route"),
        ("frontend_engineer", "技术岗", "TypeScript Vue React Vite 性能优化", "project_builtin_frontend_route"),
        ("qa_engineer", "技术岗", "测试用例 接口测试 Pytest 缺陷定位", "project_builtin_qa_route"),
        ("algorithm_engineer", "技术岗", "机器学习 特征工程 Embedding 模型评估", "project_builtin_algorithm_route"),
        ("data_analyst", "数据岗", "SQL 指标 可视化 业务归因", "project_builtin_data_analyst_route"),
        ("product_assistant", "产品岗", "需求 PRD 原型 指标复盘", "project_builtin_product_position_route"),
        ("operations_assistant", "运营岗", "活动执行 用户反馈 数据复盘", "project_builtin_operations_route"),
        ("new_media_operator", "运营岗", "内容选题 文案 阅读量 账号迭代", "project_builtin_new_media_route"),
        ("hr_specialist", "职能岗", "招聘流程 候选人 劳动合同 Excel", "project_builtin_hr_route"),
        ("recruiting_assistant", "职能岗", "招聘渠道 简历筛选 面试邀约 数据记录", "project_builtin_recruiting_route"),
        ("admin_assistant", "职能岗", "办公软件 会议组织 流程执行 服务合规", "project_builtin_admin_route"),
    ],
)
def test_multi_position_learning_routes_match_specific_job(job_id, category, text, route_source):
    route = match_learning_route_stage(job_id=job_id, category=category, text=text)

    assert route["route_source"] == route_source
    assert route["route_stage"] != "general_position_improvement"
    assert route["estimated_minutes"] > 0
    assert route["task_type"]


@pytest.mark.unit
def test_non_technical_learning_plan_uses_case_or_document_tasks_not_demo():
    metrics = matching_engine.evaluate(
        parsed_resume={
            "skills": ["Excel", "沟通", "用户调研"],
            "projects": [{"name": "校园调研", "description": "收集用户反馈，整理需求并输出复盘。"}],
        },
        target_position="产品助理",
        llm_analysis={"overall_score": 6},
        resume_evidence={"projects": ["用户反馈和需求整理"]},
    )

    tasks = metrics["learning_plan"]["tasks"]
    assert tasks
    assert all(task["route_source"] == "project_builtin_product_position_route" for task in tasks)
    assert any(task["task_type"] in {"case_practice", "document_output", "scenario_practice"} for task in tasks)
    assert all("小 Demo" not in task["practice_task"] for task in tasks)
