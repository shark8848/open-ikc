from __future__ import annotations

"""MCP Server（stdio）：将 OpenIKC 开放平台现有 REST 接口封装为 MCP 工具。

工具清单与 SDK ``OpenIKCClient`` 领域方法一一对应（24 个）：
kb_create / kb_update / kb_query / kb_get / wiki_tree / wiki_page / wiki_search /
graph_stat / graph_nodes / graph_edges / graph_neighbors / graph_export /
doc_ingest / doc_ingest_and_parse / doc_get / parse_start / parse_direct / parse_query /
parse_issue_ticket / parse_download / search_query / deep_search / sys_catalog / sys_error_codes。

所有工具返回 JSON 序列化 dict（复用 SDK 模型），错误抛 ``OpenIKCError`` 子类。
不新增平台 REST 接口，仅做上层封装。
"""

import base64
import dataclasses
import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import OpenIKCClient

SERVER_NAME = "open-ikc"
SERVER_INSTRUCTIONS = (
    "OpenIKC 开放平台北向 API 的 MCP 封装，覆盖知识库 / 文档 / 解析 / 检索四类能力。"
    "所有写操作（kb_create / kb_update / doc_ingest / doc_ingest_and_parse / parse_start / parse_direct）"
    "需注意数据权限上下文（kbId / ownerId / orgPath 等）由请求体承载，与平台 AUTHZ 一致。"
)


def _model_to_dict(obj: Any) -> dict[str, Any]:
    """将 SDK 领域模型序列化为 dict；优先使用模型自带 to_dict()，否则 dataclasses.asdict。"""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"无法序列化模型: {type(obj).__name__}")


def _json_dumps(data: dict[str, Any]) -> str:
    """紧凑 JSON 输出（ensure_ascii=False，便于 MCP 客户端展示中文）。"""
    return json.dumps(data, ensure_ascii=False, default=str)


