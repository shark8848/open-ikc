# 开放平台 SDK 集成设计（open-ikc-sdk）

> 版本：0.1（设计稿）
> 状态：待评审
> 适用范围：面向外部应用的集成客户端 SDK；与平台服务端通过 HTTP 协议解耦。

## 1. 背景与目标

平台以 FastAPI 提供四类对外业务能力（知识库 / 文档 / 解析 / 检索），统一响应体为
`{errCode, errMsg, data, traceId}`。外部应用直接调 HTTP 需要自行处理鉴权头、traceId、
统一错误码、重试与幂等，成本高且易错。本 SDK 的目标：

1. 封装四类能力为类型安全、可读的 Python 调用，屏蔽 HTTP 细节。
2. 内置 23 位数字 traceId 生成/复用、Bearer 认证、身份头透传（AUTHZ 上下文）。
3. 统一错误码 → 异常层级映射，业务失败与传输失败可区分捕获。
4. 提供同步（`OpenIKCClient`）与异步（`AsyncOpenIKCClient`）两套入口。
5. 与平台内部实现完全解耦：SDK 只依赖对外 HTTP 协议，不依赖 `app/` 任何内部代码。

## 2. 边界与冲突隔离（与逻辑层并行开发约定）

平台逻辑层（`app/`）正由 Claude Code 推进，SDK 开发须严格避免冲突：

| 维度 | 约定 |
| --- | --- |
| 写范围 | 仅 `sdk/`（新目录）与本文档；**不修改** `app/`、`tests/`（平台侧）、`pyproject.toml` |
| 依赖 | 仅第三方 `httpx`；不引入 fastapi / pydantic，不读平台内部模块 |
| 命名 | 包名 `open-ikc-sdk`，导入名 `open_ikc_sdk`，与平台包 `open-ikc-api` 区分 |
| 耦合面 | 仅 HTTP 协议：路径 `/api/v1/...`、统一响应壳、错误码、Header 约定（AGENTS.md §3） |
| 进度解耦 | 平台占位接口（`501001`）在 SDK 表现为 `OpenIKCNotImplementedError`；SDK 按 V2 目标态字段编码，模型带未知字段透传以容忍字段演进 |
| 运行时契约 | 可选诊断方法 `fetch_catalog()` / `fetch_error_codes()`，以 `/api/catalog`、`/api/error-codes` 为运行时自检入口 |

## 3. 包结构与命名

```
sdk/
  python/
    pyproject.toml          # 独立打包：open-ikc-sdk，仅依赖 httpx
    README.md               # SDK 使用说明（快速开始 + 示例）
    open_ikc_sdk/
      __init__.py           # 导出 OpenIKCClient / AsyncOpenIKCClient / 异常 / 模型
      client.py             # 主客户端 + 四类领域子客户端 + raw 逃生口
      transport.py          # 同步/异步 HTTP 传输：超时、重试、连接池
      envelope.py           # 统一响应壳解析（errCode/errMsg/data/traceId）
      errors.py             # 异常层级 + 错误码映射表
      trace.py              # 23 位数字 traceId 生成/复用
      headers.py            # 认证头 + AUTHZ 身份头构建
      models/
        __init__.py
        knowledge_base.py
        document.py
        parse.py
        search.py
    tests/                  # SDK 自测（httpx.MockTransport，无需起服务）
      test_client.py
      test_envelope.py
      test_errors.py
      test_trace.py
      test_retry.py
      test_models.py
```

命名约定：

- SDK 方法名用蛇形（`create_knowledge_base`），请求参数与响应字段**沿用平台 API 的 camelCase**（`kbName`、`kbId`、`docId`…），与接口文档 1:1 对应，避免大小写转换引入歧义。
- 数据模型用 `dataclass` + `from_dict()` 构造；未知字段收进 `extra: dict` 透传，不阻断解析。
- 每个模型带 `to_dict()`，方便日志与二次加工。

## 4. 核心对象模型

### 4.1 客户端配置

```python
OpenIKCClient(
    base_url="http://127.0.0.1:18000",   # 必填，平台服务地址
    token=None,                           # Bearer Token；缺省时读环境变量 OPEN_PLATFORM_TOKEN
    timeout=(5, 60),                      # (连接超时, 读写超时) 秒
    max_retries=2,                        # 传输级重试次数（见 §7）
    identity=None,                        # CallerIdentity，AUTHZ 身份头透传
    extra_headers=None,                   # 自定义头（如 X-Auth-System）
    trace_id=None,                        # 固定 traceId（联调用）；缺省按请求生成
)
```

