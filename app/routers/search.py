from fastapi import APIRouter, Request

from app.core.authz.runtime import authorize_or_raise
from app.schemas.search import (
    DeepSearchQueryRequest,
    DeepSearchQueryResponse,
    SearchQueryRequest,
    SearchQueryResponse,
)
from app.services.search import SearchService

router = APIRouter(prefix="/api/v1/knowledge-search", tags=["检索"])


def _resolve_kb_ids(payload) -> list[str]:
    values: list[str] = []
    if payload.kbId.strip():
        values.append(payload.kbId.strip())
    for item in payload.kbIds:
        cleaned = item.strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _request_identity(request: Request) -> dict[str, str]:
    identity = getattr(request.state, "identity", None)
    if isinstance(identity, dict):
        return {
            "user_id": str(identity.get("user_id") or ""),
            "tenant_id": str(identity.get("tenant_id") or ""),
        }
    return {"user_id": "", "tenant_id": ""}


def _authorize_scope(request: Request, payload, identity: dict[str, str]) -> None:
    """多库联合检索逐库授权：resource_id 恒为具体 kb_id，任一库授权失败即整体拒绝。

    AUTHZ 数据权限上下文中的 owner_id / org_path 一律取认证身份（request.state.identity），
    请求体 ownerId / orgPath 不作为授权依据（仅保留为兼容字段），避免调用方注入他人身份绕过授权。
    """
    kb_ids = _resolve_kb_ids(payload)
    for kb_id in kb_ids:
        authorize_or_raise(
            request=request,
            action="query",
            resource_type="search",
            resource_id=kb_id,
            context={
                "kb_id": kb_id,
                "kb_ids": kb_ids,
                "owner_id": identity["user_id"],
                "org_path": identity["tenant_id"],
                "team_id": payload.teamId.strip(),
                "org_id": payload.orgId.strip(),
                "query": payload.query,
            },
        )


@router.post(
    "/universal-search",
    summary="普通检索",
    description="在知识库中执行统一检索，返回证据列表（可选重排/关联召回/分数阈值）。kbId / kbIds 至少提供一个；检索结果按知识库类型与调用主体数据权限过滤：个人库仅创建者可检索，团队库需 teamId、企业库按 orgId 或调用主体租户收敛。多库检索逐库授权，任一库失败即整体拒绝。",
    response_model=SearchQueryResponse,
)
async def universal_search(request: Request, payload: SearchQueryRequest | None = None) -> dict:
    data = payload or SearchQueryRequest()
    identity = _request_identity(request)
    _authorize_scope(request, data, identity)
    return SearchService.query(data, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.post(
    "/query",
    summary="普通检索（兼容别名）",
    description="普通检索兼容别名，行为与 /universal-search 一致，供既有调用方平滑迁移。",
    response_model=SearchQueryResponse,
    deprecated=True,
)
async def query_alias(request: Request, payload: SearchQueryRequest | None = None) -> dict:
    data = payload or SearchQueryRequest()
    identity = _request_identity(request)
    _authorize_scope(request, data, identity)
    return SearchService.query(data, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])


@router.post(
    "/deep-search",
    summary="深度检索",
    description="Agentic 多轮深度检索：子查询规划、并行召回、反思与带引用回答。kbId / kbIds 至少提供一个；权限收敛与普通检索一致（逐库授权，任一库失败即整体拒绝）。依赖下游 DeepSearch 能力，未配置 OPEN_PLATFORM_SEARCH_BACKEND=openai 时返回 501001。",
    response_model=DeepSearchQueryResponse,
)
async def deep_search(request: Request, payload: DeepSearchQueryRequest | None = None) -> dict:
    data = payload or DeepSearchQueryRequest()
    identity = _request_identity(request)
    _authorize_scope(request, data, identity)
    return SearchService.deep_query(data, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])
