# OpenIKC 开放平台 API 开发手册

> OpenIKC 开放平台是一个面向外部开发者的**知识库开放 API 服务**：你把文档交给我们，我们负责入库、解析、检索，你的应用只需一个统一协议即可获得「可检索的企业知识」。
>
> 适用版本：open-ikc-api（FastAPI 北向开放平台）· 服务端口 18000 · 协议 HTTPS/HTTP + JSON
> 权威依据：当前代码实现 > `docs/` 设计文档。接口定义以 `/api/catalog`、`/openapi.json` 实时为准。

## 1. 平台是什么，能帮你做什么

### 1.1 定位

这是一个**北向开放平台**：平台不开放内部流水线，只对开发者暴露**四大类业务能力**——知识库、文档、解析、检索。你通过 REST、SDK、MCP 或 CLI 中的任意一种方式接入，即可在自己的产品里使用企业级知识管理能力，而无需关心存储、解析管道与检索引擎的实现细节。

### 1.2 四大能力一览

| 能力 | 它解决什么问题 | 入口 | 典型场景 |
| --- | --- | --- | --- |
| **知识库** | 组织和管理知识空间（个人/团队/企业），定义元数据模型 | `/api/v1/knowledge-bases` | 为每个业务域建独立知识库，控制谁可见 |
| **文档** | 把 URL / 文件 / 目录 / 压缩包接入为可解析的文档 | `/api/v1/knowledge-documents` | 从 OSS、网页、批量目录导入知识源 |
| **解析** | 把文档解析为结构化结果（分页、分块、OCR），支持异步任务与**免知识库独立解析** | `/api/v1/knowledge-documents/parse*` | 合同/白皮书/扫描件变成文本块；只要结构化文本不建库（§6.3.5） |
| **检索** | 基于知识内容做普通检索与 Agentic 深度检索（带引用回答） | `/api/v1/knowledge-search` | 客服问答、内部知识助手、RAG 应用 |

另有**管理面**（`/admin/*`，运维用途，独立鉴权）、**系统路由**（健康检查、API 目录、错误码目录、文档页），以及上层 **Python SDK / Java SDK / MCP Server / CLI** 四种接入方式。

### 1.3 五种接入方式，怎么选

| 接入方式 | 形态 | 适合谁 | 起步成本 |
| --- | --- | --- | --- |
| **REST** | 纯 HTTP + JSON | 任何语言、curl/Postman 调试、需要全量字段控制 | 最低，看 §2 快速开始 |
| **Python SDK** | `open-ikc-sdk`，类型提示 + 异常映射 + 同步/异步 | Python 应用（FastAPI/Django/脚本） | 低，见 §9.1 |
| **Java SDK** | `io.openikc:open-ikc-sdk`，零第三方依赖 | Java 17+ 后端服务 | 低，见 §9.2 |
| **MCP Server** | 14 个工具，供 AI Agent 调用 | Claude Desktop / Cursor 等 AI 客户端 | 低，见 §10 |
| **CLI** | 14 个子命令，全局选项 + 退出码约定 | 运维脚本、快速验证、CI 冒烟 | 最低，见 §11 |

> 选择建议：**想最快跑通** → 快速开始用 curl 或 CLI；**写正式代码** → 选对应语言的 SDK（错误码自动映射为异常）；**给 AI 助手用** → MCP。

### 1.4 这份手册怎么读

- 想**立刻动手** → 跳到 §2 快速开始，5 分钟跑通全链路
- 想**确定接入方式** → 看 §3 接入方式对比
- 想**理解业务编排** → 看 §4 典型使用流程（数据生命周期）
- 想**查某个接口的字段** → 看 §6 接口参考
- 只想**解析文件、不建库** → 看 §6.3.5 独立解析（免知识库）
- 遇到**报错** → 看 §5.4 错误码表与 §12 常见错误排查

## 2. 快速开始：5 分钟跑通「建库 → 入库 → 解析 → 检索」

本小节带你完成一次完整闭环：创建知识库 → 接入文档 → 解析 → 检索到内容。每一步都有验证点，全程使用 curl。

### 2.1 准备

```bash
# 1. 配置访问令牌（服务端校验用；可逗号分隔多个 OPEN_PLATFORM_TOKENS）
export OPEN_PLATFORM_TOKEN=your-token

# 2. 启动服务
bash scripts/start_open_platform.sh
# 或：.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload

# 3. 验证服务就绪（无需 token）
curl -s http://127.0.0.1:18000/health
```

验证点：`/health` 返回 200 即可继续。

### 2.2 第 1 步：创建知识库

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/knowledge-bases/create \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: 20260818000000000000001" \
  -d '{"kbName":"产品知识库","kbType":"team","teamId":"team_01"}'
```

验证点：响应 `errCode=000000`，`data.kbId` 即后续步骤要用的知识库 ID。响应示例：

```json
{
  "errCode": "000000",
  "errMsg": "success",
  "data": { "kbId": "kb_…", "kbName": "产品知识库", "kbType": "team", "teamId": "team_01" },
  "traceId": "20260818000000000000001"
}
```

> 知识库类型默认 `personal`（无需 teamId）；`team` 库必须传 `teamId`，否则 `100001`。同范围重名返回 `100409`。

### 2.3 第 2 步：接入文档

把一篇 URL 文档接入知识库：

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/knowledge-documents/ingest \
  -H "Authorization: Bearer your-token" -H "Content-Type: application/json" \
  -d '{"kbId":"kb_…","source":{"type":"url","url":"https://example.com/产品白皮书.pdf"}}'
```

验证点：响应含 `docId`（单文档）。接入支持 `url / file / directory / archive` 四种来源，`file` 用 `objectKey` 或 `fileToken` 定位，详见 §6.2。

### 2.4 第 3 步：启动解析并轮询结果

```bash
# 启动解析（异步任务）
curl -s -X POST http://127.0.0.1:18000/api/v1/knowledge-documents/parse \
  -H "Authorization: Bearer your-token" -H "Content-Type: application/json" \
  -d '{"kbId":"kb_…","docId":"doc_…","parseStrategy":{"docType":"pdf"},"executeMode":"async"}'

# 轮询解析状态，直到 parseStatus=success
curl -s "http://127.0.0.1:18000/api/v1/knowledge-documents/parse-result/query?docId=doc_…" \
  -H "Authorization: Bearer your-token"
```

