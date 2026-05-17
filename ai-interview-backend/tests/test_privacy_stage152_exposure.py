import sys
import types

from fastapi.testclient import TestClient


def _install_redis_stub():
    if "redis.asyncio" in sys.modules:
        return
    redis_module = types.ModuleType("redis")
    redis_asyncio_module = types.ModuleType("redis.asyncio")

    class _Redis:
        def __init__(self, *args, **kwargs):
            pass

        async def setex(self, *args, **kwargs):
            return None

        async def get(self, *args, **kwargs):
            return None

        async def delete(self, *args, **kwargs):
            return None

        async def exists(self, *args, **kwargs):
            return False

        async def brpop(self, *args, **kwargs):
            return None

        async def close(self):
            return None

        def pipeline(self, *args, **kwargs):
            return self

    redis_asyncio_module.Redis = _Redis
    redis_module.asyncio = redis_asyncio_module
    sys.modules["redis"] = redis_module
    sys.modules["redis.asyncio"] = redis_asyncio_module


def _install_boto3_stub():
    if "boto3" in sys.modules:
        return
    boto3_module = types.ModuleType("boto3")

    class _Client:
        def upload_fileobj(self, *args, **kwargs):
            return None

        def generate_presigned_url(self, *args, **kwargs):
            return "https://example.test/object"

    def client(*args, **kwargs):
        return _Client()

    boto3_module.client = client
    sys.modules["boto3"] = boto3_module


def _install_pypdf2_stub():
    if "PyPDF2" in sys.modules:
        return
    pypdf2_module = types.ModuleType("PyPDF2")

    class _PdfReader:
        pages = []

        def __init__(self, *args, **kwargs):
            pass

    pypdf2_module.PdfReader = _PdfReader
    sys.modules["PyPDF2"] = pypdf2_module


_install_redis_stub()
_install_boto3_stub()
_install_pypdf2_stub()

from app.route import route as route_module


def test_production_app_does_not_mount_swagger_or_docs_export(monkeypatch):
    monkeypatch.setattr(route_module.settings, "ENV", "production")

    app = route_module.create_app()
    client = TestClient(app)

    assert client.get("/client/openapi.json").status_code == 404
    assert client.get("/backoffice/openapi.json").status_code == 404
    assert client.get("/api-docs/").status_code == 404


def test_upload_static_mount_only_exposes_avatars(monkeypatch):
    monkeypatch.setattr(route_module.settings, "ENV", "production")

    app = route_module.create_app()
    mounted_paths = {getattr(item, "path", "") for item in app.routes}

    assert "/uploads/avatars" in mounted_paths
    assert "/uploads" not in mounted_paths

    client = TestClient(app)
    assert client.get("/uploads/resumes/private.pdf").status_code == 404


def test_client_routes_do_not_bypass_base_privacy_gate(monkeypatch):
    from app.api.client import deps as client_deps

    monkeypatch.setattr(route_module.settings, "ENV", "production")
    app = route_module.create_app()
    direct_login_only_allowlist = {
        "get_current_user_info",
        "update_profile",
        "change_password",
        "upload_resume",
        "start_interview",
    }
    bypassing_routes = []

    for item in app.routes:
        path = getattr(item, "path", "")
        if not path.startswith(route_module.settings.API_V1_STR):
            continue
        if path.startswith(f"{route_module.settings.API_V1_STR}/backoffice"):
            continue
        direct_calls = {
            getattr(dependency, "call", None)
            for dependency in getattr(getattr(item, "dependant", None), "dependencies", [])
        }
        if client_deps.get_current_user in direct_calls:
            endpoint_name = getattr(getattr(item, "endpoint", None), "__name__", None)
            if endpoint_name not in direct_login_only_allowlist:
                bypassing_routes.append((path, endpoint_name))

    assert bypassing_routes == []
