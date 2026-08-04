from __future__ import annotations

from fastapi import FastAPI
import log_center_sdk
from log_center_sdk.integrations.fastapi import TraceMiddleware

from app.core.exception_handlers import register_exception_handlers
from app.core.middlewares import build_auth_middleware, build_framework_error_response_middleware, build_trace_middleware
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

    # 注册顺序（后注册者更外层）：Trace 最外层先绑定/复用 traceId；
    # 框架错误改写位于 AuthN 内层，确保未认证/业务响应不被改写。
    app.middleware("http")(build_framework_error_response_middleware(logger))
    app.middleware("http")(build_auth_middleware(logger))
    app.middleware("http")(build_trace_middleware(logger))

    register_exception_handlers(app)
    register_system_routes(app)
    _apply_openapi_docs(app)
    return app


def _apply_openapi_docs(app: FastAPI) -> None:
    """对齐 OpenAPI 文档与运行时行为：移除不实际返回的 422，并在 200 响应上说明统一错误码。"""

    original_openapi = app.openapi

    def custom_openapi() -> dict:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = original_openapi()
        error_codes_hint = (
            "统一响应体；业务错误码（100001/100401/100403/100404/100405/100409/501001/999999）"
            "见 GET /api/error-codes"
        )
        for path_item in schema.get("paths", {}).values():
            if not isinstance(path_item, dict):
                continue
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                responses = operation.get("responses")
                if not isinstance(responses, dict):
                    continue
                responses.pop("422", None)
                success = responses.get("200")
                if isinstance(success, dict):
                    success["description"] = error_codes_hint

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
