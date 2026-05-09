"""Seed public job profile knowledge bases for the competition demo.

Run from the backend container or backend working directory:
python -m app.scripts.seed_competition_knowledge_bases
"""

import asyncio

from sqlalchemy import select

from app.constants.competition import INTERVIEW_FOCUS_LIBRARY, POSITION_PROFILES
from app.db.session import async_session
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)


def _build_content(profile: dict) -> str:
    focus = INTERVIEW_FOCUS_LIBRARY.get(profile.get("job_id"), {})
    ability_lines = []
    for ability in profile.get("ability_model") or []:
        ability_lines.append(
            "- {name}：要求等级 {level}/5，权重 {weight}，关键词 {keywords}，证据线索 {hints}，可提升系数 {improvability}。".format(
                name=ability.get("name"),
                level=ability.get("required_level"),
                weight=ability.get("weight"),
                keywords="、".join(ability.get("keywords") or []),
                hints="、".join(ability.get("evidence_hints") or []),
                improvability=ability.get("improvability", 1.0),
            )
        )
    question_lines = [
        f"- 问题：{question}\n  参考回答要点：结合真实经历说明背景、个人动作、结果和复盘。\n  复盘提醒：没有简历证据时只作为追问方向，不直接判定已掌握。"
        for question in focus.get("sample_questions") or []
    ]
    company_focus_lines = [f"- {item}" for item in focus.get("company_focus") or []]
    followup_lines = [f"- {item}" for item in profile["evaluation_focus"]]
    lines = [
        "## 岗位要求",
        f"- 岗位名称：{profile['job_name']}",
        f"- 岗位类别：{profile.get('category', '通用岗位')}",
        f"- 硬性要求：{'、'.join(profile['core_skills'])}",
        f"- 典型任务：{'、'.join(profile['typical_tasks'])}",
        f"- 加分项/关键词：{'、'.join(profile['keywords'])}",
        f"- 面试八股/知识点：{'、'.join(profile.get('interview_topics') or [])}",
        "- 公司侧重点：",
        *(company_focus_lines or ["- 暂无明确公司侧重点，先按岗位通用能力追问。"]),
        "",
        "## 问答经验",
        *(question_lines or ["- 暂无真实问答经验，后续补充来源、问题、参考回答和复盘。"]),
        "",
        "## 能力模型",
        *(ability_lines or ["- 暂无能力模型，后续补充能力项、等级、权重和证据线索。"]),
        "",
        "## 面试追问",
        *followup_lines,
        "- 评分提示：先看岗位关键词覆盖和真实项目/实习证据，再结合回答质量判断，不因表达流畅而自动判定经历真实。",
        "- 证据追问：回答模糊时继续追问背景、个人贡献、数据结果、技术/业务取舍和复盘。",
    ]
    return "\n".join(lines)


async def seed() -> None:
    async with async_session() as db:
        created = 0
        updated = 0
        for profile in POSITION_PROFILES:
            title = f"职启智评岗位画像：{profile['job_name']}"
            result = await db.execute(
                select(PositionKnowledgeBase).where(
                    PositionKnowledgeBase.scope == "public",
                    PositionKnowledgeBase.title == title,
                )
            )
            item = result.scalar_one_or_none()
            payload = {
                "scope": "public",
                "title": title,
                "target_position": profile["job_name"],
                "knowledge_content": _build_content(profile),
                "focus_points": (
                    f"{profile.get('category', '通用岗位')}；"
                    f"重点核实：{'、'.join(profile['evaluation_focus'])}。"
                ),
                "interviewer_prompt": (
                    "保留多岗位真实面试风格；技术岗要覆盖基础知识、项目追问和线上排障，"
                    "非技术岗要覆盖场景任务、沟通协作和复盘数据。优先追问简历证据，"
                    "不编造经历，不替代真实招聘决策。"
                ),
                "is_active": True,
            }
            if item:
                for key, value in payload.items():
                    setattr(item, key, value)
                updated += 1
            else:
                item = PositionKnowledgeBase(user_id=None, admin_id=None, **payload)
                db.add(item)
                created += 1
            await db.flush()
            await db.refresh(item)
            await position_knowledge_base_slice_service.rebuild_for_knowledge_base(db, item)

        await db.commit()
        print(f"职启智评岗位画像已同步：新增 {created}，更新 {updated}")


if __name__ == "__main__":
    asyncio.run(seed())
