# open-ikc-api

FastAPI 预占位框架，当前仅保留四大类对外能力：知识库、文档、解析、检索。

## 启动命令

先进入虚拟环境：

```bash
cd /home/open-ikc
. .venv/bin/activate
```

平台服务启动：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

文档服务命令：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

一键启动脚本：

```bash
bash scripts/start_open_platform.sh
```

## 文档入口

- Swagger UI: /docs
- ReDoc: /redoc
- API 浏览页: /api-browser
- 错误码目录: /api/error-codes
- AUTHZ 集成设计文档: docs/开放平台统一认证鉴权集成_AUTHZ.md
- AUTHN 集成设计文档: docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md

## 错误码与异常

1. 业务层优先抛 `AppException` 或其子类，例如 `KnowledgeBaseException`，用于表达不同领域/层级的异常边界。
2. 推荐用 `error.as_exception(...)` 或 `exception_from_code(...)` 从错误码对象直接生成异常，避免业务层手写字符串。
3. 子类只负责表达层级和边界，错误码对象负责承载默认消息、层级和说明。
4. 应用层统一捕获异常并返回 `errCode`、`errMsg`、`data`。
5. 参数校验错误由全局校验异常处理器统一映射为 `100001`。
6. 文档、解析、检索三个领域后续可分别继承 `DocumentException`、`ParseException`、`SearchException`，保持同一条异常链路。
7. 错误码推荐通过 `BaseErrorCodes.get_by_code(...)` 或 `error_code_catalog()` 查表，便于在日志、文档和调试中统一定位。
8. 线上可直接访问 `/api/error-codes` 获取当前注册的错误码目录。

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
5. `app/core/exception_handlers.py`：全局异常处理注册。
6. `app/core/system_routes.py`：系统路由（`/`、`/health`、`/api-browser`、`/api/catalog`、`/api/error-codes`）。
7. `app/core/api_browser.py`：API 浏览页 HTML 渲染。

## 当前实现进度

1. 知识库 `create` / `update` 已真实落地：进程内存储（`app/services/knowledge_base_store.py`）+ 业务校验 + AUTHZ 接入。
2. 创建返回真实 `kbId`（`kb_` + 17 位数字）与 UTC 时间；同范围（personal 按 owner、team 按 teamId、enterprise 按 orgId/租户）`kbName` 重复返回 `100409`。
3. 更新需知识库存在（否则 `100404`）；个人库仅创建者可修改（否则 `100403`）；企业库无法识别组织授权时返回 `100403`。
4. 其余文档、解析、检索接口仍为 `501001` 预占位。

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

