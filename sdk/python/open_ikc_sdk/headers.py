from __future__ import annotations

from dataclasses import dataclass, field

from ._version import __version__


@dataclass
class CallerIdentity:
    """调用方身份与 AUTHZ 上下文；仅非空字段透传为请求头。"""

    user_id: str | None = None
    tenant_id: str | None = None
    roles: list[str] | None = None
    permissions: list[str] | None = None
    deny_permissions: list[str] | None = None
    auth_system: str | None = None


def build_headers(
    *,
    token: str | None,
    trace_id: str,
    identity: CallerIdentity | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """构建请求头：认证、trace 与 AUTHZ 身份头；extra_headers 优先级最高。"""
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": f"open-ikc-sdk/{__version__}",
        "X-Request-Id": trace_id,
        "X-Trace-Id": trace_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if identity:
        if identity.user_id:
            headers["X-User-Id"] = identity.user_id
        if identity.tenant_id:
            headers["X-Tenant-Id"] = identity.tenant_id
        if identity.roles:
            headers["X-User-Roles"] = ",".join(identity.roles)
        if identity.permissions:
            headers["X-User-Permissions"] = ",".join(identity.permissions)
        if identity.deny_permissions:
            headers["X-User-Deny-Permissions"] = ",".join(identity.deny_permissions)
        if identity.auth_system:
            headers["X-Auth-System"] = identity.auth_system
    if extra_headers:
        headers.update(extra_headers)
    return headers
