I now have a complete picture. Middleware order is correct (Trace outermost, then AuthN, then framework-error). The implementation is sound and tests pass (140). My findings center on authorization-completeness and multi-KB resource_id handling. Let me write the review report.

---

# 只读审查报告：检索域真实实现落地（open-ikc 2026-08-05/06 工作区改动）

**审查方式**：只读 + 定向探针（未修改任何文件）。范围：`app/` 业务改动、`tests/test_search.py`、catalog/文档同步。
**验证结果**：`pytest tests -q` **140 passed**；探针验证 AUTHZ 打开时跨所有者 team/enterprise 库检索放行、`withCitation=False` 正确置空、多库 `kbIds` 中越权库整体拒绝。

---

## 结论

改动整体质量高：统一响应体/异常链路、schema 校验、AUTHZ 接入、测试覆盖均达标的（P0 0 项）。发现 **P1 2 项**（与鉴权语义/数据范围相关，均属"权限不降级"契约边界内的缺口）与 **P2 4 项**。均不阻塞合入，但 P1 建议在检索接口对外宣称"个人库仅创建者可检索、team/enterprise 按范围收敛"前补齐。

---

## P1 问题

### P1-1 联合检索 `kbIds` 时 AUTHZ 的 `resource_id` 收敛为 `"*"`，数据范围条件无法命中 — `app/routers/search.py:45`

**位置**：`app/routers/search.py:45`
**依据**：路由把 `resource_id` 设为 `kb_ids[0] if len(kb_ids) == 1 else "*"`。多库检索时 AUTHZ 策略引擎（`policy.py`）对 `resource_id="*"` 的事实无条件匹配，`_match_data_scope` 的资源 ID 白/黑名单条件必须依赖 `context["kb_ids"]` 才能收敛。当前 `runtime.py` 内置 adapter 的角色映射（`km_reader: [search:query]`、`km_admin: [*:*]`）产生的权限事实**不含任何 `allowed_resource_ids`/`denied_resource_ids` 条件**，因此 `*` 与 `kb_ids` 实际无差别，资源 ID 维度对检索等于失效。
**实际效果（探针实测）**：`OPEN_PLATFORM_AUTHZ_ENABLED=true` 时，reader 用户 bob 检索 admin alice 的 **enterprise/team 库返回 `000000`**（service 只校验 personal 归属，AUTHZ 无 team/enterprise 成员或组织范围事实可命中）。数据权限收敛目前**只对 personal 库成立**。
**建议**：
1. 多库场景把 `resource_id` 改为每个库独立授权（循环 `authorize_or_raise`，AUTHZ 任一库失败即整体拒绝），或在 schema 层限制 `kbIds` 列表仅含个人库（由 service 逐库 `owner_id` 校验承担收敛），保持与 `context["kb_ids"]` 一致；
2. 明确 team/enterprise 库在真实团队/组织系统接入前的**最小校验边界**（当前设计文档 V2 附录已如实声明"依赖 AUTHZ 策略"），建议要么落地一条 owner 级事实，要么在文档中明确"enterprise/team 库当前仅靠调用方显式传 `teamId/orgId/ownerId` 收敛、不校验成员关系"（见 P1-2）。

### P1-2 检索 service 对 team/enterprise 库不做数据范围校验，与个人库不对称 — `app/services/search.py:62-68`

**位置**：`app/services/search.py:62-68`
**依据**：service 仅对 `kb_type == "personal"` 且 `owner_id != 调用方` 抛 `100403`；team/enterprise 库完全信任 AUTHZ（默认关闭时信任调用方传参）。同一请求在 `AUTHZ_ENABLED=true` 与 `false` 下对 team/enterprise 库的放行/拒绝差异完全取决于 AUTHZ 是否注入了范围事实——当前内置 adapter **没有**。文档 V2 附录第 4 条已如实声明该边界，但 README 第 7 条宣称"按知识库类型与调用主体数据权限过滤"与"个人库仅创建者可检索"，对外语义可能被误解为 team/enterprise 也已收敛。
**建议**：检索前对 `kb_type == "enterprise"` 至少校验 `record.org_id == (payload.orgId or identity.tenant_id)`、对 `team` 校验 `record.team_id == payload.teamId`（与 `KnowledgeBaseService.query` 的 `_visible_records` 逻辑对齐），AUTHZ 关闭时同样成立；真实组织/团队系统接入后由 AUTHZ 或成员服务承接。需同步更新 README 措辞，避免宣称已按组织/团队收敛。

---

## P2 问题

### P2-1 `search_query_response` 与 `SearchQueryData` 的 `data` 顺序在响应模型中未被强制 — `app/core/responses.py:154-167`

**位置**：`app/core/responses.py:154-167`（对照 `app/schemas/search.py:67-77`）
**依据**：`search_query_response` 构造的 `data` 键序为 `answer/total/results`，与响应模型字段声明一致，无实测问题。但该构造器直接透传原始 dict 到 response_model，若未来新增字段（如重设计方案的 `usage`/`debug`）仅改 `responses.py` 而漏改 schema，FastAPI 会以 response_model 校验截断字段，**不会**报错——存在静默丢字段风险。属于契约内"构造器收敛"的维护性提示。
**建议**：无需立即修改；后续扩展检索字段时同步修改 `SearchQueryData`，并在测试中增加"响应字段与 schema 全字段一致"断言（现有 `test_search_catalog_consistent` 只查路径，未查字段）。

