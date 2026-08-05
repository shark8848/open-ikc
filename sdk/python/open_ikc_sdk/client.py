from __future__ import annotations

from typing import Any

import httpx

from .envelope import Envelope
from .headers import CallerIdentity
from .models.document import (
    DocumentInfo,
    DocumentIngestAndParseResult,
    DocumentIngestResult,
    DocumentSource,
)
from .models.knowledge_base import KnowledgeBase, KnowledgeBasePage, KnowledgeMetadataField
from .models.parse import DownloadResult, DownloadTicket, ParseResult, ParseTask
from .models.search import SearchResult, SearchResultItem
from .transport import DownloadPayload, Transport


class OpenIKCClient:
    """OpenIKC 开放平台同步客户端。"""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: tuple[float, float] | float | None = None,
        max_retries: int = 2,
        identity: CallerIdentity | None = None,
        extra_headers: dict[str, str] | None = None,
        trace_id: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._transport = Transport(
            base_url=base_url,
            token=token,
            timeout=timeout,
            max_retries=max_retries,
            identity=identity,
            extra_headers=extra_headers,
            trace_id=trace_id,
            http_client=http_client,
        )
        self.knowledge_bases = KnowledgeBaseClient(self)
        self.documents = DocumentClient(self)
        self.parse = ParseClient(self)
        self.search = SearchClient(self)

    def request(
        self,
        method: str,
        path: str,
        *,
        path_params: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Envelope:
        """低层业务调用：errCode != 000000 时抛对应异常。"""
        return self._transport.request(
            method,
            path,
            path_params=path_params,
            params=params,
            body=body,
            raise_for_error=True,
        )

    def raw(
        self,
        method: str,
        path: str,
        *,
        path_params: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Envelope:
        """逃生口：返回原始统一响应壳，业务错误码不抛异常。"""
        return self._transport.request(
            method,
            path,
            path_params=path_params,
            params=params,
            body=body,
            raise_for_error=False,
        )

    def fetch_catalog(self) -> list[dict[str, Any]]:
        """拉取平台对外 API 目录（/api/catalog）。"""
        return self._transport.get_json("/api/catalog")

    def fetch_error_codes(self) -> list[dict[str, Any]]:
        """拉取平台错误码目录（/api/error-codes）。"""
        return self._transport.get_json("/api/error-codes")

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "OpenIKCClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def download(self, path: str, *, params: dict[str, Any] | None = None) -> DownloadPayload:
        """低层下载调用：返回原始载荷（含统一壳解析结果或文件流字节）。"""
        return self._transport.download(path, params=params)

    def __repr__(self) -> str:
        token_state = "<set>" if self._transport.has_token else "None"
        return f"OpenIKCClient(base_url={self._transport.base_url!r}, token={token_state})"


def _dump_metadata_schema(items: list) -> list[dict]:
    return [item.to_dict() if isinstance(item, KnowledgeMetadataField) else dict(item) for item in items]


class KnowledgeBaseClient:
    """知识库域客户端：create / update / query / get。"""

    _UPDATE_FIELDS = {"kbName", "kbType", "teamId", "orgId", "kbDesc", "visibility", "metadataSchema"}

    def __init__(self, client: OpenIKCClient) -> None:
        self._client = client

    def create(
        self,
        *,
        kbName: str,
        kbType: str = "personal",
        teamId: str = "",
        orgId: str = "",
        kbDesc: str = "",
        bizDomain: str = "general",
        visibility: str = "private",
        metadataSchema: list | None = None,
    ) -> KnowledgeBase:
        """创建知识库；metadataSchema 接受 dict 或 KnowledgeMetadataField。"""
        body: dict = {
            "kbName": kbName,
            "kbType": kbType,
            "teamId": teamId,
            "orgId": orgId,
            "kbDesc": kbDesc,
            "bizDomain": bizDomain,
            "visibility": visibility,
        }
        if metadataSchema is not None:
            body["metadataSchema"] = _dump_metadata_schema(metadataSchema)
        envelope = self._client.request("POST", "/api/v1/knowledge-bases/create", body=body)
        return KnowledgeBase.from_dict(envelope.data)

    def update(self, *, kbId: str, **fields) -> KnowledgeBase:
        """局部更新：先拉取现有记录合并未变更字段，避免平台将缺省的 kbType/visibility 重置为默认值。"""
        unknown = set(fields) - self._UPDATE_FIELDS
        if unknown:
            raise TypeError(f"update() 收到未知字段: {sorted(unknown)}")
        current = self.get(kbId)
        body: dict = {"kbId": kbId}
        for key in self._UPDATE_FIELDS:
            if key == "metadataSchema":
                body[key] = [item.to_dict() for item in current.metadataSchema]
            else:
                body[key] = getattr(current, key)
        for key, value in fields.items():
            if value is None:
                continue
            body[key] = _dump_metadata_schema(value) if key == "metadataSchema" else value
        envelope = self._client.request("POST", "/api/v1/knowledge-bases/update", body=body)
        return KnowledgeBase.from_dict(envelope.data)

    def query(
        self,
        *,
        page: int = 1,
        pageSize: int = 20,
        kbType: str | None = None,
        teamId: str = "",
        orgId: str = "",
        ownerId: str = "",
        keyword: str = "",
    ) -> KnowledgeBasePage:
        """分页查询调用方可访问的知识库列表；未传的过滤条件不放入请求体。"""
        body: dict = {"page": page, "pageSize": pageSize}
        if kbType is not None:
            body["kbType"] = kbType
        if teamId:
            body["teamId"] = teamId
        if orgId:
            body["orgId"] = orgId
        if ownerId:
            body["ownerId"] = ownerId
        if keyword:
            body["keyword"] = keyword
        envelope = self._client.request("POST", "/api/v1/knowledge-bases/query", body=body)
        return KnowledgeBasePage.from_dict(envelope.data)

    def get(self, kb_id: str) -> KnowledgeBase:
        """按知识库 ID 查询详情。"""
        envelope = self._client.request(
            "GET",
            "/api/v1/knowledge-bases/{kb_id}",
            path_params={"kb_id": kb_id},
        )
        return KnowledgeBase.from_dict(envelope.data)

def _dump_source(source: DocumentSource | dict) -> dict:
    return source.to_dict() if isinstance(source, DocumentSource) else dict(source)


def _dump_tags(tags: list[str] | None) -> list[str]:
    return list(tags) if tags else []


def _dump_metadata(metadata: dict | None) -> dict:
    return dict(metadata) if metadata else {}


class DocumentClient:
    """文档域客户端：ingest / ingest_and_parse / get。"""

    def __init__(self, client: OpenIKCClient) -> None:
        self._client = client

    def ingest(
        self,
        *,
        kbId: str,
        source: DocumentSource | dict,
        reqId: str = "",
        teamId: str = "",
        orgId: str = "",
        docTitle: str = "",
        tags: list[str] | None = None,
        metadata: dict | None = None,
        orchestrationMode: str = "split",
    ) -> DocumentIngestResult:
        """接入知识源；source 接受 DocumentSource 或 dict。reqId 非空时 POST 允许重试（幂等）。"""
        body: dict = {
            "kbId": kbId,
            "source": _dump_source(source),
            "orchestrationMode": orchestrationMode,
        }
        if reqId:
            body["reqId"] = reqId
        if teamId:
            body["teamId"] = teamId
        if orgId:
            body["orgId"] = orgId
        if docTitle:
            body["docTitle"] = docTitle
        if tags:
            body["tags"] = _dump_tags(tags)
        if metadata:
            body["metadata"] = _dump_metadata(metadata)
        envelope = self._client.request("POST", "/api/v1/knowledge-documents/ingest", body=body)
        return DocumentIngestResult.from_dict(envelope.data)

    def ingest_and_parse(
        self,
        *,
        kbId: str,
        source: DocumentSource | dict,
        reqId: str = "",
        teamId: str = "",
        orgId: str = "",
        docTitle: str = "",
        tags: list[str] | None = None,
        metadata: dict | None = None,
        orchestrationMode: str = "split",
        parseStrategy: dict | None = None,
        resultFormat: dict | None = None,
        executeMode: str = "async",
    ) -> DocumentIngestAndParseResult:
        """一体化接入并解析；executeMode=sync 时平台内联返回解析结果。"""
        body: dict = {
            "kbId": kbId,
            "source": _dump_source(source),
            "orchestrationMode": orchestrationMode,
            "executeMode": executeMode,
        }
        if reqId:
            body["reqId"] = reqId
        if teamId:
            body["teamId"] = teamId
        if orgId:
            body["orgId"] = orgId
        if docTitle:
            body["docTitle"] = docTitle
        if tags:
            body["tags"] = _dump_tags(tags)
        if metadata:
            body["metadata"] = _dump_metadata(metadata)
        if parseStrategy:
            body["parseStrategy"] = dict(parseStrategy)
        if resultFormat:
            body["resultFormat"] = dict(resultFormat)
        envelope = self._client.request("POST", "/api/v1/knowledge-documents/ingest-and-parse", body=body)
        return DocumentIngestAndParseResult.from_dict(envelope.data)

    def get(self, doc_id: str) -> DocumentInfo:
        """按文档 ID 查询文档信息。"""
        envelope = self._client.request(
            "GET",
            "/api/v1/knowledge-documents/{doc_id}",
            path_params={"doc_id": doc_id},
        )
        return DocumentInfo.from_dict(envelope.data)

class ParseClient:
    """解析域客户端：parse / query_result / issue_download_ticket / download。"""

    def __init__(self, client: OpenIKCClient) -> None:
        self._client = client

    def parse(
        self,
        *,
        kbId: str,
        docId: str,
        reqId: str = "",
        parseStrategy: dict | None = None,
        resultFormat: dict | None = None,
        executeMode: str = "async",
        parseMode: str | None = None,
        chunkStrategy: str | None = None,
        chunkSize: int | None = None,
    ) -> ParseTask:
        """启动文档解析；reqId 非空时 POST 允许重试（幂等）。parseMode/chunkStrategy/chunkSize 非 None 时透传。"""
        body: dict = {"kbId": kbId, "docId": docId, "executeMode": executeMode}
        if reqId:
            body["reqId"] = reqId
        if parseStrategy:
            body["parseStrategy"] = dict(parseStrategy)
        if resultFormat:
            body["resultFormat"] = dict(resultFormat)
        if parseMode is not None:
            body["parseMode"] = parseMode
        if chunkStrategy is not None:
            body["chunkStrategy"] = chunkStrategy
        if chunkSize is not None:
            body["chunkSize"] = chunkSize
        envelope = self._client.request("POST", "/api/v1/knowledge-documents/parse", body=body)
        return ParseTask.from_dict(envelope.data)

    def query_result(self, *, docId: str) -> ParseResult:
        """查询文档解析状态与产物摘要。"""
        envelope = self._client.request(
            "GET",
            "/api/v1/knowledge-documents/parse-result/query",
            params={"docId": docId},
        )
        return ParseResult.from_dict(envelope.data)

    def issue_download_ticket(self, *, docId: str) -> DownloadTicket:
        """签发解析结果短期下载凭证。"""
        envelope = self._client.request(
            "GET",
            "/api/v1/knowledge-documents/parse-result/issue-download-ticket",
            params={"docId": docId},
        )
        return DownloadTicket.from_dict(envelope.data)

    def download(self, *, docId: str, ticket: str, to_path: str | None = None) -> DownloadResult | bytes:
        """下载解析结果：平台返回 JSON 统一壳时返回 DownloadResult（当前占位元数据），文件流时返回 bytes；to_path 可落盘。"""
        payload = self._client.download(
            "/api/v1/knowledge-documents/parse-result/download",
            params={"docId": docId, "ticket": ticket},
        )
        if payload.envelope is not None:
            return DownloadResult.from_dict(payload.envelope.data)
        if to_path is not None:
            with open(to_path, "wb") as handle:
                handle.write(payload.content)
        return payload.content


class SearchClient:
    """检索域客户端：query。"""

    def __init__(self, client: OpenIKCClient) -> None:
        self._client = client

    def query(
        self,
        *,
        query: str = "",
        kbId: str = "",
        kbIds: list[str] | None = None,
        ownerId: str = "",
        orgPath: str = "",
    ) -> SearchResult:
        """统一检索问答；kbId/kbIds/ownerId/orgPath 同时是平台 AUTHZ 数据权限上下文，原样透传。"""
        body: dict = {}
        if query:
            body["query"] = query
        if kbId:
            body["kbId"] = kbId
        if kbIds:
            body["kbIds"] = list(kbIds)
        if ownerId:
            body["ownerId"] = ownerId
        if orgPath:
            body["orgPath"] = orgPath
        envelope = self._client.request("POST", "/api/v1/knowledge-search/query", body=body)
        return SearchResult.from_dict(envelope.data)

