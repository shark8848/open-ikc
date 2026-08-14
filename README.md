# open-ikc-api

FastAPI 北向开放平台 API，对外提供四大类业务能力：知识库、文档、解析、检索（均已真实落地，进程内存储实现）。
上层另有 Python SDK（`open-ikc-sdk`）与基于它的 MCP Server / CLI 封装，见「SDK / MCP / CLI 入口」。

## 启动命令

先进入虚拟环境：

```bash
cd /home/open-ikc
. .venv/bin/activate
```

依赖安装（日志链路依赖 `ikc-log-center` SDK，按 pip 安装模式接入，不引用源码目录）：

```bash
pip install -e .
# 日志中心 SDK 从本地 wheel 安装（版本与 pyproject.toml 声明一致）：
pip install /home/ikc-log-center/dist/ikc_log_center-1.4.9-py3-none-any.whl
```

日志通过 `log_center_sdk` 统一输出，trace 上下文自动携带 `traceId`，可在日志中心按链路检索。

日志中心远程投递环境变量（启动脚本已默认开启）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LOG_CENTER_ENABLE` | `true` | 是否启用远程日志投递（异步发送至日志中心） |
| `LOG_CENTER_URL` | `http://127.0.0.1:9315` | 日志中心服务端地址（SDK 自动 POST `{url}/ingest`） |
| `LOG_CENTER_TOKEN` | 空 | 日志中心开启 Bearer 认证时填写 |

平台服务启动：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

一键启动脚本：

```bash
bash scripts/start_open_platform.sh
```

一键停止脚本（按进程匹配 `uvicorn app.main:app`，SIGTERM 优雅停止，最多等待 10 秒）：

```bash
bash scripts/stop_open_platform.sh
```

## 文档入口

- Swagger UI: /docs
- ReDoc: /redoc
- API 浏览页: /api-browser
- 说明：`/docs`、`/redoc` 页面及其静态资源（`/_static/docs/`）全部本地托管，不依赖外部 CDN，离线环境可用
- 管理 Portal: /portal/（首页 `/` 直达；token 管理、端点监控、MCP/CLI 在线测试，侧边栏含 Swagger UI / ReDoc API 文档入口；需 `OPEN_PLATFORM_ADMIN_TOKEN`）
- 错误码目录: /api/error-codes
- AUTHZ 集成设计文档: docs/开放平台统一认证鉴权集成_AUTHZ.md
- AUTHN 集成设计文档: docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md
- SDK 集成设计文档: docs/开放平台SDK集成设计.md
- MCP 与 CLI 接口定义: docs/MCP与CLI接口定义.md
- 管理 Portal 设计: docs/管理Portal设计.md

## SDK / MCP / CLI 入口

- **Python SDK**：`sdk/python/`（包名 `open-ikc-sdk`，导入 `open_ikc_sdk`），封装四大类能力为类型安全调用；使用说明见 [sdk/python/README.md](sdk/python/README.md)。
- **Java SDK**：`sdk/java/`（Maven，Java 17，零第三方依赖，`io.openikc:open-ikc-sdk:1.0.0`），同协议同错误码；使用说明见 [sdk/java/README.md](sdk/java/README.md)，设计见 [docs/开放平台JavaSDK集成设计.md](docs/开放平台JavaSDK集成设计.md)。
- **MCP Server**：`python -m open_ikc_sdk.mcp`（stdio 默认），14 个工具；供 Claude 等 LLM 直接调用平台能力。
- **CLI**：`ikc`（`python -m open_ikc_sdk.cli`），11 个子命令。
- 完整能力映射 / 环境变量 / 工具清单 / 退出码约定见 [docs/MCP与CLI接口定义.md](docs/MCP与CLI接口定义.md)。

## 管理 Portal（/admin/*）

