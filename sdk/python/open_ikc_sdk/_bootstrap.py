from __future__ import annotations

"""客户端引导工厂：为 CLI / MCP 封装复用同一套环境变量读取逻辑。

- 基础配置：``OPEN_PLATFORM_BASE_URL``（默认 ``http://127.0.0.1:18000``）
- 认证：``OPEN_PLATFORM_TOKEN`` / ``OPEN_PLATFORM_TOKENS``（多 token 取第一个，与平台语义一致）
- AUTHZ 身份头：``OPEN_PLATFORM_USER_ID`` / ``OPEN_PLATFORM_TENANT_ID`` / ``OPEN_PLATFORM_ROLES``（逗号分隔）

显式传入的参数优先于环境变量，便于 CLI ``--base-url`` / ``--token`` 等覆盖。
"""

import os

from .client import OpenIKCClient
from .headers import CallerIdentity

DEFAULT_BASE_URL = "http://127.0.0.1:18000"

_ENV_BASE_URL = "OPEN_PLATFORM_BASE_URL"
_ENV_TOKEN = "OPEN_PLATFORM_TOKEN"
_ENV_TOKENS = "OPEN_PLATFORM_TOKENS"
_ENV_USER_ID = "OPEN_PLATFORM_USER_ID"
_ENV_TENANT_ID = "OPEN_PLATFORM_TENANT_ID"
_ENV_ROLES = "OPEN_PLATFORM_ROLES"


def _first_token(token: str | None, tokens: str | None) -> str | None:
    """平台语义：OPEN_PLATFORM_TOKEN 单 token；OPEN_PLATFORM_TOKENS 多 token 逗号分隔。

    取第一个可用值，避免客户端携带多个凭据导致鉴权语义歧义。
    """
    if token:
        return token.strip()
    if tokens:
        for item in tokens.split(","):
            item = item.strip()
            if item:
                return item
    return None


def _identity_from_env(
    user_id: str | None,
    tenant_id: str | None,
    roles: str | None,
) -> CallerIdentity | None:
    """组装 AUTHZ 身份上下文；所有字段为空时返回 None（不附加身份头）。"""
    user_id = user_id or os.getenv(_ENV_USER_ID, "").strip()
    tenant_id = tenant_id or os.getenv(_ENV_TENANT_ID, "").strip()
    roles_value = roles or os.getenv(_ENV_ROLES, "").strip()

    roles_list: list[str] | None = None
    if roles_value:
        roles_list = [item.strip() for item in roles_value.split(",") if item.strip()]

    if not user_id and not tenant_id and not roles_list:
        return None
    return CallerIdentity(user_id=user_id or None, tenant_id=tenant_id or None, roles=roles_list)


def client_from_env(
    *,
    base_url: str | None = None,
    token: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    roles: str | None = None,
    **kwargs,
) -> OpenIKCClient:
    """从环境变量 + 显式参数构造 ``OpenIKCClient``；显式参数优先。

    额外关键字参数（如 ``timeout`` / ``max_retries`` / ``http_client``）原样透传给客户端。
    """
    resolved_base_url = base_url or os.getenv(_ENV_BASE_URL, DEFAULT_BASE_URL)
    resolved_token = _first_token(token, os.getenv(_ENV_TOKENS)) or os.getenv(_ENV_TOKEN)
    identity = _identity_from_env(user_id, tenant_id, roles)
    return OpenIKCClient(
        base_url=resolved_base_url,
        token=resolved_token,
        identity=identity,
        **kwargs,
    )
