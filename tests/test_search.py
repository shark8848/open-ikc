from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_base_store import KnowledgeBaseStore
from app.services.search_store import SearchIndexStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def reset_search_stores() -> None:
    KnowledgeBaseStore.reset()
    SearchIndexStore.reset()
    yield
    KnowledgeBaseStore.reset()
    SearchIndexStore.reset()


def _create_kb(headers: dict | None = None, **overrides) -> dict:
    payload = {
        "kbName": "检索知识库",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "检索域集成测试库",
        "bizDomain": "customer_service",
        "visibility": "private",
        "metadataSchema": [],
    }
    payload.update(overrides)
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=headers or AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _search(payload: dict, headers: dict | None = None) -> dict:
    response = client.post("/api/v1/knowledge-search/query", json=payload, headers=headers or AUTH)
    return response.json()


def _index_doc(
    kb_id: str,
    *,
    doc_id: str = "doc_search_1",
    doc_title: str = "2026 产品白皮书",
    content: str = "平台提供统一知识接入、语义检索与可追溯问答能力。",
    keywords: list[str] | None = None,
    metadata: dict | None = None,
    owner_id: str = "",
) -> None:
    SearchIndexStore.index_doc(
        doc_id=doc_id,
        kb_id=kb_id,
        doc_title=doc_title,
        chunks=[{"content": content, "page": 3, "position": [82, 120]}],
        keywords=keywords or ["知识接入", "语义检索"],
        tags=["whitepaper"],
        metadata={"docType": "whitepaper"} if metadata is None else metadata,
        owner_id=owner_id,
    )


