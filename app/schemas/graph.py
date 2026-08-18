from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphTypeCountResponse(BaseModel):
    type: str = Field(..., description="实体/关系类型。")
    count: int = Field(..., description="该类型活跃记录数。")


class GraphStatDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 graph。")
    graphId: str = Field(..., description="库级图谱 ID：graph_ + sha1(kbId) 前 12 位。")
    nodeCount: int = Field(..., description="活跃实体节点数。")
    edgeCount: int = Field(..., description="活跃关系边数。")
    entityTypes: list[GraphTypeCountResponse] = Field(default_factory=list, description="实体类型分布。")
    relationTypes: list[GraphTypeCountResponse] = Field(default_factory=list, description="关系类型分布。")
    schemaCoverage: dict[str, Any] = Field(default_factory=dict, description="schema 命中覆盖率（治理指标）。")


class GraphStatResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: GraphStatDataResponse = Field(..., description="图谱摘要数据。")


class GraphNodeDetailResponse(BaseModel):
    entityId: str = Field(..., description="稳定实体 ID：ent_ + sha1(graphId:type:normalizedName) 前 12 位。")
    type: str = Field(..., description="实体类型（schema entityTypes 约束）。")
    name: str = Field(..., description="实体名称。")
    properties: dict[str, Any] = Field(default_factory=dict, description="实体属性。")
    aliases: list[str] = Field(default_factory=list, description="别名（对齐累积）。")
    evidence: list[dict[str, str]] = Field(default_factory=list, description="证据：docId/pageId/chunkId/原文。")
    confidence: float = Field(..., description="置信度 0–1。")
    status: str = Field(..., description="active / deprecated。")
    createdAt: str = Field(..., description="创建时间（UTC ISO）。")
    updatedAt: str = Field(..., description="更新时间（UTC ISO）。")


class GraphNodesDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 graph。")
    total: int = Field(..., description="活跃节点总数。")
    page: int = Field(..., description="当前页码。")
    pageSize: int = Field(..., description="每页条数。")
    items: list[GraphNodeDetailResponse] = Field(default_factory=list, description="节点列表。")


class GraphNodesResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: GraphNodesDataResponse = Field(..., description="节点分页数据。")


class GraphEdgeDetailResponse(BaseModel):
    relationId: str = Field(..., description="稳定关系 ID：rel_ + sha1(graphId:type:source:target) 前 12 位。")
    type: str = Field(..., description="关系类型（schema relationTypes 约束）。")
    sourceEntityId: str = Field(..., description="源实体 ID。")
    targetEntityId: str = Field(..., description="目标实体 ID。")
    properties: dict[str, Any] = Field(default_factory=dict, description="关系属性。")
    evidence: list[dict[str, str]] = Field(default_factory=list, description="证据。")
    confidence: float = Field(..., description="置信度 0–1。")
    status: str = Field(..., description="active / deprecated。")
    createdAt: str = Field(..., description="创建时间（UTC ISO）。")
    updatedAt: str = Field(..., description="更新时间（UTC ISO）。")


class GraphEdgesDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 graph。")
    total: int = Field(..., description="活跃边总数。")
    page: int = Field(..., description="当前页码。")
    pageSize: int = Field(..., description="每页条数。")
    items: list[GraphEdgeDetailResponse] = Field(default_factory=list, description="边列表。")


class GraphEdgesResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: GraphEdgesDataResponse = Field(..., description="边分页数据。")


class GraphNeighborsDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 graph。")
    entityId: str = Field(..., description="中心实体 ID。")
    depth: int = Field(..., description="邻域深度（1/2）。")
    center: GraphNodeDetailResponse = Field(..., description="中心节点。")
    nodes: list[GraphNodeDetailResponse] = Field(default_factory=list, description="可达节点（含中心）。")
    edges: list[GraphEdgeDetailResponse] = Field(default_factory=list, description="邻域内覆盖边。")


class GraphNeighborsResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: GraphNeighborsDataResponse = Field(..., description="邻域数据。")


class GraphExportDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 graph。")
    graphId: str = Field(..., description="库级图谱 ID。")
    format: str = Field("jsonl", description="导出格式，当前为 jsonl。")
    total: int = Field(..., description="记录总数（含 deprecated）。")
    content: str = Field(..., description="jsonl 内容（每行一条 entity/relation 记录）。")


class GraphExportResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: GraphExportDataResponse = Field(..., description="导出数据。")
