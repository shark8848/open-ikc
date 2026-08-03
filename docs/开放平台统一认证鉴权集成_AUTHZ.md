# 开放平台统一认证鉴权集成（AUTHZ）设计与实现

认证层（OAuth2 / SSO）请参考：`docs/开放平台统一认证集成_AUTHN_OAUTH2_SSO.md`。

> 文档日期：2026-08-03  
> 适用范围：开放平台与第三方系统（如数字员工平台）对接  
> 目标：在不改动现有 trace/token 中间件主链路的前提下，提供独立、可插拔、可灰度的细粒度授权能力

## 1. 背景与目标

第三方系统之间的权限体系常见差异：

1. 身份字段不一致：`uid`、`sub`、`employee_no`、`userId`。
2. 角色模型不一致：平台角色、岗位角色、应用角色混用。
3. 权限表达不一致：`resource:action`、scope 字符串、菜单点位、功能码。
4. 组织模型不一致：树形、扁平、多租户混合。

为实现快速集成，开放平台新增独立 AUTHZ 集成层，采用统一语义模型 + 适配器 + 策略引擎 + 业务桥接的方式，将外部差异隔离在适配层。

## 2. 核心设计原则

1. 独立性：AUTHZ 与现有中间件链路解耦，不与 trace/token 验证逻辑交叉。
2. 统一语义：先标准化，再判定，不直接在业务里写第三方 schema 分支。
3. 可灰度：通过开关控制启停，可按路由逐步接入。
4. 可扩展：新增第三方系统只需新增适配器或映射配置。
5. 可观测：所有授权失败进入统一异常链路，输出 `100403` 并携带 `traceId`。

## 3. 模块实现与代码映射

### 3.1 统一语义模型（Schema）

文件：`app/core/authz/schema.py`

1. `IdentityContext`：统一身份上下文（用户、租户、角色、scope、属性、来源系统）。
2. `PermissionFact`：统一权限事实（allow/deny、动作、资源、条件）。
3. `AuthorizationRequest`：授权请求（动作、资源类型、资源标识、上下文）。
4. `AuthorizationDecision`：授权结果（是否允许、原因、命中规则、元数据）。

### 3.2 适配器层（Adapters）

文件：`app/core/authz/adapters.py`

1. `AuthzAdapter` 协议：定义外部 schema 转换的标准接口。
2. `MappingAuthzAdapter`：配置驱动映射器。
3. 支持将第三方 identity/permissions 转换为统一权限事实。

### 3.3 策略引擎（Policy）

文件：`app/core/authz/policy.py`

1. 采用 deny-overrides 策略：先看 deny，再看 allow。
2. 若无命中事实，默认拒绝。
3. 支持资源、动作、租户、角色条件匹配。

### 3.4 服务门面（Service）

文件：`app/core/authz/service.py`

1. `AuthIntegrationService` 管理多系统适配器注册。
2. 对外提供统一 `authorize(...)` 方法。
3. 返回统一 `AuthorizationDecision`，屏蔽外部差异。

### 3.5 业务桥接层（Bridge）

文件：`app/core/authz/bridge.py`

1. `AuthzBridge` 在业务层调用，不改中间件。
2. 支持从 `request.state` 或 Header 自动组装 identity/permissions。
3. `require_allowed(...)` 可直接抛出统一 `100403` 异常。

### 3.6 运行时接入层（Runtime）

文件：`app/core/authz/runtime.py`

1. 开关控制：`OPEN_PLATFORM_AUTHZ_ENABLED`。
2. 默认适配器系统名：`default`。
3. 提供 `authorize_or_raise(...)`，供路由低侵入接入。

### 3.7 当前接入示例路由

文件：`app/routers/search.py`

`POST /api/v1/knowledge-search/query` 已接入细粒度授权示例：

1. 开关关闭：保持原行为（当前占位返回 `501001`）。
2. 开关开启：无授权事实返回 `100403`。
3. 开关开启 + 角色符合：通过授权后进入业务逻辑。
4. 路由会将 `kbId/kbIds/orgPath/ownerId` 传入 `AuthorizationRequest`（`resource_id` + `context`）用于数据权限判定。

## 4. 与现有中间件关系

当前链路分层如下：

1. 中间件层（既有）：trace 注入 + token 验证。
2. 业务层（新增）：authz 细粒度授权。

这意味着：

1. token 验证仍在中间件完成（认证）。
2. authz 在业务路由按需调用（授权）。
3. 两层职责明确，不互相耦合。

## 5. 第三方系统集成流程（通用）

以任意第三方系统为例，推荐步骤：

1. 梳理第三方身份字段与权限字段。
2. 配置 `identity_mapping` 与 `role_action_mapping`。
3. 注册一个系统适配器（system_name 唯一）。
4. 在目标路由调用 `authorize_or_raise(...)` 或 `AuthzBridge.authorize_request(...)`。
5. 灰度验证，逐步扩大路由覆盖。

## 6. 数字员工系统集成示例

假设数字员工平台的上游 Header 约定如下：

1. `X-User-Id`：员工唯一标识。
2. `X-Tenant-Id`：租户标识。
3. `X-User-Roles`：角色列表（逗号分隔），例如 `assistant_reader,assistant_admin`。
4. `X-User-Permissions`：细粒度权限列表（逗号分隔），例如 `search:query,document:read`。

### 6.1 适配器配置示例

