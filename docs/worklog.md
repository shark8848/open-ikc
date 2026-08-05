# 工作日志（Worklog）

> 用途：记录每次/每天的任务完成情况、进展、问题与总结；**每天开工前先读最近条目继承上下文**。
> 约定见 `AGENTS.md`「工作日志与每日继承」章节。按日期追加，每天一个条目。
> 每个工作日 `17:30` 触发例行提交任务（约定见 `AGENTS.md` §8.1）。

## 2026-08-05

### 任务：解析域真实实现落地（parse / parse-result query / download ticket / download）

- 完成：新增 `app/services/parse_store.py`（进程内存储：`ParseTaskRecord`/`ParseResultRecord`/`ParseTicketRecord`、`ParseTaskStore` 任务与结果原子读写、`ParseTicketStore` 短期凭证签发与校验、`generate_parse_task_id` `parse_`+17 位数字）。
- 完成：新增 `app/schemas/parse.py`（`DocumentParseRequest` 含 parseStrategy/resultFormat/executeMode/parseMode/chunkStrategy/chunkSize、查询/凭证/下载响应模型统一 envelope）。
- 完成：`app/core/error_codes.py` 新增 `ParseErrorCodes`——`200003 解析结果尚未就绪`、`200004 下载凭证无效或已过期`、`200011 解析失败`（200001 保留归属知识库 CREATE_FAILED，V2「解析失败 200001」按现状让位，解析域走 20001x 区间）；接入 `error_code_catalog()`。
- 完成：`app/core/responses.py` 解析域响应构造收敛（parse/query/ticket/download 四构造器）。
- 完成：`app/services/parse.py` 三占位替换为真实实现——parse 文档存在 404、个人库越权 403、幂等（queued/running/success 复用既有任务，failed 拒绝重发）、async 登记 queued、sync 请求内完成返回内联 resultInline、文档状态联动（PARSING/SUCCEEDED 写回 DocumentStore）；query 无任务 200003；issue-download-ticket 非 success 200003；download 凭证无效/不匹配 200004。
- 完成：`app/routers/parse.py` 四路由接入 `authorize_or_raise`（parse/read + `doc_id/kb_id/kb_type/owner_id/org_path` 上下文）；`app/services/document_store.py` 新增 `update_status`。
- 完成：新增 `tests/test_parse.py`（15 例，覆盖 async/sync/404/403/幂等/query/凭证签发与下载/无效凭证 200004/跨文档凭证 200004/AUTHZ/错误码注册）；全量测试 **104 passed**（原 89+15）。
- 实测：沙箱外启动 uvicorn，sync 全链路（create→ingest→parse sync→ticket→download）`000000` 且 traceId 回写；async queued 上签发凭证 `200003`、无效凭证 `200004`；`/api/error-codes` 含 200003/200004/200011。
- 同步：README §当前实现进度 增补解析域落地（第 6 条），检索仍为占位（第 7 条）。
- 决策：download 在真实结果存储落地前返回统一 JSON 体（含下载说明），后续切换 StreamingResponse 文件流；错误码 200001 不按 V2 字面重排（保持 KB 契约稳定）。
- 下一步：检索域（search/query）真实实现按同一范式推进；解析/文档/知识库存储替换真实持久化的迁移点仍收敛在各自 store。

## 2026-08-04

### 任务：仓库梳理 + 进行中改动收尾 + 契约建设

- 完成：确认并推进工作区进行中改动（`authz/adapters.py` 身份字段兜底、`middlewares.py` 系统路由免鉴权）。
- 完成：新增 `tests/test_authz_adapters.py`（12 例）与 `tests/test_auth_middleware.py`（5 例 + 8 个参数化路径）；`_pick_identity_value` 增加空值（含空列表/集合）兜底；全量测试 **25 passed**。
- 完成：创建 `AGENTS.md` 项目实现契约，`CLAUDE.md` 收敛为 `@AGENTS.md` 导入入口（Codex / Claude Code 共用）。
- 完成：契约新增「Token 效率与协作约定」与「工作日志与每日继承」章节；新建本日志文件。
- 完成：契约新增 §8.1「每日 17:30 例行提交」；当天改动按约定提交并推送到 `github` 远端。
- 完成：统一 `catalog.py` 文档查询路径 `{docId}` → `{doc_id}`（与路由一致）。
- 完成：新增 `tests/test_authz_policy.py`（14 例），覆盖资源 ID 白/黑名单、`kb_ids` 上下文、owner-only、org 路径前缀、部门、租户与 required_role 条件；全量测试 **39 passed**。

