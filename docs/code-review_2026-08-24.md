审查完成。以下为只读审查报告。

---

# open-ikc 代码审查报告（2026-08-24 工作区改动）

## 结论

改动整体质量良好：新路由（`wiki/stat`、`wiki/export`）鉴权链路、统一响应体、catalog 登记、SDK/MCP/CLI 三端覆盖、回退语义测试基本一致。发现 **P1 1 项、P2 3 项、P3 若干**。核心关切集中在 **AUTHZ 数据权限上下文不完整（KB 类型无 role 映射）**、**async 解析引擎联动在真实异步引擎下的语义缺口**、**`ensure_wiki` 的乐观同步创建在并发下的竞态**。

---

## 问题列表

### P1-1：`owner_id`/`org_path` 授权上下文来自数据库记录，未与调用方身份绑定

**位置**：`app/routers/knowledge_base.py:403-418`、`:427-446`（`stat_wiki_pages`/`export_wiki_pages`，以及既有 `get_wiki_tree`/`wiki_page`/`wiki_search` 等）

**依据**：AGENTS.md §4.2 明确「`owner_id`/`org_path` 一律取认证身份（`request.state.identity`），请求体 `ownerId`/`orgPath` 不作为授权依据」。而 AUTHZ `policy.py:_match_data_scope` 的 owner-only 判定是 `request.context["owner_id"] == identity.user_id`。新路由把 `record.owner_id`（库创建者）作为 `owner_id` 上下文传入——当 AUTHZ 配置了 owner-only 数据权限、且库创建者 ≠ 当前调用方时，**授权引擎拿「库主」去比对「调用方」恒不相等 → 无权限**；反之若配置宽松（直接透传），上下文中的 `owner_id` 又不是当前身份，owner-only 判定语义错乱。

与既有 `update_knowledge_base`（`:75-85`）写法一致，说明这是**全库共性问题**而非本次新增，但新路由复用了这一模式，本次应一并修。

**影响**：owner-only 数据权限规则在新 Wiki 只读路由上不可用（要么全拒、要么错放）。

**建议**：AUTHZ 决策上下文中区分两套字段——`owner_id`/`org_path` 传 `request.state.identity`（认证身份），库归属（`record.owner_id`/`record.org_id`）另放如 `data_owner_id`/`data_org_path` 供数据范围判定；路由与桥接层对齐后统一修正所有 wiki/graph/kb 路由（`bridge.py` 当前逻辑需核对）。

---

### P1-2：`KnowledgeBaseException` 带 `unavailable` 属性会被误判为引擎不可达而**静默吞掉真实业务错误**

**位置**：`app/services/wiki.py:95-101`、`:133-139`、`:166-173`、`:201-207`、`:238-244`、`:279-286`

**依据**：`OpenWikiEngineError.__init__` 以 `CommonErrorCodes.INTERNAL_ERROR` 构造 `KnowledgeBaseException` 并设置 `self.unavailable = True`。Service 回退逻辑是 `except KnowledgeBaseException as exc: if not getattr(exc, "unavailable", False): raise`——即引擎抛出的 **任何非 unavailable 的 `KnowledgeBaseException` 都会向上抛出，不触发回退**。问题在引擎路径内部：`ensure_wiki` 里 `_request` 对 `errCode != "0"` 且未映射到的引擎错误码会 `raise OpenWikiEngineError`（unavailable=True，回退 OK），但对映射过的错误码（`200404/200409` 等）抛的是**普通 `KnowledgeBaseException`，不带 unavailable**。若引擎侧 `build/stat/export` 中途因某个映射错误码失败，平台侧直接把这个错误抛给调用方——语义上是「引擎业务失败」，不应当作平台错误码透出。

**更关键的误判方向**：如果某处 `KnowledgeBaseException`（非引擎）恰好带了 `unavailable` 属性（例如其他业务异常被设为 True），会被静默吞掉。当前仓库仅 `OpenWikiEngineError` 设该属性，风险可控，但该回退契约是「鸭子类型」判断，脆弱。

**建议**：为「可回退」设独立异常类（如 `EngineUnavailable`）并 `except EngineUnavailable` 精确捕获，勿用 `getattr(exc, "unavailable")` 扫描所有 `KnowledgeBaseException`。

---

### P2-1：AUTHZ role→action 映射缺 `knowledge_base:read`/`knowledge_base:write`，新 Wiki 路由在 digital_employee 默认映射下必然 100403

