# 工作日志（Worklog）

> 用途：记录每次/每天的任务完成情况、进展、问题与总结；**每天开工前先读最近条目继承上下文**。
> 约定见 `AGENTS.md`「工作日志与每日继承」章节。按日期追加，每天一个条目。
> 每个工作日 `17:30` 触发例行提交任务（约定见 `AGENTS.md` §8.1）。

## 2026-08-25

### 任务：向本地 ikc-log-center 镜像灌入 10 天 × 3 节点模拟测试数据

- 需求：通过测试脚本向本地镜像（容器 `ikc-log-center`，host 网络，`http://127.0.0.1:9315`，v1.4.17）生成 10 天模拟数据，含 3 个不同 IP 节点。
- 现状：仓库现有 `gen_test_logs_cross_node.py` 仅 2 节点、3.5 小时、2000 条，不满足需求。
- 改动：新增 `scripts/gen_log_center_test_data.py`（基于 cross_node 脚本扩展）：3 节点（192.168.1.15 node-A: gateway/user-service；192.168.23.10 node-B: order/payment-service；172.16.8.20 node-C: inventory/notification-service），默认最近 10 天 × 每天 5000 条 = 50000 条，跨 3 节点 trace chain，env 可配 `LOG_CENTER_URL`/`DAYS`/`DAILY_LOGS`，batch 100 走 `POST /ingest`。
- 执行：`/home/ikc-log-center/.venv/bin/python scripts/gen_log_center_test_data.py` → 50000 条全部落库（16655/16731/16614 三节点均衡）。
- 验证：`GET /api/nodes` 显示 3 个新节点且 log_count 与生成量一致；`/search?level=ERROR` 与 message 子串查询均命中新数据，trace_id/span_id/parent_id 链路完整。

### 任务：向远程日志中心（10.88.155.31）灌入近 3 天 × 3 节点模拟数据

- 需求：向 `http://10.88.155.31:9315` 写入近 3 天模拟日志，每个节点 < 500 条。
- 执行：复用 `scripts/gen_log_center_test_data.py`，`LOG_CENTER_URL=http://10.88.155.31:9315 DAYS=3 DAILY_LOGS=400` → 1200 条全部落库（node-A 383 / node-B 411 / node-C 406，均 < 500），时间 2026-08-22 14:15 ~ 2026-08-25 14:15。
- 验证：远程 `GET /api/nodes` 节点 log_count 与生成量一致；`/search?level=CRITICAL` 命中新数据。

## 2026-08-24

### 任务：检查并纠正 reDocs 与 Swagger 的定义差异（docs UI 对齐）

- 需求：用户反馈 `/docs`（Swagger）与 `/redoc`（ReDoc）的「定义」看起来不一致，要求检查并完整纠正。
- 排查结论：两个页面共用同一份 `/openapi.json`（OpenAPI 3.1.0，36 路径 / 37 操作 / 76 schema），规范内容本身无差异；差异在 UI 呈现——ReDoc 2.x 侧边栏默认只展示标签/操作，不展示 `components.schemas`，而 Swagger UI 的 Models 区会展示全部 76 个 schema（用 node vm 加载本地 ReDoc bundle 复现：`flatItems` 仅 `{tag:5, operation:37}`，无 schema 项）。
- 修复：`app/core/app_factory.py` 新增 `_redoc_html()`（与 FastAPI `get_redoc_html` 模板一致），为 `<redoc>` 元素注入 `schema-definitions-tag-name="Schemas"`。ReDoc standalone 会把元素上的 kebab-case 属性转 camelCase 作为选项（已核 bundle 内 `Qw` 实现），修复后侧边栏新增 `Schemas` 分组，`flatItems` 变为 `{tag:6, operation:37, schema:76}`，与 Swagger Models 目录完全对齐。
- 测试：`tests/test_auth_middleware.py` 新增 `test_redoc_and_swagger_share_same_openapi_and_schema_catalog`，并给既有 docs 测试补 `schema-definitions-tag-name="Schemas"` 断言；`pytest tests -q` **295 passed**（沙箱外运行；沙箱内 TestClient 的 anyio portal 跨线程调用死锁为已知环境问题，见 2026-08-19 条目）。
- 自动审查：`scripts/review_with_claude.sh` → `docs/code-review_2026-08-24.md`；redoc 对齐改动测试覆盖 ✅，P1/P2 均为**未提交的 P3 wiki/graph 存量工作**问题（owner/org_path 授权上下文、unavailable 回退、AUTHZ 映射、async 引擎联动、ensure_wiki 竞态），已登记 process.md，随 P3 收尾一并闭环，不影响本次提交。
- 下一步：提交推送（github，只含本次任务相关文件 + worklog/process + 审查报告）。

### 任务：parseStrategy/resultFormat 等对象字段补具体定义（与 source 一样可展开）

- 需求：用户反馈免知识库独立解析（`parse-direct`）的 `parseStrategy` 等对象字段没有具体定义，要求像 `source`（DocumentSource）一样定义、可展开查看。
- 基线确认：`ParseDirectRequest`/`DocumentParseRequest`/`DocumentIngestAndParseRequest` 的 `parseStrategy`/`resultFormat` 原为裸 `dict`，OpenAPI 只生成 `{type: object, additionalProperties: true}`，无 properties 无法展开；`source` 是 `$ref: DocumentSource` 可展开。
- 落地：
  - `app/schemas/parse.py` 新增三个强类型模型：`ParseStrategy`（docType/parseMethod/backend 枚举 + pageRange + chunking + enhancement）、`ChunkingConfig`（五个非负整数字段）、`ResultFormat`（type/imageEncoding 枚举 + includeLayout/includeImages），均带 description/example；三个请求模型的 `parseStrategy`/`resultFormat` 由 `dict` 改为引用新模型（`$ref` 可展开）。
  - 校验兼容：model_validator 仍调 `validate_parse_strategy`/`validate_result_format`（传 `model_dump(exclude_unset=True)`），非法枚举/页码格式仍 100001；`app/schemas/document.py` 的 ingest-and-parse 同步改。
  - 透传兼容：`ParseService.parse` 有两条调用链（路由传 Pydantic 模型 / `DocumentService` 经 `SimpleNamespace` 传 dict），services 新增 `_as_dict()` 归一 helper，`dict(payload.parseStrategy)` → `_as_dict(payload.parseStrategy)`，保证透传语义不变。
  - 透传语义补充：模型默认丢弃额外字段，与原 dict 透传不符 → `ParseStrategy`/`ResultFormat`/`ChunkingConfig` 加 `extra="allow"`，并新增未知字段透传测试锁定。
- 测试：新增 `test_parse_strategy_and_result_format_schemas_expandable`（三请求模型 `$ref` + 属性/枚举断言）与 `test_parse_strategy_unknown_fields_passed_through`（任务记录保留未知字段）；`pytest tests -q` **297 passed**（沙箱外）。
- 自动审查：claude CLI 两次失败（Execution error / 无响应）、`codex review --uncommitted` 15 分钟超时（审查 agent 沙箱内 TestClient 死锁）→ 按用户指示改用 **Codex 主线程只读审查**，结论已追加至 `docs/code-review_2026-08-24.md`（无 P0/P1；P3-1 错误文案由 Pydantic 生成、P3-2 模型约束与校验双保险，均不影响行为）。
- 下一步：提交推送（github，只含本次任务相关文件 + worklog + 审查报告）。

### 续：双远端同步确认（github 已推送，origin 网络不可达）（2026-08-24）

- `git push github main` 成功（`297fb39..ca1855f`），github 与本地 `main` 已同步。
- `origin`（code.tiancloud.com）**网络不可达**：22/443 SSH 均被代理网关关闭（`Connection closed by 198.18.0.91`），HTTPS 握手失败（curl exit 35）；`git fetch/push origin` 无法执行，`origin/main` 仍停在 `726a133`。
- 处置：已登记 process.md 环境遗留（P2），网络恢复后执行 `git push origin main` 补推 `297fb39..ca1855f`。

### 任务：构建镜像带 HAProxy 并保存到 docker/images

- 需求：构建镜像带上 HAProxy，并把构建产物保存到 `docker/images/` 下。
- 现状确认：应用镜像本就是「单容器内含 HAProxy」（Dockerfile Stage 2 安装 haproxy+gettext，`docker/haproxy.cfg` 模板 + `docker/entrypoint.sh` envsubst 渲染，容器内 HAProxy :8080/:8404 → uvicorn 127.0.0.1:18000）。
- 落地：
  - `scripts/build_docker.sh`：新增 `--no-save` 开关；构建完成后自动 `docker save <image> | gzip` 导出到 `docker/images/<镜像tag>.tar.gz`（文件名由 IMAGE_TAG 推导，如 `open-ikc-api_1.0.0.tar.gz`），并提示离线 `docker load -i` 用法；头部注释与 usage 同步。
  - `.gitignore` 加 `docker/images/`、`.dockerignore` 加 `docker/images`（镜像归档不入库/不进构建上下文）。
  - README §1.5：补充 `--no-save` 参数与构建产物导出/离线加载说明。
- 验证（沙箱外）：
  - `docker build` 成功（基础镜像已缓存，~40s）；导出 `docker/images/open-ikc-api_1.0.0.tar.gz`（97M），`gzip -t` + `docker load -i` 均通过。
  - 镜像内含 HAProxy 3.0.11、`/etc/haproxy/haproxy.cfg.tmpl`、`/usr/local/bin/open-ikc-entrypoint.sh`。
  - 端到端冒烟（compose 起停）：宿主 18082 → HAProxy :8080 → `/health` 返回统一体；stats 18404（admin/change-me）返回 Statistics 页；容器 healthcheck healthy；验证后 `docker compose down` 清理。
  - 环境遗留：`docker/images` 目录曾被残留 nobody 所有者导致导出 Permission denied，已删除重建（sharkyai 所有）；宿主 8404 被 `openwiki-server` 占用（另一系统服务，冒烟用 18404 避开，不影响默认 compose 部署仅本机需注意端口冲突）。
- 下一步：提交推送（github；origin 网络不可达待恢复后补推）。

## 2026-08-19

### 任务：Docker 构建脚本 + 前端 HAProxy 代理层

- 需求：增加构建为 Docker 的脚本；在前端（管理 Portal / 北向 API）增加一层 HAProxy 代理层组件并配置好。
- 新增 `Dockerfile`（多阶段）：Stage1 `node:22-alpine` 构建 Portal（`npm ci` + `npm run build`）→ `/portal/dist`；Stage2 `python:3.12-slim` 先装 log-center wheel 再 `pip install .`，挂载 Portal 产物，uid 1000 非 root 运行，`CMD uvicorn app.main:app :18000`。
- 新增 `docker/haproxy.cfg`：前端入口 `:80` → 后端 `app:18000`（compose 服务名，健康检查）；安全响应头；stats `:8404`（`${HAPROXY_STATS_USER/PASSWORD}` 环境变量注入）；注释提供 `gateway_header` 模式「剥离/注入身份头」规则与 TLS 透传示例。
- 新增 `docker-compose.yml`：`app`（构建镜像 + 环境变量透传 + `app_data`/`app_logs` 卷 + healthcheck）+ `haproxy`（官方 `haproxy:3.0-alpine`，对外 `18080`/stats `8404`）；生产建议 gateway_header + 改 stats 密码与平台 token。
- 新增 `scripts/build_docker.sh`（`--wheel-only` / `--no-cache`）：自动预置私有依赖 `ikc-log-center==1.4.9` wheel —— 优先 `docker/wheels/` 已有 wheel，缺失时从 `/home/ikc-log-center` 源码 tag `v1.4.9` 现场构建（UI 产物 `web/dist` 取当前工作树，因 1.4.9 源码强制 include 该产物）；随后 `docker build`。
- 新增 `.dockerignore`（排除 `.venv/`、`logs/`、`data/`、`portal/node_modules/`、`portal/dist/` 等）；`docker/wheels/.gitkeep` 占位。
- 环境遗留：`/home/ikc-log-center/dist/` 仅有 1.4.10 wheel，1.4.9 wheel 缺失 → 已由构建脚本自动补制 `docker/wheels/ikc_log_center-1.4.9-py3-none-any.whl`（v1.4.9 源码 + 当前 web/dist 覆盖构建，SDK 为 1.4.9 代码）。
- 验证：`bash -n scripts/build_docker.sh` OK；`bash scripts/build_docker.sh --wheel-only` 成功产出 1.4.9 wheel（sha256 与手测一致）；docker 守护进程沙箱内不可达（permission denied），镜像构建与 HAProxy 语法校验需沙箱外批准执行。
- 文档：README 新增 §1.5 Docker 部署（构建/启动/端口/环境变量/生产建议）与 §7 项目结构；`process.md` 登记 1.4.9 wheel 缺失环境遗留。
- 下一步：批准后执行 `docker build` + `docker compose up -d` 端到端验证（HAProxy 18080 入口 + stats 8404）；按 §8.2 提交推送。

### 续：Claude Code 只读审查 + P1/P2 闭环 + Docker 端到端验证（2026-08-19）

- 自动审查（`scripts/review_with_claude.sh` → `docs/code-review_2026-08-19.md`）发现 3 P1 / 7 P2，全部闭环：
  - P1-1 身份头可伪造：`docker/haproxy.cfg` 默认启用 `http-request del-header X-User-Id/X-Tenant-Id/X-User-Roles/X-User-Scopes/X-User-Permissions/X-User-Deny-Permissions`（客户端无法自报身份）；gateway_header 注入示例改为 `X-Auth-*` → 平台默认头名映射（与 `OPEN_PLATFORM_AUTH_HEADER_*` 对齐）。
  - P1-2 `/api-manual` 容器内失效：`.dockerignore` 移除 `docs`，`Dockerfile` 增加 `COPY docs/ ./docs/`（运行时依赖）。
  - P1-3 wheel 构建 tag 校验：`scripts/build_docker.sh` 前置 `git rev-parse --verify v<版本>`，缺失时给出明确指引。
  - P2：`option httpchk GET /health` 统一探测路径；`LOG_CENTER_URL` 默认改 `127.0.0.1:9315`（注释警示先部署日志中心）；`docker/wheels/*.whl` 入 `.gitignore`（保留 `.gitkeep`，构建脚本自动补制）；新增 `docker/.env.example` 生产模板（gateway_header + 强 token）；`pip install .` 依赖锁定列为后续 P2（沿用仓库范围依赖约定）。
- 验证（沙箱外）：
  - `pytest tests -q` **282 passed**（24s；沙箱内同套件因网络限制挂起，沙箱外正常）。
  - 整栈 `docker compose up -d` 端到端：`/health`、`/portal/`（标题 Open IKC）、`/admin/overview`（无 token 100401 / 带 token 000000）、业务 `create` 经 HAProxy 全通；`/api-manual` 返回真实手册（92KB，含快速开始/接口参考/错误排查，容器内 `/app/docs` 已打包）；stats `admin:change-me` 200；身份头剥离验证：带 `X-User-Id: attacker` 建 personal 库，详情 `ownerId` 为空。
  - 容器身份：app=uid 1000（appuser）、haproxy=uid 99（haproxy 非 root）；新 haproxy 配置（httpchk + del-header）经组件入口 `-c` 语法校验 exit=0；`docker compose config` 解析通过。
  - 镜像：`open-ikc-api:1.0.0`（多阶段构建首次成功；后续重构建因 Docker Hub `node:22-alpine` 元数据解析持续超时，用现有镜像+docs 层离线补验，网络恢复后重跑 `bash scripts/build_docker.sh` 即可刷新）；`open-ikc-haproxy:1.0.0`（envsubst 组件）正常。
- 环境备注：Docker Hub 在本次会话中网络时通时断（首次成功、后持续超时），与沙箱无关；栈已 `docker compose down`，18080/8404 端口已释放。
- 下一步：网络恢复后执行 `bash scripts/build_docker.sh` 全量重建确认；按 §8.2 提交推送。

### 续3：按要求合并为单镜像（HAProxy 与平台同容器）+ stats 凭据说明（2026-08-19）

- 需求变更：HAProxy 与 open-ikc 合并到**同一镜像**，只经 HAProxy 反向代理，平台 API 不直接暴露。
- 结构调整：
  - `Dockerfile`：runtime 阶段 `apt-get install haproxy gettext`，`COPY docker/haproxy.cfg` 为镜像内模板、`COPY docker/entrypoint.sh` 为容器入口，`EXPOSE 80 8404`（18000 不再暴露），`ENTRYPOINT` 启动双进程。
  - `docker/entrypoint.sh`（新）：envsubst 渲染 stats 凭据到 `/tmp/haproxy.cfg` → 启动 `uvicorn 127.0.0.1:18000`（仅回环）→ 就绪探测 fail-fast（超时/进程退出即容器退出重启）→ 前台运行 haproxy；默认 stats 凭据输出告警；TERM/INT 转发双进程优雅停机。
  - `docker/haproxy.cfg`：入口 `bind *:8080`（高位端口，避免非 root 绑定 80 依赖内核参数），`option forwardfor if-none`，身份头剥离默认启用；gateway_header 注入映射改为 `if { env(HAPROXY_INJECT_IDENTITY) -m str 1 }` 环境开关（默认关闭=请求按未认证拒绝）。
  - `docker-compose.yml`：单服务（无独立 haproxy 服务），`18080->8080` + `8404->8404`，healthcheck 经 HAProxy `127.0.0.1:8080/health`；升级提示 `up -d --build`；删除 `docker/haproxy/` 组件目录。
  - `docker/.env.example`：gateway_header 配置补 `HAPROXY_INJECT_IDENTITY=1` 与前置网关注入 `X-Auth-*` 要求。
  - `scripts/docker_smoke.sh`（新）：8 项冒烟断言（/health、/portal、admin 鉴权、业务 create、/api-manual、stats 默认凭据 200/错误 401、容器 IP 连 18000 拒绝、非 root uid 1000），`--force-build` 可强制重建。
