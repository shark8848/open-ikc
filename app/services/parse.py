from __future__ import annotations

from app.core.error_codes import raise_not_implemented


class ParseService:
    @staticmethod
    def parse() -> dict:
        raise raise_not_implemented("解析", "启动文档解析", "/api/v1/knowledge-documents/parse")

    @staticmethod
    def query_parse_result(doc_id: str) -> dict:
        raise raise_not_implemented("解析", f"查询解析结果 docId={doc_id}", "/api/v1/knowledge-documents/parse-result/query")

    @staticmethod
    def issue_download_ticket(doc_id: str) -> dict:
        raise raise_not_implemented("解析", f"获取解析结果下载凭证 docId={doc_id}", "/api/v1/knowledge-documents/parse-result/issue-download-ticket")

    @staticmethod
    def download_parse_result(doc_id: str, ticket: str) -> dict:
        raise raise_not_implemented("解析", f"下载解析结果 docId={doc_id}", "/api/v1/knowledge-documents/parse-result/download")
