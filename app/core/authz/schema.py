from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Effect = Literal["allow", "deny"]


@dataclass(frozen=True, slots=True)
class IdentityContext:
    user_id: str
    tenant_id: str = ""
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)
    source_system: str = ""


@dataclass(frozen=True, slots=True)
class PermissionFact:
    effect: Effect
    action: str
    resource_type: str = "*"
    resource_id: str = "*"
    conditions: dict[str, Any] = field(default_factory=dict)
    source: str = ""


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    action: str
    resource_type: str
    resource_id: str = "*"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allow: bool
    reason: str
    matched_facts: tuple[PermissionFact, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
