from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SEARCH_ITEM_FIELDS = {"docId", "score", "snippet", "citation"}


@dataclass
class SearchResultItem:
    """检索结果条目（对应平台 D-01 results[] 目标态）。"""

    docId: str
    score: float | int | None = None
    snippet: str = ""
    citation: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResultItem":
        return cls(
            docId=str(data.get("docId", "")),
            score=data.get("score"),
            snippet=str(data.get("snippet", "")),
            citation=dict(data.get("citation") or {}),
            extra={key: value for key, value in data.items() if key not in _SEARCH_ITEM_FIELDS},
        )


_SEARCH_RESULT_FIELDS = {"answer", "qaNote", "total", "results", "searchType", "usedConfig"}


@dataclass
class SearchResult:
    """统一检索问答结果（对应平台 D-01 data 目标态）。"""

    answer: str = ""
    qaNote: str = ""
    total: int = 0
    results: list[SearchResultItem] = field(default_factory=list)
    searchType: str = "hybrid"
    usedConfig: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResult":
        return cls(
            answer=str(data.get("answer", "")),
            qaNote=str(data.get("qaNote", "")),
            total=int(data.get("total") or 0),
            results=[
                SearchResultItem.from_dict(item)
                for item in (data.get("results") or [])
                if isinstance(item, dict)
            ],
            searchType=str(data.get("searchType", "hybrid")),
            usedConfig=dict(data.get("usedConfig") or {}),
            extra={key: value for key, value in data.items() if key not in _SEARCH_RESULT_FIELDS},
        )


_DEEP_CITATION_FIELDS = {"docId", "docTitle", "score", "snippet", "position", "page"}


@dataclass
class DeepSearchCitation:
    """深度检索引用证据（对应平台 SearchCitationItem）。"""

    docId: str
    docTitle: str = ""
    score: float | int | None = None
    snippet: str = ""
    position: list[int] = field(default_factory=list)
    page: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeepSearchCitation":
        return cls(
            docId=str(data.get("docId", "")),
            docTitle=str(data.get("docTitle", "")),
            score=data.get("score"),
            snippet=str(data.get("snippet", "")),
            position=[int(p) for p in (data.get("position") or [])],
            page=data.get("page"),
            extra={key: value for key, value in data.items() if key not in _DEEP_CITATION_FIELDS},
        )


_DEEP_STEP_FIELDS = {"stage", "query", "docsCount", "elapsedMs"}


@dataclass
class DeepSearchStep:
    """深度检索 Agent 步骤（对应平台 DeepSearchStepItem）。"""

    stage: str = ""
    query: str = ""
    docsCount: int = 0
    elapsedMs: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeepSearchStep":
        return cls(
            stage=str(data.get("stage", "")),
            query=str(data.get("query", "")),
            docsCount=int(data.get("docsCount") or 0),
            elapsedMs=float(data.get("elapsedMs") or 0.0),
            extra={key: value for key, value in data.items() if key not in _DEEP_STEP_FIELDS},
        )


_DEEP_RESULT_FIELDS = {"answer", "total", "citations", "usedQueries", "steps"}


@dataclass
class DeepSearchResult:
    """Agentic 深度检索结果（对应平台 DeepSearchQueryData）。"""

    answer: str = ""
    total: int = 0
    citations: list[DeepSearchCitation] = field(default_factory=list)
    usedQueries: list[str] = field(default_factory=list)
    steps: list[DeepSearchStep] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeepSearchResult":
        return cls(
            answer=str(data.get("answer", "")),
            total=int(data.get("total") or 0),
            citations=[
                DeepSearchCitation.from_dict(item)
                for item in (data.get("citations") or [])
                if isinstance(item, dict)
            ],
            usedQueries=[str(q) for q in (data.get("usedQueries") or [])],
            steps=[
                DeepSearchStep.from_dict(item)
                for item in (data.get("steps") or [])
                if isinstance(item, dict)
            ],
            extra={key: value for key, value in data.items() if key not in _DEEP_RESULT_FIELDS},
        )
