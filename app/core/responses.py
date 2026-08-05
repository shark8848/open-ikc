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
        "teamId": record.team_id,
        "orgId": record.org_id,
        "kbDesc": record.kb_desc,
        "bizDomain": record.biz_domain,
        "visibility": record.visibility,
        "metadataSchema": record.metadata_schema,
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
