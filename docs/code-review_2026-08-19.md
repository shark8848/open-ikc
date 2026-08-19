# 代码审查报告：Docker 单镜像化（平台 + HAProxy 同容器）改动

## 结论

本次改动将「双容器（平台 `app` + HAProxy 独立镜像）」合并为「单镜像（uvicorn 仅监听回环 `127.0.0.1:18000`，HAProxy 为唯一对外入口）」。整体是**安全改进**：平台 API 无法被绕过直连、身份头剥离顺序正确（`del-header` 先于 `set-header`）、旧 haproxy 组件镜像引用清理干净、信号转发与优雅停机实现基本正确。

**未发现 P0**。但存在 **2 个 P1**：文档推荐的生产认证模式 `gateway_header` 在默认配置下开箱即破（所有请求 100401）；HAProxy stats 默认凭据 `admin/change-me` 暴露在对外端口。另有若干 P2（低端口绑定、镜像复用、文档残留、测试缺口）。

---

## 问题列表

### P1-1｜推荐生产认证模式 `gateway_header` 开箱即坏（功能陷阱，fail-closed）

- **位置**：`docker/haproxy.cfg:56-72`、`docker/.env.example:4-5`、`README.md:121`（安全说明）
- **依据**：
  1. README §1.5 与 `.env.example` 均推荐生产使用 `OPEN_PLATFORM_AUTH_MODE=gateway_header`，`.env.example` 还设置了 `OPEN_PLATFORM_GATEWAY_REQUIRE_BEARER=true`；
  2. 但 HAProxy 配置默认对 `X-User-Id/X-Tenant-Id/角色/权限` 全部 `del-header`（`haproxy.cfg:58-63`），而 gateway_header 模式的**注入映射是注释掉的**（`haproxy.cfg:67-72`，仅 `X-Auth-* → X-User-*` 示例，未启用）；
  3. 平台侧 `app/core/security.py:152-158`：`gateway_header` 模式读 `X-User-Id` 头，`identity["user_id"]` 为空即 `return None` → 全局 `100401`。
  → 按文档推荐配置部署，**所有请求都会被拒 100401**。
- **加重因素**：单镜像化后 haproxy.cfg 由 volume 挂载改为**烘焙进镜像**（`Dockerfile:51`，compose 不再挂载），启用映射需改文件并**重新构建镜像**——文档未提示这一额外步骤。
- **修复建议**：三种方案择一——(a) 默认启用映射块（用环境变量/`haproxy.cfg` 内开关控制，如 `if { env(ENABLE_GW_MAPPING) ... }`）；(b) 保持默认剥离但将 `.env.example`/README 明确改为「启用 gateway_header 需取消注释映射并重建镜像，且前置网关必须注入 `X-Auth-*` 头」；(c) 提供 `docker/haproxy.cfg` 按环境变量渲染映射段（与 stats 账号同样的 envsubst 模式）。建议至少补充启动时的显式提示。

### P1-2｜HAProxy stats 默认凭据 `admin/change-me` 且端口对外暴露

- **位置**：`docker-compose.yml:43-44`（默认值）、`docker-compose.yml:48-49`（`8404:8404` 发布到宿主）、`docker/haproxy.cfg:83`（`stats auth ${HAPROXY_STATS_USER}:${HAPROXY_STATS_PASSWORD}`）
- **依据**：stats UI（`http://127.0.0.1:8404/`）暴露后端拓扑、各 server 在线/会话/响应时延、连接数等运维信息；若宿主机对公网开放，默认 `admin/change-me` 可被直接登录。README 虽已标注「生产必改」，但属**默认即弱凭据 + 管理端口外露**的组合，且本次拓扑重构后它成了镜像内唯一管理面。该问题在旧双容器架构已存在（非本次回归），但值得一并处理。
- **修复建议**：(a) 容器启动时检测 `HAPROXY_STATS_PASSWORD` 为默认值时向 stderr 打告警并（可选）拒绝启动 stats；或 (b) 默认不发布 stats 端口、仅允许 `docker exec` 内访问；或 (c) stats `bind` 限制到回环并由运维自行 `-p` 暴露。

---

### P2-1｜非 root（uid 1000）绑定特权端口 80，依赖 Docker 内核参数

- **位置**：`Dockerfile:60`（`USER appuser`）、`docker/haproxy.cfg:38`（`bind *:80`）
- **依据**：haproxy 以 uid 1000 运行，绑定 `<1024` 端口需内核 `net.ipv4.ip_unprivileged_port_start=0`。现代 Docker 默认开启该 sysctl，但**硬化 daemon / Podman / 部分容器运行时**会拒绝 → haproxy 启动失败 → `entrypoint.sh` 因 `set -e` 退出 → `restart: unless-stopped` 崩溃循环。
- **修复建议**：容器内改用高位端口（如 `bind *:8080`）由 compose 映射 `18080:8080`；或 Dockerfile 加 `--cap-add=net_bind_service`（compose `cap_add`）；或 README 注明运行环境需放开该 sysctl。

