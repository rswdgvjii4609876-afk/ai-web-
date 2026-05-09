"""Optional embedding-based semantic matching.

This layer is deliberately best-effort. Resume analysis must keep working when
an embedding provider is unavailable, unsupported, slow, or not configured.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError as OpenAIAuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)

from app.services.client.matching_engine import matching_engine

logger = logging.getLogger(__name__)


class EmbeddingMatchService:
    MAX_TEXT_CHARS = 6000

    @classmethod
    async def enrich_metrics(
        cls,
        metrics: Dict[str, Any],
        parsed_resume: Dict[str, Any],
        target_position: str,
        embedding_candidates: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        enhanced = cls._ensure_fallback_fields(metrics)
        candidates = [item for item in embedding_candidates or [] if item and item.get("api_key")]
        if not candidates:
            enhanced["embedding_status"] = "fallback_tfidf_no_candidate"
            enhanced["embedding_error_code"] = "not_configured"
            return enhanced

        inputs = matching_engine.embedding_inputs(parsed_resume, target_position)
        resume_text = cls._trim_input(inputs.get("resume_text") or "")
        profile_text = cls._trim_input(inputs.get("profile_text") or "")
        if not resume_text or not profile_text:
            enhanced["embedding_status"] = "fallback_tfidf_empty_input"
            enhanced["embedding_error_code"] = "empty_input"
            return enhanced

        last_error_code = "embedding_request_failed"
        last_candidate: Optional[Dict[str, Any]] = None
        for candidate in candidates:
            last_candidate = candidate
            model = (candidate.get("model") or "").strip()
            if not model:
                last_error_code = "model_not_configured"
                logger.info(
                    "Embedding candidate skipped because model is not configured: provider=%s",
                    candidate.get("provider"),
                )
                continue
            try:
                resume_vector, profile_vector = await cls._embed_pair(
                    candidate=candidate,
                    resume_text=resume_text,
                    profile_text=profile_text,
                )
                score = cls._cosine_score(resume_vector, profile_vector)
                return cls._apply_embedding_score(enhanced, candidate, score)
            except Exception as exc:  # noqa: BLE001 - provider failures must not break analysis.
                last_error_code = cls._error_code(exc)
                logger.warning(
                    "Embedding candidate failed, falling back if needed: provider=%s model=%s code=%s",
                    candidate.get("provider"),
                    model,
                    last_error_code,
                )

        enhanced["embedding_status"] = "fallback_tfidf_provider_failed"
        enhanced["embedding_error_code"] = last_error_code
        if last_candidate:
            enhanced["embedding_provider"] = last_candidate.get("provider")
            enhanced["embedding_model"] = last_candidate.get("model")
        return enhanced

    @classmethod
    def _ensure_fallback_fields(cls, metrics: Dict[str, Any]) -> Dict[str, Any]:
        enhanced = dict(metrics or {})
        tfidf_score = enhanced.get("tfidf_semantic_score")
        if tfidf_score is None:
            tfidf_score = enhanced.get("semantic_score")
        enhanced.setdefault("tfidf_semantic_score", tfidf_score)
        enhanced.setdefault("semantic_score", tfidf_score or 0)
        enhanced.setdefault("embedding_semantic_score", None)
        enhanced.setdefault("semantic_backend", "tfidf")
        enhanced.setdefault("embedding_provider", None)
        enhanced.setdefault("embedding_model", None)
        enhanced.setdefault("embedding_status", "fallback_tfidf_no_candidate")
        enhanced.setdefault("embedding_error_code", "not_configured")
        return enhanced

    @classmethod
    async def _embed_pair(
        cls,
        candidate: Dict[str, Any],
        resume_text: str,
        profile_text: str,
    ) -> tuple[List[float], List[float]]:
        client = AsyncOpenAI(
            api_key=candidate["api_key"],
            base_url=candidate.get("base_url"),
        )
        response = await client.embeddings.create(
            model=candidate["model"],
            input=[resume_text, profile_text],
        )
        vectors = [item.embedding for item in response.data]
        if len(vectors) < 2:
            raise ValueError("embedding_response_missing_vectors")
        return vectors[0], vectors[1]

    @classmethod
    def _apply_embedding_score(
        cls,
        metrics: Dict[str, Any],
        candidate: Dict[str, Any],
        score: float,
    ) -> Dict[str, Any]:
        enhanced = dict(metrics)
        enhanced["embedding_status"] = "embedding_used"
        enhanced["embedding_semantic_score"] = score
        enhanced["semantic_score"] = score
        enhanced["semantic_backend"] = f"{candidate.get('provider')}_embedding"
        enhanced["embedding_provider"] = candidate.get("provider")
        enhanced["embedding_model"] = candidate.get("model")
        enhanced["embedding_error_code"] = None
        enhanced["final_score"] = matching_engine.recalculate_final_score(enhanced, score)
        return enhanced

    @classmethod
    def _cosine_score(cls, left: Sequence[float], right: Sequence[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return round(min(max(numerator / (left_norm * right_norm), 0.0), 1.0) * 100, 1)

    @classmethod
    def _trim_input(cls, text: str) -> str:
        return (text or "").strip()[: cls.MAX_TEXT_CHARS]

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if isinstance(exc, (OpenAIAuthenticationError, PermissionDeniedError)):
            return "auth_error"
        if isinstance(exc, RateLimitError):
            return "rate_limited"
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return "connection_error"
        if isinstance(exc, BadRequestError):
            return "bad_request"
        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)
            if status_code in {401, 403}:
                return "auth_error"
            if status_code in {402, 429}:
                return "rate_limited"
            if status_code in {404, 422}:
                return "model_or_endpoint_unsupported"
            return f"provider_status_{status_code or 'error'}"
        if isinstance(exc, ValueError) and str(exc) == "embedding_response_missing_vectors":
            return "malformed_response"
        return "embedding_request_failed"


embedding_match_service = EmbeddingMatchService()
