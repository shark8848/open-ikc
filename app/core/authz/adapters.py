from __future__ import annotations

from typing import Any, Protocol

from app.core.authz.schema import IdentityContext, PermissionFact


class AuthzAdapter(Protocol):
    """Adapter for translating external auth schemas into canonical auth facts."""

    def normalize_identity(self, raw_identity: dict[str, Any]) -> IdentityContext:
        ...

    def normalize_permissions(self, raw_permissions: dict[str, Any]) -> list[PermissionFact]:
        ...


class MappingAuthzAdapter:
    """Config-driven adapter for heterogeneous external auth schemas.

    identity_mapping example:
    {
        "user_id": "uid",
        "tenant_id": "tenant",
        "roles": "role_codes",
        "scopes": "scope_list",
    }

    role_action_mapping example:
    {
        "km_reader": ["search:query", "document:read"],
        "km_admin": ["*:*"],
    }
    """

    def __init__(
        self,
        system_name: str,
        *,
        identity_mapping: dict[str, str],
        role_action_mapping: dict[str, list[str]] | None = None,
        roles_key: str = "roles",
        permissions_key: str = "permissions",
        deny_permissions_key: str = "deny_permissions",
    ) -> None:
        self.system_name = system_name
        self.identity_mapping = identity_mapping
        self.role_action_mapping = role_action_mapping or {}
        self.roles_key = roles_key
        self.permissions_key = permissions_key
        self.deny_permissions_key = deny_permissions_key

    def normalize_identity(self, raw_identity: dict[str, Any]) -> IdentityContext:
        user_id = str(_pick_identity_value(raw_identity, self.identity_mapping, "user_id", "user_id", ""))
        tenant_id = str(
            _pick_identity_value(raw_identity, self.identity_mapping, "tenant_id", "tenant_id", "")
        )

        roles_raw = _pick_identity_value(raw_identity, self.identity_mapping, "roles", self.roles_key, [])
        scopes_raw = _pick_identity_value(raw_identity, self.identity_mapping, "scopes", "scopes", [])

        roles = tuple(_normalize_string_list(roles_raw))
        scopes = tuple(_normalize_string_list(scopes_raw))

        attributes = {
            key: value
            for key, value in raw_identity.items()
            if key not in {
                self.identity_mapping.get("user_id", "user_id"),
                self.identity_mapping.get("tenant_id", "tenant_id"),
                self.identity_mapping.get("roles", self.roles_key),
                self.identity_mapping.get("scopes", "scopes"),
            }
        }

        return IdentityContext(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles,
            scopes=scopes,
            attributes=attributes,
            source_system=self.system_name,
        )

    def normalize_permissions(self, raw_permissions: dict[str, Any]) -> list[PermissionFact]:
        facts: list[PermissionFact] = []

        roles = _normalize_string_list(raw_permissions.get(self.roles_key, []))
        for role in roles:
            for permission in self.role_action_mapping.get(role, []):
                facts.append(_permission_to_fact(permission, "allow", self.system_name))

        allow_permissions = _normalize_string_list(raw_permissions.get(self.permissions_key, []))
        for permission in allow_permissions:
            facts.append(_permission_to_fact(permission, "allow", self.system_name))

        deny_permissions = _normalize_string_list(raw_permissions.get(self.deny_permissions_key, []))
        for permission in deny_permissions:
            facts.append(_permission_to_fact(permission, "deny", self.system_name))

        return facts


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _permission_to_fact(permission: str, effect: str, source: str) -> PermissionFact:
    cleaned = permission.strip()
    if ":" in cleaned:
        resource_type, action = cleaned.split(":", 1)
    else:
        resource_type, action = "*", cleaned or "*"

    return PermissionFact(
        effect="allow" if effect == "allow" else "deny",
        action=action or "*",
        resource_type=resource_type or "*",
        resource_id="*",
        source=source,
    )


def _pick_identity_value(
    raw_identity: dict[str, Any],
    identity_mapping: dict[str, str],
    semantic_key: str,
    fallback_key: str,
    default: Any,
) -> Any:
    mapped_key = identity_mapping.get(semantic_key, fallback_key)
    if mapped_key in raw_identity:
        return raw_identity[mapped_key]
    if fallback_key in raw_identity:
        return raw_identity[fallback_key]
    return default
