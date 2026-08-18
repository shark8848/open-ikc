from __future__ import annotations

"""MCP 工具测试（mcp>=2.0）：通过 server.call_tool 调用工具（httpx.MockTransport，不起服务），
断言请求路径 / body 与返回 JSON。"""

import asyncio
import json

import httpx
import pytest

from open_ikc_sdk import OpenIKCClient
from open_ikc_sdk.mcp.server import build_server

OK = "000000"


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": OK, "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def make_server(handler):
    """构造已装配工具的 server。"""
    return build_server(make_client(handler))


def call_tool(server, name: str, arguments: dict | None = None) -> dict:
    """同步包装：await server.call_tool 并解析返回 JSON。"""
    arguments = arguments or {}

    async def _call():
        result = await server.call_tool(name, arguments)
        assert result.is_error is False, f"工具 {name} 返回错误: {result.content}"
        text = result.content[0].text
        return json.loads(text)

    return asyncio.run(_call())


async def list_tool_names(server):
    """返回已注册工具名集合。"""
    tools = await server.list_tools()
    return {tool.name for tool in tools}


# ---------- 知识库 ----------


def test_kb_create():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"kbId": "kb_10001", "kbName": "测试库"})

    result = call_tool(make_server(handler), "kb_create", {"kbName": "测试库", "kbType": "personal"})
    assert captured["path"] == "/api/v1/knowledge-bases/create"
    assert captured["body"]["kbName"] == "测试库"
    assert result["kbId"] == "kb_10001"


def test_kb_update():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"kbId": "kb_10001", "kbName": "新名称"})

    result = call_tool(make_server(handler), "kb_update", {"kbId": "kb_10001", "kbName": "新名称"})
    assert captured["body"]["kbId"] == "kb_10001"
    assert captured["body"]["kbName"] == "新名称"
    assert result["kbName"] == "新名称"


def test_kb_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"total": 1, "page": 1, "pageSize": 20, "items": []})

    result = call_tool(make_server(handler), "kb_query", {"page": 1, "pageSize": 10, "keyword": "知识"})
    assert captured["path"] == "/api/v1/knowledge-bases/query"
    assert captured["body"] == {"page": 1, "pageSize": 10, "keyword": "知识"}
    assert result["total"] == 1


def test_kb_get():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response({"kbId": "kb_10001", "kbName": "测试库"})

    result = call_tool(make_server(handler), "kb_get", {"kbId": "kb_10001"})
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001"
    assert result["kbId"] == "kb_10001"


def test_wiki_tree():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(
            {
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
                        "children": [
                            {"pageId": "wiki_def456", "title": "子页", "level": 2, "parentPageId": "wiki_abc123", "children": []}
                        ],
                    }
                ],
            }
        )

    result = call_tool(make_server(handler), "wiki_tree", {"kbId": "kb_10001", "page": 1, "pageSize": 20})
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/wiki/tree"
    assert captured["params"] == {"page": "1", "pageSize": "20"}
    assert result["tree"][0]["pageId"] == "wiki_abc123"
    assert result["tree"][0]["children"][0]["title"] == "子页"


def test_wiki_page():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "wiki",
                "page": {
                    "pageId": "wiki_abc123",
                    "title": "首页",
                    "level": 1,
                    "parentPageId": "",
                    "markdown": "# 首页",
                    "fields": {"owner": "张三"},
                    "tags": ["指南"],
                    "links": [{"title": "子页", "pageId": "wiki_def456"}],
                    "sourceDocs": ["doc_1"],
                    "status": "active",
                    "createdAt": "2026-08-01T00:00:00Z",
                    "updatedAt": "2026-08-02T00:00:00Z",
                },
            }
        )

    result = call_tool(make_server(handler), "wiki_page", {"kbId": "kb_10001", "pageId": "wiki_abc123"})
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/wiki/page"
    assert captured["params"] == {"pageId": "wiki_abc123"}
    assert result["page"]["title"] == "首页"
    assert result["page"]["links"] == [{"title": "子页", "pageId": "wiki_def456"}]


def test_wiki_search():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "wiki",
                "q": "产品",
                "total": 1,
                "items": [{"pageId": "wiki_abc123", "title": "产品首页", "snippet": "说明", "tags": ["指南"], "score": 0.9}],
            }
        )

    result = call_tool(make_server(handler), "wiki_search", {"kbId": "kb_10001", "q": "产品", "tag": "指南"})
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/wiki/search"
    assert captured["params"] == {"q": "产品", "tag": "指南"}
    assert result["items"][0]["pageId"] == "wiki_abc123"
    assert result["items"][0]["score"] == 0.9


# ---------- 图谱库 ----------


def test_graph_stat():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "graph",
                "graphId": "graph_abc123",
                "nodeCount": 3,
                "edgeCount": 2,
                "entityTypes": [{"type": "person", "count": 2}],
                "relationTypes": [{"type": "works_at", "count": 2}],
                "schemaCoverage": {"entity": 1.0, "relation": 1.0, "overall": 1.0},
            }
        )

    result = call_tool(make_server(handler), "graph_stat", {"kbId": "kb_10001"})
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/stat"
    assert result["nodeCount"] == 3
    assert result["entityTypes"][0]["type"] == "person"


