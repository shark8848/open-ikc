from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import search_client
from app.services.knowledge_base_store import KnowledgeBaseStore
from app.services.search_store import SearchIndexStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}


class FakeResponse:
    def __init__(self, status_code: int = 200, json_body: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_body or {}

    def json(self) -> dict:
        return self._json


@pytest.fixture(autouse=True)
def reset_search_stores() -> None:
    KnowledgeBaseStore.reset()
    SearchIndexStore.reset()
    yield
    KnowledgeBaseStore.reset()
    SearchIndexStore.reset()


@pytest.fixture
def fake_post(monkeypatch):
    calls: list[tuple[str, dict, dict]] = []
    state: dict[str, FakeResponse] = {"response": FakeResponse()}

    def _fake(url: str, headers: dict, payload: dict, timeout: float) -> FakeResponse:
        calls.append((url, headers, payload))
        return state["response"]

    monkeypatch.setattr(search_client, "_post_json", _fake)
    return state, calls


def _create_kb(headers: dict | None = None, **overrides) -> dict:
    payload = {
        "kbName": "下游检索知识库",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "下游适配测试库",
        "bizDomain": "customer_service",
        "visibility": "private",
        "metadataSchema": [],
    }
    payload.update(overrides)
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=headers or AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _ur_body() -> dict:
    return {
        "errCode": "000000",
        "errMsg": "ok",
        "status": True,
        "docs": [
            {
                "id": "doc_ur_1",
                "title": "UR 白皮书",
                "content": "平台提供统一知识接入、语义检索与可追溯问答能力。",
                "snippet": "平台提供统一知识接入",
                "scores": {"final_score": 0.91},
                "metadata": {"page": 3, "position": [82, 120]},
            }
        ],
        "used_config": {"index": "kb_chunks_write", "retrieval_mode": "hybrid"},
    }


def test_ur_backend_maps_request_and_response(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "ur")
    monkeypatch.setenv("OPEN_PLATFORM_UR_BASE_URL", "http://ur.test:8096")
    kb = _create_kb()
    monkeypatch.setenv("OPEN_PLATFORM_KB_INDEX_MAP", json.dumps({kb["kbId"]: "kb_chunks_write"}))
    fake_post[0]["response"] = FakeResponse(json_body=_ur_body())

    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={
            "query": "语义检索",
            "kbId": kb["kbId"],
            "searchType": "hybrid",
            "topK": 5,
            "useRerank": True,
            "score": 0.5,
            "relNum": 3,
            "filters": {"docType": "whitepaper"},
        },
        headers=AUTH,
    ).json()

    assert body["errCode"] == "000000"
    url, headers, payload = fake_post[1][0]
    assert url == "http://ur.test:8096/retrieval/search/sync"
    assert headers["X-Trace-Id"] == body["traceId"]
    assert payload["retrieval_mode"] == "hybrid"
    assert payload["top_k"] == 5
    assert payload["related_top_k"] == 3
    assert payload["score_threshold"] == 0.5
    assert payload["rerank_model_params"] == {"provider": "rule", "top_k": 5}
    assert payload["index"] == "kb_chunks_write"
    assert payload["filters"] == [{"docType": "whitepaper"}]
    assert payload["hybrid"] == {"strategy": "linear", "text_weight": 0.5, "vector_weight": 0.5}
    assert payload["request_id"] == body["traceId"]
    assert body["data"]["results"][0]["docId"] == "doc_ur_1"
    assert body["data"]["results"][0]["score"] == 0.91
    assert body["data"]["results"][0]["citation"] == {"page": 3, "position": [82, 120]}
    assert body["data"]["searchType"] == "hybrid"
    assert body["data"]["usedConfig"]["index"] == "kb_chunks_write"


def test_ur_backend_qa_mode_returns_note_without_answer(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "ur")
    kb = _create_kb()
    fake_post[0]["response"] = FakeResponse(json_body=_ur_body())

    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "语义检索", "kbId": kb["kbId"], "mode": "qa"},
        headers=AUTH,
    ).json()

    assert body["errCode"] == "000000"
    assert body["data"]["answer"] == ""
    assert "deep-search" in body["data"]["qaNote"]


def test_openai_backend_maps_vector_search_request(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "openai")
    monkeypatch.setenv("OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL", "http://oa.test:8088/km/search-api/aiTools/openai/bsapi")
    kb = _create_kb()
    fake_post[0]["response"] = FakeResponse(json_body={
        "errCode": "000000",
        "errMsg": "ok",
        "status": True,
        "data": [
            {
                "primary_id": "doc_oa_1",
                "title": "OA 白皮书",
                "content": "平台提供统一知识接入、语义检索与可追溯问答能力。",
                "scores": {"final_score": 0.88},
            }
        ],
    })

    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "语义检索", "kbId": kb["kbId"], "searchType": "vector", "isOptimize": True},
        headers={**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"},
    ).json()

    assert body["errCode"] == "000000"
    url, _headers, payload = fake_post[1][0]
    assert url.endswith("/VectorSearchV2")
    assert payload["searchType"] == 1
    assert payload["ct_id"] == kb["kbId"]
    assert payload["user_id"] == "alice"
    assert payload["org_id"] == "tenant_001"
    assert payload["is_optimize"] == 1
    assert body["data"]["results"][0]["docId"] == "doc_oa_1"
    assert body["data"]["results"][0]["score"] == 0.88


