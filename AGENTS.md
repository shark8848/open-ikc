# AGENTS.md — open-ikc 项目实现契约

> 本文件是所有自动化协作者（Codex / Claude Code 等）在本仓库内工作的**强制约定**。
> Claude Code 通过 `CLAUDE.md` 的 `@AGENTS.md` 导入读取同一份契约；**契约只编辑本文件**。
> 权威顺序：本文件 + 当前代码实现 > `docs/` 设计文档；设计文档只解释意图，不直接覆盖实现。

## 1. 项目定位

| 项 | 约定 |
| --- | --- |
| 仓库 / 包名 | `open-ikc` / `open-ikc-api` |
| 形态 | FastAPI **北向开放平台 API**，当前为预占位脚手架 |
| Python | `>=3.12` |
| 默认端口 | `18000` |

**对外只开放四类业务能力，禁止擅自扩展第五类或暴露内部流水线 API：**

1. **知识库** — 创建 / 修改库信息
2. **文档** — 接入知识源、文档查询
3. **解析** — 解析任务与结果获取
4. **检索** — 统一检索问答

索引能力（reindex / task query）若落地，须先对齐 `docs/开放平台接口整体方案_V2_精简.md`，并同步 `app/core/catalog.py` 与路由，不得 silently 加私有路径。

## 2. 目录与职责边界

```
app/
  main.py                 # 仅 create_app()，禁止堆业务
  core/
    app_factory.py        # FastAPI 装配：路由、中间件、异常、SDK
    middlewares.py        # Trace + AuthN 中间件
    security.py           # Token / OAuth2 / OIDC 等认证实现
    trace.py              # traceId 生成、绑定、下游透传头
    error_codes.py        # ErrorCode / AppException / 领域异常与错误码表
    exception_handlers.py # 全局异常 → 统一响应
    responses.py          # 成功/占位响应构造（含 traceId）
    catalog.py            # 对外业务 API 目录（与路由保持一致；不含 admin 管理面）
    system_routes.py      # /、/health、/api-browser、/api/catalog、/api/error-codes
    api_browser.py        # API 浏览页
    logging.py            # 日志封装
    static/docs/          # 本地 swagger-ui / redoc 静态资源（/docs、/redoc 离线可用）
    admin/                # 管理面（运维管理，独立鉴权，非业务五类，见 §3.2.1/§4.3）
      auth.py             # admin_required 依赖 + OPEN_PLATFORM_ADMIN_TOKEN 校验
      monitor.py          # 请求统计采集中间件（在线并发/明细）
      stats.py            # SQLite 请求统计（明细/端点聚合/token 聚合）
      token_store.py      # SQLite token 存储（明文一次性返回，库中存 sha256）
      mcp_cli_test.py     # MCP/CLI 在线测试（白名单命令/工具执行）
    authz/                # 独立 AUTHZ 集成层（勿与 middleware 交叉耦合）
      schema.py           # 统一权限语义（身份、权限事实、授权请求、决策）
      adapters.py         # 外部权限 schema → 统一语义的适配器
      policy.py           # 统一策略引擎（deny-overrides）
      service.py          # 适配器注册与 authorize 门面
      bridge.py           # 业务桥接层（从 request/header 组装授权输入）
      runtime.py          # 开关（authz_enabled）与 authorize_or_raise
  routers/                # 薄路由：校验入参、鉴权桥接、调 service
    admin.py              # 管理面路由（prefix=/admin，独立鉴权，见 §3.2.1）
    knowledge_base.py     # 知识库四接口
    document.py           # 文档三接口
    parse.py              # 解析四接口
    search.py             # 检索一接口
  schemas/                # Pydantic 请求/响应模型
  services/               # 业务编排 + 进程内存储
docs/                     # 方案与 AUTHN/AUTHZ 设计（中文）
portal/                   # 管理 Portal 前端（Vite 8 + React 18 + TS），构建产物 portal/dist 静态挂载于 /portal
data/                     # 运行时 SQLite 数据（默认 open_ikc_platform.db；gitignore，勿提交）
scripts/                  # 启动/停止脚本
tests/                    # pytest 测试
logs/                     # 运行日志（gitignore，勿提交）
```

**分层规则：**

