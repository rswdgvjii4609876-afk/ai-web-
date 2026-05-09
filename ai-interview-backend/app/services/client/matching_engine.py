"""Lightweight resume-to-position matching metrics.

The competition route needs measurable signals without introducing a heavy
model stack before the demo is stable. This engine provides deterministic
keyword, TF-IDF/cosine, and rule scores, and leaves room for embedding scores
when an API-based vector layer is added later.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from app.constants.competition import POSITION_PROFILES


class MatchingEngine:
    VERSION = "lightweight_matching_v1"

    @classmethod
    def evaluate(
        cls,
        parsed_resume: Dict[str, Any],
        target_position: str,
        llm_analysis: Optional[Dict[str, Any]] = None,
        resume_evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        profile = cls._resolve_profile(target_position)
        resume_text = cls._resume_to_text(parsed_resume)
        profile_text = cls._profile_to_text(profile, target_position)
        keywords = cls._profile_keywords(profile, target_position)

        matched_keywords = cls._matched_keywords(resume_text, keywords)
        missing_keywords = [item for item in keywords if item not in matched_keywords]
        keyword_coverage_value = round(len(matched_keywords) / max(len(keywords), 1), 4)
        keyword_score = round(keyword_coverage_value * 100, 1)
        semantic_score = cls._tfidf_cosine_score(resume_text, profile_text)
        rule_score = cls._rule_score(
            parsed_resume=parsed_resume,
            keyword_score=keyword_score,
            semantic_score=semantic_score,
            llm_analysis=llm_analysis,
            resume_evidence=resume_evidence,
        )
        llm_score = cls._extract_llm_score(llm_analysis)
        final_score = round(
            keyword_score * 0.30
            + semantic_score * 0.30
            + rule_score * 0.30
            + (llm_score if llm_score is not None else rule_score) * 0.10,
            1,
        )
        ability_gap_profile = cls._ability_gap_profile(
            profile=profile,
            parsed_resume=parsed_resume,
            target_position=target_position,
            resume_evidence=resume_evidence,
        )

        return {
            "engine_version": cls.VERSION,
            "target_position": target_position,
            "matched_profile": {
                "job_id": profile.get("job_id"),
                "job_name": profile.get("job_name") or target_position,
                "category": profile.get("category") or "自定义岗位",
                "source": profile.get("_source") or "preset",
            },
            "keyword_coverage": {
                "score": keyword_coverage_value,
                "score_percent": keyword_score,
                "matched_count": len(matched_keywords),
                "total": len(keywords),
                "matched": matched_keywords[:12],
                "missing": missing_keywords[:12],
            },
            "tfidf_semantic_score": semantic_score,
            "semantic_score": semantic_score,
            "rule_score": rule_score,
            "llm_score_reference": llm_score,
            "final_score": final_score,
            "score_formula": "30% keyword coverage + 30% semantic similarity (embedding preferred, TF-IDF fallback) + 30% rule score + 10% LLM reference score",
            "evidence_basis": cls._evidence_basis(
                parsed_resume=parsed_resume,
                matched_keywords=matched_keywords,
                missing_keywords=missing_keywords,
                semantic_score=semantic_score,
                rule_score=rule_score,
                resume_evidence=resume_evidence,
            ),
            "embedding_status": "fallback_tfidf_no_candidate",
            "embedding_semantic_score": None,
            "semantic_backend": "tfidf",
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_error_code": "not_configured",
            "ability_gap_profile": ability_gap_profile,
            "learning_priority_summary": cls._learning_priority_summary(ability_gap_profile),
        }

    @classmethod
    def embedding_inputs(cls, parsed_resume: Dict[str, Any], target_position: str) -> Dict[str, str]:
        profile = cls._resolve_profile(target_position)
        return {
            "resume_text": cls._resume_to_text(parsed_resume),
            "profile_text": cls._profile_to_text(profile, target_position),
        }

    @staticmethod
    def recalculate_final_score(metrics: Dict[str, Any], semantic_score: float) -> float:
        keyword_score = ((metrics.get("keyword_coverage") or {}).get("score_percent")) or 0
        rule_score = metrics.get("rule_score") or 0
        llm_score = metrics.get("llm_score_reference")
        try:
            semantic = float(semantic_score)
        except (TypeError, ValueError):
            semantic = float(metrics.get("tfidf_semantic_score") or metrics.get("semantic_score") or 0)
        try:
            llm_component = float(llm_score) if llm_score is not None else float(rule_score)
        except (TypeError, ValueError):
            llm_component = float(rule_score or 0)
        return round(
            float(keyword_score) * 0.30
            + semantic * 0.30
            + float(rule_score) * 0.30
            + llm_component * 0.10,
            1,
        )

    @classmethod
    def _resolve_profile(cls, target_position: str) -> Dict[str, Any]:
        target = cls._normalize_text(target_position)
        for profile in POSITION_PROFILES:
            names = [
                profile.get("job_name", ""),
                profile.get("job_id", ""),
                *(profile.get("keywords") or []),
            ]
            if any(cls._normalize_text(name) and cls._normalize_text(name) in target for name in names):
                return dict(profile, _source="preset")
            if profile.get("job_name") and target and target in cls._normalize_text(profile.get("job_name")):
                return dict(profile, _source="preset")

        technical_terms = ["开发", "工程师", "算法", "测试", "后端", "前端", "数据", "java", "python", "ai"]
        if any(term in target for term in technical_terms):
            keywords = [
                "项目", "语言基础", "数据库", "缓存", "接口", "算法", "系统设计",
                "性能优化", "线上排障", "Docker", "SQL",
            ]
            category = "技术岗"
        else:
            keywords = ["沟通", "执行", "数据", "复盘", "协作", "项目", "流程", "结果", "表达"]
            category = "自定义岗位"
        return {
            "job_id": "custom_position",
            "job_name": target_position or "自定义岗位",
            "category": category,
            "core_skills": keywords[:6],
            "typical_tasks": ["结合岗位要求完成工作任务", "沉淀实践证据", "复盘改进"],
            "keywords": keywords,
            "evaluation_focus": ["岗位关键词命中", "实践经历证据", "表达逻辑和改进空间"],
            "_source": "fallback",
        }

    @staticmethod
    def _resume_to_text(parsed_resume: Dict[str, Any]) -> str:
        chunks: List[str] = []

        def walk(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                chunks.append(value)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            else:
                chunks.append(str(value))

        walk(parsed_resume or {})
        return " ".join(chunks)

    @staticmethod
    def _profile_to_text(profile: Dict[str, Any], target_position: str) -> str:
        parts: List[str] = [target_position or "", profile.get("job_name", "")]
        for key in ("core_skills", "typical_tasks", "keywords", "evaluation_focus", "interview_topics"):
            parts.extend(str(item) for item in profile.get(key) or [])
        return " ".join(parts)

    @staticmethod
    def _profile_keywords(profile: Dict[str, Any], target_position: str) -> List[str]:
        values: List[str] = []
        values.extend(profile.get("keywords") or [])
        values.extend(profile.get("core_skills") or [])
        if target_position:
            values.append(target_position)
        ordered: List[str] = []
        for value in values:
            item = str(value).strip()
            if item and item not in ordered:
                ordered.append(item)
        return ordered[:24]

    @classmethod
    def _ability_model(cls, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        model = profile.get("ability_model") or []
        if model:
            return [item for item in model if isinstance(item, dict)]
        keywords = profile.get("keywords") or profile.get("core_skills") or ["项目", "沟通", "执行"]
        return [
            {
                "ability_id": "custom_core_match",
                "name": "岗位核心能力匹配",
                "required_level": 3,
                "weight": 0.34,
                "keywords": keywords[:8],
                "evidence_hints": ["项目", "实践", "经历", "负责"],
                "improvability": 1.0,
            },
            {
                "ability_id": "custom_project_evidence",
                "name": "项目/实践证据",
                "required_level": 3,
                "weight": 0.33,
                "keywords": ["项目", "实习", "负责", "结果", "指标"],
                "evidence_hints": ["有项目结果", "有个人贡献"],
                "improvability": 1.1,
            },
            {
                "ability_id": "custom_expression",
                "name": "表达与复盘",
                "required_level": 3,
                "weight": 0.33,
                "keywords": ["复盘", "总结", "表达", "沟通", "改进"],
                "evidence_hints": ["能说明复盘和改进"],
                "improvability": 1.2,
            },
        ]

    @classmethod
    def _ability_gap_profile(
        cls,
        profile: Dict[str, Any],
        parsed_resume: Dict[str, Any],
        target_position: str,
        resume_evidence: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        resume_text = cls._resume_to_text(parsed_resume or {})
        evidence_text = " ".join([resume_text, cls._resume_to_text(resume_evidence or {})])
        ability_items = cls._ability_model(profile)
        results: List[Dict[str, Any]] = []
        weighted_total = 0.0
        weight_sum = 0.0

        for ability in ability_items:
            required_level = cls._bounded_float(ability.get("required_level"), default=3.0, lower=1.0, upper=5.0)
            weight = cls._bounded_float(ability.get("weight"), default=0.1, lower=0.01, upper=1.0)
            improvability = cls._bounded_float(ability.get("improvability"), default=1.0, lower=0.1, upper=2.0)
            keywords = cls._clean_string_list(ability.get("keywords"))
            evidence_hints = cls._clean_string_list(ability.get("evidence_hints"))
            matched_keywords = cls._matched_keywords(evidence_text, keywords)
            matched_hints = cls._matched_keywords(evidence_text, evidence_hints)
            keyword_ratio = len(matched_keywords) / max(len(keywords), 1)
            hint_bonus = min(len(matched_hints) * 0.35, 0.8)
            current_level = 1.0 + keyword_ratio * 3.2 + hint_bonus
            if matched_keywords and keyword_ratio >= 0.75:
                current_level += 0.3
            if not matched_keywords and not matched_hints:
                current_level = 1.0
            current_level = round(min(max(current_level, 1.0), 5.0), 1)
            gap = round(max(required_level - current_level, 0.0), 1)
            match_score = round(min(current_level / max(required_level, 1.0), 1.0) * 100, 1)
            priority_score = round(weight * gap * improvability * 20, 1)
            missing_keywords = [item for item in keywords if item not in matched_keywords]
            weighted_total += match_score * weight
            weight_sum += weight
            results.append(
                {
                    "ability_id": str(ability.get("ability_id") or ability.get("name") or "ability"),
                    "name": str(ability.get("name") or "岗位能力"),
                    "required_level": required_level,
                    "current_level": current_level,
                    "gap": gap,
                    "weight": round(weight, 3),
                    "improvability": improvability,
                    "priority_score": priority_score,
                    "match_score": match_score,
                    "matched_keywords": matched_keywords[:8],
                    "missing_keywords": missing_keywords[:8],
                    "evidence_basis": cls._ability_evidence_basis(
                        matched_keywords=matched_keywords,
                        matched_hints=matched_hints,
                        gap=gap,
                    ),
                }
            )

        sorted_items = sorted(results, key=lambda item: item["priority_score"], reverse=True)
        return {
            "engine_version": "ability_gap_v1",
            "target_position": target_position,
            "matched_profile": {
                "job_id": profile.get("job_id"),
                "job_name": profile.get("job_name") or target_position,
                "category": profile.get("category") or "自定义岗位",
            },
            "overall_match_score": round(weighted_total / max(weight_sum, 0.01), 1) if results else 0.0,
            "items": results,
            "top_gaps": [item for item in sorted_items if item["gap"] > 0][:5],
            "strengths": sorted(results, key=lambda item: item["match_score"], reverse=True)[:3],
            "priority_formula": "提升优先级 = 岗位重要性(权重) × 能力差距 × 可提升系数",
        }

    @staticmethod
    def _learning_priority_summary(ability_gap_profile: Dict[str, Any]) -> List[str]:
        summary: List[str] = []
        for item in (ability_gap_profile or {}).get("top_gaps") or []:
            name = item.get("name") or "岗位能力"
            missing = "、".join((item.get("missing_keywords") or [])[:4]) or "补充可验证证据"
            summary.append(
                f"优先补强{name}：当前 {item.get('current_level')} / 要求 {item.get('required_level')}，建议围绕 {missing} 准备学习任务和项目证据。"
            )
        return summary[:5]

    @staticmethod
    def _bounded_float(value: Any, default: float, lower: float, upper: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return round(min(max(number, lower), upper), 2)

    @staticmethod
    def _clean_string_list(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        result: List[str] = []
        for value in values:
            item = str(value).strip()
            if item and item not in result:
                result.append(item)
        return result

    @staticmethod
    def _ability_evidence_basis(
        matched_keywords: List[str],
        matched_hints: List[str],
        gap: float,
    ) -> str:
        if matched_keywords or matched_hints:
            evidence = "、".join([*matched_keywords[:4], *matched_hints[:2]])
            if gap > 0:
                return f"已有部分证据：{evidence}；但仍需补充更直接的项目、任务或结果证明。"
            return f"已有较充分证据：{evidence}。"
        return "简历中暂未识别到直接证据，后续应通过学习任务、项目补充或面试追问继续验证。"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", "", (text or "").lower())

    @classmethod
    def _matched_keywords(cls, resume_text: str, keywords: Iterable[str]) -> List[str]:
        normalized_resume = cls._normalize_text(resume_text)
        matched: List[str] = []
        for keyword in keywords:
            normalized = cls._normalize_text(str(keyword))
            if normalized and normalized in normalized_resume:
                matched.append(str(keyword))
        return matched

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        lowered = (text or "").lower()
        words = re.findall(r"[a-z0-9+#.-]{2,}", lowered)
        chinese = re.findall(r"[\u4e00-\u9fff]+", lowered)
        bigrams: List[str] = []
        for block in chinese:
            if len(block) == 1:
                bigrams.append(block)
            else:
                bigrams.extend(block[index : index + 2] for index in range(len(block) - 1))
        return [token for token in [*words, *bigrams] if token.strip()]

    @classmethod
    def _tfidf_cosine_score(cls, resume_text: str, profile_text: str) -> float:
        doc_tokens = [cls._tokenize(resume_text), cls._tokenize(profile_text)]
        if not doc_tokens[0] or not doc_tokens[1]:
            return 0.0
        vocabulary = sorted(set(doc_tokens[0]) | set(doc_tokens[1]))
        doc_freq = {
            term: sum(1 for tokens in doc_tokens if term in tokens)
            for term in vocabulary
        }

        def vector(tokens: List[str]) -> List[float]:
            counts = Counter(tokens)
            total = max(sum(counts.values()), 1)
            values: List[float] = []
            for term in vocabulary:
                tf = counts[term] / total
                idf = math.log((1 + len(doc_tokens)) / (1 + doc_freq[term])) + 1
                values.append(tf * idf)
            return values

        left = vector(doc_tokens[0])
        right = vector(doc_tokens[1])
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return round(min(max(numerator / (left_norm * right_norm), 0.0), 1.0) * 100, 1)

    @classmethod
    def _rule_score(
        cls,
        parsed_resume: Dict[str, Any],
        keyword_score: float,
        semantic_score: float,
        llm_analysis: Optional[Dict[str, Any]],
        resume_evidence: Optional[Dict[str, Any]],
    ) -> float:
        skills_count = len(parsed_resume.get("skills") or [])
        projects_count = len(parsed_resume.get("projects") or [])
        experience_count = len(parsed_resume.get("experience") or [])
        evidence = resume_evidence or {}
        metrics_count = len(evidence.get("metrics") or [])
        ambiguity_count = len(evidence.get("ambiguity_flags") or [])
        missing_evidence_count = len(evidence.get("missing_evidence_flags") or [])
        llm_score = cls._extract_llm_score(llm_analysis)

        completeness = min(100, 20 + skills_count * 8 + projects_count * 10 + experience_count * 12)
        evidence_strength = min(100, 45 + metrics_count * 12 + projects_count * 6 - ambiguity_count * 6 - missing_evidence_count * 8)
        llm_component = llm_score if llm_score is not None else 65

        return round(
            keyword_score * 0.28
            + semantic_score * 0.22
            + completeness * 0.20
            + evidence_strength * 0.20
            + llm_component * 0.10,
            1,
        )

    @staticmethod
    def _extract_llm_score(llm_analysis: Optional[Dict[str, Any]]) -> Optional[float]:
        if not isinstance(llm_analysis, dict):
            return None
        raw = llm_analysis.get("overall_score")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if value <= 10:
            value *= 10
        return round(max(0, min(value, 100)), 1)

    @staticmethod
    def _evidence_basis(
        parsed_resume: Dict[str, Any],
        matched_keywords: List[str],
        missing_keywords: List[str],
        semantic_score: float,
        rule_score: float,
        resume_evidence: Optional[Dict[str, Any]],
    ) -> List[str]:
        basis = [
            f"命中岗位关键词 {len(matched_keywords)} 个：{'、'.join(matched_keywords[:6]) or '暂无'}。",
            f"待补强关键词 {len(missing_keywords)} 个：{'、'.join(missing_keywords[:6]) or '暂无'}。",
            f"TF-IDF/余弦相似度为 {semantic_score}，规则评分为 {rule_score}。",
        ]
        project_count = len((parsed_resume or {}).get("projects") or [])
        experience_count = len((parsed_resume or {}).get("experience") or [])
        if project_count or experience_count:
            basis.append(f"简历中识别到项目 {project_count} 项、经历 {experience_count} 项，可用于面试追问。")
        evidence = resume_evidence or {}
        if evidence.get("ambiguity_flags"):
            basis.append("存在模糊表述，后续面试需继续追问责任边界、量化结果和个人贡献。")
        if evidence.get("missing_evidence_flags"):
            basis.append("存在缺证据点，报告结论需保持保守，不能把未证明经历当作事实。")
        return basis


matching_engine = MatchingEngine()
