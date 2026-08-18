from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.catalog import API_CATALOG
from app.main import app
from app.services.document_store import DocumentStore
from app.services.graph_store import (
    GRAPH_STATUS,
    GraphNodeRecord,
    GraphRelationRecord,
    GraphStore,
    graph_id,
)
from app.services.knowledge_base_store import KnowledgeBaseStore
from app.services.parse_store import ParseTaskStore, ParseTicketStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
GRAPH_SCHEMA = {
    "entityTypes": [{"type": "person", "description": "人员"}, {"type": "org", "description": "组织"}],
    "relationTypes": [{"type": "works_at", "sourceTypes": ["person"], "targetTypes": ["org"], "description": "任职"}],
}


@pytest.fixture(autouse=True)
def reset_graph_stores() -> None:
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    ParseTaskStore.reset()
    ParseTicketStore.reset()
    GraphStore.reset()
    yield
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    ParseTaskStore.reset()
    ParseTicketStore.reset()
    GraphStore.reset()


def _create_graph_kb(title: str = "图谱专业库", **overrides) -> dict:
    payload = {
        "kbName": title,
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "图谱库集成测试",
        "bizDomain": "general",
        "visibility": "private",
        "metadataSchema": [],
        "kbMode": "graph",
        "graphSchema": GRAPH_SCHEMA,
    }
    payload.update(overrides)
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _create_text_kb() -> dict:
    payload = {
        "kbName": "文本知识库",
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "",
        "bizDomain": "general",
        "visibility": "private",
        "metadataSchema": [],
    }
    response = client.post("/api/v1/knowledge-bases/create", json=payload, headers=AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _ingest(kb_id: str, title: str) -> dict:
    payload = {
        "kbId": kb_id,
        "source": {"type": "url", "url": f"https://example.com/{title}.md"},
        "docTitle": title,
    }
    response = client.post("/api/v1/knowledge-documents/ingest", json=payload, headers=AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    return body["data"]


def _parse_sync(kb_id: str, doc_id: str) -> dict:
    payload = {
        "kbId": kb_id,
        "docId": doc_id,
        "parseStrategy": {"docType": "md", "parseMethod": "auto"},
        "resultFormat": {"type": "json"},
        "executeMode": "sync",
    }
    response = client.post("/api/v1/knowledge-documents/parse", json=payload, headers=AUTH)
    body = response.json()
    assert body["errCode"] == "000000"
    assert body["data"]["taskStatus"] == "success"
    return body["data"]


def _stat(kb_id: str) -> dict:
    return client.get(f"/api/v1/knowledge-bases/{kb_id}/graph/stat", headers=AUTH).json()


def _nodes(kb_id: str, **params) -> dict:
    return client.get(f"/api/v1/knowledge-bases/{kb_id}/graph/nodes", params=params, headers=AUTH).json()


def _edges(kb_id: str, **params) -> dict:
    return client.get(f"/api/v1/knowledge-bases/{kb_id}/graph/edges", params=params, headers=AUTH).json()


def _neighbors(kb_id: str, entity_id: str, **params) -> dict:
    return client.get(
        f"/api/v1/knowledge-bases/{kb_id}/graph/neighbors",
        params={"entityId": entity_id, **params},
        headers=AUTH,
    ).json()


def _export(kb_id: str) -> dict:
    return client.get(f"/api/v1/knowledge-bases/{kb_id}/graph/export", headers=AUTH).json()


def _make_node(kb_id: str, doc_id: str, entity_type: str, name: str, *, aliases: list[str] | None = None) -> GraphNodeRecord:
    from app.services.graph_store import _now_iso, entity_id, normalize_name

    gid = graph_id(kb_id)
    now = _now_iso()
    return GraphNodeRecord(
        entity_id=entity_id(gid, entity_type, normalize_name(name)),
        graph_id=gid,
        kb_id=kb_id,
        doc_id=doc_id,
        entity_type=entity_type,
        name=name,
        normalized_name=normalize_name(name),
        properties={},
        aliases=list(aliases or []),
        evidence=[{"docId": doc_id}],
        confidence=0.9,
        status=GRAPH_STATUS["ACTIVE"],
        created_at=now,
        updated_at=now,
    )


def _make_edge(kb_id: str, doc_id: str, source: GraphNodeRecord, target: GraphNodeRecord, relation_type: str) -> GraphRelationRecord:
    from app.services.graph_store import _now_iso, relation_id

    gid = graph_id(kb_id)
    now = _now_iso()
    return GraphRelationRecord(
        relation_id=relation_id(gid, relation_type, source.entity_id, target.entity_id),
        graph_id=gid,
        kb_id=kb_id,
        doc_id=doc_id,
        relation_type=relation_type,
        source_entity_id=source.entity_id,
        target_entity_id=target.entity_id,
        properties={},
        evidence=[{"docId": doc_id}],
        confidence=0.85,
        status=GRAPH_STATUS["ACTIVE"],
        created_at=now,
        updated_at=now,
    )


def test_graph_stat_on_text_kb_rejected() -> None:
    kb = _create_text_kb()
    body = _stat(kb["kbId"])
    assert body["errCode"] == "100001"
    assert body["data"]["field"] == "kbMode"


def test_graph_empty_stat() -> None:
    kb = _create_graph_kb()
    body = _stat(kb["kbId"])
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbMode"] == "graph"
    assert data["graphId"].startswith("graph_")
    assert data["nodeCount"] == 0
    assert data["edgeCount"] == 0
    assert data["schemaCoverage"] == {"entity": 1.0, "relation": 1.0, "overall": 1.0}
    assert _nodes(kb["kbId"])["data"]["items"] == []
    assert _edges(kb["kbId"])["data"]["items"] == []


def test_parse_sync_builds_graph_node() -> None:
    kb = _create_graph_kb()
    doc = _ingest(kb["kbId"], "张三")
    _parse_sync(kb["kbId"], doc["docId"])

    stat = _stat(kb["kbId"])
    assert stat["errCode"] == "000000"
    assert stat["data"]["nodeCount"] == 1
    assert stat["data"]["entityTypes"] == [{"type": "person", "count": 1}]
    assert stat["data"]["schemaCoverage"]["entity"] == 1.0

    nodes = _nodes(kb["kbId"])
    assert nodes["data"]["total"] == 1
    node = nodes["data"]["items"][0]
    assert node["type"] == "person"
    assert node["name"] == "张三"
    assert node["evidence"] == [{"docId": doc["docId"]}]
    assert node["status"] == "active"

    # 邻域：仅中心节点
    nb = _neighbors(kb["kbId"], node["entityId"])
    assert nb["errCode"] == "000000"
    assert nb["data"]["center"]["entityId"] == node["entityId"]
    assert [n["entityId"] for n in nb["data"]["nodes"]] == [node["entityId"]]
    assert nb["data"]["edges"] == []


def test_graph_neighbors_depth_one_and_two() -> None:
    kb = _create_graph_kb()
    alice = GraphStore.merge_node(_make_node(kb["kbId"], "d1", "person", "Alice"))
    bob = GraphStore.merge_node(_make_node(kb["kbId"], "d2", "person", "Bob"))
    org = GraphStore.merge_node(_make_node(kb["kbId"], "d3", "org", "Acme"))
    GraphStore.merge_edge(_make_edge(kb["kbId"], "d1", alice, org, "works_at"))
    GraphStore.merge_edge(_make_edge(kb["kbId"], "d2", bob, org, "works_at"))

    nb1 = _neighbors(kb["kbId"], alice.entity_id, depth=1)
    assert nb1["errCode"] == "000000"
    assert {n["name"] for n in nb1["data"]["nodes"]} == {"Alice", "Acme"}
    assert len(nb1["data"]["edges"]) == 1

    nb2 = _neighbors(kb["kbId"], alice.entity_id, depth=2)
    assert {n["name"] for n in nb2["data"]["nodes"]} == {"Alice", "Acme", "Bob"}
    assert len(nb2["data"]["edges"]) == 2


def test_graph_neighbors_not_found() -> None:
    kb = _create_graph_kb()
    body = _neighbors(kb["kbId"], "ent_not_exist")
    assert body["errCode"] == "100404"
    assert body["data"]["field"] == "entityId"


def test_graph_nodes_filter_and_pagination() -> None:
    kb = _create_graph_kb()
    GraphStore.merge_node(_make_node(kb["kbId"], "d1", "person", "Alice"))
    GraphStore.merge_node(_make_node(kb["kbId"], "d2", "person", "Bob"))
    GraphStore.merge_node(_make_node(kb["kbId"], "d3", "org", "Acme"))

    body = _nodes(kb["kbId"], entityType="person")
    assert body["data"]["total"] == 2
    assert {item["name"] for item in body["data"]["items"]} == {"Alice", "Bob"}

    body = _nodes(kb["kbId"], page=1, pageSize=2)
    assert body["data"]["total"] == 3
    assert len(body["data"]["items"]) == 2

    body = _nodes(kb["kbId"], page=2, pageSize=2)
    assert len(body["data"]["items"]) == 1


def test_graph_edges_filter() -> None:
    kb = _create_graph_kb()
    alice = GraphStore.merge_node(_make_node(kb["kbId"], "d1", "person", "Alice"))
    org = GraphStore.merge_node(_make_node(kb["kbId"], "d3", "org", "Acme"))
    GraphStore.merge_edge(_make_edge(kb["kbId"], "d1", alice, org, "works_at"))

    body = _edges(kb["kbId"])
    assert body["data"]["total"] == 1
    edge = body["data"]["items"][0]
    assert edge["type"] == "works_at"
    assert edge["sourceEntityId"] == alice.entity_id
    assert edge["targetEntityId"] == org.entity_id

    body = _edges(kb["kbId"], relationType="no_such_type")
    assert body["data"]["total"] == 0


def test_graph_export_jsonl() -> None:
    kb = _create_graph_kb()
    doc = _ingest(kb["kbId"], "张三")
    _parse_sync(kb["kbId"], doc["docId"])

    body = _export(kb["kbId"])
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["format"] == "jsonl"
    assert data["total"] == 1
    lines = [json.loads(line) for line in data["content"].splitlines() if line.strip()]
    assert lines[0]["kind"] == "entity"
    assert lines[0]["name"] == "张三"
    assert lines[0]["status"] == "active"


def test_graph_routes_registered_in_catalog() -> None:
    kb_routes = {route["path"] for route in next(item["routes"] for item in API_CATALOG if item["tag"] == "knowledge-base")}
    for path in (
        "/api/v1/knowledge-bases/{kb_id}/graph/stat",
        "/api/v1/knowledge-bases/{kb_id}/graph/nodes",
        "/api/v1/knowledge-bases/{kb_id}/graph/edges",
        "/api/v1/knowledge-bases/{kb_id}/graph/neighbors",
        "/api/v1/knowledge-bases/{kb_id}/graph/export",
    ):
        assert path in kb_routes
