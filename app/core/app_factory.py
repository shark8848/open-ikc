from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import log_center_sdk
from log_center_sdk.integrations.fastapi import TraceMiddleware

from app.core.admin.monitor import build_monitor_middleware
from app.core.exception_handlers import register_exception_handlers
from app.core.middlewares import build_auth_middleware, build_framework_error_response_middleware, build_trace_middleware
from app.core.system_routes import register_system_routes
from app.routers.admin import router as admin_router
from app.routers.document import router as document_router
from app.routers.knowledge_base import router as knowledge_base_router
from app.routers.parse import router as parse_router
from app.routers.search import router as search_router

_PORTAL_DIST = Path(__file__).resolve().parents[2] / "portal" / "dist"
# 本地静态文档资源根目录（swagger-ui / redoc），避免 /docs、/redoc 依赖外部 CDN
_DOCS_STATIC_DIR = Path(__file__).resolve().parent / "static" / "docs"
_DOCS_STATIC_PREFIX = "/_static/docs"


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
        # Swagger UI / ReDoc 均改为本地托管静态资源（app/core/static/docs/），
        # 页面不再引用 jsdelivr / Google Fonts 等外部 CDN，离线环境可用。
        # docs_url / redoc_url 置 None 关闭默认路由，改由 _register_local_docs_routes 注册
        # 自定义 /docs、/redoc 路由（get_swagger_ui_html / get_redoc_html 指向本地静态资源）。
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    # 日志中心（ikc-log-center SDK，pip 安装模式接入，见 pyproject.toml 依赖声明）：
    # - configure 初始化控制台 / 滚动文件 / 远程投递 handler；远程投递默认关闭，
    #   由环境变量控制：LOG_CENTER_ENABLE=true 时异步发送至 LOG_CENTER_URL
    #   （默认 http://127.0.0.1:9315，SDK 自动 POST {url}/ingest，见 scripts/start_open_platform.sh）；
    # - TraceMiddleware 在请求入口绑定/复用 23 位 traceId，日志上下文自动携带，
    #   便于在日志中心按链路检索（logger 名称与日志文件均带模块名 open_ikc_api）。
    log_center_sdk.configure(module_name="open_ikc_api")
    logger = log_center_sdk.get_logger(__name__)

    # 日志中心 FastAPI 集成中间件：为每个请求建立 trace 上下文（含 traceId/requestId），
    # 并透传 X-Trace-Id / X-Request-Id 响应头（与 app/core/trace.py 的 build_trace_headers 配合）。
    app.add_middleware(TraceMiddleware)

    app.include_router(knowledge_base_router)
    app.include_router(document_router)
    app.include_router(parse_router)
    app.include_router(search_router)
    app.include_router(admin_router)

    # 注册顺序（后注册者更外层）：Trace 最外层先绑定/复用 traceId；
    # 框架错误改写位于 AuthN 内层，确保未认证/业务响应不被改写；
    # 监控采集位于 AuthN 内层，可读取 request.state.identity 记录 token/身份维度。
    app.middleware("http")(build_framework_error_response_middleware(logger))
    app.middleware("http")(build_auth_middleware(logger))
    app.middleware("http")(build_monitor_middleware(logger))
    app.middleware("http")(build_trace_middleware(logger))

    register_exception_handlers(app)
    register_system_routes(app)
    _mount_portal(app)
    _mount_local_docs_static(app)
    _register_local_docs_routes(app)
    _apply_openapi_docs(app)
    return app


def _mount_portal(app: FastAPI) -> None:
    """若 portal 前端已构建，则将其静态挂载到 /portal（管理 Portal，自带独立 admin 鉴权）。"""
    if _PORTAL_DIST.is_dir():
        app.mount("/portal", StaticFiles(directory=str(_PORTAL_DIST), html=True), name="portal")


def _mount_local_docs_static(app: FastAPI) -> None:
    """将本地 swagger-ui / redoc 静态资源挂载到 /_static/docs，供 /docs、/redoc 页面引用。"""
    app.mount(_DOCS_STATIC_PREFIX, StaticFiles(directory=str(_DOCS_STATIC_DIR)), name="docs-static")


def _redoc_html(
    *,
    openapi_url: str,
    title: str,
    redoc_js_url: str,
    redoc_favicon_url: str,
) -> HTMLResponse:
    """本地 ReDoc 页面：与 FastAPI get_redoc_html 模板一致，并开启 Schemas 数据模型分组。

    ReDoc 2.x 侧边栏默认只展示标签/操作，不展示 components.schemas；而 Swagger UI 的
    Models 区会展示全部 schema，导致两个页面「定义」看起来不一致。注入
    schema-definitions-tag-name（ReDoc standalone 会把元素上的 kebab-case 属性转成
    camelCase 选项）后，侧边栏新增 Schemas 分组，与 Swagger 目录完全对齐
    （两者共用同一份 /openapi.json）。
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
<!-- needed for adaptive design -->
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="shortcut icon" href="{redoc_favicon_url}">
<!--
ReDoc doesn't change outer page styles
-->
<style>
  body {{
    margin: 0;
    padding: 0;
  }}
</style>
</head>
<body>
<noscript>
    ReDoc requires Javascript to function. Please enable it to browse the documentation.
</noscript>
<redoc spec-url="{openapi_url}" schema-definitions-tag-name="Schemas"></redoc>
<script src="{redoc_js_url}"> </script>
</body>
</html>
"""
    return HTMLResponse(html)


def _register_local_docs_routes(app: FastAPI) -> None:
    """注册 /docs、/redoc 与 oauth2-redirect 路由，页面资源全部指向本地静态目录。"""
    from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html

    app.get("/docs", include_in_schema=False)(
        lambda: get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url=f"{_DOCS_STATIC_PREFIX}/swagger-ui/swagger-ui-bundle.js",
            swagger_css_url=f"{_DOCS_STATIC_PREFIX}/swagger-ui/swagger-ui.css",
            swagger_favicon_url=f"{_DOCS_STATIC_PREFIX}/swagger-ui/favicon-32x32.png",
        )
    )
    app.get("/redoc", include_in_schema=False)(
        lambda: _redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - ReDoc",
            redoc_js_url=f"{_DOCS_STATIC_PREFIX}/redoc/redoc.standalone.js",
            redoc_favicon_url=f"{_DOCS_STATIC_PREFIX}/swagger-ui/favicon-32x32.png",
        )
    )
    app.get("/docs/oauth2-redirect", include_in_schema=False)(get_swagger_ui_oauth2_redirect_html)


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
