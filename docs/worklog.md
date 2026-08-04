# 工作日志（Worklog）

> 用途：记录每次/每天的任务完成情况、进展、问题与总结；**每天开工前先读最近条目继承上下文**。
> 约定见 `AGENTS.md`「工作日志与每日继承」章节。按日期追加，每天一个条目。
> 每个工作日 `17:30` 触发例行提交任务（约定见 `AGENTS.md` §8.1）。

## 2026-08-04

### 任务：仓库梳理 + 进行中改动收尾 + 契约建设

- 完成：确认并推进工作区进行中改动（`authz/adapters.py` 身份字段兜底、`middlewares.py` 系统路由免鉴权）。
- 完成：新增 `tests/test_authz_adapters.py`（12 例）与 `tests/test_auth_middleware.py`（5 例 + 8 个参数化路径）；`_pick_identity_value` 增加空值（含空列表/集合）兜底；全量测试 **25 passed**。
- 完成：创建 `AGENTS.md` 项目实现契约，`CLAUDE.md` 收敛为 `@AGENTS.md` 导入入口（Codex / Claude Code 共用）。
- 完成：契约新增「Token 效率与协作约定」与「工作日志与每日继承」章节；新建本日志文件。
- 完成：契约新增 §8.1「每日 17:30 例行提交」；当天改动按约定提交并推送到 `github` 远端。
- 完成：统一 `catalog.py` 文档查询路径 `{docId}` → `{doc_id}`（与路由一致）。
- 完成：新增 `tests/test_authz_policy.py`（14 例），覆盖资源 ID 白/黑名单、`kb_ids` 上下文、owner-only、org 路径前缀、部门、租户与 required_role 条件；全量测试 **39 passed**。

### 任务：知识库 create/update 首个真实实现落地

- 完成：新增 `app/services/knowledge_base_store.py`（进程内线程安全存储 + 唯一键冲突判定，`kb_`+17 位数字 ID）。
- 完成：`KnowledgeBaseService.create/update/get_or_raise` 真实业务逻辑：同范围 `kbName` 重复 `100409`、更新不存在 `100404`、个人库仅创建者可改 `100403`、企业库组织识别（orgId 优先，其次租户）失败 `100403`、元数据字段名去重 `100001`。
- 完成：`responses.py` 改为基于存储记录构造响应（真实 kbId 与 UTC 时间戳），移除硬编码占位。
- 完成：`routers/knowledge_base.py` 接入 `authorize_or_raise`（create/update + `kb_id/kb_type/owner_id/org_path` 数据上下文）。
- 完成：新增 `tests/test_knowledge_base.py`（16 例）；`test_auth_middleware.py` 补 store 复位 fixture；全量测试 **55 passed**。

### 问题 / 已知不一致

- **环境问题**：沙箱内 asyncio 跨线程唤醒失效（`call_soon_threadsafe` 无法唤醒其他线程的事件循环），导致 `TestClient` 死锁，pytest 在沙箱内无法运行；需在沙箱外（escalated）执行测试。本地 `.venv` 已装 `httpx2` 但缺 pytest，测试仍用 `/home/ikc-log-center/.venv/bin/python -m pytest tests` 运行（starlette TestClient 的 httpx 废弃告警为环境告警，未处理）。
- team 库成员关系校验依赖外部团队系统，当前占位未实现（依赖 AUTHZ 或后续接入）。

### 下一步

- 待定：文档域真实实现（如 ingest / 文档查询落地），按契约先读 V2 精简方案确认语义。
- 待定：知识库内存存储替换为真实持久化（DB）时的迁移点已收敛在 `app/services/knowledge_base_store.py`。
