# open-ikc-sdk（Java）

OpenIKC 开放平台（知识库 / 文档 / 解析 / 检索）应用集成 SDK（Java 版）。**v1.0.0**。
与 Python SDK（`open-ikc-sdk`）同协议、同错误码、同请求头约定。

设计文档：`docs/开放平台JavaSDK集成设计.md`（仓库根目录）。

- Maven：`io.openikc:open-ikc-sdk:1.0.0`
- 要求：Java 17+
- 生产代码**零第三方依赖**：HTTP 走 JDK `java.net.http`，JSON 用内置极简解析器。

## 构建

```bash
cd sdk/java
mvn -q compile          # 编译
mvn -q test             # 24 例测试全绿（本地 JDK HttpServer 假平台）
```

## 快速开始

```java
import io.openikc.sdk.*;

OpenIKCClient client = new OpenIKCClient.Builder("http://127.0.0.1:18000")
        .token("<OPEN_PLATFORM_TOKEN>")
        .identity(CallerIdentity.builder().userId("u100").tenantId("t1").build())
        .build();

// 创建知识库
KnowledgeBase kb = client.knowledgeBases().create(
        "产品知识库", "team", "team_01", null, "用于客服问答");
System.out.println(kb.getKbId() + " " + kb.getCreateTime());

// 分页查询与详情
KnowledgeBase.KnowledgeBasePage page =
        client.knowledgeBases().query(1, 20, null, "客服");
KnowledgeBase detail = client.knowledgeBases().queryGet(kb.getKbId());

client.close();
```

## 从环境变量构建

```bash
export OPEN_PLATFORM_BASE_URL=http://127.0.0.1:18000
export OPEN_PLATFORM_TOKEN=<token>        # 或 OPEN_PLATFORM_TOKENS=a,b,c（取第一个）
export OPEN_PLATFORM_USER_ID=u100
export OPEN_PLATFORM_TENANT_ID=t1
export OPEN_PLATFORM_ROLES=km_admin
```

```java
OpenIKCClient client = OpenIKCClient.fromEnv();
```

## 四类能力

| 能力 | 调用 |
| --- | --- |
| 知识库 | `client.knowledgeBases().create(...)` / `query(...)` / `queryGet(kbId)` |
| 文档 | `client.documents().ingest(...)` / `get(docId)` |
| 解析 | `client.parse().parse(...)` / `queryResult(docId)` / `issueDownloadTicket(docId)` |
| 检索 | `client.search().query(query, kbId, kbIds, topK, mode, filters)` |
| 诊断 | `client.fetchCatalog()` / `client.fetchErrorCodes()` |
| 逃生口 | `client.raw("GET", "/api/v1/...", ...)` |

## 异常层级

- `OpenIKCApiException` 子类：`ValidationException`（100001）/ `UnauthorizedException`（100401）/
  `ForbiddenException`（100403）/ `NotFoundException`（100404）/ `MethodNotAllowedException`（100405）/
  `ConflictException`（100409）/ `NotImplementedException`（501001）/ `SystemException`（999999）/ 其余 `BusinessException`。
- 传输层：`OpenIKCConnectionException` / `OpenIKCTimeoutException` / `OpenIKCProtocolException`。

```java
try {
    client.knowledgeBases().queryGet("no_such_id");
} catch (ApiExceptions.NotFoundException e) {
    System.out.println(e.getErrCode() + " " + e.getErrMsg() + " traceId=" + e.getTraceId());
}
```

## 真实平台冒烟

```bash
mvn -q compile exec:java \
  -Dexec.mainClass=io.openikc.sdk.examples.Smoke \
  -Dexec.args="http://127.0.0.1:18000 <token>"
# [1/3] fetchCatalog -> categories=4
# [2/3] fetchErrorCodes -> codes=15
# [3/3] knowledgeBases().query -> total=0 items=0
# SMOKE OK
```

## 重要约定

- **HTTP 版本固定 HTTP/1.1**：JDK `HttpClient` 默认带 HTTP/2 h2c 升级，而平台 uvicorn/h11 不支持，
  会直接拒绝（`Unsupported upgrade request.` → HTTP 400）。SDK 已显式固定 `HTTP_1_1`，
  自定义扩展时不要省略 `.version(HttpClient.Version.HTTP_1_1)`。
- traceId：每次请求自动生成 23 位数字（`X-Trace-Id`），可用 `Builder.traceId(...)` 固定复用。
- 客户端用完 `close()`。
