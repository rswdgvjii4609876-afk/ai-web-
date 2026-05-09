import logging
import re
from typing import Dict, List, Optional, Sequence, Set

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_knowledge_base import PositionKnowledgeBase
from app.models.position_knowledge_base_slice import PositionKnowledgeBaseSlice


logger = logging.getLogger(__name__)


ROLE_KEYWORDS = {
    "technical_deep_dive": [
        "python", "fastapi", "sqlalchemy", "redis", "postgres", "docker",
        "\u7b97\u6cd5", "\u6570\u636e\u7ed3\u6784", "\u5e76\u53d1", "\u5f02\u6b65",
        "\u7f13\u5b58", "\u6570\u636e\u5e93", "\u7d22\u5f15", "\u4e8b\u52a1",
        "\u6d88\u606f\u961f\u5217", "\u5fae\u670d\u52a1", "\u7f51\u7edc", "\u64cd\u4f5c\u7cfb\u7edf",
    ],
    "project_follow_up": [
        "\u9879\u76ee", "\u9879\u76ee\u7ecf\u5386", "\u67b6\u6784", "\u6a21\u5757",
        "\u65b9\u6848", "\u5b9e\u73b0", "\u4f18\u5316", "\u6392\u67e5", "\u590d\u76d8",
        "\u4e0a\u7ebf", "\u90e8\u7f72", "\u91cd\u6784", "\u6280\u672f\u9009\u578b",
    ],
    "business_scenario": [
        "\u4e1a\u52a1", "\u573a\u666f", "\u6d41\u7a0b", "\u7528\u6237", "\u9700\u6c42",
        "\u6307\u6807", "\u8f6c\u5316", "\u589e\u957f", "\u98ce\u63a7", "\u6cbb\u7406",
        "\u7a33\u5b9a\u6027", "\u53ef\u7528\u6027", "\u5bb9\u707e",
    ],
    "behavior_expression": [
        "\u6c9f\u901a", "\u534f\u4f5c", "\u63a8\u52a8", "\u590d\u76d8", "\u603b\u7ed3",
        "\u8868\u8fbe", "\u51b2\u7a81", "\u9886\u5bfc\u529b", "\u81ea\u6211\u4ecb\u7ecd",
        "\u6210\u957f", "\u5b66\u4e60",
    ],
    "pressure_challenge": [
        "\u96be\u70b9", "\u6311\u6218", "\u6545\u969c", "\u9ad8\u5e76\u53d1",
        "\u538b\u6d4b", "\u7ebf\u4e0a", "\u74f6\u9888", "\u515c\u5e95", "\u98ce\u9669",
        "\u53d6\u820d", "\u6781\u9650", "\u8d85\u65f6", "\u5931\u8d25",
    ],
}

STAGE_HINTS = {
    "opening": [
        "\u81ea\u6211\u4ecb\u7ecd", "\u80cc\u666f", "\u7ecf\u5386", "\u4eae\u70b9", "\u5b66\u4e60\u8def\u5f84",
    ],
    "project": [
        "\u9879\u76ee", "\u67b6\u6784", "\u6a21\u5757", "\u65b9\u6848", "\u5b9e\u73b0",
        "\u4f18\u5316", "\u6392\u67e5", "\u4e0a\u7ebf",
    ],
    "technical": [
        "python", "java", "\u7b97\u6cd5", "\u6570\u636e\u7ed3\u6784", "\u6570\u636e\u5e93",
        "\u7f13\u5b58", "\u5f02\u6b65", "\u7f51\u7edc",
    ],
    "scenario": [
        "\u573a\u666f", "\u4e1a\u52a1", "\u8bbe\u8ba1", "\u9ad8\u5e76\u53d1", "\u6027\u80fd",
        "\u6269\u5c55", "\u7a33\u5b9a\u6027", "\u5bb9\u707e",
    ],
    "behavior": [
        "\u534f\u4f5c", "\u6c9f\u901a", "\u51b2\u7a81", "\u590d\u76d8", "\u9886\u5bfc\u529b",
        "\u6210\u957f", "\u6297\u538b",
    ],
    "closing": [
        "\u603b\u7ed3", "\u89c4\u5212", "\u8865\u5145", "\u5efa\u8bae", "\u671f\u671b", "\u53cd\u95ee",
    ],
}