- 二轮 Claude Code 只读审查（`docs/code-review_2026-08-19.md` 已更新）：发现 2 P1（gateway_header 推荐配置开箱即坏、stats 默认凭据暴露）与 6 P2，全部闭环：P1-1 用 `HAPROXY_INJECT_IDENTITY` 开关 + 文档/模板同步；P1-2 入口启动告警 + README 强提示；P2 逐一处理（8080 高位端口、`--build` 升级提示、README 目录树残留修正、冒烟脚本、入口 fail-fast、forwardfor if-none）。
- 验证（沙箱外）：镜像离线叠加层构建（Docker Hub 又超时，最终镜像与规范 Dockerfile 内容一致，网络恢复后 `bash scripts/docker_smoke.sh --force-build` 刷新）；`bash scripts/docker_smoke.sh` **8/8 PASS**；`docker compose config` 解析 OK；栈已清理、18080/8404 释放。
- HAProxy stats UI 账号：默认 `admin` / `change-me`（`HAPROXY_STATS_USER` / `HAPROXY_STATS_PASSWORD` 可改，compose 默认值见 `docker-compose.yml`，生产模板见 `docker/.env.example`）。
- 备注：工作区出现与本任务无关的并发改动（wiki 引擎接入：`app/services/openwiki_client.py`、`tests/test_wiki_engine.py` 等），本次仅提交 Docker/HAProxy 相关文件，避免混入。
- 下一步：网络恢复后全量重建；按 §8.2 提交推送。

### 续4：Docker 构建/启动内容落文档（2026-08-19）

- 新增 `docs/Docker部署与HAProxy.md`：单镜像拓扑与端口、构建（`build_docker.sh` / wheel 预置 / 多阶段）、启动/停止/升级、环境变量表、安全与生产加固（gateway_header + `HAPROXY_INJECT_IDENTITY`、身份头剥离、非 root）、常见问题（构建网络超时、旧 tag 镜像、端口占用等）。
- README：§1.5 末尾链接部署文档；§3.2 仓库文档表新增一行。
- 验证：`docs/Docker部署与HAProxy.md` 内容与当前实现一致（拓扑 8080/8404/127.0.0.1:18000、脚本名、默认凭据）；未改动代码，无需重跑测试。
- 下一步：按 §8.2 提交推送（仅文档文件，不混入并发 wiki 改动）。

### 续5：文档补充「管理账号配置」（HAProxy UI / Portal token）（2026-08-19）

- `docs/Docker部署与HAProxy.md` 新增 §5 管理账号配置：5.1 HAProxy stats UI 用户名/密码修改步骤（`.env` + `--force-recreate`，无需重建镜像，含验证命令）；5.2 管理 Portal / `/admin/*` 的 `OPEN_PLATFORM_ADMIN_TOKEN` 设置与验证；5.3 业务 API token；并明确 Portal 登录只认 `OPEN_PLATFORM_ADMIN_TOKEN`，`/admin/tokens` API token 不用于 Portal 登录；常见问题补充「改 token 后需 --force-recreate」。
- `README.md` 新增 §1.6 管理账号配置（三组凭据的 `.env` 配置与验证命令），链接部署文档。
- `.gitignore` 新增 `.env`（文档建议以 `.env` 存凭据，防止误提交真实 token）。
- 验证：凭据校验逻辑与代码一致（`app/core/admin/auth.py` 用 `secrets.compare_digest` 比对 `OPEN_PLATFORM_ADMIN_TOKEN`；`token_store` 仅用于 `/admin/tokens` CRUD）；未改代码，无需重跑测试。
- 下一步：按 §8.2 提交推送（仅文档与 .gitignore，不混入并发 wiki 改动）。

### 续6：双远端同步确认（origin 推送权限恢复）（2026-08-19）

- `git push origin main`（code.tiancloud.com）本次成功（`4d0b9e0..efa7e08`），此前 process.md 登记的「origin 推送权限失败」环境遗留已恢复，从待办清单移除。
- 当前 `github` 与 `origin` 均已同步至 `efa7e08`；工作区仍有并发 wiki 引擎改动未提交（非本任务）。
- 下一步：无（双远端已同步）。


### 任务：契约文档核查与修补（管理面入契约 + 503001 注册 + 测试约定同步）

- 背景：核查 `AGENTS.md` 契约与当前代码一致性，发现管理面（`/admin/*` + Portal）已落地（阶段 E/F）但契约完全未登记；`503001` 硬编码在 `exception_handlers.py` 未进错误码 registry；§6 测试约定过时。
- 改动：`AGENTS.md` —— §2 目录树补 `core/admin/` 五模块、`routers/admin.py`、`static/docs/`、`portal/`、`data/`；§3.2 补业务路由 `query`/`{kb_id}` 与系统路由 `/docs/oauth2-redirect`/`/_static/docs`/`/portal`，新增 §3.2.1 管理面路由清单（10 条 + 不进入 catalog 的边界声明）；§3.3 补 `503001`；§3.4 补「新错误码必进 registry」；新增 §4.3 管理面独立鉴权（`OPEN_PLATFORM_ADMIN_TOKEN`、未配置默认关闭 `503001`、与业务 AUTHN 隔离）；§6 更新 conftest 描述（`isolate_admin_db` fixture）与测试命令（`.venv/bin/python`）。
- 改动：`app/core/error_codes.py` —— 新增 `AdminErrorCodes`（`503001 管理面未启用`，level=admin），接入 `error_code_catalog()`；`exception_handlers.py` —— `AdminDisabledError` 处理器改用 `AdminErrorCodes.ADMIN_DISABLED.to_response()`，去掉硬编码字符串。
- 改动：`README.md` 模块职责补第 8 条（`app/core/admin/` 管理面）；`tests/test_system_routes.py` 补关键错误码（含 503001）注册断言。
- 验证：`pytest tests -q` **181 passed**（原 179 + 2 断言扩展）；`/api/error-codes` 含 `503001`（16 码）；未配置 `OPEN_PLATFORM_ADMIN_TOKEN` 时 `/admin/overview` 返回 HTTP 503 + `errCode=503001` + 23 位 traceId。
- 下一步：契约与实现已对齐；待用户确认后按 §8.1 提交。

### 任务：契约新增两条基础约定（日志中心基础化 + 任务完成自动推送）

- 背景：用户要求把「接入 ikc-log-center」与「每次任务完成自动推送仓库」写入契约。
- 改动：`AGENTS.md` —— 新增 §4.4 日志中心（ikc-log-center）基础契约（依赖只经 pyproject 声明 `ikc-log-center==1.4.9`、装配初始化 `log_center_sdk.configure` + `TraceMiddleware`、远程投递环境变量 `LOG_CENTER_ENABLE/URL/TOKEN`、新代码走 `get_logger(__name__)` 勿降级为 print/裸 logging、日志禁记密钥）；§8.1 例行提交改「commit + push」（移除「不 push」）；新增 §8.2 每次任务完成自动推送（收尾后自动 commit + push，默认 `github`，可选双远端，禁止半成品入库，用户说「不要推」时跳过）；§11-7 同步为「默认任务完成后自动 commit + push」。
- 验证：契约编辑完成，未涉及行为代码改动，无需重跑测试。
- 下一步：按 §8.2 本任务完成后自动 commit + push。

## 2026-08-10

### 任务：ikc-log-center SDK 改为 pip 安装模式接入

- 背景：`app/core/app_factory.py`、`app/core/logging.py`、`app/core/trace.py` 已 import `log_center_sdk`，但 `pyproject.toml` 未声明该依赖，接入方式不显式。
- 现状核查：open-ikc `.venv` 中 `ikc-log-center 1.4.9` 已是 pip 正常安装（site-packages，无 editable/direct_url），无 sys.path/PYTHONPATH 代码级残留；`dist/ikc_log_center-1.4.9-py3-none-any.whl` 存在于 `/home/ikc-log-center/dist/`。
- 改动：`pyproject.toml` dependencies 声明 `ikc-log-center==1.4.9`（附本地 wheel 安装命令注释）；`README.md` 启动章节补充 pip 安装说明（`pip install /home/ikc-log-center/dist/ikc_log_center-1.4.9-py3-none-any.whl`）。
- 验证：`.venv` 从本地 wheel `--force-reinstall` 重装成功且 import OK；`pytest tests -q` **179 passed** 无回归。
- 下一步：无（改动已闭环）。

### 任务：补齐 ikc-log-center 远程日志投递（集成完整性核查结论）

- 核查结论：代码层（pip 安装 + `configure` + `TraceMiddleware` + `trace.py`）已接通，但 SDK 远程投递默认关闭（`LOG_CENTER_ENABLE` 默认 false），日志仅写本地 `logs/open_ikc_api.log`，**未送达日志中心服务端**——集成不完整。
- 补充：两个启动脚本（`scripts/start_open_platform.sh`、`scripts/start_open_platform_auth_mode.sh`）导出 `LOG_CENTER_ENABLE=true`、`LOG_CENTER_URL=http://127.0.0.1:9315`（服务端 ingest 端点为 `POST /ingest`，当前未开 Bearer 认证）；`README.md` 补环境变量说明表。
- 端到端验证：临时端口实例带 env 启动 → 请求 `/api/v1/knowledge-search/query`（带 23 位 traceId）→ 日志中心 9315 `/search?trace_id=...` 命中 4 条（request start/end，logger=`app.core.app_factory`，trace 关联正确）。
- 备注：`app/core/logging.py` 的 `configure_logging()` 定义但无调用点（备用封装，app_factory 直接 `log_center_sdk.configure(...)` 遵循 env），不影响链路。

### 任务：Java SDK（阶段 F）HTTP 400 根因修复 + 文档补齐

### 任务：Java SDK（阶段 F）HTTP 400 根因修复 + 文档补齐

- 问题：Java SDK 对真实平台（uvicorn/h11，18000）调用 KB query 返回 HTTP 400，测试内本地假平台（JDK HttpServer 支持 h2c）却通过。`Smoke` 失败：`OpenIKCProtocolException: HTTP 400 且响应不符合统一响应壳协议`，原始响应 `Invalid HTTP request received.`。
- 根因：JDK `HttpClient` **默认带 HTTP/2 优先升级（h2c `Upgrade: h2c` 头）**，而 uvicorn + h11 不支持 upgrade——先收到 `Unsupported upgrade request.` 再被拒绝为 `Invalid HTTP request received.`（HTTP 400）。
- 修复：`Transport.java` 的 `HttpClient.newBuilder()` 显式固定 `.version(HttpClient.Version.HTTP_1_1)`。
- 验证：临时 `H1Probe.java` 对真实平台强制 HTTP/1.1 得 `200 / errCode=000000`；修复后 `mvn test` **24 例全绿**（4+7+13）；`Smoke` 对真实平台 `SMOKE OK`（fetchCatalog 4 类目 / fetchErrorCodes 15 码 / KB query 000000）。
- 文档：新增 `docs/开放平台JavaSDK集成设计.md`（阶段 F 交付项之一，含 §8 连接关键约定——HTTP/1.1 必选）；新增 `sdk/java/README.md`（快速开始/异常层级/冒烟/重要约定）；修正 `Smoke.java` 注释中的主类名（`io.openikc.sdk.examples.Smoke`）。
- 补充遗漏（对照计划逐项复查）：README 补 Java SDK 入口说明；`docs/MCP与CLI接口定义.md` 补 §9 管理 Portal 在线测试入口（`/admin/test/mcp|cli|whitelist`）；`OpenIKCClientTest` 新增 `doesNotSendH2CUpgradeHeader` 回归测试（14 例）——模拟 uvicorn/h11 对 `Upgrade: h2c` 返回 400，已实测移除 HTTP_1_1 后该测试会失败（回归保护有效）；`.gitignore` 补 `portal/*.tsbuildinfo`/`vite.config.js`/`vite.config.d.ts`、`sdk/java/target/`（编译产物原会误提交）；修复 `.venv` 中 mcp 被降级为 1.28.1 导致 SDK MCP 测试收集失败（升级回 mcp 2.0.0）。
- 验证：Java SDK `mvn test` **25 例全绿**（+1 回归测试）；平台 `pytest tests -q` **179 passed**；SDK `pytest sdk/python/tests -q` **130 passed**；MCP stdio 端到端冒烟全链路通过（initialize→14 tools→sys_catalog→kb_create）；admin API 冒烟（带 token `000000`，不带 `100401`，未配置时 503 映射已在 handler 确认）。
- 下一步：阶段 F 收尾提交（sdk/java + admin + portal + 相关 docs/tests + gitignore）。

### 任务：管理 Portal 前端（阶段 E）——Vite 8 + React 18 + TS 四页管理台 + 后端静态挂载

- 完成：新增 `portal/`（Vite 8.2.1 + React 18.3.1 + TypeScript 5.6，深色主题对齐 api_browser 风格）——`package.json`/`vite.config.ts`（base `/portal/`、dev proxy `/admin→127.0.0.1:18000`）/`tsconfig.json`/`index.html`。
- 完成：`src/api/client.ts`（统一响应壳解包、admin token sessionStorage 管理、错误映射）+ `src/api/types.ts`（Overview/EndpointStat/TokenRecord/TestResultData 等强类型）。
- 完成：四页 —— **Dashboard**（并发/总请求/错误率/活跃端点/活跃 token 卡片 + 最近请求表，10s 自动刷新）、**Tokens**（创建表单含过期/作用域、明文 token 一次性展示、撤销确认、含已撤销筛选）、**Endpoints**（端点维度 + token 维度统计，30/60/120 分钟窗口切换）、**TestLab**（MCP 冒烟 + CLI 白名单命令执行，公共 token/baseUrl 参数）。
- 完成：`app_factory.py` 静态挂载 `/portal`（`portal/dist` 存在时）——新增 `_mount_portal()`；`middlewares.py` 的 `AUTH_EXEMPT_PREFIXES` 增加 `/portal`（静态壳无数据，数据全走受保护 `/admin/*`）；`api_browser.py` 增加「管理 Portal」入口链接。
- 完成：`tests/conftest.py` 新增 autouse fixture 隔离 `OPEN_PLATFORM_DB_PATH`（临时 DB）——修复管理面 token/统计状态跨测试串扰（真实 DB 中已撤销 token 记录导致「未配置 token 时放行」测试误失败）。
- 修复：**MCP/CLI 在线测试事件循环死锁**——`/admin/test/mcp`、`/admin/test/cli` 为 async 路由内同步 `subprocess.run`，子进程请求平台自身端点（`/api/catalog`）时平台事件循环被阻塞 → 互相等待直至 20s 超时。改用 `starlette.concurrency.run_in_threadpool` 放线程池执行，CLI 185ms / MCP 1.4s 通过。
- 修复：`_MCP_SMOKE_SCRIPT` 中 `is_error={res.is_error}` 多余转义（raw string 双花括号不插值），修正后步骤输出 `is_error=False`。
- 验证：`npm run build` 产出 dist（index 163KB / gzip 52KB）；平台 `pytest tests -q` **179 passed**（新增 portal 免鉴权断言 + conftest 隔离）；真实服务带 `OPEN_PLATFORM_ADMIN_TOKEN` 端到端验证：overview/whitelist/token 创建→业务调用 000000→撤销→100401/列表、MCP 冒烟（initialize→14 tools→call）、CLI sys-catalog 全通。
- 说明：`/admin/*` 与 `/portal` 静态页均豁免业务 AUTHN，admin 接口由 `admin_required` 独立鉴权（未配置 `OPEN_PLATFORM_ADMIN_TOKEN` 时返回 503001）。
- 下一步：提交 A–E 阶段（admin 后端 + portal 前端 + 修复）；阶段 F Java SDK（Maven，Java 17）待开工。

### 任务：MCP 与 CLI 对外接口定义 + 落地实现（SDK 上层封装）

- 完成：新增 `sdk/python/open_ikc_sdk/_bootstrap.py`——`client_from_env` 客户端引导工厂，从环境变量读取 `OPEN_PLATFORM_BASE_URL`（默认 http://127.0.0.1:18000）/`OPEN_PLATFORM_TOKEN`/`OPEN_PLATFORM_TOKENS`（多 token 取第一个）/`OPEN_PLATFORM_USER_ID`/`OPEN_PLATFORM_TENANT_ID`/`OPEN_PLATFORM_ROLES`（组装 `CallerIdentity`），显式参数优先。
- 完成：新增 `sdk/python/open_ikc_sdk/mcp/`——基于 `mcp.server.mcpserver.MCPServer`（mcp>=2.0）实现 stdio MCP Server，14 个工具与 SDK 领域方法一一对应（kb_create/kb_update/kb_query/kb_get、doc_ingest/doc_ingest_and_parse/doc_get、parse_start/parse_query/parse_issue_ticket/parse_download、search_query、sys_catalog/sys_error_codes）；复杂结构参数（source/parseStrategy/resultFormat/metadataSchema/tags/kbIds）声明为原生 object/array 类型（mcp 2.0 按 JSON Schema 校验并反序列化）；`parse_download` 文件流落地后返回 base64 字节；`python -m open_ikc_sdk.mcp` 入口。
- 完成：新增 `sdk/python/open_ikc_sdk/cli/`——typer 实现，子命令分组（kb-create/update/list/get、doc-ingest/ingest-and-parse/get、parse-start/query/ticket/download、search-query、sys-catalog/error-codes），全局选项（--base-url/--token/--user-id/--tenant-id/--roles/--json/--debug），错误→退出码映射（100401→2/100403→3/100404→4/501001→5/传输错误→6/其他业务→1），`python -m open_ikc_sdk.cli` 入口 + pyproject `[project.scripts] ikc` 注册。
- 完成：`sdk/python/pyproject.toml` 新增 `mcp = ["mcp>=2.0"]` 与 `cli = ["typer>=0.15"]` 可选依赖（核心 SDK 仍仅依赖 httpx）。
- 测试：新增 `test_bootstrap.py`（7 例环境变量→客户端/token/身份头/透传/端到端请求头）、`test_mcp_tools.py`（18 例含 14 工具逐一 MockTransport 断言请求路径/body/返回 + 工具清单完整性，mcp 2.0 `call_tool` 异步调用）、`test_cli.py`（13 例含子命令解析/--json/表格渲染/退出码/下载落盘）；SDK 全量 **130 passed**（原 91 + 新增 38）。
- 环境：SDK 以 editable 安装进项目 `.venv`（`pip install -e "sdk/python[cli,mcp,dev]"`，mcp 2.0.0/typer 0.27.1/httpx 0.28.1/pytest 9.1.1）；发现 mcp 1.x 与 2.x 的 FastMCP/MCPServer API 不兼容，按用户决策适配 mcp 2.x（含 pyproject 依赖上修与测试重写）。
- 验证：`python -m open_ikc_sdk.cli --help`、`ikc` 入口、`python -m open_ikc_sdk.mcp` 均可用；MCP stdio 实测 initialize + tools/list（14 工具）+ tools/call 返回正常。
- 文档：新增 `docs/MCP与CLI接口定义.md`（能力映射表、环境变量、MCP 工具清单、CLI 子命令/退出码、鉴权与 AUTHZ 说明、边界）；`sdk/python/README.md` 补 MCP/CLI 使用小节。
- 边界：不新增/修改任何平台 REST 路由、`catalog.py`、`app/`（仅 SDK 侧封装）；不暴露 reindex/task query 等未落地能力；平台侧 `pytest tests -q` 146 测试不受影响。
- 下一步：真实平台服务冒烟（`python -m open_ikc_sdk.mcp` 与 CLI 命令对运行中的 18000 平台实测）；MCP 客户端（Claude Desktop 等）接入配置示例可补入 README。