def build_server(client: OpenIKCClient) -> MCPServer:
    """基于已构造的 ``OpenIKCClient`` 装配 MCP Server；供测试直接调用工具函数。"""

    mcp = MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    # ---------- 知识库 ----------

    @mcp.tool()
    def kb_create(
        kbName: str,
        kbType: str = "personal",
        teamId: str = "",
        orgId: str = "",
        kbDesc: str = "",
        bizDomain: str = "general",
        visibility: str = "private",
        metadataSchema: list | None = None,
    ) -> dict[str, Any]:
        """创建知识库。

        Args:
            kbName: 知识库名称（必填）。
            kbType: 库类型：personal / team / enterprise。
            teamId: 团队库归属团队 ID。
            orgId: 企业库归属组织 ID。
            kbDesc: 知识库描述。
            bizDomain: 业务领域，默认 general。
            visibility: 可见性：private / public。
            metadataSchema: 元数据 Schema 字段数组（每个字段含 name/type/required 等），可省略。
        """
        return _model_to_dict(
            client.knowledge_bases.create(
                kbName=kbName,
                kbType=kbType,
                teamId=teamId,
                orgId=orgId,
                kbDesc=kbDesc,
                bizDomain=bizDomain,
                visibility=visibility,
                metadataSchema=metadataSchema,
            )
        )

    @mcp.tool()
    def kb_update(
        kbId: str,
        kbName: str | None = None,
        kbType: str | None = None,
        teamId: str | None = None,
        orgId: str | None = None,
        kbDesc: str | None = None,
        visibility: str | None = None,
        metadataSchema: list | None = None,
    ) -> dict[str, Any]:
        """局部更新知识库信息（缺省字段保留现有值）。

        Args:
            kbId: 知识库 ID（必填）。
            kbName / kbType / teamId / orgId / kbDesc / visibility: 需更新的字段，None 表示不更新。
            metadataSchema: 元数据 Schema 字段数组，None 表示不更新。
        """
        fields: dict[str, Any] = {}
        if kbName is not None:
            fields["kbName"] = kbName
        if kbType is not None:
            fields["kbType"] = kbType
        if teamId is not None:
            fields["teamId"] = teamId
        if orgId is not None:
            fields["orgId"] = orgId
        if kbDesc is not None:
            fields["kbDesc"] = kbDesc
        if visibility is not None:
            fields["visibility"] = visibility
        if metadataSchema is not None:
            fields["metadataSchema"] = metadataSchema
        return _model_to_dict(client.knowledge_bases.update(kbId=kbId, **fields))

    @mcp.tool()
    def kb_query(
        page: int = 1,
        pageSize: int = 20,
        kbType: str | None = None,
        teamId: str = "",
        orgId: str = "",
        ownerId: str = "",
        keyword: str = "",
    ) -> dict[str, Any]:
        """分页查询调用方可访问的知识库列表。

        Args:
            page: 页码，从 1 开始。
            pageSize: 每页数量。
            kbType: 按库类型过滤（personal / team / enterprise）。
            teamId / orgId / ownerId: 数据范围过滤条件（同时是 AUTHZ 数据权限上下文）。
            keyword: 按名称关键字模糊过滤。
        """
        return _model_to_dict(
            client.knowledge_bases.query(
                page=page,
                pageSize=pageSize,
                kbType=kbType,
                teamId=teamId,
                orgId=orgId,
                ownerId=ownerId,
                keyword=keyword,
            )
        )

    @mcp.tool()
    def kb_get(kbId: str) -> dict[str, Any]:
        """按知识库 ID 查询详情。

        Args:
            kbId: 知识库 ID。
        """
        return _model_to_dict(client.knowledge_bases.get(kbId))

    @mcp.tool()
    def wiki_tree(kbId: str, page: int = 1, pageSize: int = 20) -> dict[str, Any]:
        """查询 Wiki 库页面树（pageId/title/level/嵌套 children）。

        Args:
            kbId: Wiki 知识库 ID（kbMode=wiki）。
            page: 页码，从 1 开始。
            pageSize: 每页根节点数（最大 100）。
        """
        return _model_to_dict(client.knowledge_bases.wiki_tree(kbId, page=page, pageSize=pageSize))

    @mcp.tool()
    def wiki_page(kbId: str, pageId: str) -> dict[str, Any]:
        """查询 Wiki 页面详情（正文 / 结构化字段 / 互链 / 来源证据）。

        Args:
            kbId: Wiki 知识库 ID。
            pageId: 页面 ID（由 wiki_tree / wiki_search 返回）。
        """
        return _model_to_dict(client.knowledge_bases.wiki_page(kbId, page_id=pageId))

    @mcp.tool()
    def wiki_search(kbId: str, q: str = "", tag: str = "") -> dict[str, Any]:
        """检索 Wiki 库页面（标题命中加权 > 正文命中）。

        Args:
            kbId: Wiki 知识库 ID。
            q: 检索关键字，空串返回全部活跃页面。
            tag: 按页面标签精确过滤，可选。
        """
        return _model_to_dict(client.knowledge_bases.wiki_search(kbId, q=q, tag=tag))

    @mcp.tool()
    def graph_stat(kbId: str) -> dict[str, Any]:
        """查询图谱库摘要（节点/边计数、类型分布与 schema 覆盖率）。

        Args:
            kbId: 图谱知识库 ID（kbMode=graph）。
        """
        return _model_to_dict(client.knowledge_bases.graph_stat(kbId))

    @mcp.tool()
    def graph_nodes(kbId: str, entityType: str = "", page: int = 1, pageSize: int = 20) -> dict[str, Any]:
        """分页查询图谱实体节点（支持按实体类型过滤）。

        Args:
            kbId: 图谱知识库 ID。
            entityType: 按实体类型过滤，可选。
            page: 页码，从 1 开始。
            pageSize: 每页数量（最大 100）。
        """
        return _model_to_dict(
            client.knowledge_bases.graph_nodes(kbId, entity_type=entityType, page=page, pageSize=pageSize)
        )

    @mcp.tool()
    def graph_edges(kbId: str, relationType: str = "", page: int = 1, pageSize: int = 20) -> dict[str, Any]:
        """分页查询图谱关系边（支持按关系类型过滤）。

        Args:
            kbId: 图谱知识库 ID。
            relationType: 按关系类型过滤，可选。
            page: 页码，从 1 开始。
            pageSize: 每页数量（最大 100）。
        """
        return _model_to_dict(
            client.knowledge_bases.graph_edges(kbId, relation_type=relationType, page=page, pageSize=pageSize)
        )

    @mcp.tool()
    def graph_neighbors(kbId: str, entityId: str, depth: int = 1) -> dict[str, Any]:
        """查询实体邻域（depth 1/2），返回中心节点、可达节点与覆盖边。

        Args:
            kbId: 图谱知识库 ID。
            entityId: 中心实体 ID（由 graph_nodes 返回）。
            depth: 邻域深度：1 或 2。
        """
        return _model_to_dict(client.knowledge_bases.graph_neighbors(kbId, entity_id=entityId, depth=depth))

    @mcp.tool()
    def graph_export(kbId: str) -> dict[str, Any]:
        """全量导出图谱（jsonl 内容，含 deprecated 记录）。

        Args:
            kbId: 图谱知识库 ID。
        """
        return _model_to_dict(client.knowledge_bases.graph_export(kbId))

    # ---------- 文档 ----------

    @mcp.tool()
    def doc_ingest(
        kbId: str,
        source: dict,
        reqId: str = "",
        teamId: str = "",
        orgId: str = "",
        docTitle: str = "",
        tags: list | None = None,
        metadata: dict | None = None,
        orchestrationMode: str = "split",
    ) -> dict[str, Any]:
        """接入知识源到知识库（不解析）。

        Args:
            kbId: 目标知识库 ID（必填）。
            source: 知识源描述对象，形如 {"type":"url","url":"..."}；type 支持 url/file/directory/archive。
            reqId: 请求幂等号，非空时 POST 允许重试。
            teamId / orgId: 知识库归属校验上下文。
            docTitle: 文档标题（缺省时平台推断）。
            tags: 文档标签字符串数组。
            metadata: 文档元数据对象。
            orchestrationMode: 编排模式，默认 split。
        """
        return _model_to_dict(
            client.documents.ingest(
                kbId=kbId,
                source=source or {},
                reqId=reqId,
                teamId=teamId,
                orgId=orgId,
                docTitle=docTitle,
                tags=tags,
                metadata=metadata,
                orchestrationMode=orchestrationMode,
            )
        )

    @mcp.tool()
    def doc_ingest_and_parse(
        kbId: str,
        source: dict,
        reqId: str = "",
        teamId: str = "",
        orgId: str = "",
        docTitle: str = "",
        tags: list | None = None,
        metadata: dict | None = None,
        orchestrationMode: str = "split",
        parseStrategy: dict | None = None,
        resultFormat: dict | None = None,
        executeMode: str = "async",
    ) -> dict[str, Any]:
        """一体化接入并解析知识源。

        Args:
            kbId: 目标知识库 ID（必填）。
            source: 知识源描述对象，同 doc_ingest。
            reqId: 请求幂等号。
            teamId / orgId: 知识库归属校验上下文。
            docTitle: 文档标题。
            tags: 文档标签字符串数组。
            metadata: 文档元数据对象。
            orchestrationMode: 编排模式，默认 split。
            parseStrategy: 解析策略对象。
            resultFormat: 结果格式对象。
            executeMode: async（默认）/ sync（内联返回解析结果）。
        """
        return _model_to_dict(
            client.documents.ingest_and_parse(
                kbId=kbId,
                source=source or {},
                reqId=reqId,
                teamId=teamId,
                orgId=orgId,
                docTitle=docTitle,
                tags=tags,
                metadata=metadata,
                orchestrationMode=orchestrationMode,
                parseStrategy=parseStrategy,
                resultFormat=resultFormat,
                executeMode=executeMode,
            )
        )

    @mcp.tool()
    def doc_get(docId: str) -> dict[str, Any]:
        """按文档 ID 查询文档信息。

        Args:
            docId: 文档 ID。
        """
        return _model_to_dict(client.documents.get(docId))

    # ---------- 解析 ----------

    @mcp.tool()
    def parse_start(
        kbId: str,
        docId: str,
        reqId: str = "",
        parseStrategy: dict | None = None,
        resultFormat: dict | None = None,
        executeMode: str = "async",
        parseMode: str | None = None,
        chunkStrategy: str | None = None,
        chunkSize: int | None = None,
    ) -> dict[str, Any]:
        """启动文档解析任务。

        Args:
            kbId: 知识库 ID（必填）。
            docId: 文档 ID（必填）。
            reqId: 请求幂等号。
            parseStrategy: 解析策略对象。
            resultFormat: 结果格式对象。
            executeMode: async（默认）/ sync。
            parseMode: 解析模式（透传）。
            chunkStrategy: 切分策略（透传）。
            chunkSize: 切分大小（透传）。
        """
        return _model_to_dict(
            client.parse.parse(
                kbId=kbId,
                docId=docId,
                reqId=reqId,
                parseStrategy=parseStrategy,
                resultFormat=resultFormat,
                executeMode=executeMode,
                parseMode=parseMode,
                chunkStrategy=chunkStrategy,
                chunkSize=chunkSize,
            )
        )

    @mcp.tool()
    def parse_direct(
        source: dict,
        reqId: str = "",
        parseStrategy: dict | None = None,
        resultFormat: dict | None = None,
        executeMode: str = "async",
        parseMode: str = "auto",
        chunkStrategy: str = "auto",
        chunkSize: int = 800,
    ) -> dict[str, Any]:
        """免知识库独立解析：直接解析传入来源，不创建知识库、不登记文档。

        Args:
            source: 待解析来源对象（url/file/directory/archive），如 {"type": "url", "url": "https://example.com/a.pdf"}。
            reqId: 幂等请求标识。
            parseStrategy: 解析策略（docType/parseMethod/backend/pageRange/chunking 等）。
            resultFormat: 返回格式（type/includeLayout/includeImages/imageEncoding 等）。
            executeMode: sync 请求内返回内联结果；async 返回临时 docId 后经 parse_query/parse_issue_ticket/parse_download 轮询下载。
            parseMode: 解析模式 auto/ocr/structure。
            chunkStrategy: 分段策略 auto/fixed/semantic。
            chunkSize: 分段长度。
        """
        return _model_to_dict(
            client.parse.parse_direct(
                source=source,
                reqId=reqId,
                parseStrategy=parseStrategy,
                resultFormat=resultFormat,
                executeMode=executeMode,
                parseMode=parseMode,
                chunkStrategy=chunkStrategy,
                chunkSize=chunkSize,
            )
        )

    @mcp.tool()
    def parse_query(docId: str) -> dict[str, Any]:
        """查询文档解析状态与产物摘要。

        Args:
            docId: 文档 ID。
        """
        return _model_to_dict(client.parse.query_result(docId=docId))

    @mcp.tool()
    def parse_issue_ticket(docId: str) -> dict[str, Any]:
        """签发解析结果短期下载凭证（一次性）。

        Args:
            docId: 文档 ID。
        """
        return _model_to_dict(client.parse.issue_download_ticket(docId=docId))

    @mcp.tool()
    def parse_download(
        docId: str,
        ticket: str,
        toPath: str | None = None,
    ) -> dict[str, Any]:
        """下载解析结果。

        Args:
            docId: 文档 ID。
            ticket: 下载凭证（一次性，用后即失效）。
            toPath: 本地落盘路径；不传时返回 JSON 元数据（平台当前占位），文件流落地后返回 base64 字节。
        """
        result = client.parse.download(docId=docId, ticket=ticket, to_path=toPath)
        if isinstance(result, bytes):
            return {
                "format": "bytes",
                "encoding": "base64",
                "content": base64.b64encode(result).decode("ascii"),
                "note": "解析结果文件流（目标态）；落盘请使用 toPath 参数",
            }
        return _model_to_dict(result)

    # ---------- 检索 ----------

    @mcp.tool()
    def search_query(
        query: str = "",
        kbId: str = "",
        kbIds: list | None = None,
        teamId: str = "",
        orgId: str = "",
        ownerId: str = "",
        orgPath: str = "",
        mode: str = "qa",
        searchType: str = "hybrid",
        relNum: int = 0,
        useRerank: bool = False,
        score: float | None = None,
        topK: int = 5,
        filters: dict | None = None,
        withCitation: bool = True,
        index: str = "",
        isOptimize: bool = False,
    ) -> dict[str, Any]:
        """统一检索问答。

        Args:
            query: 检索问题或关键词。
            kbId: 目标知识库 ID（kbId / kbIds 至少提供一个）。
            kbIds: 目标知识库 ID 字符串数组。
            teamId / orgId: team/enterprise 库归属范围（数据权限上下文）。
            ownerId: 资源所有者 ID（owner_only 场景判定）。
            orgPath: 组织路径，如 /集团/销售中心/华东。
            mode: qa（附简短回答）/ search（仅证据）。
            searchType: fulltext / vector / hybrid。
            relNum: 关联召回数量（0~200）。
            useRerank: 是否重排。
            score: 分数阈值。
            topK: 证据数量上限。
            filters: 元数据过滤。
            withCitation: 是否返回引用。
            index: 目标索引名。
            isOptimize: 是否开启查询优化。
        """
        return _model_to_dict(
            client.search.query(
                query=query,
                kbId=kbId,
                kbIds=kbIds,
                teamId=teamId,
                orgId=orgId,
                ownerId=ownerId,
                orgPath=orgPath,
                mode=mode,
                searchType=searchType,
                relNum=relNum,
                useRerank=useRerank,
                score=score,
                topK=topK,
                filters=filters,
                withCitation=withCitation,
                index=index,
                isOptimize=isOptimize,
            )
        )

    @mcp.tool()
    def deep_search(
        query: str = "",
        kbId: str = "",
        kbIds: list | None = None,
        teamId: str = "",
        orgId: str = "",
        ownerId: str = "",
        orgPath: str = "",
        searchType: str = "hybrid",
        topK: int = 8,
        useRerank: bool = True,
        sessionId: str = "",
        memory: dict | None = None,
        deepSearch: dict | None = None,
        filters: dict | None = None,
        responseSpec: dict | None = None,
    ) -> dict[str, Any]:
        """Agentic 深度检索（多轮子查询规划、并行召回、反思与带引用回答）。

        Args:
            query: 复杂检索问题。
            kbId / kbIds: 目标知识库（至少提供一个）。
            teamId / orgId / ownerId / orgPath: 数据权限上下文。
            searchType: fulltext / vector / hybrid。
            topK: 每轮召回窗口。
            useRerank: 是否重排（深度检索默认开启）。
            sessionId: 会话 ID（下游记忆检索）。
            memory: 调用方注入记忆（mode/items）。
            deepSearch: 流程控制（maxSteps/subQuery/stopWhen 等）。
            filters: 元数据过滤。
            responseSpec: 返回增强控制（include: answer/citations/usedQueries/steps）。
        """
        return _model_to_dict(
            client.search.deep_search(
                query=query,
                kbId=kbId,
                kbIds=kbIds,
                teamId=teamId,
                orgId=orgId,
                ownerId=ownerId,
                orgPath=orgPath,
                searchType=searchType,
                topK=topK,
                useRerank=useRerank,
                sessionId=sessionId,
                memory=memory,
                deepSearch=deepSearch,
                filters=filters,
                responseSpec=responseSpec,
            )
        )

    # ---------- 系统 ----------

    @mcp.tool()
    def sys_catalog() -> dict[str, Any]:
        """拉取平台对外 API 目录（/api/catalog）。"""
        return {"catalog": client.fetch_catalog()}

    @mcp.tool()
    def sys_error_codes() -> dict[str, Any]:
        """拉取平台错误码目录（/api/error-codes）。"""
        return {"errorCodes": client.fetch_error_codes()}

    return mcp
