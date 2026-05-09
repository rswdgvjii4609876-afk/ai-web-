import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.configs.docs_apps import create_backoffice_app, create_client_app
from app.core.config import settings
from app.core.log_config import setup_logging, shutdown_logging
from app.db.base import close_db_engine
from app.exceptions.http_exceptions import APIException
from app.schemas.response import ApiResponse
from app.services.common.redis import redis_client
from app.services.common.thread_pool import thread_pool_service

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = settings.get_cors_origins()


@asynccontextmanager
async def lifespan(application: FastAPI):
    setup_logging()
    logger.info("Application starting up")
    try:
        yield
    finally:
        try:
            await close_db_engine()
        except Exception:
            logger.exception("Failed to close database engine during shutdown")
        try:
            await redis_client.close()
        except Exception:
            logger.exception("Failed to close redis client during shutdown")
        try:
            thread_pool_service.shutdown()
        except Exception:
            logger.exception("Failed to shutdown thread pool service")
        try:
            shutdown_logging()
        except Exception:
            logger.exception("Failed to shutdown logging cleanly")


def create_app():
    app = FastAPI(
        lifespan=lifespan,
        title=settings.PROJECT_NAME,
        description="职启智评：多岗位 AI 模拟面试与求职能力评估系统 API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.ENV in ["development", "preview"]:

        @app.get("/", tags=["docs"])
        async def swagger_navigation():
            return {
                "message": "职启智评 API - 开发环境",
                "environment": settings.ENV,
                "documentation": {
                    "client_api": {
                        "swagger": "/client/docs",
                        "redoc": "/client/redoc",
                        "openapi": "/client/openapi.json",
                        "description": "客户端 API 文档",
                    },
                    "backoffice_api": {
                        "swagger": "/backoffice/docs",
                        "redoc": "/backoffice/redoc",
                        "openapi": "/backoffice/openapi.json",
                        "description": "后台 API 文档",
                    },
                },
                "api_exports": {
                    "client_json": "/api-docs/client.json",
                    "backoffice_json": "/api-docs/backoffice.json",
                    "info": "/api-docs/",
                },
                "health_check": "/api/v1/config/health",
            }

    from app.route.router_registry import (
        get_backoffice_routes,
        get_client_routes,
        get_common_routes,
        register_routes,
    )

    register_routes(app, get_client_routes())
    register_routes(app, get_backoffice_routes())
    register_routes(app, get_common_routes())

    client_docs_app = create_client_app()
    backoffice_docs_app = create_backoffice_app()
    app.mount("/client", client_docs_app)
    app.mount("/backoffice", backoffice_docs_app)

    os.makedirs("uploads/avatars", exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        logger.error(
            "API Exception: %s - %s - %s",
            exc.status_code,
            exc.code,
            exc.detail,
            extra={"request": f"{request.method} {request.url}"},
        )
        return ApiResponse.failed(
            message=exc.detail,
            body_code=exc.code,
            http_code=exc.status_code,
            data=exc.data,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.error(
            "HTTP Exception: %s - %s",
            exc.status_code,
            exc.detail,
            extra={"request": f"{request.method} {request.url}"},
        )
        return ApiResponse.failed(
            message=exc.detail,
            body_code=exc.status_code,
            http_code=exc.status_code,
            data=None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "Validation Error: %s",
            exc.errors(),
            extra={"request": f"{request.method} {request.url}"},
        )
        return ApiResponse.failed(
            message="参数验证错误",
            body_code=1001,
            http_code=status.HTTP_400_BAD_REQUEST,
            data=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled Exception: %s",
            str(exc),
            extra={"request": f"{request.method} {request.url}"},
        )
        return ApiResponse.failed(
            message="服务器内部错误",
            body_code=1005,
            http_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return app