| 层 | 可以做 | 不可以做 |
| --- | --- | --- |
| `routers/*` | 定义路径、依赖注入、调用 `authorize_or_raise`、调 service | 写复杂业务、直接拼错误码字符串、访问 DB/下游细节 |
| `services/*` | 业务规则、编排、抛 `*Exception` | 依赖 FastAPI `Request`（除非明确桥接）、绕过 error_codes |
| `schemas/*` | 入参/出参模型、Field 描述与示例 | 副作用、I/O |
| `core/*` | 横切能力、统一协议 | 具体业务领域逻辑 |
| `core/authz/*` | 授权语义与适配 | 改 trace/token 主中间件链路 |

## 3. API 与协议契约

### 3.1 路径前缀

- 实现与目录以代码为准：`/api/v1/...`；设计文档中的 `/openapi/v1/...` 仅作方案表述。
- 新增/修改接口时使用 `/api/v1`，并同步：对应 `app/routers/*`、`app/core/catalog.py`、必要时 `docs/开放平台接口详细定义_精简版_V2.md`。
- **改路由必改 catalog。**

### 3.2 当前对外路由清单

| 能力 | Method | Path |
| --- | --- | --- |
| 知识库 | POST | `/api/v1/knowledge-bases/create` |
| 知识库 | POST | `/api/v1/knowledge-bases/update` |
| 知识库 | POST | `/api/v1/knowledge-bases/query` |
| 知识库 | GET | `/api/v1/knowledge-bases/{kb_id}` |
| 文档 | POST | `/api/v1/knowledge-documents/ingest` |
| 文档 | POST | `/api/v1/knowledge-documents/ingest-and-parse` |
| 文档 | GET | `/api/v1/knowledge-documents/{doc_id}` |
| 解析 | POST | `/api/v1/knowledge-documents/parse` |
| 解析 | GET | `/api/v1/knowledge-documents/parse-result/query` |
| 解析 | GET | `/api/v1/knowledge-documents/parse-result/issue-download-ticket` |
| 解析 | GET | `/api/v1/knowledge-documents/parse-result/download` |
| 检索 | POST | `/api/v1/knowledge-search/universal-search` |
| 检索 | POST | `/api/v1/knowledge-search/deep-search` |
| 检索 | POST | `/api/v1/knowledge-search/query`（兼容别名，指向 universal-search） |

系统路由（免业务鉴权或文档用途）：`/`、`/health`、`/docs`、`/redoc`、`/docs/oauth2-redirect`、`/openapi.json`、`/_static/docs`（本地 swagger/redoc 静态资源）、`/api-browser`、`/api/catalog`、`/api/error-codes`、`/portal`（管理 Portal 静态壳，静态无数据）。

#### 3.2.1 管理面路由（`/admin/*`，非业务五类）

| 用途 | Method | Path |
| --- | --- | --- |
| 总览 | GET | `/admin/overview` |
| 端点统计 | GET | `/admin/endpoints` |
| 最近请求 | GET | `/admin/requests` |
| Token 维度统计 | GET | `/admin/stats/token` |
| 查询 token 列表 | GET | `/admin/tokens` |
| 创建 token | POST | `/admin/tokens` |
| 撤销 token | POST | `/admin/tokens/{token_id}/revoke` |
| MCP 在线冒烟 | POST | `/admin/test/mcp` |
| CLI 在线测试 | POST | `/admin/test/cli` |
| 白名单查询 | GET | `/admin/test/whitelist` |

- **管理面 ≠ 第五类业务能力**：`/admin/*` 是运维管理面（token 管理、监控、MCP/CLI 在线测试），**不进入 `app/core/catalog.py`、不占用 §1 四类业务能力，也不暴露内部流水线接口**。
- **独立鉴权**：走 `admin_required` 依赖（`OPEN_PLATFORM_ADMIN_TOKEN`），与业务 AUTHN 完全隔离；未配置该环境变量时管理面默认关闭，`/admin/*` 返回 `503001`。详见 §4.3。
- 新增 admin 路由时同步：`app/routers/admin.py`、必要时 README「管理 Portal」小节；**无需**同步 `catalog.py`（catalog 只登记对外业务目录）。

### 3.3 统一响应体

所有业务响应（成功与失败）遵循：

```json
{
  "errCode": "000000",
  "errMsg": "success",
  "data": {},
  "traceId": "23位数字"
}
```

- 成功：`000000`；参数错误：`100001`（含 FastAPI/Pydantic 校验，由全局处理器映射）；未认证：`100401`；无权限：`100403`；未实现占位：`501001`；系统错误：`999999`；管理面未启用：`503001`（admin 专属，见 §4.3）。

