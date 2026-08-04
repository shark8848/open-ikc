from __future__ import annotations

from fastapi import FastAPI
import log_center_sdk
from log_center_sdk.integrations.fastapi import TraceMiddleware

from app.core.exception_handlers import register_exception_handlers
from app.core.middlewares import build_auth_middleware, build_trace_middleware
from app.core.system_routes import register_system_routes
from app.routers.document import router as document_router
from app.routers.knowledge_base import router as knowledge_base_router
from app.routers.parse import router as parse_router
from app.routers.search import router as search_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="开放平台 API 浏览服务",
        version="0.1.0",
        description="FastAPI 预占位框架，仅保留知识库、文档、解析、检索四大类。",
        openapi_tags=[
            {"name": "知识库", "description": "知识库创建与基础信息维护"},
            {"name": "文档", "description": "文档接入与文档级预占位接口"},
            {"name": "解析", "description": "文档解析任务与结果获取接口"},
            {"name": "检索", "description": "统一检索与问答接口"},
        ],
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    log_center_sdk.configure(module_name="open_ikc_api")
    logger = log_center_sdk.get_logger(__name__)

    app.add_middleware(TraceMiddleware)

    app.include_router(knowledge_base_router)
    app.include_router(document_router)
    app.include_router(parse_router)
    app.include_router(search_router)

    # 先注册 AuthN（内层），再注册 Trace（外层）：Trace 先绑定/复用 traceId，
    # 保证未认证响应也能回写同一链路 ID（契约 §3.5）。
    app.middleware("http")(build_auth_middleware(logger))
    app.middleware("http")(build_trace_middleware(logger))

    register_exception_handlers(app)
    register_system_routes(app)
    return app
