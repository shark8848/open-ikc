from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WikiTreeNodeResponse(BaseModel):
    pageId: str = Field(..., description="稳定页面 ID：wiki_ + sha1(kbId:stableKey) 前 12 位。")
    title: str = Field(..., description="页面标题。")
    level: int = Field(..., description="页面层级，根节点为 1。")
    parentPageId: str = Field("", description="父页面 ID，根节点为空字符串。")
    children: list["WikiTreeNodeResponse"] = Field(default_factory=list, description="子页面列表。")


class WikiTreeDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 wiki。")
    total: int = Field(..., description="页面总数（活跃页面）。")
    page: int = Field(..., description="当前页码。")
    pageSize: int = Field(..., description="每页条数。")
    tree: list[WikiTreeNodeResponse] = Field(default_factory=list, description="根节点列表，含嵌套 children。")


class WikiTreeResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: WikiTreeDataResponse = Field(..., description="页面树数据。")


class WikiPageDetailResponse(BaseModel):
    pageId: str = Field(..., description="稳定页面 ID。")
    title: str = Field(..., description="页面标题。")
    level: int = Field(..., description="页面层级。")
    parentPageId: str = Field(..., description="父页面 ID。")
    markdown: str = Field(..., description="页面正文（Markdown）。")
    fields: dict[str, Any] = Field(default_factory=dict, description="结构化字段（由 extractFields 抽取）。")
    tags: list[str] = Field(default_factory=list, description="页面标签。")
    links: list[dict[str, str]] = Field(default_factory=list, description="页面互链：title + pageId。")
    sourceDocs: list[str] = Field(default_factory=list, description="来源文档/分块证据。")
    status: str = Field(..., description="页面状态：active / deprecated。")
    createdAt: str = Field(..., description="创建时间（UTC ISO）。")
    updatedAt: str = Field(..., description="更新时间（UTC ISO）。")


class WikiPageDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 wiki。")
    page: WikiPageDetailResponse = Field(..., description="页面详情。")


class WikiPageResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: WikiPageDataResponse = Field(..., description="页面详情数据。")


class WikiSearchHitResponse(BaseModel):
    pageId: str = Field(..., description="命中的页面 ID。")
    title: str = Field(..., description="页面标题。")
    snippet: str = Field("", description="命中摘要片段。")
    tags: list[str] = Field(default_factory=list, description="页面标签。")
    score: float = Field(..., description="相关度得分（标题命中 > 正文命中）。")


class WikiSearchDataResponse(BaseModel):
    kbId: str = Field(..., description="知识库 ID。")
    kbMode: str = Field(..., description="知识库形态，恒为 wiki。")
    q: str = Field(..., description="检索关键字，空串表示返回全部页面。")
    total: int = Field(..., description="命中总数。")
    items: list[WikiSearchHitResponse] = Field(default_factory=list, description="页面级命中列表。")


class WikiSearchResponse(BaseModel):
    traceId: str = Field(..., description="请求链路追踪 ID。")
    errCode: str = Field(..., description="错误码。")
    errMsg: str = Field(..., description="错误信息。")
    data: WikiSearchDataResponse = Field(..., description="检索结果数据。")
