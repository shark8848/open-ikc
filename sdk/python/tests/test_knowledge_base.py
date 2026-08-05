from __future__ import annotations

import json

import httpx
import pytest

from open_ikc_sdk import KnowledgeMetadataField, OpenIKCClient
from open_ikc_sdk.errors import OpenIKCForbiddenError

KB_DATA = {
    "kbId": "kb_10001",
    "kbName": "产品知识库",
    "kbType": "enterprise",
    "teamId": "",
    "orgId": "org_001",
    "kbDesc": "用于客服问答",
    "bizDomain": "customer_service",
    "visibility": "org",
    "metadataSchema": [
        {
            "name": "docType",
            "type": "string",
            "required": False,
            "description": "文档类型",
            "defaultValue": "合同",
            "enum": ["合同", "制度"],
            "pattern": "",
            "minLength": 0,
            "maxLength": 32,
            "example": "合同",
        }
    ],
    "createTime": "2026-08-03T10:20:30Z",
    "updateTime": None,
}


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_create_sends_full_body_and_parses_model():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(KB_DATA)

    client = make_client(handler)
    kb = client.knowledge_bases.create(
        kbName="产品知识库",
        kbType="enterprise",
        orgId="org_001",
        visibility="org",
        metadataSchema=[{"name": "docType", "type": "string"}],
    )
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/knowledge-bases/create"
    assert captured["body"]["kbName"] == "产品知识库"
    assert captured["body"]["kbType"] == "enterprise"
    assert captured["body"]["metadataSchema"] == [{"name": "docType", "type": "string"}]
    assert kb.kbId == "kb_10001"
    assert kb.visibility == "org"
    assert kb.metadataSchema[0].name == "docType"
    client.close()


def test_create_defaults_when_omitted():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(KB_DATA)

    client = make_client(handler)
    client.knowledge_bases.create(kbName="产品知识库")
    body = captured["body"]
    assert body["kbType"] == "personal"
    assert body["visibility"] == "private"
    assert body["bizDomain"] == "general"
    assert "metadataSchema" not in body
    client.close()


def test_create_accepts_metadata_field_instances():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(KB_DATA)

    client = make_client(handler)
    client.knowledge_bases.create(
        kbName="x",
        metadataSchema=[KnowledgeMetadataField(name="docType", type="string", maxLength=32)],
    )
    assert captured["body"]["metadataSchema"][0] == {
        "name": "docType",
        "type": "string",
        "required": False,
        "description": "",
        "defaultValue": None,
        "enum": [],
        "pattern": "",
        "minLength": None,
        "maxLength": 32,
        "example": None,
    }
    client.close()


def test_get_substitutes_path_and_parses_model():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response(KB_DATA)

    client = make_client(handler)
    kb = client.knowledge_bases.get("kb_10001")
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001"
    assert kb.kbId == "kb_10001"
    assert kb.metadataSchema[0].enum == ["合同", "制度"]
    client.close()


def test_query_body_only_contains_provided_filters():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"total": 1, "page": 1, "pageSize": 20, "items": [KB_DATA]})

    client = make_client(handler)
    page = client.knowledge_bases.query(kbType="enterprise", orgId="org_001", keyword="客服")
    assert captured["body"] == {"page": 1, "pageSize": 20, "kbType": "enterprise", "orgId": "org_001", "keyword": "客服"}
    assert page.total == 1
    assert page.items[0].kbName == "产品知识库"
    client.close()


def test_query_omits_empty_filters():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"total": 0, "page": 1, "pageSize": 20, "items": []})

    client = make_client(handler)
    client.knowledge_bases.query(page=2, pageSize=10)
    assert captured["body"] == {"page": 2, "pageSize": 10}
    client.close()


def test_update_merges_unchanged_fields_from_existing_record():
    calls = []
    updated_data = {**KB_DATA, "kbName": "产品知识库-客服版"}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return ok_response(KB_DATA)
        return ok_response(updated_data)

    client = make_client(handler)
    result = client.knowledge_bases.update(kbId="kb_10001", kbName="产品知识库-客服版")
    assert calls == [
        ("GET", "/api/v1/knowledge-bases/kb_10001"),
        ("POST", "/api/v1/knowledge-bases/update"),
    ]
    assert result.kbName == "产品知识库-客服版"
    client.close()


def test_update_merge_preserves_scope_and_schema_fields():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return ok_response(KB_DATA)
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({**KB_DATA, "kbName": "改名"})

    client = make_client(handler)
    client.knowledge_bases.update(kbId="kb_10001", kbName="改名")
    body = captured["body"]
    assert body["kbId"] == "kb_10001"
    assert body["kbType"] == "enterprise"
    assert body["orgId"] == "org_001"
    assert body["visibility"] == "org"
    assert body["kbDesc"] == "用于客服问答"
    assert body["metadataSchema"][0]["name"] == "docType"
    client.close()


def test_update_override_metadata_schema():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return ok_response(KB_DATA)
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(KB_DATA)

    client = make_client(handler)
    client.knowledge_bases.update(kbId="kb_10001", metadataSchema=[{"name": "newField", "type": "string"}])
    assert captured["body"]["metadataSchema"] == [{"name": "newField", "type": "string"}]
    client.close()


def test_update_rejects_unknown_fields():
    client = make_client(lambda r: ok_response(KB_DATA))
    with pytest.raises(TypeError, match="未知字段"):
        client.knowledge_bases.update(kbId="kb_10001", unknownField="x")
    client.close()


def test_business_error_raises_mapped_exception():
    body = {"errCode": "100403", "errMsg": "无权限", "traceId": "123", "data": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = make_client(handler)
    with pytest.raises(OpenIKCForbiddenError):
        client.knowledge_bases.create(kbName="x")
    client.close()


def test_model_extra_fields_passthrough():
    client = make_client(lambda r: ok_response({**KB_DATA, "futureField": 1}))
    result = client.knowledge_bases.get("kb_10001")
    assert result.extra == {"futureField": 1}
    assert result.to_dict()["futureField"] == 1
    client.close()
