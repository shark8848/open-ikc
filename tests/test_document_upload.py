from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.upload_store import upload_dir

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
FILE_ID_PATTERN = re.compile(r"^up_[0-9a-f]{32}$")
UPLOAD_PATH = "/api/v1/knowledge-documents/upload"


@pytest.fixture(autouse=True)
def isolate_upload_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("OPEN_PLATFORM_UPLOAD_TTL_SECONDS", "604800")
    monkeypatch.setenv("OPEN_PLATFORM_UPLOAD_MAX_BYTES", "104857600")
    yield


def _upload(files=None, headers=None, **kwargs):
    payload = {"file": ("报告.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")}
    if files is not None:
        payload["file"] = files
    return client.post(UPLOAD_PATH, files=payload, headers=AUTH if headers is None else headers, **kwargs)


def test_upload_success_returns_temp_url() -> None:
    response = _upload()
    assert response.status_code == 200
    body = response.json()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert FILE_ID_PATTERN.match(data["fileId"])
    assert data["fileName"] == "报告.pdf"
    assert data["fileSize"] == len(b"%PDF-1.4 fake pdf content")
    assert data["contentType"] == "application/pdf"
    assert data["tempUrl"] == f"{UPLOAD_PATH}/{data['fileId']}"
    assert data["expiresInSeconds"] == 604800
    assert data["expiresAt"].endswith("Z")
    assert upload_dir().joinpath(data["fileId"]).is_file()
    assert upload_dir().joinpath(f"{data['fileId']}.json").is_file()


def test_upload_ttl_override_via_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_UPLOAD_TTL_SECONDS", "3600")
    body = _upload().json()
    assert body["errCode"] == "000000"
    assert body["data"]["expiresInSeconds"] == 3600


def test_upload_requires_auth() -> None:
    response = _upload(headers={"Authorization": ""})
    assert response.status_code == 200
    assert response.json()["errCode"] == "100401"


def test_upload_rejects_invalid_extension() -> None:
    response = _upload(files=("evil.exe", b"MZ fake", "application/octet-stream"))
    body = response.json()
    assert body["errCode"] == "100001"
    assert "不支持的文件类型" in body["data"]["reason"]


def test_upload_rejects_empty_file() -> None:
    response = _upload(files=("empty.pdf", b"", "application/pdf"))
    body = response.json()
    assert body["errCode"] == "100001"
    assert "为空" in body["data"]["reason"]


def test_upload_rejects_oversize(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_UPLOAD_MAX_BYTES", "10")
    response = _upload(files=("big.pdf", b"x" * 100, "application/pdf"))
    body = response.json()
    assert body["errCode"] == "100001"
    assert "超过上限" in body["data"]["reason"]


def test_upload_sanitizes_unsafe_file_name() -> None:
    response = _upload(files=("../../etc/passwd.pdf", b"safe", "application/pdf"))
    body = response.json()
    assert body["errCode"] == "000000"
    assert body["data"]["fileName"] == "passwd.pdf"
    assert "/" not in body["data"]["fileName"]


def test_access_staged_file_returns_bytes() -> None:
    content = "# 条款\n第一页".encode("utf-8")
    upload_body = _upload(files=("条款.md", content, "text/markdown")).json()
    file_id = upload_body["data"]["fileId"]
    response = client.get(f"{UPLOAD_PATH}/{file_id}", headers=AUTH)
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers.get("content-disposition", "").startswith("attachment")


def test_access_staged_file_requires_auth() -> None:
    upload_body = _upload().json()
    file_id = upload_body["data"]["fileId"]
    response = client.get(f"{UPLOAD_PATH}/{file_id}", headers={})
    assert response.status_code == 200
    assert response.json()["errCode"] == "100401"


def test_access_missing_file_returns_404() -> None:
    response = client.get(f"{UPLOAD_PATH}/up_{'0' * 32}", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["errCode"] == "100404"


def test_access_expired_file_returns_200013(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_UPLOAD_TTL_SECONDS", "604800")
    upload_body = _upload().json()
    file_id = upload_body["data"]["fileId"]
    sidecar = upload_dir().joinpath(f"{file_id}.json")
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
    record["expires_at"] = past
    sidecar.write_text(json.dumps(record), encoding="utf-8")

    response = client.get(f"{UPLOAD_PATH}/{file_id}", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["errCode"] == "200013"
    assert not sidecar.is_file()


def test_access_forbidden_for_other_owner() -> None:
    alice = {**AUTH, "X-User-Id": "alice"}
    bob = {**AUTH, "X-User-Id": "bob"}
    upload_body = _upload(headers=alice).json()
    file_id = upload_body["data"]["fileId"]

    response = client.get(f"{UPLOAD_PATH}/{file_id}", headers=bob)
    assert response.status_code == 200
    assert response.json()["errCode"] == "100403"

    assert client.get(f"{UPLOAD_PATH}/{file_id}", headers=alice).status_code == 200


def test_catalog_contains_upload_routes() -> None:
    response = client.get("/api/catalog")
    assert response.status_code == 200
    routes = [
        (item["method"], item["path"])
        for category in response.json()["data"]
        for item in category["routes"]
    ]
    assert ("POST", UPLOAD_PATH) in routes
    assert ("GET", f"{UPLOAD_PATH}/{{file_id}}") in routes


def test_error_codes_registered() -> None:
    response = client.get("/api/error-codes")
    assert response.status_code == 200
    codes = {item["errCode"] for item in response.json()["data"]}
    assert "200012" in codes
    assert "200013" in codes