COMMON_SKILLS = {
    "python", "java", "golang", "javascript", "typescript", "vue", "react", "vite",
    "fastapi", "django", "flask", "spring", "mysql", "postgresql", "postgres",
    "redis", "docker", "kubernetes", "linux", "nginx", "sql", "sqlalchemy", "celery",
    "\u6d88\u606f\u961f\u5217", "\u5fae\u670d\u52a1", "\u9ad8\u5e76\u53d1",
    "\u7cfb\u7edf\u8bbe\u8ba1", "\u6570\u636e\u7ed3\u6784", "\u7b97\u6cd5", "\u7f13\u5b58", "\u6d4b\u8bd5",
}

HARD_HINTS = [
    "\u9ad8\u5e76\u53d1", "\u5206\u5e03\u5f0f", "\u7cfb\u7edf\u8bbe\u8ba1",
    "\u67b6\u6784", "\u538b\u6d4b", "\u7a33\u5b9a\u6027",
]

MEDIUM_HINTS = [
    "\u9879\u76ee", "\u4f18\u5316", "\u6392\u67e5", "\u7f13\u5b58", "\u6570\u636e\u5e93", "\u5f02\u6b65",
]

PRIORITY_HINTS = ["\u91cd\u70b9", "\u5fc5\u987b", "\u4f18\u5148", "\u6838\u5fc3"]

SCENE_KEYWORDS = {
    "self_intro": ["\u81ea\u6211\u4ecb\u7ecd", "\u80cc\u666f", "\u7ecf\u5386", "\u4eae\u70b9"],
    "project_delivery": [
        "\u9879\u76ee", "\u4ea4\u4ed8", "\u4e0a\u7ebf", "\u67b6\u6784", "\u6a21\u5757", "\u4f18\u5316", "\u6392\u67e5",
    ],
    "technical_depth": [
        "\u6280\u672f", "\u5f02\u6b65", "\u6570\u636e\u5e93", "\u7f13\u5b58", "\u5fae\u670d\u52a1", "\u7cfb\u7edf\u8bbe\u8ba1",
    ],
    "business_case": [
        "\u573a\u666f", "\u4e1a\u52a1", "\u7528\u6237", "\u8f6c\u5316", "\u6307\u6807", "\u98ce\u63a7", "\u6cbb\u7406",
    ],
    "pressure_case": [
        "\u6311\u6218", "\u6545\u969c", "\u9ad8\u5e76\u53d1", "\u538b\u6d4b", "\u74f6\u9888", "\u98ce\u9669", "\u53d6\u820d",
    ],
    "behavior_case": [
        "\u534f\u4f5c", "\u6c9f\u901a", "\u51b2\u7a81", "\u9886\u5bfc\u529b", "\u6210\u957f", "\u590d\u76d8",
    ],
}