验证点：`parseStatus` 从 `queued → running → success`；未就绪时返回 `200003`，**继续轮询而不是报错**。结果就绪后可签发下载凭证并下载解析产物（§6.3）。

### 2.5 第 4 步：检索你的内容

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/knowledge-search/universal-search \
  -H "Authorization: Bearer your-token" -H "Content-Type: application/json" \
  -d '{"query":"产品核心能力","kbId":"kb_…","mode":"qa","searchType":"hybrid","topK":5}'
```

验证点：`data.results` 返回命中证据列表（`mode=qa` 时附带 `answer` 摘要）。至此，你的应用已经可以通过一个接口检索知识库内容。

### 2.6 下一步：从演示到生产

你已经完成一次完整的「建库 → 入库 → 解析 → 检索」闭环。按你的场景选择以下进阶路线：

#### 2.6.1 路线 A：换用 SDK 或 CLI 接入（正式开发推荐）

curl 适合验证连通性；正式开发建议用 SDK（错误码自动映射为异常、类型提示、自动透传 traceId），或 CLI（运维/脚本）。

Python SDK 最小示例（完整示例见 §9.1）：

```python
from open_ikc_sdk import OpenIKCClient

client = OpenIKCClient(base_url="http://127.0.0.1:18000", token="<token>")
try:
    result = client.search.query(query="产品核心能力", kbId="kb_…")
    for item in result.results:
        print(item.docId, item.score, item.snippet)
finally:
    client.close()
```

CLI 等价命令（完整子命令见 §11.4）：

```bash
ikc search-query --query "产品核心能力" --kb-id kb_… --json
```

#### 2.6.2 路线 B：升级深度检索（带引用编号的综合回答）

普通检索（universal-search）返回证据列表；需要**多轮规划 + 综合回答 + 引用编号**时使用 deep-search（§6.4）。

前置条件：`OPEN_PLATFORM_SEARCH_BACKEND=openai` 且下游 DeepSearch 可用，否则返回 `501001`。

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/knowledge-search/deep-search \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"query":"对比 2025 与 2026 产品白皮书的检索能力差异","kbIds":["kb_…"],"deepSearch":{"maxSteps":5}}'
```

#### 2.6.3 路线 C：接入真实环境（认证与鉴权）

- **认证模式**：`static` 模式（默认）直接采信身份头，仅限内网/测试；生产必须配置 `OPEN_PLATFORM_AUTH_MODE=gateway_header` 或 `oidc_jwt` / `oauth2_introspection`（§5.1）。
- **数据权限**：开启 `OPEN_PLATFORM_AUTHZ_ENABLED=true` 后，请求需携带身份头（`X-User-Id` / `X-Tenant-Id` / `X-User-Roles` 等），个人库仅创建者可访问，否则 `100403`（§5.5）。
- **Token 作用域**：通过管理面创建的 DB token 可用 `resource:action` 作用域（如 `search:query`）限制接口范围，超出返回 `100403`（§7）。

#### 2.6.4 路线 D：运维与管理（Token、监控、在线测试）

- 管理 Portal（`/portal`，需 admin token）：token 创建/撤销、端点监控、MCP/CLI 在线测试、本手册。
- admin token 与业务 token **隔离**，明文仅在创建时返回一次；未配置 `OPEN_PLATFORM_ADMIN_TOKEN` 时管理面返回 `503001`（§7）。

#### 2.6.5 遇到问题时

- 查 §12 常见错误排查表与 §5.4 错误码表（按 `errCode` 定位）。
- 实时权威：`/api/catalog`（业务接口目录）、`/api/error-codes`（错误码目录）、`/openapi.json`（完整规范）。
- 调用方透传 `X-Request-Id` / `X-Trace-Id` 后，可凭 23 位 `traceId` 在日志中心串联全链路排查（§5.2）。

## 3. 接入方式对比（REST / SDK / MCP / CLI）

| 维度 | REST | Python SDK | Java SDK | MCP | CLI |
| --- | --- | --- | --- | --- | --- |
| 传输 | HTTP + JSON | HTTP（httpx） | HTTP/1.1 | stdio / SSE | HTTP |
| 语言 | 任意 | Python 3.12+ | Java 17+ | 任意（AI 客户端） | Bash |
| 错误处理 | errCode 自行判断 | 自动映射为异常层级 | 异常层级 + 传输异常 | 工具错误（含 errCode/traceId） | 退出码 0–6 |
| 异步支持 | 轮询 | `AsyncOpenIKCClient` | 无 | 无 | 无 |
| 典型用途 | 集成/调试 | 业务后端 | 业务后端 | AI Agent 工具 | 运维/CI |
| 详见 | §2、§6 | §9.1 | §9.2 | §10 | §11 |

> 所有方式共用同一套协议（统一响应体、traceId、错误码），因此**中途换接入方式不改变业务语义**。

## 4. 典型使用流程：知识库数据生命周期

一个知识库从创建到被检索，遵循固定生命周期。按以下顺序编排接口即可。

| 阶段 | 你要做的事 | 推荐接口 | 注意 |
| --- | --- | --- | --- |
| 1. 建库 | 规划知识空间（个人/团队/企业），定义元数据 | `knowledge-bases/create` | team 库必传 teamId；重名 `100409` |
| 2. 接入 | 把文档（URL/文件/目录/压缩包）放入库 | `knowledge-documents/ingest` | 幂等：传 `reqId` 防止重复接入 |
| 3. 解析 | 文档 → 结构化文本（分块/OCR） | `knowledge-documents/parse` | 异步任务，轮询 `parse-result/query` |
| 4. 检索 | 让用户基于内容问答/取证 | `knowledge-search/universal-search` / `deep-search` | 见下方「检索与索引」说明 |
| 5. 消费 | 下载解析产物到业务系统 | `issue-download-ticket` → `download` | 凭证一次性，注意 `expireAt` |

**异步任务约定**（接入与解析通用）：

- 任务状态机：`PENDING → INGESTING → INGESTED / SUCCEEDED / PARTIAL_FAILED / FAILED`（解析另有 `PARSING`、`queued/running/success/failed` 表述）。
- 未就绪时查询返回 `200003`（解析结果尚未就绪）——这是**正常状态**，请按 1–2 秒间隔轮询，直到 `success`。
- `executeMode=sync` 可在单次请求内完成并内联返回结果（适用于小文件）；大文档建议 `async`。