- **管理面 ≠ 业务四类能力**：`/admin/*`（token 管理、监控统计、MCP/CLI 在线测试）是运维管理面，使用独立管理鉴权（`OPEN_PLATFORM_ADMIN_TOKEN`），不进入业务 catalog，不暴露内部流水线接口。
- **Portal 前端**：`portal/`（Vite 8 + React 18 + TS），构建产物 `portal/dist` 由平台静态挂载在 `/portal`。访问 `/portal/` 需输入 `OPEN_PLATFORM_ADMIN_TOKEN`。
- **启用管理面**：配置 `OPEN_PLATFORM_ADMIN_TOKEN` 环境变量；未配置时 `/admin/*` 返回 `503001`（默认关闭，避免暴露）。`bash scripts/start_open_platform.sh` 未配置时自动生成随机 token 并在启动输出打印（显式配置则透传），登录 Portal 以该 token 为准。
- **Token 存储**：SQLite（默认 `data/open_ikc_platform.db`，路径可经 `OPEN_PLATFORM_DB_PATH` 覆盖）；明文 token 仅在创建时返回一次，库中只存 sha256 哈希。

## 错误码与异常

1. 业务层优先抛 `AppException` 或其子类，例如 `KnowledgeBaseException`，用于表达不同领域/层级的异常边界。
2. 推荐用 `error.as_exception(...)` 或 `exception_from_code(...)` 从错误码对象直接生成异常，避免业务层手写字符串。
3. 子类只负责表达层级和边界，错误码对象负责承载默认消息、层级和说明。
4. 应用层统一捕获异常并返回 `errCode`、`errMsg`、`data`。
5. 参数校验错误由全局校验异常处理器统一映射为 `100001`。
6. 文档、解析、检索三个领域后续可分别继承 `DocumentException`、`ParseException`、`SearchException`，保持同一条异常链路。
7. 错误码推荐通过 `BaseErrorCodes.get_by_code(...)` 或 `error_code_catalog()` 查表，便于在日志、文档和调试中统一定位。
8. 线上可直接访问 `/api/error-codes` 获取当前注册的错误码目录。
9. 框架层未知路由/方法不允许（HTTP 404/405）同样映射统一响应体（`100404`/`100405` + `traceId`），保留 HTTP 状态码。
10. `/docs` 不再声明实际不返回的 `422`；校验类错误运行时统一返回 HTTP 200 + `100001`。

## TraceID

1. 所有请求都会注入 23 位纯数字 `traceId`，优先读取请求头 `X-Request-Id`、`X-Trace-Id`、`traceId`、`trace_id`。
2. 响应头会回写 `X-Request-Id` 和 `X-Trace-Id`，响应体顶层会带 `traceId`。
3. 日志上下文通过 `ikc-log-center` 的 SDK 绑定，便于在日志中心按 trace 链路检索。

## TraceID 与日志

1. 所有请求都会在入口生成或透传 `traceId`，并写入 `X-Request-Id` 与 `X-Trace-Id` 响应头。
2. 日志上下文会自动携带当前请求的 `traceId`，便于串联 `ikc-log-center` 风格的链路日志。
3. 若调用方传入 `X-Request-Id`，服务端会优先复用；否则按 23 位数字规则生成。
4. 调用下游接口时应透传同一组追踪头，可复用 `build_trace_headers()`。
5. 未认证（`100401`）响应同样复用调用方传入的 `X-Request-Id` / `X-Trace-Id`，缺失时生成 23 位数字 `traceId`。

下游透传示例：

```python
from app.core.trace import build_trace_headers

headers = {
	"Authorization": "Bearer xxx",
	**build_trace_headers(),
}
# requests.post(url, json=payload, headers=headers, timeout=5)
```

## 鉴权要求

1. 开放平台要求每次请求都携带 `Authorization: Bearer <token>`。
2. 若未携带或格式错误，接口统一返回 `100401`，并返回当前请求 `traceId`。
3. 可通过环境变量配置服务端 token：
	- `OPEN_PLATFORM_TOKEN`：单个 token
	- `OPEN_PLATFORM_TOKENS`：多个 token，逗号分隔
4. 若未配置上述环境变量，服务端仍会强制要求 Bearer token 存在，但不做值比对。
5. API 文档端点 `/docs`、`/redoc`、`/openapi.json` 及其子路径（含尾斜杠写法）免 token 校验，便于接口浏览。

