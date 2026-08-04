from __future__ import annotations

from typing import Any

from app.core.authz.policy import PolicyEngine
from app.core.authz.schema import AuthorizationRequest, IdentityContext, PermissionFact


engine = PolicyEngine()


def _identity(**overrides: Any) -> IdentityContext:
    defaults: dict[str, Any] = {
        "user_id": "u1",
        "tenant_id": "t1",
        "roles": (),
        "attributes": {},
    }
    defaults.update(overrides)
    return IdentityContext(**defaults)


def _fact(
    *,
    action: str = "query",
    resource_type: str = "search",
    resource_id: str = "*",
    effect: str = "allow",
    conditions: dict[str, Any] | None = None,
) -> PermissionFact:
    return PermissionFact(
        effect=effect,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        conditions=conditions or {},
        source="test",
    )


def _request(
    *,
    action: str = "query",
    resource_type: str = "search",
    resource_id: str = "*",
    context: dict[str, Any] | None = None,
) -> AuthorizationRequest:
    return AuthorizationRequest(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        context=context or {},
    )


def test_allow_when_action_and_resource_match() -> None:
    decision = engine.evaluate(_identity(), _request(), [_fact()])
    assert decision.allow is True
    assert decision.reason == "allowed by policy"


def test_denied_when_no_fact_matches_action() -> None:
    decision = engine.evaluate(_identity(), _request(action="read"), [_fact(action="query")])
    assert decision.allow is False
    assert decision.reason == "no matching permission fact"


def test_wildcard_fact_matches_any_request() -> None:
    fact = _fact(action="*", resource_type="*")
    decision = engine.evaluate(
        _identity(),
        _request(action="query", resource_type="document", resource_id="kb_9"),
        [fact],
    )
    assert decision.allow is True


def test_resource_id_whitelist() -> None:
    fact = _fact(conditions={"allowed_resource_ids": ["kb_1", "kb_2"]})
    assert engine.evaluate(_identity(), _request(resource_id="kb_1"), [fact]).allow is True
    assert engine.evaluate(_identity(), _request(resource_id="kb_3"), [fact]).allow is False


def test_kb_ids_context_whitelist() -> None:
    fact = _fact(conditions={"allowed_resource_ids": ["kb_1", "kb_2"]})
    ok = engine.evaluate(_identity(), _request(context={"kb_ids": ["kb_1", "kb_2"]}), [fact])
    bad = engine.evaluate(_identity(), _request(context={"kb_ids": ["kb_1", "kb_3"]}), [fact])
    assert ok.allow is True
    assert bad.allow is False


def test_resource_id_blacklist_blocks_allow_fact() -> None:
    fact = _fact(conditions={"denied_resource_ids": ["kb_secret"]})
    decision = engine.evaluate(_identity(), _request(resource_id="kb_secret"), [fact])
    assert decision.allow is False
    assert decision.reason == "no matching permission fact"


def test_deny_fact_matches_blacklisted_resource() -> None:
    deny_fact = _fact(effect="deny", conditions={"denied_resource_ids": ["kb_secret"]})
    allow_fact = _fact()
    decision = engine.evaluate(
        _identity(),
        _request(resource_id="kb_secret"),
        [allow_fact, deny_fact],
    )
    assert decision.allow is False
    assert decision.reason == "explicit deny by policy"


def test_deny_fact_ignored_for_non_blacklisted_resource() -> None:
    deny_fact = _fact(effect="deny", conditions={"denied_resource_ids": ["kb_secret"]})
    decision = engine.evaluate(_identity(), _request(resource_id="kb_other"), [deny_fact])
    assert decision.allow is False
    assert decision.reason == "no matching permission fact"


def test_owner_only_condition() -> None:
    fact = _fact(conditions={"owner_only": True})
    identity = _identity(user_id="u1")
    assert engine.evaluate(identity, _request(context={"owner_id": "u1"}), [fact]).allow is True
    assert engine.evaluate(identity, _request(context={"owner_id": "u2"}), [fact]).allow is False
    assert engine.evaluate(identity, _request(), [fact]).allow is False


def test_org_path_prefix_condition() -> None:
    fact = _fact(conditions={"allowed_org_prefixes": ["/org/tech", "/org/ops"]})
    ok = engine.evaluate(_identity(), _request(context={"org_path": "/org/tech/platform"}), [fact])
    bad = engine.evaluate(_identity(), _request(context={"org_path": "/org/sales"}), [fact])
    missing = engine.evaluate(_identity(), _request(), [fact])
    assert ok.allow is True
    assert bad.allow is False
    assert missing.allow is False


def test_department_condition() -> None:
    fact = _fact(conditions={"allowed_departments": ["platform", "ai"]})
    ok = engine.evaluate(_identity(attributes={"department": "platform"}), _request(), [fact])
    bad = engine.evaluate(_identity(attributes={"department": "hr"}), _request(), [fact])
    missing = engine.evaluate(_identity(), _request(), [fact])
    assert ok.allow is True
    assert bad.allow is False
    assert missing.allow is False


def test_tenant_id_condition() -> None:
    fact = _fact(conditions={"tenant_id": "t1"})
    assert engine.evaluate(_identity(tenant_id="t1"), _request(), [fact]).allow is True
    assert engine.evaluate(_identity(tenant_id="t2"), _request(), [fact]).allow is False


def test_allowed_tenant_ids_condition() -> None:
    fact = _fact(conditions={"allowed_tenant_ids": ["t1", "t3"]})
    assert engine.evaluate(_identity(tenant_id="t1"), _request(), [fact]).allow is True
    assert engine.evaluate(_identity(tenant_id="t2"), _request(), [fact]).allow is False


def test_required_role_condition() -> None:
    fact = _fact(conditions={"required_role": "km_reader"})
    ok = engine.evaluate(_identity(roles=("km_reader",)), _request(), [fact])
    bad = engine.evaluate(_identity(roles=("km_admin",)), _request(), [fact])
    assert ok.allow is True
    assert bad.allow is False
