from __future__ import annotations

"""client_from_env 引导工厂测试：环境变量 → 客户端 / 认证 / AUTHZ 身份头组装。"""

import httpx
import pytest

from open_ikc_sdk._bootstrap import client_from_env
from open_ikc_sdk.headers import CallerIdentity


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清理相关环境变量，避免宿主环境干扰。"""
    for key in (
        "OPEN_PLATFORM_BASE_URL",
        "OPEN_PLATFORM_TOKEN",
        "OPEN_PLATFORM_TOKENS",
        "OPEN_PLATFORM_USER_ID",
        "OPEN_PLATFORM_TENANT_ID",
        "OPEN_PLATFORM_ROLES",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


def test_default_base_url_and_no_token(monkeypatch):
    client = client_from_env()
    assert client._transport._base_url == "http://127.0.0.1:18000"
    assert client._transport._token is None
    assert client._transport.has_token is False
    client.close()


def test_base_url_and_token_env(monkeypatch):
    monkeypatch.setenv("OPEN_PLATFORM_BASE_URL", "http://platform:18000")
    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "tok_123")
    client = client_from_env()
    assert client._transport._base_url == "http://platform:18000"
    assert client._transport._token == "tok_123"
    client.close()


def test_multiple_tokens_takes_first(monkeypatch):
    monkeypatch.setenv("OPEN_PLATFORM_TOKENS", "tok_a, tok_b, tok_c")
    client = client_from_env()
    assert client._transport._token == "tok_a"
    client.close()


def test_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("OPEN_PLATFORM_BASE_URL", "http://from-env:18000")
    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "env_tok")
    client = client_from_env(base_url="http://explicit:18000", token="explicit_tok")
    assert client._transport._base_url == "http://explicit:18000"
    assert client._transport._token == "explicit_tok"
    client.close()


def test_identity_from_env(monkeypatch):
    monkeypatch.setenv("OPEN_PLATFORM_USER_ID", "u100")
    monkeypatch.setenv("OPEN_PLATFORM_TENANT_ID", "t1")
    monkeypatch.setenv("OPEN_PLATFORM_ROLES", "km_reader, km_admin")
    client = client_from_env()
    identity = client._transport._identity
    assert isinstance(identity, CallerIdentity)
    assert identity.user_id == "u100"
    assert identity.tenant_id == "t1"
    assert identity.roles == ["km_reader", "km_admin"]
    client.close()


def test_no_identity_when_all_empty():
    client = client_from_env()
    assert client._transport._identity is None
    client.close()


def test_extra_kwargs_passthrough():
    client = client_from_env(max_retries=0, timeout=1.0)
    assert client._transport._max_retries == 0
    assert client._transport._timeout.read == 1.0
    client.close()


def test_send_request_with_env_credentials(monkeypatch):
    """端到端：环境变量凭据真实附加到请求头。"""
    monkeypatch.setenv("OPEN_PLATFORM_BASE_URL", "http://platform.test")
    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "tok_abc")
    monkeypatch.setenv("OPEN_PLATFORM_USER_ID", "u100")
    monkeypatch.setenv("OPEN_PLATFORM_ROLES", "km_reader")

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": {}})

    client = client_from_env(http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1))
    client.request("GET", "/health")
    assert captured["headers"]["authorization"] == "Bearer tok_abc"
    assert captured["headers"]["x-user-id"] == "u100"
    assert captured["headers"]["x-user-roles"] == "km_reader"
    client.close()
