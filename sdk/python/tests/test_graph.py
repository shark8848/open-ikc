from __future__ import annotations

"""图谱库（kbMode=graph）SDK 客户端与模型测试：mock transport 断言路径/查询参数与模型解析。"""

import httpx

from open_ikc_sdk import OpenIKCClient

GRAPH_STAT_DATA = {
    "kbId": "kb_10001",
    "kbMode": "graph",
    "graphId": "graph_abc123",
    "nodeCount": 3,
    "edgeCount": 2,
    "entityTypes": [{"type": "person", "count": 2}, {"type": "org", "count": 1}],
    "relationTypes": [{"type": "works_at", "count": 2}],
    "schemaCoverage": {"entity": 1.0, "relation": 1.0, "overall": 1.0},
}

GRAPH_NODE_ITEM = {
    "entityId": "ent_abc123",
    "type": "person",
    "name": "张三",
    "properties": {"dept": "研发"},
    "aliases": ["张三丰"],
    "evidence": [{"docId": "doc_1", "chunkId": "chunk_1"}],
    "confidence": 0.95,
    "status": "active",
    "createdAt": "2026-08-01T00:00:00Z",
    "updatedAt": "2026-08-02T00:00:00Z",
}

GRAPH_NODES_DATA = {
    "kbId": "kb_10001",
    "kbMode": "graph",
    "total": 1,
    "page": 1,
    "pageSize": 20,
    "items": [GRAPH_NODE_ITEM],
}

GRAPH_EDGE_ITEM = {
    "relationId": "rel_abc123",
    "type": "works_at",
    "sourceEntityId": "ent_abc123",
    "targetEntityId": "ent_xyz789",
    "properties": {"since": "2024"},
    "evidence": [{"docId": "doc_1"}],
    "confidence": 0.9,
    "status": "active",
    "createdAt": "2026-08-01T00:00:00Z",
    "updatedAt": "2026-08-02T00:00:00Z",
}

GRAPH_EDGES_DATA = {
    "kbId": "kb_10001",
    "kbMode": "graph",
    "total": 1,
    "page": 1,
    "pageSize": 20,
    "items": [GRAPH_EDGE_ITEM],
}

GRAPH_NEIGHBORS_DATA = {
    "kbId": "kb_10001",
    "kbMode": "graph",
    "entityId": "ent_abc123",
    "depth": 1,
    "center": GRAPH_NODE_ITEM,
    "nodes": [GRAPH_NODE_ITEM],
    "edges": [GRAPH_EDGE_ITEM],
}

GRAPH_EXPORT_DATA = {
    "kbId": "kb_10001",
    "kbMode": "graph",
    "graphId": "graph_abc123",
    "format": "jsonl",
    "total": 2,
    "content": '{"type":"entity","entityId":"ent_abc123"}\n{"type":"relation","relationId":"rel_abc123"}',
}


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_graph_stat_parses_model():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response(GRAPH_STAT_DATA)

    client = make_client(handler)
    result = client.knowledge_bases.graph_stat("kb_10001")
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/stat"
    assert result.kbId == "kb_10001"
    assert result.kbMode == "graph"
    assert result.graphId == "graph_abc123"
    assert result.nodeCount == 3
    assert result.edgeCount == 2
    assert result.entityTypes[0].type == "person"
    assert result.entityTypes[0].count == 2
    assert result.relationTypes[0].count == 2
    assert result.schemaCoverage == {"entity": 1.0, "relation": 1.0, "overall": 1.0}
    assert result.to_dict()["nodeCount"] == 3
    client.close()


def test_graph_nodes_sends_query_params_and_parses():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(GRAPH_NODES_DATA)

    client = make_client(handler)
    result = client.knowledge_bases.graph_nodes("kb_10001", entity_type="person", page=2, pageSize=10)
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/nodes"
    assert captured["params"] == {"entityType": "person", "page": "2", "pageSize": "10"}
    assert result.total == 1
    assert result.page == 1
    assert result.pageSize == 20
    node = result.items[0]
    assert node.entityId == "ent_abc123"
    assert node.type == "person"
    assert node.name == "张三"
    assert node.properties == {"dept": "研发"}
    assert node.aliases == ["张三丰"]
    assert node.evidence == [{"docId": "doc_1", "chunkId": "chunk_1"}]
    assert node.confidence == 0.95
    assert node.status == "active"
    assert result.to_dict()["items"][0]["updatedAt"] == "2026-08-02T00:00:00Z"
    client.close()


def test_graph_nodes_defaults_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return ok_response(GRAPH_NODES_DATA)

    client = make_client(handler)
    client.knowledge_bases.graph_nodes("kb_10001")
    assert captured["params"] == {"entityType": "", "page": "1", "pageSize": "20"}
    client.close()


def test_graph_edges_sends_query_params_and_parses():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(GRAPH_EDGES_DATA)

    client = make_client(handler)
    result = client.knowledge_bases.graph_edges("kb_10001", relation_type="works_at", page=1, pageSize=20)
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/edges"
    assert captured["params"] == {"relationType": "works_at", "page": "1", "pageSize": "20"}
    edge = result.items[0]
    assert edge.relationId == "rel_abc123"
    assert edge.type == "works_at"
    assert edge.sourceEntityId == "ent_abc123"
    assert edge.targetEntityId == "ent_xyz789"
    assert edge.properties == {"since": "2024"}
    assert edge.confidence == 0.9
    assert result.to_dict()["items"][0]["relationId"] == "rel_abc123"
    client.close()


def test_graph_neighbors_sends_params_and_parses():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(GRAPH_NEIGHBORS_DATA)

    client = make_client(handler)
    result = client.knowledge_bases.graph_neighbors("kb_10001", entity_id="ent_abc123", depth=1)
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/neighbors"
    assert captured["params"] == {"entityId": "ent_abc123", "depth": "1"}
    assert result.entityId == "ent_abc123"
    assert result.depth == 1
    assert result.center.name == "张三"
    assert result.nodes[0].entityId == "ent_abc123"
    assert result.edges[0].relationId == "rel_abc123"
    assert result.to_dict()["center"]["name"] == "张三"
    client.close()


def test_graph_export_parses_content():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response(GRAPH_EXPORT_DATA)

    client = make_client(handler)
    result = client.knowledge_bases.graph_export("kb_10001")
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/export"
    assert result.kbMode == "graph"
    assert result.graphId == "graph_abc123"
    assert result.format == "jsonl"
    assert result.total == 2
    assert result.content.startswith('{"type":"entity"')
    assert result.to_dict()["total"] == 2
    client.close()
