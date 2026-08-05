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


_SEARCH_RESULT_FIELDS = {"answer", "results"}


@dataclass
class SearchResult:
    """统一检索问答结果（对应平台 D-01 data 目标态）。"""

    answer: str = ""
    results: list[SearchResultItem] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResult":
        return cls(
            answer=str(data.get("answer", "")),
            results=[
                SearchResultItem.from_dict(item)
                for item in (data.get("results") or [])
                if isinstance(item, dict)
            ],
            extra={key: value for key, value in data.items() if key not in _SEARCH_RESULT_FIELDS},
        )