> ⚠️ **检索与索引的关系**：当前阶段检索索引需要调用方显式注入（`OPEN_PLATFORM_KB_INDEX_MAP` 或请求体 `index`），**不随 ingest/parse 自动构建**。真实索引引擎落地前，接入文档后不一定立刻可检索，请先确认索引配置。

### 4.1 免库独立解析（场景 B：只要解析能力）

只做**文件/URL → 结构化文本**、不需要知识空间与检索的场景，直接调独立解析接口（§6.3.5）：

- 一次请求完成解析，**不创建知识库、不登记文档**，知识空间不被纯解析任务污染；
- `executeMode=sync` 请求内直接返回内联结果；`async` 返回临时 `docId`（`pdoc_` 前缀）后，用现有 `parse-result/query`、`issue-download-ticket`、`download` 轮询/下载；
- 任务归属调用方身份，仅创建者可查询/下载（`100403`）。

**选型建议**：需要入库、检索与知识空间管理 → 走 §4 上方生命周期；只要解析产物 → 走独立解析。

## 5. 全局约定（所有接口必须遵守）

### 5.1 认证（AUTHN）

| 项 | 约定 |
| --- | --- |
| 请求头 | 每次请求必须携带 `Authorization: Bearer <token>` |
| 服务端 token | `OPEN_PLATFORM_TOKEN`（单）/ `OPEN_PLATFORM_TOKENS`（多，逗号分隔）；未配置时仅校验 Bearer 存在、不比对值 |
| 失败响应 | 缺失或格式错误统一 `100401` + `traceId` |
| 认证模式 | `OPEN_PLATFORM_AUTH_MODE`：`static`（默认）/ `gateway_header` / `oidc_jwt` / `oauth2_introspection` |
| 部署边界 | ⚠️ `static` 直接采信身份头，仅限内网/测试；生产必须 `gateway_header` 或 `oidc_jwt`/`oauth2_introspection` |
| 免鉴权路径 | `/docs`、`/redoc`、`/openapi.json`、`/health`、`/api-browser`、`/api/catalog`、`/api/error-codes`、`/admin`、`/portal` 等 |

### 5.2 链路追踪（traceId）

- 服务端注入 **23 位纯数字** `traceId`；优先复用请求头 `X-Request-Id` / `X-Trace-Id` / `traceId` / `trace_id`。
- 响应头回写 `X-Request-Id` 与 `X-Trace-Id`，响应体顶层携带 `traceId`。
- 调用下游时透传同一组追踪头（`X-Request-Id` / `X-Trace-Id`），便于按链路检索日志。

### 5.3 统一响应体

所有业务响应（成功与失败）均为同一结构：

```json
{ "errCode": "000000", "errMsg": "success", "data": {}, "traceId": "23位数字" }
```

- 参数校验错误（Pydantic/FastAPI）由全局处理器映射为 HTTP 200 + `100001`；框架层 404/405 保留 HTTP 状态码，但仍为统一响应体。
- 判断成功请**看 `errCode` 而不是 HTTP 状态码**：`000000` 即成功。

### 5.4 错误码表

> 当前注册 18 个，实时查询 `/api/error-codes`。

| errCode | errMsg | 层级 | 触发场景 |
| --- | --- | --- | --- |
| `000000` | success | success | 成功 |
| `100001` | 参数校验失败 | parameter | 参数缺失/类型错误/业务校验（如 kbType=team 未传 teamId、scopes 格式错误） |
| `100401` | 未认证或认证失败 | auth | 缺少/错误 Bearer token |
| `100403` | 无权限访问 | authz | AUTHZ 拒绝、越权访问（个人库非创建者、企业库无法识别组织授权、token 作用域不匹配） |
| `100404` | 资源不存在 | resource | kbId/docId/token 不存在 |
| `100405` | 请求方法不允许 | framework | 路径存在但方法不支持 |
| `100409` | 资源冲突 | resource | 同范围 kbName 重复、幂等冲突 |
| `501001` | 接口已预占位，待实现 | placeholder | 占位能力 |
| `999999` | 系统内部错误 | system | 不可预期异常 |
| `503001` | 管理面未启用 | admin | 未配置 `OPEN_PLATFORM_ADMIN_TOKEN`（HTTP 503） |
| `200001` | 创建知识库失败 | business | 知识库创建失败 |
| `200002` | 修改知识库失败 | business | 知识库更新失败 |
| `200010` | 接入知识源失败 | business | 文档接入失败 |
| `200003` | 解析结果尚未就绪 | business | 查询/下载时结果未就绪 |
| `200004` | 下载凭证无效或已过期 | business | ticket 无效 |
| `200011` | 解析失败 | business | 解析任务失败 |
| `300001` | 检索执行失败 | business | 下游检索引擎执行失败（超时/连接失败/返回非成功状态） |
| `200020` | 在线测试执行失败 | admin | MCP / CLI 在线测试未通过 |

### 5.5 鉴权（AUTHZ，可选开启）

- 开关：`OPEN_PLATFORM_AUTHZ_ENABLED=true` 启用；策略 **deny-overrides**，无命中默认拒绝 → `100403`。
- 系统选择：请求头 `X-Auth-System` 或 `OPEN_PLATFORM_AUTH_SYSTEM`（内置 `default`、`digital_employee`）。
- 身份头：`X-User-Id`、`X-Tenant-Id`、`X-User-Roles`、`X-User-Permissions`、`X-User-Deny-Permissions`。
- 数据权限上下文由请求体注入：`kbId/kbIds`、`ownerId`、`orgPath`（检索接口已支持）。
- 各接口授权动作（启用 AUTHZ 后生效）：

| 接口 | action | resource_type | resource_id |
| --- | --- | --- | --- |
| 知识库 create | `create` | `knowledge_base` | — |
| 知识库 update / 详情 | `update` / `read` | `knowledge_base` | kbId |
| 知识库 query | `read` | `knowledge_base` | — |
| 文档 ingest / ingest-and-parse | `write` | `document` | kbId |
| 文档详情 | `read` | `document` | 所属 kbId |
| 解析四接口 | `write` / `read` | `parse` | kbId（parse 启动）或 docId 所属 kbId |
| 检索（universal-search / deep-search / query 别名） | `query` | `search` | 逐 kbId 授权，任一拒绝整体拒绝 |

