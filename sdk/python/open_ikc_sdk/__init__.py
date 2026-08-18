from __future__ import annotations

import logging

from ._version import __version__
from .async_client import AsyncOpenIKCClient
from .client import OpenIKCClient
from .envelope import Envelope
from .errors import (
    OpenIKCAPIError,
    OpenIKCBusinessError,
    OpenIKCConflictError,
    OpenIKCConnectionError,
    OpenIKCError,
    OpenIKCForbiddenError,
    OpenIKCHTTPStatusError,
    OpenIKCMethodNotAllowedError,
    OpenIKCNotImplementedError,
    OpenIKCNotFoundError,
    OpenIKCProtocolError,
    OpenIKCSystemError,
    OpenIKCTimeoutError,
    OpenIKCTransportError,
    OpenIKCUnauthorizedError,
    OpenIKCValidationError,
)
from .headers import CallerIdentity
from .models.document import DocumentInfo, DocumentIngestAndParseResult, DocumentIngestResult, DocumentSource
from .models.knowledge_base import KnowledgeBase, KnowledgeBasePage, KnowledgeMetadataField
from .models.graph import GraphEdge, GraphEdges, GraphExport, GraphNeighbors, GraphNode, GraphNodes, GraphStat, GraphTypeCount
from .models.parse import DownloadResult, DownloadTicket, ParseResult, ParseTask
from .models.search import SearchResult, SearchResultItem
from .models.wiki import WikiPageData, WikiPageDetail, WikiSearchData, WikiSearchHit, WikiTreeData, WikiTreeNode
from .trace import generate_trace_id

__all__ = [
    "OpenIKCClient",
    "AsyncOpenIKCClient",
    "Envelope",
    "CallerIdentity",
    "KnowledgeBaseClient",
    "KnowledgeBase",
    "KnowledgeBasePage",
    "KnowledgeMetadataField",
    "DocumentSource",
    "DocumentIngestResult",
    "DocumentIngestAndParseResult",
    "DocumentInfo",
    "ParseTask",
    "ParseResult",
    "DownloadTicket",
    "DownloadResult",
    "SearchResult",
    "SearchResultItem",
    "WikiTreeData",
    "WikiTreeNode",
    "WikiPageData",
    "WikiPageDetail",
    "WikiSearchData",
    "WikiSearchHit",
    "GraphTypeCount",
    "GraphStat",
    "GraphNode",
    "GraphNodes",
    "GraphEdge",
    "GraphEdges",
    "GraphNeighbors",
    "GraphExport",
    "generate_trace_id",
    "OpenIKCError",
    "OpenIKCTransportError",
    "OpenIKCConnectionError",
    "OpenIKCTimeoutError",
    "OpenIKCProtocolError",
    "OpenIKCHTTPStatusError",
    "OpenIKCAPIError",
    "OpenIKCValidationError",
    "OpenIKCUnauthorizedError",
    "OpenIKCForbiddenError",
    "OpenIKCNotFoundError",
    "OpenIKCMethodNotAllowedError",
    "OpenIKCConflictError",
    "OpenIKCNotImplementedError",
    "OpenIKCSystemError",
    "OpenIKCBusinessError",
    "__version__",
]


def set_log_level(level: int | str) -> None:
    """设置 SDK 日志级别（默认 WARNING）。"""
    logging.getLogger("open_ikc_sdk").setLevel(level)