## 认证模式（OAuth2 / SSO）

1. 通过 `OPEN_PLATFORM_AUTH_MODE` 切换认证模式：
	- `static`：兼容当前 Bearer token 模式
	- `gateway_header`：企业网关注入身份头
	- `oidc_jwt`：本地 JWKS 验签 JWT
	- `oauth2_introspection`：远程 introspection 校验 token
2. 认证中间件会把身份写入 `request.state.identity` 和 `request.state.permissions`，供 AUTHZ bridge 复用。
3. 具体流程图和配置清单见 `docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md`。

> ⚠️ **部署安全边界**：`static` 模式直接采信 `X-User-Id/X-User-Roles` 等身份头，**仅限内网/测试环境**；
> 生产必须使用 `gateway_header`（由可信网关完成认证并剥离/覆盖客户端伪造头）或 `oidc_jwt`/`oauth2_introspection`（服务端验签 token 派生身份）。

## 访问地址

- 平台服务: http://127.0.0.1:18000
- Swagger UI: http://127.0.0.1:18000/docs
- ReDoc: http://127.0.0.1:18000/redoc
- API 浏览页: http://127.0.0.1:18000/api-browser

## 模块职责（当前重构）

1. `app/main.py`：应用入口，仅创建 `app` 实例。
2. `app/core/app_factory.py`：应用装配（FastAPI 配置、SDK、路由、中间件、异常处理注册）。
3. `app/core/middlewares.py`：Trace 与 Token 中间件。
4. `app/core/security.py`：Token 提取、配置、校验、未认证响应构造。
5. `app/core/exception_handlers.py`：全局异常处理注册（含管理面 `AdminDisabledError` → `503001`）。
6. `app/core/system_routes.py`：系统路由（`/`、`/health`、`/api-browser`、`/api/catalog`、`/api/error-codes`）。
7. `app/core/api_browser.py`：API 浏览页 HTML 渲染。
8. `app/core/admin/`：管理面（独立 `OPEN_PLATFORM_ADMIN_TOKEN` 鉴权）——token 存储（SQLite）、请求监控统计、MCP/CLI 在线测试；路由见 `app/routers/admin.py`（`/admin/*`），不进入业务 catalog。

## 当前实现进度

1. 知识库 `create` / `update` / `query` / `{kb_id}` 已真实落地：进程内存储（`app/services/knowledge_base_store.py`）+ 业务校验 + AUTHZ 接入。
2. 创建返回真实 `kbId`（`kb_` + 17 位数字）与 UTC 时间；同范围（personal 按 owner、team 按 teamId、enterprise 按 orgId/租户）`kbName` 重复返回 `100409`。
3. 更新需知识库存在（否则 `100404`）；个人库仅创建者可修改/访问（否则 `100403`）；企业库无法识别组织授权时返回 `100403`。
4. 列表查询按调用方数据范围收敛：个人库仅本人、团队库需 `teamId`、企业库按 `orgId` 或调用主体租户。
5. 文档域 `ingest` / `ingest-and-parse` / 查询文档信息（`GET /{doc_id}`）已真实落地：进程内文档存储（`app/services/document_store.py`）+ 知识库归属校验 + 幂等登记 + AUTHZ 接入；返回真实 `ing_`/`doc_` 任务与文档 ID。
6. 解析域四接口已真实落地：`POST /parse`（async 返回 queued 任务、sync 返回内联结果）、`GET /parse-result/query`、`GET /parse-result/issue-download-ticket`、`GET /parse-result/download`；进程内解析任务/结果/凭证存储（`app/services/parse_store.py`）+ 文档归属与数据范围校验 + 幂等 + AUTHZ 接入；新增解析域错误码 `200003`/`200004`/`200011`。下载接口在真实结果存储落地前返回统一体（含下载说明）。
7. 检索域 `POST /knowledge-search/query` 已真实落地：进程内检索索引（`app/services/search_store.py`，关键词命中打分 + 元数据过滤 + topK 截断）+ 知识库存在性与数据范围校验（个人库仅创建者可检索，团队库需 `teamId`、企业库按 `orgId` 或调用主体租户收敛）+ AUTHZ 接入（多库逐库授权，任一库失败整体拒绝）；`mode=search` 返回证据列表、`mode=qa` 附带占位回答（真实问答引擎接入后替换）。检索索引在真实索引引擎落地前由调用方显式注入，不随 ingest/parse 自动构建。