> 另：**DB token 作用域运行时强制生效**（不依赖 AUTHZ 开关）——创建 token 时配置 `resource:action` 作用域（如 `knowledge_base:read`、`search:query`、`*:*`），调用未命中作用域的业务接口返回 `100403`；环境变量 token 不受作用域限制。作用域仅约束四类业务接口，管理面必须用独立 admin token。

## 6. 接口参考

> 完整 OpenAPI 规范见 `/openapi.json`（Swagger UI：`/docs`，ReDoc：`/redoc`）。

### 6.1 知识库

#### 6.1.1 创建知识库

接口：`POST /api/v1/knowledge-bases/create`

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `kbName` | string | ✅ | 知识库名称，同范围（personal 按 owner / team 按 teamId / enterprise 按 orgId 租户）重复返回 `100409` |
| `kbType` | enum | 否 | `personal`（默认）/ `team` / `enterprise` |
| `teamId` | string | 条件必填 | `kbType=team` 时必填，否则 `100001` |
| `orgId` | string | 否 | `kbType=enterprise` 时建议填写 |
| `kbDesc` | string | 否 | 描述 |
| `bizDomain` | string | 否 | 业务域标签，默认 `general` |
| `visibility` | enum | 否 | `private`（默认）/ `org` |
| `metadataSchema` | array | 否 | 元数据字段定义（见下） |

`metadataSchema[]` 元素：`name`(必填,库内唯一)、`type`(`string|number|integer|boolean|date|datetime|enum|object`)、`required`、`description`、`defaultValue`、`enum[]`、`pattern`、`minLength`、`maxLength`、`example`。

成功响应 `data` 返回完整知识库对象（含 `kbId`、`createTime`/`updateTime` UTC 时间）。

```bash
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-bases/create \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "kbName": "产品知识库", "kbType": "team", "teamId": "team_01",
    "kbDesc": "用于客服问答", "bizDomain": "customer_service", "visibility": "org",
    "metadataSchema": [{"name":"docType","type":"string","enum":["合同","制度"]}]
  }'
```

#### 6.1.2 修改知识库

接口：`POST /api/v1/knowledge-bases/update`

请求体：`kbId`(必填) + 可修改字段。`kbName`/`kbDesc` 传空字符串表示不修改；`metadataSchema` 为空表示保持不变；`kbType` 变更需同步校验 `teamId`/`orgId`。
约束：知识库不存在 `100404`；个人库仅创建者可修改（否则 `100403`）；企业库无法识别组织授权 `100403`。

#### 6.1.3 查询知识库列表

接口：`POST /api/v1/knowledge-bases/query`

请求体：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `kbType` | enum | 过滤类型，不传=全部 |
| `teamId` | string | 查看 team 库时必填 |
| `orgId` | string | 查看 enterprise 库时建议填写，为空用调用主体租户 |
| `ownerId` | string | 个人库创建者过滤（个人库始终按调用方身份收敛） |
| `keyword` | string | 名称/描述关键字 |
| `page` | int | 从 1 起，默认 1 |
| `pageSize` | int | 1–100，默认 20 |

响应 `data`：`{total, page, pageSize, items[]}`。
数据范围收敛：个人库仅本人、团队库需 `teamId`、企业库按 `orgId` 或调用主体租户。

#### 6.1.4 查询知识库详情

接口：`GET /api/v1/knowledge-bases/{kb_id}`

路径参数 `kb_id` 必填。不存在 `100404`；越权 `100403`。响应 `data` 为完整知识库对象。

### 6.2 文档

#### 6.2.1 接入知识源

接口：`POST /api/v1/knowledge-documents/ingest`

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `reqId` | string | 否 | 幂等标识，为空服务端自动生成 |
| `kbId` | string | ✅ | 目标知识库 |
| `teamId` / `orgId` | string | 否 | team/enterprise 库建议传入 |
| `source` | object | ✅ | 来源对象（见下） |
| `docTitle` | string | 否 | 为空自动推断 |
| `tags` | array | 否 | 标签 |
| `metadata` | object | 否 | 自定义元数据 |
| `orchestrationMode` | enum | 否 | `split`（默认，仅接入）/ `quick`（接入后自动解析） |

`source`：`type`(`url|file|directory|archive`，默认 `file`) + 对应字段：

- `url`：`type=url` 时 `url` 必填
- `file`：`objectKey` 或 `fileToken` 至少一个非空
- `directory`/`archive`：`objectKey` 必填；`archive` 支持 `format`(zip/7z/tar/tar.gz)、`passwordRef`、`includePattern`、`excludePattern`；`directory` 支持 `recursive`
- `metadata`：来源元信息

响应 `data`：`{ingestTaskId, docId(单文档), docIds[](目录/压缩包), taskStatus, sourceType, sourceStats, ingestTime}`。
`taskStatus` 枚举：`PENDING / INGESTING / INGESTED / SUCCEEDED / PARTIAL_FAILED / FAILED`。

#### 6.2.2 一体化接入并解析

接口：`POST /api/v1/knowledge-documents/ingest-and-parse`

继承 ingest 全部字段，另加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `parseStrategy` | object | `docType`(`auto|pdf|docx|xlsx|pptx|txt|md|html|jpg|png`)、`parseMethod`(`auto|ocr|txt`)、`backend`(`pipeline|vllm-engine`)、`pageRange`(`["1","2","4-8"]`)、`chunking`(非负整数)、`enhancement` |
| `resultFormat` | object | `type`(`json|markdown|text`)、`includeLayout`、`includeImages`、`imageEncoding`(`url|base64`) |
| `executeMode` | enum | `async`（默认，返回任务 ID）/ `sync`（请求内返回内联结果） |

响应 `data`：`{ingestTaskId, parseTaskId, docId, taskStatus(PENDING/INGESTING/PARSING/SUCCEEDED/FAILED), executeMode, resultInline}`。

#### 6.2.3 查询文档信息

接口：`GET /api/v1/knowledge-documents/{doc_id}`

路径参数 `doc_id` 必填。响应 `data`：`{docId, docTitle, kbId, sourceType, sourceUrl, objectKey, tags, metadata, status, ingestTime, updateTime}`。

### 6.3 解析

#### 6.3.1 启动文档解析

