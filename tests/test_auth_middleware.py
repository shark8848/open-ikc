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
        "/api-manual",
        "/api/catalog",
        "/api/error-codes",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/portal/",
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


def test_api_docs_are_accessible_without_auth() -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()

    redoc = client.get("/redoc")
    assert redoc.status_code == 200
    assert "redoc" in redoc.text.lower()

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "openapi" in openapi.json()

    oauth_redirect = client.get("/docs/oauth2-redirect")
    assert oauth_redirect.status_code == 200


def test_api_docs_use_local_static_assets_no_external_cdn() -> None:
    """/docs 与 /redoc 页面资源全部本地托管，不得引用任何外部域名，离线环境可用。"""
    docs = client.get("/docs")
    redoc = client.get("/redoc")
    assert docs.status_code == 200 and redoc.status_code == 200

    combined = (docs.text + redoc.text).lower()
    # 页面引用的静态资源必须指向本地 /_static/docs 前缀
    assert "/_static/docs/swagger-ui/swagger-ui-bundle.js" in combined
    assert "/_static/docs/redoc/redoc.standalone.js" in combined
    # 不得出现外部 CDN / 字体服务引用
    for external in ("cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com", "unpkg.com"):
        assert external not in combined

    # 本地静态资源本身可访问且为免鉴权路径（不返回 100401 统一体，而是真实文件内容）
    js = client.get("/_static/docs/swagger-ui/swagger-ui-bundle.js")
    assert js.status_code == 200
    assert "javascript" in js.headers.get("content-type", "")
    assert b"SwaggerUIBundle" in js.content

    redoc_js = client.get("/_static/docs/redoc/redoc.standalone.js")
    assert redoc_js.status_code == 200
    assert "javascript" in redoc_js.headers.get("content-type", "")
    assert b"Redoc" in redoc_js.content

    css = client.get("/_static/docs/swagger-ui/swagger-ui.css")
    assert css.status_code == 200
    assert css.headers.get("content-type", "").startswith("text/css")


def test_exempt_system_routes_tolerate_trailing_slash() -> None:
    for path in ["/api-browser/", "/api-manual/", "/health/", "/api/catalog/", "/api/error-codes/", "/docs/", "/portal/"]:
        response = client.get(path, follow_redirects=False)
        assert response.status_code in {200, 307}, path
        if "json" in response.headers.get("content-type", ""):
            body = response.json()
            assert body.get("errCode") != "100401", path


def test_unauthorized_response_reuses_incoming_trace_header() -> None:
    incoming = "12345678901234567890123"
    response = client.get(
        "/api/v1/knowledge-search/universal-search",
        headers={"X-Request-Id": incoming},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["errCode"] == "100401"
    assert body["traceId"] == incoming
    assert response.headers.get("X-Request-Id") == incoming
    assert response.headers.get("X-Trace-Id") == incoming


def test_unknown_route_returns_unified_404() -> None:
    response = client.get("/api/v1/unknown/foo", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404
    body = response.json()
    assert body["errCode"] == "100404"
    assert "traceId" in body
    assert body["data"]["path"] == "/api/v1/unknown/foo"


def test_method_not_allowed_returns_unified_405() -> None:
    response = client.delete(
        "/api/v1/knowledge-bases/query",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 405
    body = response.json()
    assert body["errCode"] == "100405"
    assert "traceId" in body


def test_openapi_documents_no_422_and_error_codes_hint() -> None:
    schema = client.get("/openapi.json").json()
    for path in schema["paths"].values():
        for operation in path.values():
            if isinstance(operation, dict):
                responses = operation.get("responses", {})
                assert "422" not in responses
                success = responses.get("200")
                if isinstance(success, dict):
                    assert "100401" in success["description"]