`CallerIdentity` 与平台常用身份头对应：

| 字段 | Header |
| --- | --- |
| user_id | X-User-Id |
| tenant_id | X-Tenant-Id |
| roles | X-User-Roles（逗号分隔） |
| permissions | X-User-Permissions（逗号分隔） |
| deny_permissions | X-User-Deny-Permissions（逗号分隔） |
| auth_system | X-Auth-System |

仅当字段非空时才发送对应 Header；`extra_headers` 优先级最高。

### 4.2 响应壳与数据模型

```python
@dataclass
class Envelope:
    err_code: str
    err_msg: str
    data: dict
    trace_id: str
```

- `parse_envelope(text)` 解析统一响应壳；`data` 缺省为空 dict。
- 领域模型（示例）：`KnowledgeBase`、`KnowledgeBasePage`、`DocumentIngestResult`、
  `DocumentInfo`、`ParseTask`、`ParseResult`、`DownloadTicket`、`SearchResult`。
- 所有模型字段与 V2 详细定义目标态一致；占位阶段平台返回 `501001` 时 SDK 直接抛异常，
  不依赖占位 data 形状。

### 4.3 异常层级

```
OpenIKCError                      # SDK 所有异常基类
├── OpenIKCTransportError         # 传输层：连接/超时/HTTP 非预期状态
│   ├── OpenIKCConnectionError
│   ├── OpenIKCTimeoutError
│   └── OpenIKCHTTPStatusError    # 非 2xx 且无法解析统一壳（如网关 5xx）
├── OpenIKCAPIError               # 平台返回了统一响应壳但 errCode != 000000
│   ├── OpenIKCValidationError        # 100001 参数校验失败
│   ├── OpenIKCUnauthorizedError      # 100401 未认证
│   ├── OpenIKCForbiddenError         # 100403 无权限
│   ├── OpenIKCNotFoundError          # 100404 资源不存在
│   ├── OpenIKCConflictError          # 100409 资源冲突
│   ├── OpenIKCNotImplementedError    # 501001 平台占位
│   ├── OpenIKCSystemError            # 999999 系统错误
│   └── OpenIKCBusinessError          # 2xxxxx 业务错误或未知错误码（保留 err_code/err_msg/trace_id）
```

- 每个 `OpenIKCAPIError` 携带 `err_code`、`err_msg`、`trace_id`，便于日志定位。
- 调用方可用 `except OpenIKCAPIError` 统一捕获业务失败，或按子类分别处理。
- 未知错误码统一映射为 `OpenIKCBusinessError`，保证不丢失原始信息。

## 5. 请求链路约定

每次请求固定携带：

| Header | 值 | 说明 |
| --- | --- | --- |
| Authorization | `Bearer <token>` | 认证；token 未配置时不发送（服务端仍强制 Bearer，属调用方配置缺失） |
| X-Request-Id / X-Trace-Id | 23 位数字 traceId | 服务端优先复用并回写 |
| Content-Type / Accept | `application/json` | 业务接口 |
| User-Agent | `open-ikc-sdk/<version>` | 便于平台侧排查 |

- traceId：请求级生成，`trace.generate_trace_id()` 输出 23 位纯数字；
  调用方显式传入的 `trace_id` 或 `extra_headers` 中已有 `X-Request-Id` 时优先复用（对齐 AGENTS.md §3.5）。
- 响应对象的 `trace_id` 取自响应壳；响应头回写的 `X-Request-Id`/`X-Trace-Id` 一并透出便于核对。
- 数据权限上下文（`kbId`/`kbIds`、`ownerId`、`orgPath`）由请求体承载，SDK 不做任何改写，原样透传。

## 6. 四类能力 API 设计

统一签名规则：`@dataclass` 请求体可由方法直接展开为关键字参数（camelCase，与平台字段一致），
也可传 `*_Request` 模型对象。以下仅列出展开形式。

### 6.1 知识库（KnowledgeBaseClient）

