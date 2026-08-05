from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
