"""Run an offline core feature self-check for the current upgrade stage.

The script does not call external model APIs or write application data. It
uses synthetic cases and existing service helpers to verify that the main
resume-evaluation flow stays aligned across:

- resume evaluation snapshot
- resume polish fallback/result normalization
- learning plan task generation
- interview question routing and verification targets
- member knowledge package availability
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, List

from app.scripts.import_member_knowledge_packages import (
    DEFAULT_SOURCE,
    _package_paths,
    build_import_plans,
)
from app.services.client.ai_service import AIService
from app.services.client.interview_service import InterviewService
from app.services.client.learning_plan_service import LearningPlanService
from app.services.client.resume_evaluation_snapshot import ensure_resume_evaluation_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT
    / "docs"
    / "competition"
    / "core_feature_flow_reports"
    / "stage133_core_feature_flow_latest.md"
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    target_position: str
    ability_name: str
    evidence_status: str
    verification_keywords: List[str]
    project_evidence: str
    knowledge_title: str
    knowledge_content: str
    route_stage: str
    task_type: str


SYNTHETIC_CASES = [
    SyntheticCase(
        case_id="C1",
        target_position="Python后端开发工程师",
        ability_name="缓存与 Redis 应用",
        evidence_status="claimed_only",
        verification_keywords=["Redis", "缓存", "分布式锁"],
        project_evidence="简历只写熟悉 Redis，未提供缓存一致性、分布式锁或线上排障项目证据。",
        knowledge_title="职启智评岗位画像：Python后端开发工程师",
        knowledge_content="Redis cache consistency distributed lock troubleshooting RAG backend",
        route_stage="backend_cache_verification",
        task_type="demo_task",
    ),
    SyntheticCase(
        case_id="C2",
        target_position="产品助理/产品经理实习生",
        ability_name="需求分析与 PRD 输出",
        evidence_status="indirect",
        verification_keywords=["需求分析", "PRD", "指标复盘"],
        project_evidence="简历有活动策划和用户调研经历，但没有完整 PRD、需求优先级和指标复盘证据。",
        knowledge_title="职启智评岗位画像：产品助理",
        knowledge_content="PRD requirement analysis product metrics user scenario review",
        route_stage="product_requirement_analysis",
        task_type="case_analysis",
    ),
    SyntheticCase(
        case_id="C3",
        target_position="人力资源专员",
        ability_name="招聘漏斗与候选人沟通",
        evidence_status="missing",
        verification_keywords=["招聘漏斗", "候选人沟通", "渠道转化"],
        project_evidence="简历没有招聘漏斗、候选人沟通或渠道转化数据证据。",
        knowledge_title="职启智评岗位画像：人力资源专员",
        knowledge_content="HR recruitment funnel candidate communication conversion review",
        route_stage="hr_recruitment_funnel",
        task_type="scenario_practice",
    ),
]


def _run_check(name: str, fn: Callable[[], str]) -> CheckResult:
    try:
        detail = fn()
    except Exception as exc:  # pragma: no cover - final safety net for CLI use
        return CheckResult(name=name, status="FAIL", detail=f"{type(exc).__name__}: {exc}")
    return CheckResult(name=name, status="PASS", detail=detail)


def _ability_gap(case: SyntheticCase, rank: int = 1) -> dict[str, Any]:
    return {
        "ability_id": f"{case.case_id.lower()}_ability",
        "name": case.ability_name,
        "ability_name": case.ability_name,
        "evidence_status": case.evidence_status,
        "verification_priority": "high",
        "priority_score": 20 - rank,
        "gap": 2,
        "required_level": 4,
        "current_level": 2 if case.evidence_status != "missing" else 0,
        "weight": 0.25,
        "verification_keywords": case.verification_keywords,
        "evidence": case.project_evidence,
        "evidence_summary": case.project_evidence,
        "interview_probe_reason": f"{case.ability_name}需要通过面试验证：{case.project_evidence}",
        "learning_action": "先通过面试验证掌握程度，再决定是否进入系统学习任务。",
    }


def _synthetic_analysis(case: SyntheticCase) -> dict[str, Any]:
    ability_gap = _ability_gap(case)
    matching_metrics = {
        "final_score": 68,
        "overall_score": 68,
        "semantic_score": 72,
        "evidence_score": 60,
        "keyword_coverage": {
            "matched": [case.verification_keywords[0]],
            "missing": [case.ability_name],
            "direct_matches": [case.verification_keywords[0]]
            if case.evidence_status == "direct"
            else [],
            "related_matches": [case.verification_keywords[0]]
            if case.evidence_status == "indirect"
            else [],
            "verification_needed": [case.ability_name],
            "evidence_statuses": {
                case.ability_name: {
                    "status": case.evidence_status,
                    "keywords": case.verification_keywords,
                    "reason": case.project_evidence,
                }
            },
        },
        "ability_gap_profile": {
            "version": "ability_gap_v1",
            "target_position": case.target_position,
            "top_gaps": [ability_gap],
            "abilities": [ability_gap],
        },
    }
    analysis = {
        "target_position": case.target_position,
        "matching_metrics": matching_metrics,
        "ability_gap_profile": matching_metrics["ability_gap_profile"],
        "candidate_summary": {
            "strengths": ["有可迁移经历"],
            "risks": [case.project_evidence],
        },
        "parsed_resume": {
            "skills": case.verification_keywords,
            "projects": [{"title": "Synthetic project", "summary": case.project_evidence}],
        },
    }
    aligned = ensure_resume_evaluation_snapshot(analysis, target_position=case.target_position)
    return aligned


def _check_snapshot(case: SyntheticCase, analysis: dict[str, Any]) -> str:
    snapshot = analysis.get("resume_evaluation_snapshot") or {}
    targets = snapshot.get("verification_targets") or []
    if snapshot.get("version") != "resume_evaluation_v1":
        raise AssertionError("resume_evaluation_snapshot version is not resume_evaluation_v1")
    matched = [
        item
        for item in targets
        if item.get("ability_name") == case.ability_name
        and item.get("evidence_status") == case.evidence_status
    ]
    if not matched:
        raise AssertionError("verification target did not preserve ability name and evidence status")
    return f"{case.case_id} snapshot keeps {case.ability_name} as {case.evidence_status}"


def _check_polish(case: SyntheticCase, analysis: dict[str, Any]) -> str:
    polish = AIService._normalize_resume_polish_payload(
        payload={},
        target_position=case.target_position,
        analysis=analysis,
        polish_mode="job_aligned",
        knowledge_context={
            "sources": [
                {
                    "title": case.knowledge_title,
                    "target_position": case.target_position,
                    "source_section": "interview_experience",
                    "audit_status": "可入库",
                }
            ],
            "member_submission_used": False,
        },
    )
    source_titles = [item.get("title") for item in polish.get("knowledge_sources") or []]
    polished_text = str(polish.get("polished_resume_markdown") or "")
    warnings = " ".join(str(item) for item in polish.get("risk_warnings") or [])
    if case.knowledge_title not in source_titles:
        raise AssertionError("resume polish did not expose member knowledge source")
    if "已熟练掌握" in polished_text:
        raise AssertionError("resume polish fallback overclaims mastery")
    if case.evidence_status in {"claimed_only", "missing"} and "补充" not in polished_text:
        raise AssertionError("resume polish did not leave evidence补充 placeholder")
    if "岗位知识库" not in warnings:
        raise AssertionError("resume polish did not warn about knowledge-base grounding")
    return f"{case.case_id} polish uses {case.knowledge_title} and keeps evidence constraints"


def _route_record(case: SyntheticCase) -> dict[str, Any]:
    return {
        "id": 100 + int(case.case_id[-1]),
        "job_id": None,
        "job_name": case.target_position,
        "category": "synthetic",
        "route_source": "stage133_synthetic_template",
        "route_stage": case.route_stage,
        "title": f"{case.ability_name}学习路线",
        "material_type": "template",
        "task_type": case.task_type,
        "estimated_minutes": 90,
        "keywords": case.verification_keywords,
        "material": f"围绕{case.ability_name}整理岗位要求、基础概念、场景题和复盘材料。",
        "practice_task": f"完成一个{case.ability_name}相关的场景练习，并写出证据、步骤和结果。",
        "acceptance_criteria": "能说明真实场景、关键步骤、风险边界和复盘结论。",
        "route_kind": "template",
        "plan_group": "",
        "resource_requirement": "只补充轻量文本、链接或摘要，不上传大型文件。",
        "generation_prompt": f"基于{case.ability_name}缺口生成可执行学习任务，不编造用户经历。",
        "is_active": True,
        "sort_order": 1,
    }


def _check_learning_plan(case: SyntheticCase) -> str:
    plan = LearningPlanService._build_tasks_from_records(
        records=[_route_record(case)],
        abilities=[_ability_gap(case)],
        target_position=case.target_position,
    )
    tasks = plan.get("tasks") or []
    if plan.get("version") != "learning_plan_v2" or not tasks:
        raise AssertionError("learning plan did not generate v2 tasks")
    task = tasks[0]
    metadata = task.get("task_metadata") or {}
    if task.get("ability_name") != case.ability_name:
        raise AssertionError("learning task ability name diverged from evaluation snapshot")
    if metadata.get("source_evidence_status") != case.evidence_status:
        raise AssertionError("learning task lost evidence status")
    if not task.get("route_stage") or not task.get("estimated_minutes"):
        raise AssertionError("learning task lost route stage or estimated minutes")
    return f"{case.case_id} learning plan generated editable task for {case.ability_name}"


def _check_interview_routing(case: SyntheticCase, analysis: dict[str, Any]) -> str:
    question_plan = InterviewService._build_question_plan(total_questions=3, difficulty="medium")
    knowledge_base = {
        "slices": [
            {
                "slice_id": 1000 + int(case.case_id[-1]),
                "title": case.knowledge_title,
                "content": case.knowledge_content,
                "priority": 8,
                "stage_tags": ["technical", "project", "scenario"],
                "role_tags": ["technical_deep_dive", "business_interviewer"],
                "scene_tags": ["technical_depth", "scenario_probe"],
                "topic_tags": case.verification_keywords,
                "skill_tags": [keyword.lower() for keyword in case.verification_keywords],
                "keywords": case.verification_keywords,
                "source_section": "interview_experience",
                "difficulty": "medium",
                "is_enabled": True,
                "routing_score": 8.5,
                "routing_reasons": ["synthetic member knowledge match"],
                "routing_heads": {"skill_topic": 1.0, "source_quality": 0.9},
                "grounding_confidence": "high",
                "grounding_warnings": [],
            }
        ]
    }
    routed = InterviewService._route_question_plan(
        question_plan=question_plan,
        knowledge_base=knowledge_base,
        parsed_resume=analysis.get("parsed_resume") or {},
        target_position=case.target_position,
        difficulty="medium",
        matching_metrics=analysis.get("matching_metrics"),
    )
    first = routed[0]
    target = first.get("verification_target") or {}
    if target.get("ability_name") != case.ability_name:
        raise AssertionError("interview route did not bind verification_target ability")
    if target.get("evidence_status") != case.evidence_status:
        raise AssertionError("interview route did not preserve evidence status")
    if not first.get("selected_slices"):
        raise AssertionError("interview route did not keep selected knowledge slices")
    selected = first["selected_slices"][0]
    if selected.get("grounding_confidence") not in {"high", "medium", "low"}:
        raise AssertionError("selected slice did not expose grounding confidence")
    return f"{case.case_id} interview route carries verification_target and grounded slices"


def _check_member_packages() -> str:
    plans = build_import_plans(_package_paths(DEFAULT_SOURCE))
    targets = {plan.target_position for plan in plans}
    required_fragments = ["Python", "产品", "人力"]
    missing = [
        fragment
        for fragment in required_fragments
        if not any(fragment in target for target in targets)
    ]
    if missing:
        raise AssertionError(f"member knowledge packages missing representative targets: {missing}")
    total_experiences = sum(plan.enabled_experiences for plan in plans)
    if len(plans) < 7 or total_experiences < 20:
        raise AssertionError(
            f"member package coverage too low: positions={len(plans)}, experiences={total_experiences}"
        )
    return f"member packages cover {len(plans)} positions and {total_experiences} enabled interview experiences"


def _case_checks(case: SyntheticCase) -> Iterable[CheckResult]:
    analysis = _synthetic_analysis(case)
    yield _run_check(
        f"{case.case_id} resume_evaluation_snapshot",
        lambda: _check_snapshot(case, analysis),
    )
    yield _run_check(f"{case.case_id} resume_polish", lambda: _check_polish(case, analysis))
    yield _run_check(f"{case.case_id} learning_plan", lambda: _check_learning_plan(case))
    yield _run_check(
        f"{case.case_id} interview_routing",
        lambda: _check_interview_routing(case, analysis),
    )


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(_run_check("member_knowledge_packages", _check_member_packages))
    for case in SYNTHETIC_CASES:
        results.extend(_case_checks(case))
    return results


def overall_status(results: list[CheckResult]) -> str:
    if any(item.status == "FAIL" for item in results):
        return "FAIL"
    if any(item.status == "WARN" for item in results):
        return "WARN"
    return "PASS"


def first_failure(results: list[CheckResult]) -> str:
    for item in results:
        if item.status == "FAIL":
            return f"{item.name}: {item.detail}"
    return ""


def build_report(results: list[CheckResult]) -> str:
    status = overall_status(results)
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    lines = [
        "# 阶段 133 核心功能自动化自检报告",
        "",
        f"- 生成时间：{generated_at}",
        f"- 自动结论：{status}",
        "- 检查范围：成员知识库、统一评价快照、简历润色、学习计划、AI 面试验证目标。",
        "- 数据来源：合成样例 + 已整理成员知识库数据包；不调用外部大模型，不写入业务数据库。",
    ]
    failure = first_failure(results)
    if failure:
        lines.append(f"- 第一条失败：{failure}")
    lines.extend(
        [
            "",
            "## 检查结果",
            "",
            "| 检查项 | 状态 | 说明 |",
            "|---|---|---|",
        ]
    )
    for item in results:
        lines.append(f"| {item.name} | {item.status} | {item.detail} |")
    lines.extend(
        [
            "",
            "## 三岗位覆盖",
            "",
            "| 案例 | 岗位 | 重点能力 | 证据状态 | 用途 |",
            "|---|---|---|---|---|",
        ]
    )
    for case in SYNTHETIC_CASES:
        lines.append(
            "| "
            f"{case.case_id} | {case.target_position} | {case.ability_name} | "
            f"{case.evidence_status} | 诊断、润色、学习计划、面试验证目标一致性 |"
        )
    lines.extend(
        [
            "",
            "## 下一步处理口径",
            "",
            "- `PASS`：可进入阶段 132 的人工三岗位真实闭环跑测。",
            "- `WARN`：允许继续人工跑测，但需记录警告项。",
            "- `FAIL`：只修复第一条失败原因，不继续新增页面、接口或数据库表绕过问题。",
            "- 本报告不能替代真实简历验收，只用于减少人工跑测前的基础链路错误。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(report: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stage 133 core feature self-check.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_REPORT_PATH),
        help="Markdown report path. Defaults to docs/competition/core_feature_flow_reports/.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the report without writing it to disk.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results = run_checks()
    report = build_report(results)
    if args.print_only:
        print(report)
    else:
        output_path = Path(args.output)
        write_report(report, output_path)
        print(f"report={output_path}")
    status = overall_status(results)
    print(f"result={status}")
    failure = first_failure(results)
    if failure:
        print(f"first_failure={failure}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