| 方法 | 对应路由 | 关键参数 |
| --- | --- | --- |
| `create` | POST `/api/v1/knowledge-bases/create` | `kbName`(必填)、`kbType`、`teamId`、`orgId`、`kbDesc`、`bizDomain`、`visibility`、`metadataSchema` |
| `update` | POST `/api/v1/knowledge-bases/update` | `kbId`(必填) + 需更新的字段（局部更新） |

> update 语义：平台对缺省的 `kbType`/`visibility`/`teamId`/`orgId` 会按默认值重置；SDK 采用「先 `get` 拉取现有记录 + 合并未变更字段」实现真正的局部更新，避免误重置。
| `query` | POST `/api/v1/knowledge-bases/query` | `page`、`pageSize`、`kbType`、`teamId`、`orgId`、`keyword` |
| `get` | GET `/api/v1/knowledge-bases/{kb_id}` | `kb_id` |

```python
from open_ikc_sdk import OpenIKCClient

client = OpenIKCClient(base_url="http://127.0.0.1:18000", token="...")
kb = client.knowledge_bases.create(
    kbName="产品知识库",
    kbType="team",
    teamId="team_01",
    kbDesc="用于客服问答",
)
print(kb.kbId, kb.createTime)
```

### 6.2 文档（DocumentClient）

| 方法 | 对应路由 | 关键参数 |
| --- | --- | --- |
| `ingest` | POST `/api/v1/knowledge-documents/ingest` | `reqId`、`kbId`(必填)、`source`(必填)、`teamId`、`orgId`、`docTitle`、`tags`、`metadata`、`orchestrationMode` |
| `ingest_and_parse` | POST `/api/v1/knowledge-documents/ingest-and-parse` | `ingest` 参数 + `parseStrategy`、`resultFormat`、`executeMode` |
| `get` | GET `/api/v1/knowledge-documents/{doc_id}` | `doc_id` |

`source` 为 `DocumentSource`（`type`：url/file/directory/archive；`url`/`objectKey`/`fileToken` 按类型二选一），
与平台 schema 一致。

### 6.3 解析（ParseClient）

| 方法 | 对应路由 | 关键参数 |
| --- | --- | --- |
| `parse` | POST `/api/v1/knowledge-documents/parse` | `reqId`、`kbId`、`docId`、`parseStrategy`、`resultFormat`、`executeMode`、`parseMode`、`chunkStrategy`、`chunkSize` |
| `query_result` | GET `/api/v1/knowledge-documents/parse-result/query` | `taskId`、`docId` |
| `issue_download_ticket` | GET `/api/v1/knowledge-documents/parse-result/issue-download-ticket` | `taskId`、`docId`、`format` |
| `download` | GET `/api/v1/knowledge-documents/parse-result/download` | `ticket`；`to_path` 可落盘；默认返回 `bytes` |

> download 双形态：平台当前返回 JSON 统一壳（`DownloadResult` 占位元数据）；解析结果存储落地后切换为文件流，SDK 返回 `bytes`（`to_path` 可落盘）。

`download` 兼容两种响应形态：`application/json`（统一壳，按错误码抛异常）与原始文件流（目标态，返回字节）。

### 6.4 检索（SearchClient）

| 方法 | 对应路由 | 关键参数 |
| --- | --- | --- |
| `query` | POST `/api/v1/knowledge-search/query` | `query`、`kbId`、`kbIds`、`ownerId`、`orgPath`（对齐平台当前 schema；`mode`/`topK`/`filters`/`withCitation` 等目标态参数已随平台检索域落地，SDK 如需透传可扩展 `query()` 签名） |

`kbId/kbIds/ownerId/orgPath` 同时是平台 AUTHZ 数据权限上下文（AGENTS.md §4.2），SDK 原样透传。

### 6.5 逃生口

```python
envelope = client.raw("GET", "/api/v1/knowledge-bases/{kb_id}", path_params={"kb_id": "kb_1"})
```

- `raw()` 返回 `Envelope`，不抛业务异常（错误码在 `envelope.err_code` 中），供未来新增接口提前适配。
- 仅用于平台已正式开放的能力；第五类对外业务域需平台侧评审通过后才会提供封装方法。

## 7. 超时、重试与幂等

