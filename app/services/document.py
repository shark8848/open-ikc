from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.error_codes import CommonErrorCodes, DocumentException, KnowledgeBaseException, error_response
from app.core.trace import current_trace_id
from app.services.document_store import (
    DOCUMENT_STATUS,
    DocumentRecord,
    DocumentStore,
    StoreConflictError,
    generate_ingest_task_id,
    make_record,
)
from app.services.knowledge_base import KnowledgeBaseService
from app.services.parse import ParseService


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _generate_parse_task_id() -> str:
    """生成 `parse_<17位数字>` 形态的解析任务 ID。"""
    millis = int(time.time() * 1000)
    return f"parse_{millis:013d}{secrets.randbelow(10000):04d}"


def _source_primary_key(source_type: str, source_url: str, object_key: str) -> str:
    """来源主标识：url 来源以 source_url 为键，其余以 objectKey 为键（与 document_store 判定一致）。"""
    return object_key if source_type != "url" else source_url


def _infer_doc_title(source_type: str, source_url: str, explicit_title: str) -> str:
    title = explicit_title.strip()
    if title:
        return title
    if source_type == "url" and source_url.strip():
        path_tail = source_url.strip().rstrip("/").split("/")[-1].strip()
        if path_tail:
            return path_tail
    return source_type


def _success_response(data: dict) -> dict:
    # 待 responses.py 收敛：document_ingest_response / document_info_response 落地后迁移到 app.core.responses
    return {**error_response(CommonErrorCodes.SUCCESS, data), "traceId": current_trace_id()}


