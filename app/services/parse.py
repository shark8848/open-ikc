from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.error_codes import (
    CommonErrorCodes,
    DocumentException,
    ParseErrorCodes,
    ParseException,
)
from app.core.responses import (
    download_result_response,
    issue_download_ticket_response,
    parse_direct_response,
    parse_response,
    parse_result_query_response,
)
from app.services.document_store import DOCUMENT_STATUS, DocumentStore
from app.services.knowledge_base import KnowledgeBaseService
from app.services.parse_store import (
    PARSE_STATUS,
    ParseResultRecord,
    ParseTaskRecord,
    ParseTaskStore,
    ParseTicketStore,
    generate_parse_task_id,
    generate_ticket,
)

DOWNLOAD_PATH = "/api/v1/knowledge-documents/parse-result/download"
PARSE_ONLY_DOC_PREFIX = "pdoc_"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _resolve_result_format(result_format: dict) -> dict:
    """返回格式兜底：缺省按方案默认 json。"""
    resolved = dict(result_format)
    resolved.setdefault("type", "json")
    return resolved


def _simulate_file_data(total_page: int) -> dict:
    """占位模拟：解析结果存储落地前生成结构化文件内容。"""
    return {
        "totalPage": total_page,
        "parsedPages": ["1-%d" % max(total_page, 1)],
        "pageList": [
            {
                "pageCount": 1,
                "pageContent": "占位解析内容（真实解析引擎接入后替换）",
                "pageImages": [],
            }
        ],
    }