### P2-2 `SearchIndexStore.index_doc` 以 `doc_id` 为唯一幂等键，跨库同 `doc_id` 会相互覆盖 — `app/services/search_store.py:96-121`

**位置**：`app/services/search_store.py:99-103`
**依据**：探针实测：同一 `doc_id` 先后注入 `kb_A`/`kb_B`，重建后仅剩 `kb_B` 条目（`_records` 按 `chunk_id = f"{doc_id}#{index}"` 存储，但清理按 `record.doc_id != doc_id` 全表过滤）。真实检索中文档 ID 是全局唯一的（`ing_`/`doc_` 前缀），当前仅测试直插与后续 ingest 联动会用到，故风险低；但若未来多租户复用同一 doc_id 模板会串库。
**建议**：清理条件增加 `record.kb_id == kb_id`，或将唯一键改为 `(kb_id, doc_id)` 复合键。属防御性修正，可在索引引擎落地时一并处理。

### P2-3 `filters` 仅支持标量精确等值匹配，无类型校验 — `app/services/search_store.py:186-190`

**位置**：`app/services/search_store.py:186-190`
**依据**：`_metadata_matches` 对 `metadata.get(key) != expected` 做精确比较，`filters` 字段是自由 `dict`，传入 `{docType: ["a","b"]}`、数字 vs 字符串等均无法匹配或静默空结果；schema 层也未对 `filters` 键值类型加约束。检索重设计文档已列出结构化过滤对齐需求。
**建议**：Phase 1 落码 `universalRetriever` 时补充 filters 的类型/字段白名单校验，当前可接受（进程内占位索引）。

### P2-4 catalog 检索路径 summary 与 README 对"按数据范围收敛"的表述略超前于实现 — `app/core/catalog.py:79-83`、`README.md:130`

**位置**：`app/core/catalog.py:79-83`；`README.md:130`
**依据**：catalog 检索 summary 为"统一检索问答"（与行为一致，无问题）；README 第 7 条宣称"按知识库类型与调用主体数据权限过滤"、"个人库仅创建者可检索"——后半句实测成立，前半句对 team/enterprise 不成立（见 P1-1/P1-2）。描述层面没有硬错误，但对外可被解读为"所有类型均已收敛"。
**建议**：README 措辞改为"个人库仅创建者可检索；team/enterprise 库范围收敛依赖 AUTHZ/外部组织系统（当前 AUTHZ 内置角色映射未含范围条件）"，与 V2 附录第 4 条保持一致。

---

## 达标项（与审查要点逐项核对）

| 审查要点 | 结论 |
| --- | --- |
| AUTHZ action/资源类型与角色映射 | `action="query"`、`resource_type="search"` 与 `km_reader: [search:query]` 映射一致；deny 用例（`X-User-Deny-Permissions: search:query`）实测返回 `100403`，deny-overrides 生效 |
| 统一响应体与异常链路 | 全部成功/失败均走 `{errCode, errMsg, data, traceId}`；`100404`（`get_or_raise`）、`100403`（个人库归属）、`100001`（schema 校验）链路正确；异常经 `AppException` 处理器统一带 `traceId`；中间件注册顺序 Trace 最外层 → AuthN → 框架错误改写，401 响应也带 23 位 traceId（测试断言覆盖） |
| 认证/凭证 | 认证头注入 identity 无新引入；`_request_identity` 从 `request.state.identity` 取 `user_id/tenant_id`，与 knowledge_base/document 路由一致；不存在凭证绕过路径 |
| schema 校验与数据边界 | `mode`/`topK`/`kbId/kbIds` 校验到位；`topK` 上限 100；多库列表通过 `model_validator` 强制至少一个 |
| 测试覆盖 | `tests/test_search.py` 19 例覆盖 qa/search/topK/filters/withCitation/空结果/404/403/100001/401/AUTHZ 三态/catalog；全量 140 passed 无回归；SDK 91 passed（worklog 记录） |

## 改动面核对

- **改路由必改 catalog**：检索路径 `/api/v1/knowledge-search/query` 在 `catalog.py` 中一致存在（测试断言覆盖）。✅
- **错误码 registry**：本批未新增错误码（复用 `100404/100403/100001`），符合"检索域不新增错误码"决策。✅
- **未跟踪文件**：`search_store.py`（新 store）、检索重设计草案（未落码，符合 AGENTS.md §10 关于 Excel 抽取需评审的约束）、`goals/`（记录型）、`code-review_2026-08-06.md`（本次审查输出，空文件待写）。`security-fix-document-parse` worktree 为另一分支，不在本次改动范围。

---

**修复优先级建议**：P1-1/P1-2 可在同一改动内闭合（服务层补 team/enterprise 范围校验 + 多库授权逐库化），并同步 README 措辞；P2 项列入检索接口重设计（`universalRetriever`）Phase 1 待办，不阻塞当前合入。
