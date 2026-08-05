核对完毕。以下是审查报告。

---

# open-ikc 代码与安全审查报告（只读）

**审查范围**：未提交工作区改动 + 未跟踪文件（`AGENTS.md`、`README.md`、`app/routers/document.py:82`、`scripts/review_with_claude.sh`、`goals/*`、`docs/code-review_2026-08-05.md[.err]`、`.claude/worktrees/security-fix-document-parse/`）

## 结论

本次改动实质是一个 **AUTHZ 一致性修正**（`document.py:82` 的 `resource_id="*"` → `payload.kbId`）+ 自动审查机制落地（§13 契约 + 审查脚本 + README 说明）。核心结论：**修正本身在策略引擎下是安全的、无越权回归**，但因 `MappingAuthzAdapter` 固定生成 `resource_id="*"` 的事实，该改动在当前内置映射下是**功能等价**的，更多是表达意图与防未来回归。未发现 P0/P1 级漏洞，有 3 项 P2 建议。另有两处**工程产物问题**（空审查报告残留、worktree 遗留）需处理。

---

## 问题列表

### P1（无）

### P2-1 — `resource_id` 语义在 document 与 parse 两域不一致（意图混淆）
**位置**：`app/routers/document.py:82` vs `app/routers/parse.py:57,75,93,115`

**依据**：本改动把复合操作 `ingest-and-parse` 的 `parse` 授权 `resource_id` 从 `"*"` 改为 `payload.kbId`（知识库 ID）。但同一资源类型 `parse` 的**其他四个路由全部用 `payload.docId`/`doc_id`（文档 ID）作 `resource_id`**（`parse.py:57,75,93,115`，对应文档域 `parse:write/read`）。

**影响分析**（已核对 `app/core/authz/policy.py:57` 与 `adapters.py:125`）：`MappingAuthzAdapter._permission_to_fact` 生成的 PermissionFact 恒为 `resource_id="*"`；`PolicyEngine._matches` 中 `fact.resource_id not in {"*", request.resource_id}` 恒为 False，**request.resource_id 实际不参与决策**。故此处不一致**当前无功能影响**（这正是为什么没有回归），但：
- 若未来在 `conditions` 里启用 `allowed_resource_ids`/`denied_resource_ids` 数据范围（`policy.py:87-103`），`ingest-and-parse` 的 parse 授权会被解释为「对知识库 ID 的资源范围」，而 parse 域其余路由解释为「对文档 ID」——同一 `parse` 类型两种 ID 语义，数据权限将错乱。
- goals 文档 `parse-goal.md:32` 明确写着「`authorize_or_raise(action="parse"/"read", resource_type="parse"/"document", resource_id=doc_id/kb_id)`」，说明作者对两种 ID 是有区分的，但 `ingest-and-parse` 改动后语义变得模糊。

**修复建议**：统一 `parse` 域的 `resource_id` 语义。`ingest-and-parse` 的 parse 授权应改为 `resource_id=payload.docId`（文档 ID，与 `parse.py` 一致），或在 `context` 中显式携带 `kb_id` 并保持 `resource_id=payload.kbId` 的同时，在 `parse.py` 四个路由同步为 kb 语义——**二者选一，保持一致并补注释说明 ID 语义**。当前改动的价值（消除 `"*"` 通配）应保留。

### P2-2 — 安全收益受限于适配器实现，建议补「资源级限制」测试固化语义
**位置**：`app/core/authz/adapters.py:114-127`、`app/core/authz/runtime.py:56-87`、`tests/test_document.py:297-316`

**依据**：改动把 `resource_id` 从 `"*"` 收紧为真实 kbId，意图是收紧授权范围。但如前所述，内置 `default`/`digital_employee` 适配器的映射事实恒为 `resource_id="*"`，`policy.py` 的资源白名单/黑名单/`owner_only` 数据范围在 `conditions` 缺省时不生效。即：**当前改动不能拦截任何「资源级越权」**（如用户 A 用 `document:write` 写用户 B 的库），数据范围收敛实际由 `DocumentService`/`ParseService` 内的业务校验承担。改动本身没有引入风险，但期望的「AUTHZ 资源边界」目前并未被策略引擎执行。

