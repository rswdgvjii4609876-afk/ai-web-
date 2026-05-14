from pathlib import Path

from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    build_import_plans,
    merge_interview_experience_section,
    merge_knowledge_content,
    _package_paths,
)


def test_member_knowledge_packages_validate_and_build_canonical_merge_content():
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
    assert python_plan.canonical_title == "职启智评岗位画像：Python后端开发工程师"
    assert "## 岗位要求" in python_plan.knowledge_content
    assert "## 问答经验" in python_plan.knowledge_content
    assert "## 能力模型" in python_plan.knowledge_content
    assert "## 面试追问" in python_plan.knowledge_content
    assert "审核状态：可入库" in python_plan.knowledge_content
    assert python_plan.enabled_experiences >= 1


def test_merge_knowledge_content_appends_supplement_sections_without_creating_new_profile():
    existing = """## 岗位要求
熟悉 Python Web、数据库和接口开发。

## 问答经验
### 面经 1：如何设计接口鉴权？
- 真实问题：如何设计接口鉴权？
- 参考回答要点：说明 token、权限、过期和错误处理。
- 来源说明：原有画像
- 审核状态：可入库
"""
    supplement = """## 岗位要求
补充关注 Redis 缓存一致性和线上排障。

## 问答经验
### 面经 1：如何设计接口鉴权？
- 真实问题：如何设计接口鉴权？
- 参考回答要点：说明 token、权限、过期和错误处理。
- 来源说明：原有画像
- 审核状态：可入库

### 面经 2：Redis 缓存穿透怎么处理？
- 真实问题：Redis 缓存穿透怎么处理？
- 参考回答要点：说明布隆过滤器、空值缓存和限流。
- 来源说明：成员资料
- 审核状态：可入库

## 能力模型
缓存与排障：要求 4 级。

## 面试追问
如果候选人只写熟悉 Redis，需要追问真实项目场景。
"""

    merged, stats = merge_knowledge_content(existing, supplement, "Python 成员补充包")

    assert "成员资料补充：Python 成员补充包" in merged
    assert merged.count("如何设计接口鉴权") == 2  # heading + real-question field, no duplicated card
    assert "Redis 缓存穿透怎么处理" in merged
    assert stats["interview_experiences_added"] == 1
    assert stats["sections_added"] >= 1


def test_merge_interview_experience_section_deduplicates_by_question_and_source():
    existing = """### 面经 1：招聘漏斗是什么？
- 真实问题：招聘漏斗是什么？
- 参考回答要点：投递、筛选、邀约、面试、offer、入职。
- 来源说明：成员 A
- 审核状态：可入库
"""
    supplement = existing + """

### 面经 2：候选人失联怎么办？
- 真实问题：候选人失联怎么办？
- 参考回答要点：多渠道触达、复盘动机和跟进节奏。
- 来源说明：成员 B
- 审核状态：可入库
"""

    merged, added = merge_interview_experience_section(existing, supplement)

    assert added == 1
    assert "候选人失联怎么办" in merged
    assert merged.count("招聘漏斗是什么") == 2
