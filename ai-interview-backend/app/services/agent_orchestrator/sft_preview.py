from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.agent_orchestrator.asset_guardrails import validate_demo_preview_asset
from app.services.agent_orchestrator.demo_pipeline import _build_resume_polish, _top_gaps
from app.services.agent_orchestrator.schemas import SFTPreviewRecord


DEVELOPER_PROMPT = (
    "你是职启智评 Career-AgentOS 的证据追问与简历润色 Agent。"
    "必须依据岗位画像、简历证据状态和能力缺口输出；不得编造候选人经历；"
    "当前记录是 preview/demo，不是真实训练样本。"
)


def _build_followup_record(case: Dict[str, Any]) -> SFTPreviewRecord:
    gaps = _top_gaps(case)
    missing = next((gap for gap in gaps if gap["evidence_status"] in {"missing", "claimed_only"}), gaps[0])
    assistant = {
        "question": (
            f"你目标岗位需要{missing['ability']}能力，但简历证据状态是{missing['evidence_status']}。"
            "请用一个真实场景说明个人职责、行动和结果；如果没有经历，请说明补证据计划。"
        ),
        "target_ability": missing["ability"],
        "evidence_focus": missing["evidence_status"],
    }
    return SFTPreviewRecord(
        record_id=f"{case['case_id']}_followup_preview",
        task_type="interview_followup_preview",
        messages=[
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "target_role": case["target_role"],
                        "resume_summary": case["resume_summary"],
                        "gaps": gaps,
                    },
                    ensure_ascii=False,
                ),
            },
            {"role": "assistant", "content": json.dumps(assistant, ensure_ascii=False)},
        ],
        metadata={"case_id": case["case_id"], "target_role": case["target_role"]},
    )


def _build_polish_record(case: Dict[str, Any]) -> SFTPreviewRecord:
    polish = _build_resume_polish(case, _top_gaps(case))
    return SFTPreviewRecord(
        record_id=f"{case['case_id']}_resume_polish_preview",
        task_type="evidence_bound_resume_polish_preview",
        messages=[
            {"role": "developer", "content": DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "instruction": "请基于岗位画像和证据状态，给出证据约束简历润色建议。",
                        "case": case,
                    },
                    ensure_ascii=False,
                ),
            },
            {"role": "assistant", "content": json.dumps(polish, ensure_ascii=False)},
        ],
        metadata={"case_id": case["case_id"], "target_role": case["target_role"]},
    )


def build_sft_preview_bundle(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    for case in cases:
        validate_demo_preview_asset(case, label=f"sft preview case {case.get('case_id')}")
    records: List[SFTPreviewRecord] = []
    for case in cases:
        records.append(_build_followup_record(case))
        records.append(_build_polish_record(case))
    train_records = records
    validation_records: List[SFTPreviewRecord] = []
    summary = {
        "dataset_type": "sft_preview",
        "created_for": "competition_demo",
        "ready_for_real_training": False,
        "counts": {
            "demo_constructed": len(cases),
            "real_authorized": 0,
            "train_preview_records": len(train_records),
            "validation_preview_records": len(validation_records),
        },
        "tasks": sorted({record.task_type for record in records}),
        "notes": [
            "当前为演示级 Preview，用于验证数据结构和链路。",
            "演示样本不得标记为真实授权训练样本。",
            "真实训练前需要替换或补充真实授权、人工复核样本。",
        ],
    }
    return {
        "train": [record.model_dump() for record in train_records],
        "validation": [record.model_dump() for record in validation_records],
        "summary": summary,
    }
