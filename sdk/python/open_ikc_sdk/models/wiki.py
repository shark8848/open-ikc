from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WikiTreeNode:
    """Wiki 库页面树节点（对应平台 WikiTreeNodeResponse）。"""

    pageId: str
    title: str
    level: int
    parentPageId: str = ""
    children: list["WikiTreeNode"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiTreeNode":
        return cls(
            pageId=str(data.get("pageId", "")),
            title=str(data.get("title", "")),
            level=int(data.get("level") or 1),
            parentPageId=str(data.get("parentPageId", "")),
            children=[
                WikiTreeNode.from_dict(item)
                for item in (data.get("children") or [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pageId": self.pageId,
            "title": self.title,
            "level": self.level,
            "parentPageId": self.parentPageId,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class WikiTreeData:
    """Wiki 库页面树查询结果（对应平台 WikiTreeDataResponse）。"""

    kbId: str
    kbMode: str = "wiki"
    total: int = 0
    page: int = 1
    pageSize: int = 20
    tree: list[WikiTreeNode] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiTreeData":
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "wiki")),
            total=int(data.get("total") or 0),
            page=int(data.get("page") or 1),
            pageSize=int(data.get("pageSize") or 20),
            tree=[
                WikiTreeNode.from_dict(item)
                for item in (data.get("tree") or [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "total": self.total,
            "page": self.page,
            "pageSize": self.pageSize,
            "tree": [node.to_dict() for node in self.tree],
        }


@dataclass
class WikiPageDetail:
    """Wiki 页面详情（对应平台 WikiPageDetailResponse）。"""

    pageId: str
    title: str
    level: int
    parentPageId: str = ""
    markdown: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    sourceDocs: list[str] = field(default_factory=list)
    status: str = ""
    createdAt: str = ""
    updatedAt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiPageDetail":
        return cls(
            pageId=str(data.get("pageId", "")),
            title=str(data.get("title", "")),
            level=int(data.get("level") or 1),
            parentPageId=str(data.get("parentPageId", "")),
            markdown=str(data.get("markdown", "")),
            fields=dict(data.get("fields") or {}),
            tags=[str(tag) for tag in (data.get("tags") or [])],
            links=[dict(link) for link in (data.get("links") or []) if isinstance(link, dict)],
            sourceDocs=[str(doc) for doc in (data.get("sourceDocs") or [])],
            status=str(data.get("status", "")),
            createdAt=str(data.get("createdAt", "")),
            updatedAt=str(data.get("updatedAt", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pageId": self.pageId,
            "title": self.title,
            "level": self.level,
            "parentPageId": self.parentPageId,
            "markdown": self.markdown,
            "fields": dict(self.fields),
            "tags": list(self.tags),
            "links": [dict(link) for link in self.links],
            "sourceDocs": list(self.sourceDocs),
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


@dataclass
class WikiPageData:
    """Wiki 页面详情查询结果（对应平台 WikiPageDataResponse）。"""

    kbId: str
    kbMode: str = "wiki"
    page: WikiPageDetail | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiPageData":
        page_data = data.get("page")
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "wiki")),
            page=WikiPageDetail.from_dict(page_data) if isinstance(page_data, dict) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "page": self.page.to_dict() if self.page is not None else None,
        }


@dataclass
class WikiSearchHit:
    """Wiki 库检索命中条目（对应平台 WikiSearchHitResponse）。"""

    pageId: str
    title: str
    snippet: str = ""
    tags: list[str] = field(default_factory=list)
    score: float | int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiSearchHit":
        return cls(
            pageId=str(data.get("pageId", "")),
            title=str(data.get("title", "")),
            snippet=str(data.get("snippet", "")),
            tags=[str(tag) for tag in (data.get("tags") or [])],
            score=data.get("score"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pageId": self.pageId,
            "title": self.title,
            "snippet": self.snippet,
            "tags": list(self.tags),
            "score": self.score,
        }


@dataclass
class WikiSearchData:
    """Wiki 库页面检索结果（对应平台 WikiSearchDataResponse）。"""

    kbId: str
    kbMode: str = "wiki"
    q: str = ""
    total: int = 0
    items: list[WikiSearchHit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiSearchData":
        return cls(
            kbId=str(data.get("kbId", "")),
            kbMode=str(data.get("kbMode", "wiki")),
            q=str(data.get("q", "")),
            total=int(data.get("total") or 0),
            items=[
                WikiSearchHit.from_dict(item)
                for item in (data.get("items") or [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kbId": self.kbId,
            "kbMode": self.kbMode,
            "q": self.q,
            "total": self.total,
            "items": [hit.to_dict() for hit in self.items],
        }
