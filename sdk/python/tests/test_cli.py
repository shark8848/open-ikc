from __future__ import annotations

"""CLI 测试：用 typer.testing.CliRunner + 注入 mock client 验证子命令解析、--json 输出与退出码。"""

import json

import httpx
import pytest
from typer.testing import CliRunner

from open_ikc_sdk import OpenIKCClient
from open_ikc_sdk.cli import app, init_app
from open_ikc_sdk.errors import (
    OpenIKCForbiddenError,
    OpenIKCNotFoundError,
    OpenIKCNotImplementedError,
    OpenIKCUnauthorizedError,
)

runner = CliRunner()


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


@pytest.fixture(autouse=True)
def _reset_client():
    """每个用例结束后重置注入的 client，避免跨用例串扰。"""
    yield
    init_app(client=None)


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_kb_create_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/create"
        body = json.loads(request.content or b"{}")
        assert body["kbName"] == "测试库"
        return ok_response({"kbId": "kb_10001", "kbName": "测试库"})

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "kb-create", "测试库"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kbId"] == "kb_10001"


def test_kb_list_table_output():
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response(
            {
                "total": 1,
                "page": 1,
                "pageSize": 20,
                "items": [{"kbId": "kb_10001", "kbName": "测试库", "kbType": "personal", "visibility": "private"}],
            }
        )

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["kb-list"])
    assert result.exit_code == 0, result.output
    assert "kb_10001" in result.output
    assert "测试库" in result.output
    assert "共 1 条" in result.output


def test_kb_get_uses_path_param():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001"
        return ok_response({"kbId": "kb_10001", "kbName": "测试库"})

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "kb-get", "kb_10001"])
    assert result.exit_code == 0
    assert json.loads(result.output)["kbId"] == "kb_10001"


def test_wiki_tree_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/wiki/tree"
        assert dict(request.url.params) == {"page": "2", "pageSize": "10"}
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "wiki",
                "total": 1,
                "page": 2,
                "pageSize": 10,
                "tree": [
                    {
                        "pageId": "wiki_abc123",
                        "title": "首页",
                        "level": 1,
                        "parentPageId": "",
                        "children": [],
                    }
                ],
            }
        )

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "wiki-tree", "kb_10001", "--page", "2", "--page-size", "10"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["tree"][0]["title"] == "首页"


def test_wiki_page_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/wiki/page"
        assert dict(request.url.params) == {"pageId": "wiki_abc123"}
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "wiki",
                "page": {
                    "pageId": "wiki_abc123",
                    "title": "首页",
                    "level": 1,
                    "parentPageId": "",
                    "markdown": "# 首页\n正文",
                    "fields": {},
                    "tags": [],
                    "links": [],
                    "sourceDocs": [],
                    "status": "active",
                    "createdAt": "2026-08-01T00:00:00Z",
                    "updatedAt": "2026-08-02T00:00:00Z",
                },
            }
        )

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "wiki-page", "kb_10001", "--page-id", "wiki_abc123"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["page"]["markdown"].startswith("# 首页")


def test_wiki_search_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/wiki/search"
        assert dict(request.url.params) == {"q": "产品", "tag": "指南"}
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "wiki",
                "q": "产品",
                "total": 1,
                "items": [{"pageId": "wiki_abc123", "title": "产品首页", "snippet": "说明", "tags": ["指南"], "score": 0.9}],
            }
        )

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "wiki-search", "kb_10001", "--q", "产品", "--tag", "指南"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["items"][0]["pageId"] == "wiki_abc123"


def test_graph_stat_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/graph/stat"
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

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "graph-stat", "kb_10001"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["nodeCount"] == 3


def test_graph_nodes_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/graph/nodes"
        assert dict(request.url.params) == {"entityType": "person", "page": "2", "pageSize": "10"}
        return ok_response(
            {
                "kbId": "kb_10001",
                "kbMode": "graph",
                "total": 1,
                "page": 2,
                "pageSize": 10,
                "items": [
                    {
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
                    }
                ],
            }
        )

    init_app(client=make_client(handler))
    result = runner.invoke(
        app,
        ["--json", "graph-nodes", "kb_10001", "--entity-type", "person", "--page", "2", "--page-size", "10"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["items"][0]["name"] == "张三"


def test_graph_edges_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/graph/edges"
        assert dict(request.url.params) == {"relationType": "works_at", "page": "1", "pageSize": "20"}
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

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "graph-edges", "kb_10001", "--relation-type", "works_at"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["items"][0]["relationId"] == "rel_abc123"


def test_graph_neighbors_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/graph/neighbors"
        assert dict(request.url.params) == {"entityId": "ent_abc123", "depth": "1"}
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
                "edges": [],
            }
        )

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "graph-neighbors", "kb_10001", "--entity-id", "ent_abc123"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["center"]["name"] == "张三"


