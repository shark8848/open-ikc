# 代码审查报告：错误码命名一致性 + deep-search 响应去冗余

审查范围：本次未提交工作区改动（含未跟踪 `.vscode/settings.json`）。审查方式：只读；核对代码路径、SDK 消费方、Portal 前端、契约文档，并运行全量测试确认。

---

## 结论

本次改动方向正确且完成度高：`ErrorCode.to_dict()` 键名收敛到 `errCode/errMsg` 并与统一响应壳、OpenAPI schema、Portal 前端对齐；`get_error_code()` 的旧键名 KeyError 隐患确实被修复；admin 面 10 个端点收敛到 `_ok/_fail` 壳并接入真实 23 位 traceId；`TEST_FAILED=200020` 取代了借用 `200001 创建知识库失败` 的语义错误；deep-search 去掉与 citations 重叠的 `results[]`。全量 **209 passed** 通过，此前 report 中「200001 仍被 admin 引用」的疑问经核实为已改前的残留误读，现 admin 面已全部改用 `AdminErrorCodes.TEST_FAILED`。

**审查结论：无 P0/P1 级问题，可提交。** 以下 P2 建议 3 项 + 1 处文档契约级注意点，均不阻塞。

---

## 问题列表

### P2-1 内部文档契约 `docs/开放平台接口详细定义_精简版_V2.md` 未同步（遗留遗漏）

- **位置**：`docs/开放平台接口详细定义_精简版_V2.md:1127`（`data.results` 出参表）、`:1153`（示例 `"results": []`）
- **问题**：本次删除了 `DeepSearchQueryData.results` 并同步了 `API开发手册.md`，但《接口详细定义_V2》（AGENTS.md §3.1 指定的同步对象）的 deep-search 章节仍保留 `data.results | array<object> | 召回明细（字段同 D-01 results）` 及示例中的 `"results": []`。契约与实现不符。
- **依据**：AGENTS.md §3.1「新增/修改接口时使用 `/api/v1`，并同步：对应 `app/routers/*`、`app/core/catalog.py`、必要时 `docs/开放平台接口详细定义_精简版_V2.md`」。
- **修复建议**：删除 `:1127` 的 `data.results` 行（保留 citations 为唯一证据列表的说明），删除 `:1153` 示例中的 `"results": []`，并将出参表 `data.total` 语义由「召回证据总数」改为「回答引用证据总数」、citations 说明补 `page?`。

### P2-2 `AdminErrorCodes` 错误码前缀与业务域隔离约定不符（既有，非本次引入）

- **位置**：`app/core/error_codes.py:105`（`TEST_FAILED = ErrorCode("200020", ...)`）、`:104`（`ADMIN_DISABLED = ErrorCode("503001", ...)`）
- **问题**：业务码段 `2xxxxx` 为 knowledge-base/document/parse 的 business 域错误码；`200020` 落在其中。管理面按 AGENTS.md 与业务四类完全隔离，但错误码段仍与业务域重叠（`503001` 属 `5xxxxx` 系统域，也非独立管理域）。潜在风险：业务侧未来新增码段时可能与 `200020` 冲突（`error_code_catalog()` 有去重保护，但会出现「同一 code 两个 level/描述」语义混淆）。
- **依据**：AGENTS.md §3.3/§4.3 管理面与业务域隔离；`to_dict` 去重依赖唯一 code。
- **修复建议**：为 admin 预留独立码段（如 `4xxxxx`），将 `TEST_FAILED`/`ADMIN_DISABLED` 迁入；若此为有意设计（管理面错误码「语义独立」而编码空间沿用业务段），建议在 `error_codes.py:101-105` 注释中显式声明预留范围，避免后续冲突。属低风险、可留待文档说明。

### P2-3 deep-search `score` 取值兜底链不完全（既有逻辑，本次改动后暴露更明显）

