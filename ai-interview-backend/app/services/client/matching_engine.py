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
from typing import Any, Callable, Dict, Iterable, List, Optional

from app.constants.competition import POSITION_PROFILES
from app.constants.learning_routes import AI_LEARNING_LOOP, match_learning_route_stage

RouteStageResolver = Callable[[str, str, Optional[str]], Optional[Dict[str, Any]]]


class MatchingEngine:
    VERSION = "lightweight_matching_v1"
    KEYWORD_ALIASES: Dict[str, List[str]] = {
        "sql": ["mysql", "postgresql", "sqlite", "数据库", "索引", "事务", "查询", "sqlalchemy", "orm"],
        "mysql": ["sql", "数据库", "索引", "事务"],
        "postgresql": ["sql", "数据库", "索引", "事务"],
        "数据库": ["sql", "mysql", "postgresql", "索引", "事务", "查询", "orm"],
        "fastapi": ["pythonweb", "python web", "后端接口", "接口开发", "api", "rest", "django", "flask"],
        "python": ["py", "pandas", "脚本", "自动化脚本"],
        "redis": ["缓存", "cache", "分布式锁", "缓存一致性", "kv"],
        "缓存": ["redis", "cache", "缓存一致性"],
        "docker": ["容器", "容器化", "compose", "dockercompose", "部署"],
        "celery": ["异步任务", "任务队列", "消息队列", "队列"],
        "异步": ["async", "asyncio", "异步任务", "celery"],
        "接口": ["api", "rest", "http", "后端接口", "接口设计", "接口开发"],
        "http": ["接口", "api", "rest", "网络"],
        "并发": ["线程", "多线程", "协程", "asyncio", "并行"],
        "系统设计": ["架构", "高并发", "可扩展", "限流", "降级", "分布式"],
        "线上排障": ["排障", "故障", "日志", "监控", "定位问题", "debug", "troubleshooting"],
        "java": ["jvm", "spring", "spring boot", "springboot", "后端"],
        "spring": ["spring boot", "springboot", "spring mvc", "spring cloud", "java后端"],
        "jvm": ["gc", "垃圾回收", "内存", "虚拟机", "java"],
        "线程": ["并发", "多线程", "线程池", "thread", "executor"],
        "消息队列": ["mq", "kafka", "rabbitmq", "rocketmq", "celery", "队列"],
        "javascript": ["js", "typescript", "ts", "ecmascript"],
        "typescript": ["javascript", "js", "ts"],
        "vue": ["vue2", "vue3", "vue.js", "pinia", "vuex"],
        "react": ["react.js", "hooks", "next.js"],
        "测试用例": ["用例设计", "测试设计", "testcase", "case design"],
        "接口测试": ["api测试", "postman", "pytest", "自动化测试"],
        "自动化": ["pytest", "selenium", "playwright", "自动化测试", "脚本"],
        "机器学习": ["ml", "sklearn", "scikit-learn", "模型", "算法"],
        "深度学习": ["dl", "pytorch", "tensorflow", "神经网络"],
        "embedding": ["向量", "语义向量", "rag", "检索增强"],
        "excel": ["表格", "数据透视表", "vlookup", "函数", "透视表"],
        "可视化": ["dashboard", "图表", "bi", "tableau", "powerbi", "报表"],
        "产品": ["prd", "原型", "用户故事", "需求"],
        "需求": ["需求分析", "prd", "用户故事", "痛点"],
        "原型": ["axure", "figma", "墨刀", "交互稿"],
        "运营": ["活动", "用户增长", "社群", "内容", "转化"],
        "招聘": ["候选人", "简历筛选", "邀约", "面试安排"],
        "行政": ["会议", "办公软件", "资产", "采购", "流程"],
    }

    @classmethod
    def evaluate(
        cls,
        parsed_resume: Dict[str, Any],
        target_position: str,
        llm_analysis: Optional[Dict[str, Any]] = None,
        resume_evidence: Optional[Dict[str, Any]] = None,
        route_stage_resolver: Optional[RouteStageResolver] = None,
    ) -> Dict[str, Any]:
        profile = cls._resolve_profile(target_position)
        resume_text = cls._resume_to_text(parsed_resume)
        profile_text = cls._profile_to_text(profile, target_position)
        keywords = cls._profile_keywords(profile, target_position)

        keyword_breakdown = cls._keyword_match_breakdown(
            parsed_resume=parsed_resume,
            resume_evidence=resume_evidence,
            keywords=keywords,
        )
        matched_keywords = keyword_breakdown["matched"]
        missing_keywords = keyword_breakdown["missing"]
        keyword_coverage_value = round(keyword_breakdown["weighted_score"] / 100, 4)
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
            keyword_score * 0.20
            + semantic_score * 0.35
            + rule_score * 0.30
            + (llm_score if llm_score is not None else rule_score) * 0.15,
            1,
        )
        ability_gap_profile = cls._ability_gap_profile(
            profile=profile,
            parsed_resume=parsed_resume,
            target_position=target_position,
            resume_evidence=resume_evidence,
        )
        learning_plan = cls._build_learning_plan(
            ability_gap_profile=ability_gap_profile,
            profile=profile,
            target_position=target_position,
            route_stage_resolver=route_stage_resolver,
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
                "direct_matches": keyword_breakdown["direct_matches"][:12],
                "related_matches": keyword_breakdown["related_matches"][:12],
                "verification_needed": keyword_breakdown["verification_needed"][:12],
                "evidence_statuses": keyword_breakdown["evidence_statuses"][:24],
            },
            "tfidf_semantic_score": semantic_score,
            "semantic_score": semantic_score,
            "rule_score": rule_score,
            "llm_score_reference": llm_score,
            "final_score": final_score,
            "score_formula": "20% normalized keyword evidence + 35% semantic similarity (embedding preferred, TF-IDF fallback) + 30% rule score + 15% LLM reference score",
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
            "learning_plan": learning_plan,
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
            float(keyword_score) * 0.20
            + semantic * 0.35
            + float(rule_score) * 0.30
            + llm_component * 0.15,
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

    @classmethod
    def _resume_evidence_sections(
        cls,
        parsed_resume: Dict[str, Any],
        resume_evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        proof_keys = (
            "projects",
            "project_experience",
            "experience",
            "work_experience",
            "internships",
            "employment",
            "jobs",
            "research",
            "portfolio",
        )
        claim_keys = (
            "skills",
            "technical_skills",
            "summary",
            "certifications",
            "education",
            "awards",
        )
        proof_parts = [cls._resume_to_text(parsed_resume.get(key) or {}) for key in proof_keys if isinstance(parsed_resume, dict)]
        claim_parts = [cls._resume_to_text(parsed_resume.get(key) or {}) for key in claim_keys if isinstance(parsed_resume, dict)]
        evidence = resume_evidence if isinstance(resume_evidence, dict) else {}
        proof_parts.extend(cls._resume_to_text(evidence.get(key) or {}) for key in ("projects", "metrics", "followup_candidates"))
        claim_parts.extend(cls._resume_to_text(evidence.get(key) or {}) for key in ("skills", "ambiguity_flags", "missing_evidence_flags"))
        all_text = cls._resume_to_text(parsed_resume or {})
        if evidence:
            all_text = " ".join([all_text, cls._resume_to_text(evidence)])
        return {
            "proof": " ".join(part for part in proof_parts if part),
            "claim": " ".join(part for part in claim_parts if part),
            "all": all_text,
        }

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
    def _keyword_terms(cls, keyword: str) -> List[str]:
        base = str(keyword or "").strip()
        normalized = cls._normalize_text(base)
        aliases = list(cls.KEYWORD_ALIASES.get(normalized, []))
        for key, values in cls.KEYWORD_ALIASES.items():
            if normalized in [cls._normalize_text(value) for value in values] and key not in aliases:
                aliases.append(key)
        terms: List[str] = []
        for item in [base, *aliases]:
            text = str(item or "").strip()
            if text and text not in terms:
                terms.append(text)
        return terms

    @classmethod
    def _contains_term(cls, text: str, term: str) -> bool:
        normalized_term = cls._normalize_text(term)
        return bool(normalized_term and normalized_term in cls._normalize_text(text or ""))

    @classmethod
    def _keyword_evidence_status(cls, sections: Dict[str, str], keyword: str) -> Dict[str, Any]:
        terms = cls._keyword_terms(keyword)
        base = terms[0] if terms else str(keyword)
        aliases = terms[1:]
        direct_terms = [term for term in [base] if cls._contains_term(sections.get("proof", ""), term)]
        related_terms = [term for term in aliases if cls._contains_term(sections.get("proof", ""), term)]
        claimed_terms = [
            term for term in terms
            if cls._contains_term(sections.get("claim", ""), term)
            or (cls._contains_term(sections.get("all", ""), term) and term not in direct_terms and term not in related_terms)
        ]
        if direct_terms:
            status = "direct"
            weight = 1.0
            matched_term = direct_terms[0]
        elif related_terms:
            status = "indirect"
            weight = 0.75
            matched_term = related_terms[0]
        elif claimed_terms:
            status = "claimed_only"
            weight = 0.45
            matched_term = claimed_terms[0]
        else:
            status = "missing"
            weight = 0.0
            matched_term = ""
        return {
            "keyword": str(keyword),
            "status": status,
            "matched_term": matched_term,
            "matched_terms": [*direct_terms, *related_terms, *claimed_terms],
            "weight": weight,
        }

    @classmethod
    def _keyword_match_breakdown(
        cls,
        parsed_resume: Dict[str, Any],
        resume_evidence: Optional[Dict[str, Any]],
        keywords: List[str],
    ) -> Dict[str, Any]:
        sections = cls._resume_evidence_sections(parsed_resume, resume_evidence)
        statuses = [cls._keyword_evidence_status(sections, keyword) for keyword in keywords]
        direct = [item["keyword"] for item in statuses if item["status"] == "direct"]
        related = [item["keyword"] for item in statuses if item["status"] == "indirect"]
        verification = [item["keyword"] for item in statuses if item["status"] == "claimed_only"]
        missing = [item["keyword"] for item in statuses if item["status"] == "missing"]
        weighted_score = round(sum(item["weight"] for item in statuses) / max(len(statuses), 1) * 100, 1)
        return {
            "weighted_score": weighted_score,
            "matched": [*direct, *related, *verification],
            "direct_matches": direct,
            "related_matches": related,
            "verification_needed": verification,
            "missing": missing,
            "evidence_statuses": statuses,
        }

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
            keyword_breakdown = cls._keyword_match_breakdown(
                parsed_resume=parsed_resume or {},
                resume_evidence=resume_evidence,
                keywords=keywords,
            )
            direct_keywords = keyword_breakdown["direct_matches"]
            related_keywords = keyword_breakdown["related_matches"]
            verification_keywords = keyword_breakdown["verification_needed"]
            matched_keywords = keyword_breakdown["matched"]
            matched_hints = cls._matched_keywords(evidence_text, evidence_hints)
            keyword_ratio = keyword_breakdown["weighted_score"] / 100
            proof_ratio = (len(direct_keywords) + len(related_keywords) * 0.75) / max(len(keywords), 1)
            claimed_ratio = len(verification_keywords) / max(len(keywords), 1)
            hint_bonus = min(len(matched_hints) * 0.35, 0.8)
            current_level = 1.0 + proof_ratio * 3.0 + claimed_ratio * 1.0 + hint_bonus
            if matched_keywords and proof_ratio >= 0.75:
                current_level += 0.3
            if not matched_keywords and not matched_hints:
                current_level = 1.0
            if verification_keywords and not direct_keywords and not related_keywords:
                current_level = min(current_level, 2.3)
            current_level = round(min(max(current_level, 1.0), 5.0), 1)
            gap = round(max(required_level - current_level, 0.0), 1)
            match_score = round(min(current_level / max(required_level, 1.0), 1.0) * 100, 1)
            verification_bonus = 0.7 if verification_keywords else 0.3 if related_keywords and gap > 0 else 0.0
            priority_score = round(weight * (gap + verification_bonus) * improvability * 20, 1)
            missing_keywords = keyword_breakdown["missing"]
            evidence_status = cls._ability_evidence_status(
                direct_keywords=direct_keywords,
                related_keywords=related_keywords,
                verification_keywords=verification_keywords,
                missing_keywords=missing_keywords,
            )
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
                    "direct_matches": direct_keywords[:8],
                    "related_matches": related_keywords[:8],
                    "verification_keywords": verification_keywords[:8],
                    "missing_keywords": missing_keywords[:8],
                    "evidence_status": evidence_status,
                    "verification_priority": cls._verification_priority(evidence_status, priority_score),
                    "interview_probe_reason": cls._interview_probe_reason(
                        ability_name=str(ability.get("name") or "岗位能力"),
                        evidence_status=evidence_status,
                        verification_keywords=verification_keywords,
                        related_keywords=related_keywords,
                        missing_keywords=missing_keywords,
                    ),
                    "evidence_basis": cls._ability_evidence_basis(
                        direct_keywords=direct_keywords,
                        related_keywords=related_keywords,
                        verification_keywords=verification_keywords,
                        missing_keywords=missing_keywords,
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

    @classmethod
    def _build_learning_plan(
        cls,
        ability_gap_profile: Dict[str, Any],
        profile: Dict[str, Any],
        target_position: str,
        route_stage_resolver: Optional[RouteStageResolver] = None,
    ) -> Dict[str, Any]:
        top_gaps = (ability_gap_profile or {}).get("top_gaps") or []
        if not top_gaps:
            items = sorted(
                (ability_gap_profile or {}).get("items") or [],
                key=lambda item: item.get("priority_score") or 0,
                reverse=True,
            )
            top_gaps = items[:5]

        tasks: List[Dict[str, Any]] = []
        for index, item in enumerate(top_gaps[:5], start=1):
            task = cls._build_learning_task(
                item=item,
                profile=profile,
                target_position=target_position,
                rank=index,
                route_stage_resolver=route_stage_resolver,
            )
            if task:
                tasks.append(task)

        return {
            "version": "learning_plan_v1",
            "target_position": target_position,
            "matched_profile": (ability_gap_profile or {}).get("matched_profile")
            or {
                "job_id": profile.get("job_id"),
                "job_name": profile.get("job_name") or target_position,
                "category": profile.get("category"),
            },
            "source_ability_gap_engine": (ability_gap_profile or {}).get("engine_version") or "ability_gap_v1",
            "progress_storage": "server_account_learning_tasks_json_backup",
            "task_count": len(tasks),
            "tasks": tasks,
            "summary": [
                f"已根据 {target_position or '目标岗位'} 的能力差距生成 {len(tasks)} 个优先学习任务。",
                "学习任务保存到当前账号，JSON 导入导出只作为备份和迁移。",
            ],
        }

    @classmethod
    def _build_learning_task(
        cls,
        item: Dict[str, Any],
        profile: Dict[str, Any],
        target_position: str,
        rank: int,
        route_stage_resolver: Optional[RouteStageResolver] = None,
    ) -> Dict[str, Any]:
        ability_id = str(item.get("ability_id") or f"ability_{rank}")
        ability_name = str(item.get("name") or "岗位能力")
        missing_keywords = cls._clean_string_list(item.get("missing_keywords"))
        matched_keywords = cls._clean_string_list(item.get("matched_keywords"))
        route = cls._learning_route(
            profile=profile,
            ability_name=ability_name,
            missing_keywords=missing_keywords,
            target_position=target_position,
            route_stage_resolver=route_stage_resolver,
        )
        material_type = route.get("material_type") or route["task_type"]
        material = route["material"]
        focus_terms = missing_keywords[:4] or matched_keywords[:4] or [ability_name]
        focus_text = "、".join(focus_terms)
        priority_score = cls._bounded_float(item.get("priority_score"), default=0.0, lower=0.0, upper=100.0)
        practice_task = route.get("practice_task") or cls._learning_task_practice(
            route=route,
            ability_name=ability_name,
            focus_text=focus_text,
        )
        deliverable = cls._learning_task_deliverable(route=route, ability_name=ability_name)
        acceptance_criteria = route.get("acceptance_criteria") or cls._learning_task_acceptance(route=route)

        return {
            "task_id": f"{profile.get('job_id') or 'custom'}_{ability_id}_{rank}",
            "ability_id": ability_id,
            "ability_name": ability_name,
            "title": f"补强{ability_name}",
            "material_type": material_type,
            "route_source": route["route_source"],
            "route_stage": route["route_stage"],
            "task_type": route["task_type"],
            "learning_material": material,
            "practice_task": practice_task,
            "deliverable": deliverable,
            "estimated_hours": "2-4 小时",
            "estimated_minutes": route["estimated_minutes"],
            "acceptance_criteria": acceptance_criteria,
            "priority_score": priority_score,
            "priority_rank": rank,
            "evidence_basis": item.get("evidence_basis") or "由能力差距模型根据简历证据和岗位画像生成。",
            "current_level": item.get("current_level"),
            "required_level": item.get("required_level"),
            "gap": item.get("gap"),
            "task_metadata": {
                "route_stage_title": route["title"],
                "learning_loop": AI_LEARNING_LOOP,
                "source_route_files": ["python后端学习路线.md", "python基础学习路线.md"]
                if route["route_source"].startswith("project_builtin_python")
                else ["岗位画像知识库"],
            },
        }

    @classmethod
    def _learning_route(
        cls,
        profile: Dict[str, Any],
        ability_name: str,
        missing_keywords: List[str],
        target_position: str,
        route_stage_resolver: Optional[RouteStageResolver] = None,
    ) -> Dict[str, Any]:
        job_id = str(profile.get("job_id") or "")
        category = str(profile.get("category") or "")
        text = cls._normalize_text(" ".join([ability_name, target_position, *missing_keywords]))
        if route_stage_resolver:
            route = route_stage_resolver(job_id, text, category)
            if route:
                return route
        return match_learning_route_stage(job_id=job_id, text=text, category=category)

    @staticmethod
    def _learning_task_practice(route: Dict[str, Any], ability_name: str, focus_text: str) -> str:
        task_type = route.get("task_type")
        if task_type == "document_output":
            return f"围绕 {focus_text} 产出一份可提交文档：包含背景、处理步骤、关键判断和最终结论。"
        if task_type == "scenario_practice":
            return f"围绕 {focus_text} 写出一个真实工作场景处理方案：说明目标、沟通对象、流程节点和风险兜底。"
        if task_type == "case_practice":
            return f"围绕 {focus_text} 拆解一个案例：写清问题、判断依据、行动方案、验证指标和复盘结论。"
        if task_type == "theory_case":
            return f"围绕 {focus_text} 整理规则或基础知识，并配 1 个情景案例说明如何应用。"
        if task_type == "project_review":
            return f"围绕 {focus_text} 复盘一个项目或练习经历：讲清背景、个人贡献、问题定位和改进结果。"
        return f"围绕 {focus_text} 完成一次可展示练习：整理知识点、写出一个小 Demo 或复盘一个相关项目经历。"

    @staticmethod
    def _learning_task_deliverable(route: Dict[str, Any], ability_name: str) -> str:
        task_type = route.get("task_type")
        if task_type in {"document_output", "scenario_practice", "case_practice", "theory_case"}:
            return f"形成一份不少于 300 字的任务记录，并准备 1 个能在面试中讲清楚的 {ability_name} 场景证据。"
        return f"形成一份不少于 300 字的学习记录，并准备 1 个能在面试中讲清楚的 {ability_name} 证据。"

    @staticmethod
    def _learning_task_acceptance(route: Dict[str, Any]) -> List[str]:
        task_type = route.get("task_type")
        if task_type == "document_output":
            return ["文档结构完整，包含背景、步骤、判断和结论。", "能说明文档如何服务目标岗位工作。", "能回答一轮追问，并指出下一步补强点。"]
        if task_type == "scenario_practice":
            return ["能说清场景目标、参与角色和流程节点。", "能给出沟通话术或处理步骤。", "能说明风险兜底和复盘改进。"]
        if task_type == "case_practice":
            return ["能拆清问题、依据、行动和结果。", "能用指标或证据说明方案是否有效。", "能回答一轮追问，并说明下一次怎么改。"]
        if task_type == "theory_case":
            return ["能解释关键规则或基础概念。", "能用一个岗位场景说明如何应用。", "能指出常见风险或注意事项。"]
        return ["能用自己的话解释核心概念、适用场景和常见问题。", "能给出与简历或目标岗位相关的项目/任务证据。", "能回答一轮追问，并说明下一步改进计划。"]

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
        direct_keywords: List[str],
        related_keywords: List[str],
        verification_keywords: List[str],
        missing_keywords: List[str],
        matched_hints: List[str],
        gap: float,
    ) -> str:
        if direct_keywords:
            evidence = "、".join([*direct_keywords[:4], *matched_hints[:2]])
            if gap > 0:
                return f"已有直接证据：{evidence}；仍需通过面试确认掌握深度、责任边界和结果。"
            return f"已有较充分直接证据：{evidence}。"
        if related_keywords:
            evidence = "、".join([*related_keywords[:4], *matched_hints[:2]])
            return f"已有间接相关证据：{evidence}；不能直接等同于完全掌握，建议面试追问迁移能力。"
        if verification_keywords:
            evidence = "、".join(verification_keywords[:4])
            return f"简历声明涉及：{evidence}；但缺少项目、职责或结果支撑，应通过面试验证掌握程度。"
        if missing_keywords:
            evidence = "、".join(missing_keywords[:4])
            return f"简历暂未提供足够证据：{evidence}；建议用基础理解题和场景题继续验证。"
        return "简历中暂未识别到直接证据，后续应通过学习任务、项目补充或面试追问继续验证。"

    @staticmethod
    def _ability_evidence_status(
        direct_keywords: List[str],
        related_keywords: List[str],
        verification_keywords: List[str],
        missing_keywords: List[str],
    ) -> str:
        if direct_keywords and not missing_keywords:
            return "direct"
        if direct_keywords or related_keywords:
            return "indirect"
        if verification_keywords:
            return "claimed_only"
        return "missing"

    @staticmethod
    def _verification_priority(evidence_status: str, priority_score: float) -> str:
        if evidence_status in {"claimed_only", "indirect"}:
            return "high" if priority_score >= 12 else "medium"
        if evidence_status == "missing":
            return "medium" if priority_score >= 10 else "low"
        return "low"

    @staticmethod
    def _interview_probe_reason(
        ability_name: str,
        evidence_status: str,
        verification_keywords: List[str],
        related_keywords: List[str],
        missing_keywords: List[str],
    ) -> str:
        if evidence_status == "claimed_only":
            terms = "、".join(verification_keywords[:4]) or ability_name
            return f"简历声明涉及 {terms}，但缺少项目或职责证据，面试需验证真实掌握程度。"
        if evidence_status == "indirect":
            terms = "、".join(related_keywords[:4]) or ability_name
            return f"简历存在 {terms} 等间接证据，面试需追问是否能迁移到目标岗位要求。"
        if evidence_status == "missing":
            terms = "、".join(missing_keywords[:4]) or ability_name
            return f"简历暂未提供 {terms} 的明确证据，面试需用基础理解和场景题确认学习空间。"
        return f"简历已有较直接证据，面试可继续深挖 {ability_name} 的责任边界、技术取舍和结果。"

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
            keyword_score * 0.18
            + semantic_score * 0.27
            + completeness * 0.20
            + evidence_strength * 0.25
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