def test_graph_nodes():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "graph",
                "total": 1,
                "page": 1,
                "pageSize": 20,
                "items": [
                    {
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
                ],
            }
        )

    result = call_tool(
        make_server(handler),
        "graph_nodes",
        {"kbId": "kb_10001", "entityType": "person", "page": 1, "pageSize": 20},
    )
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/nodes"
    assert captured["params"] == {"entityType": "person", "page": "1", "pageSize": "20"}
    assert result["items"][0]["name"] == "张三"
    assert result["items"][0]["confidence"] == 0.95


def test_graph_edges():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "graph",
                "total": 1,
                "page": 1,
                "pageSize": 20,
                "items": [
                    {
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
                ],
            }
        )

    result = call_tool(
        make_server(handler),
        "graph_edges",
        {"kbId": "kb_10001", "relationType": "works_at", "page": 1, "pageSize": 20},
    )
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/edges"
    assert captured["params"] == {"relationType": "works_at", "page": "1", "pageSize": "20"}
    assert result["items"][0]["relationId"] == "rel_abc123"
    assert result["items"][0]["sourceEntityId"] == "ent_abc123"


def test_graph_neighbors():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "graph",
                "entityId": "ent_abc123",
                "depth": 1,
                "center": {
                    "entityId": "ent_abc123",
                    "type": "person",
                    "name": "张三",
                    "properties": {},
                    "aliases": [],
                    "evidence": [],
                    "confidence": 0.95,
                    "status": "active",
                    "createdAt": "2026-08-01T00:00:00Z",
                    "updatedAt": "2026-08-02T00:00:00Z",
                },
                "nodes": [],
                "edges": [
                    {
                        "relationId": "rel_abc123",
                        "type": "works_at",
                        "sourceEntityId": "ent_abc123",
                        "targetEntityId": "ent_xyz789",
                        "properties": {},
                        "evidence": [],
                        "confidence": 0.9,
                        "status": "active",
                        "createdAt": "2026-08-01T00:00:00Z",
                        "updatedAt": "2026-08-02T00:00:00Z",
                    }
                ],
            }
        )

    result = call_tool(
        make_server(handler),
        "graph_neighbors",
        {"kbId": "kb_10001", "entityId": "ent_abc123", "depth": 1},
    )
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/neighbors"
    assert captured["params"] == {"entityId": "ent_abc123", "depth": "1"}
    assert result["center"]["name"] == "张三"
    assert result["edges"][0]["relationId"] == "rel_abc123"


def test_graph_export():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "graph",
                "graphId": "graph_abc123",
                "format": "jsonl",
                "total": 2,
                "content": '{"type":"entity","entityId":"ent_abc123"}\n{"type":"relation","relationId":"rel_abc123"}',
            }
        )

    result = call_tool(make_server(handler), "graph_export", {"kbId": "kb_10001"})
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001/graph/export"
    assert result["format"] == "jsonl"
    assert result["total"] == 2
    assert result["content"].startswith('{"type":"entity"')


# ---------- 文档 ----------


def test_doc_ingest():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"ingestTaskId": "ing_10001", "docId": "doc_10001"})

    result = call_tool(
        make_server(handler),
        "doc_ingest",
        {
            "kbId": "kb_10001",
            "source": {"type": "url", "url": "https://example.com/a.pdf"},
            "docTitle": "示例文档",
        },
    )
    assert captured["path"] == "/api/v1/knowledge-documents/ingest"
    assert captured["body"]["source"]["type"] == "url"
    assert captured["body"]["docTitle"] == "示例文档"
    assert result["docId"] == "doc_10001"


def test_doc_ingest_invalid_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response({})

    server = make_server(handler)
    with pytest.raises(Exception):
        call_tool(
            server,
            "doc_ingest",
            {"kbId": "kb_1", "source": {"type": "url", "url": "x"}, "tags": {"not": "list"}},
        )


