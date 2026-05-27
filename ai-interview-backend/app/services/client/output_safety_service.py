import re
from typing import Any


INTERNAL_PROMPT_LEAK_PATTERN = re.compile(
    r"Blueprint\s+priority|blueprint[_\s-]*track|blueprint[_\s-]*priority|"
    r"role[_\s-]*calibration|Question\s+plan|Question\s+reason|"
    r"Question\s+target\s+gap|Evaluation\s+focus|Interview\s+routing\s+context|"
    r"Interview\s+blueprint|Internal\s+panel|Internal\s+roles|Moderator\s+name|"
    r"Plan\s*#|Lead\s+role|Support\s+roles|Requirement\s+status|"
    r"Candidate\s+evidence|Suggested\s+followups|question_plan|"
    r"candidate_evidence|verification_reason|stage/category/intent|"
    r"lead_role|support_roles|assessment_points|selected_questions|"
    r"used_slice_ids|routed[_\s-]*slice|routed\s+slices|evaluation_focus|"
    r"selected_followups|chain[-\s]?of[-\s]?thought|题目计划|评估重点|"
    r"主持人推理|内部面板|内部字段|候选人证据|蓝图优先级|链式思考|"
    r"\b(stage|category|intent|moderator|schema|step|type|goal|priority|focus|blueprint)\b\s*[:=]",
    re.IGNORECASE,
)


class OutputSafetyService:
    @staticmethod
    def has_internal_prompt_leak(value: Any) -> bool:
        return bool(INTERNAL_PROMPT_LEAK_PATTERN.search(str(value or "")))

    @staticmethod
    def sanitize_public_text(
        value: Any,
        *,
        fallback: str = "内容生成异常：系统已拦截内部调试信息，请重新生成。",
    ) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if OutputSafetyService.has_internal_prompt_leak(text):
            return fallback
        return text


output_safety_service = OutputSafetyService()
