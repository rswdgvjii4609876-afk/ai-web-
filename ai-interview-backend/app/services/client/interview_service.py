from collections import Counter
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import logging
import re
import zipfile
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete as sql_delete
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.privacy import DATA_CONTRIBUTION_CONSENT_VERSION
from app.exceptions.http_exceptions import NotFoundError, ValidationError
from app.models.interview import Interview
from app.models.interview_message import InterviewMessage
from app.models.position_knowledge_base import PositionKnowledgeBase
from app.models.resume import Resume
from app.models.user import User
from app.services.client.ai_service import AIService
from app.services.client.position_knowledge_base_slice_service import (
    position_knowledge_base_slice_service,
)
from app.services.client.resume_evaluation_snapshot import (
    ensure_resume_evaluation_snapshot,
    matching_metrics_from_payload,
)
from app.services.client.resume_normalizer import normalize_parsed_resume
from app.services.client.privacy_consent_service import privacy_consent_service

logger = logging.getLogger(__name__)

TRAINING_SAMPLE_QUALITY_TIERS = {"needs_review", "low", "medium", "high"}
TRAINING_SAMPLE_DATASET_SPLITS = {"", "train", "validation", "test", "holdout", "demo"}
EVALUATION_DATASET_SCHEMA_VERSION = "ai-interview.evaluation-dataset.v1"
FINE_TUNING_SAMPLE_SCHEMA_VERSION = "ai-interview.fine-tuning-sample.v1"
FINE_TUNING_READINESS_REPORT_VERSION = "ai-interview.fine-tuning-readiness-report.v1"
USER_DELETED_COMPLETED_INTERVIEW_REASON = "user_deleted_completed_interview_retained_for_review"
START_PANEL_QUESTION_TIMEOUT_SECONDS = 25
ANSWER_EVALUATION_TIMEOUT_SECONDS = 45
ANSWER_REPORT_TIMEOUT_SECONDS = 45
ANSWER_STREAM_TOTAL_TIMEOUT_SECONDS = 140
ANSWER_STREAM_HEARTBEAT_SECONDS = 8
DIRECT_IDENTIFIER_REPLACEMENTS = (
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[REDACTED_ID]"),
    (
        re.compile(
            r"(姓名|手机号|手机|电话|邮箱|电子邮箱|学号|证件号|身份证|详细住址|家庭住址|住址|文件名|name|phone|email|id|student_id|student id)\s*[:：=]\s*[^,，;；\n]{2,}",
            re.IGNORECASE,
        ),
        r"\1：[REDACTED]",
    ),
    (re.compile(r"[\w\u4e00-\u9fff-]{2,}\.(?:pdf|doc|docx)", re.IGNORECASE), "[REDACTED_FILE]"),
    (re.compile(r"\d{6,}[\u4e00-\u9fff]{2,6}[^,，;；\n\s]{0,12}"), "[REDACTED_IDENTIFIER]"),
)
EVALUATION_DATASET_DEFINITIONS = (
    {
        "dataset_type": "golden_cases",
        "filename": "golden_cases.jsonl",
        "label": "黄金样本集",
        "description": "高质量、无幻觉且高分的稳定训练样本。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.is_high_quality=true",
            "training_sample_review.has_hallucination=false",
            "overall_score>=7.5",
        ],
    },
    {
        "dataset_type": "hallucination_cases",
        "filename": "hallucination_cases.jsonl",
        "label": "幻觉问题集",
        "description": "人工判定存在幻觉或无依据强答的案例。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.has_hallucination=true",
        ],
    },
    {
        "dataset_type": "followup_quality_cases",
        "filename": "followup_quality_cases.jsonl",
        "label": "追问质量集",
        "description": "追问值得保留，且本轮存在可复用的 evidence-driven follow-up 信号。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.followup_worthy=true",
            "training_sample_review.has_hallucination=false",
            "overall_score>=6.0",
            "followup_signal_present=true",
        ],
    },
    {
        "dataset_type": "report_quality_cases",
        "filename": "report_quality_cases.jsonl",
        "label": "报告质量集",
        "description": "报告建议具有可执行性，且报告聚合信号完整。",
        "rules": [
            "status=completed",
            "training_sample_review.review_status=reviewed",
            "training_sample_review.report_actionable=true",
            "training_sample_review.has_hallucination=false",
            "overall_score>=6.0",
            "report_signal_present=true",
        ],
    },
)

START_INTERVIEW_DB_ERROR_MESSAGE = (
    "开始面试失败：数据库写入异常，可能是服务器数据库迁移未完成。"
    "请管理员执行 alembic upgrade head，并查看后端日志中的第一条数据库异常。"
)


PANEL_ROLE_SPECS = [
    {
        "key": "technical_deep_dive",
        "name": "Technical Deep Dive",
        "focus": "Probe core principles, technical trade-offs, and hard engineering details.",
    },
    {
        "key": "project_follow_up",
        "name": "Project Follow-up",
        "focus": "Verify ownership, real contribution, trade-offs, and project retrospection.",
    },
    {
        "key": "business_scenario",
        "name": "Business Scenario",
        "focus": "Test whether technical thinking can be grounded in realistic business context.",
    },
    {
        "key": "behavior_expression",
        "name": "Behavior & Communication",
        "focus": "Observe structure, collaboration, growth mindset, and communication quality.",
    },
    {
        "key": "pressure_challenge",
        "name": "Pressure Challenge",
        "focus": "Test boundary handling, risk awareness, pressure response, and decision trade-offs.",
    },
]

QUESTION_TEMPLATES = {
    "opening_intro": {
        "stage": "opening",
        "category": "self-intro",
        "lead_role": "behavior_expression",
        "support_roles": ["project_follow_up"],
        "intent": "Use the self-introduction to quickly assess background fit, clarity, and motivation.",
        "evaluation_focus": ["structured expression", "role motivation", "background highlights"],
    },
    "project_core": {
        "stage": "project",
        "category": "project",
        "lead_role": "project_follow_up",
        "support_roles": ["technical_deep_dive"],
        "intent": "Deep-dive the most important project to verify ownership, trade-offs, and retrospection quality.",
        "evaluation_focus": ["ownership", "solution trade-offs", "project retrospection"],
    },
    "technical_core": {
        "stage": "technical",
        "category": "technical",
        "lead_role": "technical_deep_dive",
        "support_roles": ["project_follow_up"],
        "intent": "Validate mastery of core knowledge and depth of understanding.",
        "evaluation_focus": ["core principles", "accuracy", "technical depth"],
    },
    "business_scenario": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "business_scenario",
        "support_roles": ["technical_deep_dive"],
        "intent": "Place the candidate in a realistic business scenario to test execution quality.",
        "evaluation_focus": ["business understanding", "solution landing", "stability awareness"],
    },
    "behavior_growth": {
        "stage": "behavior",
        "category": "behavior",
        "lead_role": "behavior_expression",
        "support_roles": ["project_follow_up"],
        "intent": "Evaluate collaboration, communication, reflection, and growth potential.",
        "evaluation_focus": ["communication", "collaboration reflection", "growth potential"],
    },
    "pressure_tradeoff": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "pressure_challenge",
        "support_roles": ["technical_deep_dive", "business_scenario"],
        "intent": "Assess boundary awareness and trade-offs under pressure.",
        "evaluation_focus": ["risk trade-offs", "stability", "pressure response"],
    },
    "technical_debug": {
        "stage": "technical",
        "category": "technical",
        "lead_role": "technical_deep_dive",
        "support_roles": ["pressure_challenge"],
        "intent": "Use debugging or optimization questions to verify diagnosis and engineering experience.",
        "evaluation_focus": ["debugging approach", "engineering experience", "optimization ability"],
    },
    "basic_knowledge": {
        "stage": "technical",
        "category": "technical",
        "lead_role": "technical_deep_dive",
        "support_roles": ["project_follow_up"],
        "intent": "Check basic role knowledge, common framework usage, and daily execution readiness.",
        "evaluation_focus": ["basic knowledge", "framework usage", "execution readiness"],
    },
    "system_design_depth": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "pressure_challenge",
        "support_roles": ["technical_deep_dive", "business_scenario"],
        "intent": "Probe scalable system design, concurrency, reliability, performance, and trade-offs.",
        "evaluation_focus": ["system design", "concurrency", "reliability", "trade-offs"],
    },
    "rag_optimization": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "technical_deep_dive",
        "support_roles": ["pressure_challenge", "business_scenario"],
        "intent": "Probe RAG or LLM engineering optimization only when the role or evidence is relevant.",
        "evaluation_focus": ["RAG retrieval quality", "reranking", "groundedness", "evaluation"],
    },
    "project_ownership": {
        "stage": "project",
        "category": "project",
        "lead_role": "project_follow_up",
        "support_roles": ["behavior_expression"],
        "intent": "Further verify role boundaries, leadership level, and delivery outcomes in projects.",
        "evaluation_focus": ["role boundary", "result orientation", "retrospective quality"],
    },
    "scenario_tradeoff": {
        "stage": "scenario",
        "category": "system-design",
        "lead_role": "business_scenario",
        "support_roles": ["pressure_challenge"],
        "intent": "Use business changes and resource limits to validate solution trade-offs.",
        "evaluation_focus": ["scenario fit", "priority judgment", "resource trade-offs"],
    },
    "closing_reflection": {
        "stage": "closing",
        "category": "behavior",
        "lead_role": "behavior_expression",
        "support_roles": ["pressure_challenge"],
        "intent": "Close the interview by checking self-awareness and most urgent training priorities.",
        "evaluation_focus": ["self-awareness", "summary ability", "training direction"],
    },
}

QUESTION_ORDERS = {
    "easy": [
        "opening_intro",
        "basic_knowledge",
        "project_core",
        "technical_debug",
        "behavior_growth",
        "project_ownership",
        "technical_core",
        "business_scenario",
        "closing_reflection",
        "closing_reflection",
    ],
    "medium": [
        "opening_intro",
        "project_core",
        "technical_core",
        "business_scenario",
        "behavior_growth",
        "pressure_tradeoff",
        "technical_debug",
        "project_ownership",
        "scenario_tradeoff",
        "closing_reflection",
    ],
    "hard": [
        "opening_intro",
        "project_core",
        "system_design_depth",
        "pressure_tradeoff",
        "rag_optimization",
        "business_scenario",
        "technical_debug",
        "project_ownership",
        "scenario_tradeoff",
        "technical_core",
        "closing_reflection",
    ],
}

RAG_SIGNAL_RE = re.compile(
    r"rag|llm|大模型|检索增强|向量|向量库|embedding|embeddings|rerank|reranker|重排|召回|"
    r"grounded|grounding|幻觉|问答系统|retrieval|chunk|chunking",
    re.IGNORECASE,
)

INTERVIEW_DIFFICULTY_PROFILES: Dict[str, Dict[str, Any]] = {
    "easy": {
        "public_label": "简单",
        "company_archetype": "基础执行型面试",
        "question_strategy_summary": "基础知识、常见框架使用、项目复述和日常问题处理。",
        "rubric_summary": "能讲清基础概念、自己做过什么、常见错误如何处理，就能获得较好评价。",
        "feedback_style": "训练导向，指出基础表达和项目复述的具体补强点。",
        "difficulty_guidance": "按基础执行型岗位标准出题，先确认基础知识和可执行性，不提前进行高强度系统设计追问。",
        "routing_difficulty": "easy",
        "routing_top_k": 2,
        "adjacent_difficulties": ["medium"],
        "followup_depth": "basic",
        "evidence_strictness": "normal",
    },
    "medium": {
        "public_label": "中等",
        "company_archetype": "常规岗位能力验证",
        "question_strategy_summary": "项目职责、技术取舍、证据验证、能力短板和复盘。",
        "rubric_summary": "需要证明自己真实参与、能解释方案选择，并能说明不足与改进。",
        "feedback_style": "岗位能力导向，明确证据是否充分、职责边界是否清楚。",
        "difficulty_guidance": "按常规岗位面试标准出题，围绕项目证据、职责边界和技术取舍追问。",
        "routing_difficulty": "medium",
        "routing_top_k": 3,
        "adjacent_difficulties": ["easy", "hard"],
        "followup_depth": "evidence",
        "evidence_strictness": "strict",
    },
    "hard": {
        "public_label": "困难",
        "company_archetype": "高强度综合面试",
        "question_strategy_summary": "项目深挖、系统设计、高并发、稳定性、性能、成本和复杂工程取舍。",
        "rubric_summary": "不仅要讲做了什么，还要讲边界、失败模式、扩展性、成本和可验证结果。",
        "feedback_style": "高标准评估导向，直接指出系统化思考、深度证据和风险控制不足。",
        "difficulty_guidance": "按高强度综合面试标准出题，优先深挖项目、系统设计、并发、可靠性和取舍；RAG 只在岗位相关时出现。",
        "routing_difficulty": "hard",
        "routing_top_k": 4,
        "adjacent_difficulties": ["medium"],
        "followup_depth": "pressure",
        "evidence_strictness": "high",
    },
}

PANEL_ROLE_TITLES = {
    "technical_deep_dive": "Technical Deep Dive",
    "project_follow_up": "Project Follow-up",
    "business_scenario": "Business Scenario",
    "behavior_expression": "Behavior & Communication",
    "pressure_challenge": "Pressure Challenge",
}


