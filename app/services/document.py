from __future__ import annotations

from app.core.error_codes import raise_not_implemented


class DocumentService:
    @staticmethod
    def ingest() -> dict:
        raise raise_not_implemented("文档", "接入知识源", "/api/v1/knowledge-documents/ingest")

    @staticmethod
    def ingest_and_parse() -> dict:
        raise raise_not_implemented("文档", "一体化接入并解析", "/api/v1/knowledge-documents/ingest-and-parse")

    @staticmethod
    def get_document(doc_id: str) -> dict:
        raise raise_not_implemented("文档", f"查询文档信息 doc_id={doc_id}", f"/api/v1/knowledge-documents/{doc_id}")
