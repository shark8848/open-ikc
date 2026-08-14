All verification complete. Let me compose the review report.

# 代码审查报告 — Token 作用域运行时强制生效（2026-08-14）

**范围**：未提交工作区改动（含未跟踪文件）。**模式**：只读审查，未修改任何文件。
**基线验证**：`pytest tests/ -q` → **189 passed**（含新增 `tests/test_token_scope_enforcement.py` 8 个）。

---

## 结论

改动整体质量好，P1 级安全语义缺口（上一轮审查的 P1-1「scope 仅展示不生效」）已被闭环：作用域真正在运行时强制校验，命名体系与 AUTHZ `resource_type:action` 对齐，8 个端点全覆盖，且有直接测试支撑。**未发现 P0 问题**。存在 **2 个 P1**（非本次引入、与本改动交织的鉴权缺口；及一个 scope 语义盲区）和若干 P2。测试 189 全绿，但有一条关键测试断言**在开放平台默认部署下与真实鉴权行为不一致**（P2-1），值得修正。

---

## P1 问题

### P1-1　`AUTH_EXEMPT_PREFIXES` 含 `/admin`——DB token 对管理面豁免鉴权，且 scope 未覆盖 admin
- **位置**：`app/core/middlewares.py:15`（`AUTH_EXEMPT_PREFIXES = ("/docs", "/redoc", "/admin", "/portal", "/_static/docs")`）
- **问题**：业务 AUTHN 中间件对所有 `/admin/*` 路径直接放行，管理面鉴权完全依赖 `admin_required`（`OPEN_PLATFORM_ADMIN_TOKEN` 比对）。这意味着**业务 DB token 与 admin token 在同一 HTTP 空间中**：若运维将同一 token 复用为 `OPEN_PLATFORM_ADMIN_TOKEN`（或凭据混淆），DB token 可直接调用 `/admin/tokens` 自我提权/查看明文 token——而新加的 scope 强制校验**只作用于四类业务端点**，对 `/admin/*` 无任何约束（`authorize_or_raise` 未在 admin 路由中调用）。这是上一轮即存在的缺口，本轮「运行时强制 scope」的语境放大了其影响：运维很可能以为 scope 约束了 token 的全部能力。
- **依据**：`middlewares.py:15`、`app/routers/admin.py:23`（`_admin_dep = admin_required`，仅比对单一 admin token）。
- **建议**：中期在文档（README「Token 作用域」段落）明确「作用域仅约束四类业务接口，管理面以独立 admin token 鉴权，禁止复用业务 token 作为 admin token」；或进一步拆分 token 空间（admin 端点要求 `X-Admin-Token` 头而非与业务共用 Bearer）。非本次改动引入，可按契约「修改行为时同步文档」顺带落实。

### P1-2　`_lookup_token_scopes` 静默吞异常——DB 故障时作用域约束退化为「不限」
- **位置**：`app/core/security.py:114-125`（`except Exception: return []`）；同模式 `token_store.py:245-247`（`except Exception: return []`）
- **问题**：static 模式下，若 `get_active_token_scopes` 抛异常（DB 锁、路径不可写、SQLite 损坏），返回空列表 → `_enforce_token_scopes` 直接放行。这与 `is_token_valid` 的同类静默失败叠加：`is_token_in_db` 失败返回 False 时 token 会被拒（fail-closed），但 **scope 查询失败则 fail-open**——一条「认证能过、但 scope 查询恰好失败」的 DB token 会获得超越其配置的权限。安全功能对故障的默认行为应 fail-closed。
- **建议**：`_lookup_token_scopes` 中 DB 层失败时记录告警日志（`logger.exception`）并**返回 None 语义**（即「无法确认 → 拒绝」，由 `_enforce_token_scopes` 对「配置了 scopes 但查询失败」抛 `100403`），或至少与 `is_token_valid` 保持一致的可观测性。当前返回 `[]` 的静默路径使「token 有 scopes 记录但查询异常」与「token 本就无 scopes」无法区分。

