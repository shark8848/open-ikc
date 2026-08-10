# 管理 Portal 设计

> 版本：1.0.0 · 2026-08-10
> 范围：`/admin/*` 管理面后端 + `portal/` 前端（token 管理、端点监控、MCP/CLI 在线测试）。
> 契约：`AGENTS.md`（管理面 ≠ 第五类业务能力，不进入 catalog，独立管理鉴权）。

## 1. 定位与边界

- **管理面 ≠ 业务四类能力**：`/admin/*` 与 `/portal` 是运维管理面，使用独立管理鉴权（`OPEN_PLATFORM_ADMIN_TOKEN`），**不进入** `catalog.py` 的四类业务目录，不暴露内部流水线业务接口。
- **业务四类能力（知识库/文档/解析/检索）完全不动**；平台测试必须保持全绿。
- 统一响应体协议（errCode/errMsg/data/traceId）在 admin 接口同样遵守（成功 `000000`）。

## 2. 目录结构

```
app/core/admin/                    # 管理面核心（独立于业务）
  token_store.py                  # SQLite token 管理（创建/撤销/列表/校验）
  stats.py                        # SQLite 统计存储（请求/并发/错误/token 维度）
  monitor.py                      # 统计采集中间件（挂在 app_factory）
  mcp_cli_test.py                 # MCP/CLI 在线测试执行器（subprocess + 白名单）
  auth.py                         # admin_required 独立鉴权依赖
app/routers/admin.py              # /admin/* 管理路由
portal/                           # 前端（Vite 8 + React 18 + TS），构建产物 portal/dist
  src/api/client.ts               # /admin/* API 封装 + admin token 管理
  src/pages/                      # Dashboard / Tokens / Endpoints / TestLab
```

## 3. 后端

### 3.1 Token 管理（token_store.py）

- SQLite 路径：`OPEN_PLATFORM_DB_PATH`（默认 `data/open_ikc_platform.db`，gitignore 的 `data/`）。
- 表 `api_tokens`：`id, token_hash(sha256), name, owner, scopes, status(active/revoked), created_at, expires_at, last_used_at`。
- 明文 token 仅在创建时返回一次；库中只存 sha256 哈希。
- `active_token_set()` 与业务 `security.configured_tokens()`（env token）合并校验。
- **撤销语义**：`has_any_token_record()` 区分「从未配置」（业务鉴权退化为仅要求 Bearer 存在）与「配置过但全部撤销/过期」（拒绝）。撤销后业务请求返回 `100401`。

### 3.2 监控统计（stats.py + monitor.py）

- 表：`request_stats`（明细，可滚动清理）、`endpoint_agg`（path/method 窗口聚合）、`token_agg`（token 维度窗口聚合）。
- 聚合窗口 60s，明细保留 1h；`ConcurrencyCounter` 进程内并发计数。
- 采集中间件 `build_monitor_middleware` 位于 AuthN 内层，可读 `request.state.identity` 记录 token/身份维度。

### 3.3 Admin 路由与独立鉴权

- 前缀 `/admin`，所有接口需 `Authorization: Bearer <admin-token>`（`OPEN_PLATFORM_ADMIN_TOKEN`）。
- 未配置 admin token 时返回 `503001`（默认关闭，避免暴露）。
- `/admin` 在业务 AUTHN 中间件 `AUTH_EXEMPT_PREFIXES` 中豁免，由 `admin_required` 依赖自行校验。
- 接口：
  - `GET /admin/overview`：在线并发、总请求、错误率、活跃端点、活跃 token 数
  - `GET /admin/endpoints`：端点维度统计（`window_minutes`）
  - `GET /admin/requests`：最近请求明细（`limit`）
  - `GET /admin/stats/token`：token 维度调用统计
  - `GET /admin/tokens`：token 列表（`include_revoked`）
  - `POST /admin/tokens`：创建 token（返回明文一次）
  - `POST /admin/tokens/{id}/revoke`：撤销
  - `POST /admin/test/mcp`：MCP 冒烟（subprocess 真实执行）
  - `POST /admin/test/cli`：CLI 白名单命令执行
  - `GET /admin/test/whitelist`：CLI 命令 / MCP 工具白名单

