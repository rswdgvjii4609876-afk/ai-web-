import asyncio

import pytest

from app.services.client.embedding_match_service import EmbeddingMatchService
from app.services.client.matching_engine import matching_engine


PARSED_RESUME = {
    "skills": ["Python", "FastAPI", "PostgreSQL", "Redis"],
    "projects": [
        {
            "name": "Backend service",
            "description": "Built FastAPI APIs with PostgreSQL indexes and Redis cache.",
        }
    ],
}


def _base_metrics():
    return matching_engine.evaluate(
        parsed_resume=PARSED_RESUME,
        target_position="Python后端开发工程师",
        llm_analysis={"overall_score": 8},
        resume_evidence={"metrics": ["latency -30%"]},
    )


def test_embedding_metrics_fallback_without_candidates():
    result = asyncio.run(
        EmbeddingMatchService.enrich_metrics(
            metrics=_base_metrics(),
            parsed_resume=PARSED_RESUME,
            target_position="Python后端开发工程师",
            embedding_candidates=[],
        )
    )

    assert result["semantic_backend"] == "tfidf"
    assert result["embedding_status"] == "fallback_tfidf_no_candidate"
    assert result["embedding_error_code"] == "not_configured"
    assert result["embedding_semantic_score"] is None
    assert 0 <= result["semantic_score"] <= 100
    assert 0 <= result["final_score"] <= 100


def test_embedding_metrics_uses_deepseek_when_candidate_succeeds(monkeypatch):
    async def fake_embed_pair(**kwargs):
        return [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]

    monkeypatch.setattr(EmbeddingMatchService, "_embed_pair", staticmethod(fake_embed_pair))

    result = asyncio.run(
        EmbeddingMatchService.enrich_metrics(
            metrics=_base_metrics(),
            parsed_resume=PARSED_RESUME,
            target_position="Python后端开发工程师",
            embedding_candidates=[
                {
                    "provider": "deepseek",
                    "api_key": "test-key",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-embedding-test",
                }
            ],
        )
    )

    assert result["semantic_backend"] == "deepseek_embedding"
    assert result["embedding_status"] == "embedding_used"
    assert result["embedding_provider"] == "deepseek"
    assert result["embedding_semantic_score"] == 100.0
    assert result["semantic_score"] == 100.0
    assert result["embedding_error_code"] is None
    assert 0 <= result["final_score"] <= 100


def test_embedding_metrics_falls_back_when_deepseek_fails(monkeypatch):
    async def fake_embed_pair(**kwargs):
        raise ValueError("provider does not support embeddings")

    monkeypatch.setattr(EmbeddingMatchService, "_embed_pair", staticmethod(fake_embed_pair))

    base = _base_metrics()
    result = asyncio.run(
        EmbeddingMatchService.enrich_metrics(
            metrics=base,
            parsed_resume=PARSED_RESUME,
            target_position="Python后端开发工程师",
            embedding_candidates=[
                {
                    "provider": "deepseek",
                    "api_key": "test-key",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-embedding-test",
                }
            ],
        )
    )

    assert result["semantic_backend"] == "tfidf"
    assert result["embedding_status"] == "fallback_tfidf_provider_failed"
    assert result["embedding_error_code"] == "embedding_request_failed"
    assert result["semantic_score"] == base["semantic_score"]
    assert result["embedding_semantic_score"] is None
    assert 0 <= result["final_score"] <= 100


def test_embedding_metrics_uses_openai_after_deepseek_failure(monkeypatch):
    async def fake_embed_pair(**kwargs):
        candidate = kwargs["candidate"]
        if candidate["provider"] == "deepseek":
            raise ValueError("provider does not support embeddings")
        return [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]

    monkeypatch.setattr(EmbeddingMatchService, "_embed_pair", staticmethod(fake_embed_pair))

    result = asyncio.run(
        EmbeddingMatchService.enrich_metrics(
            metrics=_base_metrics(),
            parsed_resume=PARSED_RESUME,
            target_position="Python后端开发工程师",
            embedding_candidates=[
                {
                    "provider": "deepseek",
                    "api_key": "test-key",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-embedding-test",
                },
                {
                    "provider": "openai",
                    "api_key": "test-key",
                    "base_url": "https://api.openai.com/v1",
                    "model": "text-embedding-3-small",
                },
            ],
        )
    )

    assert result["semantic_backend"] == "openai_embedding"
    assert result["embedding_status"] == "embedding_used"
    assert result["embedding_provider"] == "openai"
    assert result["embedding_model"] == "text-embedding-3-small"
    assert result["embedding_semantic_score"] == 100.0
    assert 0 <= result["final_score"] <= 100


def test_embedding_metrics_skips_candidate_without_model():
    result = asyncio.run(
        EmbeddingMatchService.enrich_metrics(
            metrics=_base_metrics(),
            parsed_resume=PARSED_RESUME,
            target_position="Python后端开发工程师",
            embedding_candidates=[
                {
                    "provider": "deepseek",
                    "api_key": "test-key",
                    "base_url": "https://api.deepseek.com",
                    "model": "",
                }
            ],
        )
    )

    assert result["semantic_backend"] == "tfidf"
    assert result["embedding_status"] == "fallback_tfidf_provider_failed"
    assert result["embedding_error_code"] == "model_not_configured"
    assert result["embedding_provider"] == "deepseek"
