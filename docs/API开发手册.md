# OpenIKC 开放平台 API 开发手册

> 适用版本：open-ikc-api（FastAPI 北向开放平台）· 服务端口 18000 · 协议 HTTPS/HTTP + JSON
> 权威依据：当前代码实现 > `docs/` 设计文档。接口定义以 `/api/catalog`、`/openapi.json` 实时为准。

## 1. 平台概述

平台对外提供**四大类业务能力**（禁止自行扩展第五类）：

| 能力 | 路径前缀 | 接口数 | 说明 |
| --- | --- | --- | --- |
| 知识库 | `/api/v1/knowledge-bases` | 4 | 创建 / 修改 / 列表查询 / 详情 |
| 文档 | `/api/v1/knowledge-documents` | 3 | 接入知识源 / 一体化接入解析 / 文档信息 |
| 解析 | `/api/v1/knowledge-documents/parse*` | 4 | 启动解析 / 查询结果 / 签发下载凭证 / 下载 |
| 检索 | `/api/v1/knowledge-search` | 2 | 普通检索（证据列表）/ 深度检索（Agentic 多轮 + 带引用回答） |
| 合计 | — | 13 | 业务接口共 13 个（`/query` 为普通检索兼容别名，不计新增） |

另有**管理面**（`/admin/*`，运维用途，独立鉴权）、**系统路由**（健康检查、API 目录、错误码目录、文档页），以及上层 **Python SDK / Java SDK / MCP Server / CLI** 四种接入方式。

**开发环境**

- Python ≥ 3.12；服务默认端口 `18000`
- 启动：`bash scripts/start_open_platform.sh`（或 `.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload`）
- 文档入口：Swagger UI `/docs`、ReDoc `/redoc`、API 浏览页 `/api-browser`（均免 token，离线可用）

## 2. 快速开始（3 分钟跑通）

```bash
# 1. 配置访问令牌（环境变量方式）
export OPEN_PLATFORM_TOKEN=your-token          # 服务端校验；可逗号分隔多个 OPEN_PLATFORM_TOKENS

# 2. 启动服务
bash scripts/start_open_platform.sh

# 3. 第一个请求：创建知识库
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-bases/create \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: 20260817000000000000001" \
  -d '{"kbName":"产品知识库","kbType":"team","teamId":"team_01"}'
```

响应：

```json
{
  "errCode": "000000",
  "errMsg": "success",
  "data": {
    "kbId": "kb_…（17 位数字）",
    "kbName": "产品知识库",
    "kbType": "team",
    "teamId": "team_01",
    "orgId": "",
    "kbDesc": "",
    "bizDomain": "general",
    "visibility": "private",
    "metadataSchema": [],
    "createTime": "2026-08-17T…Z",
    "updateTime": "2026-08-17T…Z"
  },
  "traceId": "20260817000000000000001"
}
```

## 3. 全局约定（所有接口必须遵守）

### 3.1 认证（AUTHN）

| 项 | 约定 |
| --- | --- |
| 请求头 | 每次请求必须携带 `Authorization: Bearer <token>` |
| 服务端 token | `OPEN_PLATFORM_TOKEN`（单）/ `OPEN_PLATFORM_TOKENS`（多，逗号分隔）；未配置时仅校验 Bearer 存在、不比对值 |
| 失败响应 | 缺失或格式错误统一 `100401` + `traceId` |
| 认证模式 | `OPEN_PLATFORM_AUTH_MODE`：`static`（默认）/ `gateway_header` / `oidc_jwt` / `oauth2_introspection` |
| 部署边界 | ⚠️ `static` 直接采信身份头，仅限内网/测试；生产必须 `gateway_header` 或 `oidc_jwt`/`oauth2_introspection` |
| 免鉴权路径 | `/docs`、`/redoc`、`/openapi.json`、`/health`、`/api-browser`、`/api/catalog`、`/api/error-codes`、`/admin`、`/portal` 等 |

### 3.2 链路追踪（traceId）

- 服务端注入 **23 位纯数字** `traceId`；优先复用请求头 `X-Request-Id` / `X-Trace-Id` / `traceId` / `trace_id`。
- 响应头回写 `X-Request-Id` 与 `X-Trace-Id`，响应体顶层携带 `traceId`。
- 调用下游时透传同一组追踪头（`X-Request-Id` / `X-Trace-Id`），便于按链路检索日志。

### 3.3 统一响应体

所有业务响应（成功与失败）均为同一结构：

```json
{ "errCode": "000000", "errMsg": "success", "data": {}, "traceId": "23位数字" }
```

- 参数校验错误（Pydantic/FastAPI）由全局处理器映射为 HTTP 200 + `100001`；框架层 404/405 保留 HTTP 状态码，但仍为统一响应体。

### 3.4 错误码表（当前注册 17 个，实时查询 `/api/error-codes`）

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

### 3.5 鉴权（AUTHZ，可选开启）

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

## 4. 业务接口详细定义

