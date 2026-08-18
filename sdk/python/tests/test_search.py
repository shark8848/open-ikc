from __future__ import annotations

import json

import httpx
import pytest

from open_ikc_sdk import OpenIKCClient
from open_ikc_sdk.errors import OpenIKCNotImplementedError

SEARCH_DATA = {
    "answer": "核心能力包括统一知识接入、语义检索和权限治理。",
    "results": [
        {
            "docId": "doc_90001",
            "score": 0.92,
            "snippet": "平台提供统一知识接入...",
            "citation": {"page": 3, "position": [82, 120, 512, 220]},
        }
    ],
}


def ok_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"errCode": "000000", "errMsg": "success", "traceId": "123", "data": data})


def make_client(handler) -> OpenIKCClient:
    return OpenIKCClient(
        "http://platform.test",
        token="t",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1),
    )


def test_search_sends_body_and_parses_result():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(SEARCH_DATA)

    client = make_client(handler)
    result = client.search.query(
        query="产品白皮书的核心能力？",
        kbId="kb_10001",
        kbIds=["kb_10001", "kb_10002"],
        ownerId="u100",
        orgPath="/集团/销售中心/华东",
    )
    assert captured["path"] == "/api/v1/knowledge-search/universal-search"
    assert captured["body"] == {
        "query": "产品白皮书的核心能力？",
        "kbId": "kb_10001",
        "kbIds": ["kb_10001", "kb_10002"],
        "ownerId": "u100",
        "orgPath": "/集团/销售中心/华东",
        "mode": "qa",
        "searchType": "hybrid",
        "relNum": 0,
        "useRerank": False,
        "topK": 5,
        "withCitation": True,
        "isOptimize": False,
    }
    assert result.answer.startswith("核心能力")
    assert result.results[0].docId == "doc_90001"
    assert result.results[0].score == 0.92
    assert result.results[0].citation["page"] == 3
    client.close()


def test_search_empty_body_when_no_filters():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(SEARCH_DATA)

    client = make_client(handler)
    client.search.query()
    assert captured["body"] == {
        "mode": "qa",
        "searchType": "hybrid",
        "relNum": 0,
        "useRerank": False,
        "topK": 5,
        "withCitation": True,
        "isOptimize": False,
    }
    client.close()


def test_search_platform_placeholder_raises_not_implemented():
    body = {"errCode": "501001", "errMsg": "接口已预占位，待实现", "traceId": "123", "data": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = make_client(handler)
    with pytest.raises(OpenIKCNotImplementedError):
        client.search.query(query="任意问题")
    client.close()


DEEP_SEARCH_DATA = {
    "answer": "结论：平台具备统一检索能力。",
    "total": 2,
    "citations": [
        {"docId": "doc_90001", "docTitle": "白皮书", "score": 0.9, "snippet": "统一知识接入", "position": [3], "page": 1}
    ],
    "usedQueries": ["对比检索能力"],
    "steps": [{"stage": "plan", "query": "对比检索能力", "docsCount": 2, "elapsedMs": 12.5}],
}


def test_deep_search_sends_body_and_parses_result():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content or b"{}")
        return ok_response(DEEP_SEARCH_DATA)

    client = make_client(handler)
    result = client.search.deep_search(
        query="对比 2025 与 2026 白皮书",
        kbId="kb_10001",
        searchType="hybrid",
        topK=8,
        useRerank=True,
        sessionId="s1",
        deepSearch={"maxSteps": 5},
        responseSpec={"include": ["answer", "citations"]},
    )
    assert captured["path"] == "/api/v1/knowledge-search/deep-search"
    assert captured["body"] == {
        "query": "对比 2025 与 2026 白皮书",
        "kbId": "kb_10001",
        "searchType": "hybrid",
        "topK": 8,
        "useRerank": True,
        "sessionId": "s1",
        "deepSearch": {"maxSteps": 5},
        "responseSpec": {"include": ["answer", "citations"]},
    }
    assert result.answer.startswith("结论")
    assert result.total == 2
    assert result.citations[0].docId == "doc_90001"
    assert result.usedQueries == ["对比检索能力"]
    assert result.steps[0].stage == "plan"
    client.close()
