# MCP 与 CLI 对外接口定义（open-ikc-sdk 上层封装）

- **日期**：2026-08-10
- **版本**：v1.0.0
- **定位**：MCP 与 CLI 是**对现有已定义 REST 接口（`/api/v1/...` 四大类能力）的上层封装**，不新增第五类独立接口，不触碰平台侧 `app/` 与 `catalog.py`。
- **实现载体**：`sdk/python/open_ikc_sdk/` 内的 `mcp/` 与 `cli/` 子包，复用 SDK transport / 错误映射 / 模型。

## 1. 能力映射总览

现有 SDK 领域方法 → MCP 工具 → CLI 子命令：

| 能力域 | SDK 方法 | MCP 工具 | CLI 子命令 |
| --- | --- | --- | --- |
| 知识库 | `knowledge_bases.create` | `kb_create` | `kb-create` |
| 知识库 | `knowledge_bases.update` | `kb_update` | `kb-update` |
| 知识库 | `knowledge_bases.query` | `kb_query` | `kb-list` |
| 知识库 | `knowledge_bases.get` | `kb_get` | `kb-get` |
| 知识库 | `knowledge_bases.wiki_tree` | `wiki_tree` | `wiki-tree` |
| 知识库 | `knowledge_bases.wiki_page` | `wiki_page` | `wiki-page` |
| 知识库 | `knowledge_bases.wiki_search` | `wiki_search` | `wiki-search` |
| 文档 | `documents.ingest` | `doc_ingest` | `doc-ingest` |
| 文档 | `documents.ingest_and_parse` | `doc_ingest_and_parse` | `doc-ingest-and-parse` |
| 文档 | `documents.get` | `doc_get` | `doc-get` |
| 解析 | `parse.parse` | `parse_start` | `parse-start` |
| 解析 | `parse.parse_direct` | `parse_direct` | `parse-direct` |
| 解析 | `parse.query_result` | `parse_query` | `parse-query` |
| 解析 | `parse.issue_download_ticket` | `parse_issue_ticket` | `parse-ticket` |
| 解析 | `parse.download` | `parse_download` | `parse-download` |
| 检索 | `search.query` | `search_query` | `search-query` |
| 检索 | `search.deep_search` | `deep_search` | `deep-search` |
| 系统 | `fetch_catalog` | `sys_catalog` | `sys-catalog` |
| 系统 | `fetch_error_codes` | `sys_error_codes` | `sys-error-codes` |

> 复杂结构参数（`source`、`parseStrategy`、`resultFormat`、`metadataSchema`、`tags`、`kbIds`）：
> - **MCP**：声明为原生 `object` / `array` 类型（mcp>=2.0 由框架按 JSON Schema 校验并反序列化）。
> - **CLI**：以 **JSON 字符串** 接收（命令行天然为字符串），由封装层解析后透传 SDK。

## 2. 运行与配置

### 2.1 环境变量（`open_ikc_sdk/_bootstrap.py`）

> 依赖：MCP 需 `mcp>=2.0`（`pip install "sdk/python[mcp]"`）；CLI 需 `typer>=0.15`（`pip install "sdk/python[cli]"`）。安装后 `python -m open_ikc_sdk.mcp` 与 `ikc` 入口直接可用。

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `OPEN_PLATFORM_BASE_URL` | 平台地址 | `http://127.0.0.1:18000` |
| `OPEN_PLATFORM_TOKEN` | 单 token | 无 |
| `OPEN_PLATFORM_TOKENS` | 多 token（逗号分隔），取第一个 | 无 |
| `OPEN_PLATFORM_USER_ID` | AUTHZ 身份头 `X-User-Id` | 无 |
| `OPEN_PLATFORM_TENANT_ID` | AUTHZ 身份头 `X-Tenant-Id` | 无 |
| `OPEN_PLATFORM_ROLES` | AUTHZ 角色（逗号分隔）→ `X-User-Roles` | 无 |

显式传参（CLI `--base-url` / `--token` 等）优先于环境变量。

### 2.2 MCP Server

```bash
# stdio 运行（默认）
python -m open_ikc_sdk.mcp

# 指定参数
python -m open_ikc_sdk.mcp --base-url http://127.0.0.1:18000 --token <token>

# 其他传输方式（sse / streamable-http）
python -m open_ikc_sdk.mcp --transport sse
```