接口：`POST /api/v1/knowledge-documents/parse`

请求体：`reqId`、`kbId`(✅)、`docId`(✅)、`parseStrategy`、`resultFormat`、`executeMode`(`async`默认/`sync`)、`parseMode`(`auto|ocr|structure`，默认 `auto`)、`chunkStrategy`(`auto|fixed|semantic`，默认 `auto`)、`chunkSize`(默认 800)。

响应 `data`：`{taskId, taskStatus(queued/running/success/failed), executeMode, resultInline}`。`executeMode=sync` 时 `resultInline` 含 `fileData(totalPage/parsedPages/pageList)`、`tags`、`summary`、`keywords`、`questions`。

```bash
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-documents/parse \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"kbId":"kb_10001","docId":"doc_10001","parseStrategy":{"docType":"pdf"},"executeMode":"async"}'
```

#### 6.3.2 查询解析结果

接口：`GET /api/v1/knowledge-documents/parse-result/query?docId=doc_10001`

Query 参数：`docId`（必填）。响应 `data`：`{parseStatus(queued/running/success/failed), resultFormat, pageCount, chunkCount, failedReason}`。任务不存在或未就绪返回 `200003`。

#### 6.3.3 获取下载凭证

接口：`GET /api/v1/knowledge-documents/parse-result/issue-download-ticket?docId=doc_10001`

Query 参数：`docId`（必填）。响应 `data`：`{ticket, expireAt, downloadPath}`。结果未就绪 `200003`。

#### 6.3.4 下载解析结果

接口：`GET /api/v1/knowledge-documents/parse-result/download?docId=doc_10001&ticket=xxx`

Query 参数：`docId` + `ticket`（均必填）。凭证无效/过期 `200004`。
> 当前阶段：真实结果存储落地前返回统一体（`data` 含 `docId/taskId/downloadPath/format/note`），后续切换为文件流。

#### 6.3.5 独立解析（免知识库）

接口：`POST /api/v1/knowledge-documents/parse-direct`

对一次性传入的来源直接解析，**不创建知识库、不登记文档**；适合「只要结构化文本、不建库不检索」的场景（选型见 §4.1）。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `source` | object | ✅ | 来源对象，与 ingest 一致（`type=url/file/directory/archive`，字段校验相同） |
| `reqId` | string | 否 | 幂等请求标识 |
| `parseStrategy` | object | 否 | 同 §6.3.1（docType/parseMethod/backend/pageRange/chunking 等） |
| `resultFormat` | object | 否 | 同 §6.3.1（type/includeLayout/includeImages/imageEncoding 等） |
| `executeMode` | enum | 否 | `async`（默认，返回任务轮询）/ `sync`（请求内返回内联结果） |
| `parseMode` | enum | 否 | `auto`（默认）/ `ocr` / `structure` |
| `chunkStrategy` / `chunkSize` | — | 否 | 同 §6.3.1（默认 `auto` / 800） |

响应 `data`：`{taskId, docId（临时标识 pdoc_ 前缀，仅用于后续轮询/下载）, taskStatus, executeMode, resultInline}`。

后续环节复用现有接口，以返回的 `docId` 操作：

- `parse-result/query?docId=<pdoc_xxx>`：轮询解析状态；
- `parse-result/issue-download-ticket?docId=<pdoc_xxx>`：签发一次性下载凭证；
- `parse-result/download?docId=<pdoc_xxx>&ticket=xxx`：下载解析结果。

数据权限：任务归属调用方认证身份，仅创建者可查询/下载（否则 `100403`）；不进入知识库可见范围、不参与检索索引。

```bash
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-documents/parse-direct \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"source":{"type":"url","url":"https://example.com/contract.pdf"},"parseStrategy":{"docType":"pdf"},"executeMode":"sync"}'
```

### 6.4 检索

#### 6.4.1 普通检索

接口：`POST /api/v1/knowledge-search/universal-search`

接口：`POST /api/v1/knowledge-search/query`（兼容别名，行为与 `universal-search` 一致，deprecated，供既有调用方平滑迁移）

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 否 | 检索问题或关键词 |
| `kbId` | string | 条件 | 与 `kbIds` 至少提供一个（否则 `100001`） |
| `kbIds` | array | 条件 | 多库联合检索 |
| `teamId` / `orgId` | string | 否 | team/enterprise 库建议传入 |
| `ownerId` | string | 否 | 资源所有者 ID（owner_only 判定） |
| `orgPath` | string | 否 | 组织路径，如 `/集团/销售中心/华东` |
| `mode` | enum | 否 | `qa`（默认，附简短回答）/ `search`（仅证据） |
| `searchType` | enum | 否 | `fulltext` / `vector` / `hybrid`（默认 `hybrid`） |
| `relNum` | int | 否 | 0–200，关联召回数量，默认 0 |
| `useRerank` | bool | 否 | 是否启用重排，默认 false |
| `score` | float | 否 | 分数阈值，低于阈值的证据不返回 |
| `topK` | int | 否 | 1–100，默认 5 |
| `filters` | object | 否 | 元数据过滤，如 `{"docType":"whitepaper"}` |
| `withCitation` | bool | 否 | 是否返回引用，默认 true |
| `index` | string | 否 | 目标索引名；缺省按知识库映射或下游 collocation 解析 |
| `isOptimize` | bool | 否 | 是否开启查询优化（OpenAI 检索网关时生效），默认 false |

响应 `data`：`{answer, qaNote, total, results[], searchType, usedConfig}`；`results[]` 元素：`{docId, docTitle, score, snippet, citation}`。

- `mode=qa` 且下游不生成回答时，`answer` 为空串、`qaNote` 提示改用深度检索接口；`in_process` 占位后端保留占位回答。
- `searchType` 为实际执行的检索类型；`usedConfig` 为下游实际生效配置摘要（可选）。
- 后端开关：`OPEN_PLATFORM_SEARCH_BACKEND=in_process`（默认，进程内关键词索引，离线/测试用）`| ur`（普通检索走 universal_retriever `/retrieval/search/sync`）`| openai`（走 VectorSearchV2）；相关环境变量：`OPEN_PLATFORM_UR_BASE_URL`、`OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL`、`OPEN_PLATFORM_SEARCH_TIMEOUT_SECONDS`、`OPEN_PLATFORM_KB_INDEX_MAP`。
- 数据范围校验同知识库（个人库仅创建者、团队库需 teamId、企业库按 orgId/租户）；多库逐库 AUTHZ，任一拒绝整体 `100403`。