---

## P2 问题

### P2-1　既有测试断言与真实鉴权行为不一致（真实部署下可能暴露 scope 绕过）
- **位置**：`tests/test_admin_api.py:75-90`（`test_create_and_revoke_token_flow`）、`tests/test_token_scope_enforcement.py:91-98`
- **问题**：新增测试 `test_search_scope_allows_search_but_blocks_kb_create` 依赖 **DB 中不存在任何已撤销 token 记录**——若 DB 曾创建过 token（生产常态，`test_admin_api.py` 就是先创建 token），则「未配置 token 时放行」分支失效，行为改为「未命中集合即 401」。两条测试在同一套件中**互斥地改变全局 `is_token_valid` 语义**：`test_admin_api.py` 先创建 token 后断言 `kb.query` 用 scope 化 token 返回 `000000`（作用域 `knowledge_base:read` 命中 read，OK）；但 `test_create_and_revoke_token_flow` 撤销 token 后仍断言 `kb2` 返回 `100401`。真正的问题是**生产上任何已撤销 token 的存在都会把「未配置 token 请求」从放行翻转为 401**，而 scope 强制校验只在认证通过后生效——攻击者可先观察「有已撤销记录与否」推知 DB 状态。此乃既有设计（`has_any_token_record` 兜底），但本轮测试刻意规避了该状态，造成覆盖盲区。
- **建议**：`test_token_scope_enforcement.py` 在 fixture 中**先构造一条已撤销 token 记录**（复现生产常态），再验证 scope 放行/拒绝，避免与 `test_admin_api` 的状态互斥掩盖行为差异。

### P2-2　scope 前缀/字面量硬编码，且 `SCOPE_OPTIONS` 与运行时 action 集分离维护
- **位置**：`portal/src/pages/Tokens.tsx:18-26`（`SCOPE_OPTIONS` 硬编码 8 个预设）、`app/core/authz/runtime.py:77-83`（`_scope_allows` 对 `resource_type`/`action` 逐字比较）
- **问题**：前端预设（`knowledge_base:read` 等）与运行时 action 枚举（`create/update/read/write/query`，见 `routers/knowledge_base.py:38-105`）**分处两地、无校验**。若未来新增 `resource_type`（如 `team:read`）或 action（如 `delete`），前端预设可手填任意 `a:b` 字符串（`/admin/tokens` 仅校验「是数组」，不校验元素格式），运行时 `_scope_allows` 对未知 action 一律拒绝 → token 静默失效。同时 `partition(":")` 对 `a:b:c` 这类多冒号输入容忍为 `a`/`b:c`，不报错。
- **建议**：`/admin/tokens` 对 scope 元素做格式校验（`^[a-z_]+(\*):[a-z_]+(\*)$`，非法即 `100001`）；或在 catalog 注册 action 枚举供前端生成预设，避免双源漂移。

### P2-3　`_scope_allows` 的 `*` 通配不受 catalog 约束——`*:*` 等于完全放行，语义与「仅四类能力」契约边界有张力
- **位置**：`app/core/authz/runtime.py:77-83`
- **问题**：`*:*`（README 明确支持的示例）对任意 `resource_type:action` 放行。当前四类业务端点全部走 `authorize_or_raise`，但未来若新增端点忘记接入，scope 天然不拦截（等同无 scope）。且「`*:*` 放行」与 AGENTS.md「对外只开放四类业务能力」的强约束不同——授权语义上 `*:*` 只应覆盖**已注册**的 catalog 能力，而不是无条件放行。
- **建议**：`_enforce_token_scopes` 校验 resource_type 是否在 catalog 能力集合内（未注册类型直接拒绝），使 `*:*` 的放行范围始终受 catalog 边界约束。

