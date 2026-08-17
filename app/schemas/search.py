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
    mode: str = Field("qa", description="检索模式：search（仅返回证据）或 qa（附简短回答）。")
    searchType: str = Field("hybrid", description="检索类型：fulltext（全文）/ vector（向量）/ hybrid（混合）。")
    relNum: int = Field(0, description="关联召回数量（0~200），追加召回相关片段。")
    useRerank: bool = Field(False, description="是否启用重排。")
    score: float | None = Field(None, ge=0, description="分数阈值，低于阈值的证据不返回。")
    topK: int = Field(5, description="返回证据数量上限。")
    filters: dict = Field(default_factory=dict, description="元数据过滤条件。")
    withCitation: bool = Field(True, description="是否返回引用信息。")
    index: str = Field("", description="目标索引名；缺省按知识库映射或下游 collocation 解析。")
    isOptimize: bool = Field(False, description="是否开启查询优化（走 OpenAI 检索网关时生效）。")

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"search", "qa"}:
            raise ValueError("mode 仅支持 search / qa")
        return cleaned

    @field_validator("searchType")
    @classmethod
    def _validate_search_type(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"fulltext", "vector", "hybrid"}:
            raise ValueError("searchType 仅支持 fulltext / vector / hybrid")
        return cleaned

    @field_validator("relNum")
    @classmethod
    def _validate_rel_num(cls, value: int) -> int:
        if value < 0 or value > 200:
            raise ValueError("relNum 必须在 0~200 之间")
        return value

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
                "searchType": "hybrid",
                "topK": 5,
                "useRerank": False,
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
    qaNote: str = Field("", description="回答说明：普通检索不生成回答时提示使用深度检索。")
    total: int = Field(0, description="命中证据总数。")
    results: list[SearchResultItemData] = Field(default_factory=list, description="检索结果列表。")
    searchType: str = Field("hybrid", description="实际执行的检索类型。")
    usedConfig: dict = Field(default_factory=dict, description="下游实际生效配置摘要（可选）。")


class SearchQueryResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: SearchQueryData = Field(..., description="业务数据。")


class DeepSearchSubQuerySpec(BaseModel):
    enabled: bool = Field(True, description="是否启用子查询拆分。")
    maxSubQueries: int = Field(3, ge=1, le=10, description="最大子查询数。")
    mergeStrategy: str = Field("rrf", description="子查询结果融合策略：rrf / union / weighted_sum。")

    @field_validator("mergeStrategy")
    @classmethod
    def _validate_merge_strategy(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"rrf", "union", "weighted_sum"}:
            raise ValueError("mergeStrategy 仅支持 rrf / union / weighted_sum")
        return cleaned


class DeepSearchStopWhenSpec(BaseModel):
    minEvidence: int | None = Field(None, ge=1, description="最少证据条数达到即可停止。")
    minFinalScore: float | None = Field(None, ge=0, description="最小最终分阈值达到即可停止。")
    maxLatencyMs: int | None = Field(None, ge=1, description="最大耗时（毫秒）超过即停止。")


class DeepSearchControlSpec(BaseModel):
    maxSteps: int = Field(5, ge=1, le=20, description="最大检索轮数。")
    recallTopnPolicy: str = Field("adaptive", description="召回窗口策略：fixed / adaptive。")
    subQuery: DeepSearchSubQuerySpec | None = Field(default=None, description="子查询拆分控制。")
    stopWhen: DeepSearchStopWhenSpec | None = Field(default=None, description="停止条件。")

    @field_validator("recallTopnPolicy")
    @classmethod
    def _validate_recall_policy(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"fixed", "adaptive"}:
            raise ValueError("recallTopnPolicy 仅支持 fixed / adaptive")
        return cleaned


class DeepSearchMemorySpec(BaseModel):
    mode: str = Field("caller", description="记忆来源：caller（调用方注入）。")
    items: list[dict] = Field(default_factory=list, description="调用方注入的记忆条目。")

    @field_validator("mode")
    @classmethod
    def _validate_memory_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"caller", "none"}:
            raise ValueError("memory.mode 仅支持 caller / none")
        return cleaned


