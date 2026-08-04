from __future__ import annotations

import logging

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.error_codes import CommonErrorCodes, error_response
from app.core.responses import with_trace_id
from app.core.security import authenticate_request, build_unauthorized_response
from app.core.trace import bind_trace_context, build_trace_headers, clear_trace, normalize_trace_id


AUTH_EXEMPT_PREFIXES = ("/docs", "/redoc")
AUTH_EXEMPT_PATHS = {
    "/",
    "/health",
    "/openapi.json",
    "/docs/oauth2-redirect",
    "/api-browser",
    "/api/catalog",
    "/api/error-codes",
}


def build_framework_error_response_middleware(logger: logging.Logger):
    """将框架层 404/405 响应改写为统一响应体（保留 HTTP 状态码）。

    未知路由与方法不允许由 Starlette 路由层直接返回裸 JSON，不经过异常链路，
    这里在响应路径统一映射为 {errCode, errMsg, data, traceId}。
    """

    async def framework_error_middleware(request: Request, call_next):
        response = await call_next(request)
        if response.status_code not in {404, 405}:
            return response

        error = (
            CommonErrorCodes.METHOD_NOT_ALLOWED
            if response.status_code == 405
            else CommonErrorCodes.NOT_FOUND
        )
        unified = with_trace_id(
            error_response(
                error,
                {"method": request.method, "path": request.url.path},
            )
        )
        headers = {
            name: value
            for name, value in response.headers.items()
            if name.lower() not in {"content-type", "content-length"}
        }
        logger.info(
            "framework error %s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return JSONResponse(
            status_code=response.status_code,
            content=jsonable_encoder(unified),
            headers=headers,
        )

    return framework_error_middleware


def _is_auth_exempt_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in AUTH_EXEMPT_PATHS:
        return True
    return any(normalized.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


def build_trace_middleware(logger: logging.Logger):
    async def trace_id_middleware(request: Request, call_next):
        incoming_trace_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Trace-Id")
            or request.headers.get("traceId")
            or request.headers.get("trace_id")
        )
        trace_id = normalize_trace_id(incoming_trace_id)
        header_bytes = trace_id.encode("utf-8")
        normalized_headers = []
        seen_trace_id = False
        seen_request_id = False
        for name, value in request.scope.get("headers", []):
            lowered = name.lower()
            if lowered == b"x-trace-id":
                normalized_headers.append((name, header_bytes))
                seen_trace_id = True
            elif lowered == b"x-request-id":
                normalized_headers.append((name, header_bytes))
                seen_request_id = True
            else:
                normalized_headers.append((name, value))
        if not seen_trace_id:
            normalized_headers.append((b"x-trace-id", header_bytes))
        if not seen_request_id:
            normalized_headers.append((b"x-request-id", header_bytes))
        request.scope["headers"] = normalized_headers

        bind_trace_context(trace_id)
        request.state.trace_id = trace_id
        request.state.trace_headers = build_trace_headers(trace_id)

        logger.info("request start %s %s", request.method, request.url.path)

        try:
            response = await call_next(request)
            response.headers.setdefault("X-Request-Id", trace_id)
            response.headers.setdefault("X-Trace-Id", trace_id)
            logger.info("request end %s %s %s", request.method, request.url.path, response.status_code)
            return response
        finally:
            clear_trace()

    return trace_id_middleware


def build_auth_middleware(logger: logging.Logger):
    async def auth_middleware(request: Request, call_next):
        if _is_auth_exempt_path(request.url.path):
            return await call_next(request)

        auth_result = authenticate_request(request)
        if auth_result is not None:
            request.state.identity = auth_result.identity
            request.state.permissions = auth_result.permissions
            request.state.auth_system = auth_result.auth_system
            return await call_next(request)

        logger.warning("request unauthorized %s %s", request.method, request.url.path)
        trace_id = getattr(request.state, "trace_id", None)
        return build_unauthorized_response(trace_id)

    return auth_middleware
