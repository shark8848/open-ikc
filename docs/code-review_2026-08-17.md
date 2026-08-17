审查完成。以下是报告。

---

# 代码审查报告 — 检索能力优化（universal-search / deep-search）

**审查范围**：`d09f17f^..d09f17f`（普通检索 + 深度检索落地，对接 knowledge_transformer）
**审查方式**：只读，未修改任何文件
**测试**：未执行（`test_search_downstream.py` 新增 338 行覆盖已通读核对，与路由/service 行为一致）

## 结论

总体实现质量较高：统一响应体与异常链路、AUTHZ 接入方式、数据权限收敛逻辑均保持了与既有检索域一致的规范，测试覆盖对新后端映射（ur/openai/deep-search）和错误码传播较扎实。**无 P0 问题**。

发现 **P1 × 3、P2 × 6**，集中在：调用方可控字段回填身份导致的**数据权限绕过**（两处）、role-action 映射未包含 `search:query`、token 作用域无法在 `*:*` 通配下约束检索。详见下。

---

## P1（建议修复后再合入/上线）

### P1-1 调用方可控 `ownerId`/`orgId`/`teamId` 覆盖 AUTHZ 数据权限上下文 → 潜在越权

- **位置**：`app/routers/search.py:19-21`（`_authorize_scope` context 组装）、`app/routers/search.py:19`（`SearchService.query` 的 `owner_id`/`tenant_id` 来源）
- **依据**：
  - `DeepSearchQueryRequest`（`app/schemas/search.py:51`）、`SearchQueryRequest`（`app/schemas/search.py:12`）的 `ownerId`/`orgPath`/`teamId`/`orgId` 均为**调用方请求体字段**。
  - AUTHZ 上下文直接 `payload.ownerId.strip() or identity["user_id"]`：**调用方传入 `ownerId=任意值` 时，context 的 `owner_id` 采用调用方值**（`identity["user_id"]` 仅在 `ownerId` 为空时兜底）。
  - `policy.py` 的 owner-only 判定 `str(request.context.get("owner_id", ...)) == identity.user_id`：若调用方把 `ownerId` 设成其身份 user_id，则任一个人库（owner 为该用户）都被授权通过；若传与自身不同的值，则本应可访问的库被拒绝——**读的是身份还是外部字段，取决于是否空串**，攻击者只需传 `ownerId=<自己的user_id>` 即可命中 owner-only 条件，令资源 ID 范围、owner-only、org/team 条件全部按调用方自述值判定。
  - 同问题影响 service 层数据范围收敛：`app/services/search.py` 的 `_query_openai` 用 `owner_id`（调用方注入）构造下游 `user_id`、`_query_ur` 无该问题；`deep_query` 同样把调用方 `ownerId` 回填进 AUTHZ context。
- **修复建议**：AUTHZ context 的 `owner_id`/`tenant_id`/`org_path` 一律取自 `request.state.identity`（中间件注入的认证身份，`X-User-Id`/`X-Tenant-Id`），**不使用请求体回填**；`teamId`/`orgId` 仅在“数据范围校验”环节（`_validate_kb_scope`）从请求体读取（那是业务上的团队/组织归属声明，与授权身份分离）。补充测试：`ownerId=与身份一致/不一致` 时授权结果不变。

### P1-2 `role_action_mapping` 未包含 `search:query`，`km_reader`/`de_km_reader` 检索授权将 deny

- **位置**：`app/core/authz/runtime.py:90`（default 映射）、`app/core/authz/runtime.py:114-115`（digital_employee 映射）
- **依据**：
  - 检索路由 `authorize_or_raise(action="query", resource_type="search")`（`app/routers/search.py:42-43`）。
  - `MappingAuthzAdapter` 的 `role_action_mapping` 只把角色翻译为 `<resource>:<action>` 权限事实；default 的 `km_reader` 只有 `["search:query"]`，**`search` 不是资源类型**，`knowledge_base:read` 也不匹配 `resource_type="search"`。数字员工映射同理（`de_km_reader` 有 `search:query` 但没有 `search` 域；`de_km_operator` 也只有 document/parse/kb，无 search）。
  - 因此开启 `OPEN_PLATFORM_AUTHZ_ENABLED=true` 且调用方仅带角色（无显式 permissions）时，universal-search/deep-search 一律无命中 → deny-overrides 默认拒绝 → `100403`。
