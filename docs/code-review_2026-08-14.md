I have completed a thorough read-only review. All 181 tests pass. Here is the report.

---

# 代码审查报告 — 未提交工作区改动（2026-08-14）

**范围**：AUTHZ 一致性、统一响应体/异常链路、认证鉴权与越权风险、schema 校验与数据边界、测试覆盖。只读审查，未修改任何文件。

**基线验证**：`pytest tests/` → **181 passed**（含新增 `test_api_docs_use_local_static_assets_no_external_cdn`、`test_root_redirects_to_portal_when_built`、503001 注册断言、免鉴权路径 `/_static/docs` 断言）。

---

## 结论

改动整体质量较好：本地托管 swagger/redoc 静态资源、管理面错误码 `503001` 统一注册、Portal 主题/反馈组件、Token 表单改造均有测试支撑，测试 181 全绿。**未发现 P0 问题**。但存在 **1 个安全语义缺口（P1，scope 未真正生效）**、**1 个管理面默认关闭契约被脚本反向弱化（P1）**、以及 **1 个离线化目标未完全达成（P1，redoc 仍远程拉 logo）**。其余为 P2 级健壮性/一致性问题。

---

## P1 问题

### P1-1　Token `scopes` 仅为展示，运行时从未校验（安全语义缺口）
- **位置**：`portal/src/pages/Tokens.tsx:17-24`（`SCOPE_OPTIONS` 预设）、`app/routers/admin.py:126`（入库）、`app/core/security.py:95-97` + `app/core/authz/runtime.py:31-42`（鉴权路径）
- **问题**：Portal 创建 Token 时支持多选 scopes（`kb:read`、`doc:write`、`search:query` 等）并存入 `api_tokens.scopes`，但运行时**没有任何代码读取该字段**。`security.py` 静态模式校验只比对 sha256 哈希集合（`is_token_valid` → `is_token_in_db`），身份/权限上下文完全来自请求头（`_context_from_headers`）。也就是说：给 Token 配了 `doc:write`，实际调用任意接口都不会受限，UI 呈现的「作用域=权限控制」语义与实际行为不符。
- **依据**：`grep` 确认 scopes 仅存在于 schema/adapters 的身份上下文中（来自 header/claims），DB token 记录 scopes 无消费方；与 AUTHZ 运行时的 `action`（`create`/`update`/`read`/`write`/`query`）命名体系也不一致（预设用 `kb:read`，运行时是 `resource_type:action`）。
- **建议**：二选一并在文档中明确——(a) 若要真正生效，在静态 token 命中后把记录 scopes 注入 `request.state.permissions` 并经 PolicyEngine 校验；(b) 若暂不落地，**移除 UI 作用域多选或标注「预留，未生效」**，避免运营人员误以为已授权。同时在 `docs/` 说明该限制。

### P1-2　启动脚本自动生成并打印管理 token，反向弱化「管理面默认关闭」契约
- **位置**：`scripts/start_open_platform.sh:22-25`
- **问题**：`OPEN_PLATFORM_ADMIN_TOKEN` 未配置时自动 `secrets.token_hex(16)` 并 `echo` 到 stdout。脚本是文档推荐启动方式，意味着**只要用脚本启动，管理面就从「默认关闭」变为「默认开启」**，且明文 token 进入终端/日志（CI、journald、shell 历史都可能留存）。这与 AGENTS.md §4.3「未配置时管理面默认关闭，避免暴露」及 README 新增描述（`503001` 默认关闭）矛盾。
- **依据**：`admin_enabled()` 仅判断环境变量非空（`app/core/admin/auth.py:24-25`），脚本必然导出该变量；token 明文打印无任何遮蔽。
- **建议**：保留本地便利的同时——打印时给出一次性遮蔽提示（如截断显示 `****...` 尾 4 位）、或增加 `OPEN_PLATFORM_ADMIN_AUTOGEN=off` 开关、或在 README 明确「使用本脚本 = 管理面开启，日志可见 token，仅限本地」；生产部署路径（systemd/k8s）保持显式注入。

### P1-3　redoc 离线化未完全达成：bundle 内仍有远程资源拉取
- **位置**：`app/core/static/docs/redoc/redoc.standalone.js`
- **问题**：`get_redoc_html(... with_google_fonts=False)` 已关闭字体，但 vendored 的 `redoc.standalone.js` 内部仍含 `src:"https://cdn.redoc.ly/redoc/logo-mini.svg"`（带 `onError` 兜底，离线时仅缺 logo）。这与改动目标「页面不再引用外部 CDN，离线环境可用」部分冲突。
- **依据**：grep 确认 bundle 中含 `cdn.redoc.ly/redoc/logo-mini.svg`；新增测试 `test_api_docs_use_local_static_assets_no_external_cdn` 只检查**页面 HTML** 中的 URL（`tests/test_auth_middleware.py:137-140`），未扫描 vendored 资源本身，形成盲区。
- **建议**：若严格离线，可在构建 redoc 时以 build 配置替换 logo URL 或本地化该图片；若可接受「仅缺 logo」，在 README 注明，并把测试扩展到对 vendored 文件做外部域名扫描。

---

## P2 问题

