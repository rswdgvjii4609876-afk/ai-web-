from __future__ import annotations

from typing import Any, Dict, List

from app.services.agent_orchestrator.evaluator import evaluate_trace
from app.services.agent_orchestrator.schemas import AgentStep, AgentTrace


def _top_gaps(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    for item in case.get("evidence_items", []):
        status = item.get("evidence_status", "")
        gap_level = "高" if status == "missing" else "中" if status == "claimed_only" else "低"
        gaps.append(
            {
                "ability": item["ability"],
                "required_level": "目标岗位核心能力",
                "evidence_status": status,
                "gap_level": gap_level,
                "diagnosis": item["risk"],
                "next_question_focus": item["interview_focus"],
            }
        )
    return gaps


def _build_resume_polish(case: Dict[str, Any], gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing = [gap["ability"] for gap in gaps if gap["evidence_status"] in {"missing", "claimed_only"}]
    return {
        "overall_strategy": "围绕目标岗位强化已证明经历；对仅声明或缺失能力，只给补证据建议，不写成已完成经历。",
        "section_suggestions": [
            {
                "section": "项目经历",
                "original_issue": "项目描述有技术或任务关键词，但缺少职责、动作和结果。",
                "polish_suggestion": "将真实经历改写为“负责模块 + 采取动作 + 协作对象 + 可验证结果”的表达。",
                "evidence_constraint": "只能使用简历已有项目和用户可证明事实，不新增公司、时间、技术栈或指标。",
                "missing_evidence_to_prepare": missing[:3],
            }
        ],
        "risk_warnings": [
            f"{ability} 证据不足，不能写成已经独立完成相关项目。"
            for ability in missing[:3]
        ],
    }


def _build_interview_question(case: Dict[str, Any], gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_gap = next((gap for gap in gaps if gap["evidence_status"] in {"missing", "claimed_only"}), gaps[0])
    ability = target_gap["ability"]
    return {
        "question": (
            f"你目标岗位需要{ability}能力，但简历证据状态是“{target_gap['evidence_status']}”。"
            "请结合一个真实项目说明：当时的场景是什么，你负责哪一部分，采取了什么行动，结果如何验证？"
            "如果没有实际经历，也请说明你准备如何补齐这个证据。"
        ),
        "target_ability": ability,
        "evidence_focus": target_gap["evidence_status"],
        "reason": target_gap["diagnosis"],
        "expected_answer_elements": ["具体场景", "个人职责", "行动方案", "结果或指标", "证据补齐计划"],
    }


def run_demo_pipeline(case: Dict[str, Any]) -> AgentTrace:
    evidence = case.get("evidence_items", [])
    role_profile = case.get("role_profile", {})
    gaps = _top_gaps(case)
    polish = _build_resume_polish(case, gaps)
    question = _build_interview_question(case, gaps)
    report = {
        "summary": f"{case['target_role']}演示样本已形成证据链、能力缺口、润色建议和追问目标。",
        "top_gaps": [gap["ability"] for gap in gaps if gap["gap_level"] in {"高", "中"}],
        "next_actions": ["补齐证据材料", "完成三轮模拟面试", "将授权样本交由后台人工评分"],
    }
    learning_tasks = [
        {
            "title": f"补齐{gap['ability']}证据",
            "practice": gap["next_question_focus"],
            "acceptance": "能用 STAR 结构讲清一次真实经历或明确补证据计划",
        }
        for gap in gaps[:2]
    ]
    data_governance = {
        "sample_origin": case.get("sample_origin", "demo_constructed"),
        "for_training": False,
        "for_competition_demo": True,
        "claim": "演示样本只用于比赛展示和链路验证，不作为真实训练样本。",
    }

    steps = [
        AgentStep(step=1, agent="ResumeEvidenceAgent", title="简历证据链", output={"evidence_items": evidence}),
        AgentStep(step=2, agent="RoleProfileAgent", title="岗位画像", output=role_profile),
        AgentStep(step=3, agent="GapAnalysisAgent", title="能力差距", output={"gaps": gaps}),
        AgentStep(
            step=4,
            agent="ResumePolishAgent",
            title="证据约束简历润色",
            output=polish,
            warnings=polish["risk_warnings"],
        ),
        AgentStep(step=5, agent="InterviewFollowupAgent", title="证据追问", output=question),
        AgentStep(step=6, agent="ReportAgent", title="报告摘要", output=report),
        AgentStep(step=7, agent="LearningTaskAgent", title="学习任务", output={"tasks": learning_tasks}),
        AgentStep(step=8, agent="DataGovernanceAgent", title="数据治理", output=data_governance),
    ]
    trace = AgentTrace(
        trace_id=f"{case['case_id']}.competition.trace",
        case_id=case["case_id"],
        target_role=case["target_role"],
        sample_origin=case.get("sample_origin", "demo_constructed"),
        for_training=False,
        for_competition_demo=True,
        steps=steps,
    )
    trace.eval_score = evaluate_trace(trace)
    trace.sft_preview_summary = {
        "dataset_type": "sft_preview",
        "created_for": "competition_demo",
        "ready_for_real_training": False,
        "counts": {
            "demo_constructed": 3,
            "real_authorized": 0,
            "train_preview_records": 6,
            "validation_preview_records": 0,
        },
        "preview_tasks": ["interview_followup", "evidence_bound_resume_polish"],
    }
    trace.steps.append(
        AgentStep(
            step=9,
            agent="EvalAgent",
            title="Eval Preview",
            output=trace.eval_score.model_dump(),
        )
    )
    trace.steps.append(
        AgentStep(
            step=10,
            agent="SFTPreviewAgent",
            title="SFT Preview 摘要",
            output=trace.sft_preview_summary,
        )
    )
    return trace
