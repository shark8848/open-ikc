from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from open_ikc_sdk import AsyncOpenIKCClient
from open_ikc_sdk.errors import OpenIKCForbiddenError, OpenIKCNotImplementedError

KB_DATA = {
    "kbId": "kb_10001",
    "kbName": "产品知识库",
    "kbType": "enterprise",
    "teamId": "",
    "orgId": "org_001",
    "kbDesc": "",
    "bizDomain": "general",
    "visibility": "org",
    "metadataSchema": [],
    "createTime": "2026-08-03T10:20:30Z",
    "updateTime": None,
}

INGEST_DATA = {
    "ingestTaskId": "it_10001",
    "docId": "doc_10001",
    "docIds": [],
    "taskStatus": "SUCCEEDED",
    "sourceType": "file",
    "sourceStats": {},
    "ingestTime": "2026-08-03T10:20:30Z",
}

PARSE_RESULT_DATA = {
    "parseStatus": "success",
    "resultFormat": {},
    "pageCount": 12,
    "chunkCount": 24,
    "failedReason": "",
}

SEARCH_DATA = {"answer": "回答", "results": [{"docId": "doc_9", "score": 0.9, "snippet": "片段", "citation": {}}]}


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> AsyncOpenIKCClient:
    return AsyncOpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_async_request_returns_envelope():
    async def main():
        client = make_client(lambda r: ok_response({}))
        envelope = await client.request("GET", "/api/v1/ping")
        assert envelope.ok
        await client.close()

    asyncio.run(main())


def test_async_business_error_raises_mapped_exception():
    async def main():
        body = {"errCode": "100403", "errMsg": "无权限", "traceId": "123", "data": {}}
        client = make_client(lambda r: httpx.Response(200, json=body))
        with pytest.raises(OpenIKCForbiddenError):
            await client.request("GET", "/api/v1/knowledge-bases/kb_1")
        await client.close()

    asyncio.run(main())


def test_async_knowledge_bases_create():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content or b"{}")
            return ok_response(KB_DATA)

        client = make_client(handler)
        kb = await client.knowledge_bases.create(kbName="产品知识库", kbType="enterprise", orgId="org_001")
        assert captured["body"]["kbName"] == "产品知识库"
        assert kb.kbId == "kb_10001"
        await client.close()

    asyncio.run(main())


def test_async_knowledge_bases_update_merges_fields():
    async def main():
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            if request.method == "GET":
                return ok_response(KB_DATA)
            return ok_response({**KB_DATA, "kbName": "改名"})

        client = make_client(handler)
        kb = await client.knowledge_bases.update(kbId="kb_10001", kbName="改名")
        assert calls == ["GET", "POST"]
        assert kb.kbName == "改名"
        await client.close()

    asyncio.run(main())


def test_async_documents_ingest():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content or b"{}")
            return ok_response(INGEST_DATA)

        client = make_client(handler)
        result = await client.documents.ingest(
            kbId="kb_10001",
            source={"type": "file", "objectKey": "oss://bucket/a.pdf"},
            reqId="req_1",
        )
        assert captured["body"]["reqId"] == "req_1"
        assert result.docId == "doc_10001"
        await client.close()

    asyncio.run(main())


def test_async_parse_query_result():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return ok_response(PARSE_RESULT_DATA)

        client = make_client(handler)
        result = await client.parse.query_result(docId="doc_10001")
        assert "docId=doc_10001" in captured["url"]
        assert result.pageCount == 12
        await client.close()

    asyncio.run(main())


def test_async_search_query_placeholder_raises():
    async def main():
        body = {"errCode": "501001", "errMsg": "接口已预占位，待实现", "traceId": "123", "data": {}}
        client = make_client(lambda r: httpx.Response(200, json=body))
        with pytest.raises(OpenIKCNotImplementedError):
            await client.search.query(query="问题")
        await client.close()

    asyncio.run(main())


def test_async_search_query_parses_result():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content or b"{}")
            return ok_response(SEARCH_DATA)

        client = make_client(handler)
        result = await client.search.query(query="问题", kbIds=["kb_1", "kb_2"])
        assert captured["body"] == {
            "query": "问题",
            "kbIds": ["kb_1", "kb_2"],
            "mode": "qa",
            "searchType": "hybrid",
            "relNum": 0,
            "useRerank": False,
            "topK": 5,
            "withCitation": True,
            "isOptimize": False,
        }
        assert result.results[0].score == 0.9
        await client.close()

    asyncio.run(main())


def test_async_download_raw_bytes(tmp_path):
    async def main():
        raw = b"%PDF-1.4 async"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=raw, headers={"content-type": "application/pdf"})

        client = make_client(handler)
        content = await client.parse.download(docId="doc_10001", ticket="tk")
        assert content == raw
        target = tmp_path / "async.pdf"
        content = await client.parse.download(docId="doc_10001", ticket="tk", to_path=str(target))
        assert target.read_bytes() == raw
        await client.close()

    asyncio.run(main())


def test_async_context_manager():
    async def main():
        client = make_client(lambda r: ok_response({}))
        async with client:
            envelope = await client.raw("GET", "/api/v1/ping")
            assert envelope.ok

    asyncio.run(main())


