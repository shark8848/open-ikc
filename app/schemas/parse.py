from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.source import DocumentSource

PARSE_DOC_TYPES = {"auto", "pdf", "docx", "xlsx", "pptx", "txt", "md", "html", "jpg", "png"}
PARSE_METHODS = {"auto", "ocr", "txt"}
PARSE_BACKENDS = {"pipeline", "vllm-engine"}
PARSE_MODES = {"auto", "ocr", "structure"}
CHUNK_STRATEGIES = {"auto", "fixed", "semantic"}
RESULT_FORMAT_TYPES = {"json", "markdown", "text"}
IMAGE_ENCODINGS = {"url", "base64"}
_PAGE_RANGE_PATTERN = re.compile(r"\d+(-\d+)?")


def _validate_parse_strategy(strategy: dict[str, Any]) -> None:
    """parseStrategy 枚举与范围校验：docType/parseMethod/backend/pageRange/chunking。"""
    doc_type = strategy.get("docType")
    if doc_type is not None and doc_type not in PARSE_DOC_TYPES:
        raise ValueError(
            f"parseStrategy.docType 非法：{doc_type}（可选：{'/'.join(sorted(PARSE_DOC_TYPES))}）"
        )
    parse_method = strategy.get("parseMethod")
    if parse_method is not None and parse_method not in PARSE_METHODS:
        raise ValueError(
            f"parseStrategy.parseMethod 非法：{parse_method}（可选：{'/'.join(sorted(PARSE_METHODS))}）"
        )
    backend = strategy.get("backend")
    if backend is not None and backend not in PARSE_BACKENDS:
        raise ValueError(
            f"parseStrategy.backend 非法：{backend}（可选：{'/'.join(sorted(PARSE_BACKENDS))}）"
        )
    page_range = strategy.get("pageRange")
    if page_range is not None:
        if not isinstance(page_range, list) or not all(
            isinstance(item, str) and _PAGE_RANGE_PATTERN.fullmatch(item.strip()) for item in page_range
        ):
            raise ValueError('parseStrategy.pageRange 格式非法（示例：["1","2","4-8"]）')
    chunking = strategy.get("chunking")
    if isinstance(chunking, dict):
        for field_name in (
            "chunkSize",
            "chunkOverlap",
            "parentChunkSize",
            "parentChunkOverlap",
            "audioVideoChunkDuration",
        ):
            value = chunking.get(field_name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"parseStrategy.chunking.{field_name} 必须为非负整数")


def validate_parse_strategy(strategy: dict[str, Any]) -> None:
    """解析策略入参校验入口（Parse 请求与 ingest-and-parse 共用）。"""
    if isinstance(strategy, dict):
        _validate_parse_strategy(strategy)


def validate_result_format(result_format: dict[str, Any]) -> None:
    """返回格式枚举校验：type/imageEncoding。"""
    if not isinstance(result_format, dict):
        return
    fmt_type = result_format.get("type")
    if fmt_type is not None and fmt_type not in RESULT_FORMAT_TYPES:
        raise ValueError(f"resultFormat.type 非法：{fmt_type}（可选：{'/'.join(sorted(RESULT_FORMAT_TYPES))}）")
    image_encoding = result_format.get("imageEncoding")
    if image_encoding is not None and image_encoding not in IMAGE_ENCODINGS:
        raise ValueError(f"resultFormat.imageEncoding 非法：{image_encoding}（可选：{'/'.join(sorted(IMAGE_ENCODINGS))}）")


