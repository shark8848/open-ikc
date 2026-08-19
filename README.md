# open-ikc-api

> **北向开放平台 API**：面向外部开发者，以统一协议提供**知识库 / 文档 / 解析 / 检索**四大类业务能力。平台不开放内部流水线，开发者通过 REST、SDK、MCP 或 CLI 任意一种方式接入，即可在自己的产品中获得「可检索的企业知识」。

| | |
| --- | --- |
| 语言 / 框架 | Python ≥ 3.12 · FastAPI |
| 默认端口 | `18000` |
| 协议 | HTTPS/HTTP + JSON，统一响应体 `errCode / errMsg / data / traceId` |
| 认证 | `Authorization: Bearer <token>`（static / gateway_header / oidc_jwt / oauth2_introspection） |
| 在线文档 | `/docs`（Swagger）· `/redoc` · `/api-manual`（开发手册） |

## 目录

- [1. 快速开始](#1-快速开始)
- [2. 能力总览](#2-能力总览)
- [3. 文档导航](#3-文档导航)
- [4. SDK / MCP / CLI](#4-sdk--mcp--cli)
- [5. 配置参考](#5-配置参考)
- [6. 协议约定](#6-协议约定)
- [7. 项目结构](#7-项目结构)
- [8. 测试](#8-测试)
- [9. 实现状态](#9-实现状态)
- [10. 协作与审查](#10-协作与审查)

## 1. 快速开始

### 1.1 环境要求

- Python ≥ 3.12；仓库已初始化虚拟环境 `.venv`（`/home/open-ikc/.venv`）。
- 安装依赖（日志链路依赖 `ikc-log-center` SDK，采用 pip 安装模式，勿改为源码目录引用）：

```bash
cd /home/open-ikc
. .venv/bin/activate
pip install -e .
pip install /home/ikc-log-center/dist/ikc_log_center-1.4.9-py3-none-any.whl
```

### 1.2 启动服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

或使用一键脚本（自动导出日志投递、检索后端等变量；未配置管理 token 时自动生成并打印）：

```bash
bash scripts/start_open_platform.sh   # 启动
bash scripts/stop_open_platform.sh    # 停止（按进程匹配 SIGTERM 优雅停止，最多等待 10 秒）
```

### 1.3 验证服务就绪

```bash
curl -s http://127.0.0.1:18000/health
```

期望 HTTP 200，无需 token。

### 1.4 第一次业务调用

配置服务端 token 后调用「创建知识库」：

```bash
export OPEN_PLATFORM_TOKEN=your-token
curl -s -X POST http://127.0.0.1:18000/api/v1/knowledge-bases/create \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: 20260818000000000000001" \
  -d '{"kbName":"产品知识库","kbType":"team","teamId":"team_01"}'
```

响应 `errCode=000000` 即成功，`data.kbId` 为后续步骤的知识库 ID；每次响应都带 23 位数字 `traceId`。

> **下一步**：5 分钟全链路（建库 → 接入文档 → 解析轮询 → 检索）见 [API 开发手册 §2](docs/API开发手册.md)，进阶路线（换用 SDK/CLI、深度检索、生产认证、运维）见 §2.6。

### 1.5 Docker 部署（含 HAProxy 代理层）

一键构建镜像（平台 + HAProxy 代理层**同一镜像** `open-ikc-api:1.0.0`，多阶段构建）：

```bash
bash scripts/build_docker.sh                 # 准备 wheel 并构建镜像
bash scripts/build_docker.sh --wheel-only    # 仅准备 ikc-log-center wheel（不执行 docker build）
```

- 私有依赖 `ikc-log-center==1.4.9`（PyPI 不可得）由脚本自动准备：优先使用 `docker/wheels/` 中已有 wheel，缺失时从 `/home/ikc-log-center` 源码 `v1.4.9` 现场构建（可用 `IKC_LOG_CENTER_REPO` 覆盖路径）。
- 构建需要网络（PyPI 依赖 + npm registry）；`.dockerignore` 已排除 `.venv/`、`logs/`、`data/`、`portal/node_modules/`、`portal/dist/` 等。

启动整栈（HAProxy 代理层 + 平台）：

```bash
docker compose up -d
curl -s http://127.0.0.1:18080/health     # 经 HAProxy 访问平台
```

升级旧镜像时先构建再显式重建（避免复用旧 tag 镜像）：`bash scripts/build_docker.sh && docker compose up -d --build`。

生产环境建议先复制配置模板再启动（`gateway_header` 强认证 + 强 token）：

```bash
cp docker/.env.example .env   # 修改其中 token / stats 密码后执行
docker compose up -d
```

| 组件 | 端口 | 说明 |
| --- | --- | --- |
| HAProxy 代理层（与平台同镜像） | `18080`（HTTP 入口，容器内 `8080`）/ `8404`（stats） | 容器内唯一对外入口，反向代理到仅监听回环 `127.0.0.1:18000` 的 uvicorn；**平台 API 不直接暴露** |
| FastAPI 北向平台 | `18000`（仅容器回环） | 北向 API + `/portal` 管理 Portal + `/docs` 等，只能经 HAProxy 访问 |

> HAProxy stats UI 地址 `http://127.0.0.1:8404/`，默认账号 **`admin` / `change-me`**（可用 `HAPROXY_STATS_USER` / `HAPROXY_STATS_PASSWORD` 修改；使用默认凭据时容器日志会输出告警，生产必改）。

常用环境变量（`docker compose` 读取当前 shell 或 `.env`）：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OPEN_PLATFORM_AUTH_MODE` | `static` | 认证模式；生产建议 `gateway_header` / `oidc_jwt` / `oauth2_introspection` |
| `OPEN_PLATFORM_TOKEN` | `test-token` | 业务 Bearer token（static 模式比对） |
| `OPEN_PLATFORM_ADMIN_TOKEN` | `test-admin-token` | 管理面 `/admin/*` 独立 token；未配置时管理面关闭（`503001`） |
| `HAPROXY_HTTP_PORT` | `18080` | HAProxy 对外 HTTP 端口 |
| `HAPROXY_STATS_PORT` | `8404` | HAProxy stats 端口 |
| `HAPROXY_STATS_USER/PASSWORD` | `admin` / `change-me` | HAProxy stats UI 登录账号（`http://127.0.0.1:8404/`），生产务必修改 |
| `LOG_CENTER_ENABLE` | `false` | 日志中心远程投递（容器内默认关闭，需 `LOG_CENTER_URL` 指向可达服务） |

数据（SQLite）与日志分别挂载到卷 `app_data`（`/app/data`）与 `app_logs`（`/app/logs`）。

> **安全说明**：
> - 拓扑为「单镜像 + HAProxy 反代」：uvicorn 只监听 `127.0.0.1:18000`，对外仅暴露 HAProxy（`8080`/`8404`），平台 API 无法被绕过直连。
> - HAProxy 已默认剥离客户端伪造的身份头（`X-User-Id` / `X-Tenant-Id` / 角色 / 权限），防止 static 模式下自报身份越权。
> - `gateway_header` 模式：前置可信网关注入 `X-Auth-*` 头并剥离客户端伪造的 `X-Auth-*` / `X-User-*` 头，同时设置 `HAPROXY_INJECT_IDENTITY=1`（见 `docker/.env.example`）启用 HAProxy 头映射；未设置时身份头全部剥离，请求按未认证拒绝。
> - 生产必改：`OPEN_PLATFORM_TOKEN` / `OPEN_PLATFORM_ADMIN_TOKEN` / `HAPROXY_STATS_PASSWORD`（默认凭据启动会输出告警）；对外端口建议置于 TLS 终止网关之后。
> - `/api-manual` 依赖 `docs/API开发手册.md`，该目录已随镜像打包（勿从 `.dockerignore` 排除）。

## 2. 能力总览

平台刻意收敛能力面，只对外暴露四类业务能力：

| 能力 | 路由前缀 | 接口数 | 典型场景 |
| --- | --- | --- | --- |
| 知识库 | `/api/v1/knowledge-bases` | 12 | 组织与管理知识空间（个人/团队/企业），支持形态 `kbMode`：文本库 / Wiki 库 / 图谱库；Wiki 库提供 `wiki/*`（页面树/详情/检索），图谱库提供 `graph/*`（摘要/节点/边/邻域/导出） |
| 文档 | `/api/v1/knowledge-documents` | 5 | 接入 URL / 文件 / 目录 / 压缩包为可解析文档；上传文档 7 天暂存并返回临时访问地址 |
| 解析 | `/api/v1/knowledge-documents/parse*` | 5 | 解析为结构化结果，支持异步任务、凭证与下载；支持免知识库独立解析（`parse-direct`） |
| 检索 | `/api/v1/knowledge-search` | 2 + 1 兼容别名 | 普通检索（证据列表）与深度检索（Agentic 多轮 + 带引用回答） |

另有：

- **管理面** `/admin/*`：token 管理、端点监控、MCP/CLI 在线测试，独立 admin 鉴权，不进入业务 catalog。
- **系统路由**：`/health`、`/api/catalog`、`/api/error-codes`、文档页等，免业务鉴权。

**接入方式选型**：

| 方式 | 适合谁 | 起步成本 | 入口 |
| --- | --- | --- | --- |
| REST | 任何语言、curl/Postman 调试、需全量字段控制 | 最低 | §1.4 / 手册 §6 |
| Python SDK | Python 应用（FastAPI/Django/脚本），类型安全 + 异常映射 | 低 | §4 |
| Java SDK | Java 17+ 后端服务，零第三方依赖 | 低 | §4 |
| MCP Server | Claude Desktop / Cursor 等 AI 客户端（26 个工具） | 低 | §4 |
| CLI | 运维脚本、快速验证、CI 冒烟（26 个子命令） | 最低 | §4 |

## 3. 文档导航

### 3.1 在线入口（服务启动后）

| 入口 | 路径 | 说明 |
| --- | --- | --- |
| API 开发手册 | `/api-manual` | 服务端渲染的开发者手册（免鉴权，含快速开始 / 接口参考 / 错误排查） |
| Swagger UI | `/docs` | OpenAPI 交互式调试；页面与静态资源本地托管，离线可用 |
| ReDoc | `/redoc` | OpenAPI 阅读视图 |
| API 浏览页 | `/api-browser` | 平台能力浏览 |
| 业务 API 目录 | `/api/catalog` | 对外业务接口实时目录（与路由保持一致） |
| 错误码目录 | `/api/error-codes` | 当前注册错误码实时查询 |
| 管理 Portal | `/portal/` | token 管理、端点监控、MCP/CLI 在线测试、开发手册应用内页面（需 `OPEN_PLATFORM_ADMIN_TOKEN`） |

### 3.2 仓库文档（docs/）

| 主题 | 文件 |
| --- | --- |
| 实现契约（强制约定） | 根目录 `AGENTS.md` |
| 接口整体方案（V2 精简） | `docs/开放平台接口整体方案_V2_精简.md` |
| 接口详细定义（V2 精简） | `docs/开放平台接口详细定义_精简版_V2.md` |
| 认证集成（AUTHN / OAuth2 / SSO） | `docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md` |
| 鉴权集成（AUTHZ） | `docs/开放平台统一认证鉴权集成_AUTHZ.md` |
| SDK 集成设计 | `docs/开放平台SDK集成设计.md`、`docs/开放平台JavaSDK集成设计.md` |
| MCP / CLI 接口定义 | `docs/MCP与CLI接口定义.md` |
| 管理 Portal 设计 | `docs/管理Portal设计.md` |
| 解析场景分析（需库 / 免库） | `docs/解析场景分析_需库与免库.md` |
| 知识加工与专业库形态方案（文本 / Wiki / 图谱库） | `docs/知识加工形态优化方案_wiki图谱与解析.md` |
| 工作日志（跨天上下文） | `docs/worklog.md` |

> 权威顺序：`AGENTS.md` 与当前代码 > `docs/` 设计文档；接口定义以 `/api/catalog`、`/openapi.json` 实时为准。

## 4. SDK / MCP / CLI

- **Python SDK**：`sdk/python/`（包名 `open-ikc-sdk`），四大能力类型安全封装：同步/异步客户端、异常映射、trace 透传、MCP/CLI 同源；[sdk/python/README.md](sdk/python/README.md)。
- **Java SDK**：`sdk/java/`（Maven，Java 17，零第三方依赖，`io.openikc:open-ikc-sdk:1.0.0`），同协议同错误码；[sdk/java/README.md](sdk/java/README.md)，设计见 [docs/开放平台JavaSDK集成设计.md](docs/开放平台JavaSDK集成设计.md)。
- **MCP Server**：`python -m open_ikc_sdk.mcp`（stdio 默认），26 个工具，供 Claude 等 LLM 直接调用平台能力（含 Wiki 库 `wiki_*` 与图谱库 `graph_*`）。
- **CLI**：`python -m open_ikc_sdk.cli`（安装后 `ikc`），26 个子命令，全局选项 + 退出码约定（含 Wiki 库 `wiki-*` 与图谱库 `graph-*`）。
- 完整能力映射 / 环境变量 / 工具与命令清单 / 退出码约定见 [docs/MCP与CLI接口定义.md](docs/MCP与CLI接口定义.md)。

## 5. 配置参考

### 5.1 认证（AUTHN）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OPEN_PLATFORM_TOKEN` | 空 | 服务端静态 token（单值） |
| `OPEN_PLATFORM_TOKENS` | 空 | 多 token，逗号分隔 |
| `OPEN_PLATFORM_AUTH_MODE` | `static` | `static` / `gateway_header` / `oidc_jwt` / `oauth2_introspection` |
| `OPEN_PLATFORM_GATEWAY_REQUIRE_BEARER` | `false` | `gateway_header` 模式下是否仍强制 Bearer 存在 |
| `OPEN_PLATFORM_AUTH_HEADER_*` | `X-User-Id` 等 | gateway_header 身份头名：`USER_ID`/`TENANT_ID`/`ROLES`/`SCOPES`/`PERMISSIONS`/`DENY_PERMISSIONS` |
| `OPEN_PLATFORM_AUTH_CLAIM_*` | `sub` 等 | oidc_jwt 的 JWT claim 键名：`USER_ID`/`TENANT_ID`/`ROLES`/`SCOPES`/`PERMISSIONS`/`DENY_PERMISSIONS`/`SYSTEM` |
| `OPEN_PLATFORM_OIDC_ISSUER` / `_AUDIENCE` / `_JWKS_URL` / `_ALGORITHMS` | — | oidc_jwt 验签配置（算法默认 `RS256`） |
| `OPEN_PLATFORM_OAUTH2_INTROSPECTION_URL` / `_CLIENT_ID` / `_CLIENT_SECRET` / `_TIMEOUT_SECONDS` | — | oauth2_introspection 配置 |

> ⚠️ **部署安全边界**：`static` 模式直接采信身份头，**仅限内网/测试**；生产必须使用 `gateway_header`（可信网关剥离/覆盖客户端伪造头）或 `oidc_jwt` / `oauth2_introspection`（服务端验签 token 派生身份）。

### 5.2 鉴权（AUTHZ）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OPEN_PLATFORM_AUTHZ_ENABLED` | `false` | 开启细粒度授权；deny-overrides，无命中默认拒绝（`100403`） |
| `OPEN_PLATFORM_AUTH_SYSTEM` | `default` | 授权系统选择（`default` / `digital_employee`），可被请求头 `X-Auth-System` 覆盖 |
| `OPEN_PLATFORM_DEFAULT_ROLE_ACTION_MAPPING` / `OPEN_PLATFORM_DE_ROLE_ACTION_MAPPING` | 内置 | 角色 → `resource:action` 动作映射 |

### 5.3 管理面

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OPEN_PLATFORM_ADMIN_TOKEN` | 空 | 管理面独立 token；**未配置时 `/admin/*` 默认关闭（`503001`）**；启动脚本未配置时自动生成随机值并打印 |
| `OPEN_PLATFORM_DB_PATH` | `data/open_ikc_platform.db` | 管理面 SQLite（token 哈希、请求统计）路径 |

### 5.4 日志与检索

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LOG_CENTER_ENABLE` | `true` | 远程日志投递开关（SDK 异步 POST `{url}/ingest`） |
| `LOG_CENTER_URL` | `http://127.0.0.1:9315` | 日志中心服务端地址 |
| `LOG_CENTER_TOKEN` | 空 | 日志中心开启 Bearer 认证时的 token |
| `OPEN_PLATFORM_SEARCH_BACKEND` | `in_process` | `in_process`（内置检索索引）/ `ur`（universal_retriever）/ `openai`（openai 检索网关） |
| `OPEN_PLATFORM_UR_BASE_URL` | `http://127.0.0.1:8096` | `ur` 后端地址 |
| `OPEN_PLATFORM_OPENAI_SEARCH_BASE_URL` | `http://127.0.0.1:8088/...` | `openai` 后端地址 |
| `OPEN_PLATFORM_KB_INDEX_MAP` | 空 | JSON 对象，显式映射 `kb_id -> index` |
| `OPEN_PLATFORM_SEARCH_TIMEOUT_SECONDS` | `10` | 普通检索下游超时（秒） |
| `OPEN_PLATFORM_DEEP_SEARCH_TIMEOUT_SECONDS` | `60` | 深度检索下游超时（秒） |
| `OPEN_PLATFORM_UPLOAD_DIR` | `data/uploads` | 文档暂存目录（`upload` 接口落盘位置，7 天 TTL） |
| `OPEN_PLATFORM_UPLOAD_TTL_SECONDS` | `604800` | 暂存有效期秒数（默认 7 天），到期惰性清理 |
| `OPEN_PLATFORM_UPLOAD_MAX_BYTES` | `104857600` | 单文件暂存大小上限（默认 100 MB） |

## 6. 协议约定

### 6.1 统一响应体

所有业务响应（成功与失败）统一结构：

```json
{
  "errCode": "000000",
  "errMsg": "success",
  "data": {},
  "traceId": "23位数字"
}
```

- 成功 `000000`；参数错误 `100001`（含 FastAPI/Pydantic 校验，返回 HTTP 200）；未认证 `100401`；无权限 `100403`；资源不存在 `100404`；方法不允许 `100405`；资源冲突 `100409`；未实现占位 `501001`；系统错误 `999999`；管理面未启用 `503001`。
- 完整错误码目录实时查询 `/api/error-codes`。

### 6.2 错误码与异常

1. 业务层优先抛 `AppException` 子类（`KnowledgeBaseException` / `DocumentException` / `ParseException` / `SearchException`），用领域异常表达层级与边界。
2. 推荐用 `error.as_exception(...)` / `exception_from_code(...)` 从错误码对象生成异常，避免业务层手写字符串；错误码经 `BaseErrorCodes.get_by_code(...)` / `error_code_catalog()` 查表。
3. 应用层统一捕获异常并返回统一响应壳；框架层未知路由/方法（HTTP 404/405）同样映射 `100404`/`100405` + traceId，保留 HTTP 状态码。
4. 新错误码必须进入 `error_code_catalog()` registry，并在 `/api/error-codes` 可见。

### 6.3 认证（AUTHN）

1. 每次请求必须携带 `Authorization: Bearer <token>`；缺失或格式错误统一返回 `100401` + traceId。
2. 未配置 token 环境变量时，服务端仍强制 Bearer 存在但不做值比对。
3. 系统路径免业务鉴权：`/docs`、`/redoc`、`/openapi.json`、`/api-manual`、`/api/catalog`、`/api/error-codes`、`/health`、`/admin`、`/portal`（见 `app/core/middlewares.py` 的 `AUTH_EXEMPT_PATHS` / `AUTH_EXEMPT_PREFIXES`）。
4. 认证中间件把身份写入 `request.state.identity` 与 `request.state.permissions`，供 AUTHZ bridge 复用；模式细节见 [AUTHN 设计文档](docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md)。

### 6.4 TraceID 与日志

1. 每个请求注入 23 位纯数字 `traceId`，优先复用请求头 `X-Request-Id` / `X-Trace-Id` / `traceId` / `trace_id`。
2. 响应头回写 `X-Request-Id` 与 `X-Trace-Id`；未认证响应同样携带。
3. 日志经 `ikc-log-center`（`log_center_sdk.get_logger(__name__)`）统一输出，日志上下文自动携带 traceId，可跨链路检索；调用下游时透传同一组追踪头：

```python
from app.core.trace import build_trace_headers

headers = {
    "Authorization": "Bearer xxx",
    **build_trace_headers(),
}
# requests.post(url, json=payload, headers=headers, timeout=5)
```

### 6.5 鉴权（AUTHZ）

- 开启 `OPEN_PLATFORM_AUTHZ_ENABLED=true` 后生效；策略 **deny-overrides**，无命中默认拒绝（`100403` + traceId）。
- 业务接入用 `authorize_or_raise(request, action, resource_type, ...)`（参考 `POST /api/v1/knowledge-search/query`）；授权逻辑不进 middleware。
- 授权事实经请求头注入：`X-User-Id`、`X-Tenant-Id`、`X-User-Roles`、`X-User-Permissions`、`X-User-Deny-Permissions`（头名可经 `OPEN_PLATFORM_AUTH_HEADER_*` 定制）。
- 数据权限上下文：`kb_id`/`kb_ids` 从请求体注入；**`owner_id`/`org_path` 一律取认证身份（`request.state.identity`），请求体 `ownerId`/`orgPath` 不作为授权依据**；`teamId`/`orgId` 作为业务范围声明读取。
- 新接入方优先「适配器 + 映射配置」（`MappingAuthzAdapter`），避免在业务 service 里写第三方字段 if/else；详见 [AUTHZ 设计文档](docs/开放平台统一认证鉴权集成_AUTHZ.md)。

## 7. 项目结构

```
app/
  main.py                 # 应用入口，仅 create_app()
  core/
    app_factory.py        # FastAPI 装配：路由、中间件、异常、SDK
    middlewares.py        # Trace + AuthN 中间件
    security.py           # Token / OAuth2 / OIDC 认证实现
    trace.py              # traceId 生成、绑定、透传头
    error_codes.py        # ErrorCode / AppException / 错误码 registry
    exception_handlers.py # 全局异常 → 统一响应
    responses.py          # 成功/占位响应构造
    catalog.py            # 对外业务 API 目录（与路由一致）
    system_routes.py      # /、/health、/api-browser、/api/catalog、/api/error-codes
    api_browser.py        # API 浏览页
    admin/                # 管理面：auth / monitor / stats / token_store / mcp_cli_test
    authz/                # 独立 AUTHZ 集成层：schema / adapters / policy / service / bridge / runtime
  routers/                # 薄路由：admin / knowledge_base / document / parse / search
  schemas/                # Pydantic 请求/响应模型
  services/               # 业务编排 + 进程内存储
portal/                   # 管理 Portal 前端（Vite 8 + React 18 + TS），产物静态挂载于 /portal
sdk/                      # python/（open-ikc-sdk）、java/（io.openikc:open-ikc-sdk）
scripts/                  # 启动/停止/Docker 构建脚本
Dockerfile                # 平台镜像（多阶段：Portal 前端 + FastAPI 后端）
docker/                   # HAProxy 代理层配置与入口 + 预置依赖 wheel（同镜像）
  haproxy.cfg             # HAProxy 配置模板：前端入口 / 平台后端 / stats（${HAPROXY_STATS_*} 启动时渲染）
  entrypoint.sh           # 容器入口：渲染 haproxy 配置，同进程启动 uvicorn(127.0.0.1:18000) + haproxy
  wheels/                 # ikc-log-center 私有依赖 wheel（build_docker.sh 预置）
docker-compose.yml        # 单镜像编排（HAProxy 对外 18080）
tests/                    # pytest 测试
docs/                     # 方案与 AUTHN/AUTHZ 设计（中文）
```

分层职责：`routers/*` 只做参数校验、鉴权桥接、调 service；`services/*` 做业务规则与编排、抛领域异常；`schemas/*` 只定义模型、无副作用；`core/*` 提供横切能力；`core/authz/*` 独立于 middleware。

## 8. 测试

```bash
cd /home/open-ikc && .venv/bin/python -m pytest tests -q
```

- 每个测试文件自建 `TestClient(app)`；`tests/conftest.py` 的 `isolate_admin_db` fixture 隔离管理面 SQLite，避免跨测试串扰。
- 管理面测试在 `tests/test_admin_*.py`；鉴权免检路径、AUTHZ（deny-overrides、数据权限条件）、错误码 registry 均有对应用例。
- 新增/修改行为必须补测试，约定见 `AGENTS.md` §6。

## 9. 实现状态

| 能力 | 状态 |
| --- | --- |
| 知识库 | 已落地：进程内存储 + 业务校验 + AUTHZ；创建返回真实 `kbId`，同名冲突 `100409`，个人/团队/企业库按数据范围收敛；`kbMode`（text/wiki/graph）形态协议 + `wikiConfig`/`graphSchema` 配置与校验，wiki↔graph 互转拒绝 `200014`（P1）；**Wiki 库已落地（P2）**：库级页面树存储（`pageId=sha1(kbId+稳定键)`）、跨文档 dedup 合并（merge/overwrite/skip）、增量废弃，`wiki/tree|page|search` 只读接口，`sync` 解析成功后自动建页；**图谱库已落地（P3）**：库级图谱（`graphId=sha1(kbId)`）、实体/关系稳定 ID（`(type,normalizedName)` 对齐）、证据挂接与置信度、增量废弃，`graph/stat|nodes|edges|neighbors|export` 只读接口，`sync` 解析成功后自动建图 |
| 文档 | 已落地：`ingest` / `ingest-and-parse` / 详情查询 / 上传暂存（`upload`，7 天 TTL + 临时访问地址，惰性过期清理），知识库归属校验 + 幂等登记 + AUTHZ |
| 解析 | 已落地：异步任务与内联结果、结果查询 / 下载凭证 / 下载，进程内任务与结果存储 + AUTHZ；`parse-direct` 免库独立解析（不建库、不登记文档，仅创建者可查询/下载） |
| 检索 | 已落地：普通检索（`universal-search`，后端可切 `in_process` / `ur` / `openai`）+ 深度检索（`deep-search`，依赖下游 DeepSearch）；`/query` 为普通检索兼容别名 |

## 10. 协作与审查

- **实现契约**：见根目录 `AGENTS.md`（能力边界、路由清单、协议、分层、测试与提交约定，所有自动化协作者强制遵守）。
- **自动审查**：行为有改动且测试通过后，可运行 `scripts/review_with_claude.sh` 调用 Claude Code headless 做只读代码+安全审查，报告输出 `docs/code-review_<日期>.md`；`OPEN_PLATFORM_AUTO_REVIEW=false` 可跳过。
- **工作日志**：`docs/worklog.md` 按日期记录任务、决策与下一步；跨天/跨会话开工先读最近条目。
- **提交约定**：任务收尾且测试通过后自动 commit + push（默认推送 `github`，见 `AGENTS.md` §8.2）；不提交 `.venv/`、`logs/`、`__pycache__/`、密钥与真实 token。
