from __future__ import annotations

from app.core.error_codes import raise_not_implemented


class SearchService:
    @staticmethod
    def query() -> dict:
        raise raise_not_implemented("检索", "统一检索问答", "/api/v1/knowledge-search/query")
