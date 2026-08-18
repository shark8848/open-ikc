from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any


class StoreNotFoundError(Exception):
    """目标记录不存在。"""


class StoreConflictError(Exception):
    """同范围存在重复业务键（如知识库名称重复）。"""


@dataclass(frozen=True, slots=True)
class KnowledgeBaseRecord:
    kb_id: str
    kb_name: str
    kb_type: str
    team_id: str
    org_id: str
    kb_desc: str
    biz_domain: str
    visibility: str
    metadata_schema: list[dict[str, Any]]
    owner_id: str
    tenant_id: str
    scope_key: str
    create_time: str
    update_time: str | None = None
    kb_mode: str = "text"
    wiki_config: dict[str, Any] = field(default_factory=dict)
    graph_schema: dict[str, Any] = field(default_factory=dict)


class KnowledgeBaseStore:
    """进程内知识库存储（占位实现，后续可替换为真实持久化存储）。

    仅负责原子读写与唯一键冲突判定，业务校验与异常语义由 service 层承担。
    """

    _lock = threading.Lock()
    _records: dict[str, KnowledgeBaseRecord] = {}

    @classmethod
    def create(cls, record: KnowledgeBaseRecord) -> KnowledgeBaseRecord:
        with cls._lock:
            if cls._find_duplicate_scope_name(record.kb_name, record.scope_key, exclude_kb_id=None):
                raise StoreConflictError(record.kb_name)
            cls._records[record.kb_id] = record
            return record

    @classmethod
    def update(cls, record: KnowledgeBaseRecord) -> KnowledgeBaseRecord:
        with cls._lock:
            existing = cls._records.get(record.kb_id)
            if existing is None:
                raise StoreNotFoundError(record.kb_id)
            if cls._find_duplicate_scope_name(record.kb_name, record.scope_key, exclude_kb_id=record.kb_id):
                raise StoreConflictError(record.kb_name)
            cls._records[record.kb_id] = record
            return record

    @classmethod
    def get(cls, kb_id: str) -> KnowledgeBaseRecord | None:
        with cls._lock:
            return cls._records.get(kb_id)

    @classmethod
    def list_records(cls, *, keyword: str = "") -> list[KnowledgeBaseRecord]:
        keyword_lower = keyword.strip().lower()
        with cls._lock:
            records = []
            for record in cls._records.values():
                if keyword_lower and keyword_lower not in record.kb_name.lower() and keyword_lower not in record.kb_desc.lower():
                    continue
                records.append(record)
            return records

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._records.clear()

    @classmethod
    def _find_duplicate_scope_name(cls, kb_name: str, scope_key: str, exclude_kb_id: str | None) -> bool:
        for record in cls._records.values():
            if record.kb_id == exclude_kb_id:
                continue
            if record.kb_name == kb_name and record.scope_key == scope_key:
                return True
        return False


def generate_kb_id() -> str:
    millis = int(time.time() * 1000)
    return f"kb_{millis:013d}{secrets.randbelow(10000):04d}"


def make_record(
    *,
    kb_id: str | None = None,
    kb_name: str,
    kb_type: str,
    team_id: str,
    org_id: str,
    kb_desc: str,
    biz_domain: str,
    visibility: str,
    metadata_schema: list[dict[str, Any]],
    owner_id: str,
    tenant_id: str,
    scope_key: str,
    create_time: str,
    update_time: str | None = None,
    kb_mode: str = "text",
    wiki_config: dict[str, Any] | None = None,
    graph_schema: dict[str, Any] | None = None,
) -> KnowledgeBaseRecord:
    return KnowledgeBaseRecord(
        kb_id=kb_id or generate_kb_id(),
        kb_name=kb_name,
        kb_type=kb_type,
        kb_mode=kb_mode,
        team_id=team_id,
        org_id=org_id,
        kb_desc=kb_desc,
        biz_domain=biz_domain,
        visibility=visibility,
        metadata_schema=list(metadata_schema),
        owner_id=owner_id,
        tenant_id=tenant_id,
        scope_key=scope_key,
        create_time=create_time,
        update_time=update_time,
        wiki_config=dict(wiki_config or {}),
        graph_schema=dict(graph_schema or {}),
    )
