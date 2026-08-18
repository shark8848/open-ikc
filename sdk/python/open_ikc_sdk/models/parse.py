from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_PARSE_TASK_FIELDS = {"taskId", "taskStatus", "executeMode", "resultInline"}


@dataclass
class ParseTask:
    """解析任务（对应平台 DocumentParseResponse.data）。"""

    taskId: str
    taskStatus: str
    executeMode: str
    resultInline: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParseTask":
        return cls(
            taskId=str(data.get("taskId", "")),
            taskStatus=str(data.get("taskStatus", "")),
            executeMode=str(data.get("executeMode", "")),
            resultInline=dict(data.get("resultInline") or {}),
            extra={key: value for key, value in data.items() if key not in _PARSE_TASK_FIELDS},
        )


_PARSE_RESULT_FIELDS = {"parseStatus", "resultFormat", "pageCount", "chunkCount", "failedReason"}


@dataclass
class ParseResult:
    """解析结果摘要（对应平台 ParseResultQueryData）。"""

    parseStatus: str
    resultFormat: dict[str, Any] = field(default_factory=dict)
    pageCount: int = 0
    chunkCount: int = 0
    failedReason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParseResult":
        return cls(
            parseStatus=str(data.get("parseStatus", "")),
            resultFormat=dict(data.get("resultFormat") or {}),
            pageCount=int(data.get("pageCount") or 0),
            chunkCount=int(data.get("chunkCount") or 0),
            failedReason=str(data.get("failedReason", "")),
            extra={key: value for key, value in data.items() if key not in _PARSE_RESULT_FIELDS},
        )


_PARSE_DIRECT_FIELDS = {"taskId", "docId", "taskStatus", "executeMode", "resultInline"}


@dataclass
class ParseDirectResult:
    """免知识库独立解析结果（对应平台 ParseDirectResponse.data）。"""

    taskId: str
    docId: str
    taskStatus: str
    executeMode: str
    resultInline: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParseDirectResult":
        return cls(
            taskId=str(data.get("taskId", "")),
            docId=str(data.get("docId", "")),
            taskStatus=str(data.get("taskStatus", "")),
            executeMode=str(data.get("executeMode", "")),
            resultInline=dict(data.get("resultInline") or {}),
            extra={key: value for key, value in data.items() if key not in _PARSE_DIRECT_FIELDS},
        )


_DOWNLOAD_TICKET_FIELDS = {"ticket", "expireAt", "downloadPath"}


@dataclass
class DownloadTicket:
    """解析结果下载凭证（对应平台 IssueDownloadTicketData）。"""

    ticket: str
    expireAt: str
    downloadPath: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadTicket":
        return cls(
            ticket=str(data.get("ticket", "")),
            expireAt=str(data.get("expireAt", "")),
            downloadPath=str(data.get("downloadPath", "")),
            extra={key: value for key, value in data.items() if key not in _DOWNLOAD_TICKET_FIELDS},
        )


_DOWNLOAD_RESULT_FIELDS = {"docId", "taskId", "downloadPath", "format", "note"}


@dataclass
class DownloadResult:
    """下载结果信息（对应平台 DownloadResultData；文件流落地前为统一体元数据）。"""

    docId: str
    taskId: str
    downloadPath: str
    format: str = "json"
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadResult":
        return cls(
            docId=str(data.get("docId", "")),
            taskId=str(data.get("taskId", "")),
            downloadPath=str(data.get("downloadPath", "")),
            format=str(data.get("format", "json")),
            note=str(data.get("note", "")),
            extra={key: value for key, value in data.items() if key not in _DOWNLOAD_RESULT_FIELDS},
        )
