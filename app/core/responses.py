from __future__ import annotations

from typing import Any

from app.core.error_codes import CommonErrorCodes, ErrorCode, KnowledgeBaseErrorCodes, error_response
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
