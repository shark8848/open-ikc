from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module

app = main_module.app


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_DB_PATH", str(tmp_path / "test_admin_api.db"))
    monkeypatch.setenv("OPEN_PLATFORM_ADMIN_TOKEN", "test-admin-token")
    # 清空 token 表，避免跨测试污染
    from app.core.admin.token_store import _connect

    conn = _connect()
    try:
        conn.execute("DROP TABLE IF EXISTS api_tokens")
        conn.commit()
    finally:
        conn.close()


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-admin-token"}


def test_admin_requires_token() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/overview")
    assert resp.status_code == 200
    assert resp.json()["errCode"] == "100401"


def test_admin_rejects_wrong_token() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/overview", headers={"Authorization": "Bearer wrong"})
    assert resp.json()["errCode"] == "100401"


def test_admin_disabled_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPEN_PLATFORM_ADMIN_TOKEN", raising=False)
    with TestClient(app) as client:
        resp = client.get("/admin/overview", headers=_admin_headers())
    assert resp.status_code == 503
    assert resp.json()["errCode"] == "503001"


def test_overview() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/overview", headers=_admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert "concurrency" in data
    assert "totalRequests" in data
    assert "activeTokens" in data


def test_endpoints_and_requests() -> None:
    with TestClient(app) as client:
        ep = client.get("/admin/endpoints", headers=_admin_headers())
        req = client.get("/admin/requests", headers=_admin_headers())
    assert ep.json()["errCode"] == "000000"
    assert isinstance(ep.json()["data"], list)
    assert req.json()["errCode"] == "000000"
    assert isinstance(req.json()["data"], list)


def test_create_and_revoke_token_flow() -> None:
    with TestClient(app) as client:
        # 创建
        resp = client.post(
            "/admin/tokens",
            json={"name": "ops-token", "owner": "ops", "scopes": ["read"], "expiresInSeconds": 3600},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["errCode"] == "000000"
        data = body["data"]
        assert data["token"]  # 明文返回一次
        assert data["name"] == "ops-token"
        token_id = data["id"]

        # 列表包含
        listed = client.get("/admin/tokens", headers=_admin_headers()).json()["data"]
        assert any(t["id"] == token_id for t in listed)

        # 用新 token 调业务接口
        kb = client.post(
            "/api/v1/knowledge-bases/query",
            json={"page": 1, "pageSize": 10},
            headers={"Authorization": f"Bearer {data['token']}"},
        )
        assert kb.json()["errCode"] == "000000"

        # 撤销
        revoke = client.post(f"/admin/tokens/{token_id}/revoke", headers=_admin_headers())
        assert revoke.json()["errCode"] == "000000"

        # 撤销后 token 失效
        kb2 = client.post(
            "/api/v1/knowledge-bases/query",
            json={"page": 1, "pageSize": 10},
            headers={"Authorization": f"Bearer {data['token']}"},
        )
        assert kb2.json()["errCode"] == "100401"


def test_create_token_requires_name() -> None:
    with TestClient(app) as client:
        resp = client.post("/admin/tokens", json={}, headers=_admin_headers())
    assert resp.json()["errCode"] == "100001"


def test_token_stats_route() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/stats/token", headers=_admin_headers())
    assert resp.status_code == 200
    assert resp.json()["errCode"] == "000000"
    assert isinstance(resp.json()["data"], list)


def test_whitelist_route() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/test/whitelist", headers=_admin_headers())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "kb-list" in data["cli"]
    assert "sys_catalog" in data["mcpTools"]