- 工具名（19 个）：`kb_create` / `kb_update` / `kb_query` / `kb_get` / `wiki_tree` / `wiki_page` / `wiki_search` / `doc_ingest` / `doc_ingest_and_parse` / `doc_get` / `parse_start` / `parse_direct` / `parse_query` / `parse_issue_ticket` / `parse_download` / `search_query` / `deep_search` / `sys_catalog` / `sys_error_codes`。
- 工具返回：JSON 序列化 dict（复用 SDK 模型 `to_dict()` / `dataclasses.asdict`）。
- 错误：SDK `OpenIKCError` 子类，由 MCP 运行时转为工具错误；错误信息含 `errCode` / `errMsg` / `traceId`。
- 客户端配置（Claude Desktop / Claude Code 等）：stdio 命令指向 `python -m open_ikc_sdk.mcp`，并注入上述环境变量。

**MCP 客户端接入配置示例**（Claude Desktop `claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "open-ikc": {
      "command": "/home/open-ikc/.venv/bin/python",
      "args": ["-m", "open_ikc_sdk.mcp", "--transport", "stdio"],
      "env": {
        "OPEN_PLATFORM_BASE_URL": "http://127.0.0.1:18000",
        "OPEN_PLATFORM_TOKEN": "<token>",
        "OPEN_PLATFORM_USER_ID": "<user>",
        "OPEN_PLATFORM_TENANT_ID": "<tenant>",
        "OPEN_PLATFORM_ROLES": "km_reader"
      }
    }
  }
}
```

> 注意：`command` 需指向安装了 `open-ikc-sdk[mcp]` 的 Python 解释器；`env` 中的 token 与 AUTHZ 身份头用于平台鉴权，按环境注入。

### 2.3 CLI

```bash
# 模块入口
python -m open_ikc_sdk.cli --help

# 安装后（pyproject [project.scripts] 注册了 ikc 入口）
ikc --help
```

**全局选项**（位于子命令之前）：

| 选项 | 说明 |
| --- | --- |
| `--base-url` | 覆盖平台地址 |
| `--token` | 覆盖 token |
| `--user-id` / `--tenant-id` / `--roles` | AUTHZ 身份头 |
| `--json` | 输出原始 JSON（默认渲染简洁表格） |
| `--debug` | 打印异常堆栈 |

**退出码约定**：

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 业务错误（2xxxxx 或未知错误码） |
| 2 | 未认证（100401） |
| 3 | 无权限（100403） |
| 4 | 资源不存在（100404） |
| 5 | 平台占位未实现（501001） |
| 6 | 传输层错误（连接 / 超时 / HTTP 状态） |

## 3. MCP 工具定义

### 3.1 知识库

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `kb_create` | `kbName`(必填), `kbType`="personal", `teamId`, `orgId`, `kbDesc`, `bizDomain`="general", `visibility`="private", `metadataSchema`(JSON) | 创建知识库 |
| `kb_update` | `kbId`(必填), `kbName`/`kbType`/`teamId`/`orgId`/`kbDesc`/`visibility`/`metadataSchema`(均可选) | 局部更新（缺省字段保留现有值） |
| `kb_query` | `page`=1, `pageSize`=20, `kbType`, `teamId`, `orgId`, `ownerId`, `keyword` | 分页查询可访问知识库 |
| `kb_get` | `kbId`(必填) | 查询知识库详情 |
| `wiki_tree` | `kbId`(必填), `page`=1, `pageSize`=20 | 查询 Wiki 库页面树（仅 `kbMode=wiki`，只读） |
| `wiki_page` | `kbId`(必填), `pageId`(必填) | 查询 Wiki 页面详情（正文/字段/互链/来源） |
| `wiki_search` | `kbId`(必填), `q`="", `tag`="" | 检索 Wiki 库页面（标题命中加权 > 正文命中） |

### 3.2 文档

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `doc_ingest` | `kbId`(必填), `source`(object, 必填), `reqId`, `teamId`, `orgId`, `docTitle`, `tags`(array), `metadata`(object), `orchestrationMode`="split" | 接入知识源（不解析） |
| `doc_ingest_and_parse` | 同 `doc_ingest` + `parseStrategy`(JSON), `resultFormat`(JSON), `executeMode`="async" | 一体化接入并解析 |
| `doc_get` | `docId`(必填) | 查询文档信息 |

`source` 结构（与平台 D-02 一致）：

```json
{"type": "url", "url": "https://example.com/a.pdf"}
{"type": "file", "objectKey": "oss://bucket/obj", "fileToken": "..."}
{"type": "directory", "objectKey": "...", "directory": {...}}
{"type": "archive", "objectKey": "...", "archive": {...}}
```

