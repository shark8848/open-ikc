from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SOURCE_FIELDS = {"type", "url", "objectKey", "fileToken", "archive", "directory", "metadata"}


@dataclass
class DocumentSource:
    """文档来源对象：url / file / directory / archive 四种形态。"""

    type: str = "file"
    url: str = ""
    objectKey: str = ""
    fileToken: str = ""
    archive: dict[str, Any] = field(default_factory=dict)
    directory: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentSource":
        return cls(
            type=str(data.get("type", "file")),
            url=str(data.get("url", "")),
            objectKey=str(data.get("objectKey", "")),
            fileToken=str(data.get("fileToken", "")),
            archive=dict(data.get("archive") or {}),
            directory=dict(data.get("directory") or {}),
            metadata=dict(data.get("metadata") or {}),
            extra={key: value for key, value in data.items() if key not in _SOURCE_FIELDS},
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type,
            "url": self.url,
            "objectKey": self.objectKey,
            "fileToken": self.fileToken,
            "archive": dict(self.archive),
            "directory": dict(self.directory),
            "metadata": dict(self.metadata),
        }
        result.update(self.extra)
        return result


_INGEST_RESULT_FIELDS = {
    "ingestTaskId",
    "docId",
    "docIds",
    "taskStatus",
    "sourceType",
    "sourceStats",
    "ingestTime",
}


@dataclass
class DocumentIngestResult:
    """接入知识源结果（对应平台 DocumentIngestData）。"""

    ingestTaskId: str
    taskStatus: str
    sourceType: str
    ingestTime: str
    docId: str | None = None
    docIds: list[str] = field(default_factory=list)
    sourceStats: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentIngestResult":
        return cls(
            ingestTaskId=str(data.get("ingestTaskId", "")),
            docId=data.get("docId"),
            docIds=list(data.get("docIds") or []),
            taskStatus=str(data.get("taskStatus", "")),
            sourceType=str(data.get("sourceType", "")),
            sourceStats=dict(data.get("sourceStats") or {}),
            ingestTime=str(data.get("ingestTime", "")),
            extra={key: value for key, value in data.items() if key not in _INGEST_RESULT_FIELDS},
        )


_INGEST_AND_PARSE_FIELDS = {
    "ingestTaskId",
    "parseTaskId",
    "docId",
    "taskStatus",
    "executeMode",
    "resultInline",
}


@dataclass
class DocumentIngestAndParseResult:
    """一体化接入并解析结果（对应平台 DocumentIngestAndParseData）。"""

    ingestTaskId: str
    parseTaskId: str
    taskStatus: str
    executeMode: str
    docId: str | None = None
    resultInline: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentIngestAndParseResult":
        return cls(
            ingestTaskId=str(data.get("ingestTaskId", "")),
            parseTaskId=str(data.get("parseTaskId", "")),
            docId=data.get("docId"),
            taskStatus=str(data.get("taskStatus", "")),
            executeMode=str(data.get("executeMode", "")),
            resultInline=dict(data.get("resultInline") or {}),
            extra={key: value for key, value in data.items() if key not in _INGEST_AND_PARSE_FIELDS},
        )


_DOCUMENT_INFO_FIELDS = {
    "docId",
    "docTitle",
    "kbId",
    "sourceType",
    "sourceUrl",
    "objectKey",
    "tags",
    "metadata",
    "status",
    "ingestTime",
    "updateTime",
}


@dataclass
class DocumentInfo:
    """文档信息（对应平台 DocumentInfoData）。"""

    docId: str
    docTitle: str = ""
    kbId: str = ""
    sourceType: str = ""
    sourceUrl: str = ""
    objectKey: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = ""
    ingestTime: str = ""
    updateTime: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentInfo":
        return cls(
            docId=str(data.get("docId", "")),
            docTitle=str(data.get("docTitle", "")),
            kbId=str(data.get("kbId", "")),
            sourceType=str(data.get("sourceType", "")),
            sourceUrl=str(data.get("sourceUrl", "")),
            objectKey=str(data.get("objectKey", "")),
            tags=list(data.get("tags") or []),
            metadata=dict(data.get("metadata") or {}),
            status=str(data.get("status", "")),
            ingestTime=str(data.get("ingestTime", "")),
            updateTime=data.get("updateTime"),
            extra={key: value for key, value in data.items() if key not in _DOCUMENT_INFO_FIELDS},
        )