class DocumentParseRequest(BaseModel):
    reqId: str = Field("", description="幂等请求标识，建议调用方传入；为空时服务端自动生成。")
    kbId: str = Field(..., description="知识库 ID。")
    docId: str = Field(..., description="文档 ID。")
    parseStrategy: dict = Field(
        default_factory=dict,
        description="解析策略对象：docType/parseMethod/backend/pageRange/chunking/enhancement 等，透传。",
    )
    resultFormat: dict = Field(
        default_factory=dict,
        description="返回格式对象：type/includeLayout/includeImages/imageEncoding 等，透传。",
    )
    executeMode: Literal["sync", "async"] = Field(
        "async",
        description="执行方式：sync 请求内返回内联结果，async 返回任务 ID 异步轮询。",
    )
    parseMode: str = Field("auto", description="解析模式：auto/ocr/structure。")
    chunkStrategy: str = Field("auto", description="分段策略：auto/fixed/semantic。")
    chunkSize: int = Field(800, description="分段长度，chunkStrategy=fixed 时生效。")

    @model_validator(mode="after")
    def validate_parse_options(self) -> "DocumentParseRequest":
        validate_parse_strategy(self.parseStrategy)
        validate_result_format(self.resultFormat)
        if self.parseMode not in PARSE_MODES:
            raise ValueError(f"parseMode 非法：{self.parseMode}（可选：{'/'.join(sorted(PARSE_MODES))}）")
        if self.chunkStrategy not in CHUNK_STRATEGIES:
            raise ValueError(
                f"chunkStrategy 非法：{self.chunkStrategy}（可选：{'/'.join(sorted(CHUNK_STRATEGIES))}）"
            )
        if isinstance(self.chunkSize, bool) or self.chunkSize < 0:
            raise ValueError("chunkSize 必须为非负整数")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reqId": "req_parse_20260803_0001",
                "kbId": "kb_10001",
                "docId": "doc_10001",
                "parseStrategy": {
                    "docType": "pdf",
                    "parseMethod": "auto",
                },
                "resultFormat": {
                    "type": "json",
                    "includeLayout": True,
                },
                "executeMode": "async",
                "parseMode": "auto",
                "chunkStrategy": "auto",
                "chunkSize": 800,
            }
        }
    )


class ParseDirectRequest(BaseModel):
    """免知识库独立解析请求：直接传入来源解析，不创建知识库、不登记文档。"""

    reqId: str = Field("", description="幂等请求标识，建议调用方传入；为空时服务端自动生成。")
    source: DocumentSource = Field(
        ...,
        description="待解析来源对象，支持 url/file/directory/archive；免知识库，不登记文档。",
    )
    parseStrategy: dict = Field(
        default_factory=dict,
        description="解析策略对象：docType/parseMethod/backend/pageRange/chunking/enhancement 等，透传。",
    )
    resultFormat: dict = Field(
        default_factory=dict,
        description="返回格式对象：type/includeLayout/includeImages/imageEncoding 等，透传。",
    )
    executeMode: Literal["sync", "async"] = Field(
        "async",
        description="执行方式：sync 请求内返回内联结果，async 返回任务 ID 后经 parse-result 系列接口轮询/下载。",
    )
    parseMode: str = Field("auto", description="解析模式：auto/ocr/structure。")
    chunkStrategy: str = Field("auto", description="分段策略：auto/fixed/semantic。")
    chunkSize: int = Field(800, description="分段长度，chunkStrategy=fixed 时生效。")

    @model_validator(mode="after")
    def validate_options(self) -> "ParseDirectRequest":
        validate_parse_strategy(self.parseStrategy)
        validate_result_format(self.resultFormat)
        if self.parseMode not in PARSE_MODES:
            raise ValueError(f"parseMode 非法：{self.parseMode}（可选：{'/'.join(sorted(PARSE_MODES))}）")
        if self.chunkStrategy not in CHUNK_STRATEGIES:
            raise ValueError(
                f"chunkStrategy 非法：{self.chunkStrategy}（可选：{'/'.join(sorted(CHUNK_STRATEGIES))}）"
            )
        if isinstance(self.chunkSize, bool) or self.chunkSize < 0:
            raise ValueError("chunkSize 必须为非负整数")
        source = self.source
        if source.type == "url" and not source.url.strip():
            raise ValueError("source.type=url 时 source.url 必填")
        if source.type == "file" and not source.objectKey.strip() and not source.fileToken.strip():
            raise ValueError("source.type=file 时 objectKey 或 fileToken 至少一个非空")
        if source.type in {"directory", "archive"} and not source.objectKey.strip():
            raise ValueError("source.type=directory/archive 时 objectKey 必填")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reqId": "req_parse_direct_20260818_0001",
                "source": {"type": "url", "url": "https://example.com/contract.pdf"},
                "parseStrategy": {"docType": "pdf", "parseMethod": "auto"},
                "resultFormat": {"type": "json", "includeLayout": True},
                "executeMode": "sync",
                "parseMode": "auto",
                "chunkStrategy": "auto",
                "chunkSize": 800,
            }
        }
    )


