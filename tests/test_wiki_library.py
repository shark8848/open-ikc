from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.catalog import API_CATALOG
from app.main import app
from app.services.document_store import DocumentStore
from app.services.knowledge_base_store import KnowledgeBaseStore
from app.services.parse_store import ParseTaskStore, ParseTicketStore
from app.services.wiki_store import WikiPageStore

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}
WIKI_CONFIG = {"granularity": "heading", "extractFields": ["负责人", "版本"], "linkMode": "auto", "dedup": "merge"}


@pytest.fixture(autouse=True)
def reset_wiki_stores() -> None:
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    ParseTaskStore.reset()
    ParseTicketStore.reset()
    WikiPageStore.reset()
    yield
    DocumentStore.reset()
    KnowledgeBaseStore.reset()
    ParseTaskStore.reset()
    ParseTicketStore.reset()
    WikiPageStore.reset()


def _create_wiki_kb(title: str = "Wiki 专业库", **overrides) -> dict:
    payload = {
        "kbName": title,
        "kbType": "personal",
        "teamId": "",
        "orgId": "",
        "kbDesc": "Wiki 库集成测试",
        "bizDomain": "general",
        "visibility": "private",
        "metadataSchema": [],
        "kbMode": "wiki",
        "wikiConfig": WIKI_CONFIG,
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


def _wiki_tree(kb_id: str, **params) -> dict:
    response = client.get(f"/api/v1/knowledge-bases/{kb_id}/wiki/tree", params=params, headers=AUTH)
    return response.json()


def _wiki_page(kb_id: str, page_id: str) -> dict:
    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/wiki/page",
        params={"pageId": page_id},
        headers=AUTH,
    )
    return response.json()


def _wiki_search(kb_id: str, **params) -> dict:
    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/wiki/search",
        params=params,
        headers=AUTH,
    )
    return response.json()


def test_wiki_tree_on_text_kb_rejected() -> None:
    kb = _create_text_kb()
    body = _wiki_tree(kb["kbId"])
    assert body["errCode"] == "100001"
    assert body["data"]["field"] == "kbMode"


def test_wiki_tree_empty_on_wiki_kb() -> None:
    kb = _create_wiki_kb()
    body = _wiki_tree(kb["kbId"])
    assert body["errCode"] == "000000"
    data = body["data"]
    assert data["kbId"] == kb["kbId"]
    assert data["kbMode"] == "wiki"
    assert data["total"] == 0
    assert data["tree"] == []


def test_parse_sync_builds_wiki_page_tree() -> None:
    kb = _create_wiki_kb()
    doc = _ingest(kb["kbId"], "产品使用手册")
    _parse_sync(kb["kbId"], doc["docId"])

    tree_body = _wiki_tree(kb["kbId"])
    assert tree_body["errCode"] == "000000"
    tree = tree_body["data"]["tree"]
    assert tree_body["data"]["total"] == 1
    assert tree[0]["title"] == "产品使用手册"
    assert tree[0]["level"] == 1
    assert tree[0]["parentPageId"] == ""

    page_id = tree[0]["pageId"]
    page_body = _wiki_page(kb["kbId"], page_id)
    assert page_body["errCode"] == "000000"
    page = page_body["data"]["page"]
    assert page["pageId"] == page_id
    assert page["status"] == "active"
    assert page["sourceDocs"] == [doc["docId"]]
    assert "占位页面" in page["markdown"]


def test_wiki_page_not_found() -> None:
    kb = _create_wiki_kb()
    body = _wiki_page(kb["kbId"], "wiki_does_not_exist")
    assert body["errCode"] == "100404"
    assert body["data"]["field"] == "pageId"


def test_wiki_search_finds_page_by_title_and_tag() -> None:
    kb = _create_wiki_kb()
    doc = _ingest(kb["kbId"], "请假制度")
    _parse_sync(kb["kbId"], doc["docId"])

    body = _wiki_search(kb["kbId"], q="请假")
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 1
    hit = body["data"]["items"][0]
    assert hit["title"] == "请假制度"
    assert hit["score"] >= 10  # 标题命中加权

    # 无关关键字无命中
    body = _wiki_search(kb["kbId"], q="不存在的词")
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 0


def test_wiki_search_empty_q_returns_all() -> None:
    kb = _create_wiki_kb()
    for title in ("第一章", "第二章"):
        doc = _ingest(kb["kbId"], title)
        _parse_sync(kb["kbId"], doc["docId"])

    body = _wiki_search(kb["kbId"], q="")
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 2


def test_wiki_dedup_merge_across_docs() -> None:
    kb = _create_wiki_kb(wikiConfig={**WIKI_CONFIG, "dedup": "merge"})
    doc1 = _ingest(kb["kbId"], "核心制度")
    doc2 = _ingest(kb["kbId"], "核心制度")
    _parse_sync(kb["kbId"], doc1["docId"])
    _parse_sync(kb["kbId"], doc2["docId"])

    body = _wiki_tree(kb["kbId"])
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 1

    page_id = body["data"]["tree"][0]["pageId"]
    page = _wiki_page(kb["kbId"], page_id)["data"]["page"]
    assert set(page["sourceDocs"]) == {doc1["docId"], doc2["docId"]}


def test_wiki_dedup_overwrite_keeps_single_page() -> None:
    kb = _create_wiki_kb(wikiConfig={**WIKI_CONFIG, "dedup": "overwrite"})
    doc1 = _ingest(kb["kbId"], "同题文档")
    doc2 = _ingest(kb["kbId"], "同题文档")
    _parse_sync(kb["kbId"], doc1["docId"])
    _parse_sync(kb["kbId"], doc2["docId"])

    body = _wiki_tree(kb["kbId"])
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 1
    page_id = body["data"]["tree"][0]["pageId"]
    page = _wiki_page(kb["kbId"], page_id)["data"]["page"]
    assert page["sourceDocs"] == [doc2["docId"]]


def test_wiki_tree_pagination() -> None:
    kb = _create_wiki_kb()
    for title in ("页面一", "页面二", "页面三"):
        doc = _ingest(kb["kbId"], title)
        _parse_sync(kb["kbId"], doc["docId"])

    body = _wiki_tree(kb["kbId"], page=1, pageSize=2)
    assert body["errCode"] == "000000"
    assert body["data"]["total"] == 3
    assert len(body["data"]["tree"]) == 2

    body = _wiki_tree(kb["kbId"], page=2, pageSize=2)
    assert len(body["data"]["tree"]) == 1


def test_wiki_routes_registered_in_catalog() -> None:
    kb_routes = {route["path"] for route in next(item["routes"] for item in API_CATALOG if item["tag"] == "knowledge-base")}
    assert "/api/v1/knowledge-bases/{kb_id}/wiki/tree" in kb_routes
    assert "/api/v1/knowledge-bases/{kb_id}/wiki/page" in kb_routes
    assert "/api/v1/knowledge-bases/{kb_id}/wiki/search" in kb_routes