### 任务：知识库 create/update 首个真实实现落地

- 完成：新增 `app/services/knowledge_base_store.py`（进程内线程安全存储 + 唯一键冲突判定，`kb_`+17 位数字 ID）。
- 完成：`KnowledgeBaseService.create/update/get_or_raise` 真实业务逻辑：同范围 `kbName` 重复 `100409`、更新不存在 `100404`、个人库仅创建者可改 `100403`、企业库组织识别（orgId 优先，其次租户）失败 `100403`、元数据字段名去重 `100001`。
- 完成：`responses.py` 改为基于存储记录构造响应（真实 kbId 与 UTC 时间戳），移除硬编码占位。
- 完成：`routers/knowledge_base.py` 接入 `authorize_or_raise`（create/update + `kb_id/kb_type/owner_id/org_path` 数据上下文）。
- 完成：新增 `tests/test_knowledge_base.py`（16 例）；`test_auth_middleware.py` 补 store 复位 fixture；全量测试 **55 passed**。

### 任务：文档服务接口信息同步核查

- 完成：核查文档/解析域路由 ↔ `catalog.py` ↔ V2 方案/详细定义一致性；`/ingest`、`/ingest-and-parse`、`/parse`、`/parse-result/*` 与 `GET /{doc_id}` 均已对齐（`/openapi/v1` 为方案表述，以 `/api/v1` 实现为准）。
- 完成：补齐文档缺口——`GET /api/v1/knowledge-documents/{doc_id}`「查询文档信息」在代码/catalog 已存在但 V2 方案未收录；已在整体方案 §3.2 增补第 7 项，并在详细定义新增 B-07（标注预占位，字段契约待实现时对齐，不擅自定外部 API 形状）。

### 任务：API 文档免鉴权核查与修正

- 完成：实测 `/docs`、`/redoc`、`/openapi.json`、`/docs/oauth2-redirect`、`/api-browser` 等无 token 均可访问，主逻辑已符合「API 文档不需要 auth」。
- 修正：`app_factory.py` 调整中间件注册顺序（AuthN 内层、Trace 外层），未认证响应复用并回写调用方传入的 `X-Request-Id`/`X-Trace-Id`（契约 §3.5），未授权请求也具备完整 request start/end 链路日志。
- 修正：`middlewares.py` 免鉴权判定容忍尾斜杠（`/api-browser/`、`/health/` 等不再 401）。
- 完成：新增 3 例测试（docs 免鉴权、尾斜杠豁免、401 复用 trace 头）；全量测试 **58 passed**。

### 任务：启动服务实测验证

- 完成：沙箱外启动 `uvicorn app.main:app --host 0.0.0.0 --port 18000`（项目 `.venv`）。
- 实测：`/docs`、`/redoc`、`/openapi.json`、`/docs/oauth2-redirect`、`/api-browser`、`/api/catalog`、`/api/error-codes`、`/health` 无 token 均 200；尾斜杠变体（`/api-browser/`、`/health/`、`/docs/`）307 而非 401。
- 实测：业务路由无 token 返回 `100401`；带 Bearer 创建知识库返回 `000000`（真实 kbId），响应体与 `X-Request-Id`/`X-Trace-Id` 均回写传入 traceId `99988877766655544433321`。
- 环境备注：沙箱禁用 socket 创建且网络命名空间隔离，服务启动与 curl 验证均需在沙箱外执行。

### 任务：知识库读接口开放（列表查询 + 详情查询）