def test_graph_export_to_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb_10001/graph/export"
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

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["graph-export", "kb_10001", "--to-path", "/tmp/ikc_graph_export.jsonl"])
    assert result.exit_code == 0, result.output
    assert "已导出 2 条记录" in result.output
    import os

    assert os.path.exists("/tmp/ikc_graph_export.jsonl")
    with open("/tmp/ikc_graph_export.jsonl", "r", encoding="utf-8") as handle:
        assert handle.read() == '{"type":"entity","entityId":"ent_abc123"}\n{"type":"relation","relationId":"rel_abc123"}'
    os.remove("/tmp/ikc_graph_export.jsonl")


def test_doc_ingest_json_source():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-documents/ingest"
        body = json.loads(request.content or b"{}")
        assert body["source"] == {"type": "url", "url": "https://example.com/a.pdf"}
        return ok_response({"ingestTaskId": "ing_1", "docId": "doc_1"})

    init_app(client=make_client(handler))
    result = runner.invoke(
        app,
        ["--json", "doc-ingest", "kb_10001", '{"type": "url", "url": "https://example.com/a.pdf"}'],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["docId"] == "doc_1"


def test_search_query_output():
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response({"answer": "核心能力说明", "results": [{"docId": "doc_1", "score": 0.9, "snippet": "片段"}]})

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["search-query", "--query", "产品能力", "--kb-id", "kb_10001"])
    assert result.exit_code == 0, result.output
    assert "核心能力说明" in result.output
    assert "doc_1" in result.output


def test_sys_catalog():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/catalog"
        return httpx.Response(200, json={"apiCatalog": []})

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["--json", "sys-catalog"])
    assert result.exit_code == 0
    assert "apiCatalog" in result.output


# ---------- 错误与退出码 ----------


def _client_with_error(exception: BaseException) -> OpenIKCClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    return make_client(handler)


def test_unauthorized_exit_code_2():
    init_app(client=_client_with_error(OpenIKCUnauthorizedError("100401 未认证", err_code="100401", err_msg="未认证")))
    result = runner.invoke(app, ["kb-list"])
    assert result.exit_code == 2


def test_forbidden_exit_code_3():
    init_app(client=_client_with_error(OpenIKCForbiddenError("100403 无权限", err_code="100403", err_msg="无权限")))
    result = runner.invoke(app, ["kb-list"])
    assert result.exit_code == 3


def test_not_found_exit_code_4():
    init_app(client=_client_with_error(OpenIKCNotFoundError("100404 不存在", err_code="100404", err_msg="不存在")))
    result = runner.invoke(app, ["kb-get", "kb_xxx"])
    assert result.exit_code == 4


def test_not_implemented_exit_code_5():
    init_app(
        client=_client_with_error(
            OpenIKCNotImplementedError("501001 未实现", err_code="501001", err_msg="接口已预占位")
        )
    )
    result = runner.invoke(app, ["kb-list"])
    assert result.exit_code == 5


def test_connection_error_exit_code_6():
    init_app(client=_client_with_error(httpx.ConnectError("连接失败")))
    result = runner.invoke(app, ["kb-list"])
    assert result.exit_code == 6


def test_unknown_error_exit_code_1():
    init_app(client=_client_with_error(RuntimeError("未知错误")))
    result = runner.invoke(app, ["kb-list"])
    assert result.exit_code == 1


def test_parse_download_to_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-documents/parse-result/download"
        return httpx.Response(200, content=b"file-content", headers={"Content-Type": "application/octet-stream"})

    init_app(client=make_client(handler))
    result = runner.invoke(app, ["parse-download", "doc_1", "tk_123", "--to-path", "/tmp/ikc_test_dl.bin"])
    assert result.exit_code == 0, result.output
    assert "已下载" in result.output
    import os

    assert os.path.exists("/tmp/ikc_test_dl.bin")
    with open("/tmp/ikc_test_dl.bin", "rb") as handle:
        assert handle.read() == b"file-content"
    os.remove("/tmp/ikc_test_dl.bin")
