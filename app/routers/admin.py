from __future__ import annotations

"""管理面路由（/admin/*）：token 管理、监控、在线测试。

独立管理鉴权（OPEN_PLATFORM_ADMIN_TOKEN），与业务四类能力隔离。
"""

import re
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.admin import mcp_cli_test, stats, token_store
from app.core.admin.auth import admin_required
from app.core.error_codes import AdminErrorCodes, CommonErrorCodes, ErrorCode
from app.core.trace import current_trace_id
from app.schemas.admin_test import CliTestRequest, McpTestRequest

router = APIRouter(prefix="/admin", tags=["admin"])


_admin_dep = admin_required  # 管理鉴权依赖（抛异常由全局处理器映射统一响应）


_SCOPE_RE = re.compile(r"^(?:[a-z_]+|\*):(?:[a-z_]+|\*)$")


def _valid_scope(scope: str) -> bool:
    """作用域格式：resource:action，两侧支持 * 通配（如 `*:*`、`knowledge_base:*`）。"""
    return _SCOPE_RE.fullmatch(scope) is not None


def _ok(data: Any = None) -> dict[str, Any]:
    """管理面成功响应：统一响应壳 {errCode, errMsg, data, traceId}，traceId 取当前链路。"""
    return {
        "errCode": CommonErrorCodes.SUCCESS.code,
        "errMsg": CommonErrorCodes.SUCCESS.message,
        "data": {} if data is None else data,
        "traceId": current_trace_id(),
    }


def _fail(error: ErrorCode, message: str | None = None, data: Any = None) -> dict[str, Any]:
    """管理面失败响应：统一响应壳，错误码一律取注册表（ErrorCode）。"""
    return {
        "errCode": error.code,
        "errMsg": error.message if message is None else message,
        "data": {} if data is None else data,
        "traceId": current_trace_id(),
    }


# ---------- 总览与监控 ----------


@router.get("/overview")
async def overview(_: Any = Depends(_admin_dep)) -> JSONResponse:
    snap = stats.snapshot()
    tokens = token_store.list_tokens()
    return JSONResponse(
        _ok({
            **snap,
            "activeTokens": len(tokens),
        })
    )


@router.get("/endpoints")
async def endpoints(
    window_minutes: int | None = None,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    return JSONResponse(_ok(stats.endpoint_stats(window_minutes=window_minutes)))


@router.get("/requests")
async def requests(
    limit: int = 50,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    return JSONResponse(_ok(stats.recent_requests(limit=max(1, min(limit, 200)))))


@router.get("/stats/token")
async def token_stats(
    window_minutes: int | None = None,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    return JSONResponse(_ok(stats.token_stats(window_minutes=window_minutes)))


# ---------- Token 管理 ----------


@router.get("/tokens")
async def tokens(
    include_revoked: bool = False,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    records = token_store.list_tokens(include_revoked=include_revoked)
    return JSONResponse(_ok([r.to_dict() for r in records]))


@router.post("/tokens")
async def create_token(
    payload: dict[str, Any],
    request: Request,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    name = str(payload.get("name", "")).strip()
    if not name:
        return JSONResponse(_fail(CommonErrorCodes.INVALID_PARAMS, message="name 必填"))

    scopes: list[str] | None = None
    raw_scopes = payload.get("scopes")
    if raw_scopes is not None:
        if not isinstance(raw_scopes, list):
            return JSONResponse(_fail(CommonErrorCodes.INVALID_PARAMS, message="scopes 需为字符串数组"))
        scopes = [str(item).strip() for item in raw_scopes if str(item).strip()]
        if len(scopes) > 32 or any(len(s) > 64 or not _valid_scope(s) for s in scopes):
            return JSONResponse(
                _fail(
                    CommonErrorCodes.INVALID_PARAMS,
                    message="scopes 需为 resource:action 格式（支持 * 通配），单个不超过 64 字符、最多 32 个",
                )
            )

    expires_in_seconds: int | None = None
    raw_expires = payload.get("expiresInSeconds")
    if raw_expires is not None:
        try:
            expires_in_seconds = int(raw_expires)
        except (TypeError, ValueError):
            return JSONResponse(_fail(CommonErrorCodes.INVALID_PARAMS, message="expiresInSeconds 需为正整数秒"))
        if expires_in_seconds <= 0:
            return JSONResponse(_fail(CommonErrorCodes.INVALID_PARAMS, message="expiresInSeconds 需为正整数秒"))

    record, plain = token_store.create_token(
        name=name,
        owner=str(payload.get("owner", "")).strip(),
        scopes=scopes,
        expires_in_seconds=expires_in_seconds,
    )
    return JSONResponse(
        _ok({
            **record.to_dict(),
            "token": plain,
            "notice": "token 明文仅在此刻返回一次，请妥善保存",
        })
    )


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(
    token_id: int,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    ok = token_store.revoke_token(token_id)
    if not ok:
        return JSONResponse(_fail(CommonErrorCodes.NOT_FOUND, message="token 不存在或已撤销", data={"revoked": False}))
    return JSONResponse(_ok({"revoked": True}))


# ---------- MCP / CLI 在线测试 ----------


@router.post("/test/mcp")
async def test_mcp(
    payload: McpTestRequest,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    # subprocess 为同步阻塞调用，需在线程池中执行，避免阻塞事件循环
    # （子进程请求平台自身端点，若事件循环被阻塞则互相等待直至超时）。
    result = await run_in_threadpool(
        mcp_cli_test.run_mcp_smoke,
        token=payload.token,
        base_url=payload.baseUrl,
        tool=payload.tool,
        args=payload.args,
        timeout_seconds=payload.timeoutSeconds or mcp_cli_test.DEFAULT_TIMEOUT_SECONDS,
    )
    if not result.ok:
        return JSONResponse(_fail(AdminErrorCodes.TEST_FAILED, message="MCP 测试未通过", data=result.to_dict()))
    return JSONResponse(_ok(result.to_dict()))


@router.post("/test/cli")
async def test_cli(
    payload: CliTestRequest,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    # 同步阻塞 subprocess 在线程池执行，避免事件循环死锁（见 test/mcp 注释）。
    result = await run_in_threadpool(
        mcp_cli_test.run_cli_command,
        command=payload.command,
        args=payload.args,
        token=payload.token,
        base_url=payload.baseUrl,
        identity=payload.identity,
        timeout_seconds=payload.timeoutSeconds or mcp_cli_test.DEFAULT_TIMEOUT_SECONDS,
    )
    if not result.ok:
        return JSONResponse(_fail(AdminErrorCodes.TEST_FAILED, message="CLI 测试未通过", data=result.to_dict()))
    return JSONResponse(_ok(result.to_dict()))


@router.get("/test/whitelist")
async def test_whitelist(_: Any = Depends(_admin_dep)) -> JSONResponse:
    return JSONResponse(_ok(mcp_cli_test.whitelist_payload()))
