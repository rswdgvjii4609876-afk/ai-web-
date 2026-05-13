from pathlib import Path

from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    build_import_plans,
    _package_paths,
)


def test_member_knowledge_packages_validate_and_build_content():
    plans = build_import_plans(_package_paths(Path(DEFAULT_SOURCE)))

    positions = {plan.target_position for plan in plans}
    assert {
        "Python后端开发工程师",
        "Java后端开发工程师",
        "前端开发工程师",
        "算法工程师",
        "产品助理",
        "运营助理",
        "人力资源专员",
    }.issubset(positions)

    python_plan = next(plan for plan in plans if plan.target_position == "Python后端开发工程师")
    assert python_plan.db_title == "成员资料补充：Python后端开发工程师"
    assert "## 岗位要求" in python_plan.knowledge_content
    assert "## 问答经验" in python_plan.knowledge_content
    assert "## 能力模型" in python_plan.knowledge_content
    assert "## 面试追问" in python_plan.knowledge_content
    assert "审核状态：可入库" in python_plan.knowledge_content
    assert python_plan.enabled_experiences >= 1
