from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


WIKI_STATUS = {"ACTIVE": "active", "DEPRECATED": "deprecated"}
DEDUP_MODES = ("merge", "overwrite", "skip")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_title(title: str) -> str:
    """标题规范化：去除空白与标点、统一小写，用于稳定键派生与同名合并。"""
    normalized = re.sub(r"[\W_]+", "", title.strip().lower())
    return normalized or "untitled"


def page_id(kb_id: str, stable_key: str) -> str:
    """稳定页面 ID：wiki_ + sha1(kbId:stableKey) 前 12 位，跨文档/跨构建稳定。"""
    digest = hashlib.sha1(f"{kb_id}:{stable_key}".encode("utf-8")).hexdigest()
    return f"wiki_{digest[:12]}"


@dataclass(frozen=True, slots=True)
class WikiPageRecord:
    page_id: str
    kb_id: str
    doc_id: str
    title: str
    level: int
    parent_page_id: str
    stable_key: str
    fields: dict[str, Any]
    tags: list[str]
    markdown: str
    links: list[dict[str, str]]
    source_docs: list[str]
    status: str
    created_at: str
    updated_at: str


class WikiPageStore:
    """进程内 Wiki 库页面存储（占位实现）。

    仅负责原子读写、按稳定键合并与树/检索派生，业务校验与异常语义由 service 层承担。
    """

    _lock = threading.Lock()
    _pages: dict[str, WikiPageRecord] = {}

    @classmethod
    def save(cls, record: WikiPageRecord, *, dedup: str = "merge") -> WikiPageRecord:
        """按稳定键写入页面；dedup 决定同名（同 kbId+stableKey）策略。"""
        with cls._lock:
            existing = cls._find_by_key_locked(record.kb_id, record.stable_key)
            if existing is not None:
                if dedup == "skip":
                    return existing
                if dedup == "overwrite":
                    merged = replace(record, created_at=existing.created_at)
                    cls._pages[record.page_id] = merged
                    return merged
                # merge：保留稳定键页面，合并来源证据与链接，正文以新内容为准
                merged = replace(
                    record,
                    created_at=existing.created_at,
                    source_docs=sorted(set(existing.source_docs) | set(record.source_docs)),
                    links=sorted({(l["title"], l.get("pageId", "")) for l in existing.links + record.links}, key=lambda x: x[0]),
                )
                merged = replace(
                    merged,
                    links=[{"title": title, "pageId": page_id} for title, page_id in merged.links],
                )
                cls._pages[record.page_id] = merged
                return merged
            cls._pages[record.page_id] = record
            return record

    @classmethod
    def get(cls, page_id: str) -> WikiPageRecord | None:
        with cls._lock:
            return cls._pages.get(page_id)

    @classmethod
    def list_pages(cls, kb_id: str) -> list[WikiPageRecord]:
        with cls._lock:
            return [
                record
                for record in cls._pages.values()
                if record.kb_id == kb_id and record.status == WIKI_STATUS["ACTIVE"]
            ]

    @classmethod
    def build_tree(cls, kb_id: str) -> list[dict[str, Any]]:
        """构建库级页面树：按 parentPageId 挂接子页面，无父页面者为根节点。"""
        records = cls.list_pages(kb_id)
        nodes: dict[str, dict[str, Any]] = {}
        for record in records:
            nodes[record.page_id] = {
                "pageId": record.page_id,
                "title": record.title,
                "level": record.level,
                "parentPageId": record.parent_page_id,
                "children": [],
            }
        roots: list[dict[str, Any]] = []
        for record in records:
            node = nodes[record.page_id]
            parent = nodes.get(record.parent_page_id)
            if parent is not None and parent is not node:
                parent["children"].append(node)
            else:
                roots.append(node)
        return roots

    @classmethod
    def search(
        cls,
        kb_id: str,
        q: str,
        tag: str | None = None,
        *,
        limit: int = 20,
    ) -> list[tuple[WikiPageRecord, float]]:
        """库内页面检索：标题命中加权 > 正文命中；可附加 tag 过滤。q 为空时返回全部页面。"""
        q_raw = (q or "").strip()
        q_norm = normalize_title(q_raw)
        hits: list[tuple[WikiPageRecord, float]] = []
        for record in cls.list_pages(kb_id):
            if tag and tag not in record.tags:
                continue
            title_norm = normalize_title(record.title)
            content_norm = normalize_title(re.sub(r"[\s#*`>\-\n]+", "", record.markdown))
            if q_raw:
                score = 0.0
                if q_norm in title_norm:
                    score += 10.0
                if q_norm in content_norm:
                    score += 3.0
                for link in record.links:
                    if q_norm in normalize_title(link.get("title", "")):
                        score += 1.0
                if score <= 0:
                    continue
            else:
                score = 1.0
            hits.append((record, score))
        hits.sort(key=lambda item: (-item[1], item[0].title))
        return hits[:limit]

    @classmethod
    def deprecate_doc_pages(cls, kb_id: str, doc_id: str, active_stable_keys: set[str]) -> int:
        """增量废弃：仅由该文档贡献、且本次构建未再出现的页面标记 deprecated（不物理删除，保审计）。"""
        deprecated = 0
        with cls._lock:
            for record in list(cls._pages.values()):
                if record.kb_id != kb_id or doc_id not in record.source_docs:
                    continue
                if record.stable_key in active_stable_keys:
                    continue
                if set(record.source_docs) != {doc_id}:
                    continue
                if record.status == WIKI_STATUS["ACTIVE"]:
                    cls._pages[record.page_id] = replace(record, status=WIKI_STATUS["DEPRECATED"], updated_at=_now_iso())
                    deprecated += 1
        return deprecated

    @classmethod
    def _find_by_key_locked(cls, kb_id: str, stable_key: str, *, exclude_page_id: str | None = None) -> WikiPageRecord | None:
        """在调用方已持有 _lock 的前提下按稳定键查找（避免不可重入锁死锁）。"""
        for record in cls._pages.values():
            if record.kb_id == kb_id and record.stable_key == stable_key:
                if exclude_page_id is not None and record.page_id == exclude_page_id:
                    continue
                return record
        return None

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._pages.clear()


def build_document_pages(
    *,
    kb_id: str,
    doc_id: str,
    title: str,
    tags: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> list[WikiPageRecord]:
    """按 wikiConfig 生成文档页面（占位实现：当前按单页生成，待解析引擎接入后按 granularity 切页）。

    页面正文为占位文本，fields 为空；链路（建页→合并→树→搜索）完整可验证。
    """
    config = dict(config or {})
    granularity = config.get("granularity") or "auto"
    title = title.strip() or "未命名文档"
    stable_key = normalize_title(title)
    now = _now_iso()
    record = WikiPageRecord(
        page_id=page_id(kb_id, stable_key),
        kb_id=kb_id,
        doc_id=doc_id,
        title=title,
        level=1,
        parent_page_id="",
        stable_key=stable_key,
        fields=dict(config.get("fields") or {}),
        tags=list(tags or []),
        markdown=f"## {title}\n\n（占位页面：由文档 {doc_id} 加工生成，granularity={granularity}；待解析引擎接入后填充真实正文与字段。）",
        links=[],
        source_docs=[doc_id],
        status=WIKI_STATUS["ACTIVE"],
        created_at=now,
        updated_at=now,
    )
    return [record]