```python
from app.core.authz import AuthIntegrationService, MappingAuthzAdapter

service = AuthIntegrationService()
service.register_adapter(
    "digital_employee",
    MappingAuthzAdapter(
        "digital_employee",
        identity_mapping={
            "user_id": "user_id",
            "tenant_id": "tenant_id",
            "roles": "roles",
            "scopes": "scopes",
        },
        role_action_mapping={
            "assistant_reader": ["search:query", "document:read"],
            "assistant_admin": ["*:*"],
        },
        roles_key="roles",
        permissions_key="permissions",
        deny_permissions_key="deny_permissions",
    ),
)
```

### 6.2 路由授权调用示例

```python
from app.core.authz.runtime import authorize_or_raise

# 在具体路由中
authorize_or_raise(
    request=request,
    action="query",
    resource_type="search",
)
```

调用方携带：

1. `Authorization: Bearer <token>`（认证）
2. `X-Auth-System: digital_employee`（可选，指定系统）
3. `X-User-Id`、`X-Tenant-Id`、`X-User-Roles`、`X-User-Permissions`（授权事实）
4. 请求体可携带 `kbId` 或 `kbIds`、`orgPath`、`ownerId`（数据权限上下文）。

### 6.3 决策行为

1. 若角色包含 `assistant_reader`，允许 `search:query`。
2. 若权限命中 deny 规则，优先拒绝。
3. 若无任何匹配规则，默认拒绝并返回 `100403`。

## 7. 运行配置

### 7.1 开启/关闭细粒度授权

```bash
# 关闭（默认）
export OPEN_PLATFORM_AUTHZ_ENABLED=false

# 开启
export OPEN_PLATFORM_AUTHZ_ENABLED=true
```

### 7.2 认证开关与文档端点

认证仍沿用既有中间件逻辑：

1. 除 docs/redoc/openapi 端点外，默认需要 Bearer token。
2. docs 相关端点免 token，便于文档浏览。

## 8. 集成建议与最佳实践

1. 先用角色映射快速上线，再逐步补充权限细化。
2. 高风险动作优先显式 deny 规则。
3. 对接初期保留审计日志，核对 decision.reason 与命中规则。
4. 以系统维度注册适配器，避免多系统规则混在一起。
5. 路由接入遵循“先核心、后边缘”的灰度策略。

## 8.1 数据权限设计（重点）

除了“能不能调用接口”的功能权限，AUTHZ 还支持数据权限约束（能看哪些数据）。

### 数据权限约束字段（PermissionFact.conditions）

1. `allowed_resource_ids`：允许访问的资源 ID 集合（如可访问知识库 ID）。
2. `denied_resource_ids`：禁止访问的资源 ID 集合。
3. `owner_only`：仅资源所有者可访问（通过 `request.context.owner_id` 判定）。
4. `allowed_org_prefixes`：组织路径前缀白名单（通过 `request.context.org_path` 判定）。
5. `allowed_departments`：允许访问的部门集合（通过 `identity.attributes.department` 判定）。
6. `allowed_tenant_ids`：允许访问的租户集合。

### 判定优先级

1. 先匹配动作/资源。
2. 再匹配条件（租户、组织、owner、资源 ID 范围等）。
3. 命中 deny 即拒绝（deny-overrides）。
4. 无命中 allow 时默认拒绝。

多资源语义（`kbIds`）：

1. allow 规则：请求中的每个资源都必须在 `allowed_resource_ids` 内。
2. deny 规则：只要请求中的任一资源命中 `denied_resource_ids` 即拒绝。

### 数据权限示例

```python
from app.core.authz.schema import PermissionFact

facts = [
    PermissionFact(
        effect="allow",
        action="query",
        resource_type="search",
        conditions={
            "allowed_resource_ids": ["kb_10001", "kb_10002"],
            "allowed_tenant_ids": ["t1"],
            "allowed_org_prefixes": ["/集团/销售中心"],
        },
    ),
    PermissionFact(
        effect="deny",
        action="query",
        resource_type="search",
        conditions={
            "denied_resource_ids": ["kb_secret_01"],
        },
    ),
]
```

## 8.2 数字员工系统的数据权限对接建议

推荐数字员工系统向开放平台同时传递“身份事实 + 数据范围事实”：

1. 身份事实：`X-User-Id`、`X-Tenant-Id`、`X-User-Roles`。
2. 数据范围事实：
   - `X-User-Permissions`（动作权限）
   - `X-User-Data-Scope`（可选，扩展字段，可编码为 JSON）

如果数字员工已有数据范围模型（例如“本部门可见”“本人可见”“指定知识库可见”），建议在适配器侧映射到上面的 conditions 字段，而不是在业务代码里写分支。

## 9. 常见问题

### 9.1 开启 AUTHZ 后全部拒绝

排查项：

1. 是否正确设置 `X-Auth-System`。
2. 是否对应 system_name 已注册适配器。
3. 传入角色/权限字段是否匹配配置键。

### 9.2 明明有角色却被拒绝

排查项：

1. 角色名大小写是否一致。
2. `role_action_mapping` 是否覆盖目标动作。
3. 是否存在 deny 权限事实触发了优先拒绝。

### 9.3 如何做到无侵入接入更多路由

建议：

1. 先在 service 层封装通用授权函数。
2. 路由仅调用一个授权入口，避免重复代码。
3. 通过配置管理系统扩展适配器，不改主链路。

## 10. 版本与演进

当前版本提供：

1. 独立 AUTHZ 语义层与策略层。
2. 业务桥接 + 运行时开关。
3. `search/query` 路由示例接入。

后续可扩展：

1. 多策略引擎（RBAC + ABAC 组合）。
2. Redis 缓存权限事实。
3. 远程策略中心（统一下发规则）。
4. 组织关系同步与动态角色映射。