### 任务：MCP 2.0 适配 + stdio 端到端冒烟 + 推送远端

- 完成：MCP 实现从 mcp 1.x `fastmcp` 适配为 **mcp 2.0 `MCPServer`**（提交 `a4574c3`）——`list_tools` 异步协程返回 `list[MCPTool]`、工具经 `call_tool` 返回 `CallToolResult`；复杂结构参数（source/parseStrategy/resultFormat/metadataSchema/tags/kbIds）声明为原生 object/array 类型；`pyproject.toml` 依赖 `mcp>=2.0`；CLI `--json` 渲染修复（`_render._as_dict()` 兜底）；平台 `pytest tests -q` 146 + SDK 130 全绿。
- 发现：mcp 2.x 协议字段为 snake_case——`InitializeResult.server_info`、`CallToolResult.is_error`（1.x/部分文档为 camelCase），冒烟脚本与测试已按 2.0 字段名适配。
- 完成：新增 `scripts/mcp_stdio_smoke.py`（提交 `dab76bd`）——以官方 mcp 2.0 `ClientSession + stdio_client` 连接 `python -m open_ikc_sdk.mcp --transport stdio`，四步全链路：`initialize（open-ikc）→ list_tools（14 工具齐全）→ call_tool(sys_catalog) → call_tool(kb_create)`，对运行中的 18000 平台实测通过（平台 AUTHN Bearer 校验、SDK token 透传链路一并验证）。
- 完成：`git push github main` 推送 `2ebf3a2..a4574c3..dab76bd`（github 远端领先 origin 4 个提交，origin 停在 b75686c，未同步）。
- 清理：冒烟创建的测试知识库为平台进程内存储，服务停止后自动消失，无持久化残留；`logs/smoke_server.log` 已删除。
- 文档：本次同步更新根 `README.md`（落地状态 + SDK/MCP/CLI 入口）、`sdk/python/README.md`（检索落地 + stdio 冒烟 + 测试命令）、`docs/开放平台SDK集成设计.md`（v1.0.0 已发布、包结构、里程碑全落地）、`docs/MCP与CLI接口定义.md`（2.0 适配要点 + 客户端接入示例 + 端到端冒烟）。
- 下一步：`origin`（code.tiancloud.com）如需同步执行 `git push origin main`（待用户确认）。

## 2026-08-05

### 任务：检索域真实实现落地（统一检索问答，四域全落地）

- 完成：新增 `app/services/search_store.py`（进程内检索索引：`SearchIndexRecord`/`SearchIndexStore` 原子读写、`index_doc` 按 doc_id 重建幂等覆盖、`search` 关键词加权打分[标题 3.0/keywords 2.0/content 1.0] + 元数据过滤 + topK 截断、轻量分词）。
- 完成：`app/schemas/search.py` 扩展——`SearchQueryRequest` 补 `teamId/orgId/mode(search|qa 默认 qa)/topK(默认 5)/filters/withCitation(默认 true)` + field_validator（mode 枚举、topK>=1）+ model_validator（kbId/kbIds 至少其一）；`SearchResultItemData` 补 `docTitle`、`SearchQueryData` 补 `total`。
- 完成：`app/core/responses.py` 新增 `search_query_response(answer/total/results)` 构造器收敛；`app/services/search.py` 占位替换——逐 kb 存在性 100404、个人库仅创建者可检索 100403、索引检索 + topK/filters/withCitation、mode=search 空 answer / mode=qa 占位 answer（引用 top1 证据，注明回答引擎落地后替换）。
- 完成：`app/routers/search.py` 保留 `action="query"` AUTHZ，补从 `request.state.identity` 取 owner_id/tenant_id 传 service（修复占位期未传身份的缺口）、注入 team_id/org_id 数据上下文、description 去掉「预占位」。
- 决策：检索索引为进程内内存模拟，真实索引引擎落地前由调用方显式注入（不随 ingest/parse 自动构建）；错误码复用公共码（100404/100403/100001），检索域不新增错误码。
- 决策：AUTHZ 语义固化——`km_reader` 含 `search:query`（只读能力读者可检索），deny 用例走 `X-User-Deny-Permissions: search:query`；reader 企业库放行测试用 enterprise + 同租户构造。
- 测试：重写 `tests/test_search.py`（2→18 例，覆盖 qa/search/topK/filters/withCitation/空结果/404/403/100001/401/AUTHZ 三态/catalog 一致性）；全量测试 **139 passed**（原 123+16）。
- 实测：TestClient 端到端冒烟——create KB → 注入索引 → query `000000`（answer 引用证据、total=1、23 位 traceId、citation 完整）、mode=search 空 answer、不存在 kb `100404`；SDK `pytest sdk/python/tests -q` **91 passed** 无回归。
- 同步：README §当前实现进度（检索占位→真实，第 7 条重写，四域全落地）；V2 详细定义附录「当前占位实现说明」收敛为仅索引 C-01/C-02 占位；SDK 集成设计 §6.4 检索目标态参数已落地标注。
- 下一步：真实检索/索引引擎落地后替换进程内关键词索引并补向量/倒排；检索自动随 ingest/parse 构建索引的联动；`goals/search-goal.md` 已建并标记完成。

### 任务：解析域真实实现落地（parse / parse-result query / download ticket / download）

- 完成：新增 `app/services/parse_store.py`（进程内存储：`ParseTaskRecord`/`ParseResultRecord`/`ParseTicketRecord`、`ParseTaskStore` 任务与结果原子读写、`ParseTicketStore` 短期凭证签发与校验、`generate_parse_task_id` `parse_`+17 位数字）。
- 完成：新增 `app/schemas/parse.py`（`DocumentParseRequest` 含 parseStrategy/resultFormat/executeMode/parseMode/chunkStrategy/chunkSize、查询/凭证/下载响应模型统一 envelope）。
- 完成：`app/core/error_codes.py` 新增 `ParseErrorCodes`——`200003 解析结果尚未就绪`、`200004 下载凭证无效或已过期`、`200011 解析失败`（200001 保留归属知识库 CREATE_FAILED，V2「解析失败 200001」按现状让位，解析域走 20001x 区间）；接入 `error_code_catalog()`。
- 完成：`app/core/responses.py` 解析域响应构造收敛（parse/query/ticket/download 四构造器）。
- 完成：`app/services/parse.py` 三占位替换为真实实现——parse 文档存在 404、个人库越权 403、幂等（queued/running/success 复用既有任务，failed 拒绝重发）、async 登记 queued、sync 请求内完成返回内联 resultInline、文档状态联动（PARSING/SUCCEEDED 写回 DocumentStore）；query 无任务 200003；issue-download-ticket 非 success 200003；download 凭证无效/不匹配 200004。
- 完成：`app/routers/parse.py` 四路由接入 `authorize_or_raise`（parse/read + `doc_id/kb_id/kb_type/owner_id/org_path` 上下文）；`app/services/document_store.py` 新增 `update_status`。
- 完成：新增 `tests/test_parse.py`（15 例，覆盖 async/sync/404/403/幂等/query/凭证签发与下载/无效凭证 200004/跨文档凭证 200004/AUTHZ/错误码注册）；全量测试 **104 passed**（原 89+15）。
- 实测：沙箱外启动 uvicorn，sync 全链路（create→ingest→parse sync→ticket→download）`000000` 且 traceId 回写；async queued 上签发凭证 `200003`、无效凭证 `200004`；`/api/error-codes` 含 200003/200004/200011。
- 同步：README §当前实现进度 增补解析域落地（第 6 条），检索仍为占位（第 7 条）。
- 决策：download 在真实结果存储落地前返回统一 JSON 体（含下载说明），后续切换 StreamingResponse 文件流；错误码 200001 不按 V2 字面重排（保持 KB 契约稳定）。
- 下一步：检索域（search/query）真实实现按同一范式推进；解析/文档/知识库存储替换真实持久化的迁移点仍收敛在各自 store。

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

### 任务：文档服务接口信息同步核查

- 完成：核查文档/解析域路由 ↔ `catalog.py` ↔ V2 方案/详细定义一致性；`/ingest`、`/ingest-and-parse`、`/parse`、`/parse-result/*` 与 `GET /{doc_id}` 均已对齐（`/openapi/v1` 为方案表述，以 `/api/v1` 实现为准）。
- 完成：补齐文档缺口——`GET /api/v1/knowledge-documents/{doc_id}`「查询文档信息」在代码/catalog 已存在但 V2 方案未收录；已在整体方案 §3.2 增补第 7 项，并在详细定义新增 B-07（标注预占位，字段契约待实现时对齐，不擅自定外部 API 形状）。

### 任务：API 文档免鉴权核查与修正

- 完成：实测 `/docs`、`/redoc`、`/openapi.json`、`/docs/oauth2-redirect`、`/api-browser` 等无 token 均可访问，主逻辑已符合「API 文档不需要 auth」。
- 修正：`app_factory.py` 调整中间件注册顺序（AuthN 内层、Trace 外层），未认证响应复用并回写调用方传入的 `X-Request-Id`/`X-Trace-Id`（契约 §3.5），未授权请求也具备完整 request start/end 链路日志。
- 修正：`middlewares.py` 免鉴权判定容忍尾斜杠（`/api-browser/`、`/health/` 等不再 401）。
- 完成：新增 3 例测试（docs 免鉴权、尾斜杠豁免、401 复用 trace 头）；全量测试 **58 passed**。

### 任务：启动服务实测验证

- 完成：沙箱外启动 `uvicorn app.main:app --host 0.0.0.0 --port 18000`（项目 `.venv`）。
- 实测：`/docs`、`/redoc`、`/openapi.json`、`/docs/oauth2-redirect`、`/api-browser`、`/api/catalog`、`/api/error-codes`、`/health` 无 token 均 200；尾斜杠变体（`/api-browser/`、`/health/`、`/docs/`）307 而非 401。
- 实测：业务路由无 token 返回 `100401`；带 Bearer 创建知识库返回 `000000`（真实 kbId），响应体与 `X-Request-Id`/`X-Trace-Id` 均回写传入 traceId `99988877766655544433321`。
- 环境备注：沙箱禁用 socket 创建且网络命名空间隔离，服务启动与 curl 验证均需在沙箱外执行。

### 任务：知识库读接口开放（列表查询 + 详情查询）

- 完成：新增 `POST /api/v1/knowledge-bases/query`（分页 + kbType/teamId/orgId/keyword 过滤）与 `GET /api/v1/knowledge-bases/{kb_id}`（详情）。
- 完成：数据范围收敛——个人库仅本人、团队库需显式 `teamId`、企业库按 `orgId` 或调用主体租户；详情个人库非创建者 `100403`、不存在 `100404`。
- 完成：两个读路由接入 `authorize_or_raise(action="read", resource_type="knowledge_base")` 与数据上下文。
- 完成：同步 `catalog.py`（知识库域 4 个路由）、V2 整体方案 §3.1（新增第 3/4 项）、详细定义 A-03/A-04、README。
- 完成：新增 12 例测试（列表空/范围/团队/企业/关键字/分页/详情/403/404/AUTHZ）；全量测试 **70 passed**。

### 任务：HTTP 状态码与 OpenAPI 文档一致性核查与修正

- 核查：运行时业务/校验错误统一 HTTP 200 + errCode（校验为 100001），符合契约统一响应体。
- 修正：`/docs` 声明 422 但实际从不返回（校验已被映射为 200/100001）——新增 `_apply_openapi_docs` 移除 422 并在 200 响应描述说明统一错误码。
- 修正：未知路由 404、方法不允许 405 原为裸 `{"detail": ...}` 且无 traceId——新增 `build_framework_error_response_middleware` 映射统一体（保留 HTTP 状态码）；新增错误码 `100405 请求方法不允许`（进 registry，/api/error-codes 自动可见）。
- 完成：新增 3 例测试（404/405 统一体、OpenAPI 无 422）；全量测试 **73 passed**。

### 问题 / 已知不一致

- **环境问题**：沙箱内 asyncio 跨线程唤醒失效（`call_soon_threadsafe` 无法唤醒其他线程的事件循环），导致 `TestClient` 死锁，pytest 在沙箱内无法运行；需在沙箱外（escalated）执行测试。本地 `.venv` 已装 `httpx2` 但缺 pytest，测试仍用 `/home/ikc-log-center/.venv/bin/python -m pytest tests` 运行（starlette TestClient 的 httpx 废弃告警为环境告警，未处理）。
- team 库成员关系校验依赖外部团队系统，当前占位未实现（依赖 AUTHZ 或后续接入）。

### 下一步

- 待定：文档域真实实现（如 ingest / 文档查询落地），按契约先读 V2 精简方案确认语义。
- 待定：知识库内存存储替换为真实持久化（DB）时的迁移点已收敛在 `app/services/knowledge_base_store.py`。

### 任务：环境修复——Claude Code 经 LiteLLM 调 deepseek-v4-flash 工具调用 400

- 现象：Claude Code 工具调用报 `400 "No tool output found for tool call call_00_..."`；后续又报 `reasoning_text in the thinking mode must be passed back to the API`。
- 根因一（No tool output）：LiteLLM 的 Anthropic→Responses 适配器把 assistant `tool_use` 转成 `function_call` 时排在 assistant 文本消息之前，导致其后的 `function_call_output` 无法与 `function_call` 相邻，DeepSeek 校验失败。
- 根因二（reasoning_text）：`deepseek-v4-flash` 无论是否传 thinking 参数都始终以 thinking 模式生成（实测响应恒含 `reasoning` item）；Claude Code 未开 thinking 时 assistant 无 thinking 块可回传，新会话（新 call_id）工具轮次必 400。
- 修复（`/home/litellm/.venv/.../responses_adapters/transformation.py`，均先备份 `transformation.py.bak.*`）：
  1. assistant 文本消息先于 `function_call` 输出，保证 `function_call → function_call_output` 相邻。
  2. `thinking` 块转成 Responses `reasoning` item（`content` 数组格式，DeepSeek 仅接受 plain-text content，不支持 summary）。
  3. deepseek 模型（model 名含 `deepseek`）的工具调用轮次若无 thinking 块，自动补占位非空 `reasoning`（内容 `...`），避免影响 grok/minimax 等其他 openai 前缀模型。
- 验证：经 proxy 全量形态 A/B/C/D + 全新 call_id（A 无 thinking、D 带 thinking）+ 两轮对话端到端，**全部 200**；`api.deepseek.com` 实际解析到本地网关 `198.18.0.19`，对 call_id 有状态记忆（旧 call_id 偶发豁免校验，新 call_id 必校验）。
- 决策：采用「无 thinking 工具轮次补占位 reasoning」而非「强制开启 thinking 让 Claude Code 回传」，因 LiteLLM 转回的 thinking block 无 signature，Claude Code 无法可靠回传。
- 下一步：如需真实思考链，可在 Claude Code 侧开启 thinking 模式（assistant 会带 thinking 块，适配器已支持转 reasoning 回传）。

### 任务：文档域真实实现落地（ingest / ingest-and-parse / 查询文档信息）

- 完成：新增 `app/services/document_store.py`（进程内文档存储：`DocumentRecord`、`DocumentStore` 原子读写、`doc_`/`ing_`+17 位数字 ID、幂等冲突判定、`DOCUMENT_STATUS` 常量）。
- 完成：新增 `app/schemas/document.py`（`DocumentSource` 四态 + 条件校验、`DocumentIngestRequest`/`DocumentIngestAndParseRequest`、统一响应体 envelope 响应模型）；`app/core/error_codes.py` 新增 `DocumentErrorCodes.INGEST_FAILED=200010` 并接入 `error_code_catalog()`。
- 完成：`app/services/document.py` 三占位替换为真实实现——ingest 校验知识库存在/类型归属（personal 仅创建者、team 匹配 teamId、enterprise 匹配 orgId/租户）、来源校验、幂等登记、docTitle 自动推断、`orchestrationMode=quick` 登记 PARSING；ingest-and-parse 内部两阶段返回双任务 ID；查询文档信息 404/403 + 数据范围收敛。
- 完成：`app/routers/document.py` 三路由接入 `authorize_or_raise`（create/read + `kb_id/kb_type/owner_id/org_path` 上下文，AUTHZ 先于 service 副作用）。
- 修正：schemas 响应模型原为扁平结构（违反统一响应体 §3.3），主线程改包 `data` envelope；补 `DocumentIngestAndParseResponse`；去除冗余 `DOC_NOT_FOUND` 别名。
- 完成：新增 `tests/test_document.py`（16 例，覆盖成功/幂等/404/403/参数校验/一体化/查询/AUTHZ）；全量测试 **89 passed**（原 73+16）。
- 实测：沙箱内启动 uvicorn，ingest/ingest-and-parse/查询文档 三接口均 `000000` 且 traceId 回写；不存在文档 `100404`。
- 同步：README §当前实现进度 增补文档域落地（第 5 条），解析/检索仍为占位（第 6 条）。
- 决策：响应构造在 service 内联 `error_response(SUCCESS, data)`（注释标注待 responses.py 收敛）；按最小改动优先，暂不迁移。
- 下一步：解析域（parse/parse-result）真实实现按同一范式推进；文档/知识库存储替换真实持久化的迁移点仍收敛在各自 store。

