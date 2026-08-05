from __future__ import annotations

import json

import httpx
import pytest

from open_ikc_sdk import DocumentSource, OpenIKCClient
from open_ikc_sdk.errors import OpenIKCConnectionError, OpenIKCNotFoundError

INGEST_DATA = {
    "ingestTaskId": "it_10001",
    "docId": "doc_10001",
    "docIds": [],
    "taskStatus": "SUCCEEDED",
    "sourceType": "file",
    "sourceStats": {"total": 1, "success": 1, "failed": 0},
    "ingestTime": "2026-08-03T10:20:30Z",
}

INGEST_AND_PARSE_DATA = {
    "ingestTaskId": "it_10001",
    "parseTaskId": "pt_10001",
    "docId": "doc_10001",
    "taskStatus": "PARSING",
    "executeMode": "async",
    "resultInline": {},
}

DOC_INFO_DATA = {
    "docId": "doc_10001",
    "docTitle": "产品白皮书",
    "kbId": "kb_10001",
    "sourceType": "url",
    "sourceUrl": "https://example.com/files/spec.pdf",
    "objectKey": "",
    "tags": ["产品", "2026"],
    "metadata": {"owner": "u100"},
    "status": "INGESTED",
    "ingestTime": "2026-08-03T10:20:30Z",
    "updateTime": None,
}


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_ingest_sends_minimal_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(INGEST_DATA)

    client = make_client(handler)
    result = client.documents.ingest(
        kbId="kb_10001",
        source={"type": "file", "objectKey": "oss://bucket/a.pdf"},
    )
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/knowledge-documents/ingest"
    assert captured["body"] == {
        "kbId": "kb_10001",
        "source": {"type": "file", "objectKey": "oss://bucket/a.pdf"},
        "orchestrationMode": "split",
    }
    assert result.ingestTaskId == "it_10001"
    assert result.docId == "doc_10001"
    assert result.taskStatus == "SUCCEEDED"
    client.close()


def test_ingest_includes_optional_fields_when_provided():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(INGEST_DATA)

    client = make_client(handler)
    client.documents.ingest(
        kbId="kb_10001",
        source=DocumentSource(type="url", url="https://example.com/spec.pdf"),
        reqId="req_1",
        teamId="team_01",
        orgId="org_001",
        docTitle="规格书",
        tags=["合同"],
        metadata={"system": "erp"},
        orchestrationMode="quick",
    )
    body = captured["body"]
    assert body["reqId"] == "req_1"
    assert body["teamId"] == "team_01"
    assert body["orgId"] == "org_001"
    assert body["docTitle"] == "规格书"
    assert body["tags"] == ["合同"]
    assert body["metadata"] == {"system": "erp"}
    assert body["orchestrationMode"] == "quick"
    assert body["source"] == {
        "type": "url",
        "url": "https://example.com/spec.pdf",
        "objectKey": "",
        "fileToken": "",
        "archive": {},
        "directory": {},
        "metadata": {},
    }
    client.close()


def test_ingest_source_accepts_document_source_instance():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(INGEST_DATA)

    client = make_client(handler)
    client.documents.ingest(
        kbId="kb_10001",
        source=DocumentSource(type="archive", objectKey="oss://bucket/x.zip", archive={"format": "zip"}),
    )
    assert captured["body"]["source"] == {
        "type": "archive",
        "objectKey": "oss://bucket/x.zip",
        "archive": {"format": "zip"},
        "url": "",
        "fileToken": "",
        "directory": {},
        "metadata": {},
    }
    client.close()


def test_ingest_and_parse_sends_parse_options():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({**INGEST_AND_PARSE_DATA, "executeMode": "sync"})

    client = make_client(handler)
    result = client.documents.ingest_and_parse(
        kbId="kb_10001",
        source={"type": "url", "url": "https://example.com/spec.pdf"},
        reqId="req_2",
        parseStrategy={"docType": "pdf", "parseMethod": "auto"},
        resultFormat={"type": "json"},
        executeMode="sync",
    )
    assert captured["path"] == "/api/v1/knowledge-documents/ingest-and-parse"
    body = captured["body"]
    assert body["parseStrategy"] == {"docType": "pdf", "parseMethod": "auto"}
    assert body["resultFormat"] == {"type": "json"}
    assert body["executeMode"] == "sync"
    assert result.parseTaskId == "pt_10001"
    assert result.executeMode == "sync"
    client.close()


def test_get_document_substitutes_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response(DOC_INFO_DATA)

    client = make_client(handler)
    info = client.documents.get("doc_10001")
    assert captured["path"] == "/api/v1/knowledge-documents/doc_10001"
    assert info.docTitle == "产品白皮书"
    assert info.tags == ["产品", "2026"]
    assert info.metadata == {"owner": "u100"}
    client.close()


def test_document_info_extra_fields_passthrough():
    client = make_client(lambda r: ok_response({**DOC_INFO_DATA, "futureField": "v"}))
    info = client.documents.get("doc_10001")
    assert info.extra == {"futureField": "v"}
    client.close()


def test_ingest_post_with_req_id_retried_on_connection_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("boom", request=request)
        return ok_response(INGEST_DATA)

    client = make_client(handler)
    result = client.documents.ingest(kbId="kb_10001", source={"type": "file", "objectKey": "k"}, reqId="req_retry")
    assert result.ingestTaskId == "it_10001"
    assert len(calls) == 2
    client.close()


def test_ingest_post_without_req_id_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("boom", request=request)

    client = make_client(handler)
    with pytest.raises(OpenIKCConnectionError):
        client.documents.ingest(kbId="kb_10001", source={"type": "file", "objectKey": "k"})
    assert len(calls) == 1
    client.close()


def test_business_error_raises_mapped_exception():
    body = {"errCode": "100404", "errMsg": "资源不存在", "traceId": "123", "data": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = make_client(handler)
    with pytest.raises(OpenIKCNotFoundError):
        client.documents.get("doc_missing")
    client.close()