### 3.4 错误码与异常

1. 业务层优先抛 `AppException` 或其子类（`KnowledgeBaseException` / `DocumentException` / `ParseException` / `SearchException`），表达不同领域/层级的异常边界。
2. 推荐用 `error.as_exception(...)` 或 `exception_from_code(...)` 从错误码对象直接生成异常，避免业务层手写字符串。
3. 子类只负责表达层级和边界，错误码对象负责承载默认消息、层级和说明。
4. 应用层统一捕获异常并返回 `errCode`、`errMsg`、`data`。
5. 参数校验错误由全局校验异常处理器统一映射为 `100001`。
6. 文档、解析、检索三个领域分别继承 `DocumentException`、`ParseException`、`SearchException`，保持同一条异常链路。
7. 错误码通过 `BaseErrorCodes.get_by_code(...)` 或 `error_code_catalog()` 查表，便于日志、文档和调试统一定位。
8. 线上可通过 `/api/error-codes` 获取当前注册的错误码目录；新错误码必须进 `error_code_catalog()` registry（admin 的 `503001` 也须经 `AdminErrorCodes` 注册，见 §5.2）。

### 3.5 Trace

1. 每个请求注入 23 位纯数字 `traceId`，优先复用请求头 `X-Request-Id` / `X-Trace-Id` / `traceId` / `trace_id`。
2. 响应头回写 `X-Request-Id` 与 `X-Trace-Id`，响应体顶层带 `traceId`。
3. 日志上下文自动携带 `traceId`；调用下游时透传同一组追踪头，可复用 `build_trace_headers()`。

## 4. 认证与鉴权契约

### 4.1 认证（AUTHN）

- 每次请求必须携带 `Authorization: Bearer <token>`，缺失或格式错误统一返回 `100401` + `traceId`。
- 服务端 token：`OPEN_PLATFORM_TOKEN`（单个）/ `OPEN_PLATFORM_TOKENS`（多个，逗号分隔）；未配置时只强制 Bearer 存在、不做值比对。
- `OPEN_PLATFORM_AUTH_MODE` 切换认证模式：`static` / `gateway_header` / `oidc_jwt` / `oauth2_introspection`。
- **部署边界**：`static` 模式直接采信身份头，仅限内网/测试；生产必须 `gateway_header`（网关剥离伪造头）或 `oidc_jwt`/`oauth2_introspection`。
- 认证中间件把身份写入 `request.state.identity` 与 `request.state.permissions`，供 AUTHZ bridge 复用。
- 免鉴权路径集中在 `app/core/middlewares.py` 的 `AUTH_EXEMPT_PATHS` / `AUTH_EXEMPT_PREFIXES`，新增系统级路径需同步更新并补测试。

### 4.2 鉴权（AUTHZ，独立集成层）

- 开关：`OPEN_PLATFORM_AUTHZ_ENABLED=true` 才启用；策略 **deny-overrides**，无命中默认拒绝，拒绝统一 `100403` + `traceId`。
- 业务接入用 `authorize_or_raise(request, action, resource_type, ...)`，参考 `POST /api/v1/knowledge-search/query`；禁止把授权逻辑塞进 middleware。
- 系统选择：请求头 `X-Auth-System` 或 `OPEN_PLATFORM_AUTH_SYSTEM`（内置 `default`、`digital_employee`）。
- 常用身份头：`X-User-Id`、`X-Tenant-Id`、`X-User-Roles`、`X-User-Permissions`、`X-User-Deny-Permissions`。
- 数据权限上下文可注入：`kb_id` / `kb_ids`、`owner_id`、`org_path`、`team_id`、`org_id` 等；**`owner_id`/`org_path` 一律取认证身份（`request.state.identity`），请求体 `ownerId`/`orgPath` 不作为授权依据（仅保留为兼容字段）**；`teamId`/`orgId` 作为业务范围声明从请求体读取（与授权身份分离）。
- 新接入方优先「适配器 + 映射配置」（`MappingAuthzAdapter`），禁止在业务 service 里写第三方字段 if/else 丛林。

### 4.3 管理面独立鉴权（admin，非业务五类）

