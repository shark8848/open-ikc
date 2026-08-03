from __future__ import annotations

import os
from typing import Any

from fastapi import Request

from app.core.authz.adapters import MappingAuthzAdapter
from app.core.authz.bridge import AuthzBridge
from app.core.authz.service import AuthIntegrationService


_bridge_singleton: AuthzBridge | None = None


def authz_enabled() -> bool:
    return (os.getenv("OPEN_PLATFORM_AUTHZ_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"})


def get_authz_bridge() -> AuthzBridge:
    global _bridge_singleton
    if _bridge_singleton is not None:
        return _bridge_singleton

    service = AuthIntegrationService()
    _register_builtin_adapters(service)
    _bridge_singleton = AuthzBridge(service)
    return _bridge_singleton


def authorize_or_raise(
    *,
    request: Request,
    action: str,
    resource_type: str,
    resource_id: str = "*",
    context: dict[str, Any] | None = None,
) -> None:
    if not authz_enabled():
        return

    bridge = get_authz_bridge()
    system_name = request.headers.get("X-Auth-System", "default")
    decision = bridge.authorize_request(
        request=request,
        system_name=system_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        context=context,
    )
    bridge.require_allowed(decision)


def _register_builtin_adapters(service: AuthIntegrationService) -> None:
    default_role_mapping = _load_role_action_mapping(
        "OPEN_PLATFORM_DEFAULT_ROLE_ACTION_MAPPING",
        {
            "km_reader": ["search:query"],
            "km_admin": ["*:*"],
        },
    )
    service.register_adapter(
        "default",
        MappingAuthzAdapter(
            "default",
            identity_mapping={
                "user_id": "user_id",
                "tenant_id": "tenant_id",
                "roles": "roles",
                "scopes": "scopes",
            },
            role_action_mapping=default_role_mapping,
            roles_key="roles",
            permissions_key="permissions",
            deny_permissions_key="deny_permissions",
        ),
    )

    de_role_mapping = _load_role_action_mapping(
        "OPEN_PLATFORM_DE_ROLE_ACTION_MAPPING",
        {
            "de_km_reader": ["search:query", "knowledge_base:read", "document:read"],
            "de_km_operator": ["search:query", "document:read", "document:write"],
            "de_km_admin": ["*:*"],
        },
    )
    service.register_adapter(
        "digital_employee",
        MappingAuthzAdapter(
            "digital_employee",
            identity_mapping={
                "user_id": "employee_id",
                "tenant_id": "tenant_code",
                "roles": "role_codes",
                "scopes": "scopes",
            },
            role_action_mapping=de_role_mapping,
            roles_key="roles",
            permissions_key="permissions",
            deny_permissions_key="deny_permissions",
        ),
    )


def _load_role_action_mapping(env_name: str, fallback: dict[str, list[str]]) -> dict[str, list[str]]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return fallback

    parsed: dict[str, list[str]] = {}
    for role_block in raw.split(";"):
        cleaned = role_block.strip()
        if not cleaned or "=" not in cleaned:
            continue
        role, actions = cleaned.split("=", 1)
        role_name = role.strip()
        if not role_name:
            continue
        action_items = [item.strip() for item in actions.split(",") if item.strip()]
        if action_items:
            parsed[role_name] = action_items

    return parsed or fallback
