from __future__ import annotations

from app.core.authz import AuthIntegrationService, AuthorizationRequest, MappingAuthzAdapter


DIGITAL_EMPLOYEE_ADAPTER = MappingAuthzAdapter(
    "digital_employee",
    identity_mapping={
        "user_id": "employee_id",
        "tenant_id": "tenant_code",
        "roles": "role_codes",
        "scopes": "scopes",
    },
    role_action_mapping={
        "de_km_reader": ["search:query", "knowledge_base:read"],
        "de_km_admin": ["*:*"],
    },
)


DEFAULT_ADAPTER = MappingAuthzAdapter(
    "default",
    identity_mapping={
        "user_id": "user_id",
        "tenant_id": "tenant_id",
        "roles": "roles",
        "scopes": "scopes",
    },
    role_action_mapping={
        "km_reader": ["search:query"],
        "km_admin": ["*:*"],
    },
)


def test_normalize_identity_uses_mapped_keys() -> None:
    identity = DIGITAL_EMPLOYEE_ADAPTER.normalize_identity(
        {
            "employee_id": "e100",
            "tenant_code": "t1",
            "role_codes": ["de_km_reader", "de_km_admin"],
            "scopes": "s1",
        }
    )
    assert identity.user_id == "e100"
    assert identity.tenant_id == "t1"
    assert identity.roles == ("de_km_reader", "de_km_admin")
    assert identity.scopes == ("s1",)
    assert identity.source_system == "digital_employee"


def test_normalize_identity_skips_empty_mapped_value_and_falls_back() -> None:
    identity = DIGITAL_EMPLOYEE_ADAPTER.normalize_identity(
        {
            "employee_id": "",
            "tenant_code": None,
            "role_codes": [],
            "user_id": "u_fallback",
            "tenant_id": "t_fallback",
            "roles": ["km_reader"],
        }
    )
    assert identity.user_id == "u_fallback"
    assert identity.tenant_id == "t_fallback"
    assert identity.roles == ("km_reader",)


def test_normalize_identity_uses_semantic_keys_without_mapping() -> None:
    adapter = MappingAuthzAdapter("default", identity_mapping={})
    identity = adapter.normalize_identity(
        {
            "user_id": "u1",
            "tenant_id": "t1",
            "roles": ["km_admin"],
        }
    )
    assert identity.user_id == "u1"
    assert identity.tenant_id == "t1"
    assert identity.roles == ("km_admin",)


def test_normalize_identity_defaults_to_empty() -> None:
    identity = DIGITAL_EMPLOYEE_ADAPTER.normalize_identity({})
    assert identity.user_id == ""
    assert identity.tenant_id == ""
    assert identity.roles == ()
    assert identity.scopes == ()


def test_normalize_identity_roles_accepts_string_and_list() -> None:
    from_string = DEFAULT_ADAPTER.normalize_identity({"roles": "km_reader"})
    from_list = DEFAULT_ADAPTER.normalize_identity({"roles": ["km_reader", ""]})
    assert from_string.roles == ("km_reader",)
    assert from_list.roles == ("km_reader",)


def test_normalize_identity_attributes_exclude_identity_keys() -> None:
    identity = DIGITAL_EMPLOYEE_ADAPTER.normalize_identity(
        {
            "employee_id": "e100",
            "tenant_code": "t1",
            "role_codes": ["de_km_reader"],
            "department": "platform",
        }
    )
    assert "department" in identity.attributes
    assert "employee_id" not in identity.attributes
    assert "tenant_code" not in identity.attributes
    assert "role_codes" not in identity.attributes


def test_normalize_permissions_builds_allow_and_deny_facts() -> None:
    facts = DEFAULT_ADAPTER.normalize_permissions(
        {
            "roles": ["km_reader", "unknown_role"],
            "permissions": ["document:read"],
            "deny_permissions": ["search:query"],
        }
    )

    allows = {(fact.resource_type, fact.action) for fact in facts if fact.effect == "allow"}
    denies = {(fact.resource_type, fact.action) for fact in facts if fact.effect == "deny"}
    assert ("search", "query") in allows
    assert ("document", "read") in allows
    assert ("search", "query") in denies
    assert len(facts) == 3


def test_authorize_allows_km_reader_search_query() -> None:
    service = AuthIntegrationService()
    service.register_adapter("default", DEFAULT_ADAPTER)

    decision = service.authorize(
        system_name="default",
        raw_identity={"user_id": "u1", "tenant_id": "t1", "roles": ["km_reader"]},
        raw_permissions={"roles": ["km_reader"], "permissions": [], "deny_permissions": []},
        request=AuthorizationRequest(action="query", resource_type="search"),
    )
    assert decision.allow is True
    assert decision.metadata["user_id"] == "u1"


def test_authorize_deny_overrides_allow() -> None:
    service = AuthIntegrationService()
    service.register_adapter("default", DEFAULT_ADAPTER)

    decision = service.authorize(
        system_name="default",
        raw_identity={"user_id": "u1", "tenant_id": "t1", "roles": ["km_reader"]},
        raw_permissions={
            "roles": ["km_reader"],
            "permissions": [],
            "deny_permissions": ["search:query"],
        },
        request=AuthorizationRequest(action="query", resource_type="search"),
    )
    assert decision.allow is False
    assert decision.reason == "explicit deny by policy"


def test_authorize_denied_without_matching_facts() -> None:
    service = AuthIntegrationService()
    service.register_adapter("default", DEFAULT_ADAPTER)

    decision = service.authorize(
        system_name="default",
        raw_identity={"user_id": "u1", "tenant_id": "t1", "roles": []},
        raw_permissions={"roles": [], "permissions": [], "deny_permissions": []},
        request=AuthorizationRequest(action="query", resource_type="search"),
    )
    assert decision.allow is False


def test_authorize_denied_for_unregistered_system() -> None:
    service = AuthIntegrationService()
    service.register_adapter("default", DEFAULT_ADAPTER)

    decision = service.authorize(
        system_name="unknown",
        raw_identity={"user_id": "u1"},
        raw_permissions={},
        request=AuthorizationRequest(action="query", resource_type="search"),
    )
    assert decision.allow is False
    assert decision.reason == "adapter not registered"


def test_mapping_facts_resource_id_wildcard() -> None:
    """固化当前行为：内置映射生成的事实 resource_id 恒为 '*'，
    request.resource_id 不参与策略决策，资源级授权由 service 业务校验兜底。"""
    service = AuthIntegrationService()
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
            role_action_mapping={"km_reader": ["document:read"]},
        ),
    )
    identity = {"user_id": "u1", "tenant_id": "t1", "roles": ["km_reader"]}
    permissions = {"roles": ["km_reader"], "permissions": [], "deny_permissions": []}

    first = service.authorize(
        system_name="default",
        raw_identity=identity,
        raw_permissions=permissions,
        request=AuthorizationRequest(action="read", resource_type="document", resource_id="kb_9"),
    )
    other = service.authorize(
        system_name="default",
        raw_identity=identity,
        raw_permissions=permissions,
        request=AuthorizationRequest(action="read", resource_type="document", resource_id="kb_999"),
    )
    assert first.allow is True
    assert other.allow is True