### P2-2｜`docker compose up` 可能复用旧架构的过期镜像，健康检查永久失败

- **位置**：`docker-compose.yml:16-22`（`build` + 固定 `image: open-ikc-api:1.0.0`）
- **依据**：同一 tag 的旧镜像（无 HAProxy、监听 18000）已存在时，`docker compose up -d` 默认**不重建**，直接复用旧镜像。新健康检查改为探测 `127.0.0.1:80`（`docker-compose.yml:55`），旧镜像无人监听 80 → 容器「运行中但永久 unhealthy」，且对外 18080 无服务。README 虽要求先跑 `build_docker.sh`，但用户在升级时仅 `git pull` + `up -d` 即踩坑。
- **修复建议**：compose 服务加 `pull_policy: build`（或 `docker compose up --build` 写进 README 显式命令）；或升级镜像 tag（如 `1.1.0`）强制区分。

### P2-3｜文档残留：README 目录树仍描述双容器拓扑

- **位置**：`README.md:331`（`docker-compose.yml # 整栈编排：app + haproxy`）
- **依据**：本次 diff 已更新 README 的组件表与目录树，但 `docker-compose.yml` 行仍写「app + haproxy（HAProxy 对外 18080）」，与实际单容器拓扑矛盾。
- **修复建议**：改为「单镜像编排（HAProxy 对外 18080）」。

### P2-4｜部署行为变更无任何测试覆盖

- **位置**：`docker/entrypoint.sh`、`Dockerfile`、`docker-compose.yml`（全量）；`tests/` 无 docker/entrypoint/haproxy 相关测试
- **依据**：AGENTS.md 要求「新增/修改行为必须补测试」。本次改动了容器入口（进程编排、就绪等待、信号转发）、端口拓扑（18000→80）、健康检查链路（直连→经 HAProxy），均无自动化验证。特别是「uvicorn 未就绪时 HAProxy 是否 503」「haproxy 崩溃是否触发容器重启」等路径无覆盖。
- **修复建议**：新增一个冒烟脚本（非 pytest 也可）：`build_docker.sh` → 起容器 → 断言 `:18080/health` 200、断言容器内 `18000` 从**外部**不可达、断言 stats 默认凭据登录/拒绝。可挂进 `scripts/` 并在 CI 或 worklog 例行执行。

### P2-5｜入口脚本就绪等待无 fail-fast，uvicorn 失联仅靠健康检查兜底

- **位置**：`docker/entrypoint.sh:17-23`（循环不校验最终结果）、`:26-27`（uvicorn 崩溃后 HAProxy 仍常驻）
- **依据**：健康循环最多 30s 后无条件启动 HAProxy；此后若 uvicorn 崩溃，容器「运行中但 503」，仅 compose healthcheck 能察觉，排障体验差。
- **修复建议**：循环结束后校验 `kill -0 "$APP_PID"` 与 `/health`，失败则打印日志并以非零退出；或将 `wait "$APP_PID"` 放入子 shell，任一方退出即终止整个容器（`trap` 已具备）。

### P2-6｜`option forwardfor` 与前置网关 XFF 可能叠加

- **位置**：`docker/haproxy.cfg:30`（`option forwardfor`）
- **依据**：README 拓扑为「TLS 终止网关 → HAProxy」。若上游网关已注入 `X-Forwarded-For`，HAProxy `forwardfor` 会追加自身视角地址，产生双值 XFF，影响依赖客户端 IP 的日志/限流。属轻微。
- **修复建议**：按需改为 `option forwardfor if-none`（或注释说明叠加语义）。

---

## 非问题确认（审查通过项）

- **回环绑定的安全性**：uvicorn 绑定容器内 `127.0.0.1:18000`，网络命名空间隔离使其他容器/外部均无法直连，与「唯一入口 HAProxy」声明一致（`entrypoint.sh:14`）。
- **身份头剥离顺序**：`del-header`（`haproxy.cfg:58-63`）在（注释的）`set-header` 之前执行，网关注入模式启用后顺序正确；剥离对重复/大小写变体头部均生效。
- **凭据渲染**：`envsubst` 仅替换两个白名单变量，stats 密码含 `$` 等字符不会被二次解释；模板与渲染产物路径（`/etc/haproxy/haproxy.cfg.tmpl` → `/tmp/haproxy.cfg`）对 appuser 可读可写。
- **信号处理**：`trap TERM/INT` 转发至双进程并 `wait` 等待 uvicorn 优雅退出，`|| true` 防竞态，符合容器优雅停机预期。
- **AUTHZ/异常链路/schema**：本改动不触碰业务代码，统一响应体、errCode 链路、AUTHZ 映射均无变化。

---

**建议处理顺序**：先修 P1-1（决定默认启用还是明确文档+启动告警），随后 P1-2（默认凭据防护），再补齐 P2-4 冒烟脚本与 P2-2 的 tag/`--build` 提示，其余 P2 按需。
