# 开放平台 Java SDK 集成设计（open-ikc-sdk / Java）

> 版本：1.0.0
> 状态：已发布（阶段 F 全部落地）
> 适用范围：面向外部 Java 应用的集成客户端 SDK；与平台服务端通过 HTTP 协议解耦，与 Python SDK（`open-ikc-sdk`）同协议、同语义。

## 1. 背景与目标

平台以 FastAPI 提供四类对外业务能力（知识库 / 文档 / 解析 / 检索），统一响应体为
`{errCode, errMsg, data, traceId}`。外部 Java 应用直接调 HTTP 需要自行处理鉴权头、traceId、
统一错误码、重试与超时，成本高且易错。本 SDK 的目标：

1. 封装四类能力为类型安全、可读的 Java 调用，屏蔽 HTTP 细节。
2. 内置 23 位数字 traceId 生成/复用、Bearer 认证、身份头透传（AUTHZ 上下文）。
3. 统一错误码 → 异常层级映射，业务失败与传输失败可区分捕获。
4. 与平台内部实现完全解耦：SDK 只依赖对外 HTTP 协议，不依赖 `app/` 任何内部代码。
5. 生产代码零第三方依赖：HTTP 走 JDK `java.net.http`，JSON 用内置极简解析器。

## 2. 边界与冲突隔离

| 维度 | 约定 |
| --- | --- |
| 写范围 | 仅 `sdk/java/` 与本文档；**不修改** `app/`、`tests/`（平台侧） |
| 依赖 | 生产代码零第三方依赖（`java.net.http` + 手写 JSON 解析/序列化）；测试用 JUnit 5 + JDK `HttpServer` |
| 构建 | Maven，Java 17（`maven.compiler.release=17`），`io.openikc:open-ikc-sdk:1.0.0` |
| 耦合面 | 仅 HTTP 协议：路径 `/api/v1/...`、统一响应壳、错误码、Header 约定（AGENTS.md §3） |
| 运行时契约 | 可选诊断方法 `fetchCatalog()` / `fetchErrorCodes()`，以 `/api/catalog`、`/api/error-codes` 为运行时自检入口 |

## 3. 包结构与命名

```
sdk/java/
  pom.xml                       # io.openikc:open-ikc-sdk:1.0.0，Java 17，JUnit 5.10.2（测试域）
  src/main/java/io/openikc/sdk/
    OpenIKCClient.java          # 主入口：Builder / fromEnv / 四类领域客户端 / raw / fetchCatalog / fetchErrorCodes
    CallerIdentity.java         # 调用者身份（user_id/tenant_id/roles/permissions/deny_permissions/auth_system）
    Envelope.java               # 统一响应壳（errCode/errMsg/data/traceId，isOk()）
    TraceId.java                # 23 位数字 traceId 生成/校验
    OpenIKCError.java           # 根异常（RuntimeException）
    OpenIKCTransportException.java  # 传输层异常（含 traceId）
    OpenIKCConnectionException.java # 连接失败
    OpenIKCTimeoutException.java    # 读超时
    OpenIKCProtocolException.java   # HTTP 状态码/响应体不符统一壳协议
    OpenIKCApiException.java        # 业务异常（errCode/errMsg/traceId）
    ApiExceptions.java              # 错误码 → 具体异常子类（Validation/Unauthorized/Forbidden/NotFound/MethodNotAllowed/Conflict/NotImplemented/System/Business）
    examples/Smoke.java             # 真实平台冒烟（catalog + error-codes + KB query）
  src/main/java/io/openikc/sdk/internal/
    Transport.java              # java.net.http 封装：超时/重试/HTTP 版本/统一壳解析
    HeaderBuilder.java          # 认证/身份/traceId 请求头组装
    Json.java                   # 极简 JSON 解析器
    JsonWriter.java             # 请求体序列化
    EnvelopeParser.java         # 统一响应壳解析
  src/main/java/io/openikc/sdk/model/
    Models.java                 # 泛型数据模型基座（str/integer/number/strList/obj/extra）
    KnowledgeBase.java          # 知识库模型
    Documents.java              # 文档 ingest/get 模型
    Parse.java                  # 解析任务/结果/下载票据/下载结果
    Search.java                 # 检索结果
  src/test/java/io/openikc/sdk/
    TraceIdTest.java            # 4 例：23 位纯数字、唯一性
    EnvelopeTest.java           # 7 例：成功/业务错误/非 JSON
    OpenIKCClientTest.java      # 13 例：JDK HttpServer 起本地假平台，KB create/query/get、错误映射、身份头
```

## 4. 核心对象模型

### 4.1 客户端配置

```java
OpenIKCClient client = new OpenIKCClient.Builder("http://127.0.0.1:18000")
        .token("YOUR_TOKEN")
        .timeoutSeconds(30)          // 读超时，默认 30s
        .maxRetries(2)               // 可重试状态码（502/503/504）重试次数，默认 2
        .identity(CallerIdentity.builder()
                .userId("u1").tenantId("t1").roles(List.of("km_admin")).build())
        .extraHeaders(Map.of("X-Custom", "v"))   // 透传自定义头
        .build();
```

- `fromEnv()`：读 `OPEN_PLATFORM_BASE_URL`（默认 `http://127.0.0.1:18000`）/ `OPEN_PLATFORM_TOKEN`
  （单个）/ `OPEN_PLATFORM_TOKENS`（多个，取第一个）/ `OPEN_PLATFORM_USER_ID` / `OPEN_PLATFORM_TENANT_ID` / `OPEN_PLATFORM_ROLES`。
- 客户端实现 `AutoCloseable`，用完 `close()`。

### 4.2 响应壳与数据模型