> ⚠️ 检索索引需调用方显式注入，不随 ingest/parse 自动构建（真实索引引擎落地前）。

```bash
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-search/universal-search \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"query":"产品核心能力","kbIds":["kb_10001"],"mode":"qa","searchType":"hybrid","relNum":10,"useRerank":true,"topK":5,"withCitation":true}'
```

#### 6.4.2 深度检索

接口：`POST /api/v1/knowledge-search/deep-search`

Agentic 多轮深度检索：子查询规划、并行召回、反思与带引用回答；权限收敛与普通检索一致（逐库授权，任一拒绝整体 `100403`）。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 否 | 复杂检索问题 |
| `kbId` | string | 条件 | 与 `kbIds` 至少提供一个（否则 `100001`） |
| `kbIds` | array | 条件 | 多库联合检索 |
| `teamId` / `orgId` | string | 否 | team/enterprise 库建议传入 |
| `ownerId` | string | 否 | 资源所有者 ID（owner_only 判定） |
| `orgPath` | string | 否 | 组织路径，如 `/集团/销售中心/华东` |
| `searchType` | enum | 否 | `fulltext` / `vector` / `hybrid`（默认 `hybrid`） |
| `topK` | int | 否 | 1–100，默认 8（每轮召回窗口） |
| `useRerank` | bool | 否 | 是否启用重排，默认 true |
| `sessionId` | string | 否 | 会话 ID，用于下游记忆检索 |
| `memory` | object | 否 | 调用方注入记忆，如 `{"mode":"caller","items":[]}`（mode 支持 caller / none） |
| `deepSearch` | object | 否 | 深度检索流程控制（见下） |
| `filters` | object | 否 | 元数据过滤 |
| `responseSpec` | object | 否 | 返回增强控制，`include` 支持 `answer` / `citations` / `usedQueries` / `steps`（默认 `["answer","citations","usedQueries"]`） |

`deepSearch` 子字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `maxSteps` | int | 最大检索轮数，默认 5（1–20） |
| `recallTopnPolicy` | enum | 召回窗口策略：`fixed` / `adaptive`（默认 `adaptive`） |
| `subQuery` | object | 子查询拆分：`{enabled, maxSubQueries, mergeStrategy}`；`mergeStrategy` 支持 `rrf` / `union` / `weighted_sum` |
| `stopWhen` | object | 停止条件：`{minEvidence, minFinalScore, maxLatencyMs}` |

响应 `data`：`{answer, total, citations[], usedQueries[], steps[]}`；`citations[]` 为唯一证据列表（引用编号 `[n]` 对应数组下标），元素：`{docId, docTitle, score, snippet, position[], page?}`；`steps[]` 元素：`{stage, query, docsCount, elapsedMs}`（`responseSpec.include` 含 `steps` 时返回）。

- 后端：**仅 `OPEN_PLATFORM_SEARCH_BACKEND=openai` 可用**（走下游 `DeepSearch`），未配置返回 `501001`；超时由 `OPEN_PLATFORM_DEEP_SEARCH_TIMEOUT_SECONDS` 控制；下游未启用 DeepSearch（403）同样映射 `501001`。

```bash
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-search/deep-search \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"query":"对比 2025 与 2026 产品白皮书的检索能力差异，并给出结论","kbIds":["kb_10001"],"searchType":"hybrid","topK":8,"useRerank":true,"deepSearch":{"maxSteps":5,"subQuery":{"enabled":true,"maxSubQueries":3}}}'
```

响应样例：

```json
{
  "errCode": "000000",
  "errMsg": "success",
  "data": {
    "answer": "综合证据，2025 版侧重……（带 [1][2] 引用编号作答）",
    "total": 2,
    "citations": [
      {"docId": "doc_10001", "docTitle": "2025 产品白皮书", "score": 0.92, "snippet": "……", "position": [82, 120], "page": 3},
      {"docId": "doc_10002", "docTitle": "2026 产品白皮书", "score": 0.9, "snippet": "……", "position": [10, 58], "page": 1}
    ],
    "usedQueries": ["2025 白皮书检索能力", "2026 白皮书检索能力", "差异对比"],
    "steps": [
      {"stage": "plan", "query": "2025 白皮书检索能力", "docsCount": 6, "elapsedMs": 120.5}
    ]
  },
  "traceId": "20260817000000000000001"
}
```

## 7. 管理面接口（`/admin/*`，运维用途）

> 管理面与业务接口隔离：独立 token、不进入业务 catalog、请求不纳入业务监控统计。

- 鉴权：`Authorization: Bearer <admin-token>`，token 来自环境变量 `OPEN_PLATFORM_ADMIN_TOKEN`（**与业务 token 隔离，禁止复用**）。
- 未配置该环境变量时管理面默认关闭，所有请求返回 `503001`（HTTP 503）。
- 启动脚本未配置时会自动生成随机 token 并打印（`[admin] 管理面已启用，本次 OPEN_PLATFORM_ADMIN_TOKEN=...`）。

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/overview` | 总览（在线并发、请求统计 + `activeTokens`） |
| GET | `/admin/endpoints?window_minutes=` | 端点聚合统计 |
| GET | `/admin/requests?limit=` | 最近请求明细（limit 1–200，默认 50） |
| GET | `/admin/stats/token?window_minutes=` | Token 维度统计 |
| GET | `/admin/tokens?include_revoked=` | Token 列表（默认不含已撤销） |
| POST | `/admin/tokens` | 创建 token：`{name(必填), owner, scopes[], expiresInSeconds}`；`scopes` 为 `resource:action`（支持 `*`），≤32 个、单个 ≤64 字符；响应含**仅此一次**的明文 `token` |
| POST | `/admin/tokens/{token_id}/revoke` | 撤销 token（不存在返回 `100404`） |
| POST | `/admin/test/mcp` | MCP 在线冒烟：`{tool, token, baseUrl}` |
| POST | `/admin/test/cli` | CLI 在线测试：`{command, args[], token, baseUrl, identity}`（白名单命令） |
| GET | `/admin/test/whitelist` | CLI 命令 / MCP 工具白名单 |

DB token 存储于 SQLite（`OPEN_PLATFORM_DB_PATH` 可覆盖，默认 `data/open_ikc_platform.db`），库中只存 sha256。

## 8. 系统路由（无需业务鉴权）

| Path | 说明 |
| --- | --- |
| `/`、`/health` | 首页、健康检查 |
| `/docs`、`/redoc`、`/openapi.json` | 离线 Swagger UI / ReDoc / OpenAPI 规范 |
| `/api-browser` | API 浏览页 |
| `/api/catalog` | 对外业务 API 目录（**开发时以此为准**） |
| `/api/error-codes` | 错误码目录 |
| `/portal` | 管理 Portal 前端壳 |

## 9. SDK 接入

### 9.1 Python SDK（`open-ikc-sdk` v1.0.0）

```bash
pip install sdk/python
```

```python
from open_ikc_sdk import CallerIdentity, OpenIKCClient

