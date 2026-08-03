from __future__ import annotations

from typing import Any

from app.core.authz.adapters import AuthzAdapter
from app.core.authz.policy import PolicyEngine
from app.core.authz.schema import AuthorizationDecision, AuthorizationRequest, IdentityContext


class AuthIntegrationService:
    """Independent auth integration layer for heterogeneous external systems."""

    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()
        self._adapters: dict[str, AuthzAdapter] = {}

    def register_adapter(self, system_name: str, adapter: AuthzAdapter) -> None:
        self._adapters[system_name] = adapter

    def authorize(
        self,
        *,
        system_name: str,
        raw_identity: dict[str, Any],
        raw_permissions: dict[str, Any],
        request: AuthorizationRequest,
    ) -> AuthorizationDecision:
        adapter = self._adapters.get(system_name)
        if adapter is None:
            return AuthorizationDecision(
                allow=False,
                reason="adapter not registered",
                metadata={"source_system": system_name},
            )

        identity: IdentityContext = adapter.normalize_identity(raw_identity)
        facts = adapter.normalize_permissions(raw_permissions)
        decision = self.policy_engine.evaluate(identity, request, facts)

        metadata = dict(decision.metadata)
        metadata.update(
            {
                "source_system": system_name,
                "user_id": identity.user_id,
                "tenant_id": identity.tenant_id,
            }
        )

        return AuthorizationDecision(
            allow=decision.allow,
            reason=decision.reason,
            matched_facts=decision.matched_facts,
            metadata=metadata,
        )
