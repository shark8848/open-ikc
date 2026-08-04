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

### 问题 / 已知不一致

- 项目 `.venv` 未安装 pytest/httpx，测试须用 `/home/ikc-log-center/.venv/bin/python -m pytest tests` 运行。
- starlette `TestClient` 提示 httpx 已废弃、建议 httpx2（环境告警，未处理）。

### 下一步

- 待定：开始四类业务能力的首个真实实现（如知识库 create/update 落地）。按契约先读 V2 精简方案确认语义，缺少决策时询问用户，不擅自定外部 API 形状。