- 完成：新增 `POST /api/v1/knowledge-bases/query`（分页 + kbType/teamId/orgId/keyword 过滤）与 `GET /api/v1/knowledge-bases/{kb_id}`（详情）。
- 完成：数据范围收敛——个人库仅本人、团队库需显式 `teamId`、企业库按 `orgId` 或调用主体租户；详情个人库非创建者 `100403`、不存在 `100404`。
- 完成：两个读路由接入 `authorize_or_raise(action="read", resource_type="knowledge_base")` 与数据上下文。
- 完成：同步 `catalog.py`（知识库域 4 个路由）、V2 整体方案 §3.1（新增第 3/4 项）、详细定义 A-03/A-04、README。
- 完成：新增 12 例测试（列表空/范围/团队/企业/关键字/分页/详情/403/404/AUTHZ）；全量测试 **70 passed**。

### 任务：HTTP 状态码与 OpenAPI 文档一致性核查与修正

- 核查：运行时业务/校验错误统一 HTTP 200 + errCode（校验为 100001），符合契约统一响应体。
- 修正：`/docs` 声明 422 但实际从不返回（校验已被映射为 200/100001）——新增 `_apply_openapi_docs` 移除 422 并在 200 响应描述说明统一错误码。
- 修正：未知路由 404、方法不允许 405 原为裸 `{"detail": ...}` 且无 traceId——新增 `build_framework_error_response_middleware` 映射统一体（保留 HTTP 状态码）；新增错误码 `100405 请求方法不允许`（进 registry，/api/error-codes 自动可见）。
- 完成：新增 3 例测试（404/405 统一体、OpenAPI 无 422）；全量测试 **73 passed**。

### 问题 / 已知不一致

- **环境问题**：沙箱内 asyncio 跨线程唤醒失效（`call_soon_threadsafe` 无法唤醒其他线程的事件循环），导致 `TestClient` 死锁，pytest 在沙箱内无法运行；需在沙箱外（escalated）执行测试。本地 `.venv` 已装 `httpx2` 但缺 pytest，测试仍用 `/home/ikc-log-center/.venv/bin/python -m pytest tests` 运行（starlette TestClient 的 httpx 废弃告警为环境告警，未处理）。
- team 库成员关系校验依赖外部团队系统，当前占位未实现（依赖 AUTHZ 或后续接入）。

### 下一步

- 待定：文档域真实实现（如 ingest / 文档查询落地），按契约先读 V2 精简方案确认语义。
- 待定：知识库内存存储替换为真实持久化（DB）时的迁移点已收敛在 `app/services/knowledge_base_store.py`。

### 任务：环境修复——Claude Code 经 LiteLLM 调 deepseek-v4-flash 工具调用 400

- 现象：Claude Code 工具调用报 `400 "No tool output found for tool call call_00_..."`；后续又报 `reasoning_text in the thinking mode must be passed back to the API`。
- 根因一（No tool output）：LiteLLM 的 Anthropic→Responses 适配器把 assistant `tool_use` 转成 `function_call` 时排在 assistant 文本消息之前，导致其后的 `function_call_output` 无法与 `function_call` 相邻，DeepSeek 校验失败。
- 根因二（reasoning_text）：`deepseek-v4-flash` 无论是否传 thinking 参数都始终以 thinking 模式生成（实测响应恒含 `reasoning` item）；Claude Code 未开 thinking 时 assistant 无 thinking 块可回传，新会话（新 call_id）工具轮次必 400。
- 修复（`/home/litellm/.venv/.../responses_adapters/transformation.py`，均先备份 `transformation.py.bak.*`）：
  1. assistant 文本消息先于 `function_call` 输出，保证 `function_call → function_call_output` 相邻。
  2. `thinking` 块转成 Responses `reasoning` item（`content` 数组格式，DeepSeek 仅接受 plain-text content，不支持 summary）。
  3. deepseek 模型（model 名含 `deepseek`）的工具调用轮次若无 thinking 块，自动补占位非空 `reasoning`（内容 `...`），避免影响 grok/minimax 等其他 openai 前缀模型。
- 验证：经 proxy 全量形态 A/B/C/D + 全新 call_id（A 无 thinking、D 带 thinking）+ 两轮对话端到端，**全部 200**；`api.deepseek.com` 实际解析到本地网关 `198.18.0.19`，对 call_id 有状态记忆（旧 call_id 偶发豁免校验，新 call_id 必校验）。
- 决策：采用「无 thinking 工具轮次补占位 reasoning」而非「强制开启 thinking 让 Claude Code 回传」，因 LiteLLM 转回的 thinking block 无 signature，Claude Code 无法可靠回传。
- 下一步：如需真实思考链，可在 Claude Code 侧开启 thinking 模式（assistant 会带 thinking 块，适配器已支持转 reasoning 回传）。

