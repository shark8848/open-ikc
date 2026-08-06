from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchIndexRecord:
    """进程内检索索引条目（占位实现，后续可替换为向量/倒排索引等真实检索后端）。

    一个条目对应一份文档的一个分块（chunk），`SearchIndexStore` 以 doc_id 为粒度重建。
    """

    doc_id: str
    kb_id: str
    doc_title: str
    chunk_id: str
    content: str
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    owner_id: str = ""
    org_path: str = ""
    page: int = 1
    position: list[int] = field(default_factory=list)
    created_at: str = ""


@dataclass(frozen=True, slots=True)
class SearchHit:
    """一次检索命中的结果条目。"""

    doc_id: str
    doc_title: str
    kb_id: str
    score: float
    snippet: str
    citation: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    """轻量分词：对查询与内容做去空白/小写切分；真实语义检索落地前用关键词命中打分。"""
    cleaned = "".join(ch for ch in (text or "").lower() if ch.isalnum() or ch.isspace())
    return [token for token in cleaned.split() if token]


def _hit_score(query_tokens: list[str], record: SearchIndexRecord) -> float:
    """关键词加权打分：标题命中权重最高，其次 keywords 与 content 命中。"""
    title_tokens = _tokenize(record.doc_title)
    keyword_tokens = _tokenize(" ".join(record.keywords))
    content_tokens = _tokenize(record.content)

    score = 0.0
    for token in query_tokens:
        if token in title_tokens:
            score += 3.0
        if token in keyword_tokens:
            score += 2.0
        if token in content_tokens:
            score += 1.0
    return score


def _build_snippet(record: SearchIndexRecord) -> str:
    content = (record.content or "").strip()
    return (content[:80] + "…") if len(content) > 80 else content


class SearchIndexStore:
    """进程内检索索引（占位实现）。

    仅负责索引写入与关键词检索，业务校验与数据权限判定由 service 层承担。
    真实索引构建/向量检索落地前，由调用方显式注入索引数据（测试直插或后续 ingest/parse 联动）。
    """

    _lock = threading.Lock()
    _records: dict[str, SearchIndexRecord] = {}

    @classmethod
    def index_doc(
        cls,
        *,
        doc_id: str,
        kb_id: str,
        doc_title: str,
        chunks: list[dict[str, Any]],
        keywords: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        owner_id: str = "",
        org_path: str = "",
        created_at: str = "",
    ) -> list[SearchIndexRecord]:
        """按 doc_id 重建索引（同文档多次索引幂等覆盖）。chunks 元素含 content/page/position 等。"""
        records: list[SearchIndexRecord] = []
        with cls._lock:
            cls._records = {
                record.doc_id: record
                for record in cls._records.values()
                if record.doc_id != doc_id
            }
            for index, chunk in enumerate(chunks, start=1):
                record = SearchIndexRecord(
                    doc_id=doc_id,
                    kb_id=kb_id,
                    doc_title=doc_title,
                    chunk_id=f"{doc_id}#{index}",
                    content=str(chunk.get("content") or ""),
                    keywords=list(keywords or []),
                    tags=list(tags or []),
                    metadata=dict(metadata or {}),
                    owner_id=owner_id,
                    org_path=org_path,
                    page=int(chunk.get("page") or 1),
                    position=list(chunk.get("position") or []),
                    created_at=created_at,
                )
                cls._records[record.chunk_id] = record
                records.append(record)
        return records

    @classmethod
    def get_by_doc(cls, doc_id: str) -> list[SearchIndexRecord]:
        with cls._lock:
            return [
                record
                for record in cls._records.values()
                if record.doc_id == doc_id
            ]

    @classmethod
    def search(
        cls,
        query: str,
        kb_ids: list[str],
        *,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        """关键词检索：限定 kb_ids 范围 + 元数据过滤，按分值降序截断 top_k。"""
        tokens = _tokenize(query)
        kb_set = set(kb_ids)
        resolved_filters = dict(filters or {})
        hits: list[SearchHit] = []

        with cls._lock:
            candidates = [
                record
                for record in cls._records.values()
                if record.kb_id in kb_set
            ]
            if resolved_filters:
                candidates = [
                    record
                    for record in candidates
                    if _metadata_matches(record.metadata, resolved_filters)
                ]

            for record in candidates:
                score = _hit_score(tokens, record)
                if score <= 0:
                    continue
                hits.append(
                    SearchHit(
                        doc_id=record.doc_id,
                        doc_title=record.doc_title,
                        kb_id=record.kb_id,
                        score=score,
                        snippet=_build_snippet(record),
                        citation={"page": record.page, "position": list(record.position)},
                        metadata=dict(record.metadata),
                    )
                )

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[: max(top_k, 1)]

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._records.clear()


def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        if metadata.get(key) != expected:
            return False
    return True
