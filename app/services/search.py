from __future__ import annotations

from typing import Any

from app.core.error_codes import (
    CommonErrorCodes,
    KnowledgeBaseException,
    SearchErrorCodes,
    SearchException,
)
from app.core.responses import deep_search_query_response, search_query_response
from app.core.trace import current_trace_id
from app.services import search_client
from app.services.knowledge_base import KnowledgeBaseService
from app.services.search_store import SearchIndexStore

DEEP_SEARCH_QA_NOTE = "普通检索不生成回答，如需带引用回答请调用深度检索接口 /api/v1/knowledge-search/deep-search。"


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
    """进程内占位后端的问答回答：真实检索后端接入后由下游生成回答。"""
    if not results:
        return "未检索到相关证据。"
    top = results[0]
    return (
        f"针对“{query}”，基于检索到的证据（文档《{top.doc_title or top.doc_id}》，"
        f"相关度 {top.score:.2f}）作答；回答引擎接入后在此生成真实答案。"
    )


def _snippet(text: str, max_len: int = 160) -> str:
    content = (text or "").strip()
    return (content[:max_len] + "…") if len(content) > max_len else content


def _pick_score(scores: dict[str, Any]) -> float:
    """按优先级取下游证据分数：final > rerank > fused > vector > lexical > 0。"""
    return float(
        scores.get("final_score")
        or scores.get("rerank_score")
        or scores.get("fused_score")
        or scores.get("vector_score")
        or scores.get("lexical_score")
        or 0.0
    )


def _citation_from_metadata(metadata: dict | None, *, with_citation: bool) -> dict:
    if not with_citation:
        return {}
    meta = metadata or {}
    citation: dict[str, Any] = {}
    if meta.get("page") is not None:
        citation["page"] = int(meta["page"])
    if meta.get("position") is not None:
        citation["position"] = meta["position"]
    if meta.get("chunk_id") is not None:
        citation["chunkId"] = str(meta["chunk_id"])
    return citation


def _ur_doc_to_item(doc: dict, *, with_citation: bool) -> dict:
    score = _pick_score(doc.get("scores") or {})
    return {
        "docId": str(doc.get("id") or doc.get("doc_id") or ""),
        "docTitle": str(doc.get("title") or ""),
        "score": float(score or 0.0),
        "snippet": str(doc.get("snippet") or doc.get("content") or ""),
        "citation": _citation_from_metadata(doc.get("metadata"), with_citation=with_citation),
    }


def _doc_item_to_item(item: dict, *, with_citation: bool) -> dict:
    score = _pick_score(item.get("scores") or {})
    return {
        "docId": str(item.get("primary_id") or item.get("knowledge_id") or item.get("file_id") or ""),
        "docTitle": str(item.get("title") or ""),
        "score": float(score or 0.0),
        "snippet": _snippet(str(item.get("content") or "")),
        "citation": _citation_from_metadata(item.get("metadata"), with_citation=with_citation),
    }


def _validate_kb_scope(payload, kb_ids: list[str], *, owner_id: str, tenant_id: str) -> None:
    """逐库校验知识库存在性与数据范围，与 KnowledgeBaseService._visible_records 收敛逻辑对齐。"""
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


def _query_in_process(payload, kb_ids: list[str]) -> dict:
    """进程内占位检索（离线/测试）：关键词索引 + 占位回答。"""
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
        search_type=payload.searchType or "hybrid",
    )


