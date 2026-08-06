# Goals

## 解析域真实实现（parse / parse-result query / download ticket / download）

**状态**: 已完成 ✅
**创建日期**: 2026-08-05
**完成日期**: 2026-08-05

### 目标

将 `app/routers/parse.py` 与 `app/services/parse.py` 中四个占位接口（`501001`）落地为真实实现，对齐 V2 精简方案与详细定义 B-02 / B-03 / B-04 / B-05，接入 AUTHZ。

### 任务分解

1. **store**（`app/services/parse_store.py`）— 新增
   - `ParseTaskRecord` frozen dataclass：task_id、doc_id、kb_id、parse_status（queued/running/success/failed）、execute_mode、parse_strategy、result_format、page_count、chunk_count、failed_reason、owner_id、tenant_id、created_at、finished_at。
   - `ParseResultRecord`：doc_id、task_id、total_page、parsed_pages、page_list、summary、keywords、questions、tags、result_format。
   - `ParseTaskStore`（进程内，原子读写）：create / get / get_by_doc / get_latest_success / save_result / reset。
   - `ParseTicketStore`：issue_ticket(doc_id, task_id, expire_seconds) → ticket + expireAt；validate_ticket(ticket) → doc_id/task_id（过期/无效抛 `TicketExpiredError`）；reset。
   - `generate_parse_task_id()`：`parse_` + 17 位数字（统一文档域形态）。

2. **schemas + error codes + responses**（进行中）
   - `app/schemas/parse.py`：`DocumentParseRequest`（kbId/docId/parseStrategy/resultFormat/executeMode/parseMode/chunkStrategy/chunkSize/reqId）、`ParseResultQueryResponse`、`IssueDownloadTicketResponse`、`DownloadResultResponse`（统一体 envelope，data 携带下载说明与 downloadPath）。
   - `app/core/error_codes.py`：新增 `ParseErrorCodes` — `PARSE_FAILED=200011`、`RESULT_NOT_READY=200003`、`TICKET_INVALID=200004`（200001 归属 KB 不动，V2「解析失败 200001」按现状让位于知识库 CREATE_FAILED，解析域走 20001x 区间）；接入 `error_code_catalog()`。
   - `app/core/responses.py`：解析域响应构造收敛到此处（parse/query/ticket）。

3. **service + router + AUTHZ**
   - `ParseService.parse`：文档存在校验（100404）、数据范围（personal 仅创建者 100403）、幂等（同 doc 既有 success/failed 复用，PARSING 中返回 RESULT_NOT_READY 200003）、登记任务（async→queued，sync→success+内联 resultInline）、文档状态联动（PARSING→SUCCEEDED/FAILED，写回 DocumentStore）。
   - `ParseService.query_parse_result`：文档存在/范围校验、无 parse 记录 → 200003、返回 parseStatus/resultFormat/pageCount/chunkCount/failedReason。
   - `ParseService.issue_download_ticket`：文档存在/范围校验、最近成功任务（无则 200003）、签发短期凭证（ticket + expireAt + downloadPath）。
   - `ParseService.download_parse_result`：凭证校验（无效/过期 → 200004）、文档/任务匹配校验、返回统一 JSON 体（占位阶段，data 含 downloadPath 与说明；真实结果存储落地后改 StreamingResponse 文件流）。
   - 路由接入 `authorize_or_raise(action="parse"/"read", resource_type="parse"/"document", resource_id=doc_id/kb_id, context)`。

4. **测试**（`tests/test_parse.py`）
   - parse 成功（async queued / sync success+resultInline）、文档不存在 100404、个人库越权 100403、幂等复用、PARSING 中 200003。
   - query 成功、无解析记录 200003。
   - ticket 签发成功、下载成功、凭证无效/过期 200004。
   - AUTHZ：reader 拒绝、admin 放行。

### 约束（AGENTS.md §11）

- 不扩大能力面：解析域四个路由已在 catalog，不新增接口。
- 统一响应体 errCode/errMsg/data/traceId 不可拆；download 占位阶段也返回 JSON 体。
- 改路由必改 catalog（本任务不改路由形状，catalog 已含四路由）。
- 错误码进 registry：`error_code_catalog()` 聚合 `ParseErrorCodes`。
- 中文注释与文案，`from __future__ import annotations` 文件首行。

### 验收标准

- [x] 全量测试通过：**104 passed**（原 89 + 解析域 15）
- [x] `/api/error-codes` 可见 200003 / 200004 / 200011（实测确认）
- [x] 四路由实测：parse / query / issue-download-ticket / download 均统一体返回；sync 全链路 `000000` 且 traceId 回写
- [x] 更新 `docs/worklog.md`（2026-08-05 条目）

### 完成摘要

- 新增 `app/services/parse_store.py`、`app/schemas/parse.py`、`tests/test_parse.py`、`goals/parse-goal.md`
- 改写 `app/services/parse.py`（真实实现）、`app/routers/parse.py`（AUTHZ 接入）、`app/services/document_store.py`（新增 update_status）
- `app/core/error_codes.py` 新增 `ParseErrorCodes`（200003/200004/200011）；`app/core/responses.py` 解析域响应构造收敛
- 决策：download 占位阶段返回统一 JSON 体（真实结果存储落地后改 StreamingResponse）；200001 保持知识库 CREATE_FAILED 归属不动
