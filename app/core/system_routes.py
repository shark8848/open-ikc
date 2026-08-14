from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.api_browser import render_api_browser_html
from app.core.catalog import API_CATALOG
from app.core.error_codes import error_code_catalog
from app.core.trace import current_trace_id

_PORTAL_DIST = Path(__file__).resolve().parents[2] / "portal" / "dist"


def register_system_routes(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        # 首页直达管理 Portal（已构建时）；未构建时回退 API 浏览页。
        if _PORTAL_DIST.is_dir():
            return RedirectResponse(url="/portal/")
        return RedirectResponse(url="/api-browser")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, Any]:
        return {"status": True, "service": "open-ikc-api", "version": app.version, "traceId": current_trace_id()}

    @app.get("/api-browser", include_in_schema=False, response_class=HTMLResponse)
    async def api_browser() -> HTMLResponse:
        return HTMLResponse(render_api_browser_html())

    @app.get("/api/catalog", include_in_schema=False)
    async def api_catalog() -> dict[str, Any]:
        return {"status": True, "data": API_CATALOG, "traceId": current_trace_id()}

    @app.get("/api/error-codes", include_in_schema=False)
    async def api_error_codes() -> dict[str, Any]:
        return {"status": True, "data": error_code_catalog(), "traceId": current_trace_id()}
