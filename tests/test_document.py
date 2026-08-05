from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_store import DocumentStore
from app.services.knowledge_base_store import KnowledgeBaseStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
INGEST_TASK_ID_PATTERN = re.compile(r"^ing_\d{17}$")
PARSE_TASK_ID_PATTERN = re.compile(r"^parse_\d{17}$")
DOC_ID_PATTERN = re.compile(r"^doc_\d{17}$")


@pytest.fixture(autouse=True)
def reset_document_and_knowledge_base_stores() -> None:
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    yield
    DocumentStore.reset()
    KnowledgeBaseStore.reset()


def _create_kb(headers: dict | None = None, **overrides) -> dict:
    """创建知识库并返回响应 data（含 kbId）。"""
    payload = {
        "kbName": "文档知识库",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "文档域集成测试库",
        "bizDomain": "customer_service",
        "visibility": "private",
        "metadataSchema": [],
    }
    payload.update(overrides)
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=headers or AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _ingest_payload(kb_id: str, **overrides) -> dict:
    payload: dict = {
        "kbId": kb_id,
        "source": {"type": "url", "url": "https://example.com/spec.pdf"},
    }
    source = overrides.pop("source", None)
    if source is not None:
        payload["source"] = source
    payload.update(overrides)
    return payload


def _ingest(payload: dict, headers: dict | None = None) -> dict:
    response = client.post("/api/v1/knowledge-documents/ingest", json=payload, headers=headers or AUTH)
    return response.json()


def _ingest_and_parse(payload: dict, headers: dict | None = None) -> dict:
    response = client.post(
        "/api/v1/knowledge-documents/ingest-and-parse",
        json=payload,
        headers=headers or AUTH,
    )
    return response.json()


def _get_document(doc_id: str, headers: dict | None = None) -> dict:
    response = client.get(f"/api/v1/knowledge-documents/{doc_id}", headers=headers or AUTH)
    return response.json()


def _query(doc_id: str, headers: dict | None = None) -> dict:
    response = client.get(
        "/api/v1/knowledge-documents/parse-result/query",
        params={"docId": doc_id},
        headers=headers or AUTH,
    )
    return response.json()


def test_ingest_url_success() -> None:
    kb = _create_kb()
    body = _ingest(_ingest_payload(kb["kbId"]))
    assert body["errCode"] == "000000"
    data = body["data"]
    assert INGEST_TASK_ID_PATTERN.match(data["ingestTaskId"])
    assert DOC_ID_PATTERN.match(data["docId"])
    assert data["taskStatus"] == "INGESTED"
    assert data["sourceType"] == "url"
    assert data["sourceStats"]["total"] == 1
    assert data["ingestTime"].endswith("Z")


def test_ingest_file_source_success() -> None:
    kb = _create_kb()
    payload = _ingest_payload(
        kb["kbId"],
        source={"type": "file", "objectKey": "oss://bucket/spec.pdf", "fileToken": ""},
    )
    body = _ingest(payload)
    assert body["errCode"] == "000000"
    data = body["data"]
    assert INGEST_TASK_ID_PATTERN.match(data["ingestTaskId"])
    assert DOC_ID_PATTERN.match(data["docId"])
    assert data["taskStatus"] == "INGESTED"
    assert data["sourceType"] == "file"


def test_ingest_same_source_idempotent() -> None:
    kb = _create_kb()
    payload = _ingest_payload(kb["kbId"])
    first = _ingest(payload)
    second = _ingest(payload)
    assert first["errCode"] == "000000"
    assert second["errCode"] == "000000"
    assert second["data"]["ingestTaskId"] == first["data"]["ingestTaskId"]
    assert second["data"]["docId"] == first["data"]["docId"]


def test_ingest_knowledge_base_not_found() -> None:
    body = _ingest(_ingest_payload("kb_missing"))
    assert body["errCode"] == "100404"


def test_ingest_personal_by_non_owner_forbidden() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    kb = _create_kb(headers=alice)
    body = _ingest(_ingest_payload(kb["kbId"]), headers=bob)
    assert body["errCode"] == "100403"


def test_ingest_team_with_mismatched_team_id_forbidden() -> None:
    headers = {**AUTH, "X-User-Id": "alice"}
    kb = _create_kb(headers=headers, kbType="team", teamId="team_01")
    body = _ingest(_ingest_payload(kb["kbId"], teamId="team_02"), headers=headers)
    assert body["errCode"] == "100403"


