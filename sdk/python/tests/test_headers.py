from __future__ import annotations

from open_ikc_sdk.headers import CallerIdentity, build_headers


def test_authorization_header_sent_when_token_set():
    headers = build_headers(token="secret", trace_id="123")
    assert headers["Authorization"] == "Bearer secret"


def test_authorization_header_absent_without_token():
    headers = build_headers(token=None, trace_id="123")
    assert "Authorization" not in headers


def test_trace_headers_always_present():
    headers = build_headers(token=None, trace_id="12345678901234567890123")
    assert headers["X-Request-Id"] == "12345678901234567890123"
    assert headers["X-Trace-Id"] == "12345678901234567890123"


def test_identity_headers_sent_only_when_non_empty():
    identity = CallerIdentity(user_id="u100", tenant_id="t1", roles=["admin"], permissions=[], deny_permissions=None)
    headers = build_headers(token=None, trace_id="123", identity=identity)
    assert headers["X-User-Id"] == "u100"
    assert headers["X-Tenant-Id"] == "t1"
    assert headers["X-User-Roles"] == "admin"
    assert "X-User-Permissions" not in headers
    assert "X-User-Deny-Permissions" not in headers


def test_identity_list_headers_joined_by_comma():
    identity = CallerIdentity(permissions=["kb:read", "kb:write"], deny_permissions=["kb:delete"])
    headers = build_headers(token=None, trace_id="123", identity=identity)
    assert headers["X-User-Permissions"] == "kb:read,kb:write"
    assert headers["X-User-Deny-Permissions"] == "kb:delete"


def test_auth_system_header():
    identity = CallerIdentity(auth_system="digital_employee")
    headers = build_headers(token=None, trace_id="123", identity=identity)
    assert headers["X-Auth-System"] == "digital_employee"


def test_extra_headers_override_defaults():
    headers = build_headers(token=None, trace_id="123", extra_headers={"X-Trace-Id": "custom", "X-Forwarded-For": "1.2.3.4"})
    assert headers["X-Trace-Id"] == "custom"
    assert headers["X-Forwarded-For"] == "1.2.3.4"


def test_user_agent_contains_version():
    headers = build_headers(token=None, trace_id="123")
    assert headers["User-Agent"].startswith("open-ikc-sdk/")