def _query_ur(payload, kb_ids: list[str]) -> dict:
    """普通检索走 universal_retriever /retrieval/search/sync。"""
    top_k = payload.topK or 5
    mode = (payload.mode or "qa").strip().lower() or "qa"
    with_citation = bool(payload.withCitation)

    request: dict[str, Any] = {
        "query": (payload.query or "").strip(),
        "retrieval_mode": payload.searchType or "hybrid",
        "top_k": top_k,
        "page": 1,
        "page_size": top_k,
        "filters": [dict(payload.filters)] if payload.filters else None,
        "request_id": current_trace_id(),
    }
    index = payload.index.strip() or search_client.resolve_index(kb_ids)
    if index:
        request["index"] = index
    if payload.relNum:
        request["related_top_k"] = int(payload.relNum)
    if payload.useRerank:
        request["rerank_model_params"] = {"provider": "rule", "top_k": top_k}
    if payload.score is not None:
        request["score_threshold"] = float(payload.score)
    if request["retrieval_mode"] == "hybrid":
        request["hybrid"] = {"strategy": "linear", "text_weight": 0.5, "vector_weight": 0.5}

    body = search_client.ur_search_sync(request, trace_id=current_trace_id())
    docs = body.get("docs") or []
    items = [_ur_doc_to_item(doc, with_citation=with_citation) for doc in docs]
    answer = ""
    qa_note = DEEP_SEARCH_QA_NOTE if mode == "qa" else ""
    return search_query_response(
        answer=answer,
        qa_note=qa_note,
        total=len(items),
        results=items,
        search_type=payload.searchType or "hybrid",
        used_config=body.get("used_config") if isinstance(body.get("used_config"), dict) else None,
    )