| 项 | 规则 |
| --- | --- |
| 超时 | 连接 5s、读写 60s（可配）；下载接口单独放宽读超时（默认 300s，可配） |
| 重试 | 仅重试传输级失败：连接错误、读/写超时、HTTP 502/503/504；最多 `max_retries`（默认 2）次，指数退避 + 抖动 |
| 不重试 | 4xx、统一壳中的业务错误码（`errCode != 000000`）、下载流已部分读取 |
| POST 幂等 | 默认不重试 POST；调用方显式传入 `reqId`（幂等键）时允许重试，由平台侧去重 |
| 幂等建议 | 文档接入、解析等异步任务类请求，调用方应始终携带 `reqId`（如 `req_<biz>_<uuid>`） |

## 8. 日志与可观测

- 默认使用标准库 `logging`，logger 名 `open_ikc_sdk`；不绑定平台日志体系。
- 每次请求输出一条摘要日志（方法、路径、耗时、HTTP 状态、errCode、traceId），DEBUG 级输出完整头/体摘要（脱敏 Authorization）。
- 提供 `set_log_level()` 便捷方法；集成方如需接 `log_center_sdk`，可通过标准 `logging.Handler` 接入，SDK 不引入额外依赖。

## 9. 安全

1. Token 仅接受运行时注入或环境变量 `OPEN_PLATFORM_TOKEN`，**不落库、不写进日志、不序列化进模型**。
2. `OpenIKCClient` 提供 `__repr__` 脱敏（隐藏 token 明文）。
3. 日志与异常信息脱敏：Authorization、X-User-Permissions 等敏感头不打全量。
4. 传输层默认 `http://` 仅限内网/联调；生产建议 `https://`，SDK 不做强制但文档明示。
5. SDK 不做任何服务端鉴权决策，AUTHZ 由平台侧策略引擎裁决；SDK 仅透传身份头。

## 10. 异步支持

```python
from open_ikc_sdk import AsyncOpenIKCClient

async def main():
    async with AsyncOpenIKCClient(base_url="...", token="...") as client:
        page = await client.knowledge_bases.query(page=1, pageSize=20)
```

- 同步基于 `httpx.Client`，异步基于 `httpx.AsyncClient`，共享同一套模型与错误映射。
- 异步客户端支持 `async with` 上下文管理；同步客户端支持 `with` 关闭连接池。

## 11. 测试与验证

- SDK 单元测试使用 `httpx.MockTransport`，**无需启动平台服务**，覆盖：
  - 统一壳解析（成功/业务错误/未知错误码/非 JSON）
  - 错误码 → 异常映射全表
  - traceId 生成（23 位纯数字）与复用
  - 身份头透传（非空才发送）
  - 重试策略（传输失败重试、业务错误不重试、POST 无 reqId 不重试）
  - 同步/异步行为一致性、模型 `extra` 透传
- 联调验证（可选，平台侧起服务后执行）：提供 `examples/quickstart.py` 与冒烟脚本，
  用 `OPEN_PLATFORM_TOKEN` 走通创建库 → 接入文档 → 解析 → 检索全链路。

## 12. 版本与发布

| 项 | 约定 |
| --- | --- |
| 版本 | 独立语义化版本，初始 `0.1.0`；与平台 `open-ikc-api` 版本号解耦 |
| 兼容 | minor 版本内保持 API 兼容；破坏性变更升 major |
| 发布 | 默认源码形态（`pip install sdk/python` 或拷贝包）；如需私有 index 再行配置，不发布公共 PyPI |
| 文档同步 | SDK 字段变更时同步本设计文档与 `sdk/python/README.md` |

## 13. 里程碑（设计评审后执行）

1. M1：骨架落地——包结构、transport、envelope、errors、trace、headers + 单测。
2. M2：知识库域四方法 + 模型 + 测试（平台已真实实现，可直接联调）。
3. M3：文档域三方法 + 模型 + 测试（平台已落地）。
4. M4：解析/检索域方法 + 模型 + 测试（平台占位期以 `501001` 与 mock 验证）。
5. M5：异步客户端、下载流支持、日志脱敏完善、README 与示例。

> 本设计稿仅定义 SDK 边界与协议，不涉及平台内部实现；若平台对外协议（路径、字段、错误码）调整，
> 以 AGENTS.md 权威顺序（契约 > 代码 > V2 文档）为准同步本文档。
