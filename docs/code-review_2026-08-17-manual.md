审查完成。以下是只读审查报告。

---

# 代码审查报告：开发手册接入 Portal（fba9452 变更集）

**审查范围**：自 `77be2ac` 起的 11 个文件 + 1 个未跟踪文件（`.vscode/settings.json`，工作区配置，不参与行为审查）
**审查方式**：只读，未修改任何文件
**审查重点**：AUTHZ 一致性、统一响应体/异常链路、认证鉴权与越权风险、schema 边界、测试覆盖

## 结论

**通过，无 P0/P1 问题。** 本改动是纯文档页功能（`/api-manual` 服务端渲染 `docs/API开发手册.md`）+ 一处监控中间件健壮性修复，不触碰业务路由、AUTHZ 映射或统一响应协议。与契约（AGENTS.md）的同步要求（AUTH_EXEMPT_PATHS、测试、README、pyproject、worklog）均已完成。发现 3 项 P2 改进点与 1 项需知悉的行为变化。

## 逐审查点核对

### 1. AUTHZ action/资源类型与角色映射一致性 — ✅ 无问题
本次改动零业务路由变更，`/api-manual` 与 `/api-browser`、`/api/catalog` 同级，属于契约 §3.2 的「系统路由（免业务鉴权或文档用途）」，不进入 `knowledge-search/query` 类业务 action 的 AUTHZ 判定路径。`AUTH_EXEMPT_PATHS` 精确路径匹配（`middlewares.py:22`），不存在前缀误匹配业务前缀的情况，无鉴权绕过面。

### 2. 统一响应体与异常链路 — ✅ 无问题
`/api-manual` 是 HTML 文档页，与 `/api-browser` 一致豁免统一 JSON 协议（契约明确允许文档用途豁免）。真正值得关注的是 `monitor.py` 修复在异常链路上的语义——见 P2-4。

### 3. 认证/鉴权/凭证与越权风险 — ✅ 无真实凭证泄露（见 P2-2 信息暴露）
- 实测 `MarkdownIt("commonmark", {"html": False}).enable("table")` 的转义行为：`<script>`、`<img onerror>`、`javascript:` 链接、`data:` 链接、属性注入均被正确转义或拒绝渲染为链接；`/api-manual` 页面无用户输入（内容为仓库静态文档），XSS 面极低。
- 手册全文中 token 均为占位符（`your-token`/`<token>`），无真实凭证。
- 手册不含日志中心内部地址（`9315` 未出现在手册中）。

### 4. schema 校验与数据边界 — ✅ 无问题
markdown 渲染输入是仓库静态文件，无运行时用户输入，无 schema 边界问题。

### 5. 测试覆盖 — ⚠️ 见 P2-1
新增测试覆盖了渲染正确性（`test_system_routes.py:53`）、免鉴权参数化（`test_auth_middleware.py:26`）、尾斜杠归一化（`test_auth_middleware.py:161`）。但 **monitor.py 的 UnboundLocalError 修复没有回归测试**——这正是本次改动中唯一的行为变更。

---

## 问题列表

### P2-1 — monitor 异常路径修复缺回归测试
- **位置**：`app/core/admin/monitor.py:27-35` / `tests/test_admin_stats.py:96`
- **依据**：`test_monitor_middleware_records_requests` 仅覆盖正常路径（`/health` 200）。修复引入的行为变更——`call_next` 抛异常时不再记录统计、原异常正常上抛（不再被 UnboundLocalError 掩盖）——无任何测试断言。契约要求「新增/修改行为必须补测试」。
- **修复建议**：新增用例模拟异常路径：monkeypatch 使 `call_next` 抛异常（或指向一个抛未捕获异常的测试路由），断言 `stats._concurrency` 归零、异常原样抛出（不被 UnboundLocalError 替换）、`record_request` 未被调用。

### P2-2 — `/api-manual` 免鉴权暴露内部部署细节
- **位置**：`docs/API开发手册.md:470-475`（渲染入口 `app/core/api_manual.py:13`，免鉴权见 `middlewares.py:22`）
- **依据**：手册 CLI 配置示例含本机绝对路径 `"/home/open-ikc/.venv/bin/python"`，另含 DB 路径 `data/open_ikc_platform.db`（`:393`）。该页免业务鉴权对外可达，泄露主机目录结构与内部存储路径。
- **说明**：无真实凭证，且信息量低于 `/docs` 已免鉴权暴露的完整 OpenAPI 定义；属轻微信息暴露。
- **修复建议**：将 CLI 示例中 `/home/open-ikc/.venv/bin/python` 改为通用占位符（如 `path/to/venv/bin/python` 或 `$(python -c "import sys;print(sys.executable)")`）；DB 路径改为 `<OPEN_PLATFORM_DB_PATH>`。

### P2-3 — `render_api_manual_html` 每次请求全量读文件 + 渲染，无缓存
- **位置**：`app/core/api_manual.py:13-16`（async 路由 `system_routes.py:34` 内同步调用）
- **依据**：手册 33KB，每次请求都执行磁盘读 + 完整 markdown 渲染（实测级 ms），且在 `async` 路由中同步执行会短暂阻塞事件循环。内部平台流量低、影响有限，但与 `api_browser.py` 同样属于可优化项。
- **修复建议**：模块级缓存渲染结果（文件 mtime 变化时失效），或改为 `functools.lru_cache`/启动时预热一次；`async` 路由可改 `def`（FastAPI 会自动走线程池），避免阻塞事件循环。

### P2-4（需知悉）— 异常逃逸时请求不再计入统计
- **位置**：`app/core/admin/monitor.py:33-35`
- **依据**：修复后 `response is None` 时跳过 `_record`。即当 `call_next` 真正抛异常（而非经 `ServerErrorMiddleware` 捕获转 500 响应）时，该请求**不入统计**。
- **说明**：这是修复的合理取舍——原代码会 UnboundLocalError 掩盖真实异常，漏统计远好于崩溃。且实际触发场景有限：领域异常（`AppException`）与框架 500 均被 `exception_handlers.py` 捕获并生成正常 response（`call_next` 正常返回、统计照常记录），只有逃逸 `ServerErrorMiddleware` 之外的异常（如 trace 中间件自身出错）才触发此分支。并发计数 `stats._concurrency.dec()` 在 finally 无条件执行，计数正确。
- **建议**：知悉即可；若希望异常请求也有统计痕迹，可在异常分支降级记录 `errCode="999999"`（但会引入 try/except 复杂性，非必须）。

---

## 与契约符合性确认

| 契约要求 | 状态 |
|---|---|
| 新增系统级路径同步 `AUTH_EXEMPT_PATHS` | ✅ `middlewares.py:22` |
| 新增行为补测试 | ✅（除 monitor 修复，见 P2-1） |
| 声明依赖 | ✅ `pyproject.toml` `markdown-it-py>=3.0,<5.0` |
| 同步 README | ✅ |
| 同步 worklog | ✅ |
| 不占用业务四类能力 | ✅ 系统文档页，非第五类 |
| catalog.py 同步 | 不适用（`/api-browser` 等系统路由本就不在 `catalog.py`，文档页非业务接口，行为一致） |

## 验证记录
- `markdown-it-py 4.2.0` 已装，实测 6 类 XSS 输入全部正确转义/拒绝
- 中间件装配顺序 `framework_error → auth → monitor → trace → ServerErrorMiddleware` 已核对，monitor 修复不影响异常处理器链路
- 手册无真实 token（全占位符），无日志中心内部端口
- 全量 207 passed 的结论与 worklog 记录一致（本次未重跑，基于现有测试文件核对）
