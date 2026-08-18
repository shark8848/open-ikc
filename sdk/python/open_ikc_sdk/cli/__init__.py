from __future__ import annotations

"""OpenIKC 开放平台 CLI：将现有 REST 接口封装为命令行子命令。

入口：``python -m open_ikc_sdk.cli``（安装后可用 ``ikc``）。

子命令分组（与 SDK 领域方法一一对应）：
- kb: create / update / list / get
- doc: ingest / ingest-and-parse / get
- parse: start / direct / query / ticket / download
- search: query / deep-search
- sys: catalog / error-codes

全局选项：
- --base-url / --token：覆盖环境变量（OPEN_PLATFORM_BASE_URL / OPEN_PLATFORM_TOKEN）
- --user-id / --tenant-id / --roles：AUTHZ 身份头（OPEN_PLATFORM_USER_ID / TENANT_ID / ROLES）
- --json：输出原始 JSON；默认渲染简洁表格

退出码约定：
- 0 成功
- 1 业务错误（2xxxxx 或未知错误码）
- 2 未认证（100401）
- 3 无权限（100403）
- 4 资源不存在（100404）
- 5 平台占位未实现（501001）
- 6 传输层错误（连接 / 超时 / HTTP 状态）
"""

import traceback
from typing import Any

import typer

from .._bootstrap import client_from_env
from ..client import OpenIKCClient
from ..errors import (
    OpenIKCConnectionError,
    OpenIKCForbiddenError,
    OpenIKCNotFoundError,
    OpenIKCNotImplementedError,
    OpenIKCTransportError,
    OpenIKCUnauthorizedError,
)
from . import _render