- 管理面路由（`/admin/*`，见 §3.2.1）使用独立管理 token：环境变量 `OPEN_PLATFORM_ADMIN_TOKEN`（单个）；请求需 `Authorization: Bearer <admin-token>`。
- **未配置 `OPEN_PLATFORM_ADMIN_TOKEN` 时管理面默认关闭**：`/admin/*` 返回 `503001`（`AdminDisabledError` 由全局异常处理器映射，HTTP 503 + 统一响应壳），避免默认暴露。
- **与业务 AUTHN/AUTHZ 完全隔离**：`/admin/*` 不进入业务 catalog、不占用四类业务能力；`/admin` 与 `/portal` 静态壳在 `AUTH_EXEMPT_PREFIXES` 豁免业务 AUTHN，但 admin 接口自身仍强制 `admin_required`（未配置或 token 错误时 `503001`/`100401`）。
- 管理面自身请求不纳入业务监控统计（`request.state.skip_stats`），token 明文仅在创建时返回一次，库中只存 sha256 哈希（`app/core/admin/token_store.py`）。

### 4.4 日志中心（ikc-log-center）基础契约

> 日志是全仓库的**基础可观测设施**（可替代 AUTHN 作为贯穿链路），接入方式为 pip 安装模式，依赖声明在 `pyproject.toml`：`ikc-log-center==1.4.9`（本地 wheel 安装，勿改为源码目录引用）。

1. **依赖只经 `pyproject.toml` 声明**；`log_center_sdk` 是唯一日志体系，勿随意替换。版本升级需同步 `README.md` 安装说明与启动脚本。
2. **初始化在应用装配**：`app/core/app_factory.py` 调用 `log_center_sdk.configure(module_name="open_ikc_api")`，并挂载 `TraceMiddleware`（请求入口绑定/复用 23 位 traceId，日志上下文自动携带，透传 `X-Trace-Id` / `X-Request-Id` 响应头）。
3. **远程投递由环境变量控制**（启动脚本已默认开启）：
   - `LOG_CENTER_ENABLE=true` 时异步发送至 `LOG_CENTER_URL`（默认 `http://127.0.0.1:9315`，SDK 自动 POST `{url}/ingest`）；服务端开启 Bearer 认证时额外配置 `LOG_CENTER_TOKEN`。
   - 本地默认也落盘 `logs/open_ikc_api.log`；`logs/` 不入库。
4. **不降级为 print / 裸 logging**：新代码如需打日志，走 `log_center_sdk.get_logger(__name__)`（logger 名带模块名 `open_ikc_api`，便于日志中心按链路检索）。
5. 日志禁止记录密钥与真实 token。

## 5. 代码风格与实现约定

1. 文件首行：`from __future__ import annotations`。
2. 路由保持薄：参数模型 →（可选）AUTHZ → Service。
3. Service 用 `@staticmethod` 或清晰无状态方法；未实现能力必须返回 `501001`，**禁止静默空成功**。
4. 依赖只在 `pyproject.toml` 声明；当前核心依赖 FastAPI、Uvicorn、PyJWT；日志走 `log_center_sdk`，勿随意替换日志体系。
5. 注释与用户可见文案用中文（与仓库一致），标识符保持英文。
6. 不要提交：`.venv/`、`logs/`、`__pycache__/`、`*:Zone.Identifier`、密钥与真实 token。
7. 修改行为时同步：README 相关段落、`app/core/catalog.py`、必要 docs。

## 6. 测试约定

- 测试位于 `tests/`，使用 pytest；每个测试文件自行创建 `TestClient(app)`。`tests/conftest.py` 除把仓库根目录加入 `sys.path` 外，另有 `isolate_admin_db` autouse fixture：把 `OPEN_PLATFORM_DB_PATH` 指向 `tmp_path` 临时 SQLite，隔离管理面 token/统计状态，避免跨测试串扰（admin 测试文件自行覆盖 `OPEN_PLATFORM_ADMIN_TOKEN`）。
- 测试运行命令（项目 `.venv` 已装 pytest/httpx，二者皆可）：
  ```bash
  cd /home/open-ikc && .venv/bin/python -m pytest tests -q
  ```
  若 `.venv` 环境异常，回退 `/home/ikc-log-center/.venv/bin/python -m pytest tests -q`。
- 测试启动应用会写 `logs/open_ikc_api.log`，需具备项目目录写权限。
- 管理面测试在 `tests/test_admin_*.py`（api/stats/testlab/token 四文件），覆盖 `admin_required` 鉴权、未配置 token 时 `503001`、token 创建/撤销、MCP/CLI 白名单。
- 新增/修改行为必须补测试：鉴权免检路径、`MappingAuthzAdapter` 身份映射兜底、deny-overrides、数据权限条件（资源 ID 范围 / owner-only / org 路径 / 部门 / 租户）、admin 管理面等；新增错误码进 registry 时补 `/api/error-codes` 断言。