### 任务：文档域真实实现落地（ingest / ingest-and-parse / 查询文档信息）

- 完成：新增 `app/services/document_store.py`（进程内文档存储：`DocumentRecord`、`DocumentStore` 原子读写、`doc_`/`ing_`+17 位数字 ID、幂等冲突判定、`DOCUMENT_STATUS` 常量）。
- 完成：新增 `app/schemas/document.py`（`DocumentSource` 四态 + 条件校验、`DocumentIngestRequest`/`DocumentIngestAndParseRequest`、统一响应体 envelope 响应模型）；`app/core/error_codes.py` 新增 `DocumentErrorCodes.INGEST_FAILED=200010` 并接入 `error_code_catalog()`。
- 完成：`app/services/document.py` 三占位替换为真实实现——ingest 校验知识库存在/类型归属（personal 仅创建者、team 匹配 teamId、enterprise 匹配 orgId/租户）、来源校验、幂等登记、docTitle 自动推断、`orchestrationMode=quick` 登记 PARSING；ingest-and-parse 内部两阶段返回双任务 ID；查询文档信息 404/403 + 数据范围收敛。
- 完成：`app/routers/document.py` 三路由接入 `authorize_or_raise`（create/read + `kb_id/kb_type/owner_id/org_path` 上下文，AUTHZ 先于 service 副作用）。
- 修正：schemas 响应模型原为扁平结构（违反统一响应体 §3.3），主线程改包 `data` envelope；补 `DocumentIngestAndParseResponse`；去除冗余 `DOC_NOT_FOUND` 别名。
- 完成：新增 `tests/test_document.py`（16 例，覆盖成功/幂等/404/403/参数校验/一体化/查询/AUTHZ）；全量测试 **89 passed**（原 73+16）。
- 实测：沙箱内启动 uvicorn，ingest/ingest-and-parse/查询文档 三接口均 `000000` 且 traceId 回写；不存在文档 `100404`。
- 同步：README §当前实现进度 增补文档域落地（第 5 条），解析/检索仍为占位（第 6 条）。
- 决策：响应构造在 service 内联 `error_response(SUCCESS, data)`（注释标注待 responses.py 收敛）；按最小改动优先，暂不迁移。
- 下一步：解析域（parse/parse-result）真实实现按同一范式推进；文档/知识库存储替换真实持久化的迁移点仍收敛在各自 store。

### 任务：暂停点快照（关机恢复用）

> 本条目为**会话中断前的恢复指引**，恢复任务时先读本条。

- **任务状态**：文档域真实实现**已完成并验证**（任务清单 #1–#4 全部 completed；`goals/goals.md` 标记已完成）。
- **未提交改动**（全在工作目录内，未 commit/push）：
  - 修改：`README.md`、`app/core/error_codes.py`、`app/routers/document.py`、`app/services/document.py`、`docs/worklog.md`
  - 新增：`app/schemas/document.py`、`app/services/document_store.py`、`goals/goals.md`、`tests/test_document.py`
- **验证基线**：全量测试 `89 passed`（`/home/ikc-log-center/.venv/bin/python -m pytest tests -q`）；三路由端到端实测 `000000`；`/api/error-codes` 含 `200010`。
- **恢复后的待办**：
  1. 运行 `pytest tests -q` 确认 89 passed 基线仍在。
  2. 若用户要求提交：按 §8.1 提交当天改动（仅 git add 上列文件，不含 `.venv`/`logs`），commit 信息如 `feat: 文档域 ingest/ingest-and-parse/查询文档信息 真实落地并接入 AUTHZ`。
  3. 可选项：解析域（parse/parse-result）真实实现，按本任务同一范式（schemas→store→service→router→AUTHZ→测试）推进。
  4. 可选项：service 内联响应构造收敛到 `app/core/responses.py`（`document_ingest_response` / `document_info_response`）。

