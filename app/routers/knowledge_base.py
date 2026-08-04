from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.authz.runtime import authorize_or_raise
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseResponse, KnowledgeBaseUpdateRequest
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["知识库"])


def _request_identity(request: Request) -> dict[str, str]:
    identity = getattr(request.state, "identity", None)
    if isinstance(identity, dict):
        return {
            "user_id": str(identity.get("user_id") or ""),
            "tenant_id": str(identity.get("tenant_id") or ""),
        }
    return {"user_id": "", "tenant_id": ""}


@router.post(
    "/create",
    summary="创建知识库",
    description="创建一个新的知识库，并返回知识库标识、基础信息、元数据定义和创建时间。",
    response_model=KnowledgeBaseResponse,
)
async def create_knowledge_base(request: Request, payload: KnowledgeBaseCreateRequest) -> dict:
    identity = _request_identity(request)
    authorize_or_raise(
        request=request,
        action="create",
        resource_type="knowledge_base",
        context={
            "kb_type": payload.kbType,
            "owner_id": identity["user_id"],
            "org_path": payload.orgId or identity["tenant_id"],
        },
    )
    return KnowledgeBaseService.create(payload, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.post(
    "/update",
    summary="修改知识库信息",
    description="更新知识库基础信息、可见范围和元数据字段定义，并返回完整的更新后报文。",
    response_model=KnowledgeBaseResponse,
)
async def update_knowledge_base(request: Request, payload: KnowledgeBaseUpdateRequest) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(payload.kbId)
    authorize_or_raise(
        request=request,
        action="update",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return KnowledgeBaseService.update(payload, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])
