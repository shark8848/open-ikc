from __future__ import annotations

"""请求统计采集中间件。

挂在业务中间件栈最内层（紧贴路由），记录每个请求：
path / method / status / errCode / token / 身份 / 耗时 / client_ip，并维护在线并发计数。
- 通过 ``request.state.stats_enabled`` 可由上层中间件关闭采集（如 admin 自身请求）。
- 统计写入 SQLite（best-effort，异常静默不阻塞业务）。
"""

import logging
import time

from fastapi import Request

from app.core.admin import stats


def build_monitor_middleware(logger: logging.Logger):
    async def monitor_middleware(request: Request, call_next):
        # admin 管理面自身请求不纳入业务监控统计
        if getattr(request.state, "skip_stats", False):
            return await call_next(request)

        start = time.monotonic()
        stats._concurrency.inc()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            stats._concurrency.dec()
            if response is not None:
                duration_ms = int((time.monotonic() - start) * 1000)
                _record(request, response.status_code, duration_ms)

    return monitor_middleware


def _record(request: Request, status_code: int, duration_ms: int) -> None:
    try:
        identity = getattr(request.state, "identity", None) or {}
        token_id = getattr(request.state, "admin_token_id", None)
        stats.record_request(
            path=request.url.path,
            method=request.method,
            status_code=status_code,
            err_code=_status_based_err_code(status_code, request),
            token_id=token_id if isinstance(token_id, int) else None,
            user_id=str(identity.get("user_id", "") if isinstance(identity, dict) else ""),
            tenant_id=str(identity.get("tenant_id", "") if isinstance(identity, dict) else ""),
            duration_ms=duration_ms,
            client_ip=_client_ip(request),
        )
    except Exception:
        pass


def _status_based_err_code(status_code: int, request: Request) -> str:
    """由 HTTP 状态推断 errCode（统一响应体 errCode 提取在独立中间件完成后不可靠，此处用状态近似）。"""
    if status_code < 400:
        return "000000"
    mapping = {
        401: "100401",
        403: "100403",
        404: "100404",
        405: "100405",
        409: "100409",
    }
    return mapping.get(status_code, "999999")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else ""