def test_async_repr_hides_token():
    async def main():
        client = make_client(lambda r: ok_response({}))
        assert "secret" not in repr(client)
        assert "<set>" in repr(client)
        await client.close()

    asyncio.run(main())


def test_async_retry_on_connection_error():
    async def main():
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                raise httpx.ConnectError("boom", request=request)
            return ok_response(INGEST_DATA)

        client = make_client(handler)
        result = await client.documents.ingest(kbId="kb_10001", source={"type": "file", "objectKey": "k"}, reqId="req_r")
        assert result.ingestTaskId == "it_10001"
        assert len(calls) == 2
        await client.close()

    asyncio.run(main())


WIKI_TREE_DATA = {
    "kbId": "kb_10001",
    "kbMode": "wiki",
    "total": 1,
    "page": 1,
    "pageSize": 20,
    "tree": [
        {
            "pageId": "wiki_abc123",
            "title": "首页",
            "level": 1,
            "parentPageId": "",
            "children": [{"pageId": "wiki_def456", "title": "子页", "level": 2, "parentPageId": "wiki_abc123", "children": []}],
        }
    ],
}

WIKI_PAGE_DATA = {
    "kbId": "kb_10001",
    "kbMode": "wiki",
    "page": {
        "pageId": "wiki_abc123",
        "title": "首页",
        "level": 1,
        "parentPageId": "",
        "markdown": "# 首页",
        "fields": {},
        "tags": [],
        "links": [],
        "sourceDocs": [],
        "status": "active",
        "createdAt": "2026-08-01T00:00:00Z",
        "updatedAt": "2026-08-02T00:00:00Z",
    },
}

WIKI_SEARCH_DATA = {
    "kbId": "kb_10001",
    "kbMode": "wiki",
    "q": "产品",
    "total": 1,
    "items": [{"pageId": "wiki_abc123", "title": "产品首页", "snippet": "说明", "tags": ["指南"], "score": 0.8}],
}


def test_async_wiki_tree():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return ok_response(WIKI_TREE_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.wiki_tree("kb_10001", page=2, pageSize=10)
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/wiki/tree"
        assert captured["params"] == {"page": "2", "pageSize": "10"}
        assert result.total == 1
        assert result.tree[0].children[0].pageId == "wiki_def456"
        await client.close()

    asyncio.run(main())


def test_async_wiki_page():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return ok_response(WIKI_PAGE_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.wiki_page("kb_10001", page_id="wiki_abc123")
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/wiki/page"
        assert captured["params"] == {"pageId": "wiki_abc123"}
        assert result.page.title == "首页"
        assert result.page.status == "active"
        await client.close()

    asyncio.run(main())


def test_async_wiki_search():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return ok_response(WIKI_SEARCH_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.wiki_search("kb_10001", q="产品", tag="指南")
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/wiki/search"
        assert captured["params"] == {"q": "产品", "tag": "指南"}
        assert result.total == 1
        assert result.items[0].score == 0.8
        await client.close()

    asyncio.run(main())


GRAPH_STAT_DATA = {
    "kbId": "kb_10001",
    "kbMode": "graph",
    "graphId": "graph_abc123",
    "nodeCount": 3,
    "edgeCount": 2,
    "entityTypes": [{"type": "person", "count": 2}],
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


def test_async_graph_stat():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return ok_response(GRAPH_STAT_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.graph_stat("kb_10001")
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/stat"
        assert result.kbMode == "graph"
        assert result.nodeCount == 3
        assert result.entityTypes[0].type == "person"
        assert result.schemaCoverage["overall"] == 1.0
        await client.close()

    asyncio.run(main())


def test_async_graph_nodes():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return ok_response(GRAPH_NODES_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.graph_nodes("kb_10001", entity_type="person", page=2, pageSize=10)
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/nodes"
        assert captured["params"] == {"entityType": "person", "page": "2", "pageSize": "10"}
        assert result.items[0].name == "张三"
        assert result.items[0].confidence == 0.95
        await client.close()

    asyncio.run(main())


def test_async_graph_edges():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return ok_response(GRAPH_EDGES_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.graph_edges("kb_10001", relation_type="works_at")
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/edges"
        assert captured["params"] == {"relationType": "works_at", "page": "1", "pageSize": "20"}
        assert result.items[0].sourceEntityId == "ent_abc123"
        await client.close()

    asyncio.run(main())


def test_async_graph_neighbors():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return ok_response(GRAPH_NEIGHBORS_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.graph_neighbors("kb_10001", entity_id="ent_abc123", depth=1)
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/neighbors"
        assert captured["params"] == {"entityId": "ent_abc123", "depth": "1"}
        assert result.center.name == "张三"
        assert result.edges[0].relationId == "rel_abc123"
        await client.close()

    asyncio.run(main())


def test_async_graph_export():
    async def main():
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return ok_response(GRAPH_EXPORT_DATA)

        client = make_client(handler)
        result = await client.knowledge_bases.graph_export("kb_10001")
        assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/export"
        assert result.format == "jsonl"
        assert result.total == 2
        assert result.content.startswith('{"type":"entity"')
        await client.close()

    asyncio.run(main())
