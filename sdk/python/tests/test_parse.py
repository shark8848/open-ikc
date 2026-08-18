from __future__ import annotations

import json

import httpx
import pytest

from open_ikc_sdk import OpenIKCClient
from open_ikc_sdk.errors import OpenIKCNotImplementedError

PARSE_TASK_DATA = {
    "taskId": "pt_10001",
    "taskStatus": "QUEUED",
    "executeMode": "async",
    "resultInline": {},
}

PARSE_RESULT_DATA = {
    "parseStatus": "success",
    "resultFormat": {"type": "json"},
    "pageCount": 12,
    "chunkCount": 24,
    "failedReason": "",
}

TICKET_DATA = {
    "ticket": "tk_abc123",
    "expireAt": "2026-08-03T10:30:00Z",
    "downloadPath": "/api/v1/knowledge-documents/parse-result/download",
}

DOWNLOAD_DATA = {
    "docId": "doc_10001",
    "taskId": "pt_10001",
    "downloadPath": "/api/v1/knowledge-documents/parse-result/download?docId=doc_10001&ticket=tk_abc123",
    "format": "json",
    "note": "占位说明：真实解析结果存储落地前返回统一体，后续切换为文件流。",
}


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_parse_sends_body_and_returns_task():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(PARSE_TASK_DATA)

    client = make_client(handler)
    task = client.parse.parse(
        kbId="kb_10001",
        docId="doc_10001",
        reqId="req_parse_1",
        parseStrategy={"docType": "pdf"},
        resultFormat={"type": "json"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/parse"
    assert captured["body"] == {
        "kbId": "kb_10001",
        "docId": "doc_10001",
        "executeMode": "async",
        "reqId": "req_parse_1",
        "parseStrategy": {"docType": "pdf"},
        "resultFormat": {"type": "json"},
    }
    assert task.taskId == "pt_10001"
    assert task.taskStatus == "QUEUED"
    client.close()


def test_parse_direct_sends_body_and_returns_result():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(
            {
                "taskId": "pt_20001",
                "docId": "pdoc_20001",
                "taskStatus": "success",
                "executeMode": "sync",
                "resultInline": {"fileData": {"totalPage": 12}, "summary": "摘要"},
            }
        )

    client = make_client(handler)
    result = client.parse.parse_direct(
        source={"type": "url", "url": "https://example.com/a.pdf"},
        executeMode="sync",
        parseStrategy={"docType": "pdf"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/parse-direct"
    assert captured["body"]["source"] == {"type": "url", "url": "https://example.com/a.pdf"}
    assert captured["body"]["executeMode"] == "sync"
    assert captured["body"]["parseStrategy"] == {"docType": "pdf"}
    assert result.docId == "pdoc_20001"
    assert result.taskStatus == "success"
    assert result.resultInline["summary"] == "摘要"
    client.close()


def test_parse_omits_optional_tuning_when_not_provided():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(PARSE_TASK_DATA)

    client = make_client(handler)
    client.parse.parse(kbId="kb_10001", docId="doc_10001")
    assert set(captured["body"].keys()) == {"kbId", "docId", "executeMode"}
    client.close()


def test_parse_includes_tuning_when_provided():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(PARSE_TASK_DATA)

    client = make_client(handler)
    client.parse.parse(kbId="kb_10001", docId="doc_10001", parseMode="ocr", chunkStrategy="fixed", chunkSize=500)
    assert captured["body"]["parseMode"] == "ocr"
    assert captured["body"]["chunkStrategy"] == "fixed"
    assert captured["body"]["chunkSize"] == 500
    client.close()


def test_query_result_sends_doc_id_param():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return ok_response(PARSE_RESULT_DATA)

    client = make_client(handler)
    result = client.parse.query_result(docId="doc_10001")
    assert "docId=doc_10001" in captured["url"]
    assert result.parseStatus == "success"
    assert result.pageCount == 12
    client.close()


def test_issue_download_ticket_sends_doc_id_param():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return ok_response(TICKET_DATA)

    client = make_client(handler)
    ticket = client.parse.issue_download_ticket(docId="doc_10001")
    assert "docId=doc_10001" in captured["url"]
    assert ticket.ticket == "tk_abc123"
    assert ticket.expireAt == "2026-08-03T10:30:00Z"
    client.close()


def test_download_json_envelope_returns_download_result():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": DOWNLOAD_DATA})

    client = make_client(handler)
    result = client.parse.download(docId="doc_10001", ticket="tk_abc123")
    assert isinstance(result, object)
    assert result.docId == "doc_10001"
    assert result.format == "json"
    assert "docId=doc_10001" in captured["url"] and "ticket=tk_abc123" in captured["url"]
    client.close()


def test_download_json_envelope_error_raises():
    body = {"errCode": "501001", "errMsg": "接口已预占位，待实现", "traceId": "123", "data": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = make_client(handler)
    with pytest.raises(OpenIKCNotImplementedError):
        client.parse.download(docId="doc_10001", ticket="tk_abc123")
    client.close()


def test_download_raw_bytes_and_to_path(tmp_path):
    raw = b"%PDF-1.4 fake-content"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=raw, headers={"content-type": "application/pdf"})

    client = make_client(handler)
    content = client.parse.download(docId="doc_10001", ticket="tk_abc123")
    assert content == raw

    target = tmp_path / "result.pdf"
    content = client.parse.download(docId="doc_10001", ticket="tk_abc123", to_path=str(target))
    assert content == raw
    assert target.read_bytes() == raw
    client.close()
