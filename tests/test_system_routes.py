from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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