## 2026-08-05

### 任务：独立设计并定义开放平台 SDK（open-ikc-sdk）

- 完成：新增设计文档 `docs/开放平台SDK集成设计.md`（286 行，待评审）。
- 决策：SDK 与平台逻辑层（Claude Code 进行中）完全解耦——写范围仅 `sdk/` + 本文档，不触碰 `app/`/`tests/`/`pyproject.toml`；依赖仅 `httpx`，不引入 fastapi/pydantic；包名 `open-ikc-sdk`。
- 决策：方法名蛇形、请求参数与响应字段沿用平台 camelCase；模型 dataclass + 未知字段 `extra` 透传；错误码全表映射异常层级（`OpenIKCAPIError` 子类 + 传输层异常区分）。
- 决策：同步 `OpenIKCClient` / 异步 `AsyncOpenIKCClient`；traceId 23 位数字生成与复用；身份头按非空透传（AUTHZ 上下文）；POST 仅显式传 `reqId` 时允许重试。
- 下一步：设计评审通过后按里程碑 M1（骨架）→ M2 知识库 → M3 文档 → M4 解析/检索 → M5 异步与下载流推进；与逻辑层无文件交集。

### 任务：SDK M1 骨架落地（设计评审前置推进）

- 完成：新建 `sdk/python/` 独立包 `open-ikc-sdk`（仅依赖 httpx，未触碰 `app/`，与逻辑层零文件交集）。
- 完成：核心模块——`errors.py`（异常层级 + 错误码映射表，含 100405）、`trace.py`（23 位数字 traceId 生成/复用）、`envelope.py`（统一响应壳解析）、`headers.py`（Bearer + trace 头 + AUTHZ 身份头按非空透传）、`transport.py`（超时/指数退避重试、POST 仅显式 reqId 才重试、HTTP 状态与统一壳双路径异常映射）、`client.py`（`OpenIKCClient`：`request`/`raw`/`fetch_catalog`/`fetch_error_codes`，repr 脱敏 token）。
- 完成：SDK 单元测试 5 文件 47 例（trace/envelope/errors/headers/retry/client），使用 `httpx.MockTransport` 无需起服务；验证 **47 passed**。
- 决策：`OpenIKCProtocolError` 归类传输层；未知错误码统一 `OpenIKCBusinessError`；`raw()` 不抛业务异常作逃生口。
- 下一步：M2 知识库域封装（`KnowledgeBaseClient` + 模型 + 测试），可与平台真实实现联调。

### 任务：SDK M2 知识库域封装（KnowledgeBaseClient + 模型 + 测试）

- 完成：新增 `models/knowledge_base.py`（`KnowledgeMetadataField` / `KnowledgeBase` / `KnowledgeBasePage`，camelCase 字段、`from_dict`/`to_dict`、未知字段 `extra` 透传）。
- 完成：`client.py` 新增 `KnowledgeBaseClient` 并挂载为 `client.knowledge_bases`：`create`（含 metadataSchema dict/模型双形态）、`update`（拉取现有记录 + 合并的局部更新，避免平台缺省重置 kbType/visibility，未知字段抛 TypeError）、`query`（仅放非空过滤条件）、`get`（路径参数替换）。
- 完成：新增 `tests/test_knowledge_base.py` 12 例；SDK 全量 **59 passed**。
- 决策：update 采用先 GET 后 POST 的合并语义并写入设计文档 §6.1 说明；修复一次 `__repr__` 插入错位（重写 `client.py` 保证结构正确）。
- 下一步：M3 文档域封装（`DocumentClient` + `DocumentSource`/`DocumentIngestResult` 等模型），平台文档域已落地可直接联调。

### 任务：SDK M3 文档域封装（DocumentClient + 模型 + 测试）

