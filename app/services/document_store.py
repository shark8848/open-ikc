from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any


class StoreNotFoundError(Exception):
    """目标记录不存在。"""


class StoreConflictError(Exception):
    """同范围存在重复业务键（如同知识库下重复登记文档）。"""


DOCUMENT_STATUS = {
    "PENDING": "PENDING",
    "INGESTING": "INGESTING",
    "INGESTED": "INGESTED",
    "PARSING": "PARSING",
    "SUCCEEDED": "SUCCEEDED",
    "FAILED": "FAILED",
}


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    doc_id: str
    kb_id: str
    ingest_task_id: str
    doc_title: str
    source_type: str
    source_url: str = ""
    object_key: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = DOCUMENT_STATUS["INGESTED"]
    owner_id: str = ""
    tenant_id: str = ""
    ingest_time: str = ""
    update_time: str | None = None


class DocumentStore:
    """进程内文档存储（占位实现，后续可替换为真实持久化存储）。

    仅负责原子读写与重复登记冲突判定，业务校验与异常语义由 service 层承担。
    """

    _lock = threading.Lock()
    _records: dict[str, DocumentRecord] = {}

    @classmethod
    def create(cls, record: DocumentRecord) -> DocumentRecord:
        with cls._lock:
            if cls._find_duplicate_registration(record):
                raise StoreConflictError(record.doc_title)
            cls._records[record.doc_id] = record
            return record

    @classmethod
    def get(cls, doc_id: str) -> DocumentRecord | None:
        with cls._lock:
            return cls._records.get(doc_id)

    @classmethod
    def list_by_kb(cls, kb_id: str) -> list[DocumentRecord]:
        with cls._lock:
            return [record for record in cls._records.values() if record.kb_id == kb_id]

    @classmethod
    def get_by_ingest_task(cls, ingest_task_id: str) -> DocumentRecord | None:
        with cls._lock:
            for record in cls._records.values():
                if record.ingest_task_id == ingest_task_id:
                    return record
            return None

    @classmethod
    def update_status(cls, doc_id: str, status: str, *, update_time: str | None = None) -> DocumentRecord | None:
        """更新文档接入/解析状态并刷新 update_time。"""
        with cls._lock:
            record = cls._records.get(doc_id)
            if record is None:
                return None
            updated = replace(record, status=status, update_time=update_time or record.update_time)
            cls._records[doc_id] = updated
            return updated

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._records.clear()

    @classmethod
    def _source_primary_key(cls, record: DocumentRecord) -> str:
        return record.object_key if record.source_type != "url" else record.source_url

    @classmethod
    def _find_duplicate_registration(cls, record: DocumentRecord) -> bool:
        source_key = cls._source_primary_key(record)
        for existing in cls._records.values():
            if existing.doc_id == record.doc_id:
                continue
            if existing.kb_id != record.kb_id:
                continue
            if existing.status not in (DOCUMENT_STATUS["INGESTED"], DOCUMENT_STATUS["PENDING"]):
                continue
            if existing.doc_title != record.doc_title:
                continue
            if cls._source_primary_key(existing) != source_key:
                continue
            return True
        return False


def generate_doc_id() -> str:
    millis = int(time.time() * 1000)
    return f"doc_{millis:013d}{secrets.randbelow(10000):04d}"


def generate_ingest_task_id() -> str:
    millis = int(time.time() * 1000)
    return f"ing_{millis:013d}{secrets.randbelow(10000):04d}"


def make_record(
    *,
    doc_id: str | None = None,
    kb_id: str,
    ingest_task_id: str,
    doc_title: str,
    source_type: str,
    source_url: str = "",
    object_key: str = "",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    status: str = DOCUMENT_STATUS["INGESTED"],
    owner_id: str = "",
    tenant_id: str = "",
    ingest_time: str = "",
    update_time: str | None = None,
) -> DocumentRecord:
    return DocumentRecord(
        doc_id=doc_id or generate_doc_id(),
        kb_id=kb_id,
        ingest_task_id=ingest_task_id,
        doc_title=doc_title,
        source_type=source_type,
        source_url=source_url,
        object_key=object_key,
        tags=list(tags) if tags else [],
        metadata=dict(metadata) if metadata else {},
        status=status,
        owner_id=owner_id,
        tenant_id=tenant_id,
        ingest_time=ingest_time,
        update_time=update_time,
    )
