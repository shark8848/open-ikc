from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}


def test_search_query_placeholder_returns_501001() -> None:
    response = client.post(
        "/api/v1/knowledge-search/query",
        json={"query": "任意问题", "kbId": "kb_1", "kbIds": ["kb_1"]},
        headers=AUTH,
    )
    body = response.json()
    assert body["errCode"] == "501001"
    assert len(body["traceId"]) == 23


def test_search_query_unauthenticated_returns_401() -> None:
    response = client.post("/api/v1/knowledge-search/query", json={"query": "x"})
    assert response.json()["errCode"] == "100401"