**位置**：`app/core/authz/runtime.py:111-118`（`de_role_mapping`）

**依据**：`digital_employee` 的 `de_km_reader` 只有 `search:query / knowledge_base:read / document:read / parse:read`。新路由 `authorize_or_raise(action="read", resource_type="knowledge_base")` 需要 `knowledge_base:read`，`de_km_reader` 已含 → 读通过；但 `km_reader`（default 系统）只有 `search:query`，任何 wiki 读操作都会 100403。图谱既有路由（`graph/stat` 等，`:246-261`）也同此问题——即**图谱路由在 `km_reader` 角色下本来就不可用**，本次新增的 wiki 只读路由沿用了同一口径。AGENTS.md §4.2「角色映射一致性」要求 action/资源类型必须对齐。

**影响**：default 系统的 `km_reader` 无法读取 wiki/graph 库；角色与资源类型不一致。

**建议**：在 `runtime.py` 默认映射与 `OPEN_PLATFORM_DEFAULT_ROLE_ACTION_MAPPING` 示例中补 `knowledge_base:read`；`km_reader` 至少补 `knowledge_base:read`，并同步文档。此问题在本次改动之前已存在于 graph 路由，属存量问题，但新增 wiki 只读路由应一起纠正。

---

### P2-2：async 解析链路在引擎启用时直接返回 QUEUED，但无引擎任务 ID、也无任何异步任务查询接口

**位置**：`app/services/parse.py:337-338`

**依据**：`ParseService.parse` async 分支登记 `QUEUED` 任务后，仅当 `openwiki_enabled()` 时调 `_build_kb_assets_after_parse(doc, execute_mode="async")`，后者对 wiki 库走 `openwiki_client.build_from_doc(... async_build=True)` 提交引擎异步任务（`wiki.py:279-287`）。但：
1. 平台侧 `parse_result/query` 只查 `ParseTaskStore` 本地状态（`parse.py:346-361`），**引擎的 async 任务状态无从查询**，调用方轮询只会看到永恒 `QUEUED`；
2. `wiki.py:287` 在 `async_build=True` 且引擎可用时返回 `[]`，进程内 `WikiPageStore` 不落任何页面——一旦引擎不可达**且** async，页面永远不建（`wiki.py:288-291` 提前 `return []`）；
3. sync 分支（`:307`）`execute_mode="sync"` 对引擎启用时走的是同步构建（`async_build=False`），行为与 async 分支不一致。

**建议**：明确 async 引擎联动的最小闭环——要么暂不支持 async 引擎联动（回退本地占位，与 sync 对齐），要么在 `parse` 响应里携带引擎任务引用并在 `parse_result/query` 透查引擎 `get_job`。当前状态是「半挂」：任务登记为 QUEUED 但无人消费，测试也未覆盖（`test_wiki_engine.py` 只测了 `build_from_doc` 层，未测 `ParseService` 全链路）。

---

### P2-3：`ensure_wiki` 乐观创建并发竞态 + `_request` 对 HTTP 4xx 无业务错误码时的处理

**位置**：`app/services/openwiki_client.py:81-103`、`:56-78`

**依据**：
1. `ensure_wiki` 先 GET 判断 404 再 POST 创建，无锁/无幂等键（POST 只用 `kbId` 作业务幂等）。引擎侧未按 kbId 幂等时，**并发首请求会重复建 wiki 实例**（409 被映射为 `CommonErrorCodes.CONFLICT` 抛给调用方，见 `_ENGINE_CODE_MAP` 的 `200409`）。
2. `_request`（`:76-77`）：当 `response.status_code >= 400` 但 body 的 `errCode == "0"` 时抛 `OpenWikiEngineError`（unavailable=True → Service 回退）。但若引擎对 **HTTP 404 返回 errCode=200404**（测试 `test_engine_error_mapping` 断言了此路径），`_request` 在 `:71-75` 就抛普通 `KnowledgeBaseException`，`ensure_wiki` 的 `except` 按 `exc.error != NOT_FOUND` 判断再走创建——这里**依赖引擎在 HTTP 404 时 body 也带 errCode 200404**；若引擎只回 HTTP 404 + body errCode=0，`_request` 会抛 unavailable 错误，`ensure_wiki` 不会创建（因为 `except KnowledgeBaseException` 只接 `NOT_FOUND`），Wiki 视图整体回退进程内——语义尚可，但与 `test_ensure_wiki_creates_on_engine_404` 的假设（body 带 200404）耦合。

