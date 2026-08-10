from __future__ import annotations

"""MCP Server（stdio）：将 OpenIKC 开放平台现有 REST 接口封装为 MCP 工具。

工具清单与 SDK ``OpenIKCClient`` 领域方法一一对应（14 个）：
kb_create / kb_update / kb_query / kb_get / doc_ingest / doc_ingest_and_parse /
doc_get / parse_start / parse_query / parse_issue_ticket / parse_download /
search_query / sys_catalog / sys_error_codes。

所有工具返回 JSON 序列化 dict（复用 SDK 模型），错误抛 ``OpenIKCError`` 子类。
不新增平台 REST 接口，仅做上层封装。
"""

import base64
import dataclasses
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import OpenIKCClient

SERVER_NAME = "open-ikc"
SERVER_INSTRUCTIONS = (
    "OpenIKC 开放平台北向 API 的 MCP 封装，覆盖知识库 / 文档 / 解析 / 检索四类能力。"
    "所有写操作（kb_create / kb_update / doc_ingest / doc_ingest_and_parse / parse_start）"
    "需注意数据权限上下文（kbId / ownerId / orgPath 等）由请求体承载，与平台 AUTHZ 一致。"
)


def _model_to_dict(obj: Any) -> dict[str, Any]:
    """将 SDK 领域模型序列化为 dict；优先使用模型自带 to_dict()，否则 dataclasses.asdict。"""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"无法序列化模型: {type(obj).__name__}")


def _parse_json_arg(value: str | None, field_name: str) -> dict | list | None:
    """将工具入参中的 JSON 字符串解析为 dict/list；None 或空字符串返回 None。"""
    if not value or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} 不是合法 JSON: {exc.msg}") from exc


def _json_dumps(data: dict[str, Any]) -> str:
    """紧凑 JSON 输出（ensure_ascii=False，便于 MCP 客户端展示中文）。"""
    return json.dumps(data, ensure_ascii=False, default=str)