### 任务：暂停点快照（关机恢复用）

> 本条目为**会话中断前的恢复指引**，恢复任务时先读本条。

- **任务状态**：文档域真实实现**已完成并验证**（任务清单 #1–#4 全部 completed；`goals/goals.md` 标记已完成）。
- **未提交改动**（全在工作目录内，未 commit/push）：
  - 修改：`README.md`、`app/core/error_codes.py`、`app/routers/document.py`、`app/services/document.py`、`docs/worklog.md`
  - 新增：`app/schemas/document.py`、`app/services/document_store.py`、`goals/goals.md`、`tests/test_document.py`
- **验证基线**：全量测试 `89 passed`（`/home/ikc-log-center/.venv/bin/python -m pytest tests -q`）；三路由端到端实测 `000000`；`/api/error-codes` 含 `200010`。
- **恢复后的待办**：
  1. 运行 `pytest tests -q` 确认 89 passed 基线仍在。
  2. 若用户要求提交：按 §8.1 提交当天改动（仅 git add 上列文件，不含 `.venv`/`logs`），commit 信息如 `feat: 文档域 ingest/ingest-and-parse/查询文档信息 真实落地并接入 AUTHZ`。
  3. 可选项：解析域（parse/parse-result）真实实现，按本任务同一范式（schemas→store→service→router→AUTHZ→测试）推进。
  4. 可选项：service 内联响应构造收敛到 `app/core/responses.py`（`document_ingest_response` / `document_info_response`）。

## 2026-08-05

### 任务：独立设计并定义开放平台 SDK（open-ikc-sdk）

- 完成：新增设计文档 `docs/开放平台SDK集成设计.md`（286 行，待评审）。
- 决策：SDK 与平台逻辑层（Claude Code 进行中）完全解耦——写范围仅 `sdk/` + 本文档，不触碰 `app/`/`tests/`/`pyproject.toml`；依赖仅 `httpx`，不引入 fastapi/pydantic；包名 `open-ikc-sdk`。
- 决策：方法名蛇形、请求参数与响应字段沿用平台 camelCase；模型 dataclass + 未知字段 `extra` 透传；错误码全表映射异常层级（`OpenIKCAPIError` 子类 + 传输层异常区分）。
- 决策：同步 `OpenIKCClient` / 异步 `AsyncOpenIKCClient`；traceId 23 位数字生成与复用；身份头按非空透传（AUTHZ 上下文）；POST 仅显式传 `reqId` 时允许重试。
- 下一步：设计评审通过后按里程碑 M1（骨架）→ M2 知识库 → M3 文档 → M4 解析/检索 → M5 异步与下载流推进；与逻辑层无文件交集。

### 任务：SDK M1 骨架落地（设计评审前置推进）

- 完成：新建 `sdk/python/` 独立包 `open-ikc-sdk`（仅依赖 httpx，未触碰 `app/`，与逻辑层零文件交集）。
- 完成：核心模块——`errors.py`（异常层级 + 错误码映射表，含 100405）、`trace.py`（23 位数字 traceId 生成/复用）、`envelope.py`（统一响应壳解析）、`headers.py`（Bearer + trace 头 + AUTHZ 身份头按非空透传）、`transport.py`（超时/指数退避重试、POST 仅显式 reqId 才重试、HTTP 状态与统一壳双路径异常映射）、`client.py`（`OpenIKCClient`：`request`/`raw`/`fetch_catalog`/`fetch_error_codes`，repr 脱敏 token）。
- 完成：SDK 单元测试 5 文件 47 例（trace/envelope/errors/headers/retry/client），使用 `httpx.MockTransport` 无需起服务；验证 **47 passed**。
- 决策：`OpenIKCProtocolError` 归类传输层；未知错误码统一 `OpenIKCBusinessError`；`raw()` 不抛业务异常作逃生口。
- 下一步：M2 知识库域封装（`KnowledgeBaseClient` + 模型 + 测试），可与平台真实实现联调。

### 任务：SDK M2 知识库域封装（KnowledgeBaseClient + 模型 + 测试）

- 完成：新增 `models/knowledge_base.py`（`KnowledgeMetadataField` / `KnowledgeBase` / `KnowledgeBasePage`，camelCase 字段、`from_dict`/`to_dict`、未知字段 `extra` 透传）。
- 完成：`client.py` 新增 `KnowledgeBaseClient` 并挂载为 `client.knowledge_bases`：`create`（含 metadataSchema dict/模型双形态）、`update`（拉取现有记录 + 合并的局部更新，避免平台缺省重置 kbType/visibility，未知字段抛 TypeError）、`query`（仅放非空过滤条件）、`get`（路径参数替换）。
- 完成：新增 `tests/test_knowledge_base.py` 12 例；SDK 全量 **59 passed**。
- 决策：update 采用先 GET 后 POST 的合并语义并写入设计文档 §6.1 说明；修复一次 `__repr__` 插入错位（重写 `client.py` 保证结构正确）。
- 下一步：M3 文档域封装（`DocumentClient` + `DocumentSource`/`DocumentIngestResult` 等模型），平台文档域已落地可直接联调。

### 任务：SDK M3 文档域封装（DocumentClient + 模型 + 测试）

- 完成：新增 `models/document.py`（`DocumentSource` / `DocumentIngestResult` / `DocumentIngestAndParseResult` / `DocumentInfo`，未知字段 `extra` 透传）。
- 完成：`client.py` 新增 `DocumentClient` 并挂载为 `client.documents`：`ingest`、`ingest_and_parse`（parseStrategy/resultFormat/executeMode 按非空透传）、`get`（路径参数替换）。
- 决策：ingest 类请求 `reqId` 仅在显式传入时放入请求体，与传输层「POST 带 reqId 才允许重试」对齐；`source` 同时接受 dict 与 `DocumentSource` 实例。
- 完成：新增 `tests/test_document.py` 10 例；SDK 全量 **68 passed**（修正 2 处断言：to_dict 全字段输出、mock executeMode 与请求一致）。
- 下一步：M4 解析/检索域封装（`ParseClient` 四方法含下载、`SearchClient.query`），平台占位期以 mock 验证。

### 任务：SDK M4 解析/检索域封装（ParseClient + SearchClient + 下载双形态）

- 完成：`transport.py` 重构——抽取 `_send()` 统一重试/超时/传输异常映射；新增 `download()` + `DownloadPayload` 兼容 JSON 统一壳与原始文件流。
- 完成：新增 `models/parse.py`（`ParseTask`/`ParseResult`/`DownloadTicket`/`DownloadResult`）与 `models/search.py`（`SearchResultItem`/`SearchResult`，按 V2 D-01 目标态）。
- 完成：`client.py` 新增 `ParseClient`（`parse`/`query_result`/`issue_download_ticket`/`download`，`download` 返回 `DownloadResult | bytes`，`to_path` 落盘）与 `SearchClient.query`（对齐平台当前 schema 五字段）。
- 决策：检索请求参数以平台代码 schema 为准（`query`/`kbId`/`kbIds`/`ownerId`/`orgPath`），`filters`/`topK` 等目标态参数待平台落地后补充，已同步设计文档 §6.4。
- 完成：新增 `tests/test_parse.py` 8 例、`tests/test_search.py` 3 例；SDK 全量 **79 passed**。
- 下一步：M5 异步客户端 `AsyncOpenIKCClient`（httpx.AsyncClient + 同一套模型/错误映射）与 README 完善。

### 任务：SDK M5 异步客户端（AsyncOpenIKCClient）

- 完成：`transport.py` 抽取共享辅助函数（`resolve_timeout`/`build_url`/`can_retry`/`backoff_delay`/`handle_response`/`_download_payload`），同步 Transport 行为不变。
- 完成：新增 `transport_async.py`（`AsyncTransport`：async request/get_json/download/_send，退避用 `asyncio.sleep(backoff_delay())` 不阻塞事件循环）。
- 完成：新增 `async_client.py`（`AsyncOpenIKCClient` + `AsyncKnowledgeBaseClient`/`AsyncDocumentClient`/`AsyncParseClient`/`AsyncSearchClient`，复用 client.py 的 body 组装辅助函数与全部模型）。
- 完成：`__init__.py` 导出 `AsyncOpenIKCClient`；新增 `tests/test_async.py` 12 例（`asyncio.run` + `httpx.MockTransport`，覆盖 request/错误映射/四域方法/下载落盘/上下文管理/repr 脱敏/连接错误重试）；SDK 全量 **91 passed**。
- 下一步：可选——真实平台联调冒烟（`examples/quickstart.py`）、README 完善已完成；SDK 五里程碑（M1-M5）全部落地，待设计评审与联调。

### 任务：SDK 联调冒烟脚本补充

- 完成：新增 `sdk/python/examples/quickstart.py`（同步全链路冒烟：创建知识库 → 接入文档 → sync 解析 → 查询解析结果 → 签发凭证 → 下载 → 检索 → `/api/catalog` 自检；检索占位 `501001` 打印提示不报错；身份头 `CallerIdentity` 保持一致满足个人库范围收敛）。
- 完成：新增 `sdk/python/examples/async_quickstart.py`（异步客户端 create/query 示例）。
- 完成：README 新增「联调冒烟」章节；两脚本 `py_compile` 通过。
- 备注：冒烟需平台服务运行（沙箱网络隔离，需在沙箱外执行）并配置 `OPEN_PLATFORM_TOKEN`；SDK 全量测试基线 **91 passed** 不受影响。

### 任务：开放平台 API 接口定义全面一致性核查（只读审计）

- 完成：以知识库域为规范基准，并行派发文档/解析/检索三域只读审计子代理（各域路由↔catalog↔schema↔service↔错误码↔AUTHZ↔V2文档↔测试 交叉核对）。
- 结论：四域主干协议/路由↔catalog/统一响应壳/异常链路均达标；共 20 项发现（高 2、中 11、低 7）。
- 关键：高 1 文档域 quick 分支 `taskStatus` 硬编码 INGESTED 与 PARSING 状态不符（`services/document.py:191`）；高 2 V2 B-07 仍标注占位但接口已真实实现；中 11 含 KB A-02 文档「保持不变」与实际重置语义不符、解析 data 裸 dict、kbId 未校验、检索缺 response_model/测试、错误码编号跨域交错等。
- 决策：逻辑层相关修复交由并行开发收尾时处理（避免文件冲突）；文档同步项（B-07/A-02/B-03~05/B-06/错误码表）可独立先行；SDK 侧无需改动。
- 输出：`docs/API接口定义一致性核查报告_2026-08-05.md`（73 行，含修复建议与归属）。

### 任务：一致性核查后续动作（文档同步修正 + 逻辑层待办交接）

- 完成：修正 `docs/开放平台接口详细定义_精简版_V2.md`（20 处，+27 行）——错误码表补 200003/200004/200010/200011 并泛化公共码适用范围；A-02 修正 update 缺省重置语义（kbType/visibility/teamId/orgId 全量字段）+ 出参样例 createTime；B-03/B-04/B-05 以代码为准（仅 docId/docId+ticket 查询参数，下载出参改统一体+目标态文件流说明，补错误码 200003/200004）；B-06 补 docTitle/tags/metadata/orchestrationMode 入参与 taskStatus 出参；B-07 由「预占位」重写为真实实现（完整出参表+错误 100404/100403）；附录占位说明收敛为「仅检索/索引占位」。
- 完成：新增 `docs/逻辑层一致性修复待办_2026-08-05.md`（17 项交接清单：P0 行为正确性 3 项、P1 契约对齐 6 项、P2 测试/文档 8 项，含位置/动作/验收）。
- 备注：文档同步项不触碰 `app/`，与并行逻辑层开发零冲突；逻辑层修复项待其收尾时按待办清单闭环。

### 任务：逻辑层一致性修复闭环（P0 全部 + P1 部分，测试全绿）

- 完成：`app/services/parse.py` 增加 kbId 归属校验——`kbId` 与文档所属知识库不一致返回 `100001 INVALID_PARAMS`（P0-2）。
- 完成：`app/services/document.py` quick 分支 `taskStatus` 改为返回 `record.status`（与解析状态一致，P0-1）；`ingest_and_parse` 重构——先新建/复用文档，再委托 `ParseService.parse`，async 返回真实 queued 任务、sync 返回真实内联结果（P0-3）。
- 完成：`app/schemas/parse.py` 新增 `DocumentParseData`（taskId/taskStatus/executeMode/resultInline），`DocumentParseResponse.data` 由裸 dict 改为强类型（P1-4）；`app/schemas/search.py` 新增 `SearchResultItemData/SearchQueryData/SearchQueryResponse`，`app/routers/search.py` 补 summary/description/response_model 三件套（P1-5 响应模型部分）。
- 决策：P1-6 AUTHZ 角色映射补 parse 权限曾试做，但与既有「km_reader 仅 search:query 被拒」测试冲突，已回退保持现状，待逻辑层确认权限语义后再议。
- 测试：`tests/test_parse.py` 全部 `_parse_payload` 调用点补真实 kbId（含 1 处漏改 `test_download_with_ticket_for_other_document`）、新增 kbId 不匹配 100001 用例；`tests/test_document.py` 更新 async 断言 `taskStatus=="queued"` 并新增 3 用例；新建 `tests/test_search.py`（鉴权 501001 / 未认证 100401）。
- 验证：平台 `pytest tests -q` **110 passed**；SDK `pytest sdk/python/tests -q` **91 passed**，无回归。
- 下一步：剩余 P1/P2 待办（P2-13 directory/archive 伪展开标注、P2-14 responses.py 收敛、P1-8 下载 000000 豁免决策、P1-6 AUTHZ parse 权限语义）可自行决定继续或交还逻辑层。

### 任务：Claude Code 代码/安全审查 6 项修复闭环

- 完成：AUTHZ action 语义统一——document `/ingest`、`/ingest-and-parse` 由 `create` 改 `write`（对齐 `document:write`），parse 启动由 `parse` 改 `write`；`ingest-and-parse` 复合校验 `document:write` + `parse:write`；`runtime.py` de 映射补 `parse:read`/`parse:write`（`de_km_reader`/`de_km_operator`），修复 operator 无法接入/解析、非 admin 无法发起解析的缺口（P1-6 闭环）。
- 完成：下载凭证一次性消费——`ParseTicketStore.validate` 命中即删除（one-time），新增单次使用用例。
- 完成：`DocumentStore.update_status` 不再把 update_time 覆盖为 None（`update_time or record.update_time`），文档创建时 `update_time=ingest_time`，新增保留用例。
- 完成：AUTHN 文档 §3.1/§3.2/§5.2 补安全边界说明——static 仅限内网/测试、生产必须 gateway_header 且网关剥离伪造身份头。
- 决策：parseStrategy/resultFormat 深度校验按审查建议延后（落地真实解析引擎前补枚举/范围校验）。
- 测试：新增 5 例（operator ingest/ingest-and-parse/parse 允许、凭证单次使用、updateTime 保留）；平台 **115 passed**、SDK **91 passed**。
- 下一步：剩余 #7/#8/#9/#13/#14/#15/#16/#17 与 GET 403/401 用例按待办清单继续或交还逻辑层。

### 任务：审查复查闭环——README/AGENTS.md 安全边界 + parse schema 深度校验

- 完成：问题 3 复查项——README「认证模式」段与 `AGENTS.md` §4.1 补部署安全边界（static 仅限内网/测试，生产必须 gateway_header 且网关剥离伪造头，或 oidc_jwt/oauth2_introspection）。
- 完成：问题 6 复查项——`app/schemas/parse.py` 新增 `validate_parse_strategy`/`validate_result_format` 与 `DocumentParseRequest` model_validator：docType/parseMethod/backend/parseMode/chunkStrategy/resultFormat.type/imageEncoding 枚举、chunkSize≥0（顶层与 chunking 嵌套）、pageRange 格式（`\d+(-\d+)?`）；`app/schemas/document.py` 的 ingest-and-parse 复用同一套校验。
- 测试：新增 7 例（非法 docType/parseMethod/resultFormat.type/parseMode、负 chunkSize、非法 pageRange、ingest-and-parse 非法 docType）；平台 **122 passed**、SDK **91 passed**。
- 备注：附带发现 2（错 doc_id 消费凭证即丢失）与发现 3（ingest-and-parse parse 授权 resource_id="*"）均为一次性/复合操作的务实折中，保持现状并在待办清单记录。

### 任务：完成后自动审查机制落地（claude headless 只读审查）+ 4 轮实测验证

- 完成：新增 `scripts/review_with_claude.sh`——headless `claude -p --permission-mode plan` 只读审查（机制性禁止写工具），默认审未提交改动（含未跟踪文件清单），工作区干净回退最近一次提交；`OPEN_PLATFORM_AUTO_REVIEW=false` 跳过；`--since/--out` 可覆盖；失败/空报告自动清理半成品并退出非零。
- 完成：`AGENTS.md` 新增 §13 自动审查契约、README 新增说明节。
- 实测 4 轮：第 1 轮抓到「开关未实现」P2 → 修复；第 2 轮抓到「pipefail 下 git diff|head 崩溃」「未跟踪文件不在范围」2 个 P1 → 重写脚本（临时文件截断、未跟踪清单）；第 3 轮抓到「git diff 错误被 || true 静默」「无 HEAD~1 回退」→ 显式失败/首提交回退，并顺带修复 P2（ingest-and-parse parse 授权 `resource_id="*"` → `kbId`）；第 4 轮无 P0/P1。
- 验证：第 4 轮报告 7 项 P2 已闭环或记录——适配器恒生成 `resource_id="*"` 补固化测试（`tests/test_authz_adapters.py`）、resource_id 语义注释、P2-4 schema 校验此前已落地（审查者未注意到 model_validator）；`.err` 残留清理、worktree 遗留（`.claude/worktrees/`，Claude Code 并行产物不纳入）。
- 决策：资源级授权当前由 service 业务校验兜底（`MappingAuthzAdapter` 事实恒 `resource_id="*"`），策略引擎不按 request.resource_id 收敛，已在测试固化并记录待办。
- 验证：平台 `pytest tests -q` **123 passed**（+1 固化测试）；SDK **91 passed**。
- 下一步：P2-2（pageRange start<=end）、P2-3（ingest_and_parse 幂等 executeMode 歧义）、P2-4（download 凭证语义文档化）记入待办，落地真实解析引擎/存储前定稿。

