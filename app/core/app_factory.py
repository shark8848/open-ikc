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
        title="开放平台北向 API",
        version="1.0.0",
        description=(
            "对外提供知识库、文档、解析、检索四类业务能力（知识库基本信息管理 / 文档接入与查询 / "
            "解析任务与结果获取 / 统一检索问答）。"
            "所有业务接口需携带 Authorization: Bearer <token>；统一响应体 {errCode, errMsg, data, traceId}，"
            "完整错误码目录见 GET /api/error-codes。"
        ),
        openapi_tags=[
            {"name": "知识库", "description": "知识库创建、修改、列表查询与详情获取"},
            {"name": "文档", "description": "知识源接入（url/file/directory/archive）、一体化接入解析与文档信息查询"},
            {"name": "解析", "description": "解析任务启动（async/sync）、进度查询与结果下载（一次性下载凭证）"},
            {"name": "检索", "description": "统一检索与问答（search 证据列表 / qa 带回答，按数据权限过滤）"},
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
        # 声明 HTTP Bearer 鉴权，使 /docs 与 /redoc 呈现统一认证要求（与运行时 AuthN 中间件一致）
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "opaque",
            "description": "所有业务接口需携带 Authorization: Bearer <token>；缺失或格式错误返回 100401。",
        }
        schema.setdefault("security", [{"BearerAuth": []}])
        error_codes_hint = (
            "统一响应体（errCode/errMsg/data/traceId）；通用错误码 100001/100401/100403/100404/100405/"
            "100409/501001/999999，业务错误码 200xxx（如 200004 下载凭证无效或已过期），"
            "完整目录见 GET /api/error-codes"
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
