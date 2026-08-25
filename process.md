# process.md — 当前未完成事项（待办清单）

> 本文档是**未完成/待办事项清单**（工作流交接载体），与 `docs/worklog.md`（流水日志）互补：
> - **开始任务前**：先读本文档 + `docs/worklog.md` 最近条目，继承待办与上下文；
> - **任务完成/收尾时**：更新本文档——已闭环的项删除（或移入 worklog 完成记录），新发现的未完成项登记。
> 优先级：P0 阻塞 / P1 高 / P2 中 / P3 低。格式：`状态 | 优先级 | 事项 | 下一步`。

## 1. 平台能力（按方案分期）

| 状态 | 优先级 | 事项 | 下一步 |
| --- | --- | --- | --- |
| 待评审 | P1 | **P4 检索消费侧**：wiki 页面粒度检索（`universal-search` 扩展 `searchMode=page`，可选沿 wiki-link 扩展候选）+ 图谱多跳检索；检索按库形态（text/wiki/graph）路由 | 依赖真实检索后端（`ur`/`openai`）；评审 `docs/知识加工形态优化方案_wiki图谱与解析.md` §8 后实施 |
| 待落地 | P1 | **真实解析/抽取引擎接入**：`parse` 占位结果（`_simulate_file_data`）、wiki 占位正文（`build_document_pages`）、graph 占位单实体（`build_document_graph`）→ 替换为真实引擎输出（分块/切页/实体关系抽取） | 接入解析引擎后替换占位；同步升级 `parse-result/download` 产物流 |
| 待落地 | P1 | **async 任务后台执行器**：`executeMode=async` 目前只登记 `queued`，无后台 worker 执行；专业库 async 建页/建图未执行 | 落地任务队列/worker；async 完成后更新任务状态与库资产 |
| 待落地 | P2 | **parse-direct 的 productType**：方案 §4.2 的免库 `productType=wiki|graph` 一次性加工（图谱仅 `graphScope=doc`）未实现，`ParseDirectRequest` 无该字段 | 评审后加字段 + 校验（跨形态拒绝 100001） |
| 待落地 | P2 | **download 真实产物流**：`parse-result/download` 当前返回 JSON 壳元数据；需升级为真实产物流（text/markdown/json；wiki 页面 jsonl；图谱 nodes/edges jsonl）；`graph/export` 下载凭证链路待统一（当前内联返回） | 与 §1-2 引擎接入一并落地 |

## 2. 已知问题 / 环境遗留