def test_deep_search_maps_request_and_response(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "openai")
    kb = _create_kb()
    fake_post[0]["response"] = FakeResponse(json_body={
        "errCode": "000000",
        "errMsg": "ok",
        "status": True,
        "result": {"answer": "结论：[1]", "used_queries": ["白皮书 检索能力", "2025 检索能力"]},
        "citations": [
            {"id": "doc_deep_1", "title": "白皮书 2026", "snippet": "检索能力对比", "scores": {"final_score": 0.95}},
        ],
        "data": [
            {"primary_id": "doc_deep_1", "title": "白皮书 2026", "content": "检索能力对比内容", "scores": {"final_score": 0.95}},
        ],
        "extra": {"agent_steps": [{"stage": "retrieve", "query": "白皮书 检索能力", "docs_count": 2, "elapsed_ms": 15}]},
    })

    body = client.post(
        "/api/v1/knowledge-search/deep-search",
        json={
            "query": "对比 2025 与 2026 白皮书检索能力差异",
            "kbId": kb["kbId"],
            "searchType": "hybrid",
            "topK": 8,
            "sessionId": "sess_001",
            "memory": {"mode": "caller", "items": [{"type": "preference", "content": "关注检索能力"}]},
            "deepSearch": {"maxSteps": 5, "subQuery": {"enabled": True, "maxSubQueries": 3}, "recallTopnPolicy": "adaptive"},
            "responseSpec": {"include": ["answer", "citations", "usedQueries", "steps"]},
        },
        headers=AUTH,
    ).json()

    assert body["errCode"] == "000000"
    url, _headers, payload = fake_post[1][0]
    assert url.endswith("/DeepSearch")
    assert payload["deepSearch"]["enabled"] is True
    assert payload["deepSearch"]["maxSteps"] == 5
    assert payload["deepSearch"]["subQuery"] == {"enabled": True, "maxSubQueries": 3, "mergeStrategy": "rrf"}
    assert payload["session_id"] == "sess_001"
    assert payload["memory"]["mode"] == "caller"
    assert payload["searchType"] == 2
    data = body["data"]
    assert data["answer"] == "结论：[1]"
    assert data["usedQueries"] == ["白皮书 检索能力", "2025 检索能力"]
    assert data["citations"][0]["docId"] == "doc_deep_1"
    assert data["citations"][0]["score"] == 0.95
    assert data["results"][0]["docId"] == "doc_deep_1"
    assert data["steps"][0]["stage"] == "retrieve"


def test_deep_search_in_process_backend_returns_501(fake_post, monkeypatch) -> None:
    kb = _create_kb()
    body = client.post(
        "/api/v1/knowledge-search/deep-search",
        json={"query": "深度问题", "kbId": kb["kbId"]},
        headers=AUTH,
    ).json()
    assert body["errCode"] == "501001"
    assert fake_post[1] == []


def test_deep_search_ur_backend_returns_501(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "ur")
    kb = _create_kb()
    body = client.post(
        "/api/v1/knowledge-search/deep-search",
        json={"query": "深度问题", "kbId": kb["kbId"]},
        headers=AUTH,
    ).json()
    assert body["errCode"] == "501001"
    assert fake_post[1] == []


def test_deep_search_downstream_disabled_returns_501(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "openai")
    kb = _create_kb()
    fake_post[0]["response"] = FakeResponse(status_code=403, json_body={"errMsg": "DeepSearch is disabled"})

    body = client.post(
        "/api/v1/knowledge-search/deep-search",
        json={"query": "深度问题", "kbId": kb["kbId"]},
        headers=AUTH,
    ).json()

    assert body["errCode"] == "501001"


def test_downstream_http_error_maps_to_300001(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "ur")

    def _boom(*_args, **_kwargs) -> FakeResponse:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(search_client, "_post_json", _boom)
    kb = _create_kb()

    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "语义检索", "kbId": kb["kbId"]},
        headers=AUTH,
    ).json()

    assert body["errCode"] == "300001"


def test_downstream_business_failure_maps_to_300001(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "ur")
    kb = _create_kb()
    fake_post[0]["response"] = FakeResponse(json_body={"errCode": "999999", "errMsg": "es cluster down", "status": False})

    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "语义检索", "kbId": kb["kbId"]},
        headers=AUTH,
    ).json()

    assert body["errCode"] == "300001"


def test_downstream_permission_still_enforced_before_call(fake_post, monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_SEARCH_BACKEND", "ur")
    owner = {**AUTH, "X-User-Id": "alice"}
    other = {**AUTH, "X-User-Id": "bob"}
    kb = _create_kb(headers=owner)

    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "语义检索", "kbId": kb["kbId"]},
        headers=other,
    ).json()

    assert body["errCode"] == "100403"
    assert fake_post[1] == []


def test_error_codes_catalog_contains_300001() -> None:
    body = client.get("/api/error-codes").json()
    assert any(item["code"] == "300001" for item in body["data"])


def test_search_type_validation_rejects_unknown_value() -> None:
    kb = _create_kb()
    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "x", "kbId": kb["kbId"], "searchType": "semantic"},
        headers=AUTH,
    ).json()
    assert body["errCode"] == "100001"


def test_rel_num_validation_rejects_out_of_range() -> None:
    kb = _create_kb()
    body = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "x", "kbId": kb["kbId"], "relNum": 999},
        headers=AUTH,
    ).json()
    assert body["errCode"] == "100001"