def build_server(client: OpenIKCClient) -> FastMCP:
    """基于已构造的 ``OpenIKCClient`` 装配 MCP Server；供测试直接调用工具函数。"""

    mcp = FastMCP(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

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
        metadataSchema: str | None = None,
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
            metadataSchema: 元数据 Schema（JSON 字符串或省略）。
        """
        schema = _parse_json_arg(metadataSchema, "metadataSchema")
        return _model_to_dict(
            client.knowledge_bases.create(
                kbName=kbName,
                kbType=kbType,
                teamId=teamId,
                orgId=orgId,
                kbDesc=kbDesc,
                bizDomain=bizDomain,
                visibility=visibility,
                metadataSchema=schema,
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
        metadataSchema: str | None = None,
    ) -> dict[str, Any]:
        """局部更新知识库信息（缺省字段保留现有值）。

        Args:
            kbId: 知识库 ID（必填）。
            kbName / kbType / teamId / orgId / kbDesc / visibility: 需更新的字段，None 表示不更新。
            metadataSchema: 元数据 Schema（JSON 字符串），None 表示不更新。
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
            fields["metadataSchema"] = _parse_json_arg(metadataSchema, "metadataSchema")
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

    # ---------- 文档 ----------

    @mcp.tool()
    def doc_ingest(
        kbId: str,
        source: str,
        reqId: str = "",
        teamId: str = "",
        orgId: str = "",
        docTitle: str = "",
        tags: str | None = None,
        metadata: str | None = None,
        orchestrationMode: str = "split",
    ) -> dict[str, Any]:
        """接入知识源到知识库（不解析）。

        Args:
            kbId: 目标知识库 ID（必填）。
            source: 知识源描述（JSON 字符串），形如 {"type":"url","url":"..."}；type 支持 url/file/directory/archive。
            reqId: 请求幂等号，非空时 POST 允许重试。
            teamId / orgId: 知识库归属校验上下文。
            docTitle: 文档标题（缺省时平台推断）。
            tags: 文档标签（JSON 字符串数组）。
            metadata: 文档元数据（JSON 字符串对象）。
            orchestrationMode: 编排模式，默认 split。
        """
        tags_list = _parse_json_arg(tags, "tags")
        if tags_list is not None and not isinstance(tags_list, list):
            raise ValueError("tags 必须是 JSON 字符串数组")
        return _model_to_dict(
            client.documents.ingest(
                kbId=kbId,
                source=_parse_json_arg(source, "source") or {},
                reqId=reqId,
                teamId=teamId,
                orgId=orgId,
                docTitle=docTitle,
                tags=list(tags_list) if tags_list else None,
                metadata=_parse_json_arg(metadata, "metadata"),
                orchestrationMode=orchestrationMode,
            )
        )

    @mcp.tool()
    def doc_ingest_and_parse(
        kbId: str,
        source: str,
        reqId: str = "",
        teamId: str = "",
        orgId: str = "",
        docTitle: str = "",
        tags: str | None = None,
        metadata: str | None = None,
        orchestrationMode: str = "split",
        parseStrategy: str | None = None,
        resultFormat: str | None = None,
        executeMode: str = "async",
    ) -> dict[str, Any]:
        """一体化接入并解析知识源。

        Args:
            kbId: 目标知识库 ID（必填）。
            source: 知识源描述（JSON 字符串），同 doc_ingest。
            reqId: 请求幂等号。
            teamId / orgId: 知识库归属校验上下文。
            docTitle: 文档标题。
            tags: 文档标签（JSON 字符串数组）。
            metadata: 文档元数据（JSON 字符串对象）。
            orchestrationMode: 编排模式，默认 split。
            parseStrategy: 解析策略（JSON 字符串）。
            resultFormat: 结果格式（JSON 字符串）。
            executeMode: async（默认）/ sync（内联返回解析结果）。
        """
        tags_list = _parse_json_arg(tags, "tags")
        if tags_list is not None and not isinstance(tags_list, list):
            raise ValueError("tags 必须是 JSON 字符串数组")
        return _model_to_dict(
            client.documents.ingest_and_parse(
                kbId=kbId,
                source=_parse_json_arg(source, "source") or {},
                reqId=reqId,
                teamId=teamId,
                orgId=orgId,
                docTitle=docTitle,
                tags=list(tags_list) if tags_list else None,
                metadata=_parse_json_arg(metadata, "metadata"),
                orchestrationMode=orchestrationMode,
                parseStrategy=_parse_json_arg(parseStrategy, "parseStrategy"),
                resultFormat=_parse_json_arg(resultFormat, "resultFormat"),
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
        parseStrategy: str | None = None,
        resultFormat: str | None = None,
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
            parseStrategy: 解析策略（JSON 字符串）。
            resultFormat: 结果格式（JSON 字符串）。
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
                parseStrategy=_parse_json_arg(parseStrategy, "parseStrategy"),
                resultFormat=_parse_json_arg(resultFormat, "resultFormat"),
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
        kbIds: str | None = None,
        ownerId: str = "",
        orgPath: str = "",
    ) -> dict[str, Any]:
        """统一检索问答。

        Args:
            query: 检索问题或关键词。
            kbId: 目标知识库 ID（kbId / kbIds 至少提供一个）。
            kbIds: 目标知识库 ID 列表（JSON 字符串数组）。
            ownerId: 资源所有者 ID（owner_only 场景判定）。
            orgPath: 组织路径，如 /集团/销售中心/华东。
        """
        kb_ids_list = _parse_json_arg(kbIds, "kbIds")
        if kb_ids_list is not None and not isinstance(kb_ids_list, list):
            raise ValueError("kbIds 必须是 JSON 字符串数组")
        return _model_to_dict(
            client.search.query(
                query=query,
                kbId=kbId,
                kbIds=list(kb_ids_list) if kb_ids_list else None,
                ownerId=ownerId,
                orgPath=orgPath,
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