class DocumentService:
    @staticmethod
    def _validate_kb_scope(kb_record, payload, *, owner_id: str, tenant_id: str) -> None:
        """知识库类型与组织归属校验：个人/团队/企业库的接入范围收敛。"""
        if kb_record.kb_type == "personal":
            if kb_record.owner_id != owner_id:
                raise KnowledgeBaseException(
                    CommonErrorCodes.FORBIDDEN,
                    {"field": "kbId", "reason": "个人知识库仅创建者可接入文档"},
                )
        elif kb_record.kb_type == "team":
            if (payload.teamId or "").strip() != kb_record.team_id:
                raise KnowledgeBaseException(
                    CommonErrorCodes.FORBIDDEN,
                    {"field": "teamId", "reason": "团队知识库需匹配团队归属"},
                )
        else:  # enterprise
            org_scope = (payload.orgId or "").strip() or tenant_id.strip()
            if not org_scope or kb_record.org_id != org_scope:
                raise KnowledgeBaseException(
                    CommonErrorCodes.FORBIDDEN,
                    {"field": "orgId", "reason": "企业知识库需匹配组织范围"},
                )

    @staticmethod
    def _validate_source(source) -> None:
        source_type = (source.type or "").strip().lower()
        if source_type == "file" and not (source.objectKey or "").strip() and not (source.fileToken or "").strip():
            raise DocumentException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "source", "reason": "file 类型来源需提供 objectKey 或 fileToken"},
            )
        if source_type == "url" and not (source.url or "").strip():
            raise DocumentException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "source.url", "reason": "url 类型来源需提供 url"},
            )

    @staticmethod
    def _find_registered_document(
        kb_id: str,
        source_type: str,
        source_url: str,
        object_key: str,
        doc_title: str,
    ) -> DocumentRecord | None:
        """幂等判定：同知识库 + 来源主标识 + 文档标题的既有登记（FAILED 允许重试）。"""
        source_key = _source_primary_key(source_type, source_url, object_key)
        for record in DocumentStore.list_by_kb(kb_id):
            if record.status == DOCUMENT_STATUS["FAILED"]:
                continue
            record_key = _source_primary_key(record.source_type, record.source_url, record.object_key)
            if record_key == source_key and record.doc_title == doc_title:
                return record
        return None

    @staticmethod
    def _create_document(
        *,
        kb_id: str,
        doc_title: str,
        source_type: str,
        source_url: str,
        object_key: str,
        tags: list[str],
        metadata: dict,
        status: str,
        owner_id: str,
        tenant_id: str,
    ) -> DocumentRecord:
        now_iso = _now_iso()
        record = make_record(
            kb_id=kb_id,
            ingest_task_id=generate_ingest_task_id(),
            doc_title=doc_title,
            source_type=source_type,
            source_url=source_url,
            object_key=object_key,
            tags=list(tags),
            metadata=dict(metadata),
            status=status,
            owner_id=owner_id,
            tenant_id=tenant_id,
            ingest_time=now_iso,
            update_time=now_iso,
        )
        try:
            DocumentStore.create(record)
        except StoreConflictError:
            raise DocumentException(
                CommonErrorCodes.CONFLICT,
                {"field": "source", "reason": f"同知识库下文档重复登记：{doc_title}"},
            )
        return record

    @staticmethod
    def ingest(payload, *, owner_id: str = "", tenant_id: str = "") -> dict:
        kb_record = KnowledgeBaseService.get_or_raise(payload.kbId)
        DocumentService._validate_kb_scope(kb_record, payload, owner_id=owner_id, tenant_id=tenant_id)
        DocumentService._validate_source(payload.source)

        source_type = (payload.source.type or "file").strip().lower()
        source_url = (payload.source.url or "").strip()
        object_key = (payload.source.objectKey or "").strip()
        doc_title = _infer_doc_title(source_type, source_url, payload.docTitle or "")

        existing = DocumentService._find_registered_document(
            payload.kbId, source_type, source_url, object_key, doc_title
        )
        if existing is not None:
            # 幂等命中：复用既有 ingestTaskId/docId，status 沿用
            return _success_response(
                {
                    "ingestTaskId": existing.ingest_task_id,
                    "docId": existing.doc_id,
                    "docIds": [existing.doc_id],
                    "taskStatus": existing.status,
                    "sourceType": existing.source_type,
                    "sourceStats": {"total": 1, "success": 1, "failed": 0},
                    "ingestTime": existing.ingest_time,
                }
            )

        quick = (payload.orchestrationMode or "").strip().lower() == "quick"
        status = DOCUMENT_STATUS["PARSING"] if quick else DOCUMENT_STATUS["INGESTED"]
        record = DocumentService._create_document(
            kb_id=payload.kbId,
            doc_title=doc_title,
            source_type=source_type,
            source_url=source_url,
            object_key=object_key,
            tags=list(payload.tags or []),
            metadata=dict(payload.metadata or {}),
            status=status,
            owner_id=owner_id,
            tenant_id=tenant_id,
        )
        return _success_response(
            {
                "ingestTaskId": record.ingest_task_id,
                "docId": record.doc_id,
                "docIds": [record.doc_id],
                "taskStatus": record.status,
                "sourceType": record.source_type,
                "sourceStats": {"total": 1, "success": 1, "failed": 0},
                "ingestTime": record.ingest_time,
            }
        )

    @staticmethod
    def ingest_and_parse(payload, *, owner_id: str = "", tenant_id: str = "") -> dict:
        kb_record = KnowledgeBaseService.get_or_raise(payload.kbId)
        DocumentService._validate_kb_scope(kb_record, payload, owner_id=owner_id, tenant_id=tenant_id)
        DocumentService._validate_source(payload.source)

        source_type = (payload.source.type or "file").strip().lower()
        source_url = (payload.source.url or "").strip()
        object_key = (payload.source.objectKey or "").strip()
        doc_title = _infer_doc_title(source_type, source_url, payload.docTitle or "")

        existing = DocumentService._find_registered_document(
            payload.kbId, source_type, source_url, object_key, doc_title
        )
        if existing is not None:
            doc_id = existing.doc_id
            ingest_task_id = existing.ingest_task_id
        else:
            record = DocumentService._create_document(
                kb_id=payload.kbId,
                doc_title=doc_title,
                source_type=source_type,
                source_url=source_url,
                object_key=object_key,
                tags=list(payload.tags or []),
                metadata=dict(payload.metadata or {}),
                status=DOCUMENT_STATUS["PARSING"],
                owner_id=owner_id,
                tenant_id=tenant_id,
            )
            doc_id = record.doc_id
            ingest_task_id = record.ingest_task_id

        # 解析任务统一委托 ParseService：async 登记 queued 任务并返回真实 taskId，
        # sync 请求内完成解析并返回内联结果（与 POST /parse 一致，避免假任务 ID）。
        parse_result = ParseService.parse(
            SimpleNamespace(
                docId=doc_id,
                kbId=payload.kbId,
                executeMode=payload.executeMode or "async",
                parseStrategy=dict(payload.parseStrategy or {}),
                resultFormat=dict(payload.resultFormat or {}),
            ),
            owner_id=owner_id,
            tenant_id=tenant_id,
        )
        parse_data = parse_result["data"]
        return _success_response(
            {
                "ingestTaskId": ingest_task_id,
                "parseTaskId": parse_data["taskId"],
                "docId": doc_id,
                "taskStatus": parse_data["taskStatus"],
                "executeMode": parse_data["executeMode"],
                "resultInline": parse_data["resultInline"],
            }
        )

    @staticmethod
    def get_document(doc_id: str, *, owner_id: str = "", tenant_id: str = "") -> dict:
        doc = DocumentStore.get(doc_id)
        if doc is None:
            raise DocumentException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "docId", "reason": f"文档不存在：{doc_id}"},
            )
        kb_record = KnowledgeBaseService.get_or_raise(doc.kb_id)
        if kb_record.kb_type == "personal" and doc.owner_id != owner_id:
            raise DocumentException(
                CommonErrorCodes.FORBIDDEN,
                {"field": "docId", "reason": "个人知识库仅创建者可访问文档"},
            )
        # team / enterprise 读范围由 AUTHZ 或外部团队/组织系统收敛（与知识库读一致，成员关系校验占位）
        return _success_response(
            {
                "docId": doc.doc_id,
                "docTitle": doc.doc_title,
                "kbId": doc.kb_id,
                "sourceType": doc.source_type,
                "sourceUrl": doc.source_url,
                "objectKey": doc.object_key,
                "tags": list(doc.tags),
                "metadata": dict(doc.metadata),
                "status": doc.status,
                "ingestTime": doc.ingest_time,
                "updateTime": doc.update_time,
            }
        )
