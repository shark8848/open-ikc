from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_base_store import KnowledgeBaseStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
WIKI_CONFIG = {"granularity": "heading", "extractFields": ["负责人", "版本"], "linkMode": "auto", "dedup": "merge"}
GRAPH_SCHEMA = {
    "entityTypes": [{"type": "person", "description": "人员"}, {"type": "org", "description": "组织"}],
    "relationTypes": [{"type": "works_at", "sourceTypes": ["person"], "targetTypes": ["org"], "description": "任职"}],
}


@pytest.fixture(autouse=True)
def reset_knowledge_base_store() -> None:
    KnowledgeBaseStore.reset()
    yield
    KnowledgeBaseStore.reset()


def _create(**overrides) -> dict:
    payload = {
        "kbName": "专业库测试",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "bizDomain": "general",
        "visibility": "private",
        "metadataSchema": [],
    }
    payload.update(overrides)
    return client.post("/api/v1/knowledge-bases/create", json=payload, headers=AUTH).json()


def _update(kb_id: str, **overrides) -> dict:
    payload = {"kbId": kb_id}
    payload.update(overrides)
    return client.post("/api/v1/knowledge-bases/update", json=payload, headers=AUTH).json()


def test_create_defaults_to_text_mode() -> None:
    body = _create()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbMode"] == "text"
    assert data["wikiConfig"] == {}
    assert data["graphSchema"] == {}


def test_create_wiki_mode_with_config() -> None:
    body = _create(kbMode="wiki", wikiConfig=WIKI_CONFIG)
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbMode"] == "wiki"
    assert data["wikiConfig"] == WIKI_CONFIG
    assert data["graphSchema"] == {}


def test_create_graph_mode_with_schema() -> None:
    body = _create(kbMode="graph", graphSchema=GRAPH_SCHEMA)
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbMode"] == "graph"
    assert data["graphSchema"] == GRAPH_SCHEMA
    assert data["wikiConfig"] == {}


def test_create_invalid_kb_mode_rejected() -> None:
    body = _create(kbMode="ontology")
    assert body["errCode"] == "100001"
    assert "kbMode" in json.dumps(body, ensure_ascii=False)


def test_create_wiki_mode_invalid_granularity_rejected() -> None:
    body = _create(kbMode="wiki", wikiConfig={"granularity": "chapter"})
    assert body["errCode"] == "100001"
    assert "granularity" in json.dumps(body, ensure_ascii=False)


def test_create_wiki_mode_invalid_extract_fields_rejected() -> None:
    body = _create(kbMode="wiki", wikiConfig={"extractFields": ["负责人", 42]})
    assert body["errCode"] == "100001"


def test_create_graph_mode_empty_entity_type_rejected() -> None:
    body = _create(kbMode="graph", graphSchema={"entityTypes": [{"type": ""}]})
    assert body["errCode"] == "100001"


def test_create_graph_mode_duplicate_relation_type_rejected() -> None:
    schema = {
        "relationTypes": [
            {"type": "works_at"},
            {"type": "works_at"},
        ]
    }
    body = _create(kbMode="graph", graphSchema=schema)
    assert body["errCode"] == "100001"
    assert "重复" in json.dumps(body, ensure_ascii=False)


def test_query_filters_by_kb_mode() -> None:
    _create(kbName="文本库A")
    wiki_id = _create(kbName="Wiki库B", kbMode="wiki", wikiConfig=WIKI_CONFIG)["data"]["kbId"]
    _create(kbName="图谱库C", kbMode="graph", graphSchema=GRAPH_SCHEMA)

    wiki_only = client.post("/api/v1/knowledge-bases/query", json={"kbMode": "wiki", "page": 1, "pageSize": 20}, headers=AUTH).json()
    assert wiki_only["errCode"] == "000000"
    assert [item["kbId"] for item in wiki_only["data"]["items"]] == [wiki_id]
    assert wiki_only["data"]["items"][0]["kbMode"] == "wiki"


def test_update_text_to_wiki() -> None:
    kb_id = _create()["data"]["kbId"]
    body = _update(kb_id, kbMode="wiki", wikiConfig=WIKI_CONFIG)
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbMode"] == "wiki"
    assert data["wikiConfig"] == WIKI_CONFIG


def test_update_without_kb_mode_keeps_mode() -> None:
    kb_id = _create(kbMode="wiki", wikiConfig=WIKI_CONFIG)["data"]["kbId"]
    body = _update(kb_id, kbName="改名")
    assert body["errCode"] == "000000"
    assert body["data"]["kbMode"] == "wiki"
    assert body["data"]["wikiConfig"] == WIKI_CONFIG


def test_update_wiki_to_graph_conflict() -> None:
    kb_id = _create(kbMode="wiki", wikiConfig=WIKI_CONFIG)["data"]["kbId"]
    body = _update(kb_id, kbMode="graph", graphSchema=GRAPH_SCHEMA)
    assert body["errCode"] == "200014"
    assert body["data"]["field"] == "kbMode"


def test_detail_returns_mode_and_config() -> None:
    kb_id = _create(kbMode="graph", graphSchema=GRAPH_SCHEMA)["data"]["kbId"]
    body = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=AUTH).json()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbMode"] == "graph"
    assert data["graphSchema"] == GRAPH_SCHEMA


def test_error_code_200014_registered() -> None:
    body = client.get("/api/error-codes").json()
    codes = {item["errCode"] for item in body["data"]}
    assert "200014" in codes
