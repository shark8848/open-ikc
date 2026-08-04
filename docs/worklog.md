# 工作日志（Worklog）

> 用途：记录每次/每天的任务完成情况、进展、问题与总结；**每天开工前先读最近条目继承上下文**。
> 约定见 `AGENTS.md`「工作日志与每日继承」章节。按日期追加，每天一个条目。
> 每个工作日 `17:30` 触发例行提交任务（约定见 `AGENTS.md` §8.1）。

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
