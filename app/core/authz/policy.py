from __future__ import annotations

from typing import Any

from app.core.authz.schema import AuthorizationDecision, AuthorizationRequest, IdentityContext, PermissionFact


class PolicyEngine:
    """Simple deny-overrides engine for canonical auth facts."""

    def evaluate(
        self,
        identity: IdentityContext,
        request: AuthorizationRequest,
        facts: list[PermissionFact],
    ) -> AuthorizationDecision:
        matched = [fact for fact in facts if self._matches(fact, identity, request)]
        if not matched:
            return AuthorizationDecision(
                allow=False,
                reason="no matching permission fact",
                matched_facts=(),
                metadata={"source_system": identity.source_system},
            )

        deny_facts = [fact for fact in matched if fact.effect == "deny"]
        if deny_facts:
            return AuthorizationDecision(
                allow=False,
                reason="explicit deny by policy",
                matched_facts=tuple(deny_facts),
                metadata={"source_system": identity.source_system},
            )

        allow_facts = [fact for fact in matched if fact.effect == "allow"]
        if allow_facts:
            return AuthorizationDecision(
                allow=True,
                reason="allowed by policy",
                matched_facts=tuple(allow_facts),
                metadata={"source_system": identity.source_system},
            )

        return AuthorizationDecision(
            allow=False,
            reason="no allow fact matched",
            matched_facts=(),
            metadata={"source_system": identity.source_system},
        )

    @staticmethod
    def _matches(fact: PermissionFact, identity: IdentityContext, request: AuthorizationRequest) -> bool:
        if fact.action not in {"*", request.action}:
            return False
        if fact.resource_type not in {"*", request.resource_type}:
            return False
        if fact.resource_id not in {"*", request.resource_id}:
            return False

        tenant = fact.conditions.get("tenant_id")
        if tenant is not None and tenant != identity.tenant_id:
            return False

        allowed_tenant_ids = _as_str_set(fact.conditions.get("allowed_tenant_ids"))
        if allowed_tenant_ids and identity.tenant_id not in allowed_tenant_ids:
            return False

        role_required = fact.conditions.get("required_role")
        if role_required is not None and role_required not in identity.roles:
            return False

        if not _match_data_scope(fact.effect, fact.conditions, identity, request):
            return False

        return True


def _match_data_scope(
    effect: str,
    conditions: dict[str, Any],
    identity: IdentityContext,
    request: AuthorizationRequest,
) -> bool:
    requested_resource_ids = _requested_resource_ids(request)

    # 1) 资源 ID 白名单
    allowed_resource_ids = _as_str_set(conditions.get("allowed_resource_ids"))
    if allowed_resource_ids:
        if requested_resource_ids:
            if any(resource_id not in allowed_resource_ids for resource_id in requested_resource_ids):
                return False
        elif request.resource_id not in {"*", *allowed_resource_ids}:
            return False

    # 2) 资源 ID 黑名单
    denied_resource_ids = _as_str_set(conditions.get("denied_resource_ids"))
    if denied_resource_ids:
        denied_hit = any(resource_id in denied_resource_ids for resource_id in requested_resource_ids)
        if effect == "deny":
            if not denied_hit:
                return False
        elif denied_hit:
            return False

    # 3) 仅资源所有者可访问
    owner_only = bool(conditions.get("owner_only", False))
    if owner_only:
        owner_id = str(request.context.get("owner_id", "")).strip()
        if not owner_id or owner_id != identity.user_id:
            return False

    # 4) 组织路径前缀限制（请求上下文 org_path）
    allowed_org_prefixes = _as_str_list(conditions.get("allowed_org_prefixes"))
    if allowed_org_prefixes:
        org_path = str(request.context.get("org_path", "")).strip()
        if not org_path:
            return False
        if not any(org_path.startswith(prefix) for prefix in allowed_org_prefixes):
            return False

    # 5) 身份属性中的部门限制
    allowed_departments = _as_str_set(conditions.get("allowed_departments"))
    if allowed_departments:
        department = str(identity.attributes.get("department", "")).strip()
        if not department or department not in allowed_departments:
            return False

    return True


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _as_str_set(value: Any) -> set[str]:
    return set(_as_str_list(value))


def _requested_resource_ids(request: AuthorizationRequest) -> list[str]:
    raw_ids = request.context.get("kb_ids")
    if isinstance(raw_ids, list):
        ids = [str(item).strip() for item in raw_ids if str(item).strip()]
        if ids:
            return ids

    if request.resource_id and request.resource_id != "*":
        return [request.resource_id]

    return []
