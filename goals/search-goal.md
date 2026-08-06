# Goals

## 检索域真实实现（统一检索问答）

**状态**: 已完成 ✅
**创建日期**: 2026-08-05
**完成日期**: 2026-08-05

### 目标

将 `app/routers/search.py` 与 `app/services/search.py` 中占位接口（`501001`）落地为真实实现，对齐 V2 精简方案与详细定义 D-01，接入 AUTHZ。检索是四类对外能力中最后一个占位域，落地后四域全真实。

### 任务分解

1. **store**（`app/services/search_store.py`）— 新增
   - `SearchIndexRecord` frozen dataclass：doc_id/kb_id/doc_title/chunk_id/content/keywords/tags/metadata/owner_id/org_path/page/position/created_at。
   - `SearchIndexStore`（进程内，原子读写）：`index_doc`（按 doc_id 重建索引，幂等覆盖）、`get_by_doc`、`search`（限定 kb_ids + 元数据过滤 + 关键词加权打分 + topK 截断）、`reset`。
   - 轻量分词 `_tokenize`；打分 `_hit_score`（标题 3.0 / keywords 2.0 / content 1.0）。

2. **schemas**（`app/schemas/search.py`）— 扩展
   - `SearchQueryRequest` 新增 `teamId`/`orgId`/`mode`（search|qa，默认 qa）/`topK`（默认 5）/`filters`/`withCitation`（默认 true）；field_validator 校验 mode 枚举与 topK>=1；model_validator 要求 kbId/kbIds 至少其一。
   - `SearchResultItemData` 补 `docTitle`；`SearchQueryData` 补 `total`。

3. **responses + service**
   - `app/core/responses.py` 新增 `search_query_response(answer, total, results)` 构造器（收敛 service 内联）。
   - `app/services/search.py` 占位替换：逐 kb `get_or_raise`（100404）、个人库仅创建者可检索（100403）、`SearchIndexStore.search`、mode=search 空 answer / mode=qa 占位 answer（引用 top1 证据，注明回答引擎落地后替换）、topK 截断、withCitation 控制引用。

4. **router + AUTHZ**
   - `app/routers/search.py` 保留 `action="query", resource_type="search"` 授权；注入完整数据上下文（kb_id/kb_ids/owner_id/org_path/team_id/org_id/query）；从 `request.state.identity` 取 owner_id/tenant_id 传 service（修复占位期未传身份的缺口）；description 去掉「预占位」。

5. **测试**（`tests/test_search.py`，重写 18 例）
   - 成功（qa/search 两 mode）、topK 截断、filters 过滤、withCitation=false 清空引用、无索引空结果、qa 无命中占位 answer、kb 不存在 100404、个人库越权 100403、个人库创建者可检索、缺 kb 范围 100001、非法 mode/topK 100001、未认证 100401、AUTHZ deny-permission 拒绝 / admin 放行 / reader（km_reader 含 search:query）企业库放行、catalog 一致性。

### 约束（AGENTS.md §11）

- 不扩大能力面：检索路由已在 catalog，不新增接口；不新增第五类业务域。
- 统一响应体 errCode/errMsg/data/traceId 不可拆。
- 错误码复用公共码（100404/100403/100001），检索域不新增错误码。
- 中文注释与文案，`from __future__ import annotations` 文件首行。
- 检索索引为进程内内存模拟，真实索引引擎落地前由调用方显式注入（不随 ingest/parse 自动构建）。

### 验收标准

- [x] 全量测试通过：**139 passed**（原 123 + 检索域 16，其中 test_search.py 2→18 例）
- [x] SDK 测试 **91 passed** 无回归
- [x] 端到端冒烟：create KB → 注入索引 → query `000000`（answer/结果/23 位 traceId）；mode=search 空 answer；不存在 kb `100404`
- [x] 更新 `docs/worklog.md`（2026-08-05 条目）

### 完成摘要

- 新增 `app/services/search_store.py`、`goals/search-goal.md`
- 改写 `app/services/search.py`（真实实现）、`app/routers/search.py`（AUTHZ + 身份传递）、`app/schemas/search.py`（mode/topK/filters/withCitation + 校验）、`tests/test_search.py`（18 例）
- `app/core/responses.py` 新增 `search_query_response` 构造器
- 同步 README §当前实现进度、V2 详细定义附录、SDK 集成设计 §6.4
