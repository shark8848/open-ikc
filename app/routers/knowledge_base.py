from fastapi import APIRouter

from app.services.knowledge_base import KnowledgeBaseService
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseResponse, KnowledgeBaseUpdateRequest

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["知识库"])


@router.post(
    "/create",
    summary="创建知识库",
    description="创建一个新的知识库，并返回知识库标识、基础信息、元数据定义和创建时间。",
    response_model=KnowledgeBaseResponse,
)
async def create_knowledge_base(payload: KnowledgeBaseCreateRequest) -> dict:
    return KnowledgeBaseService.create(payload)


@router.post(
    "/update",
    summary="修改知识库信息",
    description="更新知识库基础信息、可见范围和元数据字段定义，并返回完整的更新后报文。",
    response_model=KnowledgeBaseResponse,
)
async def update_knowledge_base(payload: KnowledgeBaseUpdateRequest) -> dict:
    return KnowledgeBaseService.update(payload)
