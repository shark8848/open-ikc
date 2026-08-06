# Goals

## 文档域真实实现（ingest / ingest-and-parse / 查询文档信息）

**状态**: 已完成 ✅
**创建日期**: 2026-08-04
**完成日期**: 2026-08-04

### 目标

将 `app/routers/document.py` 与 `app/services/document.py` 中三个占位接口（`501001`）落地为真实实现，对齐 V2 精简方案与详细定义 B-01 / B-06 / B-07，并接入 AUTHZ。

### 任务分解

1. **store**（`app/services/document_store.py`）— 已就绪
   - `DocumentRecord` frozen dataclass、`DocumentStore`（create/get/list_by_kb/get_by_ingest_task/reset）、`generate_doc_id`/`generate_ingest_task_id`（`doc_`/`ing_` + 17 位数字）、`DOCUMENT_STATUS` 常量、`make_record` 工厂、`StoreConflictError` 幂等冲突判定。

2. **schemas + responses + error codes**（进行中）
   - `app/schemas/document.py`：`DocumentIngestRequest` / `DocumentIngestAndParseRequest` / `DocumentSource`（url/file/directory/archive 四态 + 条件校验）/ 响应模型（统一体 traceId/errCode/errMsg/data）。
   - `app/core/error_codes.py`：新增 `DocumentErrorCodes.INGEST_FAILED = 200010`。
   - `app/core/responses.py`：新增文档响应构造。

3. **service + router + AUTHZ**（进行中）
   - `DocumentService.ingest`：知识库存在性/类型归属校验（personal 仅创建者、team 匹配 teamId、enterprise 匹配 orgId/租户）、来源校验、幂等、docTitle 推断、taskStatus=INGESTED。
   - `ingest_and_parse`：内部两阶段，返回双任务 ID，taskStatus=PARSING。
   - `get_document`：不存在 100404，数据范围收敛。
   - 路由接入 `authorize_or_raise(action=create/read, resource_type=document, resource_id=kb_id, context)`。

4. **测试**（待执行）
   - `tests/test_document.py`：接入成功/幂等/404/403/参数校验/一体化/查询文档/AUTHZ。

### 约束（AGENTS.md §11）

- 不扩大能力面：文档域三个路由已在 catalog，不新增接口。
- 统一响应体 errCode/errMsg/data/traceId 不可拆。
- 改路由必改 catalog（本任务不改路由形状，catalog 已含三路由）。
- 错误码进 registry：`error_code_catalog()` 需聚合 `DocumentErrorCodes`（当前仅聚合 Base+KnowledgeBase）。
- 中文注释与文案，`from __future__ import annotations` 文件首行。

### 验收标准

- [x] 全量测试通过：**89 passed**（原 73 + 文档域 16）
- [x] `/api/error-codes` 可见 `200010`（`DocumentErrorCodes` 已接入 `error_code_catalog`）
- [x] 三路由实测：ingest/ingest-and-parse/查询文档信息 均 `000000` 且 traceId 回写、数据正确；不存在文档 `100404`
- [x] 更新 `docs/worklog.md`（2026-08-04 条目）

### 完成摘要

- 新增 `app/services/document_store.py`、`app/schemas/document.py`、`tests/test_document.py`
- 改写 `app/services/document.py`（真实实现）、`app/routers/document.py`（AUTHZ 接入）
- 修正 `app/core/error_codes.py`（`DocumentErrorCodes` + catalog 聚合）、`README.md`（实现进度同步）
- 主线程集成修正：schemas 响应模型改统一 envelope（原扁平结构违反 §3.3）、补 `DocumentIngestAndParseResponse`、去除冗余别名
