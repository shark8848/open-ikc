from __future__ import annotations

from app.core.error_codes import CommonErrorCodes, KnowledgeBaseException
from app.core.responses import knowledge_base_create_response, knowledge_base_update_response
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest


class KnowledgeBaseService:
    @staticmethod
    def create(payload: KnowledgeBaseCreateRequest) -> dict:
        if payload.kbType == "enterprise" and not payload.orgId.strip():
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "orgId", "reason": "kbType=enterprise 时 orgId 建议填写"},
            )
        return knowledge_base_create_response(payload)

    @staticmethod
    def update(payload: KnowledgeBaseUpdateRequest) -> dict:
        if payload.kbType == "enterprise" and not payload.orgId.strip():
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "orgId", "reason": "kbType=enterprise 时 orgId 建议填写"},
            )
        if payload.kbId.strip() == "":
            raise KnowledgeBaseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "kbId", "reason": "知识库 ID 不能为空"},
            )
        return knowledge_base_update_response(payload)
