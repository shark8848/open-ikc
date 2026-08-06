from fastapi import APIRouter, Request

from app.core.authz.runtime import authorize_or_raise
from app.schemas.search import SearchQueryRequest, SearchQueryResponse
from app.services.search import SearchService

router = APIRouter(prefix="/api/v1/knowledge-search", tags=["检索"])


def _resolve_kb_ids(payload: SearchQueryRequest) -> list[str]:
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


@router.post(
    "/query",
    summary="统一检索问答",
    description="在知识库中执行统一检索与问答：search 模式返回证据列表，qa 模式附带回答（当前为占位生成）。kbId / kbIds 至少提供一个；检索结果按知识库类型与调用主体数据权限过滤：个人库仅创建者可检索，团队库需 teamId、企业库按 orgId 或调用主体租户收敛。多库检索逐库授权，任一库失败即整体拒绝。",
    response_model=SearchQueryResponse,
)
async def query_knowledge(request: Request, payload: SearchQueryRequest | None = None) -> dict:
    data = payload or SearchQueryRequest()
    identity = _request_identity(request)
    kb_ids = _resolve_kb_ids(data)
    # 多库联合检索逐库授权：resource_id 恒为具体 kb_id，任一库授权失败即整体拒绝
    for kb_id in kb_ids:
        authorize_or_raise(
            request=request,
            action="query",
            resource_type="search",
            resource_id=kb_id,
            context={
                "kb_id": kb_id,
                "kb_ids": kb_ids,
                "owner_id": data.ownerId.strip() or identity["user_id"],
                "org_path": data.orgPath.strip() or identity["tenant_id"],
                "team_id": data.teamId.strip(),
                "org_id": data.orgId.strip(),
                "query": data.query,
            },
        )
    return SearchService.query(data, owner_id=identity["user_id"], tenant_id=identity["tenant_id"])
