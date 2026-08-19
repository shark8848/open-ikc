# Docker 部署与 HAProxy 代理层

> 本文件说明 open-ikc 平台的 Docker 化构建、单镜像栈启动/停止、HAProxy 反向代理拓扑、环境变量与生产加固。
> 配套脚本：`scripts/build_docker.sh`（构建）、`scripts/docker_smoke.sh`（冒烟）、`docker-compose.yml`（编排）、`docker/.env.example`（生产模板）。

## 1. 拓扑与端口

单镜像（`open-ikc-api:1.0.0`）同时包含 FastAPI 平台与 HAProxy 代理层：

```
宿主机 client
  │  http://127.0.0.1:18080          http://127.0.0.1:8404（stats）
  ▼                                  ▼
┌────────────────────────────────────────────────┐
│  容器 open-ikc-app-1                            │
│  HAProxy(:8080 入口 / :8404 stats)              │
│     │ 反向代理（身份头剥离默认启用）              │
│     ▼                                           │
│  uvicorn(127.0.0.1:18000 仅回环，不对外)        │
└────────────────────────────────────────────────┘
```

- **平台 API 不直接暴露**：uvicorn 只监听容器回环 `127.0.0.1:18000`，容器网络内/外部均无法直连；唯一对外入口为 HAProxy。
- 对外端口：`18080`（HTTP 入口，映射容器 `8080`）、`8404`（HAProxy stats UI）。
- 容器内 `8080` 为高位端口，避免非 root（uid 1000）绑定特权端口对运行时内核参数的依赖。

## 2. 构建镜像

```bash
bash scripts/build_docker.sh                 # 准备 wheel 并构建 open-ikc-api:1.0.0
bash scripts/build_docker.sh --wheel-only    # 仅准备 ikc-log-center wheel（不执行 docker build）
bash scripts/build_docker.sh --no-cache      # docker build --no-cache
```

- 多阶段构建：Stage 1 `node:22-alpine` 构建 Portal（`npm ci` + `npm run build`）；Stage 2 `python:3.12-slim` 安装依赖、打包 `docs/`（`/api-manual` 运行时依赖）与 Portal 产物、安装 HAProxy（`apt-get install haproxy gettext`）。
- 私有依赖 `ikc-log-center==1.4.9`（PyPI 不可得）由脚本自动预置：优先使用 `docker/wheels/` 中已有 wheel；缺失时从 `IKC_LOG_CENTER_REPO`（默认 `/home/ikc-log-center`）源码 tag `v1.4.9` 现场构建（UI 产物 `web/dist` 取该仓库当前工作树）。
- 构建需要网络（PyPI、npm registry、基础镜像）；`.dockerignore` 已排除 `.venv/`、`logs/`、`data/`、`portal/node_modules/`、`portal/dist/` 等。
- 镜像内文件：HAProxy 配置模板 `/etc/haproxy/haproxy.cfg.tmpl`、入口脚本 `/usr/local/bin/open-ikc-entrypoint.sh`（启动时 envsubst 渲染 stats 账号，同进程拉起 uvicorn + haproxy，就绪探测 fail-fast，TERM/INT 转发优雅停机）。

## 3. 启动 / 停止 / 升级

```bash
docker compose up -d                # 启动（后台）
docker compose ps                   # 查看状态（health）
docker compose logs -f app          # 查看日志
docker compose down                 # 停止并清理容器/网络（数据卷保留）
```

- 首次启动后等待健康：`docker ps` 中 `open-ikc-app-1` 显示 `(healthy)` 即就绪。
- 升级旧镜像：先 `bash scripts/build_docker.sh`，再 `docker compose up -d --build`（避免复用同 tag 旧镜像）。
- 冒烟验证：`bash scripts/docker_smoke.sh`（8 项断言：`/health`、`/portal`、admin 鉴权、业务 create、`/api-manual`、stats 默认凭据 200/错误 401、容器 IP 连 `18000` 被拒、非 root 运行；`--force-build` 可强制重建）。

## 4. 环境变量

