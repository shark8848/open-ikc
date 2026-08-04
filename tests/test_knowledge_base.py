from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_base_store import KnowledgeBaseStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
KB_ID_PATTERN = re.compile(r"^kb_\d{17}$")


@pytest.fixture(autouse=True)
def reset_knowledge_base_store() -> None:
    KnowledgeBaseStore.reset()
    yield
    KnowledgeBaseStore.reset()


def _create_payload(**overrides) -> dict:
    payload = {
        "kbName": "产品知识库",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "用于客服问答",
        "bizDomain": "customer_service",
        "visibility": "private",
        "metadataSchema": [],
    }
    payload.update(overrides)
    return payload


def _create(headers: dict | None = None, **overrides) -> dict:
    response = client.post("/api/v1/knowledge-bases/create", json=_create_payload(**overrides), headers=headers or AUTH)
    return response.json()


def test_create_success() -> None:
    body = _create()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert KB_ID_PATTERN.match(data["kbId"])
    assert data["kbName"] == "产品知识库"
    assert data["kbType"] == "personal"
    assert data["kbDesc"] == "用于客服问答"
    assert data["bizDomain"] == "customer_service"
    assert data["visibility"] == "private"
    assert data["metadataSchema"] == []
    assert data["createTime"] is not None
    assert data["updateTime"] is None
    assert data["createTime"].endswith("Z")


def test_create_duplicate_name_in_same_scope_conflict() -> None:
    assert _create()["errCode"] == "000000"
    body = _create()
    assert body["errCode"] == "100409"
    assert body["errMsg"] == "资源冲突"
    assert "重复" in body["data"]["reason"]


def test_create_same_name_different_scope_allowed() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    assert _create(headers=alice)["errCode"] == "000000"
    assert _create(headers=bob)["errCode"] == "000000"


def test_create_team_without_team_id_invalid() -> None:
    body = _create(kbType="team", teamId="")
    assert body["errCode"] == "100001"
    assert "teamId" in str(body["data"].get("detail", ""))


def test_create_enterprise_without_org_or_tenant_forbidden() -> None:
    body = _create(kbType="enterprise", orgId="")
    assert body["errCode"] == "100403"


def test_create_enterprise_org_derived_from_tenant() -> None:
    headers = {**AUTH, "X-Tenant-Id": "tenant_001"}
    body = _create(headers=headers, kbType="enterprise", orgId="")
    assert body["errCode"] == "000000"
    assert body["data"]["orgId"] == "tenant_001"


def test_create_enterprise_duplicate_name_in_same_tenant_conflict() -> None:
    headers = {**AUTH, "X-Tenant-Id": "tenant_001"}
    assert _create(headers=headers, kbType="enterprise", orgId="org_001")["errCode"] == "000000"
    body = _create(headers=headers, kbType="enterprise", orgId="org_001")
    assert body["errCode"] == "100409"


def test_create_metadata_schema_duplicate_field_name_invalid() -> None:
    payload = _create_payload(
        metadataSchema=[
            {"name": "docType", "type": "string", "required": False, "description": ""},
            {"name": "docType", "type": "string", "required": False, "description": ""},
        ]
    )
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=AUTH)
    body = response.json()
    assert body["errCode"] == "100001"
    assert "重复" in body["data"]["reason"]