### 4.1 知识库

#### 4.1.1 创建知识库 `POST /api/v1/knowledge-bases/create`

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

#### 4.1.2 修改知识库 `POST /api/v1/knowledge-bases/update`

请求体：`kbId`(必填) + 可修改字段。`kbName`/`kbDesc` 传空字符串表示不修改；`metadataSchema` 为空表示保持不变；`kbType` 变更需同步校验 `teamId`/`orgId`。
约束：知识库不存在 `100404`；个人库仅创建者可修改（否则 `100403`）；企业库无法识别组织授权 `100403`。

#### 4.1.3 查询知识库列表 `POST /api/v1/knowledge-bases/query`

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

#### 4.1.4 查询知识库详情 `GET /api/v1/knowledge-bases/{kb_id}`

路径参数 `kb_id` 必填。不存在 `100404`；越权 `100403`。响应 `data` 为完整知识库对象。

### 4.2 文档

#### 4.2.1 接入知识源 `POST /api/v1/knowledge-documents/ingest`

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

#### 4.2.2 一体化接入并解析 `POST /api/v1/knowledge-documents/ingest-and-parse`

继承 ingest 全部字段，另加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `parseStrategy` | object | `docType`(`auto|pdf|docx|xlsx|pptx|txt|md|html|jpg|png`)、`parseMethod`(`auto|ocr|txt`)、`backend`(`pipeline|vllm-engine`)、`pageRange`(`["1","2","4-8"]`)、`chunking`(非负整数)、`enhancement` |
| `resultFormat` | object | `type`(`json|markdown|text`)、`includeLayout`、`includeImages`、`imageEncoding`(`url|base64`) |
| `executeMode` | enum | `async`（默认，返回任务 ID）/ `sync`（请求内返回内联结果） |

响应 `data`：`{ingestTaskId, parseTaskId, docId, taskStatus(PENDING/INGESTING/PARSING/SUCCEEDED/FAILED), executeMode, resultInline}`。

#### 4.2.3 查询文档信息 `GET /api/v1/knowledge-documents/{doc_id}`

路径参数 `doc_id` 必填。响应 `data`：`{docId, docTitle, kbId, sourceType, sourceUrl, objectKey, tags, metadata, status, ingestTime, updateTime}`。

### 4.3 解析

#### 4.3.1 启动文档解析 `POST /api/v1/knowledge-documents/parse`

请求体：`reqId`、`kbId`(✅)、`docId`(✅)、`parseStrategy`、`resultFormat`、`executeMode`(`async`默认/`sync`)、`parseMode`(`auto|ocr|structure`，默认 `auto`)、`chunkStrategy`(`auto|fixed|semantic`，默认 `auto`)、`chunkSize`(默认 800)。

响应 `data`：`{taskId, taskStatus(queued/running/success/failed), executeMode, resultInline}`。`executeMode=sync` 时 `resultInline` 含 `fileData(totalPage/parsedPages/pageList)`、`tags`、`summary`、`keywords`、`questions`。

```bash
curl -X POST http://127.0.0.1:18000/api/v1/knowledge-documents/parse \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"kbId":"kb_10001","docId":"doc_10001","parseStrategy":{"docType":"pdf"},"executeMode":"async"}'
```

#### 4.3.2 查询解析结果 `GET /api/v1/knowledge-documents/parse-result/query?docId=doc_10001`

Query 参数：`docId`（必填）。响应 `data`：`{parseStatus(queued/running/success/failed), resultFormat, pageCount, chunkCount, failedReason}`。任务不存在或未就绪返回 `200003`。

#### 4.3.3 获取下载凭证 `GET /api/v1/knowledge-documents/parse-result/issue-download-ticket?docId=doc_10001`

Query 参数：`docId`（必填）。响应 `data`：`{ticket, expireAt, downloadPath}`。结果未就绪 `200003`。

#### 4.3.4 下载解析结果 `GET /api/v1/knowledge-documents/parse-result/download?docId=doc_10001&ticket=xxx`

Query 参数：`docId` + `ticket`（均必填）。凭证无效/过期 `200004`。
> 当前阶段：真实结果存储落地前返回统一体（`data` 含 `docId/taskId/downloadPath/format/note`），后续切换为文件流。

### 4.4 检索

#### 4.4.1 普通检索 `POST /api/v1/knowledge-search/universal-search`

> 兼容别名：`POST /api/v1/knowledge-search/query` 行为与之一致（deprecated），供既有调用方平滑迁移。

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

#### 4.4.2 深度检索 `POST /api/v1/knowledge-search/deep-search`

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