**建议**：要么在 goals/worklog 中明确「资源级授权为未来能力，当前数据范围由 service 业务校验收敛」；要么补一个测试：`_permission_to_fact` 生成的事实 `resource_id` 恒为 `"*"`，即使 `resource_id=kbId` 传入也匹配——固化当前行为，防止后续误以为 AUTHZ 已做资源级隔离。`tests/test_authz_policy.py:78-114` 已覆盖白/黑名单逻辑本身，但未覆盖「适配器产物 resource_id=* 导致 request.resource_id 被忽略」这条链路。

### P2-3 — 空报告与 .err 残留文件、worktree 遗留
**位置**：`docs/code-review_2026-08-05.md`（0 字节）、`docs/code-review_2026-08-05.md.err`（0 字节）、`.claude/worktrees/security-fix-document-parse/`

**依据**：
- 两个报告文件均为空（0 字节）。审查脚本 `review_with_claude.sh:87-90` 规定「报告为空（claude 无输出）时中止并报错」——本次运行显然是脚本**失败后留下的空占位文件**（`.err` 应报错却被置空，或调用未产生输出）。空文件既不能证明「无问题」，也不应提交。
- `.claude/worktrees/security-fix-document-parse/` 是一个与 main 严重脱节的旧 worktree（`git diff main` 显示 71 文件、8578 行删除，版本停留在初始 scaffold 时代）。它被 `git ls-files --others` 列为未跟踪，审查脚本会将其纳入范围造成干扰，且属于废弃产物。

**建议**：删除空报告与 `.err`（或确认失败原因后重跑生成有效报告）；清理废弃 worktree。若脚本在 claude 调用失败时能主动 `rm` 掉半成品空文件，则不会再有这类残留（可视为脚本增强项，P2）。

### P2-4 — schema 与实现细节（低危）
**位置**：`app/schemas/document.py:44-52`、`app/services/document.py`、`tests/test_document.py:318-326`

**依据**：
- `DocumentIngestAndParseRequest` 的 `parseStrategy`/`resultFormat` 为裸 `dict`（`document.py` 对应 schema `parseStrategy: dict`、`resultFormat: dict`），无内部结构校验；`test_ingest_and_parse_rejects_invalid_doc_type` 依赖 service 层 `100001` 兜底。`parseStrategy={"docType":"exe"}` 这类无效值能进到 service 才被拒——校验偏晚，但服务层有兜底，不构成越权或注入风险（process内解析，无真实执行）。
- `tags: list[str]` 与 `metadata: dict` 未设长度/键数上限，进程内存储场景下超长输入可造成内存放大，属低危 DoS 面，占位阶段可不处理。

**建议**：P2 记入待办即可；若解析策略白名单在服务层已枚举校验，可考虑把 `parseStrategy` 建模为 `Literal`/受限模型以提前校验。

---

## 未发现问题的方面（核对记录）

| 要点 | 结论 |
| --- | --- |
| AUTHZ action/资源类型 | `ingest-and-parse` 双重授权 `document:write` + `parse:write` 与 `runtime.py:84` 的 `de_km_operator` 映射一致；`km_admin` 通配放行；`ingest` 保持单 `document:write`。无遗漏/多余 |
| 统一响应体与异常链路 | 授权失败走 `bridge.require_allowed` → `AppException(FORBIDDEN)` → 全局处理器 → `100403` 统一体 + traceId；符合 `AGENTS.md §3.3/3.4`，未绕异常体系 |
| 认证/凭证 | 本次改动未触碰 AUTHN；download ticket 机制（`parse_store.py` 签发/过期/无效 `200004`）不属于本次 diff，未发现新凭证暴露面 |
| schema 数据边界 | `kbId` 为必填 `Field(...)`，授权调用点发生在参数校验之后，无「未校验值进入授权」路径 |
| 测试覆盖 | `test_authz_ingest_and_parse_allowed_for_operator`（`tests/test_document.py:297`）完整覆盖复合操作放行路径（de_km_operator 同时具备 `document:write`+`parse:write`），本次改动通过该测试且不改变其预期；deny 路径由 `test_authz_policy.py` 兜底 |

## 下一步建议
1. 保留 `document.py:82` 的收紧（消除通配表达意图）；决定 P2-1 的 ID 语义统一方案后同步调整 `parse.py` 或 `document.py` 并补注释。
2. 清理空报告与 worktree 残留；完善 `review_with_claude.sh` 失败时清理半成品输出。
3. 将 P2-2/P2-4 记入 `goals/` 或 worklog 待办，无需阻塞提交。