class InterviewService:
    @staticmethod
    def _normalize_difficulty(difficulty: Optional[str]) -> str:
        value = str(difficulty or "").strip().lower()
        return value if value in INTERVIEW_DIFFICULTY_PROFILES else "medium"

    @staticmethod
    def _difficulty_profile(difficulty: Optional[str]) -> Dict[str, Any]:
        normalized = InterviewService._normalize_difficulty(difficulty)
        return dict(INTERVIEW_DIFFICULTY_PROFILES[normalized])

    @staticmethod
    def _public_difficulty_profile(difficulty: Optional[str]) -> Dict[str, Any]:
        normalized = InterviewService._normalize_difficulty(difficulty)
        profile = InterviewService._difficulty_profile(difficulty)
        neutral_public_profiles = {
            "easy": {
                "public_label": "简单",
                "company_archetype": "基础执行型面试",
                "question_strategy_summary": "基础知识、常见框架使用、项目复述和日常问题处理。",
                "rubric_summary": "能讲清基础概念、自己做过什么、常见错误如何处理，就能获得较好评价。",
                "feedback_style": "训练导向，指出基础表达和项目复述的具体补强点。",
            },
            "medium": {
                "public_label": "中等",
                "company_archetype": "标准岗位能力面试",
                "question_strategy_summary": "项目职责、技术取舍、证据验证、能力短板和复盘。",
                "rubric_summary": "需要证明自己真实参与、能解释方案选择，并能说明不足与改进。",
                "feedback_style": "岗位能力导向，明确证据是否充分、职责边界是否清楚。",
            },
            "hard": {
                "public_label": "困难",
                "company_archetype": "高强度综合面试",
                "question_strategy_summary": "项目深挖、系统设计、高并发、稳定性、性能、成本和复杂工程取舍。",
                "rubric_summary": "不仅要讲做了什么，还要讲边界、失败模式、扩展性、成本和可验证结果。",
                "feedback_style": "高标准评估导向，直接指出系统化思考、深度证据和风险控制不足。",
            },
        }
        public_profile = neutral_public_profiles.get(normalized, {})
        return {
            "level": normalized,
            "public_label": public_profile.get("public_label", profile["public_label"]),
            "company_archetype": public_profile.get("company_archetype", profile["company_archetype"]),
            "question_strategy_summary": public_profile.get(
                "question_strategy_summary",
                profile["question_strategy_summary"],
            ),
            "rubric_summary": public_profile.get("rubric_summary", profile["rubric_summary"]),
            "feedback_style": public_profile.get("feedback_style", profile["feedback_style"]),
        }

    @staticmethod
    def _difficulty_profile_summary(difficulty: Optional[str]) -> str:
        profile = InterviewService._difficulty_profile(difficulty)
        return (
            f"{profile['public_label']}｜{profile['company_archetype']}："
            f"{profile['question_strategy_summary']} 评分标尺：{profile['rubric_summary']}"
        )

    @staticmethod
    def _has_rag_signal(*values: Any) -> bool:
        chunks: List[str] = []

        def collect(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                chunks.append(value)
                return
            if isinstance(value, dict):
                for nested in value.values():
                    collect(nested)
                return
            if isinstance(value, (list, tuple, set)):
                for nested in value:
                    collect(nested)
                return
            chunks.append(str(value))

        for value in values:
            collect(value)
        return bool(RAG_SIGNAL_RE.search("\n".join(chunks)))

    @staticmethod
    def _safe_routing_top_k(value: Any, fallback: Any = 3) -> int:
        try:
            top_k = int(value)
        except (TypeError, ValueError):
            try:
                top_k = int(fallback)
            except (TypeError, ValueError):
                top_k = 3
        return max(1, min(top_k, 6))

    @staticmethod
    def _load_resume_analysis_payload(resume: Resume) -> Dict[str, Any]:
        payload = (resume.analysis or "").strip()
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Resume analysis payload is not valid JSON: resume_id=%s", resume.id)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _load_resume_evidence(resume: Resume) -> Dict[str, Any]:
        analysis_payload = InterviewService._load_resume_analysis_payload(resume)
        evidence = analysis_payload.get("resume_evidence") or {}
        return evidence if isinstance(evidence, dict) else {}

    @staticmethod
    def _load_resume_payload(resume: Resume) -> Dict[str, Any]:
        payload = (resume.parsed_content or "").strip()
        if not payload:
            raise ValidationError(message="开始面试失败：简历解析结果为空，请重新解析后再试")
        try:
            parsed_resume = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                message="开始面试失败：简历解析结果异常，请重新上传简历或重新解析"
            ) from exc
        if not isinstance(parsed_resume, dict):
            raise ValidationError(
                message="开始面试失败：简历解析结果异常，请重新上传简历或重新解析"
            )
        if not isinstance(parsed_resume.get("normalized_resume"), dict):
            parsed_resume = normalize_parsed_resume(parsed_resume)
        completeness = (parsed_resume.get("normalized_resume") or {}).get("completeness") or {}
        has_skill = bool(completeness.get("has_skills") or parsed_resume.get("skills"))
        has_project_signal = bool(
            completeness.get("has_projects")
            or completeness.get("has_experience")
            or parsed_resume.get("projects")
            or parsed_resume.get("experience")
            or parsed_resume.get("campus_experience")
        )
        if not has_skill and not has_project_signal:
            raise ValidationError(
                message=(
                    "开始面试失败：当前简历解析结果缺少技能、项目或经历信息，"
                    "无法稳定生成面试问题。请重新上传文字版 PDF，或在简历中补充项目/技能后再试。"
                )
            )
        return parsed_resume

    @staticmethod
    def _format_start_interview_error(detail: Optional[str]) -> str:
        message = (detail or "").strip()
        if not message:
            return "开始面试失败：题目生成服务异常，请稍后重试"
        if message.startswith("开始面试失败："):
            return message
        if "题目生成数量不足" in message:
            return "开始面试失败：当前模型返回的题目数量不足，请切换模型或稍后重试"
        if "题目生成失败" in message:
            return "开始面试失败：AI 题目生成失败，请更换模型或稍后重试"
        if (
            "API Key" in message
            or "API Token" in message
            or "Base URL" in message
            or "模型名" in message
            or "连接 " in message
            or "请求参数错误" in message
        ):
            return f"开始面试失败：{message}"
        if "岗位知识库" in message or "简历" in message:
            return message if message.startswith("开始面试失败：") else f"开始面试失败：{message}"
        return f"开始面试失败：{message}"

    @staticmethod
    def _serialize_knowledge_base(knowledge_base: Optional[PositionKnowledgeBase]) -> Optional[Dict]:
        if not knowledge_base:
            return None
        scope = knowledge_base.scope or "private"
        return {
            "id": knowledge_base.id,
            "title": knowledge_base.title,
            "target_position": knowledge_base.target_position,
            "knowledge_content": knowledge_base.knowledge_content,
            "focus_points": knowledge_base.focus_points,
            "interviewer_prompt": knowledge_base.interviewer_prompt,
            "is_active": knowledge_base.is_active,
            "scope": scope,
            "source_label": "后台公共知识库" if scope == "public" else "我的知识库",
        }

    @staticmethod
    def _build_panel_snapshot(
        mode: str,
        requested_panel: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> Dict:
        snapshot = {
            "mode": mode,
            "requested_panel": requested_panel or mode == "panel",
            "display_name": "内部多面试官协同" if mode == "panel" else "单面试官模式",
            "moderator_name": "主持人面试官",
        }
        if mode == "panel":
            snapshot["roles"] = PANEL_ROLE_SPECS
        if fallback_reason:
            snapshot["fallback_reason"] = fallback_reason
        return snapshot

    @staticmethod
    def _set_panel_generation_metadata(
        panel_snapshot: Dict[str, Any],
        *,
        generation_strategy: str,
        panel_status: str,
        fallback_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        metadata = dict(panel_snapshot.get("metadata") or {})
        metadata["generation_strategy"] = generation_strategy
        metadata["panel_status"] = panel_status
        if fallback_reason:
            metadata["fallback_reason"] = fallback_reason
            panel_snapshot["fallback_reason"] = fallback_reason
        panel_snapshot["metadata"] = metadata
        panel_snapshot["panel_status"] = panel_status
        return panel_snapshot

    @staticmethod
    def _sanitize_ai_runtime_config(ai_config: Optional[Dict]) -> Dict:
        if not isinstance(ai_config, dict):
            return {}
        allowed_keys = ("provider", "provider_label", "base_url", "model", "source", "thinking", "reasoning_effort")
        return {
            key: ai_config.get(key)
            for key in allowed_keys
            if ai_config.get(key) not in (None, "")
        }

    @staticmethod
    def _blueprint_claim_strings(interview_blueprint: Optional[Dict], limit: int = 4) -> List[str]:
        claims: List[str] = []
        for item in (interview_blueprint or {}).get("high_risk_claims") or []:
            text = ""
            if isinstance(item, dict):
                text = str(item.get("claim") or "").strip()
                role_only = (
                    AIService._is_role_reference_text(
                        item.get("source"),
                        item.get("claim"),
                        item.get("risk_reason"),
                        item.get("evidence"),
                    )
                    or (
                        bool(item.get("role_requirement_source_ids"))
                        and not bool(item.get("evidence_ids"))
                    )
                )
                if role_only:
                    continue
            else:
                text = str(item).strip()
                if AIService._is_role_reference_text(text):
                    continue
            if text and text not in claims:
                claims.append(text)
            if len(claims) >= limit:
                break
        return claims

    @staticmethod
    def _question_target_evidence_ids(question_meta: Optional[Dict]) -> List[int]:
        ordered: List[int] = []
        for source in (
            (question_meta or {}).get("question_target_evidence_ids") or [],
            (question_meta or {}).get("blueprint_evidence_ids") or [],
        ):
            for value in source:
                try:
                    slice_id = int(value)
                except (TypeError, ValueError):
                    continue
                if slice_id not in ordered:
                    ordered.append(slice_id)
        return ordered[:8]

    @staticmethod
    def _question_target_evidence_summary(question_meta: Optional[Dict]) -> List[str]:
        summary = InterviewService._unique_strings(
            [
                *((question_meta or {}).get("question_target_evidence") or []),
                *((question_meta or {}).get("blueprint_evidence_summary") or []),
            ],
            limit=4,
        )
        return summary

    @staticmethod
    def _derive_question_target_fields(question_meta: Optional[Dict]) -> Dict[str, Any]:
        meta = dict(question_meta or {})
        target_gap = (
            str(meta.get("question_target_gap") or "").strip()
            or str(meta.get("blueprint_track") or "").strip()
            or next(
                (
                    str(item).strip()
                    for item in (meta.get("evaluation_focus") or [])
                    if str(item).strip()
                ),
                "",
            )
            or str(meta.get("intent") or "").strip()
            or str(meta.get("category") or "").strip()
        )
        target_evidence = InterviewService._question_target_evidence_summary(meta)
        target_evidence_ids = InterviewService._question_target_evidence_ids(meta)
        reason = str(meta.get("question_reason") or "").strip()
        requirement_status = str(meta.get("blueprint_requirement_status") or "").strip()
        if not reason:
            if meta.get("is_dynamic_followup"):
                reason = (
                    f"继续验证上一轮暴露的薄弱证据：{target_gap}"
                    if target_gap
                    else "继续验证上一轮回答里尚未被补强的关键证据。"
                )
            elif requirement_status == "unsupported":
                reason = (
                    f"当前几乎没有直接证据支持“{target_gap}”，需要先做保守验证。"
                    if target_gap
                    else "当前直接证据很弱，需要先做保守验证。"
                )
            elif requirement_status == "weak":
                reason = (
                    f"当前只有弱证据支持“{target_gap}”，需要通过本题继续核实。"
                    if target_gap
                    else "当前只有弱证据支持这一能力，需要通过本题继续核实。"
                )
            elif target_evidence:
                reason = (
                    f"围绕已命中的简历证据与岗位知识库追问依据继续核实“{target_gap}”是否真实成立。"
                    if target_gap
                    else "围绕已命中的简历证据与岗位知识库追问依据继续核实候选人的真实能力边界。"
                )
            else:
                reason = (
                    f"围绕“{target_gap}”补齐更具体的事实和证据。"
                    if target_gap
                    else "补齐更具体的事实和证据，避免只停留在泛化表述。"
                )

        return {
            "question_target_gap": target_gap or None,
            "question_target_evidence": target_evidence,
            "question_target_evidence_ids": target_evidence_ids,
            "question_reason": reason,
        }

    @staticmethod
    def _slice_ids_for_blueprint(question_plan: Sequence[Dict]) -> List[int]:
        ordered: List[int] = []
        for item in question_plan or []:
            for slice_item in item.get("selected_slices") or []:
                try:
                    slice_id = int(slice_item.get("slice_id"))
                except (TypeError, ValueError):
                    continue
                if slice_id not in ordered:
                    ordered.append(slice_id)
        return ordered

    @staticmethod
    def _apply_blueprint_to_question_plan(
        question_plan: Sequence[Dict],
        interview_blueprint: Optional[Dict],
    ) -> List[Dict]:
        if not interview_blueprint:
            return [dict(item) for item in question_plan]

        tracks = list((interview_blueprint or {}).get("priority_question_tracks") or [])
        training_focus = InterviewService._unique_strings(
            (interview_blueprint or {}).get("training_focus") or [],
            limit=4,
        )
        high_risk_claims = InterviewService._blueprint_claim_strings(interview_blueprint, limit=4)
        blueprint_evidence = (interview_blueprint or {}).get("blueprint_evidence") or {}
        global_evidence_ids = []
        for value in blueprint_evidence.get("slice_ids") or []:
            try:
                slice_id = int(value)
            except (TypeError, ValueError):
                continue
            if slice_id not in global_evidence_ids:
                global_evidence_ids.append(slice_id)
        global_candidate_evidence_summary = InterviewService._unique_strings(
            [
                *(blueprint_evidence.get("resume_evidence_summary") or []),
            ],
            limit=4,
        )
        global_role_calibration_summary = InterviewService._unique_strings(
            blueprint_evidence.get("slice_summaries") or [],
            limit=4,
        )

        enriched_plan: List[Dict] = []
        for index, item in enumerate(question_plan or []):
            next_item = dict(item)
            track_item = tracks[min(index, len(tracks) - 1)] if tracks else None
            if isinstance(track_item, dict):
                track_name = str(track_item.get("track") or "").strip()
                track_status = str(track_item.get("requirement_status") or "weak").strip() or "weak"
                track_reason = str(track_item.get("reason") or "").strip()
                track_ids = []
                for value in track_item.get("evidence_ids") or []:
                    try:
                        slice_id = int(value)
                    except (TypeError, ValueError):
                        continue
                    if slice_id not in track_ids:
                        track_ids.append(slice_id)
                track_role_ids = []
                for value in track_item.get("role_requirement_source_ids") or []:
                    try:
                        slice_id = int(value)
                    except (TypeError, ValueError):
                        continue
                    if slice_id not in track_role_ids:
                        track_role_ids.append(slice_id)
            else:
                track_name = ""
                track_status = "weak"
                track_reason = ""
                track_ids = []
                track_role_ids = []

            if not track_name and training_focus:
                track_name = training_focus[min(index, len(training_focus) - 1)]
            if track_name:
                candidate_summary_seed = [track_reason] if track_reason and track_ids else []
                role_summary_seed = [track_reason] if track_reason and not track_ids else []
                next_item["blueprint_track"] = track_name
                next_item["blueprint_requirement_status"] = track_status
                next_item["blueprint_evidence_ids"] = track_ids[:4]
                next_item["blueprint_role_calibration_ids"] = track_role_ids[:4] or global_evidence_ids[:4]
                next_item["blueprint_evidence_summary"] = InterviewService._unique_strings(
                    [*candidate_summary_seed, *global_candidate_evidence_summary],
                    limit=3,
                )
                next_item["blueprint_role_calibration_summary"] = InterviewService._unique_strings(
                    [*role_summary_seed, *global_role_calibration_summary],
                    limit=3,
                )
                next_item["evaluation_focus"] = InterviewService._unique_strings(
                    [
                        *(next_item.get("evaluation_focus") or []),
                        track_name,
                        *training_focus[:1],
                    ],
                    limit=6,
                )

            if high_risk_claims and index < 2:
                high_risk_claim = high_risk_claims[min(index, len(high_risk_claims) - 1)]
                next_item["blueprint_high_risk_claims"] = high_risk_claims[:3]
                next_item["selected_followups"] = InterviewService._unique_strings(
                    [*(next_item.get("selected_followups") or []), high_risk_claim],
                    limit=3,
                )

            enriched_plan.append(next_item)
        return enriched_plan

    @staticmethod
    def _compact_slice(item: Dict) -> Dict:
        return {
            "slice_id": item.get("slice_id"),
            "title": item.get("title"),
            "content": item.get("content"),
            "slice_type": item.get("slice_type"),
            "source_section": item.get("source_section"),
            "source_scope": item.get("source_scope"),
            "difficulty": item.get("difficulty"),
            "priority": item.get("priority"),
            "stage_tags": item.get("stage_tags") or [],
            "role_tags": item.get("role_tags") or [],
            "topic_tags": item.get("topic_tags") or [],
            "skill_tags": item.get("skill_tags") or [],
            "scene_tags": item.get("scene_tags") or [],
            "keywords": item.get("keywords") or [],
            "routing_score": item.get("routing_score"),
            "routing_reasons": item.get("routing_reasons") or [],
            "routing_heads": item.get("routing_heads") or {},
            "grounding_confidence": item.get("grounding_confidence"),
            "grounding_warnings": item.get("grounding_warnings") or [],
        }

    @staticmethod
    def _grounding_confidence_summary(selected_slices: Sequence[Dict]) -> Dict:
        counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
        warnings: List[str] = []
        low_confidence_slice_ids: List[int] = []
        for item in selected_slices or []:
            confidence = str(item.get("grounding_confidence") or "unknown").lower()
            if confidence not in counts:
                confidence = "unknown"
            counts[confidence] += 1
            if confidence == "low":
                try:
                    low_confidence_slice_ids.append(int(item.get("slice_id")))
                except (TypeError, ValueError):
                    pass
            for warning in item.get("grounding_warnings") or []:
                warning_text = str(warning).strip()
                if warning_text and warning_text not in warnings:
                    warnings.append(warning_text)
        ordered = ["low", "medium", "high", "unknown"]
        lowest_confidence = next((key for key in ordered if counts.get(key)), "unknown")
        return {
            "counts": counts,
            "lowest_confidence": lowest_confidence,
            "warnings": warnings[:6],
            "low_confidence_slice_ids": low_confidence_slice_ids[:6],
        }

    @staticmethod
    def _slice_label(item: Dict) -> str:
        title = str(item.get("title") or "").strip()
        if title:
            return title
        slice_id = item.get("slice_id")
        if slice_id:
            return f"切片 #{slice_id}"
        return "知识切片"

    @staticmethod
    def _build_evidence_trace(selected_slices: Sequence[Dict], used_slice_ids: Optional[Sequence[int]] = None) -> List[Dict]:
        selected_ids = set()
        for value in used_slice_ids or []:
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                continue

        trace = []
        for item in selected_slices or []:
            try:
                slice_id = int(item.get("slice_id"))
            except (TypeError, ValueError):
                slice_id = None
            reasons = [str(reason).strip() for reason in (item.get("routing_reasons") or []) if str(reason).strip()]
            trace.append(
                {
                    "slice_id": slice_id,
                    "title": InterviewService._slice_label(item),
                    "source_section": item.get("source_section") or item.get("slice_type"),
                    "reason_summary": "；".join(reasons[:3]),
                    "reasons": reasons[:4],
                    "routing_heads": item.get("routing_heads") or {},
                    "grounding_confidence": item.get("grounding_confidence"),
                    "grounding_warnings": item.get("grounding_warnings") or [],
                    "quote": str(item.get("content") or "").strip()[:120],
                    "is_selected": bool(slice_id and slice_id in selected_ids) if selected_ids else True,
                }
            )
        return trace

    @staticmethod
    def _build_evidence_summary(selected_slices: Sequence[Dict], used_slice_ids: Optional[Sequence[int]] = None) -> List[str]:
        trace = InterviewService._build_evidence_trace(selected_slices, used_slice_ids=used_slice_ids)
        summary = []
        for item in trace[:3]:
            label = item.get("title") or "知识切片"
            reason = item.get("reason_summary") or "已命中相关岗位证据"
            summary.append(f"{label}：{reason}")
        return summary

    @staticmethod
    def _route_item_to_text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            preferred_keys = (
                "title",
                "name",
                "project",
                "role",
                "company",
                "position",
                "skill",
                "evidence",
                "description",
                "summary",
                "content",
                "details",
                "result",
                "technologies",
            )
            parts = [
                InterviewService._route_item_to_text(value.get(key))
                for key in preferred_keys
                if value.get(key) is not None
            ]
            if not parts:
                parts = [InterviewService._route_item_to_text(item) for item in list(value.values())[:6]]
            return " ".join(part for part in parts if part)
        if isinstance(value, (list, tuple, set)):
            return " ".join(
                part
                for part in (InterviewService._route_item_to_text(item) for item in value)
                if part
            )
        return str(value).strip()

    @staticmethod
    def _route_values_to_texts(values, limit: int) -> List[str]:
        if values is None:
            return []
        if isinstance(values, (str, dict)):
            values = [values]
        cleaned = []
        for item in values:
            text = InterviewService._route_item_to_text(item)
            if text:
                cleaned.append(text)
            if len(cleaned) >= limit:
                break
        return cleaned

    @staticmethod
    def _resume_route_text(parsed_resume: Dict) -> str:
        parts = []
        normalized = parsed_resume.get("normalized_resume") if isinstance(parsed_resume, dict) else None
        if isinstance(normalized, dict):
            profile = normalized.get("profile") or {}
            if profile:
                parts.append(InterviewService._route_item_to_text(profile))
            for key in (
                "education",
                "skills",
                "projects",
                "experience",
                "awards",
                "campus_experience",
            ):
                value = normalized.get(key)
                if value:
                    parts.append(InterviewService._route_item_to_text(value))
        if parsed_resume.get("summary"):
            parts.append(InterviewService._route_item_to_text(parsed_resume["summary"]))
        if parsed_resume.get("education"):
            parts.append(InterviewService._route_item_to_text(parsed_resume["education"]))
        if parsed_resume.get("skills"):
            parts.append(" ".join(InterviewService._route_values_to_texts(parsed_resume.get("skills"), 12)))
        if parsed_resume.get("projects"):
            parts.append(" ".join(InterviewService._route_values_to_texts(parsed_resume.get("projects"), 4)))
        if parsed_resume.get("experience"):
            parts.append(" ".join(InterviewService._route_values_to_texts(parsed_resume.get("experience"), 4)))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _ability_verification_targets(matching_metrics: Optional[Dict]) -> List[Dict]:
        snapshot = (matching_metrics or {}).get("resume_evaluation_snapshot") or {}
        profile = snapshot.get("ability_profile") or (matching_metrics or {}).get("ability_gap_profile") or {}
        snapshot_targets = snapshot.get("verification_targets") or []
        if isinstance(snapshot_targets, list) and snapshot_targets:
            return snapshot_targets[:8]
        raw_items = profile.get("top_gaps") or profile.get("items") or []
        if not isinstance(raw_items, list):
            return []
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        targets: List[Dict] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            evidence_status = item.get("evidence_status") or "needs_verification"
            verification_keywords = item.get("verification_keywords") or []
            related_matches = item.get("related_matches") or []
            missing_keywords = item.get("missing_keywords") or []
            should_verify = (
                evidence_status in {"claimed_only", "indirect", "missing", "needs_verification"}
                or verification_keywords
                or related_matches
                or missing_keywords
            )
            if not should_verify:
                continue
            keywords = [
                str(value).strip()
                for value in [*verification_keywords, *related_matches, *missing_keywords]
                if str(value).strip()
            ]
            targets.append(
                {
                    "ability_id": item.get("ability_id"),
                    "ability_name": item.get("name") or item.get("ability_name") or "岗位关键能力",
                    "evidence_status": evidence_status,
                    "verification_priority": item.get("verification_priority") or "medium",
                    "priority_score": item.get("priority_score") or 0,
                    "reason": item.get("interview_probe_reason") or item.get("evidence_basis") or "",
                    "keywords": keywords[:8],
                }
            )
        return sorted(
            targets,
            key=lambda item: (
                priority_rank.get(str(item.get("verification_priority") or "medium"), 1),
                -float(item.get("priority_score") or 0),
            ),
        )[:8]

    @staticmethod
    def _build_question_plan(total_questions: int, difficulty: str) -> List[Dict]:
        normalized_difficulty = InterviewService._normalize_difficulty(difficulty)
        profile = InterviewService._difficulty_profile(normalized_difficulty)
        order = QUESTION_ORDERS.get(normalized_difficulty, QUESTION_ORDERS["medium"])
        plan = []
        for index, key in enumerate(order[:total_questions]):
            item = QUESTION_TEMPLATES[key].copy()
            item["index"] = index
            item["template_key"] = key
            item["difficulty_level"] = normalized_difficulty
            item["difficulty_guidance"] = profile["difficulty_guidance"]
            item["company_archetype"] = profile["company_archetype"]
            item["question_strategy_summary"] = profile["question_strategy_summary"]
            item["rubric_summary"] = profile["rubric_summary"]
            item["feedback_style"] = profile["feedback_style"]
            item["routing_difficulty"] = profile["routing_difficulty"]
            item["routing_top_k"] = profile["routing_top_k"]
            item["followup_depth"] = profile["followup_depth"]
            item["evidence_strictness"] = profile["evidence_strictness"]
            plan.append(item)
        return plan

    @staticmethod
    def _route_question_plan(
        question_plan: List[Dict],
        knowledge_base: Optional[Dict],
        parsed_resume: Dict,
        target_position: str,
        difficulty: str,
        matching_metrics: Optional[Dict] = None,
    ) -> List[Dict]:
        normalized_difficulty = InterviewService._normalize_difficulty(difficulty)
        profile = InterviewService._difficulty_profile(normalized_difficulty)
        verification_targets = InterviewService._ability_verification_targets(matching_metrics)
        has_rag_signal = InterviewService._has_rag_signal(
            target_position,
            parsed_resume.get("skills"),
            parsed_resume.get("projects"),
            parsed_resume.get("experience"),
            parsed_resume.get("work_experience"),
            parsed_resume.get("project_experience"),
        )

        def apply_rag_gate(item: Dict) -> Dict:
            effective_item = dict(item or {})
            if effective_item.get("template_key") != "rag_optimization" or has_rag_signal:
                return effective_item
            replacement = QUESTION_TEMPLATES["system_design_depth"].copy()
            replacement.update(
                {
                    key: value
                    for key, value in effective_item.items()
                    if key
                    in {
                        "index",
                        "difficulty_level",
                        "difficulty_guidance",
                        "company_archetype",
                        "question_strategy_summary",
                        "rubric_summary",
                        "feedback_style",
                        "routing_difficulty",
                        "routing_top_k",
                        "followup_depth",
                        "evidence_strictness",
                    }
                }
            )
            replacement["template_key"] = "system_design_depth"
            replacement["rag_gate_replaced"] = True
            return replacement

        def target_for(index: int) -> Optional[Dict]:
            if not verification_targets:
                return None
            return verification_targets[index % len(verification_targets)]

        def enrich_item(item: Dict, index: int, selected: Optional[List[Dict]] = None) -> Dict:
            verification_target = target_for(index)
            evaluation_focus = list(item.get("evaluation_focus") or [])
            if verification_target:
                ability_name = verification_target.get("ability_name") or "岗位关键能力"
                focus_text = f"验证{ability_name}掌握程度"
                if focus_text not in evaluation_focus:
                    evaluation_focus.append(focus_text)
            routing_difficulty = item.get("routing_difficulty") or profile["routing_difficulty"]
            routing_top_k = InterviewService._safe_routing_top_k(
                item.get("routing_top_k"),
                profile["routing_top_k"],
            )
            return {
                **item,
                "evaluation_focus": evaluation_focus,
                "verification_target": verification_target,
                "question_target_gap": (verification_target or {}).get("reason") or item.get("question_target_gap"),
                "question_reason": (verification_target or {}).get("reason") or item.get("question_reason"),
                "selected_slices": selected or [],
                "difficulty_level": item.get("difficulty_level") or normalized_difficulty,
                "difficulty_guidance": item.get("difficulty_guidance") or profile["difficulty_guidance"],
                "company_archetype": item.get("company_archetype") or profile["company_archetype"],
                "question_strategy_summary": item.get("question_strategy_summary") or profile["question_strategy_summary"],
                "rubric_summary": item.get("rubric_summary") or profile["rubric_summary"],
                "feedback_style": item.get("feedback_style") or profile["feedback_style"],
                "routing_difficulty": routing_difficulty,
                "routing_top_k": routing_top_k,
                "followup_depth": item.get("followup_depth") or profile["followup_depth"],
                "evidence_strictness": item.get("evidence_strictness") or profile["evidence_strictness"],
                "rag_signal_present": has_rag_signal,
            }

        if not knowledge_base:
            return [
                enrich_item(apply_rag_gate(item), index)
                for index, item in enumerate(question_plan)
            ]

        slices = knowledge_base.get("slices") or []
        if not slices:
            return [
                enrich_item(apply_rag_gate(item), index)
                for index, item in enumerate(question_plan)
            ]

        routed = []
        top_k = 2 if len(question_plan) >= 7 else 3
        resume_text = InterviewService._resume_route_text(parsed_resume)
        resume_skills = InterviewService._route_values_to_texts(parsed_resume.get("skills"), 12)
        resume_projects = InterviewService._route_values_to_texts(parsed_resume.get("projects"), 6)
        for index, item in enumerate(question_plan):
            effective_item = apply_rag_gate(item)
            verification_target = target_for(index)
            verification_text = ""
            weakness_terms: List[str] = []
            if verification_target:
                weakness_terms = [
                    str(value)
                    for value in [
                        verification_target.get("ability_name"),
                        *(verification_target.get("keywords") or []),
                    ]
                    if str(value or "").strip()
                ][:8]
                verification_text = "\n".join(
                    [
                        str(verification_target.get("ability_name") or ""),
                        str(verification_target.get("evidence_status") or ""),
                        str(verification_target.get("reason") or ""),
                        " ".join(verification_target.get("keywords") or []),
                    ]
                )
            query_text = "\n".join(
                [
                    target_position,
                    resume_text,
                    verification_text,
                    effective_item.get("intent") or "",
                    effective_item.get("difficulty_guidance") or "",
                    " ".join(effective_item.get("evaluation_focus") or []),
                ]
            )
            try:
                selected = position_knowledge_base_slice_service.rank_slices(
                    slices=slices,
                    query_text=query_text,
                    stage=effective_item.get("stage"),
                    role=effective_item.get("lead_role"),
                    scene=effective_item.get("category") or effective_item.get("stage"),
                    difficulty=effective_item.get("routing_difficulty") or normalized_difficulty,
                    skills=resume_skills[:8],
                    topics=[target_position, *(resume_projects[:2])],
                    weakness_terms=weakness_terms,
                    top_k=InterviewService._safe_routing_top_k(
                        effective_item.get("routing_top_k"),
                        top_k,
                    ),
                )
                if not selected:
                    selected = position_knowledge_base_slice_service.rank_slices(
                        slices=slices,
                        query_text=query_text,
                        difficulty=effective_item.get("routing_difficulty") or normalized_difficulty,
                        skills=resume_skills[:6],
                        topics=[target_position],
                        weakness_terms=weakness_terms,
                        top_k=2,
                    )
            except Exception as exc:
                logger.warning("Knowledge slice routing failed for stage=%s: %s", effective_item.get("stage"), exc)
                knowledge_base["slices"] = []
                knowledge_base["slice_count"] = 0
                knowledge_base["routing_strategy"] = "full_text_fallback"
                selected = []
            routed.append(
                enrich_item(
                    effective_item,
                    index,
                    [InterviewService._compact_slice(slice_item) for slice_item in selected],
                )
            )
        return routed

    @staticmethod
    def _first_resume_label(values: Any, keys: Sequence[str]) -> str:
        if not isinstance(values, list):
            values = [values] if values else []
        for item in values:
            if isinstance(item, dict):
                for key in keys:
                    value = str(item.get(key) or "").strip()
                    if value:
                        return value
            else:
                value = str(item or "").strip()
                if value:
                    return value
        return ""

    @staticmethod
    def _question_has_internal_prompt_leak(text: Any) -> bool:
        value = str(text or "")
        if not value.strip():
            return False
        patterns = (
            r"Blueprint\s+priority",
            r"blueprint[_\s-]*track",
            r"blueprint[_\s-]*priority",
            r"role[_\s-]*calibration",
            r"Assess\s+boundary",
            r"Place\s+the\s+candidate",
            r"Question\s+plan",
            r"Question\s+reason",
            r"Question\s+target\s+gap",
            r"Evaluation\s+focus",
            r"Interview\s+routing\s+context",
            r"Interview\s+blueprint",
            r"Internal\s+panel",
            r"Internal\s+roles",
            r"Moderator\s+name",
            r"Plan\s*#",
            r"Lead\s+role",
            r"Support\s+roles",
            r"Requirement\s+status",
            r"Candidate\s+evidence",
            r"Suggested\s+followups",
            r"question_plan",
            r"candidate_evidence",
            r"verification_reason",
            r"stage/category/intent",
            r"lead_role",
            r"support_roles",
            r"assessment_points",
            r"selected_questions",
            r"used_slice_ids",
            r"routed[_\s-]*slice",
            r"routed\s+slices",
            r"evaluation_focus",
            r"selected_followups",
            r"chain[-\s]?of[-\s]?thought",
            r"Use\s+the\s+self[-\s]?introduction",
            r"Deep[-\s]?dive\s+the\s+most\s+important\s+project",
            r"Validate\s+mastery\s+of\s+core\s+knowledge",
            r"Evaluate\s+collaboration",
            r"Use\s+debugging\s+or\s+optimization",
            r"Further\s+verify\s+role\s+boundaries",
            r"Use\s+business\s+changes",
            r"Close\s+the\s+interview",
            r"Probe\s+technical\s+depth",
            r"Check\s+basic\s+role\s+knowledge",
            r"Probe\s+scalable\s+system\s+design",
            r"Probe\s+RAG\s+or\s+LLM\s+engineering",
            r"题目计划",
            r"评估重点",
            r"主持人推理",
            r"内部面板",
            r"内部字段",
            r"候选人证据",
            r"蓝图优先级",
            r"链式思考",
            r"\b(stage|category|intent|moderator|schema|step|type|goal|priority|focus|blueprint)\b\s*[:=]",
        )
        return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _safe_visible_text(text: Any, fallback: Optional[str] = None) -> Optional[str]:
        if text is None:
            return None
        value = str(text).strip()
        if not value:
            return ""
        if InterviewService._question_has_internal_prompt_leak(value):
            return fallback
        return value

    @staticmethod
    def _sanitize_public_payload(
        payload: Any,
        fallback_question: Optional[str] = None,
        key_name: Optional[str] = None,
    ) -> Any:
        if isinstance(payload, dict):
            cleaned = {}
            for key, value in payload.items():
                cleaned_value = InterviewService._sanitize_public_payload(
                    value,
                    fallback_question=fallback_question,
                    key_name=str(key),
                )
                if cleaned_value is None:
                    continue
                cleaned[key] = cleaned_value
            return cleaned
        if isinstance(payload, list):
            cleaned_items = []
            for item in payload:
                cleaned_item = InterviewService._sanitize_public_payload(
                    item,
                    fallback_question=fallback_question,
                    key_name=key_name,
                )
                if cleaned_item is None:
                    continue
                if isinstance(cleaned_item, str) and not cleaned_item.strip():
                    continue
                cleaned_items.append(cleaned_item)
            return cleaned_items
        if isinstance(payload, str):
            if InterviewService._question_has_internal_prompt_leak(payload):
                if key_name in {"question", "selected_question"} and fallback_question:
                    return fallback_question
                return None
            return payload
        return payload

    @staticmethod
    def _safe_visible_list(items: Any) -> List[str]:
        if not items:
            return []
        if isinstance(items, str):
            items = [items]
        result = []
        for item in items or []:
            value = InterviewService._safe_visible_text(item)
            if value:
                result.append(value)
        return result

    @staticmethod
    def _sanitize_followup_payload(payload: Any, fallback_question: str) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        cleaned = dict(payload)
        if InterviewService._question_has_internal_prompt_leak(cleaned.get("question")):
            cleaned["question"] = fallback_question
        for key in ("reason", "target_gap", "next_focus"):
            if InterviewService._question_has_internal_prompt_leak(cleaned.get(key)):
                cleaned[key] = None
        for key in ("target_evidence", "evidence_source_summary", "selected_followups"):
            if key in cleaned:
                cleaned[key] = InterviewService._safe_visible_list(cleaned.get(key))
        return cleaned

    @staticmethod
    def _sanitize_panel_context(
        panel_context: Any,
        fallback_question: str,
    ) -> tuple[Dict[str, Any], bool]:
        if not isinstance(panel_context, dict):
            return {}, False
        sanitized = False
        context = dict(panel_context)
        moderator = dict(context.get("moderator") or {})
        if moderator:
            if InterviewService._question_has_internal_prompt_leak(moderator.get("selected_question")):
                moderator["selected_question"] = fallback_question
                sanitized = True
            raw_followups = moderator.get("selected_followups") or []
            safe_followups = InterviewService._safe_visible_list(raw_followups)
            if safe_followups != (raw_followups if isinstance(raw_followups, list) else [raw_followups]):
                sanitized = True
            moderator["selected_followups"] = safe_followups
            if isinstance(moderator.get("next_best_followup"), dict):
                cleaned_followup = InterviewService._sanitize_followup_payload(
                    moderator.get("next_best_followup"),
                    fallback_question=fallback_question,
                )
                if cleaned_followup != moderator.get("next_best_followup"):
                    sanitized = True
                moderator["next_best_followup"] = cleaned_followup
            context["moderator"] = moderator

        panel_items = []
        for item in context.get("panel") or []:
            if not isinstance(item, dict):
                continue
            panel_item = dict(item)
            for key in ("question_candidates", "followup_candidates"):
                if key in panel_item:
                    safe_values = InterviewService._safe_visible_list(panel_item.get(key))
                    if safe_values != panel_item.get(key):
                        sanitized = True
                    panel_item[key] = safe_values
            panel_items.append(panel_item)
        if panel_items:
            context["panel"] = panel_items

        if sanitized:
            metadata = dict(context.get("metadata") or {})
            metadata["question_sanitized_reason"] = "internal_prompt_leak"
            metadata["original_question_redacted"] = True
            context["metadata"] = metadata
        context = InterviewService._sanitize_public_payload(
            context,
            fallback_question=fallback_question,
        )
        return context, sanitized

    @staticmethod
    def _sanitize_question_public_fields(question_meta: Dict) -> Dict:
        meta = dict(question_meta or {})
        sanitized = False
        question_text = str(meta.get("question") or "").strip()
        if InterviewService._question_has_internal_prompt_leak(question_text):
            category, fallback_question = InterviewService._safe_question_text_for_plan(
                index=int(meta.get("index") or 0),
                plan=meta,
                position_label="目标岗位",
            )
            meta["question"] = fallback_question
            meta["category"] = meta.get("category") or category
            question_text = fallback_question
            sanitized = True

        for key in ("question_target_gap", "question_reason", "panel_reasoning_summary"):
            if InterviewService._question_has_internal_prompt_leak(meta.get(key)):
                meta[key] = None
                sanitized = True
        if InterviewService._question_has_internal_prompt_leak(meta.get("feedback")):
            meta["feedback"] = ""
            sanitized = True

        for key in ("selected_followups", "question_target_evidence", "evidence_summary"):
            if key in meta:
                safe_values = InterviewService._safe_visible_list(meta.get(key))
                if safe_values != meta.get(key):
                    sanitized = True
                meta[key] = safe_values

        if isinstance(meta.get("evaluation"), dict):
            meta["evaluation"] = InterviewService._sanitize_round_evaluation_public_fields(
                meta.get("evaluation") or {},
                fallback_question=question_text or "请继续补充一个具体例子。",
            )

        panel_context, panel_sanitized = InterviewService._sanitize_panel_context(
            meta.get("panel_context") or {},
            fallback_question=question_text or "请继续补充一个具体例子。",
        )
        if panel_context:
            meta["panel_context"] = panel_context
        sanitized = sanitized or panel_sanitized
        if sanitized:
            panel_context = dict(meta.get("panel_context") or {})
            metadata = dict(panel_context.get("metadata") or {})
            metadata["question_sanitized_reason"] = "internal_prompt_leak"
            metadata["original_question_redacted"] = True
            panel_context["metadata"] = metadata
            meta["panel_context"] = panel_context
        return meta

    @staticmethod
    def _sanitize_round_evaluation_public_fields(
        evaluation: Dict,
        fallback_question: str,
    ) -> Dict:
        cleaned = dict(evaluation or {})
        cleaned["selected_followups"] = InterviewService._safe_visible_list(
            cleaned.get("selected_followups") or []
        )
        cleaned["feedback"] = InterviewService._safe_visible_text(cleaned.get("feedback"))
        cleaned["strengths"] = InterviewService._safe_visible_list(cleaned.get("strengths") or [])
        cleaned["gaps"] = InterviewService._safe_visible_list(cleaned.get("gaps") or [])
        cleaned["next_focus"] = InterviewService._safe_visible_text(cleaned.get("next_focus"))
        if isinstance(cleaned.get("moderator"), dict):
            moderator = dict(cleaned.get("moderator") or {})
            moderator["selected_followups"] = InterviewService._safe_visible_list(
                moderator.get("selected_followups") or []
            )
            moderator["reasoning_summary"] = InterviewService._safe_visible_text(
                moderator.get("reasoning_summary")
            )
            moderator["difficulty_hint"] = InterviewService._safe_visible_text(
                moderator.get("difficulty_hint")
            )
            if isinstance(moderator.get("next_best_followup"), dict):
                moderator["next_best_followup"] = InterviewService._sanitize_followup_payload(
                    moderator.get("next_best_followup"),
                    fallback_question=fallback_question,
                )
            cleaned["moderator"] = moderator
        if isinstance(cleaned.get("next_best_followup"), dict):
            cleaned["next_best_followup"] = InterviewService._sanitize_followup_payload(
                cleaned.get("next_best_followup"),
                fallback_question=fallback_question,
            )
        for key in ("unresolved_gaps",):
            cleaned[key] = InterviewService._safe_visible_list(cleaned.get(key) or [])
        for key in ("evidence_strength_delta", "claim_confidence_change"):
            safe_items = []
            for item in cleaned.get(key) or []:
                if not isinstance(item, dict):
                    continue
                safe_item = dict(item)
                for text_key in ("evidence", "reason", "claim"):
                    if text_key in safe_item:
                        safe_item[text_key] = InterviewService._safe_visible_text(safe_item.get(text_key))
                safe_items.append(safe_item)
            cleaned[key] = safe_items
        cleaned = InterviewService._sanitize_public_payload(
            cleaned,
            fallback_question=fallback_question,
        )
        return cleaned

    @staticmethod
    def _safe_question_text_for_plan(
        *,
        index: int,
        plan: Dict,
        position_label: str,
        evidence_hint: Optional[str] = None,
    ) -> tuple[str, str]:
        safe_position = position_label or "目标岗位"
        safe_evidence = evidence_hint or "简历中最相关的一段经历"
        stage = str((plan or {}).get("stage") or "").strip().lower()
        category = str((plan or {}).get("category") or "").strip().lower()
        difficulty = InterviewService._normalize_difficulty((plan or {}).get("difficulty_level"))
        template_key = str((plan or {}).get("template_key") or "").strip()
        company_archetype = str((plan or {}).get("company_archetype") or "").strip()
        key = stage or category

        if index == 0 or key == "opening" or category == "self-intro":
            return (
                "self-intro",
                f"请先做一个简短自我介绍，说明你为什么匹配{safe_position}，并指出简历里最能支撑这个岗位的一段经历。",
            )
        if template_key == "basic_knowledge":
            return (
                "technical",
                f"按{company_archetype or '基础执行岗'}标准，请说明{safe_position}日常最常用的基础知识或框架能力，并结合一个你实际用过的例子说明。",
            )
        if template_key == "system_design_depth":
            return (
                "system-design",
                f"如果把你做过的“{safe_evidence}”扩展到更高并发或更多用户场景，你会如何设计接口、数据存储、缓存/队列和故障兜底？请说明关键取舍。",
            )
        if template_key == "rag_optimization":
            return (
                "system-design",
                "如果这个岗位中的 RAG/知识库能力要上线到真实业务，你会如何优化召回、切片、重排、答案可信度和评估监控？请结合项目或岗位场景说明。",
            )
        if index == 1 or key == "project" or "project" in category:
            if difficulty == "hard":
                return (
                    "project",
                    f"请围绕“{safe_evidence}”做一次项目深挖：你负责的边界是什么，最难的技术/业务取舍是什么，如果流量或数据规模扩大 10 倍会怎么改？",
                )
            return (
                "project",
                f"请围绕“{safe_evidence}”展开说明：当时的场景是什么，你具体做了什么，最后形成了什么结果？",
            )
        if key == "gap":
            return (
                "gap",
                f"结合{safe_position}的要求，你认为自己当前最需要补强的能力是什么？接下来会如何学习和验证？",
            )
        if key == "technical" or "technical" in category:
            if difficulty == "easy":
                return (
                    "technical",
                    f"请说明{safe_position}常用的一项基础技术你是怎么理解和使用的，并结合一个项目例子说明遇到问题时如何排查。",
                )
            if difficulty == "hard":
                return (
                    "technical",
                    "请结合一个具体项目说明你如何处理性能、并发、稳定性或故障恢复问题，重点说明约束、方案取舍和验证结果。",
                )
            return (
                "technical",
                "请结合一个具体项目说明你如何拆解技术问题、选择方案并验证结果，重点说明你自己的判断依据。",
            )
        if key == "scenario" or "scenario" in category:
            if difficulty == "hard":
                return (
                    "scenario",
                    f"假设你负责的{safe_position}相关系统在高峰期出现超时、数据不一致或成本上升，你会如何定位、降级、恢复并复盘？",
                )
            return (
                "scenario",
                f"假设你在{safe_position}工作中遇到需求变化或资源受限，请结合一个具体经历说明你会如何做取舍。",
            )
        if key == "behavior" or "behavior" in category:
            return (
                "behavior",
                "请举一个你与他人协作或独立推进任务的例子，说明你如何沟通、推进和复盘。",
            )
        if key == "closing":
            return (
                "closing",
                f"如果入职{safe_position}，你前三个月会如何补齐短板并证明自己能胜任？",
            )
        return (
            "followup",
            f"请补充一个与{safe_position}相关的具体例子，说明你的行动、判断依据和复盘改进。",
        )

    @staticmethod
    def _build_deterministic_question_fallback(
        *,
        question_plan: Sequence[Dict],
        parsed_resume: Dict,
        target_position: str,
        total_questions: int,
        fallback_reason: str = "question_generation_failed",
    ) -> List[Dict]:
        count = max(len(question_plan), int(total_questions or 0), 3)
        project_label = InterviewService._first_resume_label(
            parsed_resume.get("projects") or parsed_resume.get("project_experience"),
            ("title", "name", "project_name", "project", "description"),
        )
        experience_label = InterviewService._first_resume_label(
            parsed_resume.get("experience") or parsed_resume.get("work_experience"),
            ("company", "role", "position", "title", "description"),
        )
        skill_label = InterviewService._first_resume_label(
            parsed_resume.get("skills"),
            ("skill", "name", "label", "description"),
        )
        evidence_hint = project_label or experience_label or skill_label or "简历中最相关的一段经历"
        position_label = target_position or "目标岗位"
        fallback_profile = InterviewService._public_difficulty_profile(
            (question_plan[0] or {}).get("difficulty_level") if question_plan else None
        )

        templates = [
            (
                "self-intro",
                f"请先做一个简短自我介绍，说明你为什么匹配{position_label}，并指出简历里最能支撑这个岗位的一段经历。",
            ),
            (
                "project",
                f"请围绕“{evidence_hint}”展开说明：当时的场景是什么，你具体做了什么，最后形成了什么结果？",
            ),
            (
                "gap",
                f"结合{position_label}的要求，你认为自己当前最需要补强的能力是什么？接下来会如何学习和验证？",
            ),
        ]

        templates = []
        while len(templates) < count:
            extra_index = len(templates)
            extra_plan = dict(question_plan[extra_index]) if extra_index < len(question_plan) else {}
            templates.append(
                InterviewService._safe_question_text_for_plan(
                    index=extra_index,
                    plan=extra_plan,
                    position_label=position_label,
                    evidence_hint=evidence_hint,
                )
            )

        questions: List[Dict] = []
        for index in range(count):
            plan = dict(question_plan[index]) if index < len(question_plan) else {}
            if index < len(templates):
                category, text = templates[index]
            else:
                intent = str(plan.get("intent") or plan.get("category") or "岗位能力验证").strip()
                category = str(plan.get("category") or "followup")
                text = (
                    f"围绕{position_label}的“{intent}”，请补充一个具体例子，说明你的行动、判断依据和复盘改进。"
                )
            questions.append(
                {
                    "index": index,
                    "question": text,
                    "category": category,
                    "stage": plan.get("stage"),
                    "lead_role": plan.get("lead_role"),
                    "support_roles": plan.get("support_roles") or [],
                    "intent": plan.get("intent") or category,
                    "evaluation_focus": plan.get("evaluation_focus") or [],
                    "difficulty_level": plan.get("difficulty_level"),
                    "difficulty_guidance": plan.get("difficulty_guidance"),
                    "company_archetype": plan.get("company_archetype"),
                    "question_strategy_summary": plan.get("question_strategy_summary"),
                    "rubric_summary": plan.get("rubric_summary"),
                    "routing_difficulty": plan.get("routing_difficulty"),
                    "routing_top_k": plan.get("routing_top_k"),
                    "followup_depth": plan.get("followup_depth"),
                    "evidence_strictness": plan.get("evidence_strictness"),
                    "panel_context": {
                        "metadata": {
                            "fallback_generated": True,
                            "fallback_reason": fallback_reason,
                            "difficulty_profile": fallback_profile,
                        }
                    },
                }
            )
        return questions

    @staticmethod
    def _is_question_generation_validation_error(exc: ValidationError) -> bool:
        detail = str(getattr(exc, "detail", "") or getattr(exc, "message", "") or "")
        return "题目生成" in detail or "Question payload" in detail

    @staticmethod
    def _normalize_questions(
        raw_questions: List[Dict],
        question_plan: List[Dict],
        interview_mode: str,
    ) -> List[Dict]:
        if len(raw_questions) < len(question_plan):
            raise ValidationError(message="AI 题目生成数量不足，请稍后重试")

        normalized = []
        for index, plan in enumerate(question_plan):
            raw = raw_questions[index] or {}
            if isinstance(raw, str):
                raw = {"question": raw}
            question_text = (raw.get("question") or "").strip()
            if not question_text:
                raise ValidationError(message="AI 题目生成失败，请稍后重试")

            support_roles = raw.get("support_roles") or plan.get("support_roles") or []
            if isinstance(support_roles, str):
                support_roles = [support_roles]

            evaluation_focus = raw.get("evaluation_focus") or plan.get("evaluation_focus") or []
            if isinstance(evaluation_focus, str):
                evaluation_focus = [evaluation_focus]

            selected_slices = plan.get("selected_slices") or []
            requested_ids = raw.get("used_slice_ids") or raw.get("selected_slice_ids") or []
            if requested_ids:
                matched = [
                    item for item in selected_slices if item.get("slice_id") in set(requested_ids)
                ]
                if matched:
                    selected_slices = matched
            panel_context = dict(raw.get("panel_context") or {})
            metadata = dict(panel_context.get("metadata") or {})
            sanitized_category = None
            if selected_slices:
                metadata["grounding_confidence_summary"] = InterviewService._grounding_confidence_summary(
                    selected_slices
                )
                if requested_ids:
                    metadata["retrieved_slice_ids"] = requested_ids
                panel_context["metadata"] = metadata
            if InterviewService._question_has_internal_prompt_leak(question_text):
                sanitized_category, fallback_question = InterviewService._safe_question_text_for_plan(
                    index=index,
                    plan=plan,
                    position_label="目标岗位",
                )
                question_text = fallback_question
                metadata["question_sanitized_reason"] = "internal_prompt_leak"
                metadata["original_question_redacted"] = True
                panel_context["metadata"] = metadata

            raw_followups = raw.get("selected_followups") or []
            if isinstance(raw_followups, str):
                raw_followups = [raw_followups]
            selected_followups = []
            for item in raw_followups:
                followup = str(item or "").strip()
                if not followup:
                    continue
                if InterviewService._question_has_internal_prompt_leak(followup):
                    metadata["question_sanitized_reason"] = "internal_prompt_leak"
                    metadata["original_question_redacted"] = True
                    metadata["selected_followups_redacted"] = True
                    panel_context["metadata"] = metadata
                    continue
                selected_followups.append(followup)

            question_target_gap = raw.get("question_target_gap") or plan.get("question_target_gap")
            if InterviewService._question_has_internal_prompt_leak(question_target_gap):
                question_target_gap = None
                metadata["question_sanitized_reason"] = "internal_prompt_leak"
                metadata["question_target_gap_redacted"] = True
                panel_context["metadata"] = metadata

            question_reason = raw.get("question_reason") or plan.get("question_reason")
            if InterviewService._question_has_internal_prompt_leak(question_reason):
                question_reason = None
                metadata["question_sanitized_reason"] = "internal_prompt_leak"
                metadata["question_reason_redacted"] = True
                panel_context["metadata"] = metadata

            question_item = {
                "index": index,
                "question": question_text,
                "category": raw.get("category") or plan.get("category") or sanitized_category,
                "stage": raw.get("stage") or plan.get("stage"),
                "lead_role": raw.get("lead_role") or plan.get("lead_role"),
                "support_roles": support_roles,
                "intent": raw.get("intent") or plan.get("intent"),
                "evaluation_focus": evaluation_focus,
                "difficulty_level": raw.get("difficulty_level") or plan.get("difficulty_level"),
                "difficulty_guidance": raw.get("difficulty_guidance") or plan.get("difficulty_guidance"),
                "company_archetype": raw.get("company_archetype") or plan.get("company_archetype"),
                "question_strategy_summary": raw.get("question_strategy_summary") or plan.get("question_strategy_summary"),
                "rubric_summary": raw.get("rubric_summary") or plan.get("rubric_summary"),
                "feedback_style": raw.get("feedback_style") or plan.get("feedback_style"),
                "routing_difficulty": raw.get("routing_difficulty") or plan.get("routing_difficulty"),
                "routing_top_k": raw.get("routing_top_k") or plan.get("routing_top_k"),
                "followup_depth": raw.get("followup_depth") or plan.get("followup_depth"),
                "evidence_strictness": raw.get("evidence_strictness") or plan.get("evidence_strictness"),
                "rag_signal_present": raw.get("rag_signal_present") if raw.get("rag_signal_present") is not None else plan.get("rag_signal_present"),
                "selected_slices": selected_slices,
                "used_slice_ids": requested_ids or [],
                "evidence_trace": InterviewService._build_evidence_trace(
                    selected_slices,
                    used_slice_ids=requested_ids or [],
                ),
                "evidence_summary": InterviewService._build_evidence_summary(
                    selected_slices,
                    used_slice_ids=requested_ids or [],
                ),
                "blueprint_track": raw.get("blueprint_track") or plan.get("blueprint_track"),
                "blueprint_requirement_status": raw.get("blueprint_requirement_status")
                or plan.get("blueprint_requirement_status"),
                "blueprint_evidence_ids": raw.get("blueprint_evidence_ids")
                or plan.get("blueprint_evidence_ids")
                or [],
                "blueprint_evidence_summary": raw.get("blueprint_evidence_summary")
                or plan.get("blueprint_evidence_summary")
                or [],
                "blueprint_role_calibration_ids": raw.get("blueprint_role_calibration_ids")
                or plan.get("blueprint_role_calibration_ids")
                or [],
                "blueprint_role_calibration_summary": raw.get("blueprint_role_calibration_summary")
                or plan.get("blueprint_role_calibration_summary")
                or [],
                "blueprint_high_risk_claims": raw.get("blueprint_high_risk_claims")
                or plan.get("blueprint_high_risk_claims")
                or [],
                "selected_followups": selected_followups,
                "difficulty_hint": raw.get("difficulty_hint"),
                "panel_context": panel_context,
                "panel_reasoning_summary": raw.get("panel_reasoning_summary"),
                "verification_target": raw.get("verification_target") or plan.get("verification_target"),
                "question_target_gap": question_target_gap,
                "question_target_evidence": raw.get("question_target_evidence") or [],
                "question_target_evidence_ids": raw.get("question_target_evidence_ids") or [],
                "question_reason": question_reason,
                "interview_mode": interview_mode,
                "answer": None,
                "score": None,
                "feedback": None,
                "evaluation": None,
            }
            question_item.update(InterviewService._derive_question_target_fields(question_item))
            question_item = InterviewService._sanitize_question_public_fields(question_item)
            normalized.append(question_item)
        return normalized

    @staticmethod
    def _serialize_questions(questions: Any) -> List[Dict]:
        if not questions:
            return []
        parsed = questions
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                logger.warning("Interview questions_data is not valid JSON text")
                return []
        if isinstance(parsed, dict):
            for key in ("questions", "items", "data"):
                value = parsed.get(key)
                if isinstance(value, list):
                    parsed = value
                    break
            else:
                parsed = [parsed]
        if not isinstance(parsed, list):
            logger.warning("Interview questions_data is not a list: %s", type(parsed).__name__)
            return []
        cleaned = [item for item in parsed if isinstance(item, dict)]
        return json.loads(json.dumps(cleaned, ensure_ascii=False, default=InterviewService._json_safe))

    @staticmethod
    def _build_question_scores(questions: List[Dict]) -> List[Dict]:
        items = []
        for question in questions:
            safe_question = InterviewService._sanitize_question_public_fields(question)
            items.append(
                {
                    "question": safe_question.get("question"),
                    "score": float(safe_question.get("score") or 0),
                    "feedback": safe_question.get("feedback") or "",
                    "category": safe_question.get("category"),
                    "lead_role": safe_question.get("lead_role"),
                    "difficulty_level": safe_question.get("difficulty_level"),
                    "difficulty_guidance": safe_question.get("difficulty_guidance"),
                    "rubric_summary": safe_question.get("rubric_summary"),
                }
            )
        return items

    @staticmethod
    def _build_qa_data(questions: List[Dict]) -> List[Dict]:
        qa_data = []
        for question in questions:
            qa_data.append(
                {
                    "question": question.get("question"),
                    "answer": question.get("answer") or "未回答",
                    "score": float(question.get("score") or 0),
                    "feedback": question.get("feedback") or "",
                    "category": question.get("category"),
                    "stage": question.get("stage"),
                    "lead_role": question.get("lead_role"),
                    "support_roles": question.get("support_roles") or [],
                    "intent": question.get("intent"),
                    "difficulty_level": question.get("difficulty_level"),
                    "company_archetype": question.get("company_archetype"),
                    "question_strategy_summary": question.get("question_strategy_summary"),
                    "rubric_summary": question.get("rubric_summary"),
                    "evaluation_focus": question.get("evaluation_focus") or [],
                    "selected_slices": question.get("selected_slices") or [],
                    "used_slice_ids": question.get("used_slice_ids") or [],
                    "evidence_trace": question.get("evidence_trace") or [],
                    "evidence_summary": question.get("evidence_summary") or [],
                    "question_target_gap": question.get("question_target_gap"),
                    "verification_target": question.get("verification_target"),
                    "question_target_evidence": question.get("question_target_evidence") or [],
                    "question_target_evidence_ids": question.get("question_target_evidence_ids") or [],
                    "question_reason": question.get("question_reason"),
                    "blueprint_track": question.get("blueprint_track"),
                    "blueprint_requirement_status": question.get("blueprint_requirement_status"),
                    "blueprint_evidence_ids": question.get("blueprint_evidence_ids") or [],
                    "blueprint_evidence_summary": question.get("blueprint_evidence_summary") or [],
                    "blueprint_high_risk_claims": question.get("blueprint_high_risk_claims") or [],
                    "selected_followups": question.get("selected_followups") or [],
                    "panel_context": question.get("panel_context") or {},
                    "evaluation": question.get("evaluation") or {},
                }
            )
        return qa_data

    @staticmethod
    def _unique_strings(values: Sequence[Any], limit: int = 8) -> List[str]:
        ordered: List[str] = []
        for value in values or []:
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in ordered:
                ordered.append(text)
            if len(ordered) >= limit:
                break
        return ordered

    @staticmethod
    def _question_slice_ids(question_meta: Optional[Dict]) -> List[int]:
        ordered: List[int] = []
        for item in (question_meta or {}).get("selected_slices") or []:
            try:
                slice_id = int(item.get("slice_id"))
            except (TypeError, ValueError):
                continue
            if slice_id not in ordered:
                ordered.append(slice_id)
        for value in (question_meta or {}).get("used_slice_ids") or []:
            try:
                slice_id = int(value)
            except (TypeError, ValueError):
                continue
            if slice_id not in ordered:
                ordered.append(slice_id)
        return ordered

    @staticmethod
    def _extract_weakness_terms(
        current_question_meta: Dict,
        evaluation: Optional[Dict],
    ) -> List[str]:
        terms: List[str] = []
        if current_question_meta.get("evaluation_focus"):
            terms.extend(current_question_meta.get("evaluation_focus") or [])
        if current_question_meta.get("selected_followups"):
            terms.extend(current_question_meta.get("selected_followups") or [])
        if evaluation:
            terms.extend(evaluation.get("gaps") or [])
            terms.extend(evaluation.get("unresolved_gaps") or [])
            if evaluation.get("next_focus"):
                terms.append(evaluation.get("next_focus"))
            next_best_followup = evaluation.get("next_best_followup") or {}
            if isinstance(next_best_followup, dict):
                if next_best_followup.get("target_gap"):
                    terms.append(next_best_followup.get("target_gap"))
                terms.extend(next_best_followup.get("target_evidence") or [])
            for item in evaluation.get("panel_views") or []:
                if isinstance(item, dict) and item.get("summary"):
                    terms.append(item.get("summary"))
        return InterviewService._unique_strings(terms, limit=10)

    @staticmethod
    def _extract_followup_candidates(
        current_question_meta: Dict,
        evaluation: Optional[Dict],
    ) -> List[str]:
        ordered: List[str] = []

        def add_many(values):
            for value in values or []:
                if value is None:
                    continue
                text = str(value).strip()
                if text and text not in ordered:
                    ordered.append(text)

        moderator_evaluation = (evaluation or {}).get("moderator") or {}
        next_best_followup = (
            (evaluation or {}).get("next_best_followup")
            or moderator_evaluation.get("next_best_followup")
            or {}
        )
        if isinstance(next_best_followup, dict):
            add_many([next_best_followup.get("question")])
        add_many(moderator_evaluation.get("selected_followups") or [])
        add_many((evaluation or {}).get("selected_followups") or [])
        for item in (evaluation or {}).get("panel") or []:
            if isinstance(item, dict):
                add_many(item.get("followup_candidates") or [])
        add_many(current_question_meta.get("selected_followups") or [])
        return ordered[:5]

    @staticmethod
    def _apply_followup_to_next_question(
        current_question_meta: Dict,
        next_question_meta: Dict,
        evaluation: Optional[Dict],
    ) -> Dict:
        moderator_evaluation = (evaluation or {}).get("moderator") or {}
        next_best_followup = (
            (evaluation or {}).get("next_best_followup")
            or moderator_evaluation.get("next_best_followup")
            or {}
        )
        followups = InterviewService._extract_followup_candidates(current_question_meta, evaluation)
        if not followups:
            return next_question_meta

        followups_sanitized = False
        safe_followups = []
        for item in followups:
            followup = str(item or "").strip()
            if not followup:
                continue
            if InterviewService._question_has_internal_prompt_leak(followup):
                followups_sanitized = True
                continue
            safe_followups.append(followup)

        fallback_category = None
        if not safe_followups:
            try:
                fallback_index = int(
                    next_question_meta.get("index")
                    if next_question_meta.get("index") is not None
                    else (current_question_meta.get("index") or 0) + 1
                )
            except (TypeError, ValueError):
                fallback_index = 0
            fallback_category, fallback_question = InterviewService._safe_question_text_for_plan(
                index=fallback_index,
                plan=next_question_meta,
                position_label="目标岗位",
            )
            safe_followups = [fallback_question]
            followups_sanitized = True

        next_meta = dict(next_question_meta)
        next_meta["question"] = safe_followups[0]
        next_meta["stage"] = current_question_meta.get("stage") or next_meta.get("stage")
        next_meta["category"] = (
            current_question_meta.get("category") or next_meta.get("category") or fallback_category
        )
        next_meta["lead_role"] = current_question_meta.get("lead_role") or next_meta.get("lead_role")
        next_meta["support_roles"] = (
            current_question_meta.get("support_roles") or next_meta.get("support_roles") or []
        )
        next_meta["intent"] = (
            (evaluation or {}).get("next_focus")
            or current_question_meta.get("intent")
            or next_meta.get("intent")
        )
        next_meta["evaluation_focus"] = (
            (evaluation or {}).get("gaps")
            or current_question_meta.get("evaluation_focus")
            or next_meta.get("evaluation_focus")
            or []
        )
        next_meta["selected_followups"] = safe_followups[1:]
        next_meta["followup_source_question_index"] = current_question_meta.get("index")
        next_meta["is_dynamic_followup"] = True
        next_meta["blueprint_track"] = (
            current_question_meta.get("blueprint_track") or next_meta.get("blueprint_track")
        )
        next_meta["blueprint_requirement_status"] = (
            current_question_meta.get("blueprint_requirement_status")
            or next_meta.get("blueprint_requirement_status")
        )
        next_meta["blueprint_evidence_ids"] = (
            current_question_meta.get("blueprint_evidence_ids")
            or next_meta.get("blueprint_evidence_ids")
            or []
        )
        next_meta["blueprint_evidence_summary"] = InterviewService._unique_strings(
            [
                *(current_question_meta.get("blueprint_evidence_summary") or []),
                *(next_meta.get("blueprint_evidence_summary") or []),
            ],
            limit=4,
        )
        next_meta["blueprint_high_risk_claims"] = InterviewService._unique_strings(
            [
                *(current_question_meta.get("blueprint_high_risk_claims") or []),
                *(next_meta.get("blueprint_high_risk_claims") or []),
            ],
            limit=4,
        )
        if isinstance(next_best_followup, dict):
            allowed_evidence_ids = set(
                InterviewService._question_target_evidence_ids(current_question_meta)
                + InterviewService._question_target_evidence_ids(next_meta)
            )
            raw_followup_evidence_ids = []
            for value in next_best_followup.get("evidence_source_ids") or []:
                try:
                    evidence_id = int(value)
                except (TypeError, ValueError):
                    continue
                if evidence_id in allowed_evidence_ids:
                    raw_followup_evidence_ids.append(evidence_id)
            next_meta["question_target_gap"] = (
                str(next_best_followup.get("target_gap") or "").strip()
                or current_question_meta.get("question_target_gap")
                or next_meta.get("question_target_gap")
            )
            next_meta["question_target_evidence"] = InterviewService._unique_strings(
                [
                    *(next_best_followup.get("target_evidence") or []),
                    *(current_question_meta.get("question_target_evidence") or []),
                ],
                limit=4,
            )
            next_meta["question_target_evidence_ids"] = InterviewService._question_target_evidence_ids(
                {
                    **next_meta,
                    "question_target_evidence_ids": [
                        *raw_followup_evidence_ids,
                        *(current_question_meta.get("question_target_evidence_ids") or []),
                    ],
                }
            )
            next_meta["question_reason"] = (
                str(next_best_followup.get("reason") or "").strip()
                or current_question_meta.get("question_reason")
                or next_meta.get("question_reason")
            )

        panel_context = dict(current_question_meta.get("panel_context") or {})
        metadata = dict(panel_context.get("metadata") or {})
        if InterviewService._question_has_internal_prompt_leak(next_meta.get("question_target_gap")):
            next_meta["question_target_gap"] = None
            metadata["question_sanitized_reason"] = "internal_prompt_leak"
            metadata["question_target_gap_redacted"] = True
        if InterviewService._question_has_internal_prompt_leak(next_meta.get("question_reason")):
            next_meta["question_reason"] = None
            metadata["question_sanitized_reason"] = "internal_prompt_leak"
            metadata["question_reason_redacted"] = True
        if followups_sanitized:
            metadata["question_sanitized_reason"] = "internal_prompt_leak"
            metadata["original_question_redacted"] = True
            metadata["selected_followups_redacted"] = True
        if metadata:
            panel_context["metadata"] = metadata

        moderator = dict(panel_context.get("moderator") or {})
        moderator["selected_question"] = safe_followups[0]
        moderator["selected_followups"] = safe_followups[1:]
        if isinstance(next_best_followup, dict) and next_best_followup:
            safe_next_best_followup = dict(next_best_followup)
            if InterviewService._question_has_internal_prompt_leak(
                safe_next_best_followup.get("question")
            ):
                safe_next_best_followup["question"] = safe_followups[0]
                metadata["question_sanitized_reason"] = "internal_prompt_leak"
                metadata["original_question_redacted"] = True
                panel_context["metadata"] = metadata
            moderator["next_best_followup"] = safe_next_best_followup
        if (evaluation or {}).get("moderator", {}).get("reasoning_summary"):
            moderator["reasoning_summary"] = evaluation["moderator"]["reasoning_summary"]
        if (evaluation or {}).get("moderator", {}).get("difficulty_hint"):
            moderator["difficulty_hint"] = evaluation["moderator"]["difficulty_hint"]
        if moderator:
            panel_context["moderator"] = moderator
            next_meta["panel_context"] = panel_context

        next_meta.update(InterviewService._derive_question_target_fields(next_meta))
        next_meta = InterviewService._sanitize_question_public_fields(next_meta)
        return next_meta

    @staticmethod
    def _reroute_question_slices(
        question_meta: Dict,
        knowledge_base: Optional[Dict],
        parsed_resume: Dict,
        target_position: str,
        difficulty: str,
        context_terms: Optional[Sequence[str]] = None,
    ) -> Dict:
        if not knowledge_base or not (knowledge_base.get("slices") or []):
            return question_meta

        resume_text = InterviewService._resume_route_text(parsed_resume)
        resume_skills = InterviewService._route_values_to_texts(parsed_resume.get("skills"), 12)
        resume_projects = InterviewService._route_values_to_texts(parsed_resume.get("projects"), 6)
        routing_difficulty = (
            question_meta.get("routing_difficulty")
            or InterviewService._difficulty_profile(difficulty)["routing_difficulty"]
        )
        try:
            routing_top_k = int(question_meta.get("routing_top_k") or 2)
        except (TypeError, ValueError):
            routing_top_k = 2
        query_parts = [
            target_position,
            resume_text,
            question_meta.get("question") or "",
            question_meta.get("intent") or "",
            question_meta.get("difficulty_guidance") or "",
            " ".join(question_meta.get("evaluation_focus") or []),
            " ".join(context_terms or []),
        ]
        try:
            selected = position_knowledge_base_slice_service.rank_slices(
                slices=knowledge_base.get("slices") or [],
                query_text="\n".join(part for part in query_parts if part),
                stage=question_meta.get("stage"),
                role=question_meta.get("lead_role"),
                scene=question_meta.get("category") or question_meta.get("stage"),
                difficulty=routing_difficulty,
                skills=resume_skills[:8],
                topics=[target_position, *(resume_projects[:2])],
                weakness_terms=context_terms or [],
                top_k=max(2, min(routing_top_k, 4)),
            )
        except Exception as exc:
            logger.warning("Question slice reroute failed for question index=%s: %s", question_meta.get("index"), exc)
            return question_meta

        if not selected:
            return question_meta

        next_meta = dict(question_meta)
        next_meta["selected_slices"] = [
            InterviewService._compact_slice(slice_item) for slice_item in selected
        ]
        next_meta["used_slice_ids"] = [
            item.get("slice_id") for item in next_meta["selected_slices"] if item.get("slice_id")
        ]
        next_meta["evidence_trace"] = InterviewService._build_evidence_trace(
            next_meta["selected_slices"],
            used_slice_ids=next_meta["used_slice_ids"],
        )
        next_meta["evidence_summary"] = InterviewService._build_evidence_summary(
            next_meta["selected_slices"],
            used_slice_ids=next_meta["used_slice_ids"],
        )
        panel_context = dict(next_meta.get("panel_context") or {})
        metadata = dict(panel_context.get("metadata") or {})
        metadata["retrieved_slice_ids"] = next_meta["used_slice_ids"]
        metadata["grounding_confidence_summary"] = InterviewService._grounding_confidence_summary(
            next_meta["selected_slices"]
        )
        if metadata:
            panel_context["metadata"] = metadata
            next_meta["panel_context"] = panel_context
        next_meta.update(InterviewService._derive_question_target_fields(next_meta))
        return InterviewService._sanitize_question_public_fields(next_meta)

    @staticmethod
    def _is_recoverable_evaluation_error(exc: Exception) -> bool:
        return isinstance(exc, (json.JSONDecodeError, ValueError, asyncio.TimeoutError)) and not isinstance(exc, ValidationError)

    @staticmethod
    async def _await_answer_evaluation(coro):
        return await asyncio.wait_for(coro, timeout=ANSWER_EVALUATION_TIMEOUT_SECONDS)

    @staticmethod
    def _evaluation_fallback_reason(exc: Exception, default: str = "answer_evaluation_json_malformed") -> str:
        if isinstance(exc, asyncio.TimeoutError):
            return "answer_evaluation_timeout"
        return default

    @staticmethod
    def _build_deterministic_answer_evaluation_fallback(
        *,
        question: str,
        answer: str,
        question_meta: Optional[Dict[str, Any]],
        reason: str,
        exc: Exception,
    ) -> Dict[str, Any]:
        answer_text = str(answer or "").strip()
        target_gap = str((question_meta or {}).get("question_target_gap") or "").strip()
        target_evidence = InterviewService._unique_strings(
            (question_meta or {}).get("question_target_evidence") or [],
            limit=4,
        )
        base_score = 5.0
        if len(answer_text) >= 260:
            base_score += 0.8
        elif len(answer_text) >= 100:
            base_score += 0.4
        elif len(answer_text) < 30:
            base_score -= 0.6
        if re.search(r"(我|本人|主导|负责|设计|实现|优化|排查|上线|复盘|指标|结果|用户|性能)", answer_text):
            base_score += 0.4
        score = round(max(4.0, min(base_score, 6.5)), 1)
        followup_question = "请继续补充一个具体例子，按背景、你的职责、采取的行动、最终结果和复盘改进展开。"
        if target_gap:
            followup_question = f"围绕“{target_gap}”，请补充一个具体例子，说明你的职责、行动、结果和复盘。"
        feedback = (
            "本轮回答已记录。AI 结构化评分暂不可用，系统已使用保守兜底评分；"
            "建议继续补充背景、个人职责、行动过程、结果指标和复盘改进。"
        )
        return {
            "score": score,
            "feedback": feedback,
            "follow_up": True,
            "strengths": ["回答已完成记录，可继续进入下一题。"],
            "gaps": [target_gap or "仍需补充更具体的职责、行动和结果证据。"],
            "unresolved_gaps": [target_gap or "具体职责、行动过程、结果指标仍需进一步验证。"],
            "next_focus": target_gap or "补充可验证项目证据",
            "selected_followups": [followup_question],
            "evidence_strength_delta": [],
            "claim_confidence_change": [],
            "next_best_followup": {
                "question": followup_question,
                "reason": "结构化评分兜底后，优先追问可验证事实链。",
                "target_gap": target_gap or "可验证项目证据",
                "target_evidence": target_evidence,
                "evidence_source_ids": (question_meta or {}).get("question_target_evidence_ids") or [],
                "evidence_source_summary": target_evidence,
            },
            "metadata": {
                "evaluation_fallback": True,
                "fallback_reason": reason,
                "parser_error_class": exc.__class__.__name__,
                "question_preview_hash": sha256(str(question or "").encode("utf-8")).hexdigest()[:12],
            },
        }

    @staticmethod
    async def _evaluate_round(
        interview_mode: str,
        question: str,
        answer: str,
        resume_context: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
        knowledge_base: Optional[Dict[str, Any]],
        question_meta: Dict[str, Any],
        panel_snapshot: Optional[Dict[str, Any]],
        ai_config: Optional[Dict[str, Any]],
    ) -> tuple[str, Dict[str, Any]]:
        evaluation_mode = interview_mode
        try:
            if interview_mode == "panel":
                evaluation = await InterviewService._await_answer_evaluation(
                    AIService.evaluate_answer_with_panel(
                        question=question,
                        answer=answer,
                        resume_context=resume_context,
                        chat_history=chat_history,
                        knowledge_base=knowledge_base,
                        question_meta=question_meta,
                        panel_snapshot=panel_snapshot,
                        ai_config=ai_config,
                    )
                )
            else:
                evaluation = await InterviewService._await_answer_evaluation(
                    AIService.evaluate_answer(
                        question=question,
                        answer=answer,
                        resume_context=resume_context,
                        chat_history=chat_history,
                        knowledge_base=knowledge_base,
                        question_meta=question_meta,
                        ai_config=ai_config,
                    )
                )
        except Exception as exc:
            if not InterviewService._is_recoverable_evaluation_error(exc):
                raise
            if interview_mode != "panel":
                logger.warning("Single evaluation JSON failed, using deterministic fallback: %s", exc)
                return "deterministic_fallback", InterviewService._build_deterministic_answer_evaluation_fallback(
                    question=question,
                    answer=answer,
                    question_meta=question_meta,
                    reason=InterviewService._evaluation_fallback_reason(exc),
                    exc=exc,
                )
            logger.warning("Panel evaluation JSON failed, fallback to single mode: %s", exc)
            try:
                evaluation_mode = "single_fallback"
                evaluation = await InterviewService._await_answer_evaluation(
                    AIService.evaluate_answer(
                        question=question,
                        answer=answer,
                        resume_context=resume_context,
                        chat_history=chat_history,
                        knowledge_base=knowledge_base,
                        question_meta=question_meta,
                        ai_config=ai_config,
                    )
                )
            except Exception as single_exc:
                if not InterviewService._is_recoverable_evaluation_error(single_exc):
                    raise
                logger.warning("Single fallback evaluation JSON failed, using deterministic fallback: %s", single_exc)
                evaluation_mode = "deterministic_fallback"
                evaluation = InterviewService._build_deterministic_answer_evaluation_fallback(
                    question=question,
                    answer=answer,
                    question_meta=question_meta,
                    reason=InterviewService._evaluation_fallback_reason(
                        single_exc,
                        default="panel_and_single_evaluation_json_malformed",
                    ),
                    exc=single_exc,
                )
        return evaluation_mode, evaluation

    @staticmethod
    def _build_report_signals(questions: List[Dict]) -> Dict:
        gap_counter: Counter = Counter()
        strength_counter: Counter = Counter()
        slice_ids: List[int] = []
        training_priorities: List[str] = []
        panel_notes: Dict[str, List[str]] = {}
        evidence_summary: List[str] = []
        followup_loop_summary: List[str] = []
        claim_confidence_summary: List[str] = []
        grounding_counts: Counter = Counter()
        grounding_warnings: List[str] = []
        low_confidence_slice_ids: List[int] = []
        evidence_question_count = 0

        for question in questions:
            evaluation = question.get("evaluation") or {}
            unresolved_gaps = InterviewService._unique_strings(
                [
                    *(evaluation.get("unresolved_gaps") or []),
                    *(evaluation.get("gaps") or []),
                ],
                limit=5,
            )
            for item in unresolved_gaps:
                text = str(item).strip()
                if text:
                    gap_counter[text] += 1
            for item in evaluation.get("strengths") or []:
                text = str(item).strip()
                if text:
                    strength_counter[text] += 1
            for item in evaluation.get("evidence_strength_delta") or []:
                if not isinstance(item, dict):
                    continue
                evidence_text = str(item.get("evidence") or "").strip()
                delta = str(item.get("delta") or "").strip()
                reason = str(item.get("reason") or "").strip()
                if evidence_text and delta in {"strengthened", "increased"}:
                    strength_counter[evidence_text] += 1
                elif evidence_text and delta in {"weakened", "insufficient"}:
                    gap_counter[evidence_text] += 1
                if evidence_text:
                    summary_text = f"{evidence_text}：{delta or 'unchanged'}"
                    if reason:
                        summary_text = f"{summary_text}（{reason}）"
                    if summary_text not in followup_loop_summary:
                        followup_loop_summary.append(summary_text)
            for item in evaluation.get("claim_confidence_change") or []:
                if not isinstance(item, dict):
                    continue
                claim = str(item.get("claim") or "").strip()
                if not claim:
                    continue
                if (
                    AIService._is_role_reference_text(
                        item.get("source"),
                        claim,
                        item.get("reason"),
                    )
                    or (
                        bool(item.get("role_requirement_source_ids"))
                        and not bool(item.get("evidence_ids"))
                    )
                ):
                    continue
                before_level = str(item.get("from_level") or "").strip()
                after_level = str(item.get("to_level") or "").strip()
                reason = str(item.get("reason") or "").strip()
                summary_text = f"“{claim}”置信度 {before_level or '-'} -> {after_level or '-'}"
                if reason:
                    summary_text = f"{summary_text}（{reason}）"
                if summary_text not in claim_confidence_summary:
                    claim_confidence_summary.append(summary_text)
            next_focus = str(evaluation.get("next_focus") or "").strip()
            if next_focus:
                training_priorities.append(next_focus)
            next_best_followup = evaluation.get("next_best_followup") or {}
            if isinstance(next_best_followup, dict):
                if next_best_followup.get("target_gap"):
                    training_priorities.append(str(next_best_followup.get("target_gap")).strip())
                followup_reason = str(next_best_followup.get("reason") or "").strip()
                followup_question = str(next_best_followup.get("question") or "").strip()
                if followup_question:
                    summary_text = f"建议继续追问：{followup_question}"
                    if followup_reason:
                        summary_text = f"{summary_text}（{followup_reason}）"
                    if summary_text not in followup_loop_summary:
                        followup_loop_summary.append(summary_text)

            for value in question.get("used_slice_ids") or []:
                try:
                    slice_id = int(value)
                except (TypeError, ValueError):
                    continue
                if slice_id not in slice_ids:
                    slice_ids.append(slice_id)

            question_evidence_summary = InterviewService._unique_strings(
                question.get("evidence_summary") or [],
                limit=3,
            )
            if question_evidence_summary:
                evidence_question_count += 1
                for item in question_evidence_summary:
                    if item not in evidence_summary:
                        evidence_summary.append(item)
            grounding_summary = InterviewService._grounding_confidence_summary(
                question.get("selected_slices") or []
            )
            for level, count in (grounding_summary.get("counts") or {}).items():
                if count:
                    grounding_counts[level] += count
            for warning in grounding_summary.get("warnings") or []:
                if warning not in grounding_warnings:
                    grounding_warnings.append(warning)
            for slice_id in grounding_summary.get("low_confidence_slice_ids") or []:
                if slice_id not in low_confidence_slice_ids:
                    low_confidence_slice_ids.append(slice_id)

            for item in evaluation.get("panel_views") or []:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "").strip()
                summary = str(item.get("summary") or "").strip()
                if role and summary:
                    panel_notes.setdefault(role, []).append(summary)

        panel_summary = []
        for role, summaries in panel_notes.items():
            panel_summary.append(
                {
                    "role": role,
                    "title": PANEL_ROLE_TITLES.get(role, role),
                    "summary": " ".join(InterviewService._unique_strings(summaries, limit=3)),
                }
            )

        return {
            "common_gaps": [item for item, _ in gap_counter.most_common(5)],
            "common_strengths": [item for item, _ in strength_counter.most_common(5)],
            "training_priorities": InterviewService._unique_strings(
                [*training_priorities, *[item for item, _ in gap_counter.most_common(3)]],
                limit=5,
            ),
            "panel_summary": panel_summary,
            "retrieved_slice_ids": slice_ids,
            "evidence_summary": evidence_summary[:6],
            "followup_loop_summary": followup_loop_summary[:6],
            "claim_confidence_summary": claim_confidence_summary[:6],
            "grounding_confidence_summary": {
                "counts": dict(grounding_counts),
                "warnings": grounding_warnings[:6],
                "low_confidence_slice_ids": low_confidence_slice_ids[:6],
            },
            "evidence_stats": {
                "questions_with_evidence": evidence_question_count,
                "total_questions": len(questions),
                "retrieved_slice_count": len(slice_ids),
            },
        }

    @staticmethod
    def _merge_report_defaults(
        report: Dict,
        report_signals: Dict,
        interview_mode: str,
    ) -> Dict:
        diagnostics: List[Dict[str, Any]] = []
        if isinstance(report, dict):
            merged = dict(report or {})
        else:
            logger.warning("Report payload is not an object: %s", type(report).__name__)
            merged = InterviewService._fallback_report_from_signals(
                report_signals=report_signals,
                reason="invalid_report_payload_type",
                detail=f"报告生成返回 {type(report).__name__}，已使用面试记录生成基础报告。",
            )
            diagnostics.extend(merged.pop("report_diagnostics", []))
        if not merged.get("weaknesses") and report_signals.get("common_gaps"):
            merged["weaknesses"] = report_signals["common_gaps"]
        if not merged.get("strengths") and report_signals.get("common_strengths"):
            merged["strengths"] = report_signals["common_strengths"]
        if not merged.get("training_priorities") and report_signals.get("training_priorities"):
            merged["training_priorities"] = report_signals["training_priorities"]
        if not merged.get("common_gaps") and report_signals.get("common_gaps"):
            merged["common_gaps"] = report_signals["common_gaps"]
        if not merged.get("common_strengths") and report_signals.get("common_strengths"):
            merged["common_strengths"] = report_signals["common_strengths"]
        if interview_mode == "panel" and not merged.get("panel_summary") and report_signals.get("panel_summary"):
            merged["panel_summary"] = report_signals["panel_summary"]
        if not merged.get("evidence_summary") and report_signals.get("evidence_summary"):
            merged["evidence_summary"] = report_signals["evidence_summary"]
        if not merged.get("followup_loop_summary") and report_signals.get("followup_loop_summary"):
            merged["followup_loop_summary"] = report_signals["followup_loop_summary"]
        if not merged.get("claim_confidence_summary") and report_signals.get("claim_confidence_summary"):
            merged["claim_confidence_summary"] = report_signals["claim_confidence_summary"]
        if not merged.get("grounding_confidence_summary") and report_signals.get("grounding_confidence_summary"):
            merged["grounding_confidence_summary"] = report_signals["grounding_confidence_summary"]
        if not merged.get("evidence_stats") and report_signals.get("evidence_stats"):
            merged["evidence_stats"] = report_signals["evidence_stats"]
        if diagnostics:
            merged["report_diagnostics"] = [
                *(merged.get("report_diagnostics") or []),
                *diagnostics,
            ]
        return merged

    @staticmethod
    def _fallback_report_from_signals(
        report_signals: Optional[Dict],
        reason: str,
        detail: str = "",
    ) -> Dict[str, Any]:
        signals = report_signals or {}
        common_gaps = signals.get("common_gaps") or []
        common_strengths = signals.get("common_strengths") or []
        training_priorities = signals.get("training_priorities") or []
        evidence_summary = signals.get("evidence_summary") or []
        return {
            "summary": "报告生成服务返回异常，系统已基于本次面试记录、评分和证据信号生成基础报告。",
            "strengths": common_strengths[:6],
            "weaknesses": common_gaps[:6],
            "suggestions": (training_priorities or common_gaps or ["围绕本次面试暴露的薄弱点继续补充可验证案例。"])[:6],
            "hire_recommendation": "建议结合人工复核和后续训练结果再判断。",
            "training_priorities": training_priorities[:6],
            "common_gaps": common_gaps[:6],
            "common_strengths": common_strengths[:6],
            "evidence_summary": evidence_summary[:6],
            "followup_loop_summary": signals.get("followup_loop_summary") or [],
            "claim_confidence_summary": signals.get("claim_confidence_summary") or [],
            "grounding_confidence_summary": signals.get("grounding_confidence_summary") or {},
            "evidence_stats": signals.get("evidence_stats") or {},
            "report_diagnostics": [
                {
                    "reason": reason,
                    "detail": detail or "报告生成异常，已启用基础报告兜底。",
                }
            ],
        }

    @staticmethod
    def _json_dict_from_text(value: Optional[str]) -> Dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            return str(value)

    @staticmethod
    def _redact_direct_identifiers(text: str) -> tuple[str, int]:
        redacted = text
        total = 0
        for pattern, replacement in DIRECT_IDENTIFIER_REPLACEMENTS:
            redacted, count = pattern.subn(replacement, redacted)
            total += count
        return redacted, total

    @staticmethod
    def _sanitize_export_payload(
        value: Any,
        *,
        preserve_user_email: bool = False,
        path: tuple[str, ...] = (),
    ) -> tuple[Any, int]:
        if isinstance(value, dict):
            clean: Dict[str, Any] = {}
            total = 0
            for key, item in value.items():
                next_path = (*path, str(key))
                if preserve_user_email and next_path == ("interview", "user_email"):
                    clean[key] = item
                    continue
                clean_item, count = InterviewService._sanitize_export_payload(
                    item,
                    preserve_user_email=preserve_user_email,
                    path=next_path,
                )
                clean[key] = clean_item
                total += count
            return clean, total
        if isinstance(value, list):
            clean_items = []
            total = 0
            for index, item in enumerate(value):
                clean_item, count = InterviewService._sanitize_export_payload(
                    item,
                    preserve_user_email=preserve_user_email,
                    path=(*path, str(index)),
                )
                clean_items.append(clean_item)
                total += count
            return clean_items, total
        if isinstance(value, str):
            return InterviewService._redact_direct_identifiers(value)
        return value, 0

    @staticmethod
    def _assert_no_direct_identifier(
        value: Any,
        *,
        preserve_user_email: bool = False,
        path: tuple[str, ...] = (),
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                InterviewService._assert_no_direct_identifier(
                    item,
                    preserve_user_email=preserve_user_email,
                    path=(*path, str(key)),
                )
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                InterviewService._assert_no_direct_identifier(
                    item,
                    preserve_user_email=preserve_user_email,
                    path=(*path, str(index)),
                )
            return
        if not isinstance(value, str):
            return
        if preserve_user_email and path == ("interview", "user_email"):
            return
        scan_value = re.sub(r"\[REDACTED(?:_[A-Z]+)?\]", "", value)
        _, redaction_count = InterviewService._redact_direct_identifiers(scan_value)
        if redaction_count:
            location = ".".join(path) or "<root>"
            raise ValueError(f"Export payload contains direct personal identifier at {location}")

    @staticmethod
    def _sanitize_export_files(files: Dict[str, str]) -> Dict[str, str]:
        sanitized_files: Dict[str, str] = {}
        for filename, content in (files or {}).items():
            clean_content, _ = InterviewService._redact_direct_identifiers(content or "")
            _, remaining = InterviewService._redact_direct_identifiers(clean_content)
            if remaining:
                raise ValueError(f"Export file still contains direct personal identifier: {filename}")
            sanitized_files[filename] = clean_content
        return sanitized_files

    @staticmethod
    def _is_reviewed_training_sample(sample: Dict[str, Any]) -> bool:
        review = sample.get("training_sample_review") or {}
        return review.get("review_status") == "reviewed"

    @staticmethod
    def _sample_boundary_from_snapshot(
        snapshot: Any,
        *,
        data_contribution_consent: bool = False,
    ) -> Dict[str, Any]:
        raw = snapshot if isinstance(snapshot, dict) else {}
        sample_origin = str(raw.get("sample_origin") or "").strip()
        candidate_answer_source = str(raw.get("candidate_answer_source") or "").strip()
        for_real_sft = raw.get("for_real_sft")
        is_admin_override = bool(raw.get("admin_override")) and raw.get("source") == "admin_case_consent_override"

        if (
            (sample_origin and sample_origin != "real_authorized")
            or (candidate_answer_source and candidate_answer_source != "human")
            or for_real_sft is False
        ):
            return {
                "sample_origin": sample_origin or "not_real_authorized",
                "candidate_answer_source": candidate_answer_source or "unknown",
                "for_real_sft": False,
                "for_training": False,
                "for_competition_demo": bool(raw.get("for_competition_demo", True)),
                "claim_boundary": raw.get("claim_boundary")
                or "半合成样本只用于流程压测、演示和 SFT Preview，不能进入真实 SFT。",
            }

        if data_contribution_consent or is_admin_override:
            return {
                "sample_origin": "real_authorized",
                "candidate_answer_source": candidate_answer_source or "human",
                "for_real_sft": True,
                "for_training": True,
                "for_competition_demo": bool(raw.get("for_competition_demo", False)),
                "claim_boundary": raw.get("claim_boundary") or "真实授权样本，仍需人工复核和 PII 扫描后才能进入 SFT。",
            }

        return {
            "sample_origin": sample_origin or "not_authorized",
            "candidate_answer_source": candidate_answer_source or "unknown",
            "for_real_sft": False,
            "for_training": False,
            "for_competition_demo": bool(raw.get("for_competition_demo", False)),
            "claim_boundary": raw.get("claim_boundary") or "未获得数据贡献授权，不能进入训练/评测样本。",
        }

    @staticmethod
    def _is_real_sft_boundary(boundary: Any) -> bool:
        item = boundary if isinstance(boundary, dict) else {}
        return bool(
            item.get("sample_origin") == "real_authorized"
            and item.get("candidate_answer_source") == "human"
            and item.get("for_real_sft") is True
            and item.get("for_training") is True
        )

    @staticmethod
    def _sample_boundary_from_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
        interview = sample.get("interview") or {}
        export_notes = sample.get("export_notes") or {}
        existing = sample.get("sample_boundary") or export_notes.get("sample_boundary")
        if isinstance(existing, dict) and existing:
            return existing
        return InterviewService._sample_boundary_from_snapshot(
            export_notes.get("privacy_consent_snapshot"),
            data_contribution_consent=bool(
                interview.get("data_contribution_consent")
                or export_notes.get("data_contribution_consent")
            ),
        )

    @staticmethod
    def _is_export_ready_training_sample(sample: Dict[str, Any]) -> bool:
        interview = sample.get("interview") or {}
        export_notes = sample.get("export_notes") or {}
        sample_boundary = InterviewService._sample_boundary_from_sample(sample)
        return bool(
            interview.get("status") == "completed"
            and (
                interview.get("data_contribution_consent")
                or export_notes.get("data_contribution_consent")
            )
            and InterviewService._is_real_sft_boundary(sample_boundary)
            and InterviewService._is_reviewed_training_sample(sample)
        )

    @staticmethod
    def is_export_ready_training_sample(sample: Dict[str, Any]) -> bool:
        return InterviewService._is_export_ready_training_sample(sample)

    @staticmethod
    def _normalize_training_sample_review(review: Any) -> Dict[str, Any]:
        raw = review if isinstance(review, dict) else {}
        quality_tier = str(raw.get("quality_tier") or "needs_review").strip().lower()
        if quality_tier not in TRAINING_SAMPLE_QUALITY_TIERS:
            quality_tier = "needs_review"

        notes = str(raw.get("notes") or "").strip()
        if len(notes) > 2000:
            notes = notes[:2000]
        human_score_notes = str(raw.get("human_score_notes") or "").strip()
        if len(human_score_notes) > 2000:
            human_score_notes = human_score_notes[:2000]

        dataset_split = str(raw.get("dataset_split") or "").strip().lower()
        if dataset_split not in TRAINING_SAMPLE_DATASET_SPLITS:
            dataset_split = ""

        def clean_text(key: str, limit: int) -> str:
            value = str(raw.get(key) or "").strip()
            return value[:limit] if len(value) > limit else value

        def clean_score(key: str) -> Optional[float]:
            value = raw.get(key)
            if value in (None, ""):
                return None
            try:
                score = float(value)
            except (TypeError, ValueError):
                return None
            return max(0.0, min(10.0, round(score, 1)))

        normalized = {
            "quality_tier": quality_tier,
            "is_high_quality": bool(raw.get("is_high_quality")),
            "has_hallucination": bool(raw.get("has_hallucination")),
            "followup_worthy": bool(raw.get("followup_worthy")),
            "report_actionable": bool(raw.get("report_actionable")),
            "notes": notes,
            "case_id": clean_text("case_id", 64),
            "resume_source": clean_text("resume_source", 255),
            "human_overall_score": clean_score("human_overall_score"),
            "evidence_alignment_score": clean_score("evidence_alignment_score"),
            "question_quality_score": clean_score("question_quality_score"),
            "report_actionability_score": clean_score("report_actionability_score"),
            "learning_task_actionability_score": clean_score("learning_task_actionability_score"),
            "human_score_notes": human_score_notes,
            "dataset_split": dataset_split,
            "reviewed_at": raw.get("reviewed_at"),
            "reviewer_email": raw.get("reviewer_email"),
        }
        normalized["review_status"] = "reviewed" if normalized.get("reviewed_at") else "pending"
        normalized["export_recommended"] = bool(
            normalized["is_high_quality"] and not normalized["has_hallucination"]
        )
        return normalized

    @staticmethod
    def get_training_sample_review(panel_snapshot: Any) -> Dict[str, Any]:
        snapshot = panel_snapshot if isinstance(panel_snapshot, dict) else {}
        return InterviewService._normalize_training_sample_review(snapshot.get("training_sample_review") or {})

    @staticmethod
    async def update_training_sample_review(
        db: AsyncSession,
        interview_id: int,
        review_data: Dict[str, Any],
        reviewer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        interview = await db.get(Interview, interview_id)
        if not interview:
            raise NotFoundError(message="面试记录不存在")
        if not getattr(interview, "data_contribution_consent", False):
            raise ValidationError(message="该面试未获得去标识化数据贡献授权，不能进入人工评分沉淀流程")
        sample_boundary = InterviewService._sample_boundary_from_snapshot(
            getattr(interview, "privacy_consent_snapshot", None),
            data_contribution_consent=bool(getattr(interview, "data_contribution_consent", False)),
        )
        if not InterviewService._is_real_sft_boundary(sample_boundary):
            raise ValidationError(message="该案例不是真实授权训练样本，不能进入人工评分沉淀流程")
        if getattr(interview, "status", None) != "completed":
            raise ValidationError(message="该面试尚未完成，不能保存人工评分")

        panel_snapshot = interview.panel_snapshot if isinstance(interview.panel_snapshot, dict) else {}
        next_review = InterviewService._normalize_training_sample_review(review_data)
        next_review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        next_review["reviewer_email"] = reviewer_email or next_review.get("reviewer_email")
        next_review["review_status"] = "reviewed"
        next_review["export_recommended"] = bool(
            next_review["is_high_quality"] and not next_review["has_hallucination"]
        )

        interview.panel_snapshot = {
            **panel_snapshot,
            "training_sample_review": next_review,
        }
        await db.commit()
        await db.refresh(interview)
        return next_review

    @staticmethod
    def build_training_sample(
        interview: Interview,
        messages: Optional[Sequence[InterviewMessage]] = None,
        user_email: Optional[str] = None,
        include_user_email: bool = False,
    ) -> Dict[str, Any]:
        questions = InterviewService._serialize_questions(interview.questions_data or [])
        report = InterviewService._json_dict_from_text(interview.report)
        panel_snapshot = interview.panel_snapshot if isinstance(interview.panel_snapshot, dict) else {}
        knowledge_base_snapshot = (
            interview.knowledge_base_snapshot
            if isinstance(interview.knowledge_base_snapshot, dict)
            else {}
        )
        interview_blueprint = panel_snapshot.get("interview_blueprint") or {}
        training_sample_review = InterviewService.get_training_sample_review(panel_snapshot)
        answer_by_index: Dict[int, InterviewMessage] = {}
        for item in messages or []:
            if item.role == "candidate" and item.question_index is not None:
                answer_by_index[int(item.question_index)] = item

        rounds = []
        retrieved_slice_ids: List[int] = []
        for index, question in enumerate(questions):
            question_index = int(question.get("index") if question.get("index") is not None else index)
            message = answer_by_index.get(question_index)
            evaluation = question.get("evaluation") or {}
            used_slice_ids = []
            for value in question.get("used_slice_ids") or []:
                try:
                    slice_id = int(value)
                except (TypeError, ValueError):
                    continue
                used_slice_ids.append(slice_id)
                if slice_id not in retrieved_slice_ids:
                    retrieved_slice_ids.append(slice_id)
            round_score = question.get("score")
            if round_score is None and message and message.score is not None:
                round_score = float(message.score)

            answer = question.get("answer") or (message.content if message else "")
            feedback = question.get("feedback") or (message.feedback if message else "")
            round_item = {
                "question_index": question_index,
                "question": question.get("question"),
                "answer": answer,
                "score": float(round_score) if round_score is not None else None,
                "feedback": feedback or "",
                "category": question.get("category"),
                "stage": question.get("stage"),
                "lead_role": question.get("lead_role"),
                "interview_mode": question.get("interview_mode") or interview.interview_mode,
                "question_target_gap": question.get("question_target_gap"),
                "question_target_evidence": question.get("question_target_evidence") or [],
                "question_target_evidence_ids": question.get("question_target_evidence_ids") or [],
                "question_reason": question.get("question_reason"),
                "used_slice_ids": used_slice_ids,
                "evidence_trace": question.get("evidence_trace") or [],
                "evidence_summary": question.get("evidence_summary") or [],
                "blueprint_track": question.get("blueprint_track"),
                "blueprint_requirement_status": question.get("blueprint_requirement_status"),
                "selected_followups": question.get("selected_followups") or [],
                "evaluation": {
                    "strengths": evaluation.get("strengths") or [],
                    "gaps": evaluation.get("gaps") or [],
                    "unresolved_gaps": evaluation.get("unresolved_gaps") or [],
                    "evidence_strength_delta": evaluation.get("evidence_strength_delta") or [],
                    "claim_confidence_change": evaluation.get("claim_confidence_change") or [],
                    "next_best_followup": evaluation.get("next_best_followup"),
                    "panel_views": evaluation.get("panel_views") or [],
                    "evaluation_mode": evaluation.get("evaluation_mode"),
                },
                "sample_flags": {
                    "has_answer": bool((answer or "").strip()),
                    "has_evidence": bool(question.get("evidence_trace") or question.get("evidence_summary")),
                    "has_followup_loop": bool(
                        evaluation.get("next_best_followup")
                        or evaluation.get("evidence_strength_delta")
                        or evaluation.get("claim_confidence_change")
                    ),
                    "high_score_candidate": bool(round_score is not None and float(round_score) >= 8),
                },
            }
            rounds.append(round_item)

        report_summary = {
            "overall_score": float(interview.overall_score) if interview.overall_score is not None else None,
            "common_gaps": report.get("common_gaps") or [],
            "common_strengths": report.get("common_strengths") or [],
            "training_priorities": report.get("training_priorities") or [],
            "followup_loop_summary": report.get("followup_loop_summary") or [],
            "claim_confidence_summary": report.get("claim_confidence_summary") or [],
            "evidence_summary": report.get("evidence_summary") or [],
        }
        interview_meta = {
            "id": interview.id,
            "target_position": interview.target_position,
            "difficulty": interview.difficulty,
            "interview_mode": interview.interview_mode,
            "status": interview.status,
            "total_questions": interview.total_questions,
            "overall_score": float(interview.overall_score) if interview.overall_score is not None else None,
            "data_contribution_consent": bool(
                getattr(interview, "data_contribution_consent", False)
            ),
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
        }
        sample_boundary = InterviewService._sample_boundary_from_snapshot(
            getattr(interview, "privacy_consent_snapshot", None),
            data_contribution_consent=bool(getattr(interview, "data_contribution_consent", False)),
        )
        if include_user_email and user_email:
            interview_meta["user_email"] = user_email

        sample = {
            "sample_version": "ai-interview.training-sample.v1",
            "sample_boundary": sample_boundary,
            "interview": interview_meta,
            "evidence_context": {
                "knowledge_base_id": interview.knowledge_base_id,
                "knowledge_base_title": knowledge_base_snapshot.get("title"),
                "interview_blueprint": interview_blueprint,
                "retrieved_slice_ids": retrieved_slice_ids,
                "blueprint_evidence_summary": (interview_blueprint.get("evidence_summary") or [])[:6]
                if isinstance(interview_blueprint, dict)
                else [],
            },
            "rounds": rounds,
            "report_summary": report_summary,
            "training_sample_review": training_sample_review,
            "export_notes": {
                "pii_included": bool(include_user_email and user_email),
                "data_contribution_consent": bool(
                    getattr(interview, "data_contribution_consent", False)
                ),
                "privacy_consent_snapshot": getattr(
                    interview,
                    "privacy_consent_snapshot",
                    None,
                ),
                "sample_boundary": sample_boundary,
                "review_status": training_sample_review.get("review_status"),
                "export_recommended": training_sample_review.get("export_recommended"),
                "intended_use": "offline review, hallucination analysis, follow-up quality review, and future fine-tuning preparation",
            },
        }
        safe_sample = json.loads(json.dumps(sample, ensure_ascii=False, default=InterviewService._json_safe))
        safe_sample, redaction_count = InterviewService._sanitize_export_payload(
            safe_sample,
            preserve_user_email=bool(include_user_email and user_email),
        )
        safe_sample["export_notes"]["pii_redaction"] = {
            "applied": True,
            "redacted": redaction_count > 0,
            "redaction_count": redaction_count,
        }
        InterviewService._assert_no_direct_identifier(
            safe_sample,
            preserve_user_email=bool(include_user_email and user_email),
        )
        return safe_sample

    @staticmethod
    async def get_completed_training_samples(
        db: AsyncSession,
        include_user_email: bool = False,
        min_score: Optional[float] = None,
        limit: Optional[int] = None,
        require_reviewed: bool = True,
    ) -> List[Dict[str, Any]]:
        query = (
            select(Interview, User.email)
            .join(User, Interview.user_id == User.id)
            .where(Interview.status == "completed")
            .where(Interview.data_contribution_consent.is_(True))
            .order_by(Interview.created_at.desc())
        )
        if min_score is not None:
            query = query.where(Interview.overall_score >= min_score)
        result = await db.execute(query)
        rows = result.all()
        interview_ids = [interview.id for interview, _ in rows]
        messages_by_interview = {interview_id: [] for interview_id in interview_ids}

        if interview_ids:
            msg_result = await db.execute(
                select(InterviewMessage)
                .where(InterviewMessage.interview_id.in_(interview_ids))
                .order_by(InterviewMessage.interview_id, InterviewMessage.id)
            )
            for message in msg_result.scalars().all():
                messages_by_interview.setdefault(message.interview_id, []).append(message)

        samples: List[Dict[str, Any]] = []
        for interview, email in rows:
            try:
                sample = InterviewService.build_training_sample(
                    interview=interview,
                    messages=messages_by_interview.get(interview.id, []),
                    user_email=email,
                    include_user_email=include_user_email,
                )
                if require_reviewed and not InterviewService._is_reviewed_training_sample(sample):
                    continue
                if not InterviewService._is_export_ready_training_sample(sample):
                    continue
                samples.append(sample)
                if limit is not None and len(samples) >= limit:
                    break
            except Exception as exc:
                logger.warning("Skip malformed training sample interview_id=%s: %s", interview.id, exc)
        return samples

    @staticmethod
    def _sample_has_followup_signal(sample: Dict[str, Any]) -> bool:
        for round_item in sample.get("rounds") or []:
            evaluation = round_item.get("evaluation") or {}
            if (
                evaluation.get("next_best_followup")
                or evaluation.get("evidence_strength_delta")
                or evaluation.get("claim_confidence_change")
            ):
                return True
        return False

    @staticmethod
    def _sample_has_report_signal(sample: Dict[str, Any]) -> bool:
        report = sample.get("report_summary") or {}
        return bool(
            report.get("common_gaps")
            or report.get("common_strengths")
            or report.get("training_priorities")
        )

    @staticmethod
    def _match_evaluation_datasets(sample: Dict[str, Any]) -> Dict[str, List[str]]:
        interview = sample.get("interview") or {}
        review = sample.get("training_sample_review") or {}
        export_notes = sample.get("export_notes") or {}
        sample_boundary = InterviewService._sample_boundary_from_sample(sample)
        try:
            overall_score = float(interview.get("overall_score") or 0)
        except (TypeError, ValueError):
            overall_score = 0.0
        base_rules = [
            "status=completed",
            "data_contribution_consent=true",
            "sample_boundary.sample_origin=real_authorized",
            "sample_boundary.candidate_answer_source=human",
            "sample_boundary.for_real_sft=true",
            "training_sample_review.review_status=reviewed",
        ]
        if not (interview.get("data_contribution_consent") or export_notes.get("data_contribution_consent")):
            return {}
        if not InterviewService._is_real_sft_boundary(sample_boundary):
            return {}
        if interview.get("status") != "completed" or review.get("review_status") != "reviewed":
            return {}

        matched: Dict[str, List[str]] = {}
        if review.get("is_high_quality") and not review.get("has_hallucination") and overall_score >= 7.5:
            matched["golden_cases"] = [
                *base_rules,
                "training_sample_review.is_high_quality=true",
                "training_sample_review.has_hallucination=false",
                "overall_score>=7.5",
            ]
        if review.get("has_hallucination"):
            matched["hallucination_cases"] = [
                *base_rules,
                "training_sample_review.has_hallucination=true",
            ]
        if (
            review.get("followup_worthy")
            and not review.get("has_hallucination")
            and overall_score >= 6.0
            and InterviewService._sample_has_followup_signal(sample)
        ):
            matched["followup_quality_cases"] = [
                *base_rules,
                "training_sample_review.followup_worthy=true",
                "training_sample_review.has_hallucination=false",
                "overall_score>=6.0",
                "followup_signal_present=true",
            ]
        if (
            review.get("report_actionable")
            and not review.get("has_hallucination")
            and overall_score >= 6.0
            and InterviewService._sample_has_report_signal(sample)
        ):
            matched["report_quality_cases"] = [
                *base_rules,
                "training_sample_review.report_actionable=true",
                "training_sample_review.has_hallucination=false",
                "overall_score>=6.0",
                "report_signal_present=true",
            ]
        return matched

    @staticmethod
    def _select_fine_tuning_round(sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rounds = sample.get("rounds") or []
        for round_item in rounds:
            evaluation = round_item.get("evaluation") or {}
            next_followup = evaluation.get("next_best_followup")
            if isinstance(next_followup, dict) and str(next_followup.get("question") or "").strip():
                return round_item
        for round_item in rounds:
            if str(round_item.get("question") or "").strip():
                return round_item
        return None

    @staticmethod
    def _build_fine_tuning_record(sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        interview = sample.get("interview") or {}
        review = sample.get("training_sample_review") or {}
        export_notes = sample.get("export_notes") or {}
        sample_boundary = InterviewService._sample_boundary_from_sample(sample)
        if interview.get("status") != "completed":
            return None
        if review.get("review_status") != "reviewed":
            return None
        if not (interview.get("data_contribution_consent") or export_notes.get("data_contribution_consent")):
            return None
        if not InterviewService._is_real_sft_boundary(sample_boundary):
            return None
        if not (
            review.get("is_high_quality")
            or review.get("followup_worthy")
            or review.get("report_actionable")
            or review.get("has_hallucination")
        ):
            return None

        round_item = InterviewService._select_fine_tuning_round(sample)
        if not round_item:
            return None

        evaluation = round_item.get("evaluation") or {}
        next_followup = evaluation.get("next_best_followup")
        report_summary = sample.get("report_summary") or {}
        evidence_context = sample.get("evidence_context") or {}
        task_type = "followup_generation"
        output_question = None
        verification_target = round_item.get("question_target_gap") or next(
            iter(report_summary.get("common_gaps") or []),
            "",
        )
        if isinstance(next_followup, dict):
            output_question = str(next_followup.get("question") or "").strip()
            verification_target = next_followup.get("target_gap") or verification_target
        if not output_question:
            task_type = "interview_question_generation"
            output_question = str(round_item.get("question") or "").strip()
        if not output_question:
            return None

        input_payload = {
            "target_position": interview.get("target_position"),
            "ability_gap": round_item.get("question_target_gap") or next(
                iter(report_summary.get("common_gaps") or []),
                "",
            ),
            "evidence_status": round_item.get("blueprint_requirement_status"),
            "question_reason": round_item.get("question_reason"),
            "evidence_summary": (round_item.get("evidence_summary") or [])[:5],
            "rag_context": (evidence_context.get("blueprint_evidence_summary") or [])[:5],
            "report_gaps": (report_summary.get("common_gaps") or [])[:5],
            "report_training_priorities": (report_summary.get("training_priorities") or [])[:5],
        }
        if task_type == "followup_generation":
            input_payload["previous_question"] = round_item.get("question")
            input_payload["candidate_answer"] = round_item.get("answer")
            input_payload["feedback"] = round_item.get("feedback")

        reviewer_email = str(review.get("reviewer_email") or "").strip()
        reviewer_hash = sha256(reviewer_email.lower().encode("utf-8")).hexdigest() if reviewer_email else ""
        record = {
            "schema_version": FINE_TUNING_SAMPLE_SCHEMA_VERSION,
            "task_type": task_type,
            "instruction": (
                "你是就业能力诊断平台的面试追问模型。请根据岗位画像、简历证据状态、"
                "候选人回答和人工评分信号，生成能验证能力缺口且不编造经历的追问。"
            ),
            "input": input_payload,
            "output": {
                "question": output_question,
                "verification_target": verification_target,
                "expected_constraints": [
                    "不得把岗位知识库写成候选人真实经历",
                    "必须围绕证据不足或待验证能力追问",
                    "优先要求候选人给出具体场景、行动和结果",
                ],
            },
            "metadata": {
                "interview_id": interview.get("id"),
                "case_id": review.get("case_id"),
                "target_position": interview.get("target_position"),
                "quality_tier": review.get("quality_tier"),
                "review_status": review.get("review_status"),
                "reviewed_at": review.get("reviewed_at"),
                "reviewer_present": bool(review.get("reviewer_email")),
                "reviewer_hash": reviewer_hash,
                "is_high_quality": bool(review.get("is_high_quality")),
                "has_hallucination": bool(review.get("has_hallucination")),
                "followup_worthy": bool(review.get("followup_worthy")),
                "report_actionable": bool(review.get("report_actionable")),
                "human_overall_score": review.get("human_overall_score"),
                "dataset_split": review.get("dataset_split"),
                "data_contribution_consent": True,
                "sample_origin": "real_authorized",
                "candidate_answer_source": "human",
                "for_real_sft": True,
            },
        }
        return json.loads(json.dumps(record, ensure_ascii=False, default=InterviewService._json_safe))

    @staticmethod
    def build_fine_tuning_dataset_bundle(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        records: List[Dict[str, Any]] = []
        counterexamples: List[Dict[str, Any]] = []
        reviewed_samples = 0
        authorized_samples = 0
        high_quality_samples = 0

        for sample in samples:
            interview = sample.get("interview") or {}
            export_notes = sample.get("export_notes") or {}
            review = sample.get("training_sample_review") or {}
            is_completed = interview.get("status") == "completed"
            if is_completed and (
                interview.get("data_contribution_consent") or export_notes.get("data_contribution_consent")
            ) and InterviewService._is_real_sft_boundary(InterviewService._sample_boundary_from_sample(sample)):
                authorized_samples += 1
            if is_completed and review.get("review_status") == "reviewed":
                reviewed_samples += 1
            if is_completed and review.get("is_high_quality") and not review.get("has_hallucination"):
                high_quality_samples += 1

            record = InterviewService._build_fine_tuning_record(sample)
            if not record:
                continue
            if (record.get("metadata") or {}).get("has_hallucination"):
                counterexamples.append(record)
            else:
                records.append(record)

        files = {
            "fine_tuning_sft.jsonl": "\n".join(
                json.dumps(item, ensure_ascii=False) for item in records
            ),
            "fine_tuning_counterexamples.jsonl": "\n".join(
                json.dumps(item, ensure_ascii=False) for item in counterexamples
            ),
        }
        files = InterviewService._sanitize_export_files(files)
        preview = {
            "schema_version": FINE_TUNING_SAMPLE_SCHEMA_VERSION,
            "stats": {
                "authorized_samples": authorized_samples,
                "reviewed_samples": reviewed_samples,
                "high_quality_samples": high_quality_samples,
                "sft_ready_samples": len(records),
                "hallucination_counterexamples": len(counterexamples),
            },
            "files": [
                {
                    "filename": "fine_tuning_sft.jsonl",
                    "label": "SFT 正向样本",
                    "count": len(records),
                    "description": "已授权、已人工标注、无幻觉且具备追问/报告/高质量信号的微调准备样本。",
                },
                {
                    "filename": "fine_tuning_counterexamples.jsonl",
                    "label": "幻觉反例样本",
                    "count": len(counterexamples),
                    "description": "已授权、已人工标注且被标记为幻觉或无依据强答的反例样本，用于后续约束优化。",
                },
            ],
            "base_requirements": [
                "status=completed",
                "data_contribution_consent=true",
                "sample_boundary.sample_origin=real_authorized",
                "sample_boundary.candidate_answer_source=human",
                "sample_boundary.for_real_sft=true",
                "training_sample_review.review_status=reviewed",
                "positive_sft_requires_has_hallucination=false",
                "requires_quality_or_followup_or_report_signal=true",
            ],
            "jsonl_fields": ["instruction", "input", "output", "metadata"],
        }
        return {
            "preview": preview,
            "files": files,
        }

    @staticmethod
    def build_fine_tuning_readiness_report(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat()
        fine_tuning_bundle = InterviewService.build_fine_tuning_dataset_bundle(samples)
        stats = fine_tuning_bundle["preview"]["stats"]
        position_counter: Counter[str] = Counter()
        reviewed_authorized_count = 0
        for sample in samples:
            interview = sample.get("interview") or {}
            if InterviewService._is_export_ready_training_sample(sample):
                reviewed_authorized_count += 1
                position = str(interview.get("target_position") or "未填写岗位").strip()
                position_counter[position or "未填写岗位"] += 1

        top_positions = [
            {"target_position": position, "count": count}
            for position, count in position_counter.most_common(5)
        ]
        files = fine_tuning_bundle["preview"]["files"]
        positive_file = next(
            (item for item in files if item["filename"] == "fine_tuning_sft.jsonl"),
            {"count": 0},
        )
        counterexample_file = next(
            (item for item in files if item["filename"] == "fine_tuning_counterexamples.jsonl"),
            {"count": 0},
        )
        position_lines = (
            "\n".join(
                f"| {item['target_position']} | {item['count']} |"
                for item in top_positions
            )
            if top_positions
            else "| 暂无 | 0 |"
        )
        markdown = f"""# 职启智评微调准备报告

生成时间 UTC：`{generated_at}`
报告版本：`{FINE_TUNING_READINESS_REPORT_VERSION}`

## 1. 当前结论

- 当前完成的是微调准备数据链路，不代表已经完成真实 SFT/LoRA 训练。
- 可用于 SFT 的正向样本：`{positive_file.get('count', 0)}` 条。
- 幻觉或无依据强答反例：`{counterexample_file.get('count', 0)}` 条。
- 已授权样本：`{stats.get('authorized_samples', 0)}` 条；已人工复核样本：`{stats.get('reviewed_samples', 0)}` 条。
- 已授权且已人工复核样本：`{reviewed_authorized_count}` 条。

## 2. 数据来源与准入规则

| 规则 | 说明 |
|---|---|
| 用户授权 | 仅使用 `data_contribution_consent=true` 的本次案例 |
| 人工复核 | 仅使用 `training_sample_review.review_status=reviewed` 的样本 |
| 正向样本 | 要求 `has_hallucination=false`，并具备高质量、追问价值或报告可执行性信号 |
| 反例样本 | 带幻觉或无依据强答标记的样本单独沉淀，不混入正向训练目标 |

## 3. 去标识化与保留字段

- 删除或遮挡：姓名、手机号、邮箱、证件号、学号、详细住址、文件名中的个人标识。
- 为保证岗位诊断和训练质量，可能保留：学校、专业、教育经历、实习/项目经历、技能、目标岗位、面试问答、报告摘要和人工评分。
- 当前口径是去标识化/脱敏，不写“完全匿名化”。

## 4. 样本分层

| 样本层 | 数量 | 用途 |
|---|---:|---|
| 正向 SFT 样本 | {positive_file.get('count', 0)} | 训练后续追问生成、证据对齐表达和面试问题组织 |
| 幻觉反例样本 | {counterexample_file.get('count', 0)} | 约束模型不要把岗位知识写成候选人真实经历 |
| 高质量候选样本 | {stats.get('high_quality_samples', 0)} | 用于后续黄金样本筛选和评测基准 |

## 5. 岗位覆盖

| 目标岗位 | 已授权且已人工复核样本数 |
|---|---:|
{position_lines}

## 6. 可训练任务

1. 面试追问生成：围绕能力缺口、证据状态和候选人回答生成下一问。
2. 评分理由生成：学习人工评分中对证据对齐、问题质量和报告可执行性的判断。
3. 报告建议生成：把面试暴露的短板转化为可执行提升建议。
4. 学习任务生成：生成包含材料、练习、验收方式和预计耗时的学习任务。

## 7. 风险控制

- 未授权样本不导出、不进入微调准备数据。
- 岗位知识库只作为岗位要求、追问方向和表达参考，不能写成候选人真实经历。
- AI 自动评分不能冒充人工评分。
- C1/C2/C3 真实闭环仍需后续服务器跑测和 CSV 回填，本报告不能替代真实验收。

## 8. 下一步

1. 继续收集用户授权且人工复核的真实样本。
2. 当正向样本达到 30-50 条时，先做 JSONL 格式验证和小样本提示词/RAG 对照。
3. 当样本达到 100-300 条时，再进入轻量 SFT 或 LoRA/QLoRA 实验。
4. 用证据对齐率、幻觉率、追问质量、报告可执行性和 AI/人工评分差异做对照评估。
"""
        preview = {
            "schema_version": FINE_TUNING_READINESS_REPORT_VERSION,
            "generated_at": generated_at,
            "stats": {
                **stats,
                "reviewed_authorized_samples": reviewed_authorized_count,
            },
            "top_positions": top_positions,
            "sections": [
                "当前结论",
                "数据来源与准入规则",
                "去标识化与保留字段",
                "样本分层",
                "岗位覆盖",
                "可训练任务",
                "风险控制",
                "下一步",
            ],
        }
        preview, _ = InterviewService._sanitize_export_payload(preview)
        clean_markdown, _ = InterviewService._redact_direct_identifiers(markdown)
        _, remaining = InterviewService._redact_direct_identifiers(clean_markdown)
        if remaining:
            raise ValueError("Fine-tuning readiness report still contains direct personal identifiers")
        InterviewService._assert_no_direct_identifier(preview)
        InterviewService._assert_no_direct_identifier(clean_markdown)
        return {
            "preview": preview,
            "markdown": clean_markdown,
        }

    @staticmethod
    def build_evaluation_dataset_bundle(
        samples: Sequence[Dict[str, Any]],
        include_user_email: bool = False,
    ) -> Dict[str, Any]:
        exported_at = datetime.now(timezone.utc).isoformat()
        dataset_entries: Dict[str, List[Dict[str, Any]]] = {
            item["dataset_type"]: [] for item in EVALUATION_DATASET_DEFINITIONS
        }
        example_ids: Dict[str, List[int]] = {
            item["dataset_type"]: [] for item in EVALUATION_DATASET_DEFINITIONS
        }
        reviewed_samples = 0

        for sample in samples:
            review = sample.get("training_sample_review") or {}
            if review.get("review_status") == "reviewed":
                reviewed_samples += 1

            membership = InterviewService._match_evaluation_datasets(sample)
            interview_id = int((sample.get("interview") or {}).get("id") or 0)
            for dataset_type, matched_rules in membership.items():
                dataset_sample = json.loads(
                    json.dumps(sample, ensure_ascii=False, default=InterviewService._json_safe)
                )
                dataset_sample["dataset_membership"] = {
                    "dataset_type": dataset_type,
                    "matched_rules": matched_rules,
                }
                dataset_entries[dataset_type].append(dataset_sample)
                if interview_id and interview_id not in example_ids[dataset_type] and len(example_ids[dataset_type]) < 5:
                    example_ids[dataset_type].append(interview_id)

        preview_datasets = []
        manifest_datasets = []
        files: Dict[str, str] = {}
        for definition in EVALUATION_DATASET_DEFINITIONS:
            dataset_type = definition["dataset_type"]
            filename = definition["filename"]
            items = dataset_entries[dataset_type]
            files[filename] = "\n".join(
                json.dumps(item, ensure_ascii=False) for item in items
            )
            dataset_preview = {
                "dataset_type": dataset_type,
                "filename": filename,
                "label": definition["label"],
                "description": definition["description"],
                "count": len(items),
                "example_interview_ids": example_ids[dataset_type],
                "rules": definition["rules"],
            }
            preview_datasets.append(dataset_preview)
            manifest_datasets.append(dataset_preview)

        filters = {
            "base_requirements": [
                "status=completed",
                "data_contribution_consent=true",
                "sample_boundary.sample_origin=real_authorized",
                "sample_boundary.candidate_answer_source=human",
                "sample_boundary.for_real_sft=true",
                "training_sample_review.review_status=reviewed",
            ],
            "thresholds": {
                "golden_cases_min_score": 7.5,
                "followup_quality_cases_min_score": 6.0,
                "report_quality_cases_min_score": 6.0,
            },
            "overlap_allowed": True,
            "pii_included": include_user_email,
        }

        preview = {
            "schema_version": EVALUATION_DATASET_SCHEMA_VERSION,
            "generated_at": exported_at,
            "filters": filters,
            "stats": {
                "completed_samples": len(samples),
                "reviewed_samples": reviewed_samples,
                "dataset_assignments": sum(len(items) for items in dataset_entries.values()),
            },
            "datasets": preview_datasets,
        }
        fine_tuning_bundle = InterviewService.build_fine_tuning_dataset_bundle(samples)
        preview["fine_tuning"] = fine_tuning_bundle["preview"]
        manifest = {
            "schema_version": EVALUATION_DATASET_SCHEMA_VERSION,
            "exported_at": exported_at,
            "filters": filters,
            "datasets": manifest_datasets,
            "fine_tuning": fine_tuning_bundle["preview"],
            "counts": {
                definition["filename"]: len(dataset_entries[definition["dataset_type"]])
                for definition in EVALUATION_DATASET_DEFINITIONS
            },
            "pii_included": include_user_email,
        }
        files.update(fine_tuning_bundle["files"])
        files = InterviewService._sanitize_export_files(files)
        return {
            "preview": preview,
            "manifest": manifest,
            "files": files,
        }

    @staticmethod
    def build_evaluation_dataset_zip(bundle: Dict[str, Any]) -> bytes:
        manifest, _ = InterviewService._sanitize_export_payload(bundle.get("manifest") or {})
        InterviewService._assert_no_direct_identifier(manifest)
        files = InterviewService._sanitize_export_files(bundle.get("files") or {})
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            for filename, content in files.items():
                archive.writestr(filename, content or "")
        return buffer.getvalue()

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 28) -> List[str]:
        content = text or ""
        if not content:
            return [""]
        return [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]

    @staticmethod
    async def _resolve_knowledge_base(
        db: AsyncSession,
        user_id: int,
        target_position: str,
        knowledge_base_id: Optional[int] = None,
    ) -> Optional[Dict]:
        if knowledge_base_id:
            result = await db.execute(
                select(PositionKnowledgeBase).where(
                    PositionKnowledgeBase.id == knowledge_base_id,
                    or_(
                        PositionKnowledgeBase.user_id == user_id,
                        PositionKnowledgeBase.scope == "public",
                    ),
                )
            )
            knowledge_base = result.scalar_one_or_none()
            if not knowledge_base:
                raise NotFoundError(message="岗位知识库不存在")
            if not knowledge_base.is_active:
                raise ValidationError(message="所选岗位知识库已停用，请重新选择")
        else:
            normalized_target = (target_position or "").strip()
            if not normalized_target:
                return None
            result = await db.execute(
                select(PositionKnowledgeBase)
                .where(
                    PositionKnowledgeBase.user_id == user_id,
                    PositionKnowledgeBase.scope == "private",
                    PositionKnowledgeBase.is_active.is_(True),
                    PositionKnowledgeBase.target_position.ilike(f"%{normalized_target}%"),
                )
                .order_by(PositionKnowledgeBase.updated_at.desc())
            )
            knowledge_base = result.scalars().first()
            if not knowledge_base:
                result = await db.execute(
                    select(PositionKnowledgeBase)
                    .where(
                        PositionKnowledgeBase.scope == "public",
                        PositionKnowledgeBase.is_active.is_(True),
                        PositionKnowledgeBase.target_position.ilike(f"%{normalized_target}%"),
                    )
                    .order_by(PositionKnowledgeBase.updated_at.desc())
                )
                knowledge_base = result.scalars().first()

        payload = InterviewService._serialize_knowledge_base(knowledge_base)
        if not payload:
            return None
        try:
            slices = await position_knowledge_base_slice_service.list_for_knowledge_base(db, knowledge_base.id)
            payload["slices"] = [InterviewService._compact_slice(item) for item in slices]
            payload["slice_count"] = len(payload["slices"])
            payload["routing_strategy"] = (
                "structured_slice_routing_v1" if payload["slices"] else "full_text_fallback"
            )
        except Exception as exc:
            logger.warning("Knowledge slice loading failed for knowledge_base=%s: %s", knowledge_base.id, exc)
            payload["slices"] = []
            payload["slice_count"] = 0
            payload["routing_strategy"] = "full_text_fallback"
        return payload

    @staticmethod
    async def start_interview(
        db: AsyncSession,
        user_id: int,
        resume_id: int,
        target_position: str,
        knowledge_base_id: Optional[int],
        difficulty: str,
        total_questions: int,
        multi_interviewer_enabled: bool = False,
        ai_config: Optional[Dict] = None,
        data_contribution_consent: Optional[bool] = None,
        privacy_consent_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        difficulty = InterviewService._normalize_difficulty(difficulty)
        difficulty_profile = InterviewService._public_difficulty_profile(difficulty)
        result = await db.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.user_id == user_id,
            )
        )
        resume = result.scalar_one_or_none()
        if not resume:
            raise NotFoundError(message="简历不存在")
        if resume.status != "completed":
            raise ValidationError(message="简历尚未解析完成")

        effective_data_consent = (
            bool(data_contribution_consent)
            if data_contribution_consent is not None
            else False
        )
        privacy_snapshot = (
            dict(privacy_consent_snapshot)
            if isinstance(privacy_consent_snapshot, dict)
            else {}
        )
        privacy_snapshot.update(
            {
                "source": "interview_start",
                "data_contribution_consent": effective_data_consent,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        parsed_resume = InterviewService._load_resume_payload(resume)
        resume_analysis = ensure_resume_evaluation_snapshot(
            InterviewService._load_resume_analysis_payload(resume),
            target_position=target_position or resume.target_position,
        )
        matching_metrics = matching_metrics_from_payload(resume_analysis)
        knowledge_base_context = await InterviewService._resolve_knowledge_base(
            db=db,
            user_id=user_id,
            target_position=target_position,
            knowledge_base_id=knowledge_base_id,
        )
        question_plan = InterviewService._route_question_plan(
            question_plan=InterviewService._build_question_plan(total_questions, difficulty),
            knowledge_base=knowledge_base_context,
            parsed_resume=parsed_resume,
            target_position=target_position,
            difficulty=difficulty,
            matching_metrics=matching_metrics,
        )
        resume_evidence = InterviewService._load_resume_evidence(resume)
        interview_mode = "panel" if multi_interviewer_enabled else "single"
        if interview_mode == "panel":
            interview_blueprint = AIService.build_interview_blueprint_fallback(
                parsed_resume=parsed_resume,
                target_position=target_position,
                resume_evidence=resume_evidence,
                knowledge_base=knowledge_base_context,
                question_plan=question_plan,
            )
        else:
            try:
                interview_blueprint = await AIService.extract_interview_blueprint(
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    resume_evidence=resume_evidence,
                    knowledge_base=knowledge_base_context,
                    question_plan=question_plan,
                    ai_config=ai_config,
                )
            except ValidationError as exc:
                raise ValidationError(
                    message=InterviewService._format_start_interview_error(exc.detail)
                ) from exc
            except Exception as exc:
                logger.warning("Interview blueprint generation failed, using fallback: %s", exc)
                interview_blueprint = AIService.build_interview_blueprint_fallback(
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    resume_evidence=resume_evidence,
                    knowledge_base=knowledge_base_context,
                    question_plan=question_plan,
                )
        question_plan = InterviewService._apply_blueprint_to_question_plan(
            question_plan=question_plan,
            interview_blueprint=interview_blueprint,
        )

        panel_snapshot = InterviewService._build_panel_snapshot(interview_mode)
        if interview_blueprint:
            panel_snapshot["interview_blueprint"] = interview_blueprint

        if interview_mode == "panel":
            try:
                panel_payload = await asyncio.wait_for(
                    AIService.generate_panel_questions(
                        parsed_resume=parsed_resume,
                        target_position=target_position,
                        difficulty=difficulty,
                        count=total_questions,
                        question_plan=question_plan,
                        knowledge_base=knowledge_base_context,
                        panel_snapshot=panel_snapshot,
                        interview_blueprint=interview_blueprint,
                        ai_config=ai_config,
                        allow_json_repair=False,
                    ),
                    timeout=START_PANEL_QUESTION_TIMEOUT_SECONDS,
                )
                if panel_payload.get("moderator_style"):
                    panel_snapshot["moderator_style"] = panel_payload["moderator_style"]
                if panel_payload.get("metadata"):
                    panel_snapshot["structured_output"] = {
                        "version": panel_payload["metadata"].get("version"),
                        "retrieved_slice_ids": panel_payload["metadata"].get("retrieved_slice_ids") or [],
                    }
                if panel_payload.get("moderator", {}).get("reasoning_summary"):
                    panel_snapshot["moderator_reasoning_summary"] = panel_payload["moderator"]["reasoning_summary"]
                questions = InterviewService._normalize_questions(
                    raw_questions=panel_payload.get("questions") or [],
                    question_plan=question_plan,
                    interview_mode="panel",
                )
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="llm_panel_start",
                    panel_status="active",
                )
            except ValidationError as exc:
                if not InterviewService._is_question_generation_validation_error(exc):
                    raise ValidationError(
                        message=InterviewService._format_start_interview_error(exc.detail)
                    ) from exc
                logger.warning("Panel question generation returned invalid payload, using deterministic fallback: %s", exc)
                raw_questions = InterviewService._build_deterministic_question_fallback(
                    question_plan=question_plan,
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    total_questions=total_questions,
                    fallback_reason="panel_question_generation_invalid",
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="panel",
                )
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="deterministic_start_fallback",
                    panel_status="active_fallback",
                    fallback_reason="panel_question_generation_invalid",
                )
            except asyncio.TimeoutError as exc:
                logger.warning("Panel question generation timed out, using deterministic fallback")
                raw_questions = InterviewService._build_deterministic_question_fallback(
                    question_plan=question_plan,
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    total_questions=total_questions,
                    fallback_reason="panel_question_generation_timeout",
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="panel",
                )
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="deterministic_start_fallback",
                    panel_status="active_fallback",
                    fallback_reason="panel_question_generation_timeout",
                )
            except Exception as exc:
                logger.warning("Panel question generation failed, using deterministic fallback: %s", exc)
                raw_questions = InterviewService._build_deterministic_question_fallback(
                    question_plan=question_plan,
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    total_questions=total_questions,
                    fallback_reason="panel_question_generation_failed",
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="panel",
                )
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="deterministic_start_fallback",
                    panel_status="active_fallback",
                    fallback_reason="panel_question_generation_failed",
                )
        else:
            try:
                raw_questions = await AIService.generate_questions(
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    difficulty=difficulty,
                    count=total_questions,
                    knowledge_base=knowledge_base_context,
                    question_plan=question_plan,
                    interview_blueprint=interview_blueprint,
                    ai_config=ai_config,
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="single",
                )
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="llm_single_start",
                    panel_status="single_active",
                )
            except ValidationError as exc:
                if not InterviewService._is_question_generation_validation_error(exc):
                    raise ValidationError(
                        message=InterviewService._format_start_interview_error(exc.detail)
                    ) from exc
                logger.warning("Question generation returned invalid payload, using deterministic fallback: %s", exc)
                raw_questions = InterviewService._build_deterministic_question_fallback(
                    question_plan=question_plan,
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    total_questions=total_questions,
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="single",
                )
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="deterministic_start_fallback",
                    panel_status="single_fallback",
                    fallback_reason="question_generation_failed",
                )
            except Exception as exc:
                logger.exception("Question generation failed, using deterministic fallback: %s", exc)
                raw_questions = InterviewService._build_deterministic_question_fallback(
                    question_plan=question_plan,
                    parsed_resume=parsed_resume,
                    target_position=target_position,
                    total_questions=total_questions,
                )
                questions = InterviewService._normalize_questions(
                    raw_questions=raw_questions,
                    question_plan=question_plan,
                    interview_mode="single",
                )
                panel_snapshot = InterviewService._build_panel_snapshot(
                    mode="single",
                    requested_panel=False,
                    fallback_reason="question_generation_failed",
                )
                if interview_blueprint:
                    panel_snapshot["interview_blueprint"] = interview_blueprint
                InterviewService._set_panel_generation_metadata(
                    panel_snapshot,
                    generation_strategy="deterministic_start_fallback",
                    panel_status="single_fallback",
                    fallback_reason="question_generation_failed",
                )

        runtime_snapshot = InterviewService._sanitize_ai_runtime_config(ai_config)
        if runtime_snapshot:
            panel_snapshot["ai_runtime"] = runtime_snapshot

        questions = InterviewService._serialize_questions(questions)
        interview = Interview(
            user_id=user_id,
            resume_id=resume_id,
            knowledge_base_id=knowledge_base_context["id"] if knowledge_base_context else None,
            target_position=target_position,
            difficulty=difficulty,
            total_questions=total_questions,
            current_question_index=0,
            interview_mode=interview_mode,
            questions_data=questions,
            knowledge_base_snapshot=knowledge_base_context,
            panel_snapshot=panel_snapshot,
            status="in_progress",
            data_contribution_consent=effective_data_consent,
            privacy_consent_snapshot=privacy_snapshot,
        )
        db.add(interview)
        try:
            await db.commit()
            await db.refresh(interview)
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Start interview record creation failed: %s", exc)
            raise ValidationError(message=START_INTERVIEW_DB_ERROR_MESSAGE) from exc

        first_question = questions[0]["question"]
        db.add(
            InterviewMessage(
                interview_id=interview.id,
                role="interviewer",
                content=first_question,
                question_index=0,
            )
        )
        try:
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Start interview first message creation failed: %s", exc)
            try:
                await db.execute(sql_delete(Interview).where(Interview.id == interview.id))
                await db.commit()
            except SQLAlchemyError as cleanup_exc:
                await db.rollback()
                logger.warning(
                    "Failed to clean incomplete interview after first message error: interview_id=%s error=%s",
                    interview.id,
                    cleanup_exc,
                )
            raise ValidationError(message=START_INTERVIEW_DB_ERROR_MESSAGE) from exc

        return {
            "interview_id": interview.id,
            "first_question": first_question,
            "question_index": 0,
            "total_questions": total_questions,
            "knowledge_base_title": knowledge_base_context["title"] if knowledge_base_context else None,
            "interview_mode": interview_mode,
            "difficulty_profile": difficulty_profile,
            "company_archetype": difficulty_profile["company_archetype"],
            "question_strategy_summary": difficulty_profile["question_strategy_summary"],
            "rubric_summary": difficulty_profile["rubric_summary"],
            "requested_interview_mode": "panel" if multi_interviewer_enabled else "single",
            "effective_interview_mode": interview_mode,
            "panel_status": panel_snapshot.get("panel_status")
            or (panel_snapshot.get("metadata") or {}).get("panel_status"),
            "fallback_reason": panel_snapshot.get("fallback_reason")
            or (panel_snapshot.get("metadata") or {}).get("fallback_reason"),
            "generation_strategy": (panel_snapshot.get("metadata") or {}).get("generation_strategy"),
            "training_focus": interview_blueprint.get("training_focus") or [],
            "high_risk_claims": InterviewService._blueprint_claim_strings(interview_blueprint),
            "blueprint_evidence_summary": (
                (interview_blueprint.get("blueprint_evidence") or {}).get("resume_evidence_summary")
                or interview_blueprint.get("evidence_summary")
                or []
            ),
            "interview_blueprint": interview_blueprint,
            "data_contribution_consent": bool(interview.data_contribution_consent),
        }

    @staticmethod
    async def submit_answer(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
        answer: str,
        question_index: Optional[int] = None,
        ai_config: Optional[Dict] = None,
    ) -> Dict:
        answer = str(answer or "").strip()
        if not answer:
            raise ValidationError(message="回答内容不能为空")

        if question_index is None:
            raise ValidationError(message="question_index is required to prevent stale answer submission")

        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
                Interview.user_deleted_at.is_(None),
            ).with_for_update()
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")
        if interview.status == "completed":
            raise ValidationError(message="面试已结束")

        resume_result = await db.execute(select(Resume).where(Resume.id == interview.resume_id))
        resume = resume_result.scalar_one_or_none()
        if not resume:
            raise ValidationError(message="答题失败：关联简历不存在，请重新开始面试")
        try:
            parsed_resume = InterviewService._load_resume_payload(resume)
        except ValidationError as exc:
            message = str(getattr(exc, "detail", "") or "关联简历解析结果异常，请重新上传简历或重新开始面试")
            message = message.replace("开始面试失败：", "答题失败：")
            raise ValidationError(message=message) from exc
        knowledge_base_context = interview.knowledge_base_snapshot or None

        messages_result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.interview_id == interview_id)
            .order_by(InterviewMessage.id)
        )
        messages = messages_result.scalars().all()
        chat_history = [{"role": item.role, "content": item.content} for item in messages]

        current_index = int(interview.current_question_index or 0)
        questions = InterviewService._serialize_questions(interview.questions_data or [])
        if not questions:
            logger.warning("Submit answer failed: empty questions_data interview_id=%s", interview_id)
            raise ValidationError(message="面试题目状态异常，请重新开始面试")
        effective_total_questions = min(int(interview.total_questions or len(questions)), len(questions))
        if effective_total_questions <= 0:
            logger.warning("Submit answer failed: invalid total_questions interview_id=%s", interview_id)
            raise ValidationError(message="Interview question state is invalid; please restart the interview")
        if int(interview.total_questions or 0) != len(questions):
            logger.warning(
                "Submit answer using effective question count: interview_id=%s total_questions=%s questions_len=%s",
                interview_id,
                interview.total_questions,
                len(questions),
            )
        if current_index < 0 or current_index >= len(questions):
            logger.warning(
                "Submit answer failed: invalid current_question_index interview_id=%s index=%s total=%s",
                interview_id,
                current_index,
                len(questions),
            )
            raise ValidationError(message="面试进度状态异常，请刷新页面或重新开始面试")
        if int(question_index) != current_index:
            raise ValidationError(message="当前题目已更新，请刷新页面后继续作答")
        current_question_meta = dict(questions[current_index])
        current_question = str(current_question_meta.get("question") or "").strip()
        if not current_question:
            logger.warning("Submit answer failed: blank question interview_id=%s index=%s", interview_id, current_index)
            raise ValidationError(message="当前题目内容异常，请重新开始面试")

        candidate_msg = InterviewMessage(
            interview_id=interview_id,
            role="candidate",
            content=answer,
            question_index=current_index,
        )
        db.add(candidate_msg)

        evaluation_mode, evaluation = await InterviewService._evaluate_round(
            interview_mode=interview.interview_mode,
            question=current_question,
            answer=answer,
            resume_context=parsed_resume,
            chat_history=chat_history,
            knowledge_base=knowledge_base_context,
            question_meta=current_question_meta,
            panel_snapshot=interview.panel_snapshot,
            ai_config=ai_config,
        )
        evaluation = InterviewService._sanitize_round_evaluation_public_fields(
            evaluation,
            fallback_question=current_question,
        )
        evaluation_metadata = evaluation.get("metadata") or {}

        score = float(evaluation.get("score", 5.0))
        feedback = (evaluation.get("feedback") or "").strip()
        if not feedback:
            feedback = "本轮回答已记录，建议进一步补充关键细节和落地场景。"

        candidate_msg.score = Decimal(str(score))
        candidate_msg.feedback = feedback[:500]

        current_question_meta["used_slice_ids"] = (
            (evaluation.get("metadata") or {}).get("retrieved_slice_ids")
            or current_question_meta.get("used_slice_ids")
            or InterviewService._question_slice_ids(current_question_meta)
        )
        current_question_meta["evidence_trace"] = InterviewService._build_evidence_trace(
            current_question_meta.get("selected_slices") or [],
            used_slice_ids=current_question_meta.get("used_slice_ids") or [],
        )
        current_question_meta["evidence_summary"] = InterviewService._build_evidence_summary(
            current_question_meta.get("selected_slices") or [],
            used_slice_ids=current_question_meta.get("used_slice_ids") or [],
        )
        current_question_meta.update(InterviewService._derive_question_target_fields(current_question_meta))
        current_question_meta["selected_followups"] = (
            (evaluation.get("moderator") or {}).get("selected_followups")
            or evaluation.get("selected_followups")
            or current_question_meta.get("selected_followups")
            or []
        )
        if (evaluation.get("moderator") or {}).get("difficulty_hint"):
            current_question_meta["difficulty_hint"] = evaluation["moderator"]["difficulty_hint"]
        current_question_meta["answer"] = answer
        current_question_meta["score"] = score
        current_question_meta["feedback"] = feedback
        current_question_meta["evaluation"] = {
            **evaluation,
            "evaluation_mode": evaluation_mode,
        }
        current_question_meta = InterviewService._sanitize_question_public_fields(current_question_meta)
        questions[current_index] = current_question_meta

        next_index = current_index + 1
        is_finished = next_index >= effective_total_questions or next_index >= len(questions)
        response = {
            "score": score,
            "feedback": feedback,
            "question_index": current_index,
            "is_finished": is_finished,
            "next_question": None,
            "evidence_summary": current_question_meta.get("evidence_summary") or [],
            "used_slice_ids": current_question_meta.get("used_slice_ids") or [],
            "question_target_gap": current_question_meta.get("question_target_gap"),
            "question_target_evidence": current_question_meta.get("question_target_evidence") or [],
            "question_reason": current_question_meta.get("question_reason"),
            "evidence_strength_delta": evaluation.get("evidence_strength_delta") or [],
            "claim_confidence_change": evaluation.get("claim_confidence_change") or [],
            "unresolved_gaps": evaluation.get("unresolved_gaps") or [],
            "next_best_followup": evaluation.get("next_best_followup"),
            "evaluation_mode": evaluation_mode,
            "fallback_reason": evaluation_metadata.get("fallback_reason"),
            "report_status": None,
        }

        if is_finished:
            completed_questions = questions[:effective_total_questions]
            interview.questions_data = InterviewService._serialize_questions(completed_questions)
            interview.status = "completed"
            interview.current_question_index = next_index
            scored_values = [
                float(item.get("score"))
                for item in completed_questions
                if item.get("score") is not None
            ]
            overall = round(sum(scored_values) / len(scored_values), 1) if scored_values else 0
            interview.overall_score = Decimal(str(overall))

            qa_data = InterviewService._build_qa_data(completed_questions)
            report_signals = InterviewService._build_report_signals(completed_questions)
            report_diagnostics: List[Dict[str, Any]] = []
            report_status = "pending"
            report = InterviewService._fallback_report_from_signals(
                report_signals=report_signals,
                reason="report_generation_pending",
                detail="面试已完成，报告正在生成；如生成超时，系统会保留基础报告供查看。",
            )
            interview.report = json.dumps(
                {
                    **InterviewService._merge_report_defaults(
                        report=report,
                        report_signals=report_signals,
                        interview_mode=interview.interview_mode,
                    ),
                    "report_status": report_status,
                },
                ensure_ascii=False,
            )
            response["report_status"] = report_status
            await db.commit()
            try:
                if interview.interview_mode == "panel":
                    report = await asyncio.wait_for(
                        AIService.generate_panel_report(
                            parsed_resume=parsed_resume,
                            target_position=interview.target_position,
                            questions_and_scores=qa_data,
                            knowledge_base=knowledge_base_context,
                            panel_snapshot=interview.panel_snapshot,
                            report_signals=report_signals,
                            ai_config=ai_config,
                        ),
                        timeout=ANSWER_REPORT_TIMEOUT_SECONDS,
                    )
                else:
                    report = await asyncio.wait_for(
                        AIService.generate_report(
                            parsed_resume=parsed_resume,
                            target_position=interview.target_position,
                            questions_and_scores=qa_data,
                            knowledge_base=knowledge_base_context,
                            panel_snapshot=interview.panel_snapshot,
                            report_signals=report_signals,
                            ai_config=ai_config,
                        ),
                        timeout=ANSWER_REPORT_TIMEOUT_SECONDS,
                    )
                report_status = "ready"
            except Exception as exc:
                if isinstance(exc, asyncio.TimeoutError):
                    logger.warning("Primary report generation timed out, using diagnostic report")
                    report_status = "degraded_timeout"
                    report_diagnostics.append(
                        {
                            "reason": "primary_report_generation_timeout",
                            "detail": "报告生成超过时间预算，已使用面试记录生成基础报告。",
                        }
                    )
                    report = InterviewService._fallback_report_from_signals(
                        report_signals=report_signals,
                        reason="report_generation_timeout",
                        detail="报告生成超过时间预算，已使用面试记录生成基础报告。",
                    )
                else:
                    logger.warning("Primary report generation failed, fallback to single report: %s", exc)
                    report_diagnostics.append(
                        {
                            "reason": "primary_report_generation_failed",
                            "detail": str(exc),
                        }
                    )
                    try:
                        report = await asyncio.wait_for(
                            AIService.generate_report(
                                parsed_resume=parsed_resume,
                                target_position=interview.target_position,
                                questions_and_scores=qa_data,
                                knowledge_base=knowledge_base_context,
                                panel_snapshot=interview.panel_snapshot,
                                report_signals=report_signals,
                                ai_config=ai_config,
                            ),
                            timeout=ANSWER_REPORT_TIMEOUT_SECONDS,
                        )
                        report_status = "single_report_fallback"
                        if isinstance(report, dict):
                            report["fallback_mode"] = "single_report_fallback"
                    except Exception as fallback_exc:
                        logger.warning("Fallback report generation failed, using diagnostic report: %s", fallback_exc)
                        report_status = "degraded_timeout" if isinstance(fallback_exc, asyncio.TimeoutError) else "degraded_error"
                        report_diagnostics.append(
                            {
                                "reason": "fallback_report_generation_failed",
                                "detail": str(fallback_exc),
                            }
                        )
                        report = InterviewService._fallback_report_from_signals(
                            report_signals=report_signals,
                            reason="report_generation_unavailable",
                            detail="主报告和备用报告生成均失败，已使用面试记录生成基础报告。",
                        )

            report = InterviewService._merge_report_defaults(
                report=report,
                report_signals=report_signals,
                interview_mode=interview.interview_mode,
            )
            if report_diagnostics:
                report["report_diagnostics"] = [
                    *(report.get("report_diagnostics") or []),
                    *report_diagnostics,
                ]
            resume_analysis = ensure_resume_evaluation_snapshot(
                InterviewService._load_resume_analysis_payload(resume) if resume else {},
                target_position=interview.target_position,
            )
            if resume_analysis.get("matching_metrics") and not report.get("matching_metrics"):
                report["matching_metrics"] = resume_analysis["matching_metrics"]
            if resume_analysis.get("resume_evaluation_snapshot") and not report.get("resume_evaluation_snapshot"):
                report["resume_evaluation_snapshot"] = resume_analysis["resume_evaluation_snapshot"]
            if resume_analysis.get("ability_gap_profile") and not report.get("ability_gap_profile"):
                report["ability_gap_profile"] = resume_analysis["ability_gap_profile"]
            if resume_analysis.get("learning_plan") and not report.get("learning_plan"):
                report["learning_plan"] = resume_analysis["learning_plan"]
            report["question_scores"] = InterviewService._build_question_scores(completed_questions)
            report["mode_label"] = (
                "内部多面试官协同 + 单主持人输出"
                if interview.interview_mode == "panel"
                else "单面试官模式"
            )
            report["report_status"] = report_status
            response["report_status"] = report_status
            interview.report = json.dumps(report, ensure_ascii=False)
        else:
            next_question_meta = dict(questions[next_index])
            if interview.interview_mode == "panel":
                next_question_meta = InterviewService._apply_followup_to_next_question(
                    current_question_meta=current_question_meta,
                    next_question_meta=next_question_meta,
                    evaluation=evaluation,
                )
            next_question_meta = InterviewService._reroute_question_slices(
                question_meta=next_question_meta,
                knowledge_base=knowledge_base_context,
                parsed_resume=parsed_resume,
                target_position=interview.target_position,
                difficulty=interview.difficulty,
                context_terms=InterviewService._extract_weakness_terms(current_question_meta, evaluation),
            )
            questions[next_index] = next_question_meta
            interview.questions_data = InterviewService._serialize_questions(questions)
            interview.current_question_index = next_index
            next_question = next_question_meta["question"]
            response["next_question"] = next_question
            response["next_question_target_gap"] = next_question_meta.get("question_target_gap")
            response["next_question_reason"] = next_question_meta.get("question_reason")
            db.add(
                InterviewMessage(
                    interview_id=interview_id,
                    role="interviewer",
                    content=next_question,
                    question_index=next_index,
                )
            )

        await db.commit()
        return response

    @staticmethod
    def _format_answer_stream_error(exc: Exception) -> str:
        if isinstance(exc, asyncio.TimeoutError):
            return "本轮评估耗时较长，系统已停止等待。请刷新查看记录；如果回答未保存，可直接重试。"
        if InterviewService._is_recoverable_evaluation_error(exc):
            return "本轮评分生成异常，请刷新查看记录或稍后重试。"
        if isinstance(exc, ValidationError):
            return str(getattr(exc, "detail", "") or "答题失败，请稍后重试")
        message = str(exc or "").strip()
        if re.search(r"Expecting .* delimiter|JSONDecodeError|json parser|JSON\.parse|unterminated string", message, re.I):
            return "本轮评分生成异常，请刷新查看记录或稍后重试。"
        return message or "答题失败，请稍后重试"

    @staticmethod
    async def submit_answer_stream(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
        answer: str,
        question_index: Optional[int] = None,
        ai_config: Optional[Dict] = None,
    ):
        def _event(payload: Dict[str, Any]) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        is_final_round = False
        try:
            precheck = await db.execute(
                select(
                    Interview.current_question_index,
                    Interview.total_questions,
                    Interview.questions_data,
                ).where(
                    Interview.id == interview_id,
                    Interview.user_id == user_id,
                    Interview.user_deleted_at.is_(None),
                )
            )
            row = precheck.first()
            if row:
                current = int(row.current_question_index or 0)
                total = int(row.total_questions or 0)
                questions_len = len(row.questions_data or [])
                effective_total = min(total or questions_len, questions_len or total)
                is_final_round = effective_total > 0 and int(question_index or current) >= effective_total - 1
        except Exception as precheck_exc:
            logger.warning("Submit answer stream precheck failed: %s", precheck_exc)

        yield _event({"type": "stream_version", "version": "answer_stream_v2"})
        yield _event({"type": "status", "stage": "received", "content": "已收到回答，正在准备评分。"})
        yield _event({"type": "status", "stage": "evaluating", "content": "正在评估本轮回答，请稍候。"})

        task = asyncio.create_task(
            InterviewService.submit_answer(
                db=db,
                user_id=user_id,
                interview_id=interview_id,
                answer=answer,
                question_index=question_index,
                ai_config=ai_config,
            )
        )
        try:
            deadline = asyncio.get_running_loop().time() + ANSWER_STREAM_TOTAL_TIMEOUT_SECONDS
            while not task.done():
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    raise asyncio.TimeoutError()
                done, _ = await asyncio.wait(
                    {task},
                    timeout=min(ANSWER_STREAM_HEARTBEAT_SECONDS, remaining),
                )
                if not done:
                    stage = "generating_report" if is_final_round else "evaluating"
                    content = "正在生成最终报告，若模型较慢会自动保留基础报告。" if is_final_round else "仍在评估本轮回答，系统会在超时前自动兜底。"
                    yield _event(
                        {
                            "type": "heartbeat",
                            "stage": stage,
                            "content": content,
                            "remaining_seconds": max(0, int(remaining)),
                        }
                    )
            result = task.result()
        except Exception as exc:
            try:
                await db.rollback()
            except Exception as rollback_exc:
                logger.warning("Submit answer stream rollback failed: %s", rollback_exc)
            error_message = InterviewService._format_answer_stream_error(exc)
            yield _event({"type": "error", "content": error_message})
            return

        for chunk in InterviewService._chunk_text(result.get("feedback", "")):
            yield _event({"type": "chunk", "content": chunk})
        yield _event({"type": "done", **result})

    @staticmethod
    async def get_report(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
    ) -> Dict:
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
                Interview.user_deleted_at.is_(None),
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")
        if interview.status != "completed":
            raise ValidationError(message="面试尚未完成")

        questions = InterviewService._serialize_questions(interview.questions_data or [])
        report_signals = InterviewService._build_report_signals(questions)
        report: Dict[str, Any] = {}
        if interview.report:
            try:
                report = json.loads(interview.report)
            except json.JSONDecodeError as exc:
                logger.warning("Stored interview report JSON is invalid: interview_id=%s error=%s", interview_id, exc)
                report = InterviewService._fallback_report_from_signals(
                    report_signals=report_signals,
                    reason="stored_report_invalid_json",
                    detail="历史报告 JSON 损坏，已基于面试记录返回基础报告。",
                )
        report = InterviewService._merge_report_defaults(
            report=report,
            report_signals=report_signals,
            interview_mode=interview.interview_mode,
        )
        difficulty = InterviewService._normalize_difficulty(getattr(interview, "difficulty", None))
        difficulty_profile = InterviewService._public_difficulty_profile(difficulty)
        report["difficulty"] = difficulty
        report["difficulty_profile"] = difficulty_profile
        if interview.resume_id and not report.get("resume_evaluation_snapshot"):
            resume = await db.get(Resume, interview.resume_id)
            if resume:
                resume_analysis = ensure_resume_evaluation_snapshot(
                    InterviewService._load_resume_analysis_payload(resume),
                    target_position=interview.target_position,
                )
                if resume_analysis.get("resume_evaluation_snapshot"):
                    report["resume_evaluation_snapshot"] = resume_analysis["resume_evaluation_snapshot"]
                if resume_analysis.get("matching_metrics") and not report.get("matching_metrics"):
                    report["matching_metrics"] = resume_analysis["matching_metrics"]
                if resume_analysis.get("ability_gap_profile") and not report.get("ability_gap_profile"):
                    report["ability_gap_profile"] = resume_analysis["ability_gap_profile"]
                if resume_analysis.get("learning_plan") and not report.get("learning_plan"):
                    report["learning_plan"] = resume_analysis["learning_plan"]

        return {
            "interview_id": interview.id,
            "resume_id": interview.resume_id,
            "target_position": interview.target_position,
            "overall_score": float(interview.overall_score) if interview.overall_score else 0,
            "total_questions": interview.total_questions,
            "interview_mode": interview.interview_mode,
            "difficulty": difficulty,
            "difficulty_profile": difficulty_profile,
            "company_archetype": difficulty_profile["company_archetype"],
            "question_strategy_summary": difficulty_profile["question_strategy_summary"],
            "rubric_summary": difficulty_profile["rubric_summary"],
            "data_contribution_consent": bool(getattr(interview, "data_contribution_consent", False)),
            "privacy_consent_snapshot": getattr(interview, "privacy_consent_snapshot", None),
            "knowledge_base": interview.knowledge_base_snapshot,
            "panel_snapshot": interview.panel_snapshot,
            "report": report,
        }

    @staticmethod
    async def set_case_data_contribution_consent(
        db: AsyncSession,
        current_user: User,
        interview_id: int,
        data_contribution_consent: bool,
    ) -> Dict[str, Any]:
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == current_user.id,
                Interview.user_deleted_at.is_(None),
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        consent = bool(data_contribution_consent)
        proposed_boundary = InterviewService._sample_boundary_from_snapshot(
            getattr(interview, "privacy_consent_snapshot", None),
            data_contribution_consent=True,
        )
        if consent and not InterviewService._is_real_sft_boundary(proposed_boundary):
            raise ValidationError(message="该案例不是真实授权训练样本，不能开启数据贡献授权")
        snapshot = privacy_consent_service.build_snapshot(
            current_user,
            data_contribution_consent=consent,
            source="case_data_contribution",
        )
        snapshot.update(
            {
                "interview_id": interview.id,
                "resume_id": interview.resume_id,
                "target_position": interview.target_position,
            }
        )
        interview.data_contribution_consent = consent
        interview.privacy_consent_snapshot = snapshot
        try:
            await db.commit()
            await db.refresh(interview)
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Update case data contribution consent failed: %s", exc)
            raise ValidationError(message="更新本次案例数据贡献授权失败，请稍后重试") from exc

        return {
            "interview_id": interview.id,
            "data_contribution_consent": bool(interview.data_contribution_consent),
            "privacy_consent_snapshot": interview.privacy_consent_snapshot,
        }

    @staticmethod
    async def set_case_data_contribution_consent_admin(
        db: AsyncSession,
        interview_id: int,
        data_contribution_consent: bool,
        reason: str,
        admin_email: str,
    ) -> Dict[str, Any]:
        interview = await db.get(Interview, interview_id)
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        consent = bool(data_contribution_consent)
        if consent and interview.status != "completed":
            raise ValidationError(message="只有已完成面试才能由后台补录数据贡献授权")
        cleaned_reason = (reason or "").strip()
        if consent and not cleaned_reason:
            raise ValidationError(message="管理员补授权必须填写原因")

        now = datetime.now(timezone.utc)
        existing_snapshot = interview.privacy_consent_snapshot if isinstance(interview.privacy_consent_snapshot, dict) else {}
        snapshot = {
            **existing_snapshot,
            "source": "admin_case_consent_override",
            "admin_override": True,
            "admin_email": admin_email,
            "admin_override_at": now.isoformat(),
            "admin_override_reason": cleaned_reason or "后台案例标注授权撤回",
            "interview_id": interview.id,
            "resume_id": interview.resume_id,
            "target_position": interview.target_position,
            "data_contribution_consent": consent,
            "data_contribution_consent_version": DATA_CONTRIBUTION_CONSENT_VERSION if consent else None,
            "sample_origin": "real_authorized" if consent else "not_authorized",
            "candidate_answer_source": "human" if consent else "unknown",
            "for_real_sft": consent,
            "for_training": consent,
            "for_competition_demo": False,
            "claim_boundary": (
                "管理员补录授权的已完成案例；可进入人工复核沉淀流程，但必须保留补授权审计来源。"
                if consent
                else "后台已撤回本案例数据贡献授权，不能进入训练/评测样本。"
            ),
        }
        interview.data_contribution_consent = consent
        interview.privacy_consent_snapshot = snapshot
        try:
            await db.commit()
            await db.refresh(interview)
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Admin update case data contribution consent failed: %s", exc)
            raise ValidationError(message="后台更新案例授权状态失败，请稍后重试") from exc

        return {
            "interview_id": interview.id,
            "data_contribution_consent": bool(interview.data_contribution_consent),
            "privacy_consent_snapshot": interview.privacy_consent_snapshot,
            "consent_source": "admin_case_consent_override",
            "admin_override": True,
            "admin_override_at": snapshot["admin_override_at"],
            "admin_override_reason": snapshot["admin_override_reason"],
        }

    @staticmethod
    async def get_interviews(
        db: AsyncSession,
        user_id: int,
    ) -> Dict:
        result = await db.execute(
            select(Interview)
            .where(
                Interview.user_id == user_id,
                Interview.user_deleted_at.is_(None),
            )
            .order_by(Interview.created_at.desc())
        )
        interviews = result.scalars().all()
        items = [
            {
                "interview_id": item.id,
                "resume_id": item.resume_id,
                "target_position": item.target_position,
                "difficulty": item.difficulty,
                "interview_mode": item.interview_mode or "single",
                "overall_score": float(item.overall_score) if item.overall_score else None,
                "total_questions": item.total_questions,
                "status": item.status,
                "data_contribution_consent": bool(getattr(item, "data_contribution_consent", False)),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in interviews
        ]
        return {"total": len(items), "items": items}

    @staticmethod
    async def get_interview_messages(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
    ) -> List[Dict]:
        interview_result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
                Interview.user_deleted_at.is_(None),
            )
        )
        interview = interview_result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.interview_id == interview_id)
            .order_by(InterviewMessage.id)
        )
        messages = result.scalars().all()
        items = [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "question_index": item.question_index,
                "score": float(item.score) if item.score else None,
                "feedback": item.feedback,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in messages
        ]
        difficulty = InterviewService._normalize_difficulty(getattr(interview, "difficulty", None))
        difficulty_profile = InterviewService._public_difficulty_profile(difficulty)
        return {
            "items": items,
            "status": interview.status,
            "current_question_index": interview.current_question_index,
            "total_questions": interview.total_questions,
            "interview_mode": interview.interview_mode,
            "difficulty": difficulty,
            "difficulty_profile": difficulty_profile,
            "company_archetype": difficulty_profile["company_archetype"],
            "question_strategy_summary": difficulty_profile["question_strategy_summary"],
            "rubric_summary": difficulty_profile["rubric_summary"],
        }

    @staticmethod
    async def delete_interview(
        db: AsyncSession,
        user_id: int,
        interview_id: int,
    ) -> Dict:
        result = await db.execute(
            select(Interview).where(
                Interview.id == interview_id,
                Interview.user_id == user_id,
                Interview.user_deleted_at.is_(None),
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        if interview.status == "completed":
            interview.user_deleted_at = datetime.now(timezone.utc)
            interview.user_deleted_reason = USER_DELETED_COMPLETED_INTERVIEW_REASON
            await db.commit()
            return {
                "message": "面试记录已从用户端删除，后台保留用于人工复核",
                "retained_for_review": True,
            }

        await db.execute(
            sql_delete(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
        )
        await db.delete(interview)
        await db.commit()
        return {"message": "面试记录已删除"}

    @staticmethod
    async def delete_interview_admin(
        db: AsyncSession,
        interview_id: int,
    ) -> Dict:
        interview = await db.get(Interview, interview_id)
        if not interview:
            raise NotFoundError(message="面试记录不存在")

        await db.execute(
            sql_delete(InterviewMessage).where(InterviewMessage.interview_id == interview_id)
        )
        await db.delete(interview)
        await db.commit()
        return {"message": "面试记录已删除"}


interview_service = InterviewService()