`Envelope` 为统一壳：`getErrCode()/getErrMsg()/getData()/getTraceId()/isOk()`（`errCode == "000000"`）。
领域方法返回强类型 POJO（`KnowledgeBase` / `Documents` / `Parse` / `Search`）；`data` 字段通过
`Models` 泛型访问器（`str/integer/number/strList/obj/extra`）容忍字段演进。

### 4.3 异常层级

```
OpenIKCError (RuntimeException)
├── OpenIKCTransportException        # 传输层异常（含 traceId）
│   ├── OpenIKCConnectionException   # 连接失败
│   ├── OpenIKCTimeoutException      # 读超时
│   └── OpenIKCProtocolException     # HTTP 状态码非 2xx 或响应体不符统一壳协议（含 statusCode/body）
└── OpenIKCApiException              # 业务异常（errCode/errMsg/traceId）
    ├── ApiExceptions.ValidationException / UnauthorizedException / ForbiddenException /
    │   NotFoundException / MethodNotAllowedException / ConflictException /
    │   NotImplementedException / SystemException
    └── ApiExceptions.BusinessException   # 其他业务错误码兜底
```

错误码映射：`100001→Validation`、`100401→Unauthorized`、`100403→Forbidden`、`100404→NotFound`、
`100405→MethodNotAllowed`、`100409→Conflict`、`501001→NotImplemented`、`999999→System`，其余→`Business`。

## 5. 请求链路约定

1. 每次请求生成/复用 23 位数字 traceId（`X-Trace-Id` 头）。
2. 有 token 时携带 `Authorization: Bearer <token>`。
3. 身份头透传：`X-User-Id` / `X-Tenant-Id` / `X-User-Roles`（逗号分隔）/ `X-User-Permissions` / `X-User-Deny-Permissions` / `X-Auth-System`。
4. 统一壳 `errCode != "000000"` 时抛对应 `OpenIKCApiException`；`raiseForError=false` 的 `raw()` 逃生口返回原始壳。
5. HTTP 状态 502/503/504 自动重试（默认 2 次，指数退避）。

## 6. 四类能力 API

| 域 | 方法 | 对应平台端点 |
| --- | --- | --- |
| 知识库 | `knowledgeBases().create(...)` / `query(...)` / `queryGet(kbId)` | `POST /api/v1/knowledge-bases/create`、`/query`、`GET .../{kb_id}` |
| 文档 | `documents().ingest(...)` / `get(docId)` | `POST /api/v1/knowledge-documents/ingest`、`GET .../{doc_id}` |
| 解析 | `parse().parse(...)` / `queryResult(docId)` / `issueDownloadTicket(docId)` | `POST /api/v1/knowledge-documents/parse`、`/parse-result/query`、`/parse-result/issue-download-ticket` |
| 检索 | `search().query(...)` | `POST /api/v1/knowledge-search/query` |
| 诊断 | `fetchCatalog()` / `fetchErrorCodes()` | `GET /api/catalog`、`/api/error-codes` |
| 逃生口 | `raw(method, path, pathParams, queryParams, body, raiseForError)` | 任意路径 |

## 7. 超时、重试与幂等

- 连接超时默认 5s，读超时默认 30s（`timeoutSeconds` 可配）。
- 重试仅针对 502/503/504 传输级失败，业务错误（`100401` 等）不重试。
- 幂等由调用方按业务语义处理（平台文档 ingest 等端点本身可重放）。

## 8. 连接关键约定（重要）

- **HTTP 版本必须显式固定 HTTP/1.1**：JDK `java.net.http` 默认带 HTTP/2 优先升级
  （h2c `Upgrade: h2c` 头），而平台 uvicorn + h11 不支持 upgrade，会以
  `Unsupported upgrade request.` / `Invalid HTTP request received.` 直接拒绝（HTTP 400）。
  `Transport` 已固定 `.version(HttpClient.Version.HTTP_1_1)`，勿在自定义 HttpClient 中省略。
- 平台为同步 FastAPI 服务，本 SDK 提供同步入口；无独立异步客户端（Java 侧如需并发可自建线程池调用）。

## 9. 安全

- 无 token 时按平台未认证处理（平台未强制时放行）；token 不在日志打印。
- 不信任远端证书场景不在本 SDK 范围（平台为内网北向 API，默认 HTTP，如走 HTTPS 由调用方配信任链）。

## 10. 测试与验证

```bash
cd sdk/java
mvn test                 # 24 例全绿（TraceId 4 + Envelope 7 + OpenIKCClient 13，本地 JDK HttpServer 假平台）
mvn -q compile exec:java \
  -Dexec.mainClass=io.openikc.sdk.examples.Smoke \
  -Dexec.args="http://127.0.0.1:18000 <token>"   # 对真实平台冒烟：SMOKE OK
```

`OpenIKCClientTest` 用 `com.sun.net.httpserver.HttpServer` 起本地假平台，覆盖 KB create/query/get、
错误码→异常映射、身份请求头透传；`Smoke` 对运行中的 18000 真实平台验证 catalog/error-codes/KB query 全链路。

## 11. 与 Python SDK 对齐

两套 SDK 同协议、同错误码、同请求头约定，接口一一对应：

| 能力 | Python（open_ikc_sdk） | Java（open-ikc-sdk） |
| --- | --- | --- |
| 主客户端 | `OpenIKCClient` / `AsyncOpenIKCClient` | `OpenIKCClient`（同步） |
| 身份 | `CallerIdentity` | `CallerIdentity`（Builder） |
| 响应壳 | `Envelope` | `Envelope` |
| 异常 | `OpenIKCApiException`（errCode 子类） | `OpenIKCApiException` + `ApiExceptions` 子类 |
| traceId | 23 位数字 | `TraceId.generate()` 23 位数字 |