class PositionKnowledgeBaseSliceService:
    @staticmethod
    def _clean_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return re.sub(r"\n{3,}", "\n\n", value.strip())

    @staticmethod
    def _split_lines(text: str) -> List[str]:
        if not text:
            return []
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0
        for raw_line in re.split(r"\n+", text):
            line = raw_line.strip(" -\t\r")
            if not line:
                continue
            if current_len and current_len + len(line) > 260:
                chunks.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line)
        if current:
            chunks.append("\n".join(current))
        return chunks

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff+#.-]+", " ", (text or "").lower())
        return {token for token in normalized.split() if len(token) >= 2}

    @staticmethod
    def _normalize_terms(values: Optional[Sequence[str]]) -> Set[str]:
        terms: Set[str] = set()
        for value in values or []:
            if not value:
                continue
            cleaned = value.strip().lower()
            if cleaned:
                terms.add(cleaned)
        return terms

    @staticmethod
    def _infer_roles(text: str) -> List[str]:
        lowered = (text or "").lower()
        roles = [
            role
            for role, keywords in ROLE_KEYWORDS.items()
            if any(keyword.lower() in lowered for keyword in keywords)
        ]
        return roles or ["project_follow_up", "technical_deep_dive"]

    @staticmethod
    def _infer_stages(text: str, source_section: str) -> List[str]:
        lowered = (text or "").lower()
        stages = [
            stage
            for stage, keywords in STAGE_HINTS.items()
            if any(keyword.lower() in lowered for keyword in keywords)
        ]
        if stages:
            return stages
        if source_section == "focus_points":
            return ["technical", "scenario"]
        if source_section == "interviewer_prompt":
            return ["behavior", "closing"]
        return ["project", "technical"]

    @staticmethod
    def _infer_skill_tags(text: str, target_position: str) -> List[str]:
        lowered = f"{text or ''} {target_position or ''}".lower()
        hits = [skill for skill in COMMON_SKILLS if skill.lower() in lowered]
        return sorted(hits)[:12]

    @staticmethod
    def _infer_scene_tags(text: str, source_section: str) -> List[str]:
        lowered = (text or "").lower()
        scenes = [
            scene
            for scene, keywords in SCENE_KEYWORDS.items()
            if any(keyword.lower() in lowered for keyword in keywords)
        ]
        if scenes:
            return scenes[:4]
        default_scene = {
            "overview": "self_intro",
            "knowledge_content": "project_delivery",
            "focus_points": "technical_depth",
            "interviewer_prompt": "behavior_case",
        }.get(source_section, "project_delivery")
        return [default_scene]

    @staticmethod
    def _infer_difficulty(text: str, source_section: str) -> str:
        lowered = (text or "").lower()
        if any(keyword.lower() in lowered for keyword in HARD_HINTS):
            return "hard"
        if any(keyword.lower() in lowered for keyword in MEDIUM_HINTS):
            return "medium"
        if source_section == "overview":
            return "general"
        return "easy"

    @staticmethod
    def _infer_priority(source_section: str, text: str) -> int:
        priority = {
            "overview": 8,
            "focus_points": 10,
            "interviewer_prompt": 9,
            "knowledge_content": 7,
        }.get(source_section, 6)
        lowered = (text or "").lower()
        if any(keyword.lower() in lowered for keyword in PRIORITY_HINTS):
            priority += 1
        return min(priority, 10)

    @staticmethod
    def _build_slice_payload(
        knowledge_base: PositionKnowledgeBase,
        content: str,
        source_section: str,
        sort_order: int,
        title: Optional[str] = None,
        topic_tags: Optional[Sequence[str]] = None,
    ) -> Dict:
        cleaned = PositionKnowledgeBaseSliceService._clean_text(content)
        keywords = sorted(PositionKnowledgeBaseSliceService._tokenize(cleaned))[:20]
        skill_tags = PositionKnowledgeBaseSliceService._infer_skill_tags(cleaned, knowledge_base.target_position)
        stage_tags = PositionKnowledgeBaseSliceService._infer_stages(cleaned, source_section)
        role_tags = PositionKnowledgeBaseSliceService._infer_roles(cleaned)
        difficulty = PositionKnowledgeBaseSliceService._infer_difficulty(cleaned, source_section)
        scene_tags = PositionKnowledgeBaseSliceService._infer_scene_tags(cleaned, source_section)
        derived_topics = list(topic_tags or [])
        if not derived_topics:
            derived_topics = sorted({*skill_tags[:4], *keywords[:4]})[:6]

        return {
            "knowledge_base_id": knowledge_base.id,
            "title": title or knowledge_base.title,
            "content": cleaned,
            "slice_type": "prompt" if source_section == "interviewer_prompt" else "knowledge",
            "source_section": source_section,
            "source_scope": knowledge_base.scope or "private",
            "difficulty": difficulty,
            "priority": PositionKnowledgeBaseSliceService._infer_priority(source_section, cleaned),
            "sort_order": sort_order,
            "stage_tags": stage_tags,
            "role_tags": role_tags,
            "topic_tags": derived_topics,
            "skill_tags": skill_tags,
            "scene_tags": scene_tags,
            "keywords": keywords,
            "is_enabled": True,
        }

    @staticmethod
    def build_slice_payloads(knowledge_base: PositionKnowledgeBase) -> List[Dict]:
        payloads: List[Dict] = []
        sort_order = 0
        scope_label = (
            "\u540e\u53f0\u516c\u5171\u77e5\u8bc6\u5e93"
            if (knowledge_base.scope or "private") == "public"
            else "\u7528\u6237\u79c1\u6709\u77e5\u8bc6\u5e93"
        )
        overview = "\n".join([
            f"\u5c97\u4f4d\uff1a{knowledge_base.target_position}",
            f"\u77e5\u8bc6\u5e93\u6807\u9898\uff1a{knowledge_base.title}",
            f"\u6765\u6e90\u8303\u56f4\uff1a{scope_label}",
        ])
        payloads.append(
            PositionKnowledgeBaseSliceService._build_slice_payload(
                knowledge_base=knowledge_base,
                content=overview,
                source_section="overview",
                sort_order=sort_order,
                title=f"{knowledge_base.title} - \u5c97\u4f4d\u6982\u89c8",
                topic_tags=[knowledge_base.target_position],
            )
        )
        sort_order += 1

        for block in PositionKnowledgeBaseSliceService._split_lines(knowledge_base.knowledge_content):
            payloads.append(
                PositionKnowledgeBaseSliceService._build_slice_payload(
                    knowledge_base=knowledge_base,
                    content=block,
                    source_section="knowledge_content",
                    sort_order=sort_order,
                )
            )
            sort_order += 1

        for focus in PositionKnowledgeBaseSliceService._split_lines(knowledge_base.focus_points or ""):
            payloads.append(
                PositionKnowledgeBaseSliceService._build_slice_payload(
                    knowledge_base=knowledge_base,
                    content=focus,
                    source_section="focus_points",
                    sort_order=sort_order,
                    title=f"{knowledge_base.title} - \u8bad\u7ec3\u91cd\u70b9",
                )
            )
            sort_order += 1

        for prompt in PositionKnowledgeBaseSliceService._split_lines(knowledge_base.interviewer_prompt or ""):
            payloads.append(
                PositionKnowledgeBaseSliceService._build_slice_payload(
                    knowledge_base=knowledge_base,
                    content=prompt,
                    source_section="interviewer_prompt",
                    sort_order=sort_order,
                    title=f"{knowledge_base.title} - \u9762\u8bd5\u5b98\u8981\u6c42",
                )
            )
            sort_order += 1

        return [payload for payload in payloads if payload["content"]]

    @staticmethod
    def serialize(item: PositionKnowledgeBaseSlice) -> Dict:
        return {
            "slice_id": item.id,
            "knowledge_base_id": item.knowledge_base_id,
            "title": item.title,
            "content": item.content,
            "slice_type": item.slice_type,
            "source_section": item.source_section,
            "source_scope": item.source_scope,
            "difficulty": item.difficulty,
            "priority": item.priority,
            "sort_order": item.sort_order,
            "stage_tags": item.stage_tags or [],
            "role_tags": item.role_tags or [],
            "topic_tags": item.topic_tags or [],
            "skill_tags": item.skill_tags or [],
            "scene_tags": item.scene_tags or [],
            "keywords": item.keywords or [],
            "is_enabled": item.is_enabled,
        }

    @staticmethod
    def _format_reason(prefix: str, values: Sequence[str], limit: int = 3) -> Optional[str]:
        cleaned = [str(item).strip() for item in values or [] if str(item).strip()]
        if not cleaned:
            return None
        return f"{prefix}：{' / '.join(cleaned[:limit])}"

    @staticmethod
    async def rebuild_for_knowledge_base(db: AsyncSession, knowledge_base: PositionKnowledgeBase) -> List[Dict]:
        payloads = PositionKnowledgeBaseSliceService.build_slice_payloads(knowledge_base)
        await db.execute(
            delete(PositionKnowledgeBaseSlice).where(
                PositionKnowledgeBaseSlice.knowledge_base_id == knowledge_base.id
            )
        )
        if not payloads:
            return []
        slices = [PositionKnowledgeBaseSlice(**payload) for payload in payloads]
        db.add_all(slices)
        await db.flush()
        return [PositionKnowledgeBaseSliceService.serialize(item) for item in slices]

    @staticmethod
    async def list_for_knowledge_base(db: AsyncSession, knowledge_base_id: int) -> List[Dict]:
        result = await db.execute(
            select(PositionKnowledgeBaseSlice)
            .where(
                PositionKnowledgeBaseSlice.knowledge_base_id == knowledge_base_id,
                PositionKnowledgeBaseSlice.is_enabled.is_(True),
            )
            .order_by(
                PositionKnowledgeBaseSlice.priority.desc(),
                PositionKnowledgeBaseSlice.sort_order.asc(),
                PositionKnowledgeBaseSlice.id.asc(),
            )
        )
        items = result.scalars().all()
        return [PositionKnowledgeBaseSliceService.serialize(item) for item in items]

    @staticmethod
    def rank_slices(
        slices: Sequence[Dict],
        query_text: str = "",
        stage: Optional[str] = None,
        role: Optional[str] = None,
        scene: Optional[str] = None,
        difficulty: Optional[str] = None,
        skills: Optional[Sequence[str]] = None,
        topics: Optional[Sequence[str]] = None,
        weakness_terms: Optional[Sequence[str]] = None,
        top_k: int = 4,
    ) -> List[Dict]:
        if not slices:
            return []

        query_tokens = PositionKnowledgeBaseSliceService._tokenize(query_text)
        skill_terms = PositionKnowledgeBaseSliceService._normalize_terms(skills)
        topic_terms = PositionKnowledgeBaseSliceService._normalize_terms(topics)
        weakness_tokens = PositionKnowledgeBaseSliceService._normalize_terms(weakness_terms)
        ranked = []
        for item in slices:
            if not item.get("is_enabled", True):
                continue
            score = float(item.get("priority") or 0)
            reasons: List[str] = []
            stage_tags = item.get("stage_tags") or []
            role_tags = item.get("role_tags") or []
            scene_tags = item.get("scene_tags") or []
            slice_difficulty = item.get("difficulty") or "general"
            searchable = " ".join(
                [
                    item.get("content") or "",
                    " ".join(item.get("topic_tags") or []),
                    " ".join(item.get("skill_tags") or []),
                    " ".join(item.get("scene_tags") or []),
                    " ".join(item.get("keywords") or []),
                ]
            )
            overlap = len(query_tokens & PositionKnowledgeBaseSliceService._tokenize(searchable))
            score += min(overlap, 6) * 1.2
            if overlap:
                reasons.append(f"命中内容关键词 {min(overlap, 6)} 项")
            if stage and stage in stage_tags:
                score += 4
                reasons.append(f"匹配阶段：{stage}")
            if role and role in role_tags:
                score += 3
                reasons.append(f"匹配角色：{role}")
            if scene and scene in scene_tags:
                score += 2.5
                reasons.append(f"匹配场景：{scene}")
            if difficulty:
                if slice_difficulty == difficulty:
                    score += 2
                    reasons.append(f"匹配难度：{difficulty}")
                elif slice_difficulty == "general":
                    score += 1
            matched_skill_terms = sorted(
                skill_terms & PositionKnowledgeBaseSliceService._normalize_terms(item.get("skill_tags"))
            )
            if matched_skill_terms:
                score += min(len(matched_skill_terms), 4) * 1.5
                reason = PositionKnowledgeBaseSliceService._format_reason("命中技能", matched_skill_terms)
                if reason:
                    reasons.append(reason)
            matched_topic_terms = sorted(
                topic_terms & PositionKnowledgeBaseSliceService._normalize_terms(item.get("topic_tags"))
            )
            if matched_topic_terms:
                score += min(len(matched_topic_terms), 4) * 1.2
                reason = PositionKnowledgeBaseSliceService._format_reason("命中主题", matched_topic_terms)
                if reason:
                    reasons.append(reason)
            matched_weakness_terms = sorted(
                weakness_tokens & PositionKnowledgeBaseSliceService._normalize_terms(item.get("keywords"))
            )
            if matched_weakness_terms:
                score += min(len(matched_weakness_terms), 4) * 1.4
                reason = PositionKnowledgeBaseSliceService._format_reason("命中薄弱点", matched_weakness_terms)
                if reason:
                    reasons.append(reason)
            if item.get("source_section") == "focus_points":
                score += 1.5
                reasons.append("来自重点训练项")
            enriched_item = {
                **item,
                "routing_score": round(score, 2),
                "routing_reasons": reasons[:6],
            }
            ranked.append((score, enriched_item))

        ranked.sort(
            key=lambda pair: (
                pair[0],
                pair[1].get("priority") or 0,
                -(pair[1].get("sort_order") or 0),
            ),
            reverse=True,
        )
        return [item for _, item in ranked[:top_k]]


position_knowledge_base_slice_service = PositionKnowledgeBaseSliceService()