响应 `data`：`{answer, total, results[], citations[], usedQueries[], steps[]}`；`results[]` 元素同普通检索；`citations[]` 元素：`{docId, docTitle, score, snippet, position[]}`；`steps[]` 元素：`{stage, query, docsCount, elapsedMs}`（`responseSpec.include` 含 `steps` 时返回）。

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
    "total": 12,
    "results": [
      {"docId": "doc_10001", "docTitle": "2025 产品白皮书", "score": 0.92, "snippet": "……", "citation": {}}
    ],
    "citations": [
      {"docId": "doc_10001", "docTitle": "2025 产品白皮书", "score": 0.92, "snippet": "……", "position": [82, 120]}
    ],
    "usedQueries": ["2025 白皮书检索能力", "2026 白皮书检索能力", "差异对比"],
    "steps": [
      {"stage": "plan", "query": "2025 白皮书检索能力", "docsCount": 6, "elapsedMs": 120.5}
    ]
  },
  "traceId": "20260817000000000000001"
}
```

## 5. 管理面接口（`/admin/*`，运维用途）

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

## 6. 系统路由（无需业务鉴权）

| Path | 说明 |
| --- | --- |
| `/`、`/health` | 首页、健康检查 |
| `/docs`、`/redoc`、`/openapi.json` | 离线 Swagger UI / ReDoc / OpenAPI 规范 |
| `/api-browser` | API 浏览页 |
| `/api/catalog` | 对外业务 API 目录（**开发时以此为准**） |
| `/api/error-codes` | 错误码目录 |
| `/portal` | 管理 Portal 前端壳 |

## 7. SDK 接入

### 7.1 Python SDK（`open-ikc-sdk` v1.0.0）

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

### 7.2 Java SDK（`io.openikc:open-ikc-sdk:1.0.0`，Java 17+，零第三方依赖）

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

## 8. MCP Server 接入

MCP 是对现有 REST 接口的上层封装（**不新增第五类接口**），15 个工具与业务接口一一对应。

### 8.1 运行方式

```bash
pip install "sdk/python[mcp]"          # 依赖 mcp>=2.0

python -m open_ikc_sdk.mcp                        # stdio（默认）
python -m open_ikc_sdk.mcp --base-url http://127.0.0.1:18000 --token <token>
python -m open_ikc_sdk.mcp --transport sse        # 其他传输方式
```

### 8.2 客户端配置示例（Claude Desktop `claude_desktop_config.json`）

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

### 8.3 工具清单与参数（15 个）

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
| `deep_search` | `query`, `kbId`/`kbIds`(至少一个), `teamId`/`orgId`, `ownerId`, `orgPath`, `searchType`, `topK`, `useRerank`, `sessionId`, `memory`, `deepSearch`, `filters`, `responseSpec` | 深度检索（Agentic 多轮 + 带引用回答） |

> `kbId` / `kbIds` / `ownerId` / `orgPath` 同时是平台 AUTHZ 数据权限上下文，原样透传。

**系统**

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `sys_catalog` | — | 拉取 `/api/catalog` |
| `sys_error_codes` | — | 拉取 `/api/error-codes` |

### 8.4 工具返回与错误

- 返回：JSON 序列化 dict（复用 SDK 模型）。
- 错误：SDK `OpenIKCError` 子类转为工具错误，错误信息含 `errCode` / `errMsg` / `traceId`。

## 9. CLI 接入

### 9.1 安装与入口

```bash
pip install "sdk/python[cli]"          # 依赖 typer>=0.15

python -m open_ikc_sdk.cli --help      # 模块入口
ikc --help                             # 安装后入口（pyproject 注册）
```

### 9.2 全局选项（位于子命令之前）

| 选项 | 说明 |
| --- | --- |
| `--base-url` | 覆盖平台地址（默认 `http://127.0.0.1:18000`） |
| `--token` | 覆盖 token |
| `--user-id` / `--tenant-id` / `--roles` | AUTHZ 身份头 |
| `--json` | 输出原始 JSON（默认渲染简洁表格） |
| `--debug` | 打印异常堆栈 |

### 9.3 退出码约定

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 业务错误（2xxxxx 或未知错误码） |
| 2 | 未认证（100401） |
| 3 | 无权限（100403） |
| 4 | 资源不存在（100404） |
| 5 | 平台占位未实现（501001） |
| 6 | 传输层错误（连接 / 超时 / HTTP 状态） |

### 9.4 子命令与示例（15 个）

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
ikc deep-search --query "对比 2025 与 2026 产品白皮书的检索能力差异" --kb-id kb_10001 --search-type hybrid --top-k 8 --use-rerank
```

**系统**

```bash
ikc sys-catalog
ikc sys-error-codes
```

## 10. 常见错误排查

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

## 11. 补充约定

- 未实现能力必须返回 `501001`，**禁止静默空成功**。
- 调用下游时透传追踪头（`X-Request-Id` / `X-Trace-Id`），日志经 `ikc-log-center` 按 traceId 串联检索。
- 接口若变更，以 `/api/catalog`（业务目录）与 `/openapi.json` 为最新权威；管理面接口不进入 catalog。
- MCP / CLI 边界：不新增、不修改平台 REST 路由与 `catalog.py`；不暴露 reindex / task query 等未落地能力。
