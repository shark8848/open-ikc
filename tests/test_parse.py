from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_store import DocumentStore
from app.services.knowledge_base_store import KnowledgeBaseStore
from app.services.parse_store import ParseTaskStore, ParseTicketStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
PARSE_TASK_ID_PATTERN = re.compile(r"^parse_\d{17}$")
DOC_ID_PATTERN = re.compile(r"^doc_\d{17}$")


@pytest.fixture(autouse=True)
def reset_parse_stores() -> None:
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    ParseTaskStore.reset()
    ParseTicketStore.reset()
    yield
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    ParseTaskStore.reset()
    ParseTicketStore.reset()


def _create_kb(headers: dict | None = None, **overrides) -> dict:
    payload = {
        "kbName": "解析知识库",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "解析域集成测试库",
        "bizDomain": "customer_service",
        "visibility": "private",
        "metadataSchema": [],
    }
    payload.update(overrides)
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=headers or AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _ingest(kb_id: str, headers: dict | None = None, **overrides) -> dict:
    payload = {
        "kbId": kb_id,
        "source": {"type": "url", "url": "https://example.com/parse-spec.pdf"},
    }
    payload.update(overrides)
    response = client.post("/api/v1/knowledge-documents/ingest", json=payload, headers=headers or AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _parse(payload: dict, headers: dict | None = None) -> dict:
    response = client.post("/api/v1/knowledge-documents/parse", json=payload, headers=headers or AUTH)
    return response.json()


def _query(doc_id: str, headers: dict | None = None) -> dict:
    response = client.get(
        "/api/v1/knowledge-documents/parse-result/query",
        params={"docId": doc_id},
        headers=headers or AUTH,
    )
    return response.json()


def _issue_ticket(doc_id: str, headers: dict | None = None) -> dict:
    response = client.get(
        "/api/v1/knowledge-documents/parse-result/issue-download-ticket",
        params={"docId": doc_id},
        headers=headers or AUTH,
    )
    return response.json()


def _download(doc_id: str, ticket: str, headers: dict | None = None) -> dict:
    response = client.get(
        "/api/v1/knowledge-documents/parse-result/download",
        params={"docId": doc_id, "ticket": ticket},
        headers=headers or AUTH,
    )
    return response.json()


def _parse_payload(doc_id: str, kb_id: str = "kb_placeholder", **overrides) -> dict:
    payload: dict = {
        "kbId": kb_id,
        "docId": doc_id,
        "parseStrategy": {"docType": "pdf", "parseMethod": "auto"},
        "resultFormat": {"type": "json", "includeLayout": True},
        "executeMode": "async",
    }
    payload.update(overrides)
    return payload


def test_parse_async_success() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    body = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"]))
    assert body["errCode"] == "000000"
    data = body["data"]
    assert PARSE_TASK_ID_PATTERN.match(data["taskId"])
    assert data["taskStatus"] == "queued"
    assert data["executeMode"] == "async"
    assert data["resultInline"] == {}


def test_parse_sync_returns_inline_result() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    body = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"], executeMode="sync"))
    assert body["errCode"] == "000000"
    data = body["data"]
    assert PARSE_TASK_ID_PATTERN.match(data["taskId"])
    assert data["taskStatus"] == "success"
    assert data["executeMode"] == "sync"
    inline = data["resultInline"]
    assert inline["fileData"]["totalPage"] == 12
    assert inline["summary"]


def test_parse_document_not_found() -> None:
    body = _parse(_parse_payload("doc_missing"))
    assert body["errCode"] == "100404"


def test_parse_personal_by_non_owner_forbidden() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    kb = _create_kb(headers=alice)
    doc = _ingest(kb["kbId"], headers=alice)
    body = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"]), headers=bob)
    assert body["errCode"] == "100403"


def test_parse_idempotent_reuses_success_task() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    first = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"]))
    second = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"]))
    assert first["errCode"] == "000000"
    assert second["errCode"] == "000000"
    assert second["data"]["taskId"] == first["data"]["taskId"]
    assert second["data"]["taskStatus"] == "queued"


def test_query_parse_result_success() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"], executeMode="sync"))
    body = _query(doc["docId"])
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["parseStatus"] == "success"
    assert data["resultFormat"]["type"] == "json"
    assert data["pageCount"] == 12
    assert data["chunkCount"] == 24


def test_query_parse_result_not_parsed_yet() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    body = _query(doc["docId"])
    assert body["errCode"] == "200003"


def test_query_parse_result_document_not_found() -> None:
    body = _query("doc_missing")
    assert body["errCode"] == "100404"


def test_issue_download_ticket_and_download_success() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"], executeMode="sync"))
    ticket_body = _issue_ticket(doc["docId"])
    assert ticket_body["errCode"] == "000000"
    ticket_data = ticket_body["data"]
    assert ticket_data["ticket"].startswith("dlt_")
    assert ticket_data["expireAt"].endswith("Z")
    assert ticket_data["downloadPath"] == "/api/v1/knowledge-documents/parse-result/download"

    body = _download(doc["docId"], ticket_data["ticket"])
    assert body["errCode"] == "000000"
    assert body["data"]["docId"] == doc["docId"]
    assert body["data"]["format"] == "json"


def test_issue_ticket_when_result_not_ready() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    body = _issue_ticket(doc["docId"])
    assert body["errCode"] == "200003"


def test_download_with_invalid_ticket() -> None:
    kb = _create_kb()
    doc = _ingest(kb["kbId"])
    _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"], executeMode="sync"))
    body = _download(doc["docId"], "dlt_invalid_token")
    assert body["errCode"] == "200004"


def test_download_with_ticket_for_other_document() -> None:
    kb = _create_kb()
    doc_a = _ingest(kb["kbId"])
    _parse(_parse_payload(doc_a["docId"], kb_id=kb["kbId"], executeMode="sync"))
    ticket = _issue_ticket(doc_a["docId"])["data"]["ticket"]
    doc_b = _ingest(kb["kbId"], source={"type": "url", "url": "https://example.com/other.pdf"})
    body = _download(doc_b["docId"], ticket)
    assert body["errCode"] == "200004"


def test_authz_parse_denied_for_reader(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    reader = {**AUTH, "X-User-Id": "bob", "X-User-Roles": "km_reader"}
    kb = _create_kb(headers=admin)
    doc = _ingest(kb["kbId"], headers=admin)
    body = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"]), headers=reader)
    assert body["errCode"] == "100403"


def test_authz_parse_allowed_for_admin(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    kb = _create_kb(headers=admin)
    doc = _ingest(kb["kbId"], headers=admin)
    body = _parse(_parse_payload(doc["docId"], kb_id=kb["kbId"]), headers=admin)
    assert body["errCode"] == "000000"


def test_error_codes_registered() -> None:
    from app.core.error_codes import error_code_catalog

    codes = {item["code"] for item in error_code_catalog()}
    assert {"200003", "200004", "200011"} <= codes

def test_parse_kb_id_mismatch_returns_invalid_params() -> None:
    kb1 = _create_kb()
    kb2 = _create_kb(kbName="解析知识库B")
    doc = _ingest(kb1["kbId"])
    body = _parse({"kbId": kb2["kbId"], "docId": doc["docId"], "executeMode": "async"})
    assert body["errCode"] == "100001"
