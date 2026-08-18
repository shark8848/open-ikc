from __future__ import annotations

import re
from typing import Any

from app.core.error_codes import CommonErrorCodes, KnowledgeBaseException
from app.core.responses import wiki_page_response, wiki_search_response, wiki_tree_response
from app.services.knowledge_base import KnowledgeBaseService
from app.services.wiki_store import WikiPageRecord, WikiPageStore, build_document_pages


def _snippet(markdown: str, length: int = 80) -> str:
    """生成命中摘要：取正文首行并去除 Markdown 标记。"""
    first_line = markdown.strip().splitlines()[0] if markdown.strip() else ""
    plain = re.sub(r"[#*`>\[\]()]+", "", first_line).strip()
    return plain[:length]


class WikiService:
    """Wiki 库（专业库形态）库级视图与加工联动。

    - 只读视图：tree / page / search，均要求 kbMode=wiki；
    - 加工联动：build_from_doc 由解析成功链路调用，按库 wikiConfig 建页并做跨文档合并。
    """

    @staticmethod
    def _require_wiki_record(kb_id: str):
        record = KnowledgeBaseService.get_or_raise(kb_id)
        if record.kb_mode != "wiki":
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {
                    "field": "kbMode",
                    "reason": f"Wiki 接口仅支持 kbMode=wiki 的知识库（当前：{record.kb_mode}）",
                },
            )
        return record

    @staticmethod
    def tree(
        kb_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        record = WikiService._require_wiki_record(kb_id)
        roots = WikiPageStore.build_tree(kb_id)
        total = len(roots)
        start = (page - 1) * page_size
        tree_slice = roots[start : start + page_size]
        return wiki_tree_response(
            kb_id=record.kb_id,
            total=total,
            page=page,
            page_size=page_size,
            tree=tree_slice,
        )

    @staticmethod
    def page(
        kb_id: str,
        *,
        page_id: str,
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        record = WikiService._require_wiki_record(kb_id)
        page_record = WikiPageStore.get(page_id)
        if page_record is None or page_record.kb_id != kb_id:
            raise KnowledgeBaseException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "pageId", "reason": f"Wiki 页面不存在：{page_id}"},
            )
        return wiki_page_response(kb_id=record.kb_id, page_record=page_record)

    @staticmethod
    def search(
        kb_id: str,
        *,
        q: str = "",
        tag: str = "",
        owner_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        record = WikiService._require_wiki_record(kb_id)
        hits = WikiPageStore.search(kb_id, q, tag.strip() or None)
        items = [
            {
                "pageId": page_record.page_id,
                "title": page_record.title,
                "snippet": _snippet(page_record.markdown),
                "tags": list(page_record.tags),
                "score": score,
            }
            for page_record, score in hits
        ]
        return wiki_search_response(kb_id=record.kb_id, q=q, total=len(items), items=items)

    @staticmethod
    def build_from_doc(
        kb_id: str,
        doc_id: str,
        title: str,
        tags: list[str] | None = None,
        wiki_config: dict[str, Any] | None = None,
    ) -> list[WikiPageRecord]:
        """解析成功后按库 wikiConfig 建页：切页 → 稳定键对齐 → dedup 合并 → 增量废弃。

        供 ParseService 联动调用；页面正文为占位文本，真实解析引擎接入后由引擎填充。
        """
        config = dict(wiki_config or {})
        records = build_document_pages(
            kb_id=kb_id,
            doc_id=doc_id,
            title=title,
            tags=tags,
            config=config,
        )
        dedup = config.get("dedup") or "merge"
        saved = [WikiPageStore.save(record, dedup=dedup) for record in records]
        WikiPageStore.deprecate_doc_pages(kb_id, doc_id, {record.stable_key for record in records})
        return saved
