from __future__ import annotations

import httpx
import pytest

from open_ikc_sdk import CallerIdentity, OpenIKCClient
from open_ikc_sdk.errors import (
    OpenIKCForbiddenError,
    OpenIKCHTTPStatusError,
    OpenIKCNotImplementedError,
    OpenIKCNotFoundError,
)

SUCCESS_BODY = {"errCode": "000000", "errMsg": "success", "data": {}, "traceId": "123"}


def make_client(handler: httpx.MockTransport, **kwargs) -> OpenIKCClient:
    kwargs.setdefault("token", "secret-token")
    return OpenIKCClient(
        "http://platform.test",
        http_client=httpx.Client(transport=handler, timeout=1),
        **kwargs,
    )


def test_request_returns_envelope_on_success():
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=SUCCESS_BODY)))
    envelope = client.request("GET", "/api/v1/ping")
    assert envelope.ok
    assert envelope.trace_id == "123"
    client.close()


def test_request_raises_mapped_exception_on_business_error():
    body = {"errCode": "501001", "errMsg": "接口已预占位，待实现", "data": {}, "traceId": "123"}
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    with pytest.raises(OpenIKCNotImplementedError):
        client.request("GET", "/api/v1/knowledge-documents/parse")
    client.close()


def test_raw_returns_envelope_without_raising():
    body = {"errCode": "100403", "errMsg": "无权限", "data": {}, "traceId": "123"}
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    envelope = client.raw("GET", "/api/v1/knowledge-bases/kb_1")
    assert envelope.err_code == "100403"
    client.close()


def test_http_error_with_envelope_raises_mapped_exception():
    body = {"errCode": "100404", "errMsg": "资源不存在", "data": {}, "traceId": "123"}
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(404, json=body)))
    with pytest.raises(OpenIKCNotFoundError):
        client.request("GET", "/api/v1/knowledge-bases/kb_missing")
    client.close()


def test_http_error_without_envelope_raises_status_error():
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(500, text="oops")))
    with pytest.raises(OpenIKCHTTPStatusError) as exc_info:
        client.request("GET", "/api/v1/ping")
    assert exc_info.value.status_code == 500
    client.close()


def test_path_params_are_substituted():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=SUCCESS_BODY)

    client = make_client(httpx.MockTransport(handler))
    client.request("GET", "/api/v1/knowledge-bases/{kb_id}", path_params={"kb_id": "kb_9"})
    assert captured["url"] == "http://platform.test/api/v1/knowledge-bases/kb_9"
    client.close()


def test_request_headers_sent():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return httpx.Response(200, json=SUCCESS_BODY)

    client = make_client(httpx.MockTransport(handler), identity=CallerIdentity(user_id="u100", tenant_id="t1"))
    client.request("GET", "/api/v1/ping")
    headers = captured["headers"]
    assert headers["authorization"] == "Bearer secret-token"
    assert headers["x-request-id"].isdigit() and len(headers["x-request-id"]) == 23
    assert headers["x-trace-id"] == headers["x-request-id"]
    assert headers["x-user-id"] == "u100"
    assert headers["x-tenant-id"] == "t1"
    assert headers["user-agent"].startswith("open-ikc-sdk/")
    client.close()


def test_fixed_trace_id_reused():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["trace_id"] = request.headers.get("X-Request-Id")
        return httpx.Response(200, json=SUCCESS_BODY)

    client = make_client(httpx.MockTransport(handler), trace_id="99988877766655544433321")
    client.request("GET", "/api/v1/ping")
    assert captured["trace_id"] == "99988877766655544433321"
    client.close()


def test_fetch_catalog_returns_json():
    payload = [{"category": "知识库", "tag": "knowledge-base", "routes": []}]
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    assert client.fetch_catalog() == payload
    client.close()


def test_fetch_error_codes_returns_json():
    payload = [{"code": "000000", "message": "success"}]
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    assert client.fetch_error_codes() == payload
    client.close()


def test_repr_hides_token():
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=SUCCESS_BODY)))
    assert "secret-token" not in repr(client)
    assert "<set>" in repr(client)
    client.close()


def test_context_manager_closes_client():
    client = make_client(httpx.MockTransport(lambda r: httpx.Response(200, json=SUCCESS_BODY)))
    with client:
        assert client.raw("GET", "/api/v1/ping").ok
