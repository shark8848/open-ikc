from __future__ import annotations

from typing import Any

from app.core.error_codes import CommonErrorCodes, ErrorCode, KnowledgeBaseErrorCodes, ParseErrorCodes, error_response
from app.core.trace import current_trace_id
from app.services.knowledge_base_store import KnowledgeBaseRecord


def with_trace_id(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "traceId": current_trace_id()}


def placeholder_response(category: str, action: str, path: str) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.NOT_IMPLEMENTED,
        {
            "category": category,
            "action": action,
            "path": path,
        },
        message=f"{category} / {action} 接口已预占位，待实现",
    ))


def _knowledge_base_data(record: KnowledgeBaseRecord) -> dict[str, Any]:
    return {
        "kbId": record.kb_id,
        "kbName": record.kb_name,
        "kbType": record.kb_type,
        "kbMode": record.kb_mode,
        "teamId": record.team_id,
        "orgId": record.org_id,
        "kbDesc": record.kb_desc,
        "bizDomain": record.biz_domain,
        "visibility": record.visibility,
        "metadataSchema": record.metadata_schema,
        "wikiConfig": record.wiki_config,
        "graphSchema": record.graph_schema,
        "createTime": record.create_time,
        "updateTime": record.update_time,
    }


def knowledge_base_create_response(record: KnowledgeBaseRecord) -> dict[str, Any]:
    return with_trace_id(error_response(
        KnowledgeBaseErrorCodes.SUCCESS,
        _knowledge_base_data(record),
    ))


def knowledge_base_update_response(record: KnowledgeBaseRecord) -> dict[str, Any]:
    return with_trace_id(error_response(
        KnowledgeBaseErrorCodes.SUCCESS,
        _knowledge_base_data(record),
    ))


def knowledge_base_detail_response(record: KnowledgeBaseRecord) -> dict[str, Any]:
    return with_trace_id(error_response(
        KnowledgeBaseErrorCodes.SUCCESS,
        _knowledge_base_data(record),
    ))


def knowledge_base_query_response(
    *,
    total: int,
    page: int,
    page_size: int,
    records: list[KnowledgeBaseRecord],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        KnowledgeBaseErrorCodes.SUCCESS,
        {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "items": [_knowledge_base_data(record) for record in records],
        },
    ))


def parse_response(
    *,
    task_id: str,
    task_status: str,
    execute_mode: str,
    result_inline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return with_trace_id(error_response(
        ParseErrorCodes.SUCCESS,
        {
            "taskId": task_id,
            "taskStatus": task_status,
            "executeMode": execute_mode,
            "resultInline": result_inline or {},
        },
    ))


def parse_direct_response(
    *,
    task_id: str,
    doc_id: str,
    task_status: str,
    execute_mode: str,
    result_inline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return with_trace_id(error_response(
        ParseErrorCodes.SUCCESS,
        {
            "taskId": task_id,
            "docId": doc_id,
            "taskStatus": task_status,
            "executeMode": execute_mode,
            "resultInline": result_inline or {},
        },
    ))


def parse_result_query_response(
    *,
    parse_status: str,
    result_format: dict[str, Any],
    page_count: int,
    chunk_count: int,
    failed_reason: str,
) -> dict[str, Any]:
    return with_trace_id(error_response(
        ParseErrorCodes.SUCCESS,
        {
            "parseStatus": parse_status,
            "resultFormat": result_format,
            "pageCount": page_count,
            "chunkCount": chunk_count,
            "failedReason": failed_reason,
        },
    ))


def issue_download_ticket_response(
    *,
    ticket: str,
    expire_at: str,
    download_path: str,
) -> dict[str, Any]:
    return with_trace_id(error_response(
        ParseErrorCodes.SUCCESS,
        {
            "ticket": ticket,
            "expireAt": expire_at,
            "downloadPath": download_path,
        },
    ))


def download_result_response(
    *,
    doc_id: str,
    task_id: str,
    download_path: str,
    result_format: dict[str, Any],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        ParseErrorCodes.SUCCESS,
        {
            "docId": doc_id,
            "taskId": task_id,
            "downloadPath": download_path,
            "format": (result_format or {}).get("type") or "json",
            "note": "解析结果存储落地前返回统一体，后续切换为文件流下载。",
        },
    ))


def document_upload_response(record: Any) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "fileId": record.file_id,
            "fileName": record.file_name,
            "fileSize": record.file_size,
            "contentType": record.content_type,
            "tempUrl": f"/api/v1/knowledge-documents/upload/{record.file_id}",
            "expiresAt": record.expires_at,
            "expiresInSeconds": record.expires_in,
        },
    ))