- 完成：新增 `models/document.py`（`DocumentSource` / `DocumentIngestResult` / `DocumentIngestAndParseResult` / `DocumentInfo`，未知字段 `extra` 透传）。
- 完成：`client.py` 新增 `DocumentClient` 并挂载为 `client.documents`：`ingest`、`ingest_and_parse`（parseStrategy/resultFormat/executeMode 按非空透传）、`get`（路径参数替换）。
- 决策：ingest 类请求 `reqId` 仅在显式传入时放入请求体，与传输层「POST 带 reqId 才允许重试」对齐；`source` 同时接受 dict 与 `DocumentSource` 实例。
- 完成：新增 `tests/test_document.py` 10 例；SDK 全量 **68 passed**（修正 2 处断言：to_dict 全字段输出、mock executeMode 与请求一致）。
- 下一步：M4 解析/检索域封装（`ParseClient` 四方法含下载、`SearchClient.query`），平台占位期以 mock 验证。

### 任务：SDK M4 解析/检索域封装（ParseClient + SearchClient + 下载双形态）

- 完成：`transport.py` 重构——抽取 `_send()` 统一重试/超时/传输异常映射；新增 `download()` + `DownloadPayload` 兼容 JSON 统一壳与原始文件流。
- 完成：新增 `models/parse.py`（`ParseTask`/`ParseResult`/`DownloadTicket`/`DownloadResult`）与 `models/search.py`（`SearchResultItem`/`SearchResult`，按 V2 D-01 目标态）。
- 完成：`client.py` 新增 `ParseClient`（`parse`/`query_result`/`issue_download_ticket`/`download`，`download` 返回 `DownloadResult | bytes`，`to_path` 落盘）与 `SearchClient.query`（对齐平台当前 schema 五字段）。
- 决策：检索请求参数以平台代码 schema 为准（`query`/`kbId`/`kbIds`/`ownerId`/`orgPath`），`filters`/`topK` 等目标态参数待平台落地后补充，已同步设计文档 §6.4。
- 完成：新增 `tests/test_parse.py` 8 例、`tests/test_search.py` 3 例；SDK 全量 **79 passed**。
- 下一步：M5 异步客户端 `AsyncOpenIKCClient`（httpx.AsyncClient + 同一套模型/错误映射）与 README 完善。

### 任务：SDK M5 异步客户端（AsyncOpenIKCClient）

- 完成：`transport.py` 抽取共享辅助函数（`resolve_timeout`/`build_url`/`can_retry`/`backoff_delay`/`handle_response`/`_download_payload`），同步 Transport 行为不变。
- 完成：新增 `transport_async.py`（`AsyncTransport`：async request/get_json/download/_send，退避用 `asyncio.sleep(backoff_delay())` 不阻塞事件循环）。
- 完成：新增 `async_client.py`（`AsyncOpenIKCClient` + `AsyncKnowledgeBaseClient`/`AsyncDocumentClient`/`AsyncParseClient`/`AsyncSearchClient`，复用 client.py 的 body 组装辅助函数与全部模型）。
- 完成：`__init__.py` 导出 `AsyncOpenIKCClient`；新增 `tests/test_async.py` 12 例（`asyncio.run` + `httpx.MockTransport`，覆盖 request/错误映射/四域方法/下载落盘/上下文管理/repr 脱敏/连接错误重试）；SDK 全量 **91 passed**。
- 下一步：可选——真实平台联调冒烟（`examples/quickstart.py`）、README 完善已完成；SDK 五里程碑（M1-M5）全部落地，待设计评审与联调。

### 任务：SDK 联调冒烟脚本补充

- 完成：新增 `sdk/python/examples/quickstart.py`（同步全链路冒烟：创建知识库 → 接入文档 → sync 解析 → 查询解析结果 → 签发凭证 → 下载 → 检索 → `/api/catalog` 自检；检索占位 `501001` 打印提示不报错；身份头 `CallerIdentity` 保持一致满足个人库范围收敛）。
- 完成：新增 `sdk/python/examples/async_quickstart.py`（异步客户端 create/query 示例）。
- 完成：README 新增「联调冒烟」章节；两脚本 `py_compile` 通过。
- 备注：冒烟需平台服务运行（沙箱网络隔离，需在沙箱外执行）并配置 `OPEN_PLATFORM_TOKEN`；SDK 全量测试基线 **91 passed** 不受影响。

### 任务：开放平台 API 接口定义全面一致性核查（只读审计）