def _query_openai(payload, kb_ids: list[str], *, owner_id: str, tenant_id: str) -> dict:
    """普通检索走 openai_search_service VectorSearchV2。"""
    top_k = payload.topK or 5
    mode = (payload.mode or "qa").strip().lower() or "qa"
    with_citation = bool(payload.withCitation)

    request: dict[str, Any] = {
        "user_id": owner_id or "anonymous",
        "org_id": tenant_id or None,
        "search_id": current_trace_id(),
        "ct_id": ",".join(kb_ids),
        "query": {"text": (payload.query or "").strip()},
        "searchType": search_client.openai_search_type(payload.searchType),
        "topn": top_k,
        "useRerank": 1 if payload.useRerank else 0,
        "is_optimize": 1 if payload.isOptimize else 0,
        "filters": dict(payload.filters) if payload.filters else None,
    }
    index = payload.index.strip() or search_client.resolve_index(kb_ids)
    if index:
        request["index"] = index
    if payload.relNum:
        request["relNum"] = int(payload.relNum)
    if payload.score is not None:
        request["score"] = float(payload.score)

    body = search_client.openai_vector_search(request, trace_id=current_trace_id())
    items = [_doc_item_to_item(item, with_citation=with_citation) for item in (body.get("data") or [])]
    answer = ""
    qa_note = DEEP_SEARCH_QA_NOTE if mode == "qa" else ""
    return search_query_response(
        answer=answer,
        qa_note=qa_note,
        total=len(items),
        results=items,
        search_type=payload.searchType or "hybrid",
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
        _validate_kb_scope(payload, kb_ids, owner_id=owner_id, tenant_id=tenant_id)

        backend = search_client.search_backend()
        search_client.validate_backend(backend)
        if backend == "in_process":
            return _query_in_process(payload, kb_ids)
        if backend == "ur":
            return _query_ur(payload, kb_ids)
        if backend == "openai":
            return _query_openai(payload, kb_ids, owner_id=owner_id, tenant_id=tenant_id)
        raise SearchException(
            CommonErrorCodes.INVALID_PARAMS,
            {"field": "OPEN_PLATFORM_SEARCH_BACKEND", "reason": f"不支持的后端：{backend}"},
        )

    @staticmethod
    def deep_query(payload, *, owner_id: str = "", tenant_id: str = "") -> dict:
        kb_ids = _resolve_kb_ids(payload)
        if not kb_ids:
            raise SearchException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "kbIds", "reason": "kbId / kbIds 至少提供一个目标知识库"},
            )
        _validate_kb_scope(payload, kb_ids, owner_id=owner_id, tenant_id=tenant_id)

        backend = search_client.search_backend()
        search_client.validate_backend(backend)
        if backend != "openai":
            raise SearchException(
                CommonErrorCodes.NOT_IMPLEMENTED,
                {
                    "field": "deepSearch",
                    "reason": "深度检索需配置 OPEN_PLATFORM_SEARCH_BACKEND=openai 且下游 DeepSearch 可用",
                },
                message="深度检索未启用：需配置 OPEN_PLATFORM_SEARCH_BACKEND=openai 且下游 DeepSearch 可用",
            )

        request: dict[str, Any] = {
            "user_id": owner_id or "anonymous",
            "org_id": tenant_id or None,
            "search_id": current_trace_id(),
            "ct_id": ",".join(kb_ids),
            "query": {"text": (payload.query or "").strip()},
            "searchType": search_client.openai_search_type(payload.searchType),
            "topn": payload.topK,
            "useRerank": 1 if payload.useRerank else 0,
            "filters": dict(payload.filters) if payload.filters else None,
            "deepSearch": {"enabled": True},
        }
        index = payload.index.strip() if hasattr(payload, "index") else ""
        if index:
            request["index"] = index
        if payload.sessionId.strip():
            request["session_id"] = payload.sessionId.strip()
        if (
            payload.memory is not None
            and payload.memory.mode == "caller"
            and getattr(payload.memory, "items", None)
        ):
            request["memory"] = {"mode": "caller", "items": payload.memory.items}
        if payload.deepSearch is not None:
            ds = payload.deepSearch
            spec: dict[str, Any] = {"enabled": True, "maxSteps": ds.maxSteps, "recallTopnPolicy": ds.recallTopnPolicy}
            if ds.subQuery is not None:
                spec["subQuery"] = {
                    "enabled": ds.subQuery.enabled,
                    "maxSubQueries": ds.subQuery.maxSubQueries,
                    "mergeStrategy": ds.subQuery.mergeStrategy,
                }
            if ds.stopWhen is not None:
                stop: dict[str, Any] = {}
                if ds.stopWhen.minEvidence is not None:
                    stop["minEvidence"] = ds.stopWhen.minEvidence
                if ds.stopWhen.minFinalScore is not None:
                    stop["minFinalScore"] = ds.stopWhen.minFinalScore
                if ds.stopWhen.maxLatencyMs is not None:
                    stop["maxLatencyMs"] = ds.stopWhen.maxLatencyMs
                if stop:
                    spec["stopWhen"] = stop
            request["deepSearch"] = spec
        request["responseSpec"] = dict(payload.responseSpec or {})

        body = search_client.openai_deep_search(request, trace_id=current_trace_id())
        result = body.get("result") or {}
        answer = str(result.get("answer") or "")
        used_queries = [str(q) for q in (result.get("used_queries") or [])]

        citations: list[dict[str, Any]] = []
        for citation in body.get("citations") or []:
            locator = citation.get("locator") or {}
            meta = citation.get("metadata") or {}
            position = locator.get("position") or meta.get("position") or []
            if isinstance(position, int):
                position = [position]
            page = locator.get("page") or meta.get("page")
            citation_item: dict[str, Any] = {
                "docId": str(citation.get("id") or citation.get("knowledge_id") or citation.get("file_id") or ""),
                "docTitle": str(citation.get("title") or ""),
                "score": _pick_score(citation.get("scores") or {}),
                "snippet": str(citation.get("snippet") or ""),
                "position": [int(p) for p in position] if isinstance(position, list) else [],
            }
            if page is not None:
                citation_item["page"] = int(page)
            citations.append(citation_item)

        steps: list[dict[str, Any]] = []
        include = request["responseSpec"].get("include") or []
        if "steps" in include:
            extra = body.get("extra") or {}
            for raw in extra.get("agent_steps") or []:
                if not isinstance(raw, dict):
                    continue
                steps.append({
                    "stage": str(raw.get("stage") or raw.get("step") or ""),
                    "query": str(raw.get("query") or ""),
                    "docsCount": int(raw.get("docs_count") or raw.get("docsCount") or 0),
                    "elapsedMs": float(raw.get("elapsed_ms") or raw.get("elapsedMs") or 0.0),
                })

        return deep_search_query_response(
            answer=answer,
            total=len(citations),
            citations=citations,
            used_queries=used_queries,
            steps=steps,
        )