### 3.3 解析

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `parse_start` | `kbId`(必填), `docId`(必填), `reqId`, `parseStrategy`(JSON), `resultFormat`(JSON), `executeMode`="async", `parseMode`, `chunkStrategy`, `chunkSize` | 启动文档解析任务 |
| `parse_direct` | `source`(必填, url/file/directory/archive), `reqId`, `parseStrategy`(JSON), `resultFormat`(JSON), `executeMode`="async", `parseMode`, `chunkStrategy`, `chunkSize` | 免知识库独立解析（不建库、不登记文档） |
| `parse_query` | `docId`(必填) | 查询解析状态与产物摘要 |
| `parse_issue_ticket` | `docId`(必填) | 签发一次性下载凭证 |
| `parse_download` | `docId`(必填), `ticket`(必填), `toPath` | 下载解析结果 |

> `parse_download`：平台当前返回 JSON 统一壳元数据；文件流落地后返回 base64 编码字节（`format=bytes, encoding=base64`）。
> `parse_direct`：`executeMode=sync` 请求内返回内联结果；`async` 返回临时 `docId`（`pdoc_` 前缀）后复用 `parse_query` / `parse_issue_ticket` / `parse_download` 轮询/下载。

### 3.4 检索

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `search_query` | `query`, `kbId`/`kbIds`(至少一个), `teamId`/`orgId`, `ownerId`, `orgPath`, `mode`="qa", `searchType`="hybrid", `relNum`, `useRerank`, `score`, `topK`, `filters`, `withCitation`, `index`, `isOptimize` | 统一检索问答（`/universal-search`） |
| `deep_search` | `query`, `kbId`/`kbIds`(至少一个), `teamId`/`orgId`, `ownerId`, `orgPath`, `searchType`="hybrid", `topK`=8, `useRerank`=true, `sessionId`, `memory`, `deepSearch`, `filters`, `responseSpec` | Agentic 深度检索（需平台配置 openai 检索后端，否则 `501001`） |

> `kbId` / `kbIds` / `teamId` / `orgId` / `ownerId` / `orgPath` 同时是平台 AUTHZ 数据权限上下文，原样透传（与 SDK 一致）。

### 3.5 系统

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `sys_catalog` | - | 拉取 `/api/catalog` |
| `sys_error_codes` | - | 拉取 `/api/error-codes` |

## 4. CLI 子命令定义

### 4.1 知识库

```bash
ikc kb-create 名称 --kb-type personal --team-id T1 --org-id O1 --kb-desc 描述 --visibility private --metadata-schema '[...]'
ikc kb-update kb_10001 --kb-name 新名称 --visibility public
ikc kb-list --page 1 --page-size 20 --keyword 关键字
ikc kb-get kb_10001
ikc wiki-tree kb_10001 --page 1 --page-size 20
ikc wiki-page kb_10001 --page-id wiki_xxx
ikc wiki-search kb_10001 --q 请假 --tag 制度
```

### 4.2 文档

```bash
ikc doc-ingest kb_10001 '{"type":"url","url":"https://example.com/a.pdf"}' --doc-title 文档 --tags '["tag1"]'
ikc doc-ingest-and-parse kb_10001 '{"type":"url","url":"..."}' --execute-mode async
ikc doc-get doc_10001
```

### 4.3 解析

```bash
ikc parse-start kb_10001 doc_10001 --execute-mode async
ikc parse-direct '{"type":"url","url":"https://example.com/a.pdf"}' --execute-mode sync
ikc parse-query doc_10001
ikc parse-ticket doc_10001
ikc parse-download doc_10001 <ticket> --to-path ./result.json
```

### 4.4 检索

```bash
ikc search-query --query "产品能力" --kb-id kb_10001 --owner-id u100 --org-path /集团/销售中心/华东
ikc deep-search --query "对比 2025 与 2026 白皮书" --kb-id kb_10001 --top-k 8 --no-use-rerank
```

### 4.5 系统

```bash
ikc sys-catalog
ikc sys-error-codes
```

## 5. 鉴权与 AUTHZ

- 认证：与平台一致，`Authorization: Bearer <token>`（由 SDK transport 附加）。
- AUTHZ 身份头：`X-User-Id` / `X-Tenant-Id` / `X-User-Roles` 等由 `CallerIdentity` 透传；MCP / CLI 通过环境变量或 CLI `--user-id/--tenant-id/--roles` 注入。
- 数据权限上下文：`kbId` / `kbIds` / `ownerId` / `orgPath` 由请求体承载，封装层原样透传，不改变平台 AUTHZ 语义。