class DeepSearchQueryRequest(BaseModel):
    query: str = Field("", description="复杂检索问题。")
    kbId: str = Field("", description="目标知识库 ID。用于数据权限资源匹配。")
    kbIds: list[str] = Field(default_factory=list, description="目标知识库 ID 列表。用于多库联合检索的数据权限判定。")
    teamId: str = Field("", description="目标知识库类型为 team 时建议传入，用于团队归属校验。")
    orgId: str = Field("", description="目标知识库类型为 enterprise 时建议传入，用于组织范围校验。")
    ownerId: str = Field("", description="资源所有者 ID。用于 owner_only 场景判定。")
    orgPath: str = Field("", description="组织路径，如 /集团/销售中心/华东。用于组织范围判定。")
    searchType: str = Field("hybrid", description="检索类型：fulltext / vector / hybrid。")
    topK: int = Field(8, description="每轮召回窗口（证据数量上限）。")
    useRerank: bool = Field(True, description="深度检索默认启用重排。")
    sessionId: str = Field("", description="会话 ID，用于下游记忆检索。")
    memory: DeepSearchMemorySpec | None = Field(default=None, description="调用方注入记忆。")
    deepSearch: DeepSearchControlSpec | None = Field(default=None, description="深度检索流程控制。")
    filters: dict = Field(default_factory=dict, description="元数据过滤条件。")
    responseSpec: dict = Field(
        default_factory=lambda: {"include": ["answer", "citations", "usedQueries"]},
        description="返回增强控制：include 支持 answer / citations / usedQueries / steps。",
    )

    @field_validator("searchType")
    @classmethod
    def _validate_search_type(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"fulltext", "vector", "hybrid"}:
            raise ValueError("searchType 仅支持 fulltext / vector / hybrid")
        return cleaned

    @field_validator("topK")
    @classmethod
    def _validate_top_k(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("topK 必须在 1~100 之间")
        return value

    @model_validator(mode="after")
    def _validate_kb_scope(self) -> "DeepSearchQueryRequest":
        if not self.kbId.strip() and not self.kbIds:
            raise ValueError("kbId / kbIds 至少提供一个目标知识库")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "对比 2025 与 2026 产品白皮书的检索能力差异，并给出结论",
                "kbId": "kb_10001",
                "kbIds": ["kb_10001", "kb_10002"],
                "searchType": "hybrid",
                "topK": 8,
                "useRerank": True,
                "deepSearch": {"maxSteps": 5, "subQuery": {"enabled": True, "maxSubQueries": 3}},
            }
        }
    }


class SearchCitationItem(BaseModel):
    docId: str = Field(..., description="文档 ID。")
    docTitle: str = Field("", description="文档标题。")
    score: float = Field(0.0, description="相关性分值。")
    snippet: str = Field("", description="引用片段。")
    position: list[int] = Field(default_factory=list, description="引用位置（页码/坐标）。")


class DeepSearchStepItem(BaseModel):
    stage: str = Field("", description="Agent 阶段名。")
    query: str = Field("", description="该阶段执行的子查询。")
    docsCount: int = Field(0, description="该阶段命中证据数。")
    elapsedMs: float = Field(0.0, description="该阶段耗时（毫秒）。")


class DeepSearchQueryData(BaseModel):
    answer: str = Field("", description="最终回答（带证据编号引用）。")
    total: int = Field(0, description="召回证据总数。")
    results: list[SearchResultItemData] = Field(default_factory=list, description="召回明细列表。")
    citations: list[SearchCitationItem] = Field(default_factory=list, description="回答引用列表。")
    usedQueries: list[str] = Field(default_factory=list, description="实际执行的子查询列表。")
    steps: list[DeepSearchStepItem] = Field(default_factory=list, description="Agent 步骤明细（可选）。")


class DeepSearchQueryResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: DeepSearchQueryData = Field(..., description="业务数据。")
