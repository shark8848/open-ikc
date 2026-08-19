我在 plan 模式下无法写文件，直接输出报告如下。

---

# 代码审查：Docker 构建脚本 + HAProxy 代理层（2026-08-19）

- **审查对象**：未提交工作区改动（`README.md`、`docs/worklog.md`、`process.md` + 未跟踪的 `.dockerignore`、`Dockerfile`、`docker-compose.yml`、`docker/haproxy.cfg`、`docker/haproxy/`、`docker/wheels/`、`scripts/build_docker.sh`、`.vscode/settings.json`）
- **审查方式**：只读审查，未修改任何文件
- **已执行验证**：`bash -n` 三个脚本 OK；`docker compose config` 解析 OK（结构、端口、卷、healthcheck、depends_on 正确）；运行时依赖逐个核对（`security.py` / `middlewares.py` / `authz/bridge.py` / `services/search.py` / `services/upload.py` / `api_manual.py` / `token_store.py`）。docker 守护进程沙箱内不可达，镜像构建与 HAProxy 运行期行为未实测（worklog 已注明）。

## 结论

方案结构清晰、文档与代码一致性较好。但存在 **3 个 P1**（1 个数据泄露面、1 个授权绕过配置缺陷、1 个功能缺失）与若干 P2，建议修复后合并。

---

## P1 问题

### P1-1 默认 `static` 认证模式下，客户端可伪造身份头访问他人个人知识库 / 暂存文件

- **位置**：`docker-compose.yml:25`（`OPEN_PLATFORM_AUTH_MODE: static`）+ `app/core/security.py:141-150`
- **依据**：
  - compose 默认 `OPEN_PLATFORM_AUTH_MODE=static`、`OPEN_PLATFORM_TOKEN=test-token`（README 公开），对外 18080 部署即默认此配置。
  - `security.py:141-150` static 模式**仅校验 Bearer token**，`identity/permissions` 全部取自请求头（`security.py:207-226`：`X-User-Id`/`X-Tenant-Id`/`X-User-Roles`/`X-User-Permissions`），`request.state.identity` 随之被填充。
  - 数据权限收敛**直接信任该身份**：`services/search.py:105-128`（personal 库按 `owner_id != user_id` 拒绝、enterprise 按 `orgId/tenant_id` 拒绝）、`services/upload.py:get_staged_file`（暂存文件 `record.owner_id != owner_id` 拒绝）、`services/knowledge_base.py:180,202-203`。
  - **攻击路径**：拿到 `test-token` 的客户端 `curl -H "X-User-Id: victim" -H "Authorization: Bearer test-token" .../knowledge-search/universal-search` 即可检索 victim 的个人知识库；`X-Tenant-Id` 可穿透 enterprise 范围；`X-User-Roles`/`X-User-Permissions` 可伪造角色直接命中 AUTHZ deny-overrides 白名单。
- **修复建议**：
  1. `docker/haproxy.cfg:54-60` 的「剥离/注入身份头」规则目前**整段注释**——这是 HAProxy 代理层的核心安全职责，gateway_header 模式下应默认启用而非注释。
  2. **static 模式**（身份无可信来源）应在 HAProxy 入口无条件 `http-request del-header X-User-Id X-Tenant-Id ...`，使 owner 校验退化为「空身份 → 拒绝」，而非「客户端自报身份」。
  3. 生产默认值建议改为 `gateway_header` + `OPEN_PLATFORM_GATEWAY_REQUIRE_BEARER=true`，或至少 static 模式默认剥离身份头。

> 性质说明：这是**默认部署即存在**的数据越权面。README 措辞为"生产建议改强认证"，但默认值把风险前置，文档与默认配置存在落差。

### P1-2 `.dockerignore` 排除 `docs/`，`/api-manual` 在容器内失效（免检端点留空壳）

- **位置**：`.dockerignore:15`（`docs`）+ `app/core/api_manual.py:11,103,107-110`
- **依据**：`api_manual.py:11` 运行时读取 `.../docs/API开发手册.md`；`/api-manual` 注册于 `system_routes.py:34` 且列于 `middlewares.py:22` `AUTH_EXEMPT_PATHS`（对外免鉴权）。`.dockerignore:15` 排除 `docs` → 容器内 `_MANUAL_PATH.exists()` 为 False → 返回「开发手册缺失」占位页。`docs` 是**运行时功能依赖**，非纯文档。
- **修复建议**：从 `.dockerignore` 移除 `docs`（或仅排除非 `.md` 产物）；若刻意不带手册，应同步删除该免检路由与 catalog 条目，避免留空壳端点。

### P1-3 现场构建 wheel 用 `git archive v1.4.9`，tag 缺失时报错不友好且 `web/dist` 取工作树（含未提交产物）