- **位置**：`app/services/search.py:346`（`score = float((citation.get("scores") or {}).get("final_score") or 0.0)`）
- **问题**：普通检索 `_doc_item_to_item`/`_ur_doc_to_item` 的分数兜底链是 `final_score → rerank_score → fused_score → vector_score → lexical_score → 0.0`；deep-search 的 citations 只取 `final_score`，一旦下游 DeepSearch 引用证据的 `scores` 只带 `rerank_score` 或 `vector_score`（deep-search 默认 `useRerank=True`，重排场景常见），`score` 恒为 `0.0`。响应示例 `citations[0].score=0.9` 即来自下游 `scores.final_score`——若下游结构不含该键，`score` 失真。本次 `total` 改为 `len(citations)` 后，`score=0` 的条目仍计入总数，会放大「引用存在但分数全 0」的观感。
- **依据**：`app/services/search.py:71-86`、`:90-106` 的兜底链对比。
- **修复建议**：抽取共用分数解析函数 `_pick_score(scores: dict) -> float`（三处复用），或在 citations 分支复用与普通检索一致的兜底顺序。

---

## 已核对、确认无问题的点

1. **AUTHZ 身份来源 / 越权**：`app/routers/search.py:40-43` 的 `_authorize_scope` 中 `owner_id`/`org_path` 取 `request.state.identity`，请求体 `ownerId`/`orgPath` 仅作兼容字段不参与授权；`_validate_kb_scope`（`search.py:109-132`）逐库校验 personal/team/enterprise 数据范围，调用方无法注入他人身份越权。本次改动未触及。
2. **统一响应壳一致性**：业务响应 `with_trace_id(error_response(...))`（`responses.py:10-11`）与 admin `_ok/_fail` 均输出 `{errCode, errMsg, data, traceId}`；异常链路 `exception_handlers.py` 统一补 `traceId`；`ErrorCode.to_response()` 本身不带 `traceId` 但所有调用路径均经 `with_trace_id` 补全，admin 面原空串已改真实 traceId。schema `SearchQueryResponse`/`DeepSearchQueryResponse` 均含 `traceId` 必填。
3. **`to_dict` 键名变更无外部残留**：全仓 `grep` 仅 `search_client.py:91` 对下游容错读取保留 `.get("code")` 兜底（读的是下游响应而非本平台响应，属容错保留）；Portal 前端仅消费 `errCode/errMsg`；SDK 消费 `results/citations` 的字段名均与本次保留的响应一致。
4. **`get_error_code` 修复**：键名随 `to_dict` 同步改为 `errCode/errMsg`，无 KeyError；无生产调用方（仅内部），安全。
5. **`_fail`/`_ok` 不重复 `with_trace_id`**：admin 路由返回 `JSONResponse` 直出，`_ok/_fail` 已含 `traceId`，不会与中间件重复注入；`traceId` 在 `current_trace_id()` 无上下文时生成新 ID（不会空串）。
6. **`_resolve_kb_ids` 重复逻辑**（router 与 service 各一份）为存量，本次未引入回归。
7. **测试覆盖**：`test_admin_responses_carry_unified_trace_id` 覆盖 admin 壳 23 位 traceId；`test_deep_search_maps_request_and_response` 断言 `results not in data`、`total == len(citations)`；错误码目录测试全部迁移到 `errCode` 键。**209 passed** 全量通过。
8. **`.vscode/settings.json`**（未跟踪）：仅 `chatgpt.runCodexInWindowsSubsystemForLinux: true`，无敏感内容，可保留或按 `.gitignore` 策略处理。

---

## 附：文档 `API开发手册.md` 中一处可选的措辞修正（非错误）

`docs/API开发手册.md:344`（`total` 字段描述由「召回证据总数」改为「回答引用证据总数」）与实现一致；但 `docs/开放平台接口详细定义_精简版_V2.md` 出参表中 `data.total | integer | 召回证据总数` 仍为旧语义——若同步 P2-1，建议一并把该文档的 `total` 描述与 citations `page?` 字段补齐，保持双文档一致。