| 状态 | 优先级 | 事项 | 下一步 |
| --- | --- | --- | --- |
| 未闭环 | P1 | **owner_id/org_path 授权上下文语义**：wiki/graph/kb 路由把库主（record.owner_id）当 `owner_id` 上下文传入，与 AGENTS.md §4.2「owner_id 一律取认证身份」冲突，owner-only 数据权限不可用 | AUTHZ 上下文区分 `owner_id`（认证身份）/ `data_owner_id`（库归属），桥接层与路由统一修正（2026-08-24 审查 P1-1） |
| 未闭环 | P1 | **`unavailable` 鸭子类型回退脆弱**：`KnowledgeBaseException` 带 `unavailable` 属性被引擎回退逻辑扫描，映射错误码抛的普通异常会被误吞/误透 | 设独立 `EngineUnavailable` 异常类精确捕获（2026-08-24 审查 P1-2） |
| 未闭环 | P2 | **AUTHZ role→action 映射缺 `knowledge_base:read/write`**：digital_employee 默认映射下 wiki 只读路由必然 100403 | `km_reader` 角色补映射 + 文档（2026-08-24 审查 P2-1） |
| 未闭环 | P2 | **async 解析引擎联动缺口**：引擎启用时直接返回 QUEUED，无引擎任务 ID、无异步任务查询接口 | 明确 P2-2 async 引擎联动闭环或回退占位（2026-08-24 审查 P2-2） |
| 未闭环 | P2 | **`ensure_wiki` 乐观创建并发竞态** + `_request` 对 HTTP 4xx 无业务码时无统一错误映射 | 幂等化创建 + 4xx 映射（2026-08-24 审查 P2-3） |
| 环境 | P2 | **docker.io registry 不可达**：`node:22-alpine` 拉取超时（registry-1.docker.io 被网关拦截），镜像重建受阻 | 网络恢复后 `bash scripts/build_docker.sh --no-save` 重建，使 entrypoint 日志中心预检（`LOG_CENTER_ENABLE=true` 时 fail-fast）进入正式镜像（2026-08-25） |
| 环境 | P2 | **origin（code.tiancloud.com）网络不可达**：22/443 SSH 与 HTTPS 均被代理网关拦截（198.18.0.91），`git fetch/push origin` 无法执行，双远端同步受阻 | 网络恢复后执行 `git push origin main` 补推 `297fb39..ca1855f` |
| 未闭环 | P2 | **空字符串 `kbName` 未做非空校验**：`POST /knowledge-bases/create` 传 `kbName=""` 可创建空名库（conformance finding） | 补服务端非空校验（100001）或手册明确限制 |
| 未闭环 | P2 | **Java SDK 未同步 wiki/graph**：`sdk/java` 仅基础四类能力，未封装 wiki 三方法与 graph 五方法（Python SDK 已 24 工具/命令） | 按 `sdk/python` 模式补齐 Java 客户端 + 测试 |
| 待更新 | P3 | **在线测试 E2E 基线**：`/tmp/mcp_cli_e2e.py`（35/35）未随 wiki/graph 扩展；下次全量 E2E 需覆盖 24 工具/命令 | 运行前更新脚本枚举并重跑 |
| 环境 | P2 | **18000 用户侧实例**：`scripts/start_open_platform.sh` 实例使用随机 admin token 且未配置业务 token（`OPEN_PLATFORM_TOKEN`），在线测试曾因 token 错位失败 | 用户侧以「业务 token + `OPEN_PLATFORM_ADMIN_TOKEN=test-admin-token`」重启 18000 |
| 环境 | P3 | **冒烟实例端口管理**：临时 E2E 使用 18001，需确保无遗留进程占用（本次已清理 P2 遗留实例） | 启动前检查 `ss -ltn | grep 18001` |

## 3. 待产品决策

| 状态 | 优先级 | 事项 | 下一步 |
| --- | --- | --- | --- |
| 待确认 | P1 | **图谱 LLM 成本与开关**：`identityResolution=fuzzy` / `extraction=llm` 依赖 LLM，成本与启用策略需产品确认 | 方案 §6.3 参数落地前确认默认值与配额 |
| 待确认 | P2 | **图谱域边界**：图谱是否作为独立能力域 vs 知识库形态（当前按「专业库形态」实现） | 保持现状，产品侧确认后调整 |

## 4. 快速状态

- 已落地：P1 kbMode 形态协议（text/wiki/graph）；Docker 构建脚本（`scripts/build_docker.sh`）+ HAProxy 代理层（`docker/haproxy.cfg`、`docker-compose.yml`，对外 18080）；P2 Wiki 库（页面树/检索/parse 联动）；P3 图谱库（stat/nodes/edges/neighbors/export + parse 联动）；Python SDK/MCP/CLI 24 工具/命令全覆盖；文档上传 7 天暂存；在线测试模块。
- 已落地：reDocs 与 Swagger 定义对齐（ReDoc 侧边栏开启 `schemaDefinitionsTagName=Schemas` 分组，与 Swagger Models 目录一致；2026-08-24）。
- 文档权威顺序：`AGENTS.md` > 当前代码 > `docs/开放平台接口整体方案_V2_精简.md` + `docs/开放平台接口详细定义_精简版_V2.md` > 本文档与 worklog。
