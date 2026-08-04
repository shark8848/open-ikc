from __future__ import annotations

import logging

from fastapi import Request

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


def _is_auth_exempt_path(path: str) -> bool:
    if path in AUTH_EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


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
