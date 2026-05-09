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
    lines = [
        f"岗位名称：{profile['job_name']}",
        f"岗位类别：{profile.get('category', '通用岗位')}",
        f"核心能力：{'、'.join(profile['core_skills'])}",
        f"典型任务：{'、'.join(profile['typical_tasks'])}",
        f"关键词：{'、'.join(profile['keywords'])}",
        f"面试八股/知识点：{'、'.join(profile.get('interview_topics') or [])}",
        f"企业常见考察方向：{'；'.join(focus.get('company_focus') or [])}",
        f"样例面试题：{'；'.join(focus.get('sample_questions') or [])}",
        f"面试考察重点：{'、'.join(profile['evaluation_focus'])}",
        "评分提示：先看岗位关键词覆盖和真实项目/实习证据，再结合回答质量判断，不因表达流畅而自动判定经历真实。",
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