## 6. 边界（不做的事）

- 不新增 / 不修改任何平台 REST 路由、`catalog.py`、`app/`。
- 不暴露 reindex / task query 等未落地能力（AGENTS.md §1 约束）。
- CLI 不做交互式 TUI，仅子命令式。

## 7. 验证

- SDK 测试：`pytest sdk/python/tests -q` 全部通过（**134 passed**）。
- 新增测试覆盖：
  - `test_bootstrap.py`：`client_from_env` 环境变量 → 客户端 / token / 身份头组装（7 例）。
  - `test_mcp_tools.py`：19 个工具逐一断言请求路径 / body / 返回 JSON（httpx.MockTransport，不起服务，mcp 2.0 `call_tool` 异步调用）。
  - `test_cli.py`：子命令解析、`--json` 输出、错误退出码映射、下载落盘（13 例）。
- **端到端冒烟**（真实平台，`scripts/mcp_stdio_smoke.py`）：以官方 mcp 2.0 `ClientSession + stdio_client` 连接 `python -m open_ikc_sdk.mcp --transport stdio`，验证
  `initialize（server_info=open-ikc）→ list_tools（19 工具齐全）→ call_tool(sys_catalog) → call_tool(kb_create)` 全链路通过。
  用法：先 `bash scripts/start_open_platform.sh` 启动平台，再 `.venv/bin/python scripts/mcp_stdio_smoke.py [--token <token>]`。

## 8. MCP 2.0 适配要点（mcp>=2.0）

- Server 用 `mcp.server.mcpserver.MCPServer`（替代 1.x `mcp.server.fastmcp.FastMCP`）；`list_tools` 为异步协程返回 `list[MCPTool]`，工具调用经 `call_tool(name, arguments)` 返回 `CallToolResult`。
- mcp 2.x 协议字段为 **snake_case**：`InitializeResult.server_info`、`CallToolResult.is_error`（1.x/部分文档为 camelCase）。
- 复杂结构参数（`source` / `parseStrategy` / `resultFormat` / `metadataSchema` / `tags` / `kbIds`）声明为原生 `object` / `array` 类型，由 mcp 2.0 按 JSON Schema 校验并反序列化（CLI 侧以 JSON 字符串接收）。
- 依赖声明：`pyproject.toml` 可选依赖 `mcp = ["mcp>=2.0"]`。

## 9. 管理 Portal 在线测试入口

管理 Portal（`/portal/`，TestLab 页）与后台管理接口（`/admin/test/*`）提供对 MCP / CLI 的**在线真实执行**：

- `POST /admin/test/mcp`：body `{tool, args?, token?, baseUrl?, timeoutSeconds?}`。subprocess 启动 `python -m open_ikc_sdk.mcp`（stdio），走
  `initialize → list_tools → call_tool(tool, args)` 三步冒烟，返回结构化步骤结果；`args` 为工具参数 JSON 对象（key 须在工具白名单允许范围，如 `kb_get` 需 `{"kbId":"kb_10001"}`）。
- `POST /admin/test/cli`：body `{command, args[]?, token?, baseUrl?, identity?, timeoutSeconds?}` 执行白名单 CLI 命令，捕获 stdout/stderr/退出码。
- `GET /admin/test/whitelist`：返回 `{cli, mcpTools, cliArgs, mcpArgs}`。只读白名单：CLI 为 `kb-list` / `kb-get` / `wiki-tree` / `wiki-page` / `wiki-search` / `doc-get` / `parse-query` / `sys-catalog` / `sys-error-codes` / `search-query` / `deep-search`；MCP 为 `sys_catalog` / `sys_error_codes` / `kb_get` / `kb_query` / `wiki_tree` / `wiki_page` / `wiki_search` / `doc_get` / `parse_query` / `parse_issue_ticket` / `search_query` / `deep_search`。禁止任意 shell 与写操作。
- 安全约束：命令/工具 + 参数双重白名单 + 超时（默认 20s，上限 120s）；token 从请求上下文注入子进程环境变量，不落库；统一响应壳 `errCode=000000` 表示执行成功（非子进程退出码）。
- 执行实现：`app/core/admin/mcp_cli_test.py`，subprocess 经 `starlette.concurrency.run_in_threadpool` 放线程池，避免阻塞平台事件循环。
- 该能力属管理面（需 `OPEN_PLATFORM_ADMIN_TOKEN`），不进入业务 `catalog.py`。详见 `docs/管理Portal设计.md`。
