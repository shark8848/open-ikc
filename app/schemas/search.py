from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class SearchQueryRequest(BaseModel):
    query: str = Field("", description="检索问题或关键词。")
    kbId: str = Field("", description="目标知识库 ID。用于数据权限资源匹配。")
    kbIds: list[str] = Field(default_factory=list, description="目标知识库 ID 列表。用于多库联合检索的数据权限判定。")
    teamId: str = Field("", description="目标知识库类型为 team 时建议传入，用于团队归属校验。")
    orgId: str = Field("", description="目标知识库类型为 enterprise 时建议传入，用于组织范围校验。")
    ownerId: str = Field("", description="资源所有者 ID。用于 owner_only 场景判定。")
    orgPath: str = Field("", description="组织路径，如 /集团/销售中心/华东。用于组织范围判定。")
    mode: str = Field("qa", description="检索模式：search（仅返回证据）或 qa（带问答回答）。")
    topK: int = Field(5, description="返回证据数量上限。")
    filters: dict = Field(default_factory=dict, description="元数据过滤条件。")
    withCitation: bool = Field(True, description="是否返回引用信息。")

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"search", "qa"}:
            raise ValueError("mode 仅支持 search / qa")
        return cleaned

    @field_validator("topK")
    @classmethod
    def _validate_top_k(cls, value: int) -> int:
        if value < 1:
            raise ValueError("topK 必须大于等于 1")
        if value > 100:
            raise ValueError("topK 不能超过 100")
        return value

    @model_validator(mode="after")
    def _validate_kb_scope(self) -> "SearchQueryRequest":
        if not self.kbId.strip() and not self.kbIds:
            raise ValueError("kbId / kbIds 至少提供一个目标知识库")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "2026 产品白皮书的核心能力是什么？",
                "kbId": "kb_10001",
                "kbIds": ["kb_10001", "kb_10002"],
                "ownerId": "u100",
                "orgPath": "/集团/销售中心/华东",
                "mode": "qa",
                "topK": 5,
                "filters": {"docType": "whitepaper"},
                "withCitation": True,
            }
        }
    }


class SearchResultItemData(BaseModel):
    docId: str = Field(..., description="文档 ID。")
    docTitle: str = Field("", description="文档标题。")
    score: float = Field(0.0, description="相关性分值。")
    snippet: str = Field("", description="命中片段。")
    citation: dict = Field(default_factory=dict, description="引用信息（页码/位置）。")


class SearchQueryData(BaseModel):
    answer: str = Field("", description="问答模式下的回答。")
    total: int = Field(0, description="命中证据总数。")
    results: list[SearchResultItemData] = Field(default_factory=list, description="检索结果列表。")


class SearchQueryResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: SearchQueryData = Field(..., description="业务数据。")