client = OpenIKCClient(
    base_url="http://127.0.0.1:18000",
    token="<OPEN_PLATFORM_TOKEN>",
    identity=CallerIdentity(user_id="u100", tenant_id="t1"),
)

kb = client.knowledge_bases.create(kbName="产品知识库", kbType="team", teamId="team_01")
page = client.knowledge_bases.query(page=1, pageSize=20, keyword="客服")
detail = client.knowledge_bases.get(kb.kbId)
client.close()
```

- 同步 `OpenIKCClient` / 异步 `AsyncOpenIKCClient`；异常体系按错误码映射（`OpenIKCApiException` 子类）。
- 环境变量：`OPEN_PLATFORM_BASE_URL` / `OPEN_PLATFORM_TOKEN(S)` / `OPEN_PLATFORM_USER_ID` / `OPEN_PLATFORM_TENANT_ID` / `OPEN_PLATFORM_ROLES`；显式传参优先。
- 检索：`client.search.query(...)` 普通检索（对应 `/universal-search`，`/query` 兼容别名亦可），参数 `query`、`kbId`/`kbIds`（至少一个）、`teamId`/`orgId`、`ownerId`、`orgPath`、`mode`、`searchType`、`relNum`、`useRerank`、`score`、`topK`、`filters`、`withCitation`、`index`、`isOptimize`；`client.search.deep_search(...)` 深度检索（对应 `/deep-search`，需后端 `openai`），参数 `query`、`kbId`/`kbIds`、`teamId`/`orgId`、`ownerId`、`orgPath`、`searchType`、`topK`、`useRerank`、`sessionId`、`memory`、`deepSearch`、`filters`、`responseSpec`。
- 完整示例：`sdk/python/examples/quickstart.py`（同步全链路）、`sdk/python/examples/async_quickstart.py`。

### 9.2 Java SDK（`io.openikc:open-ikc-sdk:1.0.0`，Java 17+，零第三方依赖）

```java
OpenIKCClient client = new OpenIKCClient.Builder("http://127.0.0.1:18000")
        .token("<OPEN_PLATFORM_TOKEN>")
        .identity(CallerIdentity.builder().userId("u100").tenantId("t1").build())
        .build();
KnowledgeBase kb = client.knowledgeBases().create("产品知识库", "team", "team_01", null, "用于客服问答");
KnowledgeBase.KnowledgeBasePage page = client.knowledgeBases().query(1, 20, null, "客服");
client.close();
```

- 支持 `OpenIKCClient.fromEnv()`（`OPEN_PLATFORM_BASE_URL/TOKEN/USER_ID/TENANT_ID/ROLES`）。
- 异常层级：`ValidationException`(100001) / `UnauthorizedException`(100401) / `ForbiddenException`(100403) / `NotFoundException`(100404) / `MethodNotAllowedException`(100405) / `ConflictException`(100409) / `NotImplementedException`(501001) / `SystemException`(999999) / 其余 `BusinessException`；传输层 `OpenIKCConnectionException/TimeoutException/ProtocolException`。
- ⚠️ 必须固定 HTTP/1.1（JDK 默认 h2c 升级会被 uvicorn 拒绝），SDK 已内置；traceId 自动生成 23 位数字，可 `Builder.traceId(...)` 固定复用。

## 10. MCP Server 接入

MCP 是对现有 REST 接口的上层封装（**不新增第五类接口**），14 个工具与业务接口一一对应。

### 10.1 运行方式

```bash
pip install "sdk/python[mcp]"          # 依赖 mcp>=2.0

python -m open_ikc_sdk.mcp                        # stdio（默认）
python -m open_ikc_sdk.mcp --base-url http://127.0.0.1:18000 --token <token>
python -m open_ikc_sdk.mcp --transport sse        # 其他传输方式
```

### 10.2 客户端配置示例（Claude Desktop `claude_desktop_config.json`）

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

> `command` 需指向安装了 `open-ikc-sdk[mcp]` 的 Python 解释器；token 与身份头用于平台鉴权。

### 10.3 工具清单与参数

**知识库**

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `kb_create` | `kbName`(必填), `kbType`="personal", `teamId`, `orgId`, `kbDesc`, `bizDomain`="general", `visibility`="private", `metadataSchema`(object/array) | 创建知识库 |
| `kb_update` | `kbId`(必填), 其余同创建（均可选） | 局部更新（缺省字段保留现有值） |
| `kb_query` | `page`=1, `pageSize`=20, `kbType`, `teamId`, `orgId`, `ownerId`, `keyword` | 分页查询 |
| `kb_get` | `kbId`(必填) | 查询详情 |

**文档**

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `doc_ingest` | `kbId`(必填), `source`(object 必填), `reqId`, `teamId`, `orgId`, `docTitle`, `tags`(array), `metadata`(object), `orchestrationMode`="split" | 接入知识源 |
| `doc_ingest_and_parse` | 同 `doc_ingest` + `parseStrategy`(object), `resultFormat`(object), `executeMode`="async" | 一体化接入并解析 |
| `doc_get` | `docId`(必填) | 查询文档信息 |

`source` 结构（与 REST 一致）：

```json
{"type": "url", "url": "https://example.com/a.pdf"}
{"type": "file", "objectKey": "oss://bucket/obj", "fileToken": "..."}
{"type": "directory", "objectKey": "...", "directory": {"recursive": true}}
{"type": "archive", "objectKey": "...", "archive": {"format": "zip"}}
```

**解析**

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `parse_start` | `kbId`(必填), `docId`(必填), `reqId`, `parseStrategy`(object), `resultFormat`(object), `executeMode`="async", `parseMode`, `chunkStrategy`, `chunkSize` | 启动解析任务 |
| `parse_query` | `docId`(必填) | 查询解析状态与产物摘要 |
| `parse_issue_ticket` | `docId`(必填) | 签发一次性下载凭证 |
| `parse_download` | `docId`(必填), `ticket`(必填), `toPath` | 下载解析结果（文件流落地前返回 JSON 壳元数据） |

**检索**

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `search_query` | `query`, `kbId`/`kbIds`(至少一个), `teamId`/`orgId`, `ownerId`, `orgPath`, `mode`, `searchType`, `relNum`, `useRerank`, `score`, `topK`, `filters`, `withCitation`, `index`, `isOptimize` | 普通检索（证据列表） |
> `kbId` / `kbIds` / `ownerId` / `orgPath` 同时是平台 AUTHZ 数据权限上下文，原样透传。

**系统**

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `sys_catalog` | — | 拉取 `/api/catalog` |
| `sys_error_codes` | — | 拉取 `/api/error-codes` |

### 10.4 工具返回与错误

- 返回：JSON 序列化 dict（复用 SDK 模型）。
- 错误：SDK `OpenIKCError` 子类转为工具错误，错误信息含 `errCode` / `errMsg` / `traceId`。

## 11. CLI 接入

### 11.1 安装与入口

```bash
pip install "sdk/python[cli]"          # 依赖 typer>=0.15