class ParseService:
    @staticmethod
    def _generate_parse_only_doc_id() -> str:
        """生成 `pdoc_<17位数字>` 形态的免库独立解析临时文档标识。"""
        millis = int(time.time() * 1000)
        return f"pdoc_{millis:013d}{secrets.randbelow(10000):04d}"

    @staticmethod
    def _get_doc_or_raise(doc_id: str):
        doc = DocumentStore.get(doc_id)
        if doc is None:
            raise DocumentException(
                CommonErrorCodes.NOT_FOUND,
                {"field": "docId", "reason": f"文档不存在：{doc_id}"},
            )
        return doc

    @staticmethod
    def _get_parse_task_doc_or_raise(doc_id: str):
        """解析结果类接口的文档解析：知识库文档走 DocumentStore，免库任务（pdoc_ 前缀）走任务存储。"""
        if doc_id.startswith(PARSE_ONLY_DOC_PREFIX):
            task = ParseTaskStore.get_task_by_doc(doc_id)
            if task is None:
                raise DocumentException(
                    CommonErrorCodes.NOT_FOUND,
                    {"field": "docId", "reason": f"独立解析任务不存在：{doc_id}"},
                )
            return SimpleNamespace(
                doc_id=doc_id,
                kb_id="",
                owner_id=task.owner_id,
                tenant_id=task.tenant_id,
                is_parse_only=True,
            )
        return ParseService._get_doc_or_raise(doc_id)

    @staticmethod
    def _validate_personal_scope(doc, owner_id: str) -> None:
        """个人知识库仅创建者可执行解析与读取解析结果。"""
        kb_record = KnowledgeBaseService.get_or_raise(doc.kb_id)
        if kb_record.kb_type == "personal" and doc.owner_id != owner_id:
            raise DocumentException(
                CommonErrorCodes.FORBIDDEN,
                {"field": "docId", "reason": "个人知识库仅创建者可操作文档解析"},
            )

    @staticmethod
    def _validate_parse_doc_scope(doc, owner_id: str) -> None:
        """解析结果数据权限：免库任务仅创建者可查询/下载；知识库文档沿用个人库收敛规则。"""
        if getattr(doc, "is_parse_only", False):
            if doc.owner_id != owner_id:
                raise DocumentException(
                    CommonErrorCodes.FORBIDDEN,
                    {"field": "docId", "reason": "免库解析任务仅创建者可查询与下载"},
                )
            return
        ParseService._validate_personal_scope(doc, owner_id)

    @staticmethod
    def parse_direct(payload, *, owner_id: str = "", tenant_id: str = "") -> dict:
        """免知识库独立解析：直接解析传入来源，不创建知识库、不登记文档。"""
        doc_id = ParseService._generate_parse_only_doc_id()
        task_id = generate_parse_task_id()
        result_format = _resolve_result_format(payload.resultFormat)
        created_at = _now_iso()
        sync = (payload.executeMode or "").strip().lower() == "sync"

        if sync:
            # sync：请求内直接完成解析并返回内联结果
            total_page = 12
            ParseTaskStore.create_task(
                ParseTaskRecord(
                    task_id=task_id,
                    doc_id=doc_id,
                    kb_id="",
                    parse_status=PARSE_STATUS["SUCCESS"],
                    execute_mode="sync",
                    parse_strategy=dict(payload.parseStrategy),
                    result_format=result_format,
                    page_count=total_page,
                    chunk_count=total_page * 2,
                    owner_id=owner_id,
                    tenant_id=tenant_id,
                    created_at=created_at,
                    finished_at=created_at,
                )
            )
            ParseTaskStore.save_result(
                ParseResultRecord(
                    doc_id=doc_id,
                    task_id=task_id,
                    total_page=total_page,
                    parsed_pages=[f"1-{total_page}"],
                    page_list=[_simulate_file_data(total_page)["pageList"][0]],
                    summary="占位解析摘要",
                    keywords=["占位关键词"],
                    questions=["占位候选问句"],
                    tags=[],
                    result_format=result_format,
                )
            )
            return parse_direct_response(
                task_id=task_id,
                doc_id=doc_id,
                task_status=PARSE_STATUS["SUCCESS"],
                execute_mode="sync",
                result_inline={
                    "fileData": _simulate_file_data(total_page),
                    "tags": [],
                    "summary": "占位解析摘要",
                    "keywords": ["占位关键词"],
                    "questions": ["占位候选问句"],
                },
            )

        # async：登记 queued 任务，返回任务 ID 与临时文档 ID 供轮询/下载
        ParseTaskStore.create_task(
            ParseTaskRecord(
                task_id=task_id,
                doc_id=doc_id,
                kb_id="",
                parse_status=PARSE_STATUS["QUEUED"],
                execute_mode="async",
                parse_strategy=dict(payload.parseStrategy),
                result_format=result_format,
                owner_id=owner_id,
                tenant_id=tenant_id,
                created_at=created_at,
            )
        )
        return parse_direct_response(
            task_id=task_id,
            doc_id=doc_id,
            task_status=PARSE_STATUS["QUEUED"],
            execute_mode="async",
        )

    @staticmethod
    def parse(payload, *, owner_id: str = "", tenant_id: str = "") -> dict:
        doc = ParseService._get_doc_or_raise(payload.docId)
        ParseService._validate_personal_scope(doc, owner_id)

        requested_kb_id = (payload.kbId or "").strip()
        if requested_kb_id and requested_kb_id != doc.kb_id:
            raise ParseException(
                CommonErrorCodes.INVALID_PARAMS,
                {"field": "kbId", "reason": "kbId 与文档所属知识库不一致"},
            )

        result_format = _resolve_result_format(payload.resultFormat)
        existing = ParseTaskStore.get_task_by_doc(doc.doc_id)
        if existing is not None:
            # 幂等命中：queued/running 复用进行中任务，success 复用已完成任务；失败任务不允许重复发起
            if existing.parse_status in (
                PARSE_STATUS["QUEUED"],
                PARSE_STATUS["RUNNING"],
                PARSE_STATUS["SUCCESS"],
            ):
                return parse_response(
                    task_id=existing.task_id,
                    task_status=existing.parse_status,
                    execute_mode=existing.execute_mode,
                    result_inline={},
                )
            raise ParseException(
                ParseErrorCodes.PARSE_FAILED,
                {"field": "docId", "reason": f"解析任务失败：{existing.failed_reason or '未知原因'}"},
            )

        task_id = generate_parse_task_id()
        sync = (payload.executeMode or "").strip().lower() == "sync"
        created_at = _now_iso()

        if sync:
            # sync：请求内直接完成解析并返回内联结果
            total_page = 12
            ParseTaskStore.create_task(
                ParseTaskRecord(
                    task_id=task_id,
                    doc_id=doc.doc_id,
                    kb_id=doc.kb_id,
                    parse_status=PARSE_STATUS["SUCCESS"],
                    execute_mode="sync",
                    parse_strategy=dict(payload.parseStrategy),
                    result_format=result_format,
                    page_count=total_page,
                    chunk_count=total_page * 2,
                    owner_id=owner_id,
                    tenant_id=tenant_id,
                    created_at=created_at,
                    finished_at=created_at,
                )
            )
            ParseTaskStore.save_result(
                ParseResultRecord(
                    doc_id=doc.doc_id,
                    task_id=task_id,
                    total_page=total_page,
                    parsed_pages=[f"1-{total_page}"],
                    page_list=[_simulate_file_data(total_page)["pageList"][0]],
                    summary="占位解析摘要",
                    keywords=["占位关键词"],
                    questions=["占位候选问句"],
                    tags=list(doc.tags),
                    result_format=result_format,
                )
            )
            DocumentStore.update_status(doc.doc_id, DOCUMENT_STATUS["SUCCEEDED"])
            return parse_response(
                task_id=task_id,
                task_status=PARSE_STATUS["SUCCESS"],
                execute_mode="sync",
                result_inline={
                    "fileData": _simulate_file_data(total_page),
                    "tags": list(doc.tags),
                    "summary": "占位解析摘要",
                    "keywords": ["占位关键词"],
                    "questions": ["占位候选问句"],
                },
            )

        # async：登记 queued 任务，返回任务 ID 异步轮询
        ParseTaskStore.create_task(
            ParseTaskRecord(
                task_id=task_id,
                doc_id=doc.doc_id,
                kb_id=doc.kb_id,
                parse_status=PARSE_STATUS["QUEUED"],
                execute_mode="async",
                parse_strategy=dict(payload.parseStrategy),
                result_format=result_format,
                owner_id=owner_id,
                tenant_id=tenant_id,
                created_at=created_at,
            )
        )
        DocumentStore.update_status(doc.doc_id, DOCUMENT_STATUS["PARSING"])
        return parse_response(
            task_id=task_id,
            task_status=PARSE_STATUS["QUEUED"],
            execute_mode="async",
        )

    @staticmethod
    def query_parse_result(doc_id: str, *, owner_id: str = "", tenant_id: str = "") -> dict:
        doc = ParseService._get_parse_task_doc_or_raise(doc_id)
        ParseService._validate_parse_doc_scope(doc, owner_id)
        task = ParseTaskStore.get_task_by_doc(doc.doc_id)
        if task is None:
            raise ParseException(
                ParseErrorCodes.RESULT_NOT_READY,
                {"field": "docId", "reason": "该文档尚未发起解析任务，解析结果未就绪"},
            )
        return parse_result_query_response(
            parse_status=task.parse_status,
            result_format=task.result_format,
            page_count=task.page_count,
            chunk_count=task.chunk_count,
            failed_reason=task.failed_reason,
        )

    @staticmethod
    def issue_download_ticket(doc_id: str, *, owner_id: str = "", tenant_id: str = "") -> dict:
        doc = ParseService._get_parse_task_doc_or_raise(doc_id)
        ParseService._validate_parse_doc_scope(doc, owner_id)
        task = ParseTaskStore.get_task_by_doc(doc.doc_id)
        if task is None or task.parse_status != PARSE_STATUS["SUCCESS"]:
            raise ParseException(
                ParseErrorCodes.RESULT_NOT_READY,
                {"field": "docId", "reason": "解析结果尚未就绪，无法签发下载凭证"},
            )
        ticket = generate_ticket()
        expire_at = datetime.now(timezone.utc) + timedelta(seconds=600)
        expire_iso = expire_at.isoformat(timespec="seconds").replace("+00:00", "Z")
        ParseTicketStore.issue(
            ticket=ticket,
            doc_id=doc.doc_id,
            task_id=task.task_id,
            expire_at=expire_iso,
            expires_in=int(expire_at.timestamp()),
        )
        return issue_download_ticket_response(
            ticket=ticket,
            expire_at=expire_iso,
            download_path=DOWNLOAD_PATH,
        )

    @staticmethod
    def download_parse_result(doc_id: str, ticket: str, *, owner_id: str = "", tenant_id: str = "") -> dict:
        doc = ParseService._get_parse_task_doc_or_raise(doc_id)
        ParseService._validate_parse_doc_scope(doc, owner_id)
        record = ParseTicketStore.validate(ticket, datetime.now(timezone.utc).timestamp())
        if record is None:
            raise ParseException(
                ParseErrorCodes.TICKET_INVALID,
                {"field": "ticket", "reason": "下载凭证无效或已过期"},
            )
        if record.doc_id != doc.doc_id:
            raise ParseException(
                ParseErrorCodes.TICKET_INVALID,
                {"field": "docId", "reason": "下载凭证与文档不匹配"},
            )
        task = ParseTaskStore.get_task(record.task_id)
        if task is None:
            raise ParseException(
                ParseErrorCodes.TICKET_INVALID,
                {"field": "taskId", "reason": "下载凭证对应的解析任务不存在"},
            )
        return download_result_response(
            doc_id=doc.doc_id,
            task_id=task.task_id,
            download_path=DOWNLOAD_PATH,
            result_format=task.result_format,
        )