def test_update_success() -> None:
    created = _create()["data"]
    payload = {
        "kbId": created["kbId"],
        "kbName": "产品知识库-客服版",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "用于客服场景和销售支持",
        "visibility": "private",
        "metadataSchema": [],
    }
    response = client.post("/api/v1/knowledge-bases/update", json=payload, headers=AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbId"] == created["kbId"]
    assert data["kbName"] == "产品知识库-客服版"
    assert data["kbDesc"] == "用于客服场景和销售支持"
    assert data["createTime"] == created["createTime"]
    assert data["updateTime"] is not None


def test_update_keeps_fields_when_empty_values_passed() -> None:
    created = _create()["data"]
    payload = {
        "kbId": created["kbId"],
        "kbName": "",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "visibility": "private",
        "metadataSchema": [],
    }
    body = client.post("/api/v1/knowledge-bases/update", json=payload, headers=AUTH).json()
    assert body["errCode"] == "000000"
    assert body["data"]["kbName"] == created["kbName"]
    assert body["data"]["kbDesc"] == created["kbDesc"]


def test_update_not_found() -> None:
    payload = {
        "kbId": "kb_missing",
        "kbName": "不存在",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "visibility": "private",
        "metadataSchema": [],
    }
    body = client.post("/api/v1/knowledge-bases/update", json=payload, headers=AUTH).json()
    assert body["errCode"] == "100404"


def test_update_duplicate_name_conflict() -> None:
    first = _create(kbName="知识库A")["data"]
    _create(kbName="知识库B")
    payload = {
        "kbId": first["kbId"],
        "kbName": "知识库B",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "visibility": "private",
        "metadataSchema": [],
    }
    body = client.post("/api/v1/knowledge-bases/update", json=payload, headers=AUTH).json()
    assert body["errCode"] == "100409"


def test_update_personal_by_non_owner_forbidden() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    created = _create(headers=alice)["data"]
    payload = {
        "kbId": created["kbId"],
        "kbName": "改名",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "visibility": "private",
        "metadataSchema": [],
    }
    body = client.post("/api/v1/knowledge-bases/update", json=payload, headers=bob).json()
    assert body["errCode"] == "100403"
    assert "创建者" in body["data"]["reason"]


def test_authz_create_denied_for_reader(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    headers = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_reader"}
    body = _create(headers=headers)
    assert body["errCode"] == "100403"


def test_authz_create_allowed_for_admin(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    headers = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    body = _create(headers=headers)
    assert body["errCode"] == "000000"


def test_authz_update_denied_for_reader(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    reader = {**AUTH, "X-User-Id": "bob", "X-User-Roles": "km_reader"}
    created = _create(headers=admin)["data"]
    payload = {
        "kbId": created["kbId"],
        "kbName": "改名",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "visibility": "private",
        "metadataSchema": [],
    }
    body = client.post("/api/v1/knowledge-bases/update", json=payload, headers=reader).json()
    assert body["errCode"] == "100403"


def _query(payload: dict | None = None, headers: dict | None = None) -> dict:
    response = client.post("/api/v1/knowledge-bases/query", json=payload or {}, headers=headers or AUTH)
    return response.json()


def _detail(kb_id: str, headers: dict | None = None) -> dict:
    response = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=headers or AUTH)
    return response.json()


def test_query_empty_list() -> None:
    body = _query()
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_query_personal_scope_by_caller() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    _create(headers=alice, kbName="alice库A")
    _create(headers=alice, kbName="alice库B")
    _create(headers=bob, kbName="bob库")

    alice_body = _query(headers=alice)
    assert alice_body["data"]["total"] == 2
    assert {item["kbName"] for item in alice_body["data"]["items"]} == {"alice库A", "alice库B"}

    bob_body = _query(headers=bob)
    assert bob_body["data"]["total"] == 1
    assert bob_body["data"]["items"][0]["kbName"] == "bob库"


def test_query_team_requires_team_id() -> None:
    headers = {**AUTH, "X-User-Id": "alice"}
    _create(headers=headers, kbName="团队库", kbType="team", teamId="team_01")

    without_team = _query(headers=headers)
    assert without_team["data"]["total"] == 0

    with_team = _query(headers=headers, payload={"kbType": "team", "teamId": "team_01"})
    assert with_team["data"]["total"] == 1
    assert with_team["data"]["items"][0]["kbName"] == "团队库"


def test_query_enterprise_scope_by_tenant() -> None:
    tenant_headers = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"}
    _create(headers=tenant_headers, kbName="企业库", kbType="enterprise", orgId="")

    visible = _query(headers=tenant_headers, payload={"kbType": "enterprise"})
    assert visible["data"]["total"] == 1
    assert visible["data"]["items"][0]["orgId"] == "tenant_001"

    other_tenant = {**AUTH, "X-User-Id": "bob", "X-Tenant-Id": "tenant_002"}
    hidden = _query(headers=other_tenant, payload={"kbType": "enterprise"})
    assert hidden["data"]["total"] == 0


def test_query_keyword_filter() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    _create(headers=alice, kbName="产品知识库")
    _create(headers=alice, kbName="制度汇编")
    body = _query(headers=alice, payload={"keyword": "产品"})
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["kbName"] == "产品知识库"


def test_query_pagination() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    for index in range(3):
        _create(headers=alice, kbName=f"分页库{index}")

    page1 = _query(headers=alice, payload={"page": 1, "pageSize": 2})
    assert page1["data"]["total"] == 3
    assert len(page1["data"]["items"]) == 2
    assert page1["data"]["page"] == 1

    page2 = _query(headers=alice, payload={"page": 2, "pageSize": 2})
    assert len(page2["data"]["items"]) == 1


def test_detail_success() -> None:
    created = _create()["data"]
    body = _detail(created["kbId"])
    assert body["errCode"] == "000000"
    assert body["data"]["kbId"] == created["kbId"]
    assert body["data"]["kbName"] == created["kbName"]


def test_detail_other_personal_forbidden() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    created = _create(headers=alice)["data"]
    body = _detail(created["kbId"], headers=bob)
    assert body["errCode"] == "100403"
    assert "创建者" in body["data"]["reason"]


def test_detail_not_found() -> None:
    body = _detail("kb_missing")
    assert body["errCode"] == "100404"


def test_detail_enterprise_matching_tenant() -> None:
    tenant_headers = {**AUTH, "X-User-Id": "alice", "X-Tenant-Id": "tenant_001"}
    created = _create(headers=tenant_headers, kbName="企业库详情", kbType="enterprise", orgId="")["data"]
    body = _detail(created["kbId"], headers=tenant_headers)
    assert body["errCode"] == "000000"


def test_authz_query_denied_for_reader(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    headers = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_reader"}
    body = _query(headers=headers)
    assert body["errCode"] == "100403"


def test_authz_detail_allowed_for_admin(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_AUTHZ_ENABLED", "true")
    admin = {**AUTH, "X-User-Id": "alice", "X-User-Roles": "km_admin"}
    created = _create(headers=admin)["data"]
    body = _detail(created["kbId"], headers=admin)
    assert body["errCode"] == "000000"
