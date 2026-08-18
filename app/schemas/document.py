from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.parse import validate_parse_strategy, validate_result_format
from app.schemas.source import DocumentSource


class DocumentIngestRequest(BaseModel):
    reqId: str = Field("", description="幂等请求标识，建议调用方传入；为空时服务端自动生成。")
    kbId: str = Field(..., description="目标知识库 ID。")
    teamId: str = Field("", description="当目标知识库类型为 team 时建议传入，用于团队归属校验。")
    orgId: str = Field("", description="当目标知识库类型为 enterprise 时建议传入，用于租户与组织隔离。")
    source: DocumentSource = Field(..., description="来源对象，支持 url/file/directory/archive 四种形态。")
    docTitle: str = Field("", description="文档标题；为空时由服务端按来源自动推断。")
    tags: list[str] = Field(default_factory=list, description="标签列表，用于检索与分类。")
    metadata: dict = Field(default_factory=dict, description="自定义业务元数据。")
    orchestrationMode: Literal["split", "quick"] = Field(
        "split",
        description="接入与解析编排模式：split 仅接入不自动解析（默认），quick 接入后自动触发解析。",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reqId": "req_ing_20260803_0001",
                "kbId": "kb_10001",
                "teamId": "",
                "orgId": "",
                "source": {
                    "type": "archive",
                    "objectKey": "oss://bucket/contracts_2026.zip",
                    "archive": {
                        "format": "zip",
                        "includePattern": ["**/*.pdf", "**/*.docx"],
                    },
                },
                "docTitle": "",
                "tags": ["合同", "2026"],
                "metadata": {},
                "orchestrationMode": "split",
            }
        }
    )

    @model_validator(mode="after")
    def validate_source_fields(self) -> "DocumentIngestRequest":
        source = self.source
        if source.type == "url" and not source.url.strip():
            raise ValueError("source.type=url 时 source.url 必填")
        if source.type == "file" and not source.objectKey.strip() and not source.fileToken.strip():
            raise ValueError("source.type=file 时 objectKey 或 fileToken 至少一个非空")
        if source.type in {"directory", "archive"} and not source.objectKey.strip():
            raise ValueError("source.type=directory/archive 时 objectKey 必填")
        return self


class DocumentIngestAndParseRequest(DocumentIngestRequest):
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
        description="执行方式：async 异步返回任务 ID（默认），sync 同步内联返回解析结果。",
    )

    @model_validator(mode="after")
    def validate_parse_options(self) -> "DocumentIngestAndParseRequest":
        validate_parse_strategy(self.parseStrategy)
        validate_result_format(self.resultFormat)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reqId": "req_quick_20260803_0001",
                "kbId": "kb_10001",
                "teamId": "",
                "orgId": "",
                "source": {
                    "type": "url",
                    "url": "https://example.com/files/spec.pdf",
                },
                "docTitle": "",
                "tags": [],
                "metadata": {},
                "orchestrationMode": "split",
                "parseStrategy": {
                    "docType": "pdf",
                    "parseMethod": "auto",
                },
                "resultFormat": {
                    "type": "json",
                    "includeLayout": True,
                },
                "executeMode": "async",
            }
        }
    )


class _DocumentEnvelope(BaseModel):
    """统一响应体外壳：errCode / errMsg / traceId + data 业务数据。"""

    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: dict = Field(..., description="业务数据。")


class DocumentIngestData(BaseModel):
    ingestTaskId: str = Field(..., description="接入任务 ID。")
    docId: str | None = Field(None, description="单文档场景返回的文档 ID。")
    docIds: list[str] = Field(default_factory=list, description="目录/压缩包场景返回的文档 ID 列表。")
    taskStatus: str = Field(
        ...,
        description="任务状态：PENDING/INGESTING/INGESTED/SUCCEEDED/PARTIAL_FAILED/FAILED。",
    )
    sourceType: str = Field(..., description="来源类型：url/file/directory/archive。")
    sourceStats: dict = Field(default_factory=dict, description="来源统计：总文件数、成功数、失败数。")
    ingestTime: str = Field(..., description="接入时间。")


class DocumentIngestResponse(_DocumentEnvelope):
    data: DocumentIngestData = Field(..., description="业务数据。")


class DocumentIngestAndParseData(BaseModel):
    ingestTaskId: str = Field(..., description="接入任务 ID。")
    parseTaskId: str = Field(..., description="解析任务 ID。")
    docId: str | None = Field(None, description="文档 ID。")
    taskStatus: str = Field(..., description="任务状态：PENDING/INGESTING/PARSING/SUCCEEDED/FAILED。")
    executeMode: str = Field(..., description="执行方式：sync/async。")
    resultInline: dict = Field(default_factory=dict, description="executeMode=sync 时返回的内联解析结果；async 为空对象。")


class DocumentIngestAndParseResponse(_DocumentEnvelope):
    data: DocumentIngestAndParseData = Field(..., description="业务数据。")


class DocumentInfoData(BaseModel):
    docId: str = Field(..., description="文档 ID。")
    docTitle: str = Field("", description="文档标题。")
    kbId: str = Field("", description="所属知识库 ID。")
    sourceType: str = Field("", description="来源类型：url/file/directory/archive。")
    sourceUrl: str = Field("", description="来源 URL。")
    objectKey: str = Field("", description="来源对象标识，如 OSS 对象路径。")
    tags: list[str] = Field(default_factory=list, description="标签列表。")
    metadata: dict = Field(default_factory=dict, description="自定义业务元数据。")
    status: str = Field("", description="文档接入/解析状态。")
    ingestTime: str = Field("", description="接入时间。")
    updateTime: str | None = Field(None, description="更新时间。")


class DocumentInfoResponse(_DocumentEnvelope):
    data: DocumentInfoData = Field(..., description="业务数据。")