## 7. Token 效率与协作约定

> 目标：在保证质量的前提下降低单次任务的 token 消耗。主线程只做编排与集成，信息收集与可并行子任务尽量下沉。

### 7.1 子代理优先

1. 任务含多个边界清晰、可并行的子任务时，优先派发子代理（Codex：`spawn_agent`；Claude Code：`.claude/agents/` 子代理），主线程只做编排与集成。
2. 子任务必须自包含：明确输入、输出与写范围（各子任务写范围不重叠）；交付物为「改动文件清单 + 精简结论」。
3. 信息收集类任务（读代码、查文档、搜索）优先交子代理；主线程不要反复整读大文件。
4. 子代理返回后，主线程只做精简 review 与集成，**禁止重做或重读其已完成的工作**。
5. 已完成的子代理及时关闭/释放，不长期占用。

### 7.2 上下文压缩

1. 长任务按阶段推进：每完成一个阶段，主动更新计划、总结中间结果并触发上下文压缩（Claude Code：`/compact`；Codex 自动压缩，无需手动）。
2. 不把大段文件/日志贴进消息：引用「路径 + 行号」，只贴必要片段（如关键 traceback 尾部）。
3. 跨天/跨会话任务开工前，先读 `docs/worklog.md` 最近条目继承上下文，避免重读仓库。

### 7.3 低消耗工作习惯

1. 定位用 `rg`；读文件用 `sed -n` / `head -n` 取关键片段，禁止整文件 `cat`。
2. 命令批量合并执行，并控制输出量（`tail -n`、`-q`、输出上限）。
3. 不重复读取刚改动过的文件；工具已确认结果时不复查。
4. diff 保持最小：只改必要代码，避免无关格式化大扫除。
5. 失败排查只复述关键信息，不整段贴日志。

### 7.4 汇报精简

1. 最终回答控制在必要篇幅：结果 → 改动文件 → 验证 → 下一步。
2. 不贴整文件内容，不输出大段引用；文件路径用行内代码引用即可。

## 8. 工作日志与每日继承

1. 统一日志文件 `docs/worklog.md`，按日期追加条目（`YYYY-MM-DD`），条目包含：任务、完成情况、进展、问题/阻塞、决策、下一步。
2. **每日开工先读日志**：优先读取最近条目，继承进度与待办再开始任务；禁止重复调研日志已记录过的内容。
3. **任务结束或每天结束时更新日志**：追加当天条目，保持简洁，记录关键决策、未解决问题与下一步；跨天任务在对应条目续写或互相引用。
4. 日志是跨天/跨会话的上下文交接载体：以日志为准继续任务，替代重新通读仓库；与契约冲突时以本契约（`AGENTS.md`）为准。
5. 提交时同步提交日志更新（在用户允许提交的前提下）；日志禁止记录密钥与真实 token。

### 8.1 每日 17:30 例行提交

1. 每个工作日 `17:30`（以本机时间为准）执行例行提交任务；若该时刻任务进行中，则在当前任务收尾阶段完成提交；若当时无任务，则下次会话开工时先补做。
2. 提交前准备：确认/补齐当天 `docs/worklog.md` 条目（完成情况、问题、下一步）；代码或行为有改动时先跑 `pytest tests -q` 确认通过。
3. 提交范围：只 `git add` 与当天任务相关的文件；`.venv/`、`logs/`、`__pycache__/`、密钥与真实 token 一律不提交。
4. commit 信息简洁说明当天改动（如 `feat: 完成 XX 并更新工作日志`），可引用 worklog 日期。
5. 当天无改动时：不创建空提交，在 worklog 中记录「当日无改动」。

### 8.2 每次任务完成自动推送（默认契约）

1. **任务收尾后自动 commit + push**（无需逐次询问）：任务完成且验收（测试全绿、worklog 已更新）后，`git add` 与任务相关的文件并 commit，commit 信息简洁说明改动（如 `feat: 完成 XX 并更新工作日志`），然后 **push 到远端**。
2. **推送目标**：默认 `github`（`git push github main`）；同仓库另有 `origin`（`code.tiancloud.com`），需要双远端同步时执行 `git push github main && git push origin main`；远端落后时先 `pull --rebase` 再推。
3. **必须遵守**：只在任务确实完成（测试通过、无未决问题）后推送；禁止半成品或失败状态入库；`.venv/`、`logs/`、`__pycache__/`、密钥与真实 token 一律不提交。
4. **例外**：用户明确说「不要推/暂缓」时跳过；存在工作区未完成改动与任务无关时，先只提交任务相关文件，避免混入无关改动。
5. 与 §11-7「仅在用户明确要求时 commit/push」不一致时，以本条约定的自动推送为准（本文件内 §11-7 相应更新）。

