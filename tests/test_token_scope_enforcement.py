from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.admin import token_store
from app.core.authz.runtime import _scope_allows
from app.main import app
from app.services.knowledge_base_store import KnowledgeBaseStore, make_record
from app.services.search_store import SearchIndexStore

client = TestClient(app)

KB_CREATE_PAYLOAD = {
    "kbName": "作用域测试库",
    "kbType": "personal",
    "teamId": "",
    "orgId": "",
    "kbDesc": "token 作用域强制校验测试库",
    "bizDomain": "customer_service",
    "visibility": "private",
    "metadataSchema": [],
}


@pytest.fixture(autouse=True)
def reset_stores() -> None:
    KnowledgeBaseStore.reset()
    SearchIndexStore.reset()
    # 模拟生产常态：DB 存在已撤销记录，避免「从未配置 token 时放行」分支掩盖 scope 行为
    seed, _ = token_store.create_token(name="revoked-seed", scopes=["*:*"])
    token_store.revoke_token(seed.id)
    yield
    KnowledgeBaseStore.reset()
    SearchIndexStore.reset()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db_token(scopes: list[str] | None = None, name: str = "scope-test") -> str:
    _, plain = token_store.create_token(name=name, scopes=scopes)
    return plain


def _inject_kb() -> str:
    record = KnowledgeBaseStore.create(
        make_record(
            kb_name="作用域测试库",
            kb_type="personal",
            team_id="",
            org_id="",
            kb_desc="scope",
            biz_domain="customer_service",
            visibility="private",
            metadata_schema=[],
            owner_id="",
            tenant_id="",
            scope_key="personal",
            create_time="2026-08-14 00:00:00",
        )
    )
    return record.kb_id


def _search(headers: dict[str, str]) -> dict:
    kb_id = _inject_kb()
    resp = client.post(
        "/api/v1/knowledge-search/universal-search",
        json={"query": "语义检索", "kbId": kb_id},
        headers=headers,
    )
    return resp.json()


def _create_kb(headers: dict[str, str]) -> dict:
    resp = client.post("/api/v1/knowledge-bases/create", json=KB_CREATE_PAYLOAD, headers=headers)
    return resp.json()


def test_scope_allows_matrix() -> None:
    assert _scope_allows(["search:query"], "search", "query") is True
    assert _scope_allows(["search:query"], "search", "read") is False
    assert _scope_allows(["search:query"], "document", "query") is False
    assert _scope_allows(["knowledge_base:*"], "knowledge_base", "create") is True
    assert _scope_allows(["knowledge_base:*"], "search", "query") is False
    assert _scope_allows(["*:*"], "knowledge_base", "create") is True
    assert _scope_allows(["*:read"], "document", "read") is True
    assert _scope_allows(["*:read"], "document", "write") is False
    assert _scope_allows([], "search", "query") is False


def test_search_scope_allows_search_but_blocks_kb_create() -> None:
    token = _db_token(scopes=["search:query"])

    body = _search(_bearer(token))
    assert body["errCode"] == "000000"

    body = _create_kb(_bearer(token))
    assert body["errCode"] == "100403"


def test_kb_read_scope_blocks_kb_create_and_search() -> None:
    token = _db_token(scopes=["knowledge_base:read"])

    body = _create_kb(_bearer(token))
    assert body["errCode"] == "100403"

    body = _search(_bearer(token))
    assert body["errCode"] == "100403"


def test_kb_create_scope_allows_create() -> None:
    token = _db_token(scopes=["knowledge_base:create"])

    body = _create_kb(_bearer(token))
    assert body["errCode"] == "000000"


def test_wildcard_scope_allows_all() -> None:
    token = _db_token(scopes=["*:*"])

    body = _create_kb(_bearer(token))
    assert body["errCode"] == "000000"

    body = _search(_bearer(token))
    assert body["errCode"] == "000000"


def test_empty_scopes_token_unrestricted() -> None:
    token = _db_token(scopes=[])

    body = _create_kb(_bearer(token))
    assert body["errCode"] == "000000"


def test_env_token_unrestricted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "env-token")

    body = _create_kb(_bearer("env-token"))
    assert body["errCode"] == "000000"


def test_admin_create_token_rejects_bad_scopes_and_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_ADMIN_TOKEN", "test-admin-token")
    headers = _bearer("test-admin-token")

    # scopes 传字符串：拒绝，避免逐字符拆包成脏数据
    resp = client.post(
        "/admin/tokens",
        json={"name": "bad-scopes", "scopes": "kb:read"},
        headers=headers,
    )
    assert resp.json()["errCode"] == "100001"

    # expiresInSeconds 传非法值：拒绝
    resp = client.post(
        "/admin/tokens",
        json={"name": "bad-expiry", "expiresInSeconds": "abc"},
        headers=headers,
    )
    assert resp.json()["errCode"] == "100001"

    resp = client.post(
        "/admin/tokens",
        json={"name": "bad-expiry-zero", "expiresInSeconds": 0},
        headers=headers,
    )
    assert resp.json()["errCode"] == "100001"

    # scope 格式非法（非 resource:action、带大写/空格）：拒绝
    resp = client.post(
        "/admin/tokens",
        json={"name": "bad-scope-format", "scopes": ["KB:read", "search query"]},
        headers=headers,
    )
    assert resp.json()["errCode"] == "100001"

    # 合法数组作用域：正常创建并原样入库
    resp = client.post(
        "/admin/tokens",
        json={"name": "good", "scopes": ["search:query", "knowledge_base:read"], "expiresInSeconds": 3600},
        headers=headers,
    )
    body = resp.json()
    assert body["errCode"] == "000000"
    assert body["data"]["scopes"] == ["search:query", "knowledge_base:read"]