python -m open_ikc_sdk.cli --help      # 模块入口
ikc --help                             # 安装后入口（pyproject 注册）
```

### 11.2 全局选项（位于子命令之前）

| 选项 | 说明 |
| --- | --- |
| `--base-url` | 覆盖平台地址（默认 `http://127.0.0.1:18000`） |
| `--token` | 覆盖 token |
| `--user-id` / `--tenant-id` / `--roles` | AUTHZ 身份头 |
| `--json` | 输出原始 JSON（默认渲染简洁表格） |
| `--debug` | 打印异常堆栈 |

### 11.3 退出码约定

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 业务错误（2xxxxx 或未知错误码） |
| 2 | 未认证（100401） |
| 3 | 无权限（100403） |
| 4 | 资源不存在（100404） |
| 5 | 平台占位未实现（501001） |
| 6 | 传输层错误（连接 / 超时 / HTTP 状态） |

### 11.4 子命令与示例

**知识库**

```bash
ikc kb-create 产品知识库 --kb-type team --team-id team_01 --kb-desc "用于客服问答" --visibility org
ikc kb-update kb_10001 --kb-name 产品知识库-客服版
ikc kb-list --page 1 --page-size 20 --keyword 客服
ikc kb-get kb_10001
```

**文档**（`source` 以 JSON 字符串接收，复杂参数同理）

```bash
ikc doc-ingest kb_10001 '{"type":"url","url":"https://example.com/a.pdf"}' --doc-title 文档 --tags '["合同"]'
ikc doc-ingest-and-parse kb_10001 '{"type":"url","url":"https://example.com/a.pdf"}' --execute-mode async
ikc doc-get doc_10001
```

**解析**

```bash
ikc parse-start kb_10001 doc_10001 --execute-mode async
ikc parse-query doc_10001
ikc parse-ticket doc_10001
ikc parse-download doc_10001 <ticket> --to-path ./result.json
```

**检索**

```bash
ikc search-query --query "产品能力" --kb-id kb_10001 --owner-id u100 --org-path /集团/销售中心/华东 --search-type hybrid --top-k 5
```

**系统**

```bash
ikc sys-catalog
ikc sys-error-codes
```

## 12. 常见错误排查

| 现象 | 原因与处理 |
| --- | --- |
| `100401` | 缺 Bearer 头或 token 错误；确认 `OPEN_PLATFORM_TOKEN(S)` 配置 |
| `100403` | AUTHZ 拒绝（开启时身份头缺失/角色无权限）；DB token 作用域不匹配；个人库非创建者访问 |
| `100404` | kbId/docId/token_id 不存在或已被撤销 |
| `100409` | 同范围 kbName 重复；先 query 确认或换名 |
| `503001` | 管理面未配置 `OPEN_PLATFORM_ADMIN_TOKEN`，重启时配置或使用脚本自动生成值 |
| `200003` | 解析结果未就绪，轮询 `parse-result/query` 直到 `success` |
| `200004` | 下载凭证过期/无效，重新 `issue-download-ticket` |
| `300001` | 检索执行失败；确认 `OPEN_PLATFORM_SEARCH_BACKEND` 后端与下游（UR / OpenAI 检索网关）配置、网络与超时 |
| `501001` | 占位未实现；深度检索需配置 `OPEN_PLATFORM_SEARCH_BACKEND=openai` 且下游 DeepSearch 可用 |
| `100001` + HTTP 200 | 参数校验失败，检查必填/枚举/条件字段（如 `kbType=team` 缺 `teamId`、`source.type=url` 缺 `url`、检索缺 `kbId/kbIds`） |

## 13. 下一步与补充约定

- 实时权威：接口以 `/api/catalog`（业务目录）与 `/openapi.json` 为准；错误码以 `/api/error-codes` 为准；管理面接口不进入 catalog。
- 完整可运行示例：`sdk/python/examples/quickstart.py`（同步全链路）、`sdk/python/examples/async_quickstart.py`；Java 用法见 `sdk/java/README.md`。
- 管理 Portal（`/portal`）：token 管理、端点监控、MCP/CLI 在线测试、本手册应用内页面。
- 未实现能力必须返回 `501001`，**禁止静默空成功**；调用下游时透传追踪头（`X-Request-Id` / `X-Trace-Id`），日志经 `ikc-log-center` 按 traceId 串联检索。
- 场景选型：需要知识空间与检索 → 走「建库 → 入库 → 解析 → 检索」生命周期；只要解析能力 → 用 `parse-direct`（§6.3.5），仍属解析能力域，不新增第五类能力。
- MCP / CLI 边界：不新增、不修改平台 REST 路由与 `catalog.py`；不暴露 reindex / task query 等未落地能力。
- 接口若变更，以当前代码与 `/api/catalog` 为最新权威；本文档与代码不一致时以代码为准。