## 9. 功能落地工作流

1. 对照 V2 精简方案确认功能在四类能力内。
2. 按 `schemas` → `services` → `routers` 顺序实现。
3. 需要鉴权则 `authorize_or_raise` + 注入资源上下文。
4. 错误与成功均走 error_codes + trace。
5. 更新 `catalog.py` 与必要文档。
6. 本地启动（`bash scripts/start_open_platform.sh` 或 `python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload`），用 `/docs` 或 curl 带 Bearer 与 trace 头验证。
7. 保持 diff 可读，避免无关格式化大扫除。
8. 按 `docs/worklog.md` 约定，记录完成情况、问题与下一步。

## 10. 文档权威顺序

实现与评审时按以下优先级：

1. **本文件 `AGENTS.md`**（实现契约；`CLAUDE.md` 为其 Claude Code 导入入口）
2. **当前代码**（`app/`、路由、catalog、error_codes）
3. `docs/开放平台接口整体方案_V2_精简.md` + `docs/开放平台接口详细定义_精简版_V2.md`
4. `docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md`
5. `docs/开放平台统一认证鉴权集成_AUTHZ.md`
6. V1 / 规划类长文仅作背景参考，不直接当接口真理

Excel / 抽取 JSON 仅作历史接口盘点，**不得**未经评审直接扩成对外 API。

## 11. 硬性约束

1. **不扩大能力面**：不新增第五类对外业务域，不把内部流水线原子接口直接暴露。
2. **不破坏统一协议**：`errCode` / `errMsg` / `data` / `traceId` 结构不可拆。
3. **不合并 AUTHN 与 AUTHZ 中间件职责**：授权走 `authz` 包与业务桥接。
4. **不绕过异常体系**：不用裸 `HTTPException` 替代已有 `AppException` 链路（除非框架层必要且仍映射统一体）。
5. **改路由必改 catalog**；改错误码必进 registry。
6. **密钥与生产配置**：只用环境变量示例，不把真实凭证写入仓库。
7. **提交与推送**：默认**每次任务完成后自动 commit + push**（见 §8.2）；用户明确说「不要推」时跳过。commit 信息简洁说明动机。
8. **优先最小改动**：占位项目以可运行骨架 + 清晰边界为先，避免过度设计。
9. **权限不降级**：检索与读写必须可按调用方权限过滤；数据权限条件要可测试。
10. 不确定产品语义时：先读 V2 精简方案与现有 router/service，再改；缺少决策时询问用户，不擅自定外部 API 形状。

## 12. 快速索引

| 主题 | 位置 |
| --- | --- |
| 应用入口 | `app/main.py` |
| 装配 | `app/core/app_factory.py` |
| 错误码 / 异常 | `app/core/error_codes.py` |
| Trace | `app/core/trace.py` |
| 认证 | `app/core/security.py`、`app/core/middlewares.py` |
| 鉴权 | `app/core/authz/` |
| API 目录 | `app/core/catalog.py` |
| 人读说明 | `README.md` |
| 接口方案 | `docs/开放平台接口整体方案_V2_精简.md` |

## 13. 完成后自动审查（Claude Code 只读审查）

1. 任务收尾且 `pytest tests -q` 全绿、行为有改动时，Codex 自动运行 `scripts/review_with_claude.sh` 触发 Claude Code 只读审查（headless `claude -p`）。
2. 审查 prompt 强制「只读、禁止修改文件」；报告输出 `docs/code-review_<日期>.md`，与逻辑层写范围不重叠，避免与并行 Claude Code 开发冲突。
3. 审查结论写入 worklog；P0/P1 问题闭环后再提交；P2 项记入对应待办清单。
4. 开关：`OPEN_PLATFORM_AUTO_REVIEW=true`（默认开）；置 `false` 可跳过以节省 token/时间。
5. claude CLI 走 Anthropic API 需网络，Codex 沙箱内执行需沙箱外批准（`claude -p` 前缀规则可复用）。
