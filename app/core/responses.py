from __future__ import annotations

from typing import Any

from app.core.error_codes import CommonErrorCodes, ErrorCode, KnowledgeBaseErrorCodes, error_response
from app.core.trace import current_trace_id


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


def knowledge_base_create_response(payload: Any) -> dict[str, Any]:
    return with_trace_id(error_response(
        KnowledgeBaseErrorCodes.SUCCESS,
        {
            "kbId": "kb_10001",
            "kbName": payload.kbName,
            "kbType": payload.kbType,
            "teamId": payload.teamId,
            "orgId": payload.orgId,
            "kbDesc": payload.kbDesc,
            "bizDomain": payload.bizDomain,
            "visibility": payload.visibility,
            "metadataSchema": [field.model_dump() for field in payload.metadataSchema],
            "createTime": "2026-08-03T10:20:30Z",
            "updateTime": None,
        },
    ))


def knowledge_base_update_response(payload: Any) -> dict[str, Any]:
    return with_trace_id(error_response(
        KnowledgeBaseErrorCodes.SUCCESS,
        {
            "kbId": payload.kbId,
            "kbName": payload.kbName or "产品知识库-客服版",
            "kbType": payload.kbType,
            "teamId": payload.teamId,
            "orgId": payload.orgId,
            "kbDesc": payload.kbDesc,
            "bizDomain": "general",
            "visibility": payload.visibility,
            "metadataSchema": [field.model_dump() for field in payload.metadataSchema],
            "createTime": None,
            "updateTime": "2026-08-03T10:35:00Z",
        },
    ))
