from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.core.authz.runtime import authorize_or_raise
from app.schemas.graph import (
    GraphEdgesResponse,
    GraphExportResponse,
    GraphNeighborsResponse,
    GraphNodesResponse,
    GraphStatResponse,
)
from app.schemas.wiki import WikiPageResponse, WikiSearchResponse, WikiTreeResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseQueryRequest,
    KnowledgeBaseQueryResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)
from app.services.graph import GraphService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.wiki import WikiService

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


@router.post(
    "/query",
    summary="查询知识库列表",
    description="按类型、团队/组织范围、关键字分页查询调用方可访问的知识库列表，个人库按调用方身份收敛。",
    response_model=KnowledgeBaseQueryResponse,
)
async def query_knowledge_bases(request: Request, payload: KnowledgeBaseQueryRequest) -> dict:
    identity = _request_identity(request)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        context={
            "kb_type": payload.kbType or "",
            "owner_id": identity["user_id"],
            "org_path": payload.orgId or identity["tenant_id"],
        },
    )
    return KnowledgeBaseService.query(payload, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.get(
    "/{kb_id}",
    summary="查询知识库详情",
    description="按知识库 ID 查询基本信息；个人库仅创建者可访问，不存在返回 100404。",
    response_model=KnowledgeBaseResponse,
)
async def get_knowledge_base(request: Request, kb_id: str) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return KnowledgeBaseService.get_detail(kb_id, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.get(
    "/{kb_id}/wiki/tree",
    summary="查询 Wiki 库页面树",
    description="返回库级页面树（pageId/title/level/层级），支持 page/pageSize 分页；仅 kbMode=wiki 的知识库可用，无页面返回空树。",
    response_model=WikiTreeResponse,
)
async def get_wiki_tree(
    request: Request,
    kb_id: str,
    page: int = Query(1, ge=1, description="页码，从 1 开始。"),
    pageSize: int = Query(20, ge=1, le=100, description="每页根节点数，最大 100。"),
) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return WikiService.tree(
        kb_id,
        page=page,
        page_size=pageSize,
        owner_id=identity["user_id"],
        tenant_id=identity["tenant_id"],
    )


@router.get(
    "/{kb_id}/wiki/page",
    summary="查询 Wiki 页面详情",
    description="按 pageId 返回单页正文、结构化字段、互链与来源证据；页面不存在返回 100404。",
    response_model=WikiPageResponse,
)
async def get_wiki_page(
    request: Request,
    kb_id: str,
    pageId: str = Query(..., min_length=1, description="Wiki 页面 ID（由 wiki/tree 或 wiki/search 返回）。"),
) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return WikiService.page(
        kb_id,
        page_id=pageId,
        owner_id=identity["user_id"],
        tenant_id=identity["tenant_id"],
    )


@router.get(
    "/{kb_id}/wiki/search",
    summary="检索 Wiki 库页面",
    description="库内页面级检索：标题命中加权 > 正文命中；可附加 tag 过滤；q 为空返回全部活跃页面。",
    response_model=WikiSearchResponse,
)
async def search_wiki_pages(
    request: Request,
    kb_id: str,
    q: str = Query("", description="检索关键字，空串返回全部活跃页面。"),
    tag: str = Query("", description="按页面标签精确过滤，可选。"),
) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return WikiService.search(
        kb_id,
        q=q,
        tag=tag,
        owner_id=identity["user_id"],
        tenant_id=identity["tenant_id"],
    )


# ---------- 图谱库（kbMode=graph） ----------


@router.get(
    "/{kb_id}/graph/stat",
    summary="查询图谱库摘要",
    description="返回库级图谱统计：节点/边计数、类型分布与 schema 覆盖率；仅 kbMode=graph 可用，空图谱返回零值统计（非错误）。",
    response_model=GraphStatResponse,
)
async def get_graph_stat(request: Request, kb_id: str) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return GraphService.stat(kb_id, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.get(
    "/{kb_id}/graph/nodes",
    summary="查询图谱节点",
    description="分页查询实体节点，支持按 entityType 过滤；仅 kbMode=graph 可用。",
    response_model=GraphNodesResponse,
)
async def get_graph_nodes(
    request: Request,
    kb_id: str,
    entityType: str = Query("", description="按实体类型过滤，可选。"),
    page: int = Query(1, ge=1, description="页码，从 1 开始。"),
    pageSize: int = Query(20, ge=1, le=100, description="每页条数，最大 100。"),
) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return GraphService.nodes(
        kb_id,
        entity_type=entityType,
        page=page,
        page_size=pageSize,
        owner_id=identity["user_id"],
        tenant_id=identity["tenant_id"],
    )


@router.get(
    "/{kb_id}/graph/edges",
    summary="查询图谱关系",
    description="分页查询关系边，支持按 relationType 过滤；仅 kbMode=graph 可用。",
    response_model=GraphEdgesResponse,
)
async def get_graph_edges(
    request: Request,
    kb_id: str,
    relationType: str = Query("", description="按关系类型过滤，可选。"),
    page: int = Query(1, ge=1, description="页码，从 1 开始。"),
    pageSize: int = Query(20, ge=1, le=100, description="每页条数，最大 100。"),
) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return GraphService.edges(
        kb_id,
        relation_type=relationType,
        page=page,
        page_size=pageSize,
        owner_id=identity["user_id"],
        tenant_id=identity["tenant_id"],
    )


@router.get(
    "/{kb_id}/graph/neighbors",
    summary="查询实体邻域",
    description="按 entityId 查询实体邻域（depth 仅支持 1/2），返回中心节点、可达节点与覆盖边；实体不存在返回 100404。",
    response_model=GraphNeighborsResponse,
)
async def get_graph_neighbors(
    request: Request,
    kb_id: str,
    entityId: str = Query(..., min_length=1, description="中心实体 ID（由 graph/nodes 返回）。"),
    depth: int = Query(1, ge=1, le=2, description="邻域深度：1 或 2。"),
) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return GraphService.neighbors(
        kb_id,
        entity_id=entityId,
        depth=depth,
        owner_id=identity["user_id"],
        tenant_id=identity["tenant_id"],
    )


@router.get(
    "/{kb_id}/graph/export",
    summary="导出图谱全量",
    description="全量导出库级图谱（jsonl：entity/relation 记录，含 deprecated）；仅 kbMode=graph 可用。",
    response_model=GraphExportResponse,
)
async def export_graph(request: Request, kb_id: str) -> dict:
    identity = _request_identity(request)
    record = KnowledgeBaseService.get_or_raise(kb_id)
    authorize_or_raise(
        request=request,
        action="read",
        resource_type="knowledge_base",
        resource_id=record.kb_id,
        context={
            "kb_id": record.kb_id,
            "kb_type": record.kb_type,
            "owner_id": record.owner_id,
            "org_path": record.org_id or record.tenant_id,
        },
    )
    return GraphService.export(kb_id, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])