### 任务：headroom 上下文压缩代理 systemctl 托管 + 压缩率优化 + 集成方案文档

- 完成：代理从手动 `setsid` 进程迁移为 `systemctl --user` 托管——`~/.config/systemd/user/headroom.service`（EnvironmentFile=`~/.headroom/headroom.env`，`Restart=on-failure`，`enable --now` 已生效，`/health` 200）。
- 完成：压缩参数显式注入（settings.json 对直启 proxy 不生效）——`HEADROOM_TARGET_RATIO=0.3`、`HEADROOM_SAVINGS_PROFILE=coding`、`HEADROOM_LOSSLESS=0`、`HEADROOM_MODE=token`、`HEADROOM_COMPRESS_TOOL_TURNS=1`；已通过 `/proc/<pid>/environ` 核验。
- 根因分析：37 请求累计节省 4.68%（852,833→812,887 tokens，中位 0.39%）；路由 `ratio_too_high=16`、`cache_hit=22`、`lossless_log` 26 次只记录不压缩；最大浪费为工具结果 JSON 膨胀（~12k tokens/请求）；当前最大节省来自 tool_search_deferral（~23k tokens/请求）。
- 结论：Kompress ONNX 后端正常（1.1–1.8s/块）；启动横幅 `Kompress: not installed` 为显示缺陷（eager 状态 deferred 未映射），已写入文档说明。
- 输出：`docs/headroom上下文压缩代理集成方案.md`（架构链路、venv 角色、统计与根因、参数表、systemd 管理命令、验证/回滚、后续调参建议）。
- 下一步：观察 24h 新参数 PERF 统计；若仍 <5% 优先下调 `HEADROOM_MIN_TOKENS` 至 400/300 并评估 `HEADROOM_FORCE_KOMPRESS_ALL=1`；WSL 登录前自启可 `loginctl enable-linger sharkyai`。
  - 续写：`loginctl enable-linger sharkyai` 已执行（Linger=yes），headroom 随机器开机自启完成；服务自 14:11:54 运行（PID 122444，health 200）。重启后首 11 个 Claude Code 请求实测：原始 582,089 → 优化 569,230 tokens，压缩节省 12,859（2.21%，中位 2.17%），另有 tool_search_deferral 平均 ~21k tokens/请求延迟注入未计入压缩；Kompress ONNX 于 14:14:12 后台加载成功，code/text/tool 块按 0.07–0.24 保留比压缩；路由仍拒大量小块（ratio_too_high 28–37、unchanged ratio>=1.00 28–29）。proxy_savings.json 为会话级统计（上一会话 37 请求/4.63%），实时口径以 headroom-proxy.jsonl 为准。
  - 续写：按 litellm 同款改造为系统级服务——`/tmp/headroom.service` 已生成（`/etc/systemd/system/`、User=sharkyai、日志 append 到 /home/litellm/headroom.log、WantedBy=default.target），root 下可直接 `systemctl status headroom`；安装需 root（本会话无免密 sudo），命令已写入方案文档 §6.4。
  - 续写：`docs/headroom上下文压缩代理集成方案.md` 已重写为全量配置手册（337 行）——前置条件、客户端配置、headroom.env 参数表、user 级/系统级 systemd 完整步骤、日志清单、验证命令、压缩效果与根因、已知问题排障、管理速查、回滚、变更记录；当前状态明确标注「user 级运行中、系统级待 root 安装」。
  - 续写：Codex 切换 headroom——`/v1/responses` 端到端测试通过（model=deepseek-v4-flash）；`~/.codex/config.toml` 新增 `model_providers.headroom`（base_url=http://127.0.0.1:8787、wire_api=responses、复用 LITELLM_TOKEN）并将 `model_provider` 切为 `headroom`，原配置备份 `config.toml.bak.20260805`；重启 Codex 会话生效，回切改 `model_provider=litellm`。
  - 续写：`docs/headroom上下文压缩代理集成方案.md` §3.3 扩展为双客户端完整配置——Claude Code `settings.json` env 全键（token 脱敏）、Codex `config.toml` 全量（含 litellm/headroom 双 provider）、生效/验证/回切步骤。

### 任务：OpenAPI 发布文档与实际实现一致性更新（/docs、/redoc、/openapi.json）

- 更新：`app/core/app_factory.py`——应用信息由「开放平台 API 浏览服务 0.1.0 / 预占位框架」改为「开放平台北向 API 1.0.0」，描述覆盖四类能力、Bearer 认证要求与统一响应体；四个 tag 描述同步去掉「预占位」表述并细化（文档域注明 url/file/directory/archive、解析域注明 async/sync 与一次性凭证、检索域注明 search/qa）。
- 优化：OpenAPI 新增 HTTP Bearer securityScheme + 全局 security 声明，/docs 出现 Authorize 且文档明示认证要求（与 AuthN 中间件一致）；200 响应描述补充业务错误码 200xxx（如 200004）并指向 /api/error-codes。
- 校正：`app/routers/parse.py` 解析结果查询描述改为「解析任务启动后轮询」，补充 200003 未就绪语义；`app/routers/search.py` 检索描述补充 kbId/kbIds 至少提供一个、qa 回答当前为占位生成、个人库仅创建者可检索。
- 核对：12 条业务路由路径与 `app/core/catalog.py` 一致；全部响应模型（含 data 字段）与 service 实际返回逐项比对一致；错误码 100404/100409/200004 与描述一致。
- 验证：`/openapi.json` 重新生成核对（info/security/tags/描述）；平台 `pytest tests -q` **140 passed** 无回归。
- 下一步：重启平台（uvicorn）后访问 /docs、/redoc 查看生效。

### 任务：基于历史 Excel 检索接口定义，重设计开放平台检索接口（设计草案）

- 盘点：`docs/_excel_interfaces_extracted.json` 检索相关条目（VectorSearchV2 内部/第三方、DeepSearch、searchTest、queryChunk、queryAiKlgDatasetList 等），提炼可对外复用能力：图文检索、searchType/partitions、score 阈值/useRerank/relNum/maxToken、问题优化、结构化 filters、usage/debug/imageUnderstanding 可观测返回。
- 输出：`docs/开放平台检索接口重设计方案_2026-08-05.md`——历史能力盘点、现状差距分析、增强版请求/响应模型（全部向后兼容，新增字段可选）、检索域错误码 300001/300002/300003、数据权限不变、Phase 0–3 分期落地、5 项评审决策点。
- 决策：未落码（遵守 AGENTS.md：Excel 抽取不得未经评审直接扩成对外 API）；待确认决策点后进入 Phase 1 落码。
  - 续写：按用户要求，检索接口名定为 `universalRetriever`，路径改为 `POST /api/v1/knowledge-search/universalRetriever`；设计文档同步更新（§5.1 路径、§5.5 兼容性标注 Breaking Change、决策点 6 新增旧路径 `/query` 是否保留兼容别名）。

### 任务：发布 v1.0.0 版本并打 tag

- 版本：`pyproject.toml`（open-ikc-api）、`sdk/python/pyproject.toml` 与 `sdk/python/open_ikc_sdk/_version.py`（open-ikc-sdk）统一升至 `1.0.0`，与 `app_factory.py` 中 OpenAPI info 版本一致。
- 提交：检索域重设计实现（search_store、强类型响应、数据权限过滤）入库；随后提交版本 bump 并打标签 `v1.0.0`。
- 验证：发布前 `pytest tests -q` 平台 146 测试全绿。
- 下一步：如需发布到远端，执行 `git push github main && git push github v1.0.0`（待用户确认）。

## 2026-08-11

### 任务：启用管理面（配置 OPEN_PLATFORM_ADMIN_TOKEN）

- 问题：Portal 登录提示「管理面未启用：请配置 OPEN_PLATFORM_ADMIN_TOKEN 环境变量」；`/admin/overview` 返回 `503001`。
- 根因：服务启动时未设置 `OPEN_PLATFORM_ADMIN_TOKEN`，`scripts/start_open_platform.sh` 也未配置（管理面默认关闭，避免暴露）。
- 改动：`scripts/start_open_platform.sh` 未显式配置 `OPEN_PLATFORM_ADMIN_TOKEN` 时自动生成随机 token（`secrets.token_hex(16)`）并打印，显式配置则透传——不把凭证写死进仓库，本地开发开箱即用；README「启用管理面」补充启动脚本行为说明。
- 验证：重启服务后 `/admin/overview` 带生成 token 返回 `000000`（含 activeTokens 等概览数据），无 token 返回 `100401`；服务正常运行于 18000。
- 下一步：无（改动已闭环）；本轮 token 为启动时随机生成，重启后变化，Portal 登录以启动输出为准。

### 任务：新增一键停止脚本（scripts/stop_open_platform.sh）

- 新增：`scripts/stop_open_platform.sh`——与 `start_open_platform.sh` 配套，按进程匹配 `uvicorn app.main:app`（--reload 模式同时覆盖 reloader 与 worker），SIGTERM 优雅停止，最多等待 10 秒，残留时提示手动处理并退出 1。
- 修复：初版用 `pgrep -f` 会误杀命令行含同模式字符串的调用链（验证时发现自身包装 shell 被 TERM）；改为 `ps -eo pid,comm,args` + awk 仅匹配进程名 python 系列，避免误杀。
- 验证：stop → 无残留进程、端口 18000 关闭、exit 0；随后 start 脚本重新拉起服务验证恢复；README 启动章节补停止脚本说明。
- 下一步：无（改动已闭环）。

### 任务：Portal 调整——首页直达管理面，API/测试入口收拢到左侧栏

- 后端：`app/core/system_routes.py` 首页 `/` 由 307→`/api-browser` 改为 307→`/portal/`（portal/dist 已构建时；未构建回退 `/api-browser`）。
- 前端：`portal/` 左侧栏按分组导航——「管理」（总览/端点监控/Token 管理/在线测试）+「API 文档」（Swagger UI / ReDoc）；API 文档类页面以 iframe 内嵌展示（带标题栏 + 「新窗口打开」），样式新增 `nav-group-title` / `iframe-page`。
- 调整：按用户要求移除侧边栏「API 浏览」入口（与 Swagger UI / ReDoc 重复）；后端 `/api-browser` 路由保留（系统路由、README/目录仍引用）。
- 验证：`npm run build` 产物确认「API 浏览」已移除、Swagger UI/ReDoc 保留；`pytest tests -q` **180 passed**（新增首页重定向测试：307 → `/portal/`，未构建时 → `/api-browser`）；真实服务 `GET /` → 307 → `/portal/` 验证通过。
- 下一步：无（改动已闭环）。

## 2026-08-14

### 任务：Portal 左侧菜单清新化改版（图标 + 布局 + 底部菜单）

- 图标：`portal/src/components/icons.tsx` 新增 Lucide 风格线性 SVG 图标库（24x24、圆角线帽、stroke 1.8），替换原 emoji/字符图标——总览(grid)/端点监控(pulse)/Token 管理(key)/在线测试(flask)/Swagger UI(book-open)/ReDoc(file-text)/退出(log-out)，主题按钮用 moon/sun/contrast/leaf，风格对齐主流 AI 产品原生图标。
- 布局：左侧栏 210→220px；导航分「工作台」「文档」两组并加分组小标题；菜单项带 28px 圆角图标底（hover 淡染主题色、active 实底强调色+光晕）；品牌区 logo 加大圆角+渐变光晕，恢复副标题「管理平台」。
- 底部菜单（左下角）：显示样式改为 4 个纯图标主题按钮（带 title 提示）；新增「在线」状态点；退出登录改为整行图标按钮，hover 变错误红。
- 说明：文档类入口（Swagger UI / ReDoc）由历史 iframe 内嵌改为 `target="_blank"` 新窗口打开（与 2026-08-11 日志中的旧描述不同，以当前实现为准）。
- 验证：`npm run build`（tsc + vite）通过；`portal/dist` 为 gitignore 产物，不入库；后端无改动，未跑 pytest。
- 审查：`scripts/review_with_claude.sh` 只读审查 `docs/code-review_2026-08-14.md`——无 P0/P1；P2-1（`app/core/static/docs/` 未入库）与 P2-2（system_routes 文档同步）均为既有问题，非本次引入，记录待办。
- 下一步：浏览器打开 `/portal/` 复核视觉效果（本环境无无头浏览器）。

### 任务：Token 管理逻辑与 UI 优化（图标操作 + 居中确认 + 右上角 Toast）

- 反馈基建：新增 `portal/src/components/feedback.tsx`——`FeedbackProvider` + `useFeedback()`，统一提供右上角 Toast（5s 进度条动画后自动消失，可手动关闭，最多叠 3 条）与居中确认弹窗（Promise 化 `confirm()`，遮罩点击/Esc 取消，danger 红色确认，autoFocus）。
- 接入：`App.tsx` 全局包一层 `FeedbackProvider`（Login 与 Layout 共用）；context value 用 `useMemo` 稳定化，避免 Toast 生命周期触发页面 `load()` 无限重载。
- Token 页改造（`portal/src/pages/Tokens.tsx`）：
  - 操作全部图标化：创建（+）、刷新（↻）、撤销（垃圾桶，hover 红色）、关闭/复制（×/复制图标），替换原文字按钮；`window.confirm` 移除，改走居中确认弹窗（含 token 名与「撤销后 100401、不可恢复」说明）。
  - 逻辑优化：有效期正整数校验、创建中防重复提交、创建/撤销/复制/失败消息全部走右上角 Toast；明文 token 展示卡片化并新增一键复制；移除内联 ErrorBox/Banner 错误提示。
- 图标：`icons.tsx` 新增 Plus/Refresh/Trash/Close/Check/Alert/Info/Copy 8 个线性图标。
- 样式：`styles.css` 新增 icon-btn（含 primary/danger 变体）、toast-wrap/item/progress（5s keyframes）、modal-overlay/modal（居中、毛玻璃遮罩、缩放入场）、token-created 明文卡片。
- 验证：`npm run build`（tsc + vite）通过；`portal/dist` 为 gitignore 产物不入库；后端无改动。
- 下一步：浏览器打开 `/portal/` 复核（创建/撤销/Toast 动画）。

### 任务：Token 创建表单优化（作用域选择 + 日历有效期）

- 作用域：由自由文本输入改为预设多选 chips（`kb:read/write`、`doc:read/write`、`parse:read/write`、`search:query`，与四大能力对齐），选中态高亮 + 勾选角标；留空 = 不限。
- 有效期：由秒数输入改为原生日期选择器（`min` 今天），并新增「永不过期」开关（勾选则禁用日期，等价于后端 `expires_in_seconds=None`）；选日期时按当日 23:59:59 换算秒数，早于今天的日期拦截并提示。
- 样式：`styles.css` 新增 `scope-chips`/`scope-chip`（圆角胶囊多选）、`form-field-wide`（作用域独占一行）、`check-label`。
- 验证：`npm run build`（tsc + vite）通过；后端无改动。

### 任务：提交前只读审查与 P1 闭环

- 重跑 `scripts/review_with_claude.sh`（上次 claude API 失败导致报告被清空，重试成功）：`docs/code-review_2026-08-14.md`，181 测试全绿。
- P1-1（scopes 仅展示未生效，与本次 Token UI 相关）：闭环方案——UI 标注「预留 · 暂未生效」并加一行说明，避免运营误以为已授权；真正落地的运行时作用域校验属产品/安全决策，待用户确认后再做（见 §11.10）。
- P1-2（启动脚本自动生成并打印 admin token，弱化「管理面默认关闭」）：既有问题，非本次引入，记入待办（README 已注明本地用途；生产建议显式配置）。
- P1-3（redoc bundle 内仍远程拉取 logo）：既有离线化未竟事项，记入待办。
- P2 项（admin 创建请求无 Pydantic 校验、`/` 重定向与挂载时机不一致、静态前缀字面量重复、admin traceId 为空、测试确定性、有效期选「今天」趋近 0）记入待办清单。

### 任务：提交并推送（受阻）

- 提交：`git commit` 完成——`c020600`（契约新增「每次任务完成自动推送仓库」，外部提交）+ 本次 `feat: Portal 改版（线性图标侧边栏、Toast/居中确认、Token 表单选择化）+ 管理面静态文档本地化与首页直达 Portal；测试 181 全绿`；本地 main 领先 github/main 2 个提交。
- 推送受阻：`origin`（code.tiancloud.com）与 `github`（github.com）SSH 22 端口均被本地网关（198.18.0.58 / 198.18.0.35）关闭连接；HTTPS 443 连通正常（github.com 200），但仓库未配置 HTTPS 凭据（无 credential helper / .git-credentials）。
- 待办：网络恢复（内网/VPN）后执行 `git push origin main`（或提供 GitHub PAT 走 HTTPS 推送）。

### 任务：Token 作用域运行时强制生效 + 全选按钮

- 后端链路：`token_store.get_active_token_scopes()` 按明文查活跃 token 作用域（None=环境变量 token 不限 / []=DB token 未配置不限）；`security.AuthResult` 增加 `token_scopes`，static 模式认证时注入；middleware 写入 `request.state.token_scopes`；`authz/runtime.authorize_or_raise` 前置 `_enforce_token_scopes`——DB token 调用必须命中 `resource:action`（支持 `*` 通配，如 `*:*`、`knowledge_base:*`），不命中抛 `100403`，不依赖 AUTHZ 策略开关。
- 作用域命名：与运行时 `resource_type:action` 对齐（knowledge_base/document/parse/search × create/update/read/write/query）；前端 `SCOPE_OPTIONS` 由 `kb:read` 等简写改为 8 个规范预设（知识库读/建/改、文档读/写、解析读/写、检索查询）。
- 前端：新增「全选/清空」图标按钮（CheckSquareIcon，全选时变为清空）；移除「预留 · 暂未生效」标注（已生效）；README 补充作用域生效说明。
- 加固：`/admin/tokens` 创建入参校验（scopes 必须字符串数组、expiresInSeconds 必须正整数秒），闭环审查 P2-1 的脏数据问题；旧测试 `test_admin_api.py::test_create_and_revoke_token_flow` 的作用域 `read` 改为 `knowledge_base:read`（新语义下原断言被正确拒绝）。
- 新增测试：`tests/test_token_scope_enforcement.py` 8 个（_scope_allows 通配矩阵、search 作用域放行检索拒绝建库、kb:read 拒绝建库与检索、kb:create 放行、`*:*` 放行、空作用域不限、环境变量 token 不限、admin 入参校验）。
- 环境问题：本会话中沙箱 seccomp 会卡死 anyio/TestClient（最小 FastAPI 亦死锁），pytest 需在沙箱外运行（已保存白名单）；全量 **189 passed**（181 + 8）。
- 下一步：跑 Claude 只读审查后提交（推送仍受 SSH 网关阻断，待网络恢复）。

