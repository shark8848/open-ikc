from __future__ import annotations

"""MCP 工具测试：直接调用 build_server 产出的工具函数（不跑 stdio 传输），
用 httpx.MockTransport 断言请求路径/body 与返回 JSON。"""

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


def make_tools(handler):
    """返回 (server, tools_dict) —— tools_dict 收集所有已注册工具。"""
    server = build_server(make_client(handler))
    tools = {tool.name: tool.fn for tool in server._tool_manager.list_tools()}
    return server, tools


# ---------- 知识库 ----------


def test_kb_create():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"kbId": "kb_10001", "kbName": "测试库"})

    _, tools = make_tools(handler)
    result = tools["kb_create"](kbName="测试库", kbType="personal")
    assert captured["path"] == "/api/v1/knowledge-bases/create"
    assert captured["body"]["kbName"] == "测试库"
    assert result["kbId"] == "kb_10001"


def test_kb_update():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"kbId": "kb_10001", "kbName": "新名称"})

    _, tools = make_tools(handler)
    result = tools["kb_update"](kbId="kb_10001", kbName="新名称")
    assert captured["body"]["kbId"] == "kb_10001"
    assert captured["body"]["kbName"] == "新名称"
    assert result["kbName"] == "新名称"


def test_kb_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"total": 1, "page": 1, "pageSize": 20, "items": []})

    _, tools = make_tools(handler)
    result = tools["kb_query"](page=1, pageSize=10, keyword="知识")
    assert captured["path"] == "/api/v1/knowledge-bases/query"
    assert captured["body"] == {"page": 1, "pageSize": 10, "keyword": "知识"}
    assert result["total"] == 1


def test_kb_get():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response({"kbId": "kb_10001", "kbName": "测试库"})

    _, tools = make_tools(handler)
    result = tools["kb_get"](kbId="kb_10001")
    assert captured["path"] == "/api/v1/knowledge-bases/kb_10001"
    assert result["kbId"] == "kb_10001"


# ---------- 文档 ----------


def test_doc_ingest():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"ingestTaskId": "ing_10001", "docId": "doc_10001"})

    _, tools = make_tools(handler)
    result = tools["doc_ingest"](
        kbId="kb_10001",
        source='{"type": "url", "url": "https://example.com/a.pdf"}',
        docTitle="示例文档",
    )
    assert captured["path"] == "/api/v1/knowledge-documents/ingest"
    assert captured["body"]["source"]["type"] == "url"
    assert captured["body"]["docTitle"] == "示例文档"
    assert result["docId"] == "doc_10001"


def test_doc_ingest_invalid_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response({})

    _, tools = make_tools(handler)
    with pytest.raises(ValueError, match="tags"):
        tools["doc_ingest"](kbId="kb_1", source='{"type":"url","url":"x"}', tags='{"not": "list"}')


def test_doc_ingest_and_parse():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"ingestTaskId": "ing_1", "parseTaskId": "parse_1", "executeMode": "async"})

    _, tools = make_tools(handler)
    result = tools["doc_ingest_and_parse"](
        kbId="kb_10001",
        source='{"type": "url", "url": "https://example.com/a.pdf"}',
        executeMode="async",
    )
    assert captured["path"] == "/api/v1/knowledge-documents/ingest-and-parse"
    assert captured["body"]["executeMode"] == "async"
    assert result["parseTaskId"] == "parse_1"


def test_doc_get():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response({"docId": "doc_10001", "docTitle": "示例"})

    _, tools = make_tools(handler)
    result = tools["doc_get"](docId="doc_10001")
    assert captured["path"] == "/api/v1/knowledge-documents/doc_10001"
    assert result["docId"] == "doc_10001"


# ---------- 解析 ----------


def test_parse_start():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response({"taskId": "parse_10001", "taskStatus": "QUEUED"})

    _, tools = make_tools(handler)
    result = tools["parse_start"](kbId="kb_10001", docId="doc_10001")
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

    _, tools = make_tools(handler)
    result = tools["parse_query"](docId="doc_10001")
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/query"
    assert captured["params"] == {"docId": "doc_10001"}
    assert result["parseStatus"] == "SUCCEEDED"


def test_parse_issue_ticket():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return ok_response({"ticket": "tk_123", "expireAt": "2026-08-11T00:00:00Z"})

    _, tools = make_tools(handler)
    result = tools["parse_issue_ticket"](docId="doc_10001")
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/issue-download-ticket"
    assert captured["params"] == {"docId": "doc_10001"}
    assert result["ticket"] == "tk_123"


def test_parse_download_metadata_json():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return ok_response({"docId": "doc_10001", "downloadPath": "/tmp/result.json"})

    _, tools = make_tools(handler)
    result = tools["parse_download"](docId="doc_10001", ticket="tk_123")
    assert captured["path"] == "/api/v1/knowledge-documents/parse-result/download"
    assert result["downloadPath"] == "/tmp/result.json"


def test_parse_download_bytes_stream():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, content=b"file-bytes", headers={"Content-Type": "application/octet-stream"})

    _, tools = make_tools(handler)
    result = tools["parse_download"](docId="doc_10001", ticket="tk_123")
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

    _, tools = make_tools(handler)
    result = tools["search_query"](
        query="产品能力？",
        kbId="kb_10001",
        kbIds='["kb_10001", "kb_10002"]',
    )
    assert captured["path"] == "/api/v1/knowledge-search/query"
    assert captured["body"]["kbId"] == "kb_10001"
    assert captured["body"]["kbIds"] == ["kb_10001", "kb_10002"]
    assert result["answer"] == "回答"
    assert result["results"][0]["docId"] == "doc_1"


def test_search_query_invalid_kb_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response({})

    _, tools = make_tools(handler)
    with pytest.raises(ValueError, match="kbIds"):
        tools["search_query"](query="q", kbIds='{"not": "list"}')


# ---------- 系统 ----------


def test_sys_catalog():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"apiCatalog": []})

    _, tools = make_tools(handler)
    result = tools["sys_catalog"]()
    assert captured["path"] == "/api/catalog"
    assert "catalog" in result


def test_sys_error_codes():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"errorCodes": []})

    _, tools = make_tools(handler)
    result = tools["sys_error_codes"]()
    assert captured["path"] == "/api/error-codes"
    assert "errorCodes" in result


# ---------- 工具清单完整性 ----------


def test_tool_inventory_matches_contract():
    EXPECTED = {
        "kb_create",
        "kb_update",
        "kb_query",
        "kb_get",
        "doc_ingest",
        "doc_ingest_and_parse",
        "doc_get",
        "parse_start",
        "parse_query",
        "parse_issue_ticket",
        "parse_download",
        "search_query",
        "sys_catalog",
        "sys_error_codes",
    }
    _, tools = make_tools(lambda request: ok_response({}))
    assert set(tools) == EXPECTED
