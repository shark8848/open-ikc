from __future__ import annotations

from datetime import datetime, timezone

from app.core.error_codes import CommonErrorCodes, KnowledgeBaseException
from app.core.responses import knowledge_base_create_response, knowledge_base_update_response
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest
from app.services.knowledge_base_store import (
    KnowledgeBaseRecord,
    KnowledgeBaseStore,
    StoreConflictError,
    StoreNotFoundError,
    make_record,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_metadata_schema(metadata_schema: list) -> None:
    seen: set[str] = set()
    for field in metadata_schema:
        name = field.name.strip()
        if not name:
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "metadataSchema", "reason": "元数据字段名不能为空"},
            )
        if name in seen:
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "metadataSchema", "reason": f"元数据字段名重复：{name}"},
            )
        seen.add(name)


def _resolve_enterprise_org_id(requested_org_id: str, tenant_id: str) -> str:
    """企业知识库需要可识别的组织范围：优先 orgId，其次调用主体租户标识。"""
    if requested_org_id.strip():
        return requested_org_id.strip()
    if tenant_id.strip():
        return tenant_id.strip()
    raise KnowledgeBaseException(
        CommonErrorCodes.FORBIDDEN,
        {"field": "orgId", "reason": "企业知识库需提供 orgId 或可由调用主体识别组织授权"},
    )


def _scope_key(kb_type: str, *, team_id: str, org_id: str, owner_id: str) -> str:
    if kb_type == "team":
        return f"team:{team_id}"
    if kb_type == "enterprise":
        return f"org:{org_id}"
    return f"personal:{owner_id}"


def _resolve_scope(
    kb_type: str,
    payload: KnowledgeBaseCreateRequest | KnowledgeBaseUpdateRequest,
    owner_id: str,
    tenant_id: str,
) -> tuple[str, str]:
    org_id = payload.orgId.strip()
    if kb_type == "enterprise":
        org_id = _resolve_enterprise_org_id(org_id, tenant_id)
    return org_id, _scope_key(kb_type, team_id=payload.teamId.strip(), org_id=org_id, owner_id=owner_id)


class KnowledgeBaseService:
    @staticmethod
    def create(payload: KnowledgeBaseCreateRequest, *, owner_id: str = "", tenant_id: str = "") -> dict:
        _validate_metadata_schema(payload.metadataSchema)
        org_id, scope_key = _resolve_scope(payload.kbType, payload, owner_id, tenant_id)
        record = make_record(
            kb_name=payload.kbName.strip(),
            kb_type=payload.kbType,
            team_id=payload.teamId.strip(),
            org_id=org_id,
            kb_desc=payload.kbDesc.strip(),
            biz_domain=payload.bizDomain.strip() or "general",
            visibility=payload.visibility,
            metadata_schema=[field.model_dump() for field in payload.metadataSchema],
            owner_id=owner_id,
            tenant_id=tenant_id,
            scope_key=scope_key,
            create_time=_now_iso(),
        )
        try:
            KnowledgeBaseStore.create(record)
        except StoreConflictError:
            raise KnowledgeBaseException(
                CommonErrorCodes.CONFLICT,
                {"field": "kbName", "reason": f"同范围知识库名称重复：{payload.kbName}"},
            )
        return knowledge_base_create_response(record)

    @staticmethod
    def get_or_raise(kb_id: str) -> KnowledgeBaseRecord:
        record = KnowledgeBaseStore.get(kb_id)
        if record is None:
            raise KnowledgeBaseException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "kbId", "reason": f"知识库不存在：{kb_id}"},
            )
        return record

    @staticmethod
    def update(payload: KnowledgeBaseUpdateRequest, *, owner_id: str = "", tenant_id: str = "") -> dict:
        if not payload.kbId.strip():
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "kbId", "reason": "知识库 ID 不能为空"},
            )

        existing = KnowledgeBaseService.get_or_raise(payload.kbId)
        if existing.kb_type == "personal" and existing.owner_id and existing.owner_id != owner_id:
            raise KnowledgeBaseException(
                CommonErrorCodes.FORBIDDEN,
                {"field": "kbId", "reason": "个人知识库仅创建者可修改"},
            )

        _validate_metadata_schema(payload.metadataSchema)
        org_id, scope_key = _resolve_scope(payload.kbType, payload, owner_id, tenant_id)
        updated = make_record(
            kb_id=existing.kb_id,
            kb_name=payload.kbName.strip() or existing.kb_name,
            kb_type=payload.kbType,
            team_id=payload.teamId.strip(),
            org_id=org_id,
            kb_desc=payload.kbDesc.strip() or existing.kb_desc,
            biz_domain=existing.biz_domain,
            visibility=payload.visibility,
            metadata_schema=[field.model_dump() for field in payload.metadataSchema] or list(existing.metadata_schema),
            owner_id=existing.owner_id,
            tenant_id=existing.tenant_id,
            scope_key=scope_key,
            create_time=existing.create_time,
            update_time=_now_iso(),
        )
        try:
            KnowledgeBaseStore.update(updated)
        except StoreNotFoundError:
            raise KnowledgeBaseException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "kbId", "reason": f"知识库不存在：{payload.kbId}"},
            )
        except StoreConflictError:
            raise KnowledgeBaseException(
                CommonErrorCodes.CONFLICT,
                {"field": "kbName", "reason": f"同范围知识库名称重复：{payload.kbName}"},
            )
        return knowledge_base_update_response(updated)