def test_doc_ingest_and_parse():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"ingestTaskId": "ing_1", "parseTaskId": "parse_1", "executeMode": "async"})

    result = call_tool(
        make_server(handler),
        "doc_ingest_and_parse",
        {"kbId": "kb_10001", "source": {"type": "url", "url": "https://example.com/a.pdf"}, "executeMode": "async"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/ingest-and-parse"
    assert captured["body"]["executeMode"] == "async"
    assert result["parseTaskId"] == "parse_1"


def test_doc_get():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response({"docId": "doc_10001", "docTitle": "示例"})

    result = call_tool(make_server(handler), "doc_get", {"docId": "doc_10001"})
    assert captured["path"] == "/api/v1/knowledge-documents/doc_10001"
    assert result["docId"] == "doc_10001"


# ---------- 解析 ----------


def test_parse_start():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"taskId": "parse_10001", "taskStatus": "QUEUED"})

    result = call_tool(
        make_server(handler),
        "parse_start",
        {"kbId": "kb_10001", "docId": "doc_10001"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/parse"
    assert captured["body"]["kbId"] == "kb_10001"
    assert captured["body"]["docId"] == "doc_10001"
    assert result["taskId"] == "parse_10001"


def test_parse_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response({"parseStatus": "SUCCEEDED", "pageCount": 5, "chunkCount": 20})

    result = call_tool(make_server(handler), "parse_query", {"docId": "doc_10001"})
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/query"
    assert captured["params"] == {"docId": "doc_10001"}
    assert result["parseStatus"] == "SUCCEEDED"


def test_parse_issue_ticket():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response({"ticket": "tk_123", "expireAt": "2026-08-11T00:00:00Z"})

    result = call_tool(make_server(handler), "parse_issue_ticket", {"docId": "doc_10001"})
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/issue-download-ticket"
    assert captured["params"] == {"docId": "doc_10001"}
    assert result["ticket"] == "tk_123"


def test_parse_download_metadata_json():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response({"docId": "doc_10001", "downloadPath": "/tmp/result.json"})

    result = call_tool(
        make_server(handler),
        "parse_download",
        {"docId": "doc_10001", "ticket": "tk_123"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/download"
    assert result["downloadPath"] == "/tmp/result.json"


def test_parse_download_bytes_stream():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, content=b"file-bytes", headers={"Content-Type": "application/octet-stream"})

    result = call_tool(
        make_server(handler),
        "parse_download",
        {"docId": "doc_10001", "ticket": "tk_123"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/download"
    assert result["encoding"] == "base64"
    assert result["format"] == "bytes"


# ---------- 检索 ----------


def test_search_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"answer": "回答", "results": [{"docId": "doc_1", "score": 0.9}]})

    result = call_tool(
        make_server(handler),
        "search_query",
        {"query": "产品能力？", "kbId": "kb_10001", "kbIds": ["kb_10001", "kb_10002"]},
    )
    assert captured["path"] == "/api/v1/knowledge-search/universal-search"
    assert captured["body"]["kbId"] == "kb_10001"
    assert captured["body"]["kbIds"] == ["kb_10001", "kb_10002"]
    assert result["answer"] == "回答"
    assert result["results"][0]["docId"] == "doc_1"


def test_parse_direct():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(
            {
                "taskId": "parse_10001",
                "docId": "pdoc_10001",
                "taskStatus": "success",
                "executeMode": "sync",
                "resultInline": {"fileData": {"totalPage": 12}},
            }
        )

    result = call_tool(
        make_server(handler),
        "parse_direct",
        {"source": {"type": "url", "url": "https://example.com/a.pdf"}, "executeMode": "sync"},
    )
    assert captured["path"] == "/api/v1/knowledge-documents/parse-direct"
    assert captured["body"]["source"] == {"type": "url", "url": "https://example.com/a.pdf"}
    assert captured["body"]["executeMode"] == "sync"
    assert result["docId"] == "pdoc_10001"


def test_deep_search():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"answer": "结论", "total": 1, "citations": [], "usedQueries": [], "steps": []})

    result = call_tool(
        make_server(handler),
        "deep_search",
        {"query": "对比白皮书", "kbId": "kb_10001", "topK": 8},
    )
    assert captured["path"] == "/api/v1/knowledge-search/deep-search"
    assert captured["body"]["kbId"] == "kb_10001"
    assert result["answer"] == "结论"


def test_search_query_invalid_kb_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response({})

    server = make_server(handler)
    with pytest.raises(Exception):
        call_tool(server, "search_query", {"query": "q", "kbIds": {"not": "list"}})


# ---------- 系统 ----------


def test_sys_catalog():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"apiCatalog": []})

    result = call_tool(make_server(handler), "sys_catalog")
    assert captured["path"] == "/api/catalog"
    assert "catalog" in result


def test_sys_error_codes():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"errorCodes": []})

    result = call_tool(make_server(handler), "sys_error_codes")
    assert captured["path"] == "/api/error-codes"
    assert "errorCodes" in result


# ---------- 工具清单完整性 ----------


def test_tool_inventory_matches_contract():
    EXPECTED = {
        "kb_create",
        "kb_update",
        "kb_query",
        "kb_get",
        "wiki_tree",
        "wiki_page",
        "wiki_search",
        "graph_stat",
        "graph_nodes",
        "graph_edges",
        "graph_neighbors",
        "graph_export",
        "doc_ingest",
        "doc_ingest_and_parse",
        "doc_get",
        "parse_start",
        "parse_direct",
        "parse_query",
        "parse_issue_ticket",
        "parse_download",
        "search_query",
        "deep_search",
        "sys_catalog",
        "sys_error_codes",
    }
    server = make_server(lambda request: ok_response({}))
    assert asyncio.run(list_tool_names(server)) == EXPECTED