### 任务：作用域审查 P1/P2 闭环

- 审查：`docs/code-review_2026-08-14.md` 更新版——无 P0；P1-1（管理面独立鉴权、禁止复用业务 token 为 admin token）已 README 声明；P1-2（`_lookup_token_scopes` 异常静默 fail-open）闭环：环境变量 token 短路不触 DB，DB 查询失败返回不可命中哨兵 → fail-closed 403 + 告警日志。
- P2 闭环：`/admin/tokens` scope 格式校验（`resource:action`、支持 `*`、≤32 个、单元素 ≤64 字符）；前端有效期必须晚于今天；新测试 fixture 预置一条已撤销记录模拟生产常态，避免「未配置 token 放行」分支掩盖 scope 行为。
- 验证：全量 **189 passed**（沙箱外运行，沙箱 seccomp 会卡死 anyio/TestClient）；`npm run build` 通过。

### 任务：在线测试 token 明文显示切换按钮

- `portal/src/pages/TestLab.tsx` 公共参数 token 输入框改为「输入框 + 内嵌眼睛图标按钮」：点击在 `password` / `text` 间切换显示明文，tooltip 随状态切换（显示明文/隐藏明文）。
- 图标：`icons.tsx` 新增 `EyeIcon` / `EyeOffIcon`；样式：`styles.css` 新增 `field-with-action`（输入框右侧内嵌操作按钮）。
- 顺带：TestLab 白名单加载错误由内联 ErrorBox 改为右上角 Toast（对齐全局消息约定）。
- 验证：`npm run build` 通过；后端无改动。

## 2026-08-17

### 任务：输出并落盘完整 API 开发手册（含 MCP/CLI 补充）

- 新增 `docs/API开发手册.md`（553 行）：基于当前代码（catalog/路由/schemas/error_codes）逐项核对后整理的完整开发手册——平台概述、快速开始、全局约定（AUTHN/traceId/统一响应体/16 个错误码/AUTHZ 动作映射与 token 作用域）、12 个业务接口详细定义（字段表 + curl 示例）、10 个管理面接口、系统路由、Python/Java SDK 接入、MCP Server（14 工具参数表 + 客户端配置示例）、CLI（11 子命令 + 全局选项 + 退出码 + 示例）、常见错误排查。
- 完成情况：手册内容与实现一致（知识库 4 / 文档 3 / 解析 4 / 检索 1；admin 10；错误码 16）。
- 下一步：按需将手册同步至对外交付渠道；推送仍受 SSH 网关阻断（见前条待办）。

### 任务：手册页顶部标题重复修复

- 问题：`/api-manual` 服务端渲染页 hero 区块（标题+简介）与 markdown 正文首行 `# OpenIKC 开放平台 API 开发手册` 重复。
- 改动：`app/core/api_manual.py` 删除 hero 的 `<h1>`/`<p>`，仅保留导航链接条（管理 Portal/Swagger UI/ReDoc/OpenAPI JSON/API 浏览），padding 收敛为 14px 24px。
- 验证：`curl /api-manual` 页面唯一 `<h1>` 为 markdown 正文标题，无重复；标题保留于 `<title>`（浏览器标签页）。

### 任务：检索能力优化方案（普通检索 + 深度检索，对接 knowledge_transformer）

- 产出：新增 `docs/检索能力优化方案_普通检索与深度检索.md`（297 行）。
- 调研：通读 `knowledge_transformer` 检索相关实现与文档——universal_retriever（`/retrieval/search/sync`，8096，fulltext/vector/hybrid + RRF + 可插拔后端）、openai_search_service（`VectorSearchV2/UniversalSearch` 基础检索、`DeepSearch` Agentic 多轮，8088，前缀 `/km/search-api/aiTools/openai/bsapi`）；`unified_retrieval_architecture_real_impl.md` 确认 openai_search_service 进程内调 universal_retriever 内核。
- 方案要点：保留 `POST /api/v1/knowledge-search/query` 为普通检索（证据列表，可切 UR 或 VectorSearchV2），新增 `POST /api/v1/knowledge-search/deep-query` 深度检索（映射 DeepSearch）；服务层新增 `search_client.py`（httpx 下游适配 + 超时/重试/错误映射），`OPEN_PLATFORM_SEARCH_BACKEND=in_process|ur|openai` 开关；错误码注册 `300001` 检索执行失败；catalog/详细定义/README/启动脚本同步；测试计划含 mock 下游的 `test_search_downstream.py`。
- 决策留待评审：接口形态（推荐双接口）、普通检索 qa 回答策略（推荐移除占位文案）、steps 暴露粒度、searchType 默认 hybrid、kb→index 映射方式。
- 完成情况：方案文档已落盘，worklog 已更新；未改代码，未跑测试（无行为变更）。
- 下一步：评审确认后按 schemas → services → routers → error_codes/catalog/docs → 测试落地。
- 方案修订：按用户反馈「端点名称尽量与后端能力统一/靠齐」——普通检索端点定为 `POST /api/v1/knowledge-search/universal-search`（对齐 `UniversalSearch` / UR `/retrieval/search/sync`），深度检索定为 `POST /api/v1/knowledge-search/deep-search`（对齐 `DeepSearch`）；`/query` 降级为阶段一兼容别名；同步 catalog/AGENTS.md §3.2/测试路径的落地要求。
### 任务：检索能力优化落地（普通检索 + 深度检索，对接 knowledge_transformer）

- 方案已确认（前两条 worklog 任务），本次按 §9 落地：
  - 端点：`POST /api/v1/knowledge-search/universal-search`（普通检索，对齐 UniversalSearch / UR /retrieval/search/sync）、`POST /api/v1/knowledge-search/deep-search`（深度检索，对齐 DeepSearch）；旧 `/query` 保留为兼容别名（deprecated）。
  - schemas：`SearchQueryRequest` 扩展 searchType/relNum/useRerank/score/index/isOptimize，响应新增 qaNote/searchType/usedConfig；新增 `DeepSearchQueryRequest/DeepSearchQueryData/Response`（deepSearch 控制、memory、sessionId、citations/steps）。
  - services：新增 `app/services/search_client.py`（httpx 下游适配：UR sync、OpenAI VectorSearchV2/DeepSearch；超时/重试/错误映射；kb→index 映射；trace 透传）；`SearchService.query` 按 `OPEN_PLATFORM_SEARCH_BACKEND=in_process|ur|openai` 分发，新增 `deep_query`（仅 openai 后端可用，否则 501001）；权限校验与逐 kb 授权保持不变。
  - 错误码：注册 `300001` 检索执行失败（SearchErrorCodes，进 /api/error-codes）。
  - 同步：catalog（3 条检索路由）、AGENTS.md §3.2、详细定义文档 D-01/D-02、整体方案 §3.4/下游映射表、README、pyproject（新增 httpx）、启动脚本（下游环境变量默认值）。
  - 测试：新增 `tests/test_search_downstream.py` 13 个（UR/OpenAI 请求响应映射、深度检索映射、501001 分支、300001 错误映射、权限前置、错误码目录断言、参数校验）；现有测试路径切到新主端点并补 `/query` 别名用例。
- 验证：全量 `203 passed`（189 + 14 新增）。
- 下一步：docs/API开发手册.md 同步（子代理处理中）；Claude 只读审查（OPEN_PLATFORM_AUTO_REVIEW 未禁用时）；提交推送双远端。

### 任务：Claude 只读审查闭环（检索优化提交 d09f17f）

- 审查：`docs/code-review_2026-08-17.md`——无 P0；P1×3、P2×6。
- P1-1（高，越权）：AUTHZ 上下文 `owner_id`/`org_path` 改为一律取认证身份（`request.state.identity`），请求体 `ownerId`/`orgPath` 不再作为授权依据（保留为兼容字段）；`teamId`/`orgId` 仍为业务范围声明。同步 AGENTS.md §4.2、README、设计文档；新增回归测试 `test_authz_context_owner_org_comes_from_identity`。
- P1-2：经核对 `app/core/authz/runtime.py` 默认映射已含 `km_reader: search:query`，属审查误报，无需改动。
- P1-3：深度检索与普通检索共享 `search:query` 作用域，README 明示（不单独设 scope，如需独立管控后续新增 `search:deep`）。
- P2 修复两项：P2-4（memory.mode=none 时不注入 memory，补测试）；P2-5（下游 status 字符串 "false" 也判失败，显式白名单语义）。
- P2 待办：P2-1（steps 数值 `or 0` 替换 0 的语义等价问题）、P2-2（`snippet`/`score` 与真实后端字段差异）、P2-3（hybrid 权重硬编码可配置化）、P2-6（deep-search 501001 提示区分未配置/后端不支持，reason 附当前 backend）。
- 验证：全量 **205 passed**（203 + P1-1/P2-4 两个回归用例）。

### 任务：开发手册加入 Portal 侧边栏（文档区）

- 后端：新增 `app/core/api_manual.py`，用 `markdown-it-py`（commonmark + table，已装 4.2.0，无新依赖安装）服务端渲染 `docs/API开发手册.md` 为 `/api-manual` 离线文档页（深色样式 + 表格/代码块，风格对齐 api_browser）；`/api-manual` 加入 system_routes 与 `AUTH_EXEMPT_PATHS`；`pyproject.toml` 声明 `markdown-it-py>=3.0,<5.0`。
- 前端：`portal/src/components/icons.tsx` 新增 BookMarkedIcon；`Layout.tsx` 文档区新增「开发手册」链接（新标签打开 /api-manual）；`npm run build` 产物 portal/dist 已更新。
- 顺手修复：`app/core/admin/monitor.py` 监控中间件在端点抛错时 `finally` 引用未赋值 `response` 的 UnboundLocalError（会掩盖真实异常）——改为 `response=None` 初始化，异常路径不记统计、原异常正常上抛。
- 测试：新增 `test_api_manual_page_renders_manual`（200 + HTML 含手册标题/universal-search/deep-search/300001/table）；免鉴权参数化测试与尾斜杠测试补 `/api-manual`。全量 **207 passed**。

### 任务：Portal 侧边栏改动审查闭环（fba9452）

- 审查：`docs/code-review_2026-08-17-manual.md`——**通过，无 P0/P1**；P2×3 + 1 项行为知悉。
- P2-1 闭环：新增 `test_monitor_exception_path_decrements_and_propagates`（call_next 抛异常 → 并发计数归零、原异常上抛、不落统计）。
- P2-3 闭环：`/api-manual` 渲染结果按文件 mtime/size 缓存（lru_cache maxsize=1），路由改同步 `def` 交由 FastAPI 线程池执行，避免阻塞事件循环。
- P2-2 待办（信息暴露）：`/api-manual` 免鉴权展示手册，其中 CLI 示例含本机路径（/home/open-ikc/.venv）——待手册对外交付时改为通用占位符或收紧访问。
- P2-4（行为知悉）：监控中间件异常逃逸请求不再计入统计（修复副作用，可接受；如需异常痕迹后续降级记录 999999）。
- 验证：全量 **208 passed**。

### 任务：开发手册调整为左侧菜单栏项（应用内页面）

- 按用户反馈「开发手册要增加到左侧菜单栏」：将开发手册从文档区外部链接改为左侧工作台菜单项（总览/端点监控/Token 管理/在线测试/开发手册），点击后在主内容区 iframe 内嵌 `/api-manual` 渲染页面；新增 `portal/src/pages/Manual.tsx` 与 `.manual-frame` 样式，`PageKey` 增加 `manual`，`NAV_ITEMS` 新增 BookMarkedIcon 项；文档区保留 Swagger UI / ReDoc 外部链接。
- `npm run build` 通过（portal/dist 为构建产物不入库）；全量 **208 passed** 无回归。

### 任务：错误码/错误信息命名一致性全面检查 + deep-search 响应去冗余

- 用户要求：1）所有端点输出错误码/错误信息命名定义保持一致，彻底全面检查；2）deep-search 响应报文是否有冗余。
- 错误码命名一致性修复：
  - `app/core/error_codes.py`：`ErrorCode.to_dict()` 键名 `code`/`message` → `errCode`/`errMsg`（与统一响应壳一致，`/api/error-codes` 目录随之统一）；修复 `get_error_code()` 残留旧键名导致的 KeyError 隐患；新增 `AdminErrorCodes.TEST_FAILED = 200020 在线测试执行失败` 进 registry（原 MCP/CLI 测试失败借用 `200001 创建知识库失败`，语义错误）。
  - `app/routers/admin.py`：10 个 admin 端点统一收敛到 `_ok(data)`/`_fail(error, message, data)` 响应壳，`traceId` 由空串改为 `current_trace_id()`（真实 23 位）；MCP/CLI 失败错误码改 `200020`。
  - 全仓复查：routers/services/exception_handlers/security 均走 `error_response`/`to_response`/`AppException` 链路，无手写 `code`/`message` 旧命名残留（仅 search_client 对下游容错读取保留 `.get("code")` 兜底）。
- deep-search 响应去冗余：
  - 移除 `data.results[]`（与 `citations[]` 内容重叠且字段命名不一致 `citation` vs `position`）；`total` 改为 `len(citations)`；`citations[]` 增加可选 `page`（页码，与 `position` 页内坐标语义区分）；`usedQueries` 与可选 `steps[].query` 职责不同，保留。
- 同步 `app/core/responses.py`、`app/schemas/search.py`、`docs/API开发手册.md`（错误码 18 个、deep-search 响应示例去掉 results）；OpenAPI（swagger/redoc 数据源）确认 `DeepSearchQueryData` 已无 `results`。
- 验证：全量 **209 passed**（208 + 管理面统一响应壳 traceId 回归断言；沙箱内 TestClient 事件循环受限需沙箱外执行）。
- 审查闭环（docs/code-review_2026-08-17-err-consistency.md）：无 P0/P1；P2-1 同步 `docs/开放平台接口详细定义_精简版_V2.md` deep-search 出参（去掉 results、total 语义、citations 补 page?）；P2-3 抽取 `_pick_score` 统一普通/深度检索分数兜底链（final→rerank→fused→vector→lexical→0）。
- P2-2 待办：admin 错误码 `200020` 沿用业务 `2xxxxx` 码段（level=admin 语义隔离），后续业务域新码若冲突再为管理面划独立码段（如 `4xxxxx`）。
- 下一步：提交推送双远端（§8.2）。

## 2026-08-18

### 任务：API 开发手册按 LangChain OpenWiki 表达模式重构（服务开发者视角）

- 背景：用户要求参考 `docs.langchain.com/oss/openwiki/overview` 的表达模式，从服务开发者角度优化 `docs/API开发手册.md`（该文件由 `app/core/api_manual.py` 服务端渲染为 `/api-manual` 页面，Portal 左侧菜单「开发手册」内嵌）。
- 参考模式提炼：一句话定位（What + Why）→ Get started 前置（最小可运行路径）→ Modes 选择表（不同方式怎么选）→ Capabilities 卡片式能力概览 → Next steps 引导；语言行动导向、每段回答「对你有什么用」。
- 重构内容（docs/API开发手册.md 全量重写，639 → 846 行）：
  - §1 平台定位与开发者价值：一句话定位 + 四大能力「解决什么问题/典型场景」表 + 五种接入方式选型表 + 手册导航（怎么读）。
  - §2 快速开始升级为 **5 分钟全链路**：建库 → 接入文档 → 解析（含轮询约定）→ 检索，每步带 curl、响应示例与「验证点」，替代原单接口示例。
  - §3 接入方式对比表（REST/SDK/MCP/CLI 六维度），§4 新增「知识库数据生命周期」五阶段编排表 + 异步任务约定（200003 轮询语义）。
  - §5 全局约定、§6 接口参考（13 业务接口字段表与 curl 全部保留原内容，仅重排编号）、§7-§12 管理面/系统路由/SDK/MCP/CLI/错误排查原样保留、§13 下一步与补充约定。
  - 因 markdown-it 渲染关闭 HTML（html: false），LangChain 的 Card/Callout 组件以表格/引用块等效实现；H1 标题保留（tests/test_system_routes.py 断言依赖）。
- 验证：全量 `pytest tests -q` **209 passed**；`/api-manual` 渲染正常（唯一 H1、13 个 h2、24 张表格、50771 字节）。
- 下一步：按 §8.2 提交推送（docs/API开发手册.md + worklog）。

### 任务：/api-manual 手册页增加导航目录（TOC）

- 用户要求：手册页带上导航目录（参考 LangChain 文档页左侧目录形态）。
- 改动：`app/core/api_manual.py` —— 解析 markdown tokens 为 h2/h3 注入锚点 id（`sec-N`），生成侧边目录 `<nav class="toc">`（h2 一级、h3 缩进二级，共 42 项）；布局改 flex：左侧 sticky 目录（桌面，宽 250px，独立滚动）+ 右侧正文，`<900px` 时目录置顶限高 320px；标题 `scroll-margin-top` 保证锚点跳转不被遮挡。零新增依赖，`lru_cache`（mtime/size）机制不变。
- 测试：`tests/test_system_routes.py` 手册渲染用例补 TOC 断言（`class="toc"`、`href="#sec-1"`、目录字样）；全量 **209 passed**。
- 验证：线上 `/api-manual` 200 且含 TOC；Browser 子代理实测点击「2. 快速开始」跳转 `#sec-6` 滚动到位（scrollY=1964，标题位于视口顶部）。
- 下一步：已提交推送；服务如需热更新请重启（lru_cache 以 mtime/size 失效，`--reload` 下自动生效）。

### 任务：手册 2.6 节全面完善 + 目录升级为三级导航