- **修复建议**：将映射中的 `search:query` 改为 `search:query`（若下游实际权限语义为 `search:query` 则把 `search:query` 加进映射），或在文档中明确“检索需在 `permissions` 头显式声明 `search:query`”。补一条开启 AUTHZ、携带 `km_reader` 角色的检索测试。

### P1-3 token 作用域 `*:*` 通配使 `deep-search` 无独立 scope 边界

- **位置**：`app/core/authz/runtime.py:77-83`（`_scope_allows`）、`app/routers/search.py:42`（action="query"）
- **依据**：`_enforce_token_scopes` 对 `resource_type:action` 做两侧 `*` 通配匹配。`deep-search` 复用 `action="query"`、`resource_type="search"`，token scope 无法区分普通/深度检索；若 DB token scope 配置 `search:query`，则 deep-search 同样放行（深度检索会触发下游 Agentic 多轮，成本/风险更高）。这属设计取舍，但按 AGENTS.md「权限不降级」应显式界定。
- **修复建议**：如深度检索需要独立管控，将 action 区分（如 `deep-search`）并同步 token 作用域/role 映射文档；否则在 README 明示 deep-search 与普通检索共享 `search:query` scope。

---

## P2（建议记录，后续处理）

### P2-1 `agent_steps` 数值转换用 `or 0`，合法 0 被替换为默认值
- **位置**：`app/services/search.py:363`（`docsCount`）、`app/services/search.py:364`（`elapsedMs`）
- 依据：`int(raw.get("docs_count") or ... or 0)` 将真实 0 误替换为 `0.0` 兜底值（对 `docsCount` 无实质影响，但 `elapsedMs` 为 0 的步骤会显示 0.0；语义等价）。建议 `X if raw.get(k) is not None else 默认`。

### P2-2 `SearchResultItemData` 的 `snippet`/`score` 与真实后端字段不一致
- **位置**：`app/schemas/search.py:85`（`score: float`）、`app/services/search.py:79-80`、`app/services/search.py:95-98`
- 依据：下游 `final_score` 可能为 `None`，`_ur_doc_to_item`/`_doc_item_to_item` 的 `score` 用 `or 0.0` 兜底，最终 `float(0.0)`；文档描述“真实后端接入后由下游生成回答”，但 `score` 目前不可区分“无分”与“0 分”。属字段语义歧义，非错误。

### P2-3 `searchType` 下游 `hybrid` 参数映射硬编码权重
- **位置**：`app/services/search.py:183`（`request["hybrid"] = {"strategy": "linear", "text_weight": 0.5, "vector_weight": 0.5}`）
- 依据：权重不可配置；若下游对 `hybrid` 参数有默认值，此硬编码可能覆盖。建议在 schema 增加可选 `hybridStrategy` 或交由下游默认。

### P2-4 `memory.mode` 校验与使用不一致
- **位置**：`app/schemas/search.py:38-41`（mode 仅 `caller`/`none`）、`app/services/search.py:304`（`request["memory"] = {"mode": "caller", ...}`）
- 依据：`mode="none"` 时若 `items` 非空，service 仍会带 `memory` 块发送（未显式 `enabled` 开关）；下游可能执行记忆注入。建议 `mode=="none"` 时忽略/清空 items。

### P2-5 下游错误体断言过严，可能与真实下游响应结构不符
- **位置**：`app/services/search_client.py:91-94`（`errCode`/`status` 校验）
- 依据：`err_code not in {"000000","0"} or status is False`——若下游返回 `{"code":0, "status": 0}`（整数 0 为 falsy）会误判失败。`status is False` 对布尔严格；对 `0` 应视为成功。建议 `status in (True, "true", 1)` 显式白名单。

