from __future__ import annotations

"""管理面路由（/admin/*）：token 管理、监控、在线测试。

独立管理鉴权（OPEN_PLATFORM_ADMIN_TOKEN），与业务四类能力隔离。
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.admin import mcp_cli_test, stats, token_store
from app.core.admin.auth import admin_required

router = APIRouter(prefix="/admin", tags=["admin"])


_admin_dep = admin_required  # 管理鉴权依赖（抛异常由全局处理器映射统一响应）


# ---------- 总览与监控 ----------


@router.get("/overview")
async def overview(_: Any = Depends(_admin_dep)) -> JSONResponse:
    snap = stats.snapshot()
    tokens = token_store.list_tokens()
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": {
                **snap,
                "activeTokens": len(tokens),
            },
            "traceId": "",
        }
    )


@router.get("/endpoints")
async def endpoints(
    window_minutes: int | None = None,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": stats.endpoint_stats(window_minutes=window_minutes),
            "traceId": "",
        }
    )


@router.get("/requests")
async def requests(
    limit: int = 50,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": stats.recent_requests(limit=max(1, min(limit, 200))),
            "traceId": "",
        }
    )


@router.get("/stats/token")
async def token_stats(
    window_minutes: int | None = None,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": stats.token_stats(window_minutes=window_minutes),
            "traceId": "",
        }
    )


# ---------- Token 管理 ----------


@router.get("/tokens")
async def tokens(
    include_revoked: bool = False,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    records = token_store.list_tokens(include_revoked=include_revoked)
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": [r.to_dict() for r in records],
            "traceId": "",
        }
    )


@router.post("/tokens")
async def create_token(
    payload: dict[str, Any],
    request: Request,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    name = str(payload.get("name", "")).strip()
    if not name:
        return JSONResponse(
            {
                "errCode": "100001",
                "errMsg": "name 必填",
                "data": {},
                "traceId": "",
            }
        )
    record, plain = token_store.create_token(
        name=name,
        owner=str(payload.get("owner", "")).strip(),
        scopes=payload.get("scopes"),
        expires_in_seconds=payload.get("expiresInSeconds"),
    )
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": {
                **record.to_dict(),
                "token": plain,
                "notice": "token 明文仅在此刻返回一次，请妥善保存",
            },
            "traceId": "",
        }
    )


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(
    token_id: int,
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    ok = token_store.revoke_token(token_id)
    return JSONResponse(
        {
            "errCode": "000000" if ok else "100404",
            "errMsg": "success" if ok else "token 不存在或已撤销",
            "data": {"revoked": ok},
            "traceId": "",
        }
    )


# ---------- MCP / CLI 在线测试 ----------


@router.post("/test/mcp")
async def test_mcp(
    payload: dict[str, Any],
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    tool = str(payload.get("tool", "sys_catalog"))
    token = str(payload.get("token", ""))
    base_url = str(payload.get("baseUrl", "http://127.0.0.1:18000"))
    # subprocess 为同步阻塞调用，需在线程池中执行，避免阻塞事件循环
    # （子进程请求平台自身端点，若事件循环被阻塞则互相等待直至超时）。
    result = await run_in_threadpool(
        mcp_cli_test.run_mcp_smoke, token=token, base_url=base_url, tool=tool
    )
    return JSONResponse(
        {
            "errCode": "000000" if result.ok else "200001",
            "errMsg": "success" if result.ok else "MCP 测试未通过",
            "data": result.to_dict(),
            "traceId": "",
        }
    )


@router.post("/test/cli")
async def test_cli(
    payload: dict[str, Any],
    _: Any = Depends(_admin_dep),
) -> JSONResponse:
    command = str(payload.get("command", "")).strip()
    args = [str(a) for a in (payload.get("args") or [])]
    token = str(payload.get("token", ""))
    base_url = str(payload.get("baseUrl", "http://127.0.0.1:18000"))
    identity = payload.get("identity")
    # 同步阻塞 subprocess 在线程池执行，避免事件循环死锁（见 test/mcp 注释）。
    result = await run_in_threadpool(
        mcp_cli_test.run_cli_command,
        command=command,
        args=args,
        token=token,
        base_url=base_url,
        identity=identity if isinstance(identity, dict) else None,
    )
    return JSONResponse(
        {
            "errCode": "000000" if result.ok else "200001",
            "errMsg": "success" if result.ok else "CLI 测试未通过",
            "data": result.to_dict(),
            "traceId": "",
        }
    )


@router.get("/test/whitelist")
async def test_whitelist(_: Any = Depends(_admin_dep)) -> JSONResponse:
    return JSONResponse(
        {
            "errCode": "000000",
            "errMsg": "success",
            "data": {
                "cli": list(mcp_cli_test.CLI_WHITELIST.keys()),
                "mcpTools": sorted(mcp_cli_test.MCP_TOOL_WHITELIST),
            },
            "traceId": "",
        }
    )