### 3.4 MCP/CLI 在线测试（mcp_cli_test.py）

- subprocess 真实执行 `.venv/bin/python -m open_ikc_sdk.mcp` / `.venv/bin/python -m open_ikc_sdk.cli`。
- **命令白名单**：CLI 仅 `kb-list`/`kb-get`/`sys-catalog`/`sys-error-codes`/`search-query`（只读）；MCP 仅 `sys_catalog`/`sys_error_codes`/`kb_get`/`kb_query`。禁止任意 shell。
- 超时 20s；token 从请求上下文注入子进程环境变量，不落库。
- **⚠️ 事件循环死锁**：`/admin/test/mcp`、`/admin/test/cli` 为 async 路由，其中同步 `subprocess.run` 会阻塞事件循环；子进程请求平台自身端点（如 `GET /api/catalog`）时平台无法响应 → 互相等待直至超时。**必须用 `run_in_threadpool`（`starlette.concurrency`）在线程池执行。**

## 4. 前端（portal/）

- 技术栈：Vite 8.2.1 + React 18.3.1 + TypeScript 5.6，手写 CSS 深色主题（对齐 api_browser 风格）。
- `vite.config.ts`：`base: '/portal/'`，`build.outDir: dist`；dev 模式 proxy `/admin → http://127.0.0.1:18000`。
- **admin token 管理**：`sessionStorage`（`open-ikc-admin-token`），请求统一带 `Authorization: Bearer`；登录页校验（未配置 admin token 时提示 503 语义）。
- 页面：
  - **Dashboard**：总览卡片（在线并发/总请求/错误数/错误率/活跃端点/活跃 token）+ 最近请求明细表，10s 自动刷新。
  - **Tokens**：创建表单（名称/所有者/作用域/有效期）、明文 token 一次性展示、撤销确认、含已撤销筛选。
  - **Endpoints**：端点维度 + token 维度统计表，30/60/120 分钟窗口切换。
  - **TestLab**：MCP 冒烟（工具选择 + 结构化步骤结果）、CLI 命令执行器（白名单命令选择 + 参数输入 + 输出展示）。

## 5. 静态挂载与豁免

- `app_factory.py`：`_mount_portal()` 在 `portal/dist` 存在时 `app.mount("/portal", StaticFiles(html=True))`。
- `middlewares.py`：`AUTH_EXEMPT_PREFIXES` 含 `/admin` 与 `/portal`（静态壳无数据，数据全走受保护的 `/admin/*`）。
- `api_browser.py`：根链接区增加「管理 Portal」入口。

## 6. 测试

| 文件 | 覆盖 |
| --- | --- |
| `tests/test_admin_token.py` | token 创建/撤销/列表/哈希/合并校验 |
| `tests/test_admin_stats.py` | 请求统计/并发/聚合/错误/token 维度 |
| `tests/test_admin_api.py` | admin 鉴权 + 各接口（含创建→撤销→100401 全链路） |
| `tests/test_admin_testlab.py` | MCP/CLI 白名单校验/超时/参数校验 |
| `tests/conftest.py` | autouse fixture 隔离 `OPEN_PLATFORM_DB_PATH`（临时 DB，防状态串扰） |
| `tests/test_auth_middleware.py` | `/portal` 免业务鉴权断言 |

## 7. 安全与边界

- Token 明文只在创建时返回一次，DB 存 sha256 哈希。
- admin 接口独立鉴权（`OPEN_PLATFORM_ADMIN_TOKEN`），未配置默认关闭（返回 `503` 明确提示）。
- MCP/CLI 测试命令白名单 + 超时，禁止任意 shell 执行。
- 监控统计不记录 Authorization 明文；client_ip 可配脱敏。
- SQLite 路径 gitignore（`data/`）。
- Portal admin token 前端存 sessionStorage（会话级），生产建议 https + 网关保护。
