from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.authz.schema import AuthorizationDecision, AuthorizationRequest
from app.core.authz.service import AuthIntegrationService
from app.core.error_codes import AppException, CommonErrorCodes


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    identity_header_map: dict[str, str]
    permissions_header_map: dict[str, str]


DEFAULT_BRIDGE_CONFIG = BridgeConfig(
    identity_header_map={
        "user_id": "X-User-Id",
        "tenant_id": "X-Tenant-Id",
        "roles": "X-User-Roles",
        "scopes": "X-User-Scopes",
    },
    permissions_header_map={
        "permissions": "X-User-Permissions",
        "deny_permissions": "X-User-Deny-Permissions",
        "roles": "X-User-Roles",
    },
)


class AuthzBridge:
    """Business-layer bridge for independent authorization integration.

    This bridge is intentionally separate from middleware to avoid coupling
    with existing trace/token chain logic.
    """

    def __init__(self, service: AuthIntegrationService, config: BridgeConfig | None = None) -> None:
        self.service = service
        self.config = config or DEFAULT_BRIDGE_CONFIG

    def authorize_request(
        self,
        *,
        request: Request,
        system_name: str,
        action: str,
        resource_type: str,
        resource_id: str = "*",
        context: dict[str, Any] | None = None,
        raw_identity: dict[str, Any] | None = None,
        raw_permissions: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        identity = raw_identity or self._identity_from_request(request)
        permissions = raw_permissions or self._permissions_from_request(request)

        auth_request = AuthorizationRequest(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            context=context or {},
        )
        return self.service.authorize(
            system_name=system_name,
            raw_identity=identity,
            raw_permissions=permissions,
            request=auth_request,
        )

    @staticmethod
    def require_allowed(decision: AuthorizationDecision) -> None:
        if decision.allow:
            return
        raise AppException(
            CommonErrorCodes.FORBIDDEN,
            {
                "reason": decision.reason,
                "metadata": decision.metadata,
            },
            message="无权限访问",
        )

    def _identity_from_request(self, request: Request) -> dict[str, Any]:
        from_state = getattr(request.state, "identity", None)
        if isinstance(from_state, dict) and from_state:
            return from_state

        mapped: dict[str, Any] = {}
        for key, header_name in self.config.identity_header_map.items():
            raw_value = request.headers.get(header_name)
            if raw_value is None:
                continue
            mapped[key] = _split_csv(raw_value) if key in {"roles", "scopes"} else raw_value
        return mapped

    def _permissions_from_request(self, request: Request) -> dict[str, Any]:
        from_state = getattr(request.state, "permissions", None)
        if isinstance(from_state, dict) and from_state:
            return from_state

        mapped: dict[str, Any] = {}
        for key, header_name in self.config.permissions_header_map.items():
            raw_value = request.headers.get(header_name)
            if raw_value is None:
                continue
            mapped[key] = _split_csv(raw_value)
        return mapped


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
