from __future__ import annotations

from datetime import datetime, timezone

from app.core.error_codes import (
    CommonErrorCodes,
    KnowledgeBaseException,
    SearchException,
)
from app.core.responses import search_query_response
from app.services.knowledge_base import KnowledgeBaseService
from app.services.search_store import SearchIndexStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _resolve_kb_ids(payload) -> list[str]:
    values: list[str] = []
    if payload.kbId.strip():
        values.append(payload.kbId.strip())
    for item in payload.kbIds:
        cleaned = item.strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _hit_to_item(hit, *, with_citation: bool) -> dict:
    return {
        "docId": hit.doc_id,
        "docTitle": hit.doc_title,
        "score": hit.score,
        "snippet": hit.snippet,
        "citation": hit.citation if with_citation else {},
    }


def _placeholder_answer(query: str, results: list) -> str:
    """问答模式占位回答：真实问答引擎落地前引用最高分证据生成说明性回答。"""
    if not results:
        return "未检索到相关证据。"
    top = results[0]
    return (
        f"针对“{query}”，基于检索到的证据（文档《{top.doc_title or top.doc_id}》，"
        f"相关度 {top.score:.2f}）作答；回答引擎接入后在此生成真实答案。"
    )


class SearchService:
    @staticmethod
    def query(payload, *, owner_id: str = "", tenant_id: str = "") -> dict:
        kb_ids = _resolve_kb_ids(payload)
        if not kb_ids:
            raise SearchException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "kbIds", "reason": "kbId / kbIds 至少提供一个目标知识库"},
            )

        # 知识库存在性与数据范围校验：逐库校验，与 KnowledgeBaseService._visible_records 收敛逻辑对齐
        for kb_id in kb_ids:
            kb_record = KnowledgeBaseService.get_or_raise(kb_id)
            if kb_record.kb_type == "personal":
                if kb_record.owner_id and kb_record.owner_id != owner_id:
                    raise KnowledgeBaseException(
                        CommonErrorCodes.FORBIDDEN,
                        {"field": "kbId", "reason": f"个人知识库仅创建者可检索：{kb_id}"},
                    )
            elif kb_record.kb_type == "team":
                team_id = payload.teamId.strip()
                if not team_id or kb_record.team_id != team_id:
                    raise KnowledgeBaseException(
                        CommonErrorCodes.FORBIDDEN,
                        {"field": "teamId", "reason": f"团队知识库需在 teamId 指定的团队范围内检索：{kb_id}"},
                    )
            else:  # enterprise
                org_scope = payload.orgId.strip() or tenant_id.strip()
                if not org_scope or kb_record.org_id != org_scope:
                    raise KnowledgeBaseException(
                        CommonErrorCodes.FORBIDDEN,
                        {"field": "orgId", "reason": f"企业知识库需在 orgId / 调用主体组织范围内检索：{kb_id}"},
                    )

        top_k = payload.topK or 5
        mode = (payload.mode or "qa").strip().lower() or "qa"
        with_citation = bool(payload.withCitation)

        hits = SearchIndexStore.search(
            query=(payload.query or "").strip(),
            kb_ids=kb_ids,
            filters=dict(payload.filters or {}),
            top_k=top_k,
        )

        items = [_hit_to_item(hit, with_citation=with_citation) for hit in hits]
        answer = _placeholder_answer(payload.query or "", hits) if mode == "qa" else ""
        return search_query_response(
            answer=answer,
            total=len(hits),
            results=items,
        )