- 用户要求：2.6 节全面完善，并修改目录内容。
- 文档改动（docs/API开发手册.md）：2.6 由 3 条 bullet 扩展为「2.6 下一步：从演示到生产」，含 5 条进阶路线子节——2.6.1 路线 A（换用 SDK/CLI，Python 最小示例按 `SearchResult` 模型属性编写并经 SDK 源码核对）、2.6.2 路线 B（深度检索前置条件 + curl）、2.6.3 路线 C（真实环境认证/鉴权/Token 作用域）、2.6.4 路线 D（Portal 运维）、2.6.5 遇到问题时（排查指引）。
- 目录改动（app/core/api_manual.py）：TOC 从 h2/h3 两级扩展为 **h2/h3/h4 三级**（h4 缩进 28px 更小字号），目录条目 42 → 60：新增 2.6.1~2.6.5 五条路线，§6 接口参考的 13 个接口名（h4）也自动进入目录可直接锚点跳转。
- 验证：全量 `pytest tests -q` **209 passed**；线上 `/api-manual` 200，目录含「2.6.1 路线 A：换用 SDK 或 CLI 接入」。
- 下一步：已提交推送。

### 任务：README 开发手册重构（开发者快速上手 + 清晰导航）+ 手册数量事实修正

- 用户要求：对开发手册优化——更专业、更适合开发者快速上手、导航更清晰（`docs/API开发手册.md` 已于今日完成 LangChain 模式重构，本次对象为仓库 README）。
- README 全量重构（242 → 298 行）：
  - 新增顶部「目录」导航与「快速信息」表（语言/框架、端口 18000、统一响应体、认证方式、在线文档）。
  - 章节重排：1 快速开始（环境要求 → 启动 → `/health` 验证 → 第一次 curl 业务调用 → 5 分钟全链路指引）→ 2 能力总览（四类能力 + 接入方式选型）→ 3 文档导航（在线入口表 + 仓库文档表）→ 4 SDK/MCP/CLI → 5 配置参考（AUTHN/AUTHZ/管理面/日志与检索四组环境变量表）→ 6 协议约定（统一响应体/错误码/认证/TraceID/鉴权）→ 7 项目结构 → 8 测试 → 9 实现状态 → 10 协作与审查。
  - 修复原问题：删除重复小节（TraceID 出现两遍）；「当前实现进度」冗长列表收敛为状态表；「错误码与异常」过时表述修正（领域异常已全部落地）；认证/鉴权长代码示例收敛为要点 + 文档链接；CLI 子命令数 11 → 14。
- 事实修正（代码核实）：MCP 实际注册 14 个工具（`sdk/python/open_ikc_sdk/mcp/server.py`，无 deep_search 工具）、CLI 14 个子命令（无 deep-search 子命令）；同步修正 `docs/API开发手册.md` §1.3/§10/§11 的「15 个」与 deep-search 示例（SDK `client.search.deep_search(...)` 仍存在，仅 MCP/CLI 未封装）。
- 验证：全量 `pytest tests -q` **209 passed**（沙箱外执行；沙箱内 TestClient 事件循环受限，全量测试无法在沙箱内跑完）。
- 下一步：已提交推送。github 已同步（48ca9fe..b7a6a6c）；origin（code.tiancloud.com）被环境网络代理拦截（解析到 198.18.0.67，22/443 均关闭），待网络恢复后补推 `git push origin main`。

### 任务：删除 API 开发手册中的「为什么只有这四类」段落

- 用户要求：去除 `docs/API开发手册.md` §1.2 的说明「为什么只有这四类？平台刻意收敛能力面：索引管理等内部流水线接口不对外暴露。如果你发现需要第五类能力，请与平台方沟通，而不是绕过协议自行拼装」。
- 改动：删除该 blockquote（仅此一处）；手册其余内容不变。
- 验证：全量 `pytest tests -q` **209 passed**。
- 下一步：已提交推送（github）。

### 任务：接口参考章节标题去重——删除标题中「（N 个接口）」并把手册接口路径移入正文

- 用户要求：`docs/API开发手册.md` §6 中「6.1 知识库（4 个接口）」式标题删除括号数量；「6.1.1 创建知识库 `POST /api/v1/knowledge-bases/create`」式标题把路径作为正文一部分，全面检查修改。
- 改动：
  - 组标题：`6.1 知识库（4 个接口）` / `6.2 文档（3 个接口）` / `6.3 解析（4 个接口）` / `6.4 检索（2 个接口 + 1 个兼容别名）` 删除括号。
  - 13 个接口小节标题移除内联路径，统一在标题下方正文首行加「接口：`METHOD path`」（如 `接口：POST /api/v1/knowledge-bases/create`）。
  - 同类标题清理：`5.4 错误码表（当前注册 18 个，实时查询 /api/error-codes）` → 括号移除、说明移入正文引用块；`10.3 工具清单与参数（14 个）`、`11.4 子命令与示例（14 个）` 删除括号数量。
  - 其余括号标题（如 `5.1 认证（AUTHN）`、`7. 管理面接口（/admin/*，运维用途）`）为语义信息，保留。
- 验证：全量 `pytest tests -q` **209 passed**；`rg '（\d+ 个接口）'` 与路径入标题模式均无残留。
- 下一步：已提交推送（github）。

### 任务：手册「§编号」引用实现为真实锚点跳转链接

- 用户要求：手册 §1.4「这份手册怎么读」等处的「跳到 §2 快速开始」「看 §3 接入方式对比」等类似引用要可点击跳转，而不是纯文本假链接，全面实现。
- 改动（app/core/api_manual.py）：
  - 新增 `_linkify_section_refs`：解析 markdown 后按标题纯文本首部章节号（`2`/`5.4`/`11.4`…）建立「章节号 → 锚点 id（sec-N）」映射，把正文 inline 文本中的「§编号」原地替换为 `<a href="#sec-N">§编号</a>` 链接（token 级处理，不影响代码块/行内代码）。
  - 全文档 29 处 § 引用（§2、§3、§4、§5.1、§5.2、§5.4、§5.5、§6、§6.2、§6.3、§6.4、§7、§9.1、§9.2、§10、§11、§11.4、§12）自动生成真实链接，目标锚点由渲染器实时计算，不硬编码 sec 序号。
  - CSS：`article a` 加下划线、h4 加入 scroll-margin-top，锚点跳转不被 sticky 目录遮挡。
- 测试：`tests/test_system_routes.py` 手册渲染用例补断言——`§2` 链接指向「2. 快速开始」标题锚点、`§12` 链接指向「12. 常见错误排查」锚点；全量 `pytest tests -q` **209 passed**。
- 审查：Claude Code 自动审查本轮跳过（与今日此前任务一致，Anthropic API 网络受限）。
- 下一步：已提交推送（github）。

### 任务：双场景（需库 / 免库纯解析）接口满足度分析 + 落地免库独立解析接口

- 用户要求：面向「需要库（知识、解析、检索）」与「不需要库、只需要解析能力」两种场景，分析当前开发接口是否满足或可优化，并同步更新文档。
- 分析结论：场景 A（需库全链路）现状接口完全满足；场景 B（免库纯解析）**不满足**——`ingest.kbId`/`parse.kbId`+`docId` 均必填，纯解析被迫「建库→入库→解析→清理」，带来语义错配、知识空间数据污染与上手成本问题。
- 优化落地：新增 **`POST /api/v1/knowledge-documents/parse-direct` 免库独立解析**接口：
  - 入参 `source`（url/file/directory/archive，与 ingest 同构）+ `parseStrategy`/`resultFormat`/`executeMode`（sync 内联 / async 轮询）等；
  - 不创建知识库、不登记文档；async 返回临时 `docId`（`pdoc_` 前缀），复用现有 `parse-result/query`、`issue-download-ticket`、`download`；
  - 权限：任务归属调用方认证身份，仅创建者可查询/下载（100403）；不进知识库可见范围、不参与检索；仍属解析能力域，不新增第五类能力。
  - 实现：`app/schemas/source.py`（DocumentSource 从 document.py 抽出，消除 document↔parse 循环导入）、`ParseDirectRequest/Data/Response`、`ParseService.parse_direct` + `_get_parse_task_doc_or_raise`/`_validate_parse_doc_scope`、路由与 catalog 同步。
- 文档同步：新增 `docs/解析场景分析_需库与免库.md`；API 手册 §1.2/§1.4/§4.1/§6.3.5/§13、README 能力总览（解析 4→5 接口）与实现状态、V2 详细定义 B-02.1。
- 验证：全量 `pytest tests -q` **216 passed**（新增 7 例：sync 内联/async 轮询/下载链路/owner 收敛/参数校验/任务不存在/catalog）；`/api-manual` 渲染含 §6.3.5 且自动链接生效。
- 审查：Claude Code 自动审查本轮跳过（Anthropic API 网络受限，与今日此前任务一致）。
- 下一步：已提交推送（github）。

### 任务：Swagger / Redoc / API 开发手册完整性核对

- 用户要求：核对所有 Redoc、Swagger 与 API 开发手册是否完整优化和更新。
- 核对结果（全部一致）：
  - OpenAPI（/docs、/redoc、/openapi.json 数据源）：24 个路径；业务 15 条与 `/api/catalog`、手册 §6 完全一致；`parse-direct` 请求/响应模型（ParseDirectRequest/Response/Data、DocumentSource）已在 components 完整生成。
  - 手册 §6：知识库 4 + 文档 3 + 解析 5（含 6.3.5 独立解析）+ 检索 3（含 /query 兼容别名说明）；无残留旧数量表述（13/15/11 个等）。
  - 本地静态资源 `app/core/static/docs/{swagger-ui,redoc}` 就位，离线可用。
- 补测试：`tests/test_system_routes.py` 新增 `test_openapi_docs_pages_available`（/docs、/redoc、/openapi.json 200 且含最新接口）。
- 验证：全量 `pytest tests -q` **217 passed**。
- 下一步：已提交推送（github）。

### 任务：API 开发手册全面一致性测试 + 测试报告

- 用户要求：使用 `docs/API开发手册.md` 对平台进行全面完整测试，验证手册准确性与完整性，输出测试报告。
- 测试方式：TestClient 进程内逐项断言（沙箱外运行）；固定 `OPEN_PLATFORM_TOKEN=test-token` 并隔离管理面 SQLite，避免历史数据干扰。
- 覆盖：§3.1 在线入口（/api-manual、/api/catalog 等）、§5 全局约定（认证 100401、统一响应壳、23 位 traceId、18 个错误码）、§6 四类业务 15 条路由（知识库 4 / 文档 3 / 解析 5 / 检索 3，含幂等、越权 100403、sync 内联、免库 parse-direct、凭证下载 200003/200004、别名 /query、deep-search 501001）、§7 管理面 503001、§8 系统路由 8 项、手册 §6 ↔ `/api/catalog` 路由清单逐条比对。
- 结果：**62 用例全部通过（100%）**；报告输出 `docs/测试报告_API开发手册一致性_2026-08-18.md`。
- 文档修正：§6.4.1 兼容别名 `/knowledge-search/query` 原仅注释提及，已补充为正式接口行，手册与 catalog 完全对齐。
- 发现项（P2，未改实现，记入报告）：
  1. 新建知识库 `updateTime` 为 null（未更新语义），建议手册补充说明；
  2. 空字符串 `kbName` 服务端未做非空校验，可创建空名库，建议补 100001 校验或文档说明；
  3. sync 解析命中既有 queued 任务时复用状态不强制完成，与手册「sync 请求内完成」存在语义差异，建议确认产品预期并补文档。
- 测试脚本：`/tmp/manual_conformance.py`（可复跑，报告路径写死为当日文件）。
- 下一步：全量 pytest 回归后提交推送（github）。

### 任务：在线测试模块（/admin/test/*）分析检查与全面优化

- 用户要求：对在线测试模块进行分析检查，找出问题与遗漏，全面优化并确保测试完整正确。
- 审查发现的问题/遗漏：
  1. **MCP 冒烟 `kb_get` 必失败**：`kb_get(kbId)` 为必填参数，原冒烟以 `{}` 调用必然 `is_error`，白名单含 `kb_get` 但永远测不过；
  2. **白名单不完整**：CLI `kb-list` 缺 `--team-id/--org-id/--owner-id`；MCP 只读工具 `doc_get/parse_query/parse_issue_ticket/search_query` 未纳入；
  3. **Router 裸 dict 请求体**：`payload: dict[str, Any]` 无参数校验，`args` 类型错误会被拆成字符；
  4. **CLI 位置参数无上限**：`kb-get` 等可传任意多个位置参数；
  5. **MCP 冒烟不支持工具参数**，步骤超时硬编码 10s；
  6. 无 HTTP 层测试、无白名单与 SDK 命令/工具一致性测试。
- 优化落地：
  - `app/core/admin/mcp_cli_test.py`：白名单升级为「命令/工具 + 参数级」规格（`CommandSpec`：flags + 位置参数上限；MCP 工具 → 允许参数 key）；`run_mcp_smoke` 支持 `args`（JSON 注入子进程环境，避免转义）；步骤超时参数化；CLI 位置参数数量校验；新增 `whitelist_payload()`。
  - `app/schemas/admin_test.py`（新增）：`McpTestRequest` / `CliTestRequest` Pydantic 模型（含 `timeoutSeconds` 1–120、类型校验）。
  - `app/routers/admin.py`：接入 Schema、透传 args/timeoutSeconds、whitelist 返回 `{cli, mcpTools, cliArgs, mcpArgs}`。
  - Portal：`TestLab.tsx` MCP 冒烟支持工具参数 JSON 输入，并展示各命令/工具允许参数提示；`types.ts` 同步。
  - 白名单最终：CLI 7 命令（kb-list/kb-get/doc-get/parse-query/sys-catalog/sys-error-codes/search-query）；MCP 8 工具（sys_catalog/sys_error_codes/kb_get/kb_query/doc_get/parse_query/parse_issue_ticket/search_query），全部只读。
- 测试：`tests/test_admin_testlab.py` 重写扩展（18 新增）：位置参数上限、带参工具放行/拒绝、白名单 ⊆ SDK 命令/工具一致性、whitelist 结构、HTTP 层鉴权 100401/503001、参数类型错误 100001、执行失败 200020 结构化返回。全量 `pytest tests -q` **235 passed**（原 217）；`/tmp/manual_conformance.py` 62/62 回归通过；Portal `npm run build` 通过。
- 文档：`docs/管理Portal设计.md` §3.4、`docs/MCP与CLI接口定义.md` §9、`docs/API开发手册.md` §7 管理面接口表同步（args/timeoutSeconds/白名单明细/超时默认 20s 上限 120s）。
- 下一步：提交推送（github）。

### 任务：MCP / CLI 端到端完整测试 + 覆盖缺口补齐

- 用户要求：检查 MCP/CLI 测试为何未全通过，用 token 完整测试；分析 MCP/CLI 是否完整覆盖所有 API 并完善。
- 环境：后台启动平台（127.0.0.1:18000，用户 token + 独立 admin token），对运行中平台做真实端到端测试。
- 测试方式：`/tmp/mcp_cli_e2e.py` —— CLI 16 命令逐一 subprocess 真实执行、MCP 16 工具用官方 mcp 2.0 ClientSession 逐一 call_tool；唯一库名保证可重复；报告 `docs/测试报告_MCP与CLI端到端_2026-08-18.md`。
- 结果：**35/35 全部通过（100%）**。初始 2 类失败均为测试脚本问题（多行 JSON 解析、库名重复 100409），修复后全绿；deep-search 在平台 in_process 后端下返回 501001（平台未启用 openai 后端），按「链路正确 + 结构化 501001」判定通过。
- 覆盖缺口分析（对照 AGENTS.md §3.2 业务路由 15 条 + 系统 2 条）：
  - 原有缺口：**parse-direct（免库解析）与 deep-search（深度检索）在 MCP/CLI 均未封装**；另 `search.query` 走 `/knowledge-search/query` 别名而非 `/universal-search`，且未透传检索增强参数。
- 完善落地（SDK 14→16 工具/命令，覆盖全部 15 条业务路由 + 2 系统接口）：
  - 模型：`models/parse.py` 新增 `ParseDirectResult`；`models/search.py` 增强 `SearchResult`（qaNote/total/searchType/usedConfig）并新增 `DeepSearchCitation/DeepSearchStep/DeepSearchResult`。
  - 客户端：`client.py` / `async_client.py` 新增 `parse.parse_direct(...)`、`search.deep_search(...)`；`search.query(...)` 补全 teamId/orgId/mode/searchType/relNum/useRerank/score/topK/filters/withCitation/index/isOptimize 并指向 `/universal-search`。
  - MCP：`server.py` 新增 `parse_direct`、`deep_search` 工具，`search_query` 透传增强参数（16 工具）。
  - CLI：`cli/__init__.py` 新增 `parse-direct`、`deep-search` 命令（16 子命令）。
  - 在线测试白名单：CLI 加 `deep-search`、MCP 加 `deep_search`（只读）；parse-direct 属写操作（创建解析任务）按安全设计不进白名单。
  - `scripts/mcp_stdio_smoke.py` expected 工具集 14→16。
- 测试：SDK `pytest sdk/python/tests -q` **134 passed**（新增 parse_direct/deep_search 客户端与 MCP 用例、search 路径/body 断言更新）；平台 `pytest tests -q` **235 passed**（白名单结构断言补 deep-search/deep_search）；`/tmp/manual_conformance.py` 62/62；e2e 35/35。
- 文档：README、`docs/API开发手册.md`（§1.3/§10/§11）、`docs/MCP与CLI接口定义.md`（映射表/工具与命令清单/§7 验证/§9 白名单）、`docs/管理Portal设计.md`（§3.4 白名单）、`docs/开放平台SDK集成设计.md`、`sdk/python/README.md` 全部 14→16 并补 parse-direct/deep-search 说明。
- 下一步：提交推送（github）。

### 任务：排查「最后几次在线测试返回错误」根因并修复环境（2026-08-18 16:xx）

