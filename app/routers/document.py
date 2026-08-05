from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.authz.runtime import authorize_or_raise
from app.core.error_codes import CommonErrorCodes, DocumentException
from app.schemas.document import (
    DocumentIngestAndParseRequest,
    DocumentIngestAndParseResponse,
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentInfoResponse,
)
from app.services.document import DocumentService
from app.services.document_store import DocumentStore
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/knowledge-documents", tags=["文档"])


def _request_identity(request: Request) -> dict[str, str]:
    identity = getattr(request.state, "identity", None)
    if isinstance(identity, dict):
        return {
            "user_id": str(identity.get("user_id") or ""),
            "tenant_id": str(identity.get("tenant_id") or ""),
        }
    return {"user_id": "", "tenant_id": ""}


@router.post(
    "/ingest",
    summary="接入知识源",
    description="统一接入 URL/文件/目录/压缩包来源并登记到指定知识库，返回接入任务与文档标识。",
    response_model=DocumentIngestResponse,
)
async def ingest_document(request: Request, payload: DocumentIngestRequest) -> dict:
    identity = _request_identity(request)
    # AUTHZ 必须先于 service 副作用：先取知识库记录供数据权限上下文
    kb_record = KnowledgeBaseService.get_or_raise(payload.kbId)
    authorize_or_raise(
        request=request,
        action="write",
        resource_type="document",
        resource_id=payload.kbId,
        context={
            "kb_id": payload.kbId,
            "kb_type": kb_record.kb_type,
            "owner_id": identity["user_id"],
            "org_path": payload.orgId or identity["tenant_id"],
        },
    )
    return DocumentService.ingest(payload, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.post(
    "/ingest-and-parse",
    summary="一体化接入并解析",
    description="一步完成知识源接入与解析任务登记，返回接入任务与解析任务标识。",
    response_model=DocumentIngestAndParseResponse,
)
async def ingest_and_parse_document(request: Request, payload: DocumentIngestAndParseRequest) -> dict:
    identity = _request_identity(request)
    kb_record = KnowledgeBaseService.get_or_raise(payload.kbId)
    authorize_or_raise(
        request=request,
        action="write",
        resource_type="document",
        resource_id=payload.kbId,
        context={
            "kb_id": payload.kbId,
            "kb_type": kb_record.kb_type,
            "owner_id": identity["user_id"],
            "org_path": payload.orgId or identity["tenant_id"],
        },
    )
    # 复合操作：接入 + 解析，需同时具备 document 写入与 parse 写入权限
    authorize_or_raise(
        request=request,
        action="write",
        resource_type="parse",
        resource_id="*",
        context={
            "kb_id": payload.kbId,
            "kb_type": kb_record.kb_type,
            "owner_id": identity["user_id"],
            "org_path": payload.orgId or identity["tenant_id"],
        },
    )
    return DocumentService.ingest_and_parse(
        payload, owner_id=identity["user_id"], tenant_id=identity["tenant_id"]
    )


@router.get(
    "/{doc_id}",
    summary="查询文档信息",
    description="按文档 ID 查询文档基础信息与接入状态；个人库文档仅创建者可访问，不存在返回 100404。",
    response_model=DocumentInfoResponse,
)
async def get_document(request: Request, doc_id: str) -> dict:
    identity = _request_identity(request)
    doc = DocumentStore.get(doc_id)
    if doc is None:
        raise DocumentException(
            CommonErrorCodes.NOT_FOUND,
            {"field": "docId", "reason": f"文档不存在：{doc_id}"},
        )
    kb_record = KnowledgeBaseService.get_or_raise(doc.kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="document",
        resource_id=doc.kb_id,
        context={
            "kb_id": doc.kb_id,
            "kb_type": kb_record.kb_type,
            "owner_id": kb_record.owner_id,
            "org_path": kb_record.org_id or kb_record.tenant_id,
        },
    )
    return DocumentService.get_document(doc_id, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])