`docker compose` 读取当前 shell 或根目录 `.env`；生产模板见 `docker/.env.example`。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OPEN_PLATFORM_AUTH_MODE` | `static` | 认证模式；生产建议 `gateway_header` / `oidc_jwt` / `oauth2_introspection` |
| `OPEN_PLATFORM_TOKEN` | `test-token` | 业务 API Bearer token（static 模式比对） |
| `OPEN_PLATFORM_ADMIN_TOKEN` | `test-admin-token` | 管理面 `/admin/*` 与 Portal 登录 token；未配置时管理面关闭（`503001`） |
| `OPEN_PLATFORM_AUTHZ_ENABLED` | `false` | 鉴权开关（deny-overrides，开启后默认拒绝） |
| `OPEN_PLATFORM_SEARCH_BACKEND` | `in_process` | 检索下游：`in_process` / `ur` / `openai` |
| `LOG_CENTER_ENABLE` | `false` | 日志中心远程投递（启用前需先部署日志中心并修正 `LOG_CENTER_URL`） |
| `HAPROXY_HTTP_PORT` | `18080` | HAProxy 对外 HTTP 端口（映射容器 `8080`） |
| `HAPROXY_STATS_PORT` | `8404` | HAProxy stats 端口 |
| `HAPROXY_STATS_USER` / `HAPROXY_STATS_PASSWORD` | `admin` / `change-me` | stats UI 登录账号（生产必改；使用默认凭据启动会输出告警） |
| `HAPROXY_INJECT_IDENTITY` | 空 | `1` 时启用 gateway_header 身份头映射（见 §5） |
| `OPEN_PLATFORM_DB_PATH` | `data/open_ikc_platform.db` | SQLite 路径（挂载卷 `app_data` 持久化） |

数据与日志分别挂载到卷 `app_data`（`/app/data`）与 `app_logs`（`/app/logs`）。

## 5. 安全说明与生产加固

1. **唯一入口**：对外只暴露 HAProxy（`18080` / `8404`）；`18000` 仅容器回环，无法被绕过直连。
2. **身份头防伪**：HAProxy 默认剥离客户端伪造的 `X-User-Id` / `X-Tenant-Id` / 角色 / 权限头，防止 static 模式下自报身份越权。
3. **gateway_header 模式**：前置可信网关注入 `X-Auth-*` 头（并剥离客户端伪造的 `X-Auth-*` / `X-User-*` 头），设置 `HAPROXY_INJECT_IDENTITY=1` 后 HAProxy 将 `X-Auth-*` 映射为平台身份头；未设置时身份头全部剥离，请求按未认证（`100401`）拒绝。
4. **生产必改**：`OPEN_PLATFORM_TOKEN` / `OPEN_PLATFORM_ADMIN_TOKEN` / `HAPROXY_STATS_PASSWORD`；建议 `OPEN_PLATFORM_AUTH_MODE=gateway_header`（见 `docker/.env.example`）。
5. **TLS**：对外端口建议置于 TLS 终止网关之后（`docker/haproxy.cfg` 提供 `X-Forwarded-Proto` 透传示例）。
6. **非 root 运行**：容器以 uid 1000（`appuser`）运行；stats 凭据经 envsubst 白名单渲染，不落盘明文。

## 6. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| `docker build` 报 `failed to resolve source metadata` | 基础镜像元数据解析超时（Docker Hub 网络抖动）；重试或网络恢复后 `bash scripts/docker_smoke.sh --force-build` 重建 |
| `docker compose up` 后容器一直 `unhealthy` | 复用了同 tag 旧镜像；执行 `bash scripts/build_docker.sh && docker compose up -d --build` |
| 宿主端口 `18080/8404` 被占用 | 先释放旧栈/进程：`docker compose down`、`ss -ltn \| rg '18080\|8404'` |
| 业务调用报 `100401` | 确认 `Authorization: Bearer <OPEN_PLATFORM_TOKEN>`；gateway_header 模式未注入身份头时按未认证拒绝 |
| `/api-manual` 显示手册缺失 | 镜像未打包 `docs/`（旧镜像）；重建镜像 |
| 平台 `18000` 无法从外部访问 | 预期行为：平台仅容器回环监听，必须经 HAProxy（`18080`）访问 |