- 现象：Portal 在线测试（MCP/CLI）最近几次返回错误；用户提供 token `4DvPz…`（截断展示）。
- 根因（三层证据）：
  1. **端口被旧实例占用**：`/tmp/openikc_platform.log` 显示新实例 `address already in use`；旧 uvicorn（PID 121657，16:03 启动，`--reload`，`scripts/start_open_platform.sh` 启动）一直占用 18000，其 `OPEN_PLATFORM_ADMIN_TOKEN` 为脚本随机生成（`ac2dfc5a…`），且**未配置 `OPEN_PLATFORM_TOKEN`**。
  2. **业务 token 鉴权回落到 SQLite**：未配环境 token 时 `is_token_valid` 走管理面 DB；`data/open_ikc_platform.db` 中用户 token `4DvPz…` 对应记录 id=2 状态为 `revoked`（仅 id=3 新 token active）→ CLI/MCP 子进程带用户 token 调业务接口一律 `100401`（日志 16:12:51 `request unauthorized POST /api/v1/knowledge-bases/query` 复现）。
  3. **admin token 错位**：Portal 登录用的 admin token 若 ≠ 旧实例随机值 → 管理面直接 `100401`（curl 复现 `test-admin-token` 被拒）。
- 修复：停旧实例（kill 121657/121662），用 `OPEN_PLATFORM_TOKEN=4DvPz…` + `OPEN_PLATFORM_ADMIN_TOKEN=test-admin-token` 以 `setsid nohup` 后台重启（进程 125919，日志 `/tmp/openikc_platform.log`），env token 优先于 DB 鉴权。
- 验证（全绿）：
  - 在线测试复跑：`/admin/test/cli` kb-list `000000` ok=true、`/admin/test/mcp` sys_catalog `000000`（16 tools）、业务直连 `000000`、错误 admin token `100401`。
  - E2E `/tmp/mcp_cli_e2e.py` **35/35**（报告重新生成）。
  - 平台全量 `pytest tests -q` **235 passed**（沙箱外执行）。
- 环境注意：**Codex 沙箱内 pytest/TestClient 会死锁**（anyio portal 线程在 bwrap 沙箱内 select 挂起，最小 FastAPI TestClient 亦复现），跑 pytest 必须在沙箱外（escalated）。
- 下一步：Portal 登录 admin token 统一使用 `test-admin-token`；提交推送（github）。

### 任务：新增文档上传端点（7 天暂存 + 临时访问地址）（2026-08-18）

- 需求：增加文档上传端点，提供 7 天暂存服务，返回临时访问地址。
- 落地（文档能力域，不新增第五类能力）：
  - `POST /api/v1/knowledge-documents/upload`：multipart/form-data 上传单文件，平台暂存 7 天（`OPEN_PLATFORM_UPLOAD_TTL_SECONDS` 默认 604800），返回 `{fileId, fileName, fileSize, contentType, tempUrl, expiresAt, expiresInSeconds}`；支持扩展名白名单（pdf/doc/docx/xls/xlsx/ppt/pptx/txt/md/csv/html/htm/xml/json/yaml/yml/zip/rar/7z），大小上限默认 100 MB（`OPEN_PLATFORM_UPLOAD_MAX_BYTES`）。
  - `GET /api/v1/knowledge-documents/upload/{file_id}`：二进制流访问暂存文件（唯一非 JSON 业务端点），需 Bearer；仅创建者可访问（100403），不存在 100404，过期/清理 200013；过期惰性清理（上传/访问时触发）。
  - 实现：`app/services/upload_store.py`（落盘 + JSON 侧车元数据 + TTL 清理）、`app/services/upload.py`、`app/core/responses.py::document_upload_response`、`app/schemas/document.py::DocumentUploadData/Response`、路由、catalog 同步；错误码新增 `200012`（上传失败）/`200013`（暂存文件过期）；pyproject 补 `python-multipart` 依赖声明。
  - 设计决策：暂存文件归属调用方身份，仅创建者可访问（与 parse-direct 一致）；TTL 默认 7 天可配；上传不建库不登记文档。
- 文档：README（能力表 文档 3→5、实现状态、环境变量）、`docs/API开发手册.md`（§5.4 错误码、§5.5 AUTHZ 动作表、§6.2.4/6.2.5）、`docs/开放平台接口详细定义_精简版_V2.md`（B-02.2）。
- 验证：平台 `pytest tests -q` **249 passed**（新增 `tests/test_document_upload.py` 14 例）；`/tmp/manual_conformance.py` **67/67**（错误码 18→20，新增上传 5 例）；线上冒烟（18000）上传→临时访问→100401/100404/100001 全绿；`/api-manual` 与 `/openapi.json` 已含新增章节/路径。
- 环境：期间发现用户侧 16:30 又启动了 `scripts/start_open_platform.sh` 实例（随机 admin token、未配业务 token，同上次根因），已按用户指定 token（4DvPz… + test-admin-token）重启 18000。
- 下一步：MCP/CLI 暂未封装 upload（写操作 + 文件参数，按需补充）；提交推送（github）。

### 任务：知识加工形态（普通解析 / Wiki / 图谱）API 优化方案（2026-08-18）

- 需求：分析「知识加工为 wiki、图谱、普通解析」如何优化当前 API 定义，输出方案，重点分析 wiki 与图谱构建。
- 结论（方案文档：`docs/知识加工形态优化方案_wiki图谱与解析.md`，未落地）：
  - 现状：解析域仅普通解析（json/markdown/text），无 wiki/图谱概念；`resultFormat.type` 混叠「序列化格式」与「加工形态」两维度。
  - 核心设计：引入 `productType`（auto/text/wiki/graph）统一加工形态，wiki/graph 仍属**解析能力域**（不新增第五类能力），复用 parse/parse-direct 任务编排、鉴权与幂等链路。
  - Wiki：`wikiStrategy`（granularity/extractFields/linkMode/dedup/template）+ 页面树/页面/字段/互链产物模型（稳定 ID = docId+stableKey）+ `parse-result/wiki/tree|page` 查询。
  - 图谱：`graphStrategy`（graphScope/schema/extraction/model/identityResolution/minConfidence/maxEntities）+ 节点/边/证据/置信度模型 + `parse-result/graph/stat|nodes|edges|neighbors|export` 查询；schema 为质量闸门，exact 对齐为增量核心。
  - 普通解析配套：resultFormat 语义收敛、download 升级真实产物流、query 返回形态摘要。
  - 分期：P1 productType 协议铺路 → P2 Wiki → P3 图谱 → P4 检索消费侧（依赖真实后端）。
  - 风险：LLM 成本、图谱噪声、kb 级增量合并一致性、能力边界（图谱是否独立域需产品对齐）。
- 下一步：待评审；评审通过后按 P1→P2/P3 落地；提交推送（github）。

### 任务：方向修正——Wiki/图谱定义为「专业库形态」（2026-08-18 续）

- 用户决策：wiki、图谱**不是解析产物形态，而是专业的知识库形态（专业库）**。
- 方案重构（覆盖 `docs/知识加工形态优化方案_wiki图谱与解析.md` v2）：
  - 核心：知识库新增形态维度 `kbMode`（text/wiki/graph），与归属维度 `kbType`（personal/team/enterprise）正交；缺省 text 兼容现状。
  - 建库即声明形态：create/update 支持 `kbMode` + `wikiConfig`/`graphSchema`；query/detail 返回形态与配置。
  - 加工联动：`parse`/`ingest-and-parse` 的 `productType` 缺省跟随库形态，显式跨形态拒绝（100001）；免库 `parse-direct` 保留显式 wiki/graph 一次性加工。
  - Wiki 库：库级页面树（跨文档合并，pageId=sha1(kbId+stableKey)），`wiki/tree|page|search` 库级只读接口。
  - 图谱库：库级图谱（graphId=sha1(kbId)，多文档增量融合，entityId=sha1(graphId+type+normalizedName)），`graph/stat|nodes|edges|neighbors|export` 库级接口；graphSchema 为质量闸门，exact 对齐为增量核心。
  - 检索按库形态路由；text↔wiki 可双向、wiki↔graph 默认拒绝（建议新增 200014 形态冲突码）。
  - 分期：P1 kbMode 协议 → P2 Wiki 库 → P3 图谱库 → P4 检索消费侧。
- 下一步：方案评审；通过后 P1 先行落地；提交推送（github）。

### 任务：P1 落地——知识库形态协议 kbMode（2026-08-18）

- 落地内容（`docs/知识加工形态优化方案_wiki图谱与解析.md` P1）：
  - 知识库新增形态维度 `kbMode`（text/wiki/graph，默认 text），与 `kbType`（personal/team/enterprise）正交；create/update 支持 `kbMode` + `wikiConfig`/`graphSchema`，query 支持 `kbMode` 过滤，detail/列表返回形态与配置。
  - 校验：`app/schemas/knowledge_base.py` 新增 `validate_wiki_config`（granularity/linkMode/dedup 枚举 + extractFields 数组）与 `validate_graph_schema`（entityTypes/relationTypes 类型必填且不重复、sourceTypes/targetTypes 字符串数组），非法映射 100001。
  - 更新语义：`kbMode`/`wikiConfig`/`graphSchema` 不传=保持不变；wiki↔graph 互转拒绝，新增错误码 `200014` 库形态冲突（进 registry）。
  - 存储：`KnowledgeBaseRecord`/`make_record` 增加 kb_mode/wiki_config/graph_schema；响应 `_knowledge_base_data` 与响应模型同步。
- 验证：`pytest tests -q` **263 passed**（新增 `tests/test_knowledge_base_mode.py` 14 例）；手册一致性 **70/70**（错误码 20→21，新增默认 text/wiki 建库/非法 kbMode 断言）；18001 临时实例冒烟 6/6（默认 text、wiki 库、graph 库、非法 kbMode 100001、wiki→graph 200014、query 按形态过滤）。
- 文档：API 手册 §6.1/§5.4、V2 详细定义 A-01、README（能力总览 + 实现状态）、方案文档 P1 标记落地。
- 环境：18000 第三次被用户侧 `scripts/start_open_platform.sh` 实例占用（随机 admin token、未配业务 token），未再强杀；P1 冒烟在 18001 完成并已停止。用户如需 18000 正常使用，用「业务 token + admin token=test-admin-token」重启。
- 下一步：P2（Wiki 库）/ P3（图谱库）按业务优先级评审后实施；提交推送（github）。

### 任务：P2 落地——Wiki 库（库级页面树 + 检索 + parse 联动 + MCP/CLI 覆盖）（2026-08-18 续）

- 需求：按方案 P2 落地 Wiki 库；保持「MCP/CLI 完整覆盖所有 API」。
- 平台侧（`docs/知识加工形态优化方案_wiki图谱与解析.md` P2 全部落地）：
  - `app/services/wiki_store.py`：`WikiPageRecord` + `WikiPageStore`（原子读写、按稳定键 merge/overwrite/skip 合并、树构建、页面检索、增量废弃）+ `build_document_pages`；页面 ID = `wiki_ + sha1(kbId:stableKey)[:12]` 跨文档/跨构建稳定。
  - `app/services/wiki.py`（`WikiService`：tree/page/search 只读视图 + `build_from_doc` 加工联动）；`app/schemas/wiki.py`（树/页/检索响应模型）；`app/core/responses.py` 三响应构造。
  - 路由（`app/routers/knowledge_base.py` + `app/core/catalog.py`）：`GET /api/v1/knowledge-bases/{kb_id}/wiki/tree|page|search`（只读，AUTHZ 沿用库权限；非 wiki 形态 `100001`、页面不存在 `100404`）。
  - parse 联动：`ParseService` sync 解析成功后按库 `wikiConfig` 自动建页（`_build_wiki_pages_if_wiki_kb`），`ingest-and-parse` 同链路；建页失败不阻断解析主链路（logger warning）。
  - 修复两处实现缺陷：`WikiPageStore` 持锁内再加锁死锁（改 `_find_by_key_locked`）；稳定键恒同 pageId 导致 merge 分支死代码（按稳定键直接合并）；空 q 检索被 normalize 成 "untitled"（改按原始 q 判断）。
- SDK/MCP/CLI（子代理完成，写范围 `sdk/python/**`）：
  - `models/wiki.py`（6 模型）、`client.py`/`async_client.py` 三方法、MCP 三工具（`wiki_tree`/`wiki_page`/`wiki_search`）、CLI 三命令（`wiki-tree`/`wiki-page`/`wiki-search`），工具/命令 16 → 19。
- 平台在线测试白名单：`app/core/admin/mcp_cli_test.py` 补 CLI `wiki-tree`/`wiki-page`/`wiki-search` + MCP `wiki_tree`/`wiki_page`/`wiki_search`（参数级白名单）；`scripts/mcp_stdio_smoke.py` expected 16 → 19。
- 验证（全绿）：
  - 平台 `pytest tests -q` **273 passed**（新增 `tests/test_wiki_library.py` 10 例：形态拒绝/空树/建页/详情/检索/合并/覆盖/分页/catalog）。
  - SDK `pytest sdk/python/tests -q` **148 passed**（原 134 + 新增 14）。
  - 手册一致性 **78/78**（新增 wiki 8 例，覆盖 text 库拒绝、空树、sync 联动建页、页面详情、检索、空 q、catalog 18 条对齐）。
  - 端到端冒烟（临时实例 18001，已停止）：REST 建 wiki 库→ingest→sync parse 建页；CLI `wiki-tree`/`wiki-page`/`wiki-search` 全通；MCP 19 工具齐全，三 wiki 工具 call_tool 全通。
- 文档：API 手册（§6.1.5-6.1.7 wiki 三接口 + §6 全部「接口：」并入正文、§10/§11 工具与命令 16→19）、README（能力 4→7、实现状态 P2）、V2 详细定义（A-05/A-06/A-07）、`docs/MCP与CLI接口定义.md`（映射表/工具清单/白名单）、`docs/管理Portal设计.md`（白名单）、方案文档 P2 标记落地。
- 下一步：P3（图谱库）按业务优先级评审后实施；提交推送（github）。

### 任务：P3 落地——图谱库（库级图谱 + stat/nodes/edges/neighbors/export + parse 联动 + MCP/CLI 覆盖）（2026-08-18）

- 需求：按方案 P3 落地图谱库；保持「MCP/CLI 完整覆盖所有 API」。
- 平台侧（`docs/知识加工形态优化方案_wiki图谱与解析.md` P3 全部落地）：
  - `app/services/graph_store.py`：`GraphNodeRecord`/`GraphRelationRecord` + `GraphStore`（稳定 ID 增量合并、邻域 BFS、统计、jsonl 导出、增量废弃）；稳定 ID：`graphId=graph_+sha1(kbId)[:12]`、`entityId=ent_+sha1(graphId:type:normalizedName)[:12]`、`relationId=rel_+sha1(...)`，`(type,normalizedName)` 为对齐唯一键。
  - `app/services/graph.py`（`GraphService`：stat/nodes/edges/neighbors/export 只读视图 + schema 覆盖率 + `build_from_doc` 联动）；`app/schemas/graph.py`；`app/core/responses.py` 五响应构造。
  - 路由（`app/routers/knowledge_base.py` + catalog）：`GET /api/v1/knowledge-bases/{kb_id}/graph/stat|nodes|edges|neighbors|export`（只读，AUTHZ 沿用库权限；非 graph 形态 `100001`、实体不存在 `100404`、depth 限 1/2）。
  - parse 联动：`ParseService._build_kb_assets_after_parse`（原 wiki 钩子泛化）——wiki 库建页、graph 库建图（占位：单文档生成 schema 首个实体类型节点，真实抽取引擎接入后产出实体/关系）。
- SDK/MCP/CLI（子代理完成，写范围 `sdk/python/**`）：
  - `models/graph.py`（8 模型）、`client.py`/`async_client.py` 五方法、MCP 五工具（`graph_stat`/`graph_nodes`/`graph_edges`/`graph_neighbors`/`graph_export`）、CLI 五命令（`graph-stat`/`graph-nodes`/`graph-edges`/`graph-neighbors`/`graph-export`，`--to-path` 落盘 jsonl），工具/命令 19 → 24。
- 平台在线测试白名单：`app/core/admin/mcp_cli_test.py` 补 CLI graph 五命令 + MCP graph 五工具（参数级白名单）；`scripts/mcp_stdio_smoke.py` expected 19 → 24。
- 验证（全绿）：
  - 平台 `pytest tests -q` **282 passed**（新增 `tests/test_graph_library.py` 9 例：形态拒绝/空统计/建图/邻域 depth1+2/404/过滤/分页/导出/catalog）。
  - SDK `pytest sdk/python/tests -q` **169 passed**（+21）。
  - 手册一致性 **85/85**（新增 graph 7 例，catalog 23 条对齐）。
  - 端到端冒烟（临时实例 18001，已停止；期间发现 P2 遗留实例占用端口导致 404，已清理）：CLI `graph-stat`/`graph-nodes`/`graph-neighbors`/`graph-export --to-path`/`graph-edges` 全通；MCP 24 工具齐全，graph 五工具 call_tool 全通。
- 文档：API 手册（§6.1.8-6.1.12 graph 五接口 + §10/§11 工具与命令 19→24）、README（能力 7→12、实现状态 P3、MCP/CLI 24）、V2 详细定义（A-08~A-12）、`docs/MCP与CLI接口定义.md`（映射表/工具清单/白名单）、`docs/管理Portal设计.md`（白名单）、方案文档 P3 标记落地。
- 下一步：P4（检索消费侧：wiki 页面检索/图谱多跳，依赖真实检索后端）按业务优先级评审后实施；提交推送（github）。

### 任务：新增 process.md 待办清单并在契约中强调「开始读/完成更新」（2026-08-18）

- 需求：将未完成内容写入 `process.md`，并在契约（AGENTS.md）中强调：开始任务时读取、完成任务时更新。
- 落地：
  - 新建根目录 `process.md`：当前未完成事项清单（状态/优先级/事项/下一步），分四类：平台能力（P4 检索消费侧、真实解析引擎、async worker、parse-direct productType、download 产物流）、已知问题/环境遗留（空 kbName 校验、Java SDK 未同步 wiki/graph、E2E 基线、origin 推送权限、18000 用户侧实例、18001 端口管理）、待产品决策（图谱 LLM 成本、图谱域边界）、快速状态。
  - `AGENTS.md`：新增 **§8.3 process.md 待办清单契约（强制）**（任务开始先读、进行中登记、完成时更新、未闭环必须保留、随任务提交）；§10 文档权威顺序加入 process.md/worklog；§12 快速索引加入 process.md。
- 下一步：后续任务开工按 §8.3 先读 process.md；闭环项随任务更新移除。
