from __future__ import annotations

import httpx
import pytest

from open_ikc_sdk import OpenIKCClient
from open_ikc_sdk.errors import OpenIKCConnectionError, OpenIKCForbiddenError, OpenIKCTimeoutError

SUCCESS_BODY = {"errCode": "000000", "errMsg": "success", "data": {}, "traceId": "123"}


def make_client(handler: httpx.MockTransport, max_retries: int = 2) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        max_retries=max_retries,
        http_client=httpx.Client(transport=handler, timeout=1),
    )


def test_connection_error_retried_for_get():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=SUCCESS_BODY)

    client = make_client(httpx.MockTransport(handler))
    envelope = client.raw("GET", "/api/v1/ping")
    assert envelope.ok
    assert len(calls) == 2
    client.close()


def test_post_without_req_id_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("boom", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(OpenIKCConnectionError):
        client.raw("POST", "/api/v1/knowledge-bases/create", body={"kbName": "x"})
    assert len(calls) == 1
    client.close()


def test_post_with_req_id_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=SUCCESS_BODY)

    client = make_client(httpx.MockTransport(handler))
    envelope = client.raw("POST", "/api/v1/knowledge-documents/ingest", body={"reqId": "r1"})
    assert envelope.ok
    assert len(calls) == 2
    client.close()


def test_503_retried_for_get():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, text="upstream down")
        return httpx.Response(200, json=SUCCESS_BODY)

    client = make_client(httpx.MockTransport(handler))
    assert client.raw("GET", "/api/v1/ping").ok
    assert len(calls) == 2
    client.close()


def test_business_error_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"errCode": "100403", "errMsg": "无权限", "data": {}, "traceId": "123"})

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(OpenIKCForbiddenError):
        client.request("GET", "/api/v1/knowledge-bases/kb_1")
    assert len(calls) == 1
    client.close()


def test_read_timeout_maps_to_timeout_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(OpenIKCTimeoutError):
        client.request("GET", "/api/v1/ping")
    client.close()
