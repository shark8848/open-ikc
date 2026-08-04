from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_base_store import KnowledgeBaseStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_knowledge_base_store() -> None:
    KnowledgeBaseStore.reset()
    yield
    KnowledgeBaseStore.reset()


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/health",
        "/api-browser",
        "/api/catalog",
        "/api/error-codes",
        "/docs",
        "/redoc",
        "/openapi.json",
    ],
)
def test_system_routes_are_exempt_from_business_auth(path: str) -> None:
    response = client.get(path, follow_redirects=False)
    assert response.status_code in {200, 307}
    if "json" in response.headers.get("content-type", ""):
        body = response.json()
        if isinstance(body, dict):
            assert body.get("errCode") != "100401"


def test_business_route_without_token_returns_unauthorized() -> None:
    response = client.post(
        "/api/v1/knowledge-bases/create",
        json={
            "kbName": "test",
            "kbType": "personal",
            "teamId": "",
            "orgId": "",
            "kbDesc": "",
            "bizDomain": "general",
            "visibility": "private",
            "metadataSchema": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["errCode"] == "100401"
    assert "traceId" in body


def test_business_route_with_valid_token_passes_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "test-platform-token")
    response = client.post(
        "/api/v1/knowledge-bases/create",
        headers={"Authorization": "Bearer test-platform-token"},
        json={
            "kbName": "test",
            "kbType": "personal",
            "teamId": "",
            "orgId": "",
            "kbDesc": "",
            "bizDomain": "general",
            "visibility": "private",
            "metadataSchema": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["errCode"] == "000000"
    assert body["data"]["kbName"] == "test"


def test_business_route_with_wrong_token_returns_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "test-platform-token")
    response = client.post(
        "/api/v1/knowledge-bases/create",
        headers={"Authorization": "Bearer wrong-token"},
        json={"kbName": "test", "kbType": "personal"},
    )
    assert response.status_code == 200
    assert response.json()["errCode"] == "100401"


def test_business_route_accepts_any_bearer_token_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPEN_PLATFORM_TOKEN", raising=False)
    monkeypatch.delenv("OPEN_PLATFORM_TOKENS", raising=False)
    response = client.post(
        "/api/v1/knowledge-bases/create",
        headers={"Authorization": "Bearer any-token"},
        json={"kbName": "test", "kbType": "personal"},
    )
    assert response.status_code == 200
    assert response.json()["errCode"] == "000000"