class _ParseEnvelope(BaseModel):
    """统一响应体外壳：errCode / errMsg / traceId + data 业务数据。"""

    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: dict = Field(..., description="业务数据。")


class ParseResultInlineData(BaseModel):
    """executeMode=sync 时返回的模拟内联解析结果。"""

    fileData: dict = Field(default_factory=dict, description="结构化文件内容（含 totalPage/parsedPages/pageList）。")
    tags: list[str] = Field(default_factory=list, description="标签。")
    summary: str = Field("", description="摘要。")
    keywords: list[str] = Field(default_factory=list, description="关键词。")
    questions: list[str] = Field(default_factory=list, description="候选问句。")


class DocumentParseData(BaseModel):
    taskId: str = Field(..., description="解析任务 ID。")
    taskStatus: str = Field(..., description="任务状态：queued/running/success/failed。")
    executeMode: str = Field(..., description="执行方式：sync/async。")
    resultInline: dict = Field(default_factory=dict, description="executeMode=sync 时返回的内联解析结果；async 为空对象。")


class DocumentParseResponse(_ParseEnvelope):
    data: DocumentParseData = Field(..., description="解析任务信息。")


class ParseDirectData(BaseModel):
    taskId: str = Field(..., description="解析任务 ID。")
    docId: str = Field(..., description="本次独立解析生成的临时文档标识（pdoc_ 前缀），仅用于后续轮询/凭证/下载。")
    taskStatus: str = Field(..., description="任务状态：queued/running/success/failed。")
    executeMode: str = Field(..., description="执行方式：sync/async。")
    resultInline: dict = Field(default_factory=dict, description="executeMode=sync 时返回的内联解析结果；async 为空对象。")


class ParseDirectResponse(_ParseEnvelope):
    data: ParseDirectData = Field(..., description="独立解析任务信息。")


class ParseResultQueryData(BaseModel):
    parseStatus: str = Field(..., description="解析状态：queued/running/success/failed。")
    resultFormat: dict = Field(default_factory=dict, description="返回格式对象。")
    pageCount: int = Field(0, description="页数。")
    chunkCount: int = Field(0, description="分段数。")
    failedReason: str = Field("", description="失败原因，成功时为空。")


class ParseResultQueryResponse(_ParseEnvelope):
    data: ParseResultQueryData = Field(..., description="解析结果摘要。")


class IssueDownloadTicketData(BaseModel):
    ticket: str = Field(..., description="下载凭证。")
    expireAt: str = Field(..., description="凭证过期时间。")
    downloadPath: str = Field(..., description="下载接口相对路径。")


class IssueDownloadTicketResponse(_ParseEnvelope):
    data: IssueDownloadTicketData = Field(..., description="凭证信息。")


class DownloadResultData(BaseModel):
    docId: str = Field(..., description="文档 ID。")
    taskId: str = Field(..., description="解析任务 ID。")
    downloadPath: str = Field(..., description="下载接口相对路径。")
    format: str = Field("json", description="结果格式。")
    note: str = Field("", description="占位说明：真实解析结果存储落地前返回统一体，后续切换为文件流。")


class DownloadResultResponse(_ParseEnvelope):
    data: DownloadResultData = Field(..., description="下载信息（占位阶段）。")