## 完成后自动审查（Claude Code）

任务收尾且测试通过后，可运行 `scripts/review_with_claude.sh` 自动调用 Claude Code headless（`claude -p`）对当前改动做只读代码+安全审查，报告输出到 `docs/code-review_<日期>.md`（默认审查未提交改动，工作区干净时回退最近一次提交）。

- 审查 prompt 强制只读，不修改文件，可与并行开发安全共存。
- 环境变量 `OPEN_PLATFORM_AUTO_REVIEW=false` 可跳过自动审查；`CLAUDE_BIN` 可覆盖 claude 可执行文件路径。
- 约定详见 `AGENTS.md` §13。

## 统一认证鉴权集成层（独立）

为适配“两个系统权限 schema 差异明显”的场景，新增了独立的统一认证鉴权集成层，不与现有 middleware 的 trace/token 逻辑交叉。

1. `app/core/authz/schema.py`：统一权限语义模型（身份、权限事实、授权请求、授权决策）。
2. `app/core/authz/adapters.py`：外部系统权限 schema -> 统一语义的适配器。
3. `app/core/authz/policy.py`：统一策略引擎（deny-overrides）。
4. `app/core/authz/service.py`：统一服务门面（注册适配器并执行授权）。
5. `app/core/authz/bridge.py`：业务桥接层（按请求上下文/Header 组装授权输入，不侵入 middleware）。
6. 数据权限已支持条件约束：资源 ID 范围、owner-only、组织路径、部门、租户集合。
7. 运行时内置两个适配系统：`default` 与 `digital_employee`（通过 `X-Auth-System` 或 `OPEN_PLATFORM_AUTH_SYSTEM` 选择）。

示例：

```python
from app.core.authz import AuthIntegrationService, AuthorizationRequest, MappingAuthzAdapter

service = AuthIntegrationService()
service.register_adapter(
	"system_a",
	MappingAuthzAdapter(
		"system_a",
		identity_mapping={"user_id": "uid", "tenant_id": "tenant", "roles": "roles"},
		role_action_mapping={"km_reader": ["search:query"], "km_admin": ["*:*"]},
	),
)

decision = service.authorize(
	system_name="system_a",
	raw_identity={"uid": "u100", "tenant": "t1", "roles": ["km_reader"]},
	raw_permissions={"roles": ["km_reader"], "permissions": []},
	request=AuthorizationRequest(action="query", resource_type="search"),
)
```

业务桥接示例（独立于 middleware）：

```python
from app.core.authz import AuthIntegrationService, AuthzBridge

bridge = AuthzBridge(AuthIntegrationService())
decision = bridge.authorize_request(
	request=request,
	system_name="system_a",
	action="query",
	resource_type="search",
)
bridge.require_allowed(decision)
```

运行时接入（不修改 middleware）：

1. 通过环境变量 `OPEN_PLATFORM_AUTHZ_ENABLED=true` 开启细粒度授权。
2. `POST /api/v1/knowledge-bases/create`、`POST /api/v1/knowledge-bases/update`、`POST /api/v1/knowledge-search/query` 已接入 `authorize_or_raise(...)`。
3. 默认适配器系统名为 `default`，可通过请求头 `X-Auth-System` 指定系统。
4. 数字员工系统可直接使用 `X-Auth-System: digital_employee`，并按文档配置角色动作映射。
5. 可通过请求头传入授权事实（示例）：
	- `X-User-Id`
	- `X-Tenant-Id`
	- `X-User-Roles`（如 `km_reader`）
	- `X-User-Permissions`
	- `X-User-Deny-Permissions`
6. 检索路由会把请求体中的 `kbId/kbIds`、`ownerId`、`orgPath` 注入授权上下文，用于数据权限匹配。
