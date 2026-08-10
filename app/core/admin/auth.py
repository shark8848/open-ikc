from __future__ import annotations

"""管理面独立鉴权（OPEN_PLATFORM_ADMIN_TOKEN）。

- 管理接口一律要求 ``Authorization: Bearer <admin-token>``。
- 未配置 ``OPEN_PLATFORM_ADMIN_TOKEN`` 时管理面默认关闭（抛 503 明确提示），避免默认暴露。
- 与业务 AUTHN 完全独立：不进入 catalog，不混入业务中间件。
"""

import os
import secrets

from fastapi import HTTPException, Request


class AdminDisabledError(Exception):
    """管理面未启用。"""


def admin_token() -> str:
    return os.getenv("OPEN_PLATFORM_ADMIN_TOKEN", "").strip()


def admin_enabled() -> bool:
    return bool(admin_token())


def _extract_admin_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip()


def admin_required(request: Request) -> None:
    """FastAPI 依赖：校验管理 token；失败抛异常由全局处理器映射统一响应。"""
    configured = admin_token()
    if not configured:
        raise AdminDisabledError("管理面未启用：未配置 OPEN_PLATFORM_ADMIN_TOKEN")
    request_token = _extract_admin_token(request)
    if request_token is None or not secrets.compare_digest(request_token, configured):
        raise HTTPException(status_code=401, detail="管理 token 缺失或无效")
    request.state.admin_authenticated = True