### P2-1　`/admin/tokens` 无 Pydantic 校验，错误类型输入导致 500 或脏数据
- **位置**：`app/routers/admin.py:132-137`（`payload: dict[str, Any]`）→ `app/core/admin/token_store.py:127-131`
- **复现**（已实际验证）：`expires_in_seconds="3600"`（字符串）→ `TypeError: unsupported operand type(s) for +: 'int' and 'str'`（500）；`scopes` 传字符串 → `",".join()` 逐字符展开成 `['k','b',':','r','e','a','d',...]` 垃圾数据入库。
- **建议**：为创建请求定义 Pydantic `CreateTokenRequest`（`name: str`、`scopes: list[str] | None`、`expires_in_seconds: int | None`，且 `ge=1`），或至少显式 `int()`/`list()` 转换并做类型校验。

### P2-2　`/` 重定向与 `/portal` 挂载时机不一致（开发流）
- **位置**：`app/core/system_routes.py:20-23` vs `app/core/app_factory.py:89-90`
- **问题**：`/portal` 在 `create_app()` 时按 `_PORTAL_DIST.is_dir()` 决定是否挂载；而 `/` 重定向在**每次请求时**检查该目录。若启动时未构建、运行中构建了 portal → `/` 跳到 `/portal/` 但路由不存在（404）；反之启动时有、运行时删掉 → 跳转与实际挂载相反。
- **建议**：把「portal 是否可用」收敛为单一来源（模块级常量或 `app.state`），重定向与挂载共用同一判断。

### P2-3　静态文档免鉴权前缀以字面量重复定义，存在安全耦合
- **位置**：`app/core/middlewares.py:15`（`"/_static/docs"`）与 `app/core/app_factory.py:23`（`_DOCS_STATIC_PREFIX`）
- **问题**：两处字符串分离，未来若改挂载前缀而漏改中间件，文档静态资源将落入业务鉴权（或反之导致意外公开）。且 `/_static/docs` 前缀豁免后，该目录下**所有文件**无鉴权可读——当前仅含公开的 swagger/redoc 库文件，风险低，但目录被后续误放敏感文件则直接暴露。
- **建议**：从共享常量（如 `app/core/static/docs` 配置模块）导入前缀；并在该目录 README 标注「仅放公开静态资源，禁止放敏感文件」。

### P2-4　管理面统一响应体 `traceId` 恒为空，与业务链路不一致
- **位置**：`app/routers/admin.py` 全部成功响应（如 `:31` `"traceId": ""`、`:60`、`:72`…）及内联错误（`create_token` 空 name 返回 `"traceId": ""`）
- **问题**：业务侧 `traceId` 由 Trace 中间件填充真实 23 位 ID（`middlewares.py:114-115`、`exception_handlers.py` 各 handler），管理面却硬编码空串，跨链路排障（尤其 /admin 与业务混查日志中心）时丢失关联。
- **建议**：统一改用 `current_trace_id()`，或让 admin 响应也经由统一错误处理/响应构造器。

### P2-5　新增测试的确定性/覆盖盲区
- **位置**：`tests/test_system_routes.py:11-20`、`tests/test_auth_middleware.py:129-145`
- **问题**：(a) `test_root_redirects_to_portal_when_built` 以**本机 `portal/dist` 是否存在**决定断言分支——CI 与本地若构建状态不同，测试断言的是不同行为，无法真正回归「重定向目标正确」；(b) CDN 测试只查页面 HTML，漏掉 vendored bundle 内的远程 URL（见 P1-3）。
- **建议**：(a) 用 tmp_path/fixture 模拟构建目录或改为断言「与 `_mount_portal` 同一判断一致」；(b) 对三个 vendored 文件做外部域名黑名单扫描。

### P2-6　（次要）Token 有效期选择「今天」时生命周期趋近于 0
- **位置**：`portal/src/pages/Tokens.tsx:104-110`
- **问题**：`new Date('${expiresAt}T23:59:59')` 取当日 23:59:59，选「今天」时 `expiresInSeconds` 可能只剩几十秒/负数（负数已被 `<=0` 拦截，但正值也近似立即过期）。
- **建议**：校验 `expiresAt` 必须晚于今天，或至少提示「今天创建将在今天结束时失效」。

---

## 其他观察（非本次引入）

- `/admin/*` 仍出现在 `/openapi.json` 与 `/docs`（admin router 未设 `include_in_schema=False`）。AGENTS.md 要求管理面不进入业务 catalog——catalog 已排除 admin，但 OpenAPI 文档对未认证访问者可见 admin 端点清单。属既有行为，建议后续关闭 admin 的 schema 暴露。

## 正向确认

- `AdminDisabledError` → `503001` 统一注册进 `/api/error-codes`，测试断言齐全，HTTP 503 + 统一壳 + 真实 traceId 实测正确。
- `/_static/docs` 免鉴权 + 本地 swagger/redoc 资源可访问，页面 HTML 无 jsdelivr/google fonts/unpkg 引用，swagger css 外部引用均为 data URI。
- `feedback.tsx` toast 手动关闭会清理对应 timer，卸载清理全部 timer；`confirm` 弹窗 Escape 可取消，均无泄漏。
- Token 明文仅创建时返回一次、库中仅存 sha256、登录用 `sessionStorage`（非 localStorage），符合既有安全设计。
- 测试套件完整覆盖新增行为，181 全绿。
