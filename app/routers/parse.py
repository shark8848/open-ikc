from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.core.authz.runtime import authorize_or_raise
from app.schemas.parse import (
    DocumentParseRequest,
    DocumentParseResponse,
    DownloadResultResponse,
    IssueDownloadTicketResponse,
    ParseResultQueryResponse,
)
from app.services.document_store import DocumentStore
from app.services.knowledge_base import KnowledgeBaseService
from app.services.parse import ParseService

router = APIRouter(prefix="/api/v1/knowledge-documents", tags=["解析"])


def _request_identity(request: Request) -> dict[str, str]:
    identity = getattr(request.state, "identity", None)
    if isinstance(identity, dict):
        return {
            "user_id": str(identity.get("user_id") or ""),
            "tenant_id": str(identity.get("tenant_id") or ""),
        }
    return {"user_id": "", "tenant_id": ""}


def _doc_scope_context(doc_id: str) -> dict:
    """从文档记录与所属知识库组装 AUTHZ 数据权限上下文。"""
    doc = DocumentStore.get(doc_id)
    if doc is None:
        return {"doc_id": doc_id, "kb_id": "", "kb_type": "", "owner_id": "", "org_path": ""}
    kb_record = KnowledgeBaseService.get_or_raise(doc.kb_id)
    return {
        "doc_id": doc.doc_id,
        "kb_id": doc.kb_id,
        "kb_type": kb_record.kb_type,
        "owner_id": kb_record.owner_id,
        "org_path": kb_record.org_id or kb_record.tenant_id,
    }


@router.post(
    "/parse",
    summary="启动文档解析",
    description="对已接入文档启动解析任务，支持 async 异步返回任务 ID 与 sync 请求内返回内联结果。",
    response_model=DocumentParseResponse,
)
async def parse_document(request: Request, payload: DocumentParseRequest) -> dict:
    identity = _request_identity(request)
    authorize_or_raise(
        request=request,
        action="write",
        resource_type="parse",
        resource_id=payload.docId,
        context=_doc_scope_context(payload.docId),
    )
    return ParseService.parse(payload, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.get(
    "/parse-result/query",
    summary="查询解析结果",
    description="查询文档解析状态与解析产物摘要，用于上传后轮询解析进度。",
    response_model=ParseResultQueryResponse,
)
async def query_parse_result(request: Request, doc_id: str = Query(..., alias="docId")) -> dict:
    identity = _request_identity(request)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="parse",
        resource_id=doc_id,
        context=_doc_scope_context(doc_id),
    )
    return ParseService.query_parse_result(doc_id, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.get(
    "/parse-result/issue-download-ticket",
    summary="获取解析结果下载凭证",
    description="为解析结果签发短期下载凭证，后续携带凭证下载完整结果。",
    response_model=IssueDownloadTicketResponse,
)
async def issue_download_ticket(request: Request, doc_id: str = Query(..., alias="docId")) -> dict:
    identity = _request_identity(request)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="parse",
        resource_id=doc_id,
        context=_doc_scope_context(doc_id),
    )
    return ParseService.issue_download_ticket(doc_id, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.get(
    "/parse-result/download",
    summary="下载解析结果",
    description="携带下载凭证下载解析结果；解析结果存储落地前返回统一体（含下载说明），后续切换为文件流。",
    response_model=DownloadResultResponse,
)
async def download_parse_result(
    request: Request,
    doc_id: str = Query(..., alias="docId"),
    ticket: str = Query(...),
) -> dict:
    identity = _request_identity(request)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="parse",
        resource_id=doc_id,
        context=_doc_scope_context(doc_id),
    )
    return ParseService.download_parse_result(doc_id, ticket, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])