- **位置**：`scripts/build_docker.sh:64`
- **依据**：worklog 已记录 `v1.4.9` tag 存在、构建已成功（`docker/wheels/ikc_log_center-1.4.9-py3-none-any.whl`，1,088,263 字节，sha256 与手测一致）。但 tag 缺失时 `git archive` 以非零退出，错误信息不含指引；`git archive` 不包含未提交/未跟踪文件，`web/dist` 用 `cp -r` 覆盖自当前工作树，若上游该产物未提交则产出残缺 UI。
- **修复建议**：`git archive` 前先 `git -C "$LOG_CENTER_REPO" rev-parse --verify "v${VERSION}"` 校验 tag 并给出明确报错。

---

## P2 问题

| # | 位置 | 问题 | 建议 |
| --- | --- | --- | --- |
| P2-1 | `docker/haproxy.cfg:59-60` vs `app/core/security.py:208-213` | 注释示例注入 `x-auth-user-id`/`x-auth-tenant-id`，与平台默认头名 `X-User-Id`/`X-Tenant-Id` 不一致，照抄启用会认证失败/拒绝 | 注释与默认头名对齐，或注明需同步设置 `OPEN_PLATFORM_AUTH_HEADER_USER_ID` 等 |
| P2-2 | `docker-compose.yml:39` | `LOG_CENTER_URL=http://log-center:9315` 指向栈内不存在的服务，置 `LOG_CENTER_ENABLE=true` 即悬空投递 | 默认值改空或 `127.0.0.1:9315`，README 注明需先部署日志中心 |
| P2-3 | `docker/haproxy.cfg:50` vs `docker-compose.yml:48-53` | HAProxy `check inter 3s` 探测后端默认 `GET /`（返回 302），compose healthcheck 探 `/health`（每 10s），路径与阈值不一致，启动期易误判 | `server app` 加 `httpchk GET /health`，统一探测路径 |
| P2-4 | `docker-compose.yml:12,55-71` | `backend server app app:18000` 依赖默认网络 DNS；用户后续自定义网络会解析失败 | 属加固建议，显式声明网络/别名 |
| P2-5 | `docker/wheels/*.whl` | 1MB 构建产物 wheel（内嵌 web/dist）当前未在 `.gitignore`，`git add .` 会被提交进历史 | `docker/wheels/*.whl` 加入 `.gitignore`，保留 `.gitkeep` |
| P2-6 | `Dockerfile:33` | `pip install .` 对 `fastapi>=0.115,<1.0` 等范围依赖无锁定，构建不可复现 | 低优先级；如需可复现构建引入 `requirements.lock` |
| P2-7 | `README.md:§1.5` vs `docker-compose.yml:25` | README 建议生产改 `gateway_header`，默认仍 `static` | 提供生产 `.env.example` 模板，默认即强认证 |

---

## 已核验的低风险项

- `docker compose config` 解析通过；端口映射、卷、healthcheck、`depends_on` 结构正确。
- `build_docker.sh` 的 `sed` 版本解析与 `pyproject.toml:19` 一致；`--wheel-only`/`--no-cache` 分支正确。
- `haproxy-entrypoint.sh` 用 `envsubst` 限定变量集（`${HAPROXY_STATS_USER}` `${HAPROXY_STATS_PASSWORD}`），不会误替换其他 `${}`；以非 root `haproxy` 用户启动，最小权限正确。
- HAProxy stats 需认证、`hide-version` 开启、默认密码 `change-me` 已在文档警示。
- 安全响应头（nosniff / X-Frame-Options / Referrer-Policy）设置正确。
- `Dockerfile` 多阶段构建：非 root（uid 1000）、`/app` 属主、`data/logs` 挂卷、wheel 缺失时构建期显式报错（而非静默）均正确。
- `TraceMiddleware`、`AUTH_EXEMPT_*`、AUTHZ deny-overrides 决策引擎未受本次改动影响；P1-1 根因在**身份来源（请求头）**而非 AUTHZ 引擎本身。

## 修复优先级

| 级别 | 项 | 动作 |
| --- | --- | --- |
| P1 | static 模式身份头可伪造 | compose 默认剥离身份头 + gateway_header 默认启用注入规则 + README 同步 |
| P1 | `.dockerignore` 排除 `docs` 使 `/api-manual` 失效 | 移除排除项或删除免检路由 |
| P1 | wheel 构建 tag 校验 | 前置 `git rev-parse --verify` |
| P2 | 头名不一致 / LOG_CENTER_URL 悬空 / healthcheck 路径不一 | 逐一对齐 |

---

需要我把这份报告落到 `docs/code-review_2026-08-19_docker.md` 吗？（当前 plan 模式无法写文件，退出后可以。）
