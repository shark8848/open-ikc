from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any


class ParseTaskNotFoundError(Exception):
    """解析任务不存在。"""


class TicketExpiredError(Exception):
    """下载凭证无效或已过期。"""


PARSE_STATUS = {
    "QUEUED": "queued",
    "RUNNING": "running",
    "SUCCESS": "success",
    "FAILED": "failed",
}


@dataclass(frozen=True, slots=True)
class ParseTaskRecord:
    task_id: str
    doc_id: str
    kb_id: str
    parse_status: str = PARSE_STATUS["QUEUED"]
    execute_mode: str = "async"
    parse_strategy: dict[str, Any] = field(default_factory=dict)
    result_format: dict[str, Any] = field(default_factory=dict)
    page_count: int = 0
    chunk_count: int = 0
    failed_reason: str = ""
    owner_id: str = ""
    tenant_id: str = ""
    created_at: str = ""
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class ParseResultRecord:
    doc_id: str
    task_id: str
    total_page: int = 0
    parsed_pages: list[str] = field(default_factory=list)
    page_list: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    result_format: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseTicketRecord:
    ticket: str
    doc_id: str
    task_id: str
    expire_at: str
    expires_in: int


def generate_parse_task_id() -> str:
    """生成 `parse_<17位数字>` 形态的解析任务 ID（与文档域 ingest 任务形态一致）。"""
    millis = int(time.time() * 1000)
    return f"parse_{millis:013d}{secrets.randbelow(10000):04d}"


def generate_ticket() -> str:
    return f"dlt_{secrets.token_urlsafe(24)}"


class ParseTaskStore:
    """进程内解析任务与解析结果存储（占位实现，后续可替换为真实持久化）。

    仅负责原子读写，业务校验与异常语义由 service 层承担。
    """

    _lock = threading.Lock()
    _tasks: dict[str, ParseTaskRecord] = {}
    _results: dict[str, ParseResultRecord] = {}
    _doc_task_index: dict[str, str] = {}

    @classmethod
    def create_task(cls, record: ParseTaskRecord) -> ParseTaskRecord:
        with cls._lock:
            cls._tasks[record.task_id] = record
            cls._doc_task_index[record.doc_id] = record.task_id
            return record

    @classmethod
    def get_task(cls, task_id: str) -> ParseTaskRecord | None:
        with cls._lock:
            return cls._tasks.get(task_id)

    @classmethod
    def get_task_by_doc(cls, doc_id: str) -> ParseTaskRecord | None:
        with cls._lock:
            task_id = cls._doc_task_index.get(doc_id)
            if task_id is None:
                return None
            return cls._tasks.get(task_id)

    @classmethod
    def update_task(cls, task_id: str, **changes: Any) -> ParseTaskRecord | None:
        with cls._lock:
            record = cls._tasks.get(task_id)
            if record is None:
                return None
            updated = replace(record, **changes)
            cls._tasks[task_id] = updated
            return updated

    @classmethod
    def save_result(cls, result: ParseResultRecord) -> ParseResultRecord:
        with cls._lock:
            cls._results[result.task_id] = result
            return result

    @classmethod
    def get_result(cls, task_id: str) -> ParseResultRecord | None:
        with cls._lock:
            return cls._results.get(task_id)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._tasks.clear()
            cls._results.clear()
            cls._doc_task_index.clear()


class ParseTicketStore:
    """进程内下载凭证存储（占位实现）。凭证为一次性短期票据，过期即失效。"""

    _lock = threading.Lock()
    _tickets: dict[str, ParseTicketRecord] = {}

    @classmethod
    def issue(cls, ticket: str, doc_id: str, task_id: str, expire_at: str, expires_in: int) -> ParseTicketRecord:
        record = ParseTicketRecord(
            ticket=ticket,
            doc_id=doc_id,
            task_id=task_id,
            expire_at=expire_at,
            expires_in=expires_in,
        )
        with cls._lock:
            cls._tickets[ticket] = record
            return record

    @classmethod
    def validate(cls, ticket: str, now_ts: float) -> ParseTicketRecord | None:
        """一次性凭证校验：命中即消费（删除），不存在或已过期返回 None。"""
        with cls._lock:
            record = cls._tickets.pop(ticket, None)
            if record is None:
                return None
            if now_ts > record.expires_in:
                return None
            return record

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._tickets.clear()