def test_search_qa_returns_answer_and_results() -> None:
    kb = _create_kb()
    _index_doc(kb["kbId"], keywords=["语义检索", "权限治理"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"]})
    assert body["errCode"] == "000000"
    assert body["data"]["total"] >= 1
    assert "语义检索" in body["data"]["answer"]
    assert body["data"]["results"][0]["docId"] == "doc_search_1"
    assert len(body["traceId"]) == 23


def test_search_mode_search_has_no_answer() -> None:
    kb = _create_kb()
    _index_doc(kb["kbId"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"], "mode": "search"})
    assert body["errCode"] == "000000"
    assert body["data"]["answer"] == ""
    assert body["data"]["results"][0]["docId"] == "doc_search_1"


def test_search_top_k_truncates_results() -> None:
    kb = _create_kb()
    for index in range(3):
        _index_doc(kb["kbId"], doc_id=f"doc_top_{index}", doc_title=f"白皮书 {index}", keywords=["语义检索"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"], "topK": 2})
    assert body["errCode"] == "000000"
    assert len(body["data"]["results"]) == 2


def test_search_filters_metadata() -> None:
    kb = _create_kb()
    _index_doc(kb["kbId"], doc_id="doc_wp", metadata={"docType": "whitepaper"})
    _index_doc(kb["kbId"], doc_id="doc_spec", doc_title="接口规范", keywords=["语义检索"], metadata={"docType": "spec"})
    body = _search({"query": "语义检索", "kbId": kb["kbId"], "filters": {"docType": "spec"}})
    assert body["errCode"] == "000000"
    assert [item["docId"] for item in body["data"]["results"]] == ["doc_spec"]


def test_search_with_citation_false_empties_citation() -> None:
    kb = _create_kb()
    _index_doc(kb["kbId"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"], "withCitation": False})
    assert body["errCode"] == "000000"
    assert body["data"]["results"][0]["citation"] == {}


def test_search_no_index_returns_empty_results() -> None:
    kb = _create_kb()
    body = _search({"query": "任意问题", "kbId": kb["kbId"]})
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 0
    assert body["data"]["results"] == []


def test_search_qa_no_hits_answer_placeholder() -> None:
    kb = _create_kb()
    body = _search({"query": "无匹配", "kbId": kb["kbId"]})
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 0
    assert "未检索到" in body["data"]["answer"]


def test_search_missing_kb_returns_not_found() -> None:
    body = _search({"query": "x", "kbId": "kb_not_exist"})
    assert body["errCode"] == "100404"


def test_search_other_personal_kb_forbidden() -> None:
    owner = {**AUTH, "X-User-Id": "alice"}
    other = {**AUTH, "X-User-Id": "bob"}
    kb = _create_kb(headers=owner)
    _index_doc(kb["kbId"], owner_id="alice")
    body = _search({"query": "语义检索", "kbId": kb["kbId"]}, headers=other)
    assert body["errCode"] == "100403"


def test_search_personal_kb_allowed_for_owner() -> None:
    owner = {**AUTH, "X-User-Id": "alice"}
    kb = _create_kb(headers=owner)
    _index_doc(kb["kbId"], owner_id="alice")
    body = _search({"query": "语义检索", "kbId": kb["kbId"]}, headers=owner)
    assert body["errCode"] == "000000"


def test_search_team_kb_requires_matching_team_id() -> None:
    admin = {**AUTH, "X-User-Id": "alice"}
    kb = _create_kb(headers=admin, kbType="team", teamId="team_001")
    _index_doc(kb["kbId"])
    assert _search({"query": "语义检索", "kbId": kb["kbId"]})["errCode"] == "100403"
    body = _search({"query": "语义检索", "kbId": kb["kbId"], "teamId": "team_001"})
    assert body["errCode"] == "000000"
    assert _search({"query": "语义检索", "kbId": kb["kbId"], "teamId": "team_other"})["errCode"] == "100403"


def test_search_enterprise_kb_requires_matching_org_scope() -> None:
    admin = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"}
    kb = _create_kb(headers=admin, kbType="enterprise", orgId="org_001")
    _index_doc(kb["kbId"])
    assert _search({"query": "语义检索", "kbId": kb["kbId"], "orgId": "org_001"})["errCode"] == "000000"
    assert _search({"query": "语义检索", "kbId": kb["kbId"], "orgId": "org_other"})["errCode"] == "100403"
    # 未传 orgId 时按调用主体租户收敛，租户与库 orgId 不一致 → 拒绝
    body = _search(
        {"query": "语义检索", "kbId": kb["kbId"]},
        headers={**AUTH, "X-User-Id": "bob", "X-Tenant-Id": "tenant_001"},
    )
    assert body["errCode"] == "100403"


def test_search_enterprise_kb_fallback_to_tenant_scope() -> None:
    admin = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"}
    kb = _create_kb(headers=admin, kbType="enterprise")  # 未显式 orgId → 落调用主体租户范围
    _index_doc(kb["kbId"])
    body = _search(
        {"query": "语义检索", "kbId": kb["kbId"]},
        headers={**AUTH, "X-User-Id": "bob", "X-Tenant-Id": "tenant_001"},
    )
    assert body["errCode"] == "000000"
    denied = _search(
        {"query": "语义检索", "kbId": kb["kbId"]},
        headers={**AUTH, "X-User-Id": "bob", "X-Tenant-Id": "tenant_002"},
    )
    assert denied["errCode"] == "100403"


def test_search_multi_kb_any_forbidden_rejects_all() -> None:
    owner = {**AUTH, "X-User-Id": "alice"}
    other = {**AUTH, "X-User-Id": "bob"}
    kb_owner = _create_kb(headers=owner)
    kb_other = _create_kb(headers=other)
    _index_doc(kb_owner["kbId"], owner_id="alice")
    _index_doc(kb_other["kbId"], owner_id="bob")
    body = _search({"query": "语义检索", "kbIds": [kb_owner["kbId"], kb_other["kbId"]]}, headers=other)
    assert body["errCode"] == "100403"


def test_search_missing_kb_scope_invalid_params() -> None:
    body = _search({"query": "x"})
    assert body["errCode"] == "100001"


def test_search_invalid_mode_rejected() -> None:
    kb = _create_kb()
    body = _search({"query": "x", "kbId": kb["kbId"], "mode": "hybrid"})
    assert body["errCode"] == "100001"


def test_search_invalid_top_k_rejected() -> None:
    kb = _create_kb()
    body = _search({"query": "x", "kbId": kb["kbId"], "topK": 0})
    assert body["errCode"] == "100001"


def test_search_top_k_over_limit_rejected() -> None:
    kb = _create_kb()
    body = _search({"query": "x", "kbId": kb["kbId"], "topK": 101})
    assert body["errCode"] == "100001"


def test_search_unauthenticated_returns_401() -> None:
    response = client.post("/api/v1/knowledge-search/query", json={"query": "x", "kbId": "kb_1"})
    assert response.json()["errCode"] == "100401"


def test_search_authz_denied_by_deny_permission(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    denied = {**AUTH, "X-User-Id": "bob", "X-User-Roles": "km_reader", "X-User-Deny-Permissions": "search:query"}
    kb = _create_kb(headers=admin)
    body = _search({"query": "x", "kbId": kb["kbId"]}, headers=denied)
    assert body["errCode"] == "100403"


def test_search_authz_allowed_for_admin(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    kb = _create_kb(headers=admin)
    _index_doc(kb["kbId"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"]}, headers=admin)
    assert body["errCode"] == "000000"


def test_search_authz_allowed_for_reader(monkeypatch) -> None:
    # km_reader 具备 search:query 权限，检索为只读能力；企业库范围对同组织主体开放
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001", "X-User-Roles": "km_admin"}
    reader = {**AUTH, "X-User-Id": "bob", "X-Tenant-Id": "tenant_001", "X-User-Roles": "km_reader"}
    # 企业库未显式 orgId → 落调用主体租户范围，同租户 reader 可检索
    kb = _create_kb(headers=admin, kbType="enterprise", visibility="org")
    _index_doc(kb["kbId"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"]}, headers=reader)
    assert body["errCode"] == "000000"


def test_search_authz_multi_kb_loop_rejects_denied(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    denied = {**AUTH, "X-User-Id": "bob", "X-User-Roles": "km_reader", "X-User-Deny-Permissions": "search:query"}
    kb_one = _create_kb(headers=admin, kbName="多库检索一")
    kb_two = _create_kb(headers=admin, kbName="多库检索二")
    body = _search({"query": "x", "kbIds": [kb_one["kbId"], kb_two["kbId"]]}, headers=denied)
    assert body["errCode"] == "100403"


def test_search_response_fields_match_schema() -> None:
    from app.schemas.search import SearchQueryData, SearchResultItemData

    kb = _create_kb()
    _index_doc(kb["kbId"])
    body = _search({"query": "语义检索", "kbId": kb["kbId"]})
    assert body["errCode"] == "000000"
    assert set(body["data"].keys()) == set(SearchQueryData.model_fields.keys())
    assert set(body["data"]["results"][0].keys()) == set(SearchResultItemData.model_fields.keys())


def test_search_catalog_consistent() -> None:
    from app.core.catalog import API_CATALOG

    paths = {
        route["path"]
        for category in API_CATALOG
        for route in category["routes"]
        if category.get("tag") == "search"
    }
    assert "/api/v1/knowledge-search/query" in paths
