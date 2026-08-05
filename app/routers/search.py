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


@router.post(
    "/query",
    summary="统一检索问答",
    description="在知识库中执行统一检索与问答；当前为预占位实现，返回 501001。",
    response_model=SearchQueryResponse,
)
async def query_knowledge(request: Request, payload: SearchQueryRequest | None = None) -> dict:
    data = payload or SearchQueryRequest()
    kb_ids = _resolve_kb_ids(data)
    authorize_or_raise(
        request=request,
        action="query",
        resource_type="search",
        resource_id=kb_ids[0] if len(kb_ids) == 1 else "*",
        context={
            "kb_id": kb_ids[0] if kb_ids else "",
            "kb_ids": kb_ids,
            "owner_id": data.ownerId.strip(),
            "org_path": data.orgPath.strip(),
            "query": data.query,
        },
    )
    return SearchService.query()
