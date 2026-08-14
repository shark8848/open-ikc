from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


_PORTAL_DIST = Path(__file__).resolve().parents[1] / "portal" / "dist"


def test_root_redirects_to_portal_when_built() -> None:
    """首页 / 直达管理 Portal（已构建时）；未构建时回退 API 浏览页。"""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    if _PORTAL_DIST.is_dir():
        assert response.headers["location"] == "/portal/"
    else:
        assert response.headers["location"] == "/api-browser"


def test_system_routes_are_exempt_from_business_auth() -> None:
    health_response = client.get("/health")
    assert health_response.status_code == 200
    health_body = health_response.json()
    assert health_body["status"] is True
    assert health_body["service"] == "open-ikc-api"
    assert "traceId" in health_body

    catalog_response = client.get("/api/catalog")
    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["status"] is True
    assert "data" in catalog_body
    assert "traceId" in catalog_body

    error_codes_response = client.get("/api/error-codes")
    assert error_codes_response.status_code == 200
    error_codes_body = error_codes_response.json()
    assert error_codes_body["status"] is True
    assert "data" in error_codes_body
    assert "traceId" in error_codes_body
    # 关键错误码必须注册（含管理面 503001）
    registered_codes = {item["code"] for item in error_codes_body["data"]}
    assert {
        "000000", "100001", "100401", "100403", "100404", "100405", "100409",
        "501001", "999999", "503001",
    } <= registered_codes


def test_business_routes_still_require_authentication() -> None:
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
    assert response.json()["errCode"] == "100401"
