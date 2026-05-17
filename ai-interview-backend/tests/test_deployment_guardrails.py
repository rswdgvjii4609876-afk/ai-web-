import pytest
from pathlib import Path


def _install_fake_redis(monkeypatch):
    import sys
    import types

    redis_module = types.ModuleType("redis")
    asyncio_module = types.ModuleType("redis.asyncio")

    class Redis:
        def __init__(self, *args, **kwargs):
            pass

        async def ping(self):
            return True

        async def close(self):
            return None

    asyncio_module.Redis = Redis
    redis_module.asyncio = asyncio_module
    monkeypatch.setitem(sys.modules, "redis", redis_module)
    monkeypatch.setitem(sys.modules, "redis.asyncio", asyncio_module)


def test_production_settings_fail_fast_on_placeholder_values():
    from app.core.config import Settings

    with pytest.raises(ValueError, match="Invalid production configuration"):
        Settings(
            ENV="production",
            BACKEND_CORS_ORIGINS="https://example.com",
            SECRET_KEY="your-secret-key-change-in-production",
            POSTGRES_PASSWORD="demo123",
            REDIS_PASSWORD="",
        )


def test_production_settings_accept_explicit_required_values():
    from app.core.config import Settings

    settings = Settings(
        ENV="production",
        FRONTEND_URL="https://example.com",
        BACKEND_CORS_ORIGINS="https://example.com,https://admin.example.com",
        SECRET_KEY="x" * 64,
        POSTGRES_USER="app_user",
        POSTGRES_PASSWORD="postgres-password",
        POSTGRES_DB="ai_interview",
        REDIS_PASSWORD="redis-password",
        DEEPSEEK_API_KEY="deepseek-key",
        CELERY_WORKER_CONCURRENCY=2,
        CELERY_WORKER_REPLICAS=1,
    )

    assert settings.get_cors_origins() == ["https://example.com", "https://admin.example.com"]
    assert settings.CELERY_WORKER_CONCURRENCY == 2


def test_alembic_health_requires_current_head(monkeypatch):
    _install_fake_redis(monkeypatch)

    from app.api.client.v1 import config as health_config

    monkeypatch.setattr(health_config, "_get_expected_alembic_heads", lambda: {"head"})

    assert health_config._build_migration_check({"head"})["status"] == "up"

    stale = health_config._build_migration_check({"old"})
    assert stale["status"] == "down"
    assert stale["missing"] == ["head"]
    assert stale["unexpected"] == ["old"]


def test_production_app_hides_docs_and_public_resume_uploads(monkeypatch):
    _install_fake_redis(monkeypatch)

    from app.route import route as route_module
    from app.route import router_registry

    monkeypatch.setattr(route_module.settings, "ENV", "production")
    monkeypatch.setattr(router_registry, "get_client_routes", lambda: [])
    monkeypatch.setattr(router_registry, "get_backoffice_routes", lambda: [])
    monkeypatch.setattr(router_registry, "get_common_routes", lambda: [])

    app = route_module.create_app()
    mounted_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/client" not in mounted_paths
    assert "/backoffice" not in mounted_paths
    assert "/api-docs" not in mounted_paths
    assert "/uploads" not in mounted_paths
    assert "/uploads/avatars" in mounted_paths


def test_nginx_configs_do_not_proxy_docs_prefixes():
    project_root = Path(__file__).resolve().parents[2]
    for relative_path in (
        "ai-interview-frontend/nginx.conf",
        "ai-interview-admin/nginx.conf",
    ):
        content = (project_root / relative_path).read_text(encoding="utf-8")
        assert "location ^~ /client/" in content
        assert "location ^~ /backoffice/" in content

        client_block = content.split("location ^~ /client/", 1)[1].split("}", 1)[0]
        backoffice_block = content.split("location ^~ /backoffice/", 1)[1].split("}", 1)[0]
        assert "return 404" in client_block
        assert "return 404" in backoffice_block
        assert "proxy_pass" not in client_block
        assert "proxy_pass" not in backoffice_block
