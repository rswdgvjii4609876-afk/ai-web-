from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, List

from app.services.agent_orchestrator.asset_guardrails import (
    direct_identifier_hits,
    sort_demo_cases,
    validate_demo_preview_asset,
)


DIRECT_IDENTIFIER_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"(?:姓名|手机号|电话|邮箱|学号|身份证|详细住址)\s*[:：]\s*[^,，;；\n]{2,}"),
)


DEMO_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "python_backend",
        "title": "C1 Python 后端开发工程师沙盘",
        "sample_origin": "demo_constructed",
        "for_training": False,
        "for_competition_demo": True,
        "target_role": "Python 后端开发工程师",
        "resume_summary": {
            "education": "华南地区本科院校，计算机相关专业，应届生",
            "experience_level": "课程项目 + 校内实习",
            "projects": [
                {
                    "name": "校园二手交易平台",
                    "description": "基于 Flask 和 PostgreSQL 完成商品、订单、用户接口，负责接口开发、表结构设计和联调。",
                    "skills": ["Python", "Flask", "PostgreSQL", "Linux 基础"],
                    "evidence_status": "direct",
                }
            ],
            "skills": ["Python", "Flask", "PostgreSQL", "Linux 基础", "Git"],
        },
        "role_profile": {
            "core_abilities": ["REST API", "SQL 与索引", "Redis 缓存", "并发基础", "部署排障"],
            "role_requirements": [
                "能独立说明接口设计、异常处理和参数校验",
                "能解释数据库表设计、索引、事务和慢查询定位",
                "了解 Redis 缓存常见问题和一致性风险",
            ],
        },
        "evidence_items": [
            {
                "ability": "REST API",
                "resume_evidence": "项目描述出现 Flask 接口、商品/订单/用户模块和联调",
                "evidence_status": "direct",
                "risk": "需要验证个人负责边界",
                "interview_focus": "接口职责、异常返回、参数校验、权限处理",
            },
            {
                "ability": "SQL 与索引",
                "resume_evidence": "出现 PostgreSQL 和表结构设计，但没有慢查询或索引优化案例",
                "evidence_status": "indirect",
                "risk": "数据库能力可能停留在建表和简单查询",
                "interview_focus": "索引设计、事务、慢查询定位",
            },
            {
                "ability": "Redis 缓存",
                "resume_evidence": "简历未出现 Redis、缓存或性能优化相关经历",
                "evidence_status": "missing",
                "risk": "目标岗位高频考察缓存能力",
                "interview_focus": "缓存穿透、击穿、一致性、性能指标",
            },
        ],
    },
    {
        "case_id": "product_assistant",
        "title": "C2 产品助理/产品经理实习生沙盘",
        "sample_origin": "demo_constructed",
        "for_training": False,
        "for_competition_demo": True,
        "target_role": "产品助理/产品经理实习生",
        "resume_summary": {
            "education": "综合类本科院校，信息管理相关专业，应届生",
            "experience_level": "校园项目 + 社团运营",
            "projects": [
                {
                    "name": "校园活动报名小程序需求整理",
                    "description": "参与问卷收集、用户访谈和功能清单整理，协助输出流程图和原型草稿。",
                    "skills": ["问卷调研", "Axure", "流程图", "竞品分析"],
                    "evidence_status": "indirect",
                }
            ],
            "skills": ["需求分析", "用户访谈", "Axure", "Excel"],
        },
        "role_profile": {
            "core_abilities": ["需求分析", "PRD 输出", "竞品分析", "跨部门沟通", "数据意识"],
            "role_requirements": [
                "能把模糊需求拆成场景、用户故事和验收标准",
                "能说明 PRD 的结构和优先级取舍",
                "能用数据或反馈验证功能效果",
            ],
        },
        "evidence_items": [
            {
                "ability": "需求分析",
                "resume_evidence": "出现问卷、访谈、功能清单和流程图",
                "evidence_status": "indirect",
                "risk": "需要验证是否真正参与需求拆解",
                "interview_focus": "需求来源、用户场景、优先级取舍",
            },
            {
                "ability": "PRD 输出",
                "resume_evidence": "只提到原型草稿，没有明确 PRD 文档或验收标准",
                "evidence_status": "claimed_only",
                "risk": "产品文档能力证据不足",
                "interview_focus": "PRD 结构、验收标准、边界条件",
            },
            {
                "ability": "数据意识",
                "resume_evidence": "简历未说明上线指标、转化率或反馈数据",
                "evidence_status": "missing",
                "risk": "缺少功能效果复盘能力",
                "interview_focus": "指标设计、数据复盘、功能迭代",
            },
        ],
    },
    {
        "case_id": "hr_specialist",
        "title": "C3 人力资源专员沙盘",
        "sample_origin": "demo_constructed",
        "for_training": False,
        "for_competition_demo": True,
        "target_role": "人力资源专员",
        "resume_summary": {
            "education": "财经类本科院校，人力资源或管理相关专业，应届生",
            "experience_level": "校园招聘协助 + 社团组织",
            "projects": [
                {
                    "name": "校园宣讲会志愿者协调",
                    "description": "协助签到、场地沟通、候选人通知和资料整理，负责现场流程跟进。",
                    "skills": ["候选人沟通", "Excel", "流程协调", "活动执行"],
                    "evidence_status": "direct",
                }
            ],
            "skills": ["沟通协调", "Excel", "招聘流程基础", "活动组织"],
        },
        "role_profile": {
            "core_abilities": ["招聘流程", "候选人沟通", "Excel 台账", "劳动法规基础", "执行细致度"],
            "role_requirements": [
                "了解招聘漏斗和候选人沟通节点",
                "能维护候选人台账并记录反馈",
                "具备基础劳动法规和入离职流程意识",
            ],
        },
        "evidence_items": [
            {
                "ability": "候选人沟通",
                "resume_evidence": "宣讲会项目中出现候选人通知和现场沟通",
                "evidence_status": "direct",
                "risk": "需要验证沟通话术和异常处理",
                "interview_focus": "候选人爽约、改期、反馈记录",
            },
            {
                "ability": "招聘流程",
                "resume_evidence": "出现招聘协助，但没有完整漏斗或流程指标",
                "evidence_status": "indirect",
                "risk": "可能只做执行事务，不熟悉完整流程",
                "interview_focus": "简历筛选、邀约、面试、offer、入职",
            },
            {
                "ability": "劳动法规基础",
                "resume_evidence": "简历未出现劳动合同、试用期或入离职手续",
                "evidence_status": "missing",
                "risk": "HR 基础知识缺口",
                "interview_focus": "试用期、合同、入离职材料、合规意识",
            },
        ],
    },
]


def _scan_direct_identifiers(value: Any) -> List[str]:
    return direct_identifier_hits(value)


def validate_no_direct_identifiers(case: Dict[str, Any]) -> None:
    hits = _scan_direct_identifiers(case)
    if hits:
        raise ValueError(f"demo case {case.get('case_id')} contains direct identifier pattern: {hits[0]}")


def generate_demo_cases() -> List[Dict[str, Any]]:
    cases = sort_demo_cases(deepcopy(DEMO_CASES))
    for case in cases:
        validate_demo_preview_asset(case, label=f"demo case {case.get('case_id')}")
    return cases


def build_demo_case_index() -> Dict[str, Dict[str, Any]]:
    return {case["case_id"]: case for case in generate_demo_cases()}