**建议**：`ensure_wiki` 改为幂等创建（POST 携带期望幂等键或引擎侧保证按 kbId 幂等）；`_request` 对 `status_code >= 400` 且 body 无有效 errCode 时明确归类为 unavailable，避免与业务 4xx 混淆。

---

### P3（次要）

1. **stat 回退语义的字段口径**：`WikiService.stat` 进程内回退时 `active == len(pages)`、`deprecated == 0`（`wiki.py:223-229`），而 `WikiPageStore.list_pages` 已过滤 `status == ACTIVE`（`wiki_store.py:93-99`），与引擎态 `pageCount`（含废弃）语义一致，但进程内从不产生 deprecated（`deprecate_doc_pages` 无调用方），未来接入引擎前 stat 的 deprecated 恒 0 属占位语义，建议在文档标注。
2. **`WikiStat.from_dict` 值类型强转**：`sdk/.../models/wiki.py:239` `tags={str(k): int(v)}`，若引擎返回非整数值会抛 `ValueError` 而非优雅报错；`linkCount`/`pageCount` 用 `int(data.get(...) or 0)` 对 `0` 值 OK 但对 `"abc"` 会抛。引擎数据不可信时建议容忍失败并给默认值。
3. **`test_tool_inventory_matches_contract` 用 `asyncio.run`**：`sdk/.../tests/test_mcp_tools.py:677` 在已是 async 的上下文嵌套 `asyncio.run` 有潜在冲突（MCP 2.0 server 内部可能已在运行 loop），当前测试通过（134 passed），但嵌套 event loop 属脆弱写法。
4. **`wiki-export` CLI `--format` 无枚举校验**：`sdk/.../cli/__init__.py:313` 允许任意字符串透传，平台侧 `pattern="^(jsonl|json)$"` 会拦（100001），但 CLI 层更好在本地 `typer.Option` 校验；admin 白名单 `wiki-export --format` 也未限取值（`mcp_cli_test.py:46`），不过平台兜底拦截，风险低。
5. **`parse.py` 顶层 `from app.services import openwiki_client`**（`:26`）：模块级导入使 `openwiki_client` 在无 `OPENWIKI_SERVER_URL` 时也参与 import；该模块依赖 `httpx`（pyproject 已声明），无环，当前无碍，但保留为惰性局部导入更稳（与 `app/services/wiki.py` 同）。
6. **worklog 提到「`295 passed`」**：沙箱内 TestClient anyio portal 死锁为已知环境问题，本次 `tests/test_wiki_engine.py`（不依赖 TestClient）未受此影响，建议在 worklog 中明确沙箱/非沙箱验证差异。

---

## 覆盖核对

| 改动点 | 覆盖情况 |
| --- | --- |
| `wiki/stat`、`wiki/export` 路由 + 统一响应 | `tests/test_wiki_engine.py:92-112`（回退路径 stat/export）✅；**缺路由级 AUTHZ/越权测试**（非 owner 调用、kb_mode≠wiki 拒绝）⚠️ |
| openwiki_client 引擎代理/错误映射/回退 | `tests/test_wiki_engine.py:63-88, 133-246` ✅（含 404→创建、unavailable→回退、业务错误传播） |
| catalog 同步 | `app/core/catalog.py:41-50` 已登记两路由 ✅ |
| SDK/MCP/CLI | `test_mcp_tools.py` 工具清单含 `wiki_stat/wiki_export` ✅；CLI 命令注册 ✅；**缺 CLI `wiki-stat`/`wiki-export` 的单测**（`test_cli.py` 只有 wiki-tree/page/search）⚠️ |
| admin 白名单 | `mcp_cli_test.py:45-46,86-87` 已加；文档同步 ✅；**缺白名单测试**（`tests/test_admin_*` 未含新命令）⚠️ |
| redoc 对齐 | `tests/test_auth_middleware.py:132-148` 断言 `schema-definitions-tag-name` ✅ |
| async 解析联动 | **未覆盖** `ParseService.parse` async + 引擎链路 ⚠️（P2-2） |

---

## 建议优先级

1. 修 P1-1（owner/org_path 上下文语义）——全库既有模式，需一次对齐；
2. 修 P2-1（`km_reader` 角色补 `knowledge_base:read`）——一行 + 文档，见效快；
3. 明确 P2-2 async 引擎联动闭环（或回退占位）；
4. `ensure_wiki` 幂等化（P2-3）；
5. 补 `test_admin_*` 白名单断言与路由级越权测试。