### P2-4　管理面响应 `traceId` 恒为空串，与业务链路不一致（上轮 P2-4，本轮未动）
- **位置**：`app/routers/admin.py`（`create_token` 成功/失败响应均 `"traceId": ""`）
- **问题**：业务侧 `traceId` 由 Trace 中间件填充（`middlewares.py:114-115`），admin 侧硬编码空串。上轮已提出，本次未修复。跨链路排障（admin 建 token 与业务鉴权在同一请求时间窗）时丢失关联。
- **建议**：admin 响应统一走 `current_trace_id()`。

### P2-5　`expiresInSeconds` 精度问题（P2-6 残留）与 scope 无最小长度/上限
- **位置**：`app/routers/admin.py:139-156`；`portal/src/pages/Tokens.tsx:104-110`
- **问题**：(a) 上轮 P2-6 的「有效期选今天 → 生命周期趋近 0」仍存在（前端取当日 23:59:59 末秒，后端按秒取整，可能出现秒级即过期）——本轮后端新增的正整数校验拦截了 `<=0`，但正值亦可能近似立即失效，README 未提示；(b) 新增 scope 校验不限制数组长度/单元素长度，超大数组（如 10 万元素）会整串入库，`get_active_token_scopes` 每次请求全量拆分比对（无缓存），带来轻微放大开销。
- **建议**：前端校验 `expiresAt` 必须晚于今天；scope 数组限制上限（如 ≤ 32 个、单元素 ≤ 64 字符）。

---

## 其他观察（非本次引入）

- **`OPEN_PLATFORM_ADMIN_TOKEN` 自动生成并打印**（`scripts/start_open_platform.sh:22-25`）：README 已如实说明「自动生成随机 token 并打印」，但明文进入启动日志/shell 历史，与「默认关闭」契约存在张力（上轮 P1-2，本轮未动，README 措辞已收敛为「以该 token 为准」）。
- **redoc bundle 仍含 1 处远程资源**（`redoc.standalone.js` 内 `cdn.redoc.ly/logo-mini.svg`）：上轮 P1-3 盲区仍存在，CDN 测试只扫页面 HTML 未扫 vendored 文件。属既有项。
- **`.vscode/settings.json` 为新增未跟踪文件**（`chatgpt.runCodexInWindowsSubsystemForLinux: true`），建议确认是否入库。

---

## 正向确认

- **作用域命名与运行时完全对齐**：`knowledge_base/document/parse/search × create/update/read/write/query`，`authorize_or_raise` 覆盖全部 12 个业务端点（`routers/*.py` grep 确认），无遗漏。
- **`100403` 异常链路正确**：`AppException(CommonErrorCodes.FORBIDDEN, ...)` → `exception_handlers.app_exception_handler` → 统一 `{errCode, errMsg, data, traceId}`，HTTP 200 + `100403`，符合契约 §3.3。实测 `test_search_scope...` 断言 `errCode == "100403"` 通过。
- **越权面收敛**：`resource_id` 在 update/get/query/search 各端点均传入具体 `kb_id`/`doc_id`，数据权限条件保留在 AUTHZ context 中；scope 校验在 data-permission 之前（`runtime.py:42`），fail-fast。
- **明文安全**：DB 只存 sha256、明文仅创建时返回一次、撤销后 `100401` 即时失效，均有测试。
- **入参加固落实**：P2-1 的脏数据问题（scopes 字符串逐字符拆包）已用 `isinstance(raw_scopes, list)` + `int(raw_expires)` 显式校验堵死，`scopes 需为字符串数组` / `expiresInSeconds 需为正整数秒` 返回 `100001`，测试覆盖 `"abc"`/`0`/字符串数组三种非法输入。
- **测试质量**：`_scope_allows` 通配矩阵（含 `*:read` 非对称通配）、空作用域不限、环境变量 token 不限、admin 入参校验均有断言；全量 189 通过。

**建议优先处理**：P2-1（测试与真实鉴权行为互斥的盲区）、P1-2（fail-open 风险）。P1-1 建议在 README 作用域段落补一句约束说明即可，无需改码。