def test_ingest_team_matching_team_id_success() -> None:
    headers = {**AUTH, "X-User-Id": "alice"}
    kb = _create_kb(headers=headers, kbType="team", teamId="team_01")
    body = _ingest(_ingest_payload(kb["kbId"], teamId="team_01"), headers=headers)
    assert body["errCode"] == "000000"


def test_ingest_enterprise_mismatched_tenant_forbidden() -> None:
    owner_headers = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"}
    other_headers = {**AUTH, "X-User-Id": "bob", "X-Tenant-Id": "tenant_002"}
    kb = _create_kb(headers=owner_headers, kbType="enterprise", orgId="")
    body = _ingest(_ingest_payload(kb["kbId"], orgId=""), headers=other_headers)
    assert body["errCode"] == "100403"


def test_ingest_enterprise_matching_tenant_success() -> None:
    tenant_headers = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"}
    kb = _create_kb(headers=tenant_headers, kbType="enterprise", orgId="")
    body = _ingest(_ingest_payload(kb["kbId"], orgId=""), headers=tenant_headers)
    assert body["errCode"] == "000000"


def test_ingest_url_type_without_url_invalid() -> None:
    kb = _create_kb()
    payload = _ingest_payload(kb["kbId"], source={"type": "url", "url": ""})
    body = _ingest(payload)
    assert body["errCode"] == "100001"


def test_ingest_file_without_object_key_or_token_invalid() -> None:
    kb = _create_kb()
    payload = _ingest_payload(kb["kbId"], source={"type": "file", "objectKey": "", "fileToken": ""})
    body = _ingest(payload)
    assert body["errCode"] == "100001"


def test_ingest_and_parse_async_success() -> None:
    kb = _create_kb()
    payload = _ingest_payload(
        kb["kbId"],
        parseStrategy={"docType": "pdf", "parseMethod": "auto"},
        resultFormat={"type": "json", "includeLayout": True},
        executeMode="async",
    )
    body = _ingest_and_parse(payload)
    assert body["errCode"] == "000000"
    data = body["data"]
    assert INGEST_TASK_ID_PATTERN.match(data["ingestTaskId"])
    assert PARSE_TASK_ID_PATTERN.match(data["parseTaskId"])
    assert DOC_ID_PATTERN.match(data["docId"])
    assert data["taskStatus"] == "queued"
    assert data["executeMode"] == "async"


def test_get_document_success() -> None:
    kb = _create_kb()
    ingested = _ingest(_ingest_payload(kb["kbId"], docTitle="接入测试文档"))["data"]
    body = _get_document(ingested["docId"])
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["docId"] == ingested["docId"]
    assert data["docTitle"] == "接入测试文档"
    assert data["kbId"] == kb["kbId"]
    assert data["status"] == ingested["taskStatus"]


def test_get_document_not_found() -> None:
    body = _get_document("doc_missing")
    assert body["errCode"] == "100404"


def test_authz_ingest_denied_for_reader(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    reader = {**AUTH, "X-User-Id": "bob", "X-User-Roles": "km_reader"}
    kb = _create_kb(headers=admin)
    body = _ingest(_ingest_payload(kb["kbId"]), headers=reader)
    assert body["errCode"] == "100403"


def test_authz_ingest_allowed_for_admin(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    kb = _create_kb(headers=admin)
    body = _ingest(_ingest_payload(kb["kbId"]), headers=admin)
    assert body["errCode"] == "000000"

def test_ingest_quick_mode_returns_parsing() -> None:
    kb = _create_kb()
    body = _ingest(_ingest_payload(kb["kbId"], orchestrationMode="quick"))
    assert body["errCode"] == "000000"
    assert body["data"]["taskStatus"] == "PARSING"


def test_ingest_and_parse_sync_returns_inline_result() -> None:
    kb = _create_kb()
    payload = _ingest_payload(
        kb["kbId"],
        parseStrategy={"docType": "pdf", "parseMethod": "auto"},
        resultFormat={"type": "json", "includeLayout": True},
        executeMode="sync",
    )
    body = _ingest_and_parse(payload)
    assert body["errCode"] == "000000"
    data = body["data"]
    assert PARSE_TASK_ID_PATTERN.match(data["parseTaskId"])
    assert data["taskStatus"] == "success"
    assert data["resultInline"]["summary"]


def test_ingest_and_parse_async_task_queryable() -> None:
    kb = _create_kb()
    payload = _ingest_payload(kb["kbId"], executeMode="async")
    data = _ingest_and_parse(payload)["data"]
    body = _query(data["docId"])
    assert body["errCode"] == "000000"
    assert body["data"]["parseStatus"] == data["taskStatus"]