### P2-6 后端不匹配时 `deep-search` 的提示文案与 `ur` 场景
- **位置**：`app/services/search.py:278-281`（`backend != "openai"` 时 `501001`）
- 依据：文档/路由描述“未配置 `OPEN_PLATFORM_SEARCH_BACKEND=openai` 时返回 501001”，与代码一致；但 `ur` 后端下 `deep-search` 也返回 `501001`，提示语未区分“未配置”与“后端不支持”，对排障者信息有限。建议在 reason 中附带当前 backend。

---

## 正面确认项（未发现问题）

- **统一响应体**：成功路径 `search_query_response`/`deep_search_query_response` 均经 `with_trace_id` + `error_response`，`errCode/errMsg/data/traceId` 完整（`app/core/responses.py:154-195`）；新增错误码 `300001` 已进 `SearchErrorCodes.registry()` 并注册到 `/api/error-codes`（`app/core/error_codes.py:138-143`、162-177），有测试断言（`test_search_downstream.py` `test_error_codes_catalog_contains_300001`）。
- **数据范围收敛一致性**：`_validate_kb_scope`（`app/services/search.py:60-...`）与 `KnowledgeBaseService._visible_records`（`app/services/knowledge_base.py:53-76`）的个人/团队/企业分支逻辑一致；服务端仍保留逐库校验，AUTHZ 仅前置。
- **中间件顺序**：`app_factory.py` 注册顺序为 Trace → AuthN → framework error，AuthN 先于 `authorize_or_raise`（`request.state.identity`/`token_scopes` 已注入），检索路由的 `_request_identity` 与 AUTHZ 桥接的 `_identity_from_request` 均能读到中间件注入的身份。
- **token 作用域 fail-closed**：`_lookup_token_scopes` 查询失败返回哨兵 `__scope_lookup_failed__`，`_scope_allows` 不匹配即拒绝（`app/core/security.py:117-137`）。
- **AUTHZ 逐库授权**：`_authorize_scope` 对每个 `kb_id` 单独 `resource_id` 授权，任一失败整体拒绝，符合 AGENTS.md「多库逐库授权」。

## 测试覆盖评估

- **新增**：`tests/test_search_downstream.py`（338 行）覆盖 ur/openai 请求映射、deep-search 请求/响应映射、`501001`（in_process/ur/下游 403）、下游 `300001`（连接/业务失败）、AUTHZ 先于下游调用（`test_downstream_permission_still_enforced_before_call`）、错误码目录、schema 校验（searchType/relNum）。
- **缺口**：
  1. 开启 `OPEN_PLATFORM_AUTHZ_ENABLED=true` + 角色映射的检索授权测试（P1-2 直接受影响，无测试覆盖）；
  2. `ownerId` 调用方注入 vs 身份字段的越权测试（P1-1）；
  3. token scope 通配 `search:query` 与 deep-search 边界（P1-3）；
  4. `mode="none"` 时 `memory` 注入行为（P2-4）。
- 既有测试已同步迁移 `/query` → `/universal-search`，`test_query_alias_matches_universal_search` 验证别名行为一致（`tests/test_search.py`）。

## 修复优先级建议

| 编号 | 严重度 | 处理时机 |
| --- | --- | --- |
| P1-1 | 高（越权） | 合入前修复 |
| P1-2 | 高（功能 deny） | 合入前修复 |
| P1-3 | 中（设计边界） | 合入前明确 |
| P2-1..6 | 低 | 记录待办，随迭代处理 |

> 说明：P1-1 为本次审查发现的最关键问题——调用方可通过请求体 `ownerId` 影响授权判定与下游身份传递，建议在合入前完成修复并补越权回归测试。P1-2 请与既有 AUTHZ 适配器文档核对实际角色→权限映射后修正。