- 完成：以知识库域为规范基准，并行派发文档/解析/检索三域只读审计子代理（各域路由↔catalog↔schema↔service↔错误码↔AUTHZ↔V2文档↔测试 交叉核对）。
- 结论：四域主干协议/路由↔catalog/统一响应壳/异常链路均达标；共 20 项发现（高 2、中 11、低 7）。
- 关键：高 1 文档域 quick 分支 `taskStatus` 硬编码 INGESTED 与 PARSING 状态不符（`services/document.py:191`）；高 2 V2 B-07 仍标注占位但接口已真实实现；中 11 含 KB A-02 文档「保持不变」与实际重置语义不符、解析 data 裸 dict、kbId 未校验、检索缺 response_model/测试、错误码编号跨域交错等。
- 决策：逻辑层相关修复交由并行开发收尾时处理（避免文件冲突）；文档同步项（B-07/A-02/B-03~05/B-06/错误码表）可独立先行；SDK 侧无需改动。
- 输出：`docs/API接口定义一致性核查报告_2026-08-05.md`（73 行，含修复建议与归属）。

### 任务：一致性核查后续动作（文档同步修正 + 逻辑层待办交接）

- 完成：修正 `docs/开放平台接口详细定义_精简版_V2.md`（20 处，+27 行）——错误码表补 200003/200004/200010/200011 并泛化公共码适用范围；A-02 修正 update 缺省重置语义（kbType/visibility/teamId/orgId 全量字段）+ 出参样例 createTime；B-03/B-04/B-05 以代码为准（仅 docId/docId+ticket 查询参数，下载出参改统一体+目标态文件流说明，补错误码 200003/200004）；B-06 补 docTitle/tags/metadata/orchestrationMode 入参与 taskStatus 出参；B-07 由「预占位」重写为真实实现（完整出参表+错误 100404/100403）；附录占位说明收敛为「仅检索/索引占位」。
- 完成：新增 `docs/逻辑层一致性修复待办_2026-08-05.md`（17 项交接清单：P0 行为正确性 3 项、P1 契约对齐 6 项、P2 测试/文档 8 项，含位置/动作/验收）。
- 备注：文档同步项不触碰 `app/`，与并行逻辑层开发零冲突；逻辑层修复项待其收尾时按待办清单闭环。

### 任务：逻辑层一致性修复闭环（P0 全部 + P1 部分，测试全绿）

- 完成：`app/services/parse.py` 增加 kbId 归属校验——`kbId` 与文档所属知识库不一致返回 `100001 INVALID_PARAMS`（P0-2）。
- 完成：`app/services/document.py` quick 分支 `taskStatus` 改为返回 `record.status`（与解析状态一致，P0-1）；`ingest_and_parse` 重构——先新建/复用文档，再委托 `ParseService.parse`，async 返回真实 queued 任务、sync 返回真实内联结果（P0-3）。
- 完成：`app/schemas/parse.py` 新增 `DocumentParseData`（taskId/taskStatus/executeMode/resultInline），`DocumentParseResponse.data` 由裸 dict 改为强类型（P1-4）；`app/schemas/search.py` 新增 `SearchResultItemData/SearchQueryData/SearchQueryResponse`，`app/routers/search.py` 补 summary/description/response_model 三件套（P1-5 响应模型部分）。
- 决策：P1-6 AUTHZ 角色映射补 parse 权限曾试做，但与既有「km_reader 仅 search:query 被拒」测试冲突，已回退保持现状，待逻辑层确认权限语义后再议。
- 测试：`tests/test_parse.py` 全部 `_parse_payload` 调用点补真实 kbId（含 1 处漏改 `test_download_with_ticket_for_other_document`）、新增 kbId 不匹配 100001 用例；`tests/test_document.py` 更新 async 断言 `taskStatus=="queued"` 并新增 3 用例；新建 `tests/test_search.py`（鉴权 501001 / 未认证 100401）。
- 验证：平台 `pytest tests -q` **110 passed**；SDK `pytest sdk/python/tests -q` **91 passed**，无回归。
- 下一步：剩余 P1/P2 待办（P2-13 directory/archive 伪展开标注、P2-14 responses.py 收敛、P1-8 下载 000000 豁免决策、P1-6 AUTHZ parse 权限语义）可自行决定继续或交还逻辑层。