def search_query_response(
    *,
    answer: str,
    total: int,
    results: list[dict[str, Any]],
    qa_note: str = "",
    search_type: str = "hybrid",
    used_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "answer": answer,
            "qaNote": qa_note,
            "total": total,
            "results": results,
            "searchType": search_type,
            "usedConfig": used_config or {},
        },
    ))


def deep_search_query_response(
    *,
    answer: str,
    total: int,
    citations: list[dict[str, Any]],
    used_queries: list[str],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "answer": answer,
            "total": total,
            "citations": citations,
            "usedQueries": used_queries,
            "steps": steps,
        },
    ))


def wiki_tree_response(
    *,
    kb_id: str,
    total: int,
    page: int,
    page_size: int,
    tree: list[dict[str, Any]],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "wiki",
            "total": total,
            "page": page,
            "pageSize": page_size,
            "tree": tree,
        },
    ))


def _wiki_page_data(page_record: Any) -> dict[str, Any]:
    return {
        "pageId": page_record.page_id,
        "title": page_record.title,
        "level": page_record.level,
        "parentPageId": page_record.parent_page_id,
        "markdown": page_record.markdown,
        "fields": dict(page_record.fields),
        "tags": list(page_record.tags),
        "links": list(page_record.links),
        "sourceDocs": list(page_record.source_docs),
        "status": page_record.status,
        "createdAt": page_record.created_at,
        "updatedAt": page_record.updated_at,
    }


def wiki_page_response(*, kb_id: str, page_record: Any) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "wiki",
            "page": _wiki_page_data(page_record),
        },
    ))


def wiki_search_response(
    *,
    kb_id: str,
    q: str,
    total: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "wiki",
            "q": q,
            "total": total,
            "items": items,
        },
    ))


def _graph_node_data(record: Any) -> dict[str, Any]:
    return {
        "entityId": record.entity_id,
        "type": record.entity_type,
        "name": record.name,
        "properties": dict(record.properties),
        "aliases": list(record.aliases),
        "evidence": list(record.evidence),
        "confidence": record.confidence,
        "status": record.status,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def _graph_edge_data(record: Any) -> dict[str, Any]:
    return {
        "relationId": record.relation_id,
        "type": record.relation_type,
        "sourceEntityId": record.source_entity_id,
        "targetEntityId": record.target_entity_id,
        "properties": dict(record.properties),
        "evidence": list(record.evidence),
        "confidence": record.confidence,
        "status": record.status,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def graph_stat_response(
    *,
    kb_id: str,
    graph_id: str,
    stat: dict[str, Any],
    schema_coverage: dict[str, Any],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "graph",
            "graphId": graph_id,
            "nodeCount": stat["nodeCount"],
            "edgeCount": stat["edgeCount"],
            "entityTypes": stat["entityTypes"],
            "relationTypes": stat["relationTypes"],
            "schemaCoverage": schema_coverage,
        },
    ))


def graph_nodes_response(
    *,
    kb_id: str,
    total: int,
    page: int,
    page_size: int,
    records: list[Any],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "graph",
            "total": total,
            "page": page,
            "pageSize": page_size,
            "items": [_graph_node_data(record) for record in records],
        },
    ))


def graph_edges_response(
    *,
    kb_id: str,
    total: int,
    page: int,
    page_size: int,
    records: list[Any],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "graph",
            "total": total,
            "page": page,
            "pageSize": page_size,
            "items": [_graph_edge_data(record) for record in records],
        },
    ))


def graph_neighbors_response(
    *,
    kb_id: str,
    entity_id: str,
    depth: int,
    center: Any,
    nodes: list[Any],
    edges: list[Any],
) -> dict[str, Any]:
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "graph",
            "entityId": entity_id,
            "depth": depth,
            "center": _graph_node_data(center),
            "nodes": [_graph_node_data(record) for record in nodes],
            "edges": [_graph_edge_data(record) for record in edges],
        },
    ))


def graph_export_response(
    *,
    kb_id: str,
    graph_id: str,
    content: str,
) -> dict[str, Any]:
    total = content.count("\n") + 1 if content else 0
    return with_trace_id(error_response(
        CommonErrorCodes.SUCCESS,
        {
            "kbId": kb_id,
            "kbMode": "graph",
            "graphId": graph_id,
            "format": "jsonl",
            "total": total,
            "content": content,
        },
    ))