app = typer.Typer(
    name="ikc",
    help="OpenIKC 开放平台命令行（知识库 / 文档 / 解析 / 检索）",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

_client: OpenIKCClient | None = None
_global_opts: dict[str, Any] = {}


def _get_client() -> OpenIKCClient:
    """返回当前 CLI 会话客户端；测试可通过 init_app 注入。"""
    if _client is None:
        raise typer.Exit("客户端未初始化（请通过 init_app 或环境变量构造）", code=6)
    return _client


def _json_output(data: Any) -> str:
    return _render.render_json(data)


def _table_output(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return _render.render_table(rows, columns)


def _emit(data: Any) -> None:
    """按 --json / 默认渲染输出；模型先转为 dict 再序列化。"""
    if _global_opts.get("json"):
        typer.echo(_json_output(_render._as_dict(data)))
    else:
        typer.echo(_render.render_json(_render._as_dict(data)))


def _exit_code_for(err: BaseException) -> int:
    """错误 → 退出码映射（契约见模块 docstring）。"""
    if isinstance(err, OpenIKCUnauthorizedError):
        return 2
    if isinstance(err, OpenIKCForbiddenError):
        return 3
    if isinstance(err, OpenIKCNotFoundError):
        return 4
    if isinstance(err, OpenIKCNotImplementedError):
        return 5
    if isinstance(err, OpenIKCTransportError) or isinstance(err, OpenIKCConnectionError):
        return 6
    return 1


def _handle_error(err: BaseException) -> None:
    """统一错误处理：stderr 打印 errMsg（含 traceId），按退出码退出。"""
    message = str(err)
    trace_id = getattr(err, "trace_id", "") or getattr(err, "traceId", "")
    if _global_opts.get("debug"):
        traceback.print_exc()
    typer.echo(f"错误: {message}", err=True)
    if trace_id:
        typer.echo(f"traceId: {trace_id}", err=True)
    raise typer.Exit(code=_exit_code_for(err))


@app.callback()
def _main_callback(
    ctx: typer.Context,
    base_url: str = typer.Option(None, "--base-url", help="平台地址（默认 OPEN_PLATFORM_BASE_URL）"),
    token: str = typer.Option(None, "--token", help="平台 token（默认 OPEN_PLATFORM_TOKEN）"),
    user_id: str = typer.Option(None, "--user-id", help="AUTHZ 用户 ID（OPEN_PLATFORM_USER_ID）"),
    tenant_id: str = typer.Option(None, "--tenant-id", help="AUTHZ 租户 ID（OPEN_PLATFORM_TENANT_ID）"),
    roles: str = typer.Option(None, "--roles", help="AUTHZ 角色（逗号分隔，OPEN_PLATFORM_ROLES）"),
    json_output: bool = typer.Option(False, "--json", help="输出原始 JSON"),
    debug: bool = typer.Option(False, "--debug", help="打印堆栈"),
) -> None:
    _global_opts.update({"json": json_output, "debug": debug})
    if _client is None:
        init_app(
            base_url=base_url,
            token=token,
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles,
        )


def init_app(
    *,
    base_url: str | None = None,
    token: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    roles: str | None = None,
    client: OpenIKCClient | None = None,
) -> None:
    """初始化 CLI 客户端。测试可直接注入 mock client；否则从环境变量/参数构造。"""
    global _client
    if client is not None:
        _client = client
        return
    _client = client_from_env(
        base_url=base_url,
        token=token,
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
    )


# ---------- 知识库 ----------


@app.command("kb-create")
def kb_create(
    kb_name: str = typer.Argument(..., help="知识库名称"),
    kb_type: str = typer.Option("personal", "--kb-type", help="库类型：personal / team / enterprise"),
    team_id: str = typer.Option("", "--team-id", help="团队库归属团队 ID"),
    org_id: str = typer.Option("", "--org-id", help="企业库归属组织 ID"),
    kb_desc: str = typer.Option("", "--kb-desc", help="知识库描述"),
    biz_domain: str = typer.Option("general", "--biz-domain", help="业务领域"),
    visibility: str = typer.Option("private", "--visibility", help="可见性：private / public"),
    metadata_schema: str = typer.Option(None, "--metadata-schema", help="元数据 Schema（JSON 字符串）"),
) -> None:
    """创建知识库。"""
    try:
        data = _get_client().knowledge_bases.create(
            kbName=kb_name,
            kbType=kb_type,
            teamId=team_id,
            orgId=org_id,
            kbDesc=kb_desc,
            bizDomain=biz_domain,
            visibility=visibility,
            metadataSchema=_parse_json(metadata_schema) if metadata_schema else None,
        )
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("kb-update")
def kb_update(
    kb_id: str = typer.Argument(..., help="知识库 ID"),
    kb_name: str = typer.Option(None, "--kb-name", help="新名称"),
    kb_type: str = typer.Option(None, "--kb-type", help="新类型"),
    team_id: str = typer.Option(None, "--team-id", help="新团队 ID"),
    org_id: str = typer.Option(None, "--org-id", help="新组织 ID"),
    kb_desc: str = typer.Option(None, "--kb-desc", help="新描述"),
    visibility: str = typer.Option(None, "--visibility", help="新可见性"),
    metadata_schema: str = typer.Option(None, "--metadata-schema", help="元数据 Schema（JSON）"),
) -> None:
    """局部更新知识库信息（缺省字段保留）。"""
    try:
        fields: dict[str, Any] = {}
        for key, value in (
            ("kbName", kb_name),
            ("kbType", kb_type),
            ("teamId", team_id),
            ("orgId", org_id),
            ("kbDesc", kb_desc),
            ("visibility", visibility),
        ):
            if value is not None:
                fields[key] = value
        if metadata_schema is not None:
            fields["metadataSchema"] = _parse_json(metadata_schema)
        data = _get_client().knowledge_bases.update(kbId=kb_id, **fields)
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("kb-list")
def kb_list(
    page: int = typer.Option(1, "--page", help="页码"),
    page_size: int = typer.Option(20, "--page-size", help="每页数量"),
    kb_type: str = typer.Option(None, "--kb-type", help="按类型过滤"),
    team_id: str = typer.Option("", "--team-id", help="团队过滤"),
    org_id: str = typer.Option("", "--org-id", help="组织过滤"),
    owner_id: str = typer.Option("", "--owner-id", help="所有者过滤"),
    keyword: str = typer.Option("", "--keyword", help="名称关键字"),
) -> None:
    """分页查询可访问的知识库列表。"""
    try:
        data = _get_client().knowledge_bases.query(
            page=page,
            pageSize=page_size,
            kbType=kb_type or None,
            teamId=team_id,
            orgId=org_id,
            ownerId=owner_id,
            keyword=keyword,
        )
        if _global_opts.get("json"):
            typer.echo(_json_output(_render._as_dict(data)))
        else:
            items = [_render._as_dict(item) for item in data.items]
            typer.echo(_table_output(items, ["kbId", "kbName", "kbType", "visibility", "createTime"]))
            typer.echo(f"共 {data.total} 条（第 {data.page}/{max(1, (data.total + data.pageSize - 1) // data.pageSize)} 页）")
    except Exception as exc:
        _handle_error(exc)


@app.command("kb-get")
def kb_get(
    kb_id: str = typer.Argument(..., help="知识库 ID"),
) -> None:
    """按知识库 ID 查询详情。"""
    try:
        data = _get_client().knowledge_bases.get(kb_id)
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


# ---------- 文档 ----------


@app.command("doc-ingest")
def doc_ingest(
    kb_id: str = typer.Argument(..., help="目标知识库 ID"),
    source: str = typer.Argument(..., help='知识源 JSON，如 {"type":"url","url":"..."}'),
    req_id: str = typer.Option("", "--req-id", help="幂等号"),
    team_id: str = typer.Option("", "--team-id", help="团队校验上下文"),
    org_id: str = typer.Option("", "--org-id", help="组织校验上下文"),
    doc_title: str = typer.Option("", "--doc-title", help="文档标题"),
    tags: str = typer.Option(None, "--tags", help="文档标签（JSON 数组）"),
    metadata: str = typer.Option(None, "--metadata", help="文档元数据（JSON 对象）"),
    orchestration_mode: str = typer.Option("split", "--orchestration-mode", help="编排模式"),
) -> None:
    """接入知识源（不解析）。"""
    try:
        data = _get_client().documents.ingest(
            kbId=kb_id,
            source=_parse_json(source),
            reqId=req_id,
            teamId=team_id,
            orgId=org_id,
            docTitle=doc_title,
            tags=_parse_json(tags) if tags else None,
            metadata=_parse_json(metadata) if metadata else None,
            orchestrationMode=orchestration_mode,
        )
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("doc-ingest-and-parse")
def doc_ingest_and_parse(
    kb_id: str = typer.Argument(..., help="目标知识库 ID"),
    source: str = typer.Argument(..., help='知识源 JSON，如 {"type":"url","url":"..."}'),
    req_id: str = typer.Option("", "--req-id", help="幂等号"),
    team_id: str = typer.Option("", "--team-id", help="团队校验上下文"),
    org_id: str = typer.Option("", "--org-id", help="组织校验上下文"),
    doc_title: str = typer.Option("", "--doc-title", help="文档标题"),
    tags: str = typer.Option(None, "--tags", help="文档标签（JSON 数组）"),
    metadata: str = typer.Option(None, "--metadata", help="文档元数据（JSON 对象）"),
    orchestration_mode: str = typer.Option("split", "--orchestration-mode", help="编排模式"),
    parse_strategy: str = typer.Option(None, "--parse-strategy", help="解析策略（JSON）"),
    result_format: str = typer.Option(None, "--result-format", help="结果格式（JSON）"),
    execute_mode: str = typer.Option("async", "--execute-mode", help="async / sync"),
) -> None:
    """一体化接入并解析知识源。"""
    try:
        data = _get_client().documents.ingest_and_parse(
            kbId=kb_id,
            source=_parse_json(source),
            reqId=req_id,
            teamId=team_id,
            orgId=org_id,
            docTitle=doc_title,
            tags=_parse_json(tags) if tags else None,
            metadata=_parse_json(metadata) if metadata else None,
            orchestrationMode=orchestration_mode,
            parseStrategy=_parse_json(parse_strategy) if parse_strategy else None,
            resultFormat=_parse_json(result_format) if result_format else None,
            executeMode=execute_mode,
        )
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("doc-get")
def doc_get(
    doc_id: str = typer.Argument(..., help="文档 ID"),
) -> None:
    """按文档 ID 查询文档信息。"""
    try:
        data = _get_client().documents.get(doc_id)
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


# ---------- 解析 ----------


@app.command("parse-start")
def parse_start(
    kb_id: str = typer.Argument(..., help="知识库 ID"),
    doc_id: str = typer.Argument(..., help="文档 ID"),
    req_id: str = typer.Option("", "--req-id", help="幂等号"),
    parse_strategy: str = typer.Option(None, "--parse-strategy", help="解析策略（JSON）"),
    result_format: str = typer.Option(None, "--result-format", help="结果格式（JSON）"),
    execute_mode: str = typer.Option("async", "--execute-mode", help="async / sync"),
    parse_mode: str = typer.Option(None, "--parse-mode", help="解析模式"),
    chunk_strategy: str = typer.Option(None, "--chunk-strategy", help="切分策略"),
    chunk_size: int = typer.Option(None, "--chunk-size", help="切分大小"),
) -> None:
    """启动文档解析任务。"""
    try:
        data = _get_client().parse.parse(
            kbId=kb_id,
            docId=doc_id,
            reqId=req_id,
            parseStrategy=_parse_json(parse_strategy) if parse_strategy else None,
            resultFormat=_parse_json(result_format) if result_format else None,
            executeMode=execute_mode,
            parseMode=parse_mode,
            chunkStrategy=chunk_strategy,
            chunkSize=chunk_size,
        )
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("parse-query")
def parse_query(
    doc_id: str = typer.Argument(..., help="文档 ID"),
) -> None:
    """查询文档解析状态与产物摘要。"""
    try:
        data = _get_client().parse.query_result(docId=doc_id)
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("parse-ticket")
def parse_ticket(
    doc_id: str = typer.Argument(..., help="文档 ID"),
) -> None:
    """签发解析结果下载凭证（一次性）。"""
    try:
        data = _get_client().parse.issue_download_ticket(docId=doc_id)
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("parse-download")
def parse_download(
    doc_id: str = typer.Argument(..., help="文档 ID"),
    ticket: str = typer.Argument(..., help="下载凭证"),
    to_path: str = typer.Option(None, "--to-path", help="本地落盘路径"),
) -> None:
    """下载解析结果。"""
    try:
        result = _get_client().parse.download(docId=doc_id, ticket=ticket, to_path=to_path)
        if isinstance(result, bytes):
            typer.echo(f"已下载 {len(result)} 字节到 {to_path or '<内存>'}")
        else:
            _emit(result)
    except Exception as exc:
        _handle_error(exc)


# ---------- 检索 ----------


@app.command("parse-direct")
def parse_direct(
    source: str = typer.Argument(..., help='知识源 JSON，如 {"type":"url","url":"..."}'),
    req_id: str = typer.Option("", "--req-id", help="幂等号"),
    parse_strategy: str = typer.Option(None, "--parse-strategy", help="解析策略（JSON）"),
    result_format: str = typer.Option(None, "--result-format", help="结果格式（JSON）"),
    execute_mode: str = typer.Option("async", "--execute-mode", help="async / sync"),
    parse_mode: str = typer.Option(None, "--parse-mode", help="解析模式"),
    chunk_strategy: str = typer.Option(None, "--chunk-strategy", help="切分策略"),
    chunk_size: int = typer.Option(None, "--chunk-size", help="切分大小"),
) -> None:
    """免知识库独立解析（不创建知识库、不登记文档）。"""
    try:
        data = _get_client().parse.parse_direct(
            source=_parse_json(source),
            reqId=req_id,
            parseStrategy=_parse_json(parse_strategy) if parse_strategy else None,
            resultFormat=_parse_json(result_format) if result_format else None,
            executeMode=execute_mode,
            parseMode=parse_mode,
            chunkStrategy=chunk_strategy,
            chunkSize=chunk_size,
        )
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("search-query")
def search_query(
    query: str = typer.Option("", "--query", help="检索问题或关键词"),
    kb_id: str = typer.Option("", "--kb-id", help="目标知识库 ID"),
    kb_ids: str = typer.Option(None, "--kb-ids", help="知识库 ID 列表（JSON 数组）"),
    owner_id: str = typer.Option("", "--owner-id", help="资源所有者 ID"),
    org_path: str = typer.Option("", "--org-path", help="组织路径"),
) -> None:
    """统一检索问答。"""
    try:
        data = _get_client().search.query(
            query=query,
            kbId=kb_id,
            kbIds=_parse_json(kb_ids) if kb_ids else None,
            ownerId=owner_id,
            orgPath=org_path,
        )
        if _global_opts.get("json"):
            typer.echo(_json_output(_render._as_dict(data)))
        else:
            typer.echo(f"答案: {data.answer or '(无)'}")
            items = [_render._as_dict(item) for item in data.results]
            typer.echo(_table_output(items, ["docId", "score", "snippet"]))
    except Exception as exc:
        _handle_error(exc)


@app.command("deep-search")
def deep_search(
    query: str = typer.Option("", "--query", help="复杂检索问题"),
    kb_id: str = typer.Option("", "--kb-id", help="目标知识库 ID"),
    kb_ids: str = typer.Option(None, "--kb-ids", help="知识库 ID 列表（JSON 数组）"),
    owner_id: str = typer.Option("", "--owner-id", help="资源所有者 ID"),
    org_path: str = typer.Option("", "--org-path", help="组织路径"),
    search_type: str = typer.Option("hybrid", "--search-type", help="fulltext / vector / hybrid"),
    top_k: int = typer.Option(8, "--top-k", help="每轮召回窗口"),
    use_rerank: bool = typer.Option(True, "--use-rerank/--no-use-rerank", help="是否重排"),
    session_id: str = typer.Option("", "--session-id", help="会话 ID"),
) -> None:
    """Agentic 深度检索（需平台配置 openai 检索后端，否则 501001）。"""
    try:
        data = _get_client().search.deep_search(
            query=query,
            kbId=kb_id,
            kbIds=_parse_json(kb_ids) if kb_ids else None,
            ownerId=owner_id,
            orgPath=org_path,
            searchType=search_type,
            topK=top_k,
            useRerank=use_rerank,
            sessionId=session_id,
        )
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


# ---------- 系统 ----------


@app.command("sys-catalog")
def sys_catalog() -> None:
    """拉取平台 API 目录。"""
    try:
        data = _get_client().fetch_catalog()
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


@app.command("sys-error-codes")
def sys_error_codes() -> None:
    """拉取平台错误码目录。"""
    try:
        data = _get_client().fetch_error_codes()
        _emit(data)
    except Exception as exc:
        _handle_error(exc)


def _parse_json(value: str) -> Any:
    """解析 JSON 字符串；失败抛 ValueError（参数错误）。"""
    import json

    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"非法 JSON: {exc.msg}") from exc


if __name__ == "__main__":
    app()
