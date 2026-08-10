# open-ikc-sdk

OpenIKC 开放平台（知识库 / 文档 / 解析 / 检索）应用集成 SDK。**v1.0.0**。

设计文档：`docs/开放平台SDK集成设计.md`（仓库根目录）。

## 安装

```bash
pip install sdk/python
```

## 快速开始

```python
from open_ikc_sdk import CallerIdentity, OpenIKCClient

client = OpenIKCClient(
    base_url="http://127.0.0.1:18000",
    token="<OPEN_PLATFORM_TOKEN>",
    identity=CallerIdentity(user_id="u100", tenant_id="t1"),
)

# 创建知识库
kb = client.knowledge_bases.create(
    kbName="产品知识库",
    kbType="team",
    teamId="team_01",
    kbDesc="用于客服问答",
)
print(kb.kbId, kb.createTime)

# 局部更新（SDK 自动合并未变更字段，避免平台重置 kbType/visibility）
kb = client.knowledge_bases.update(kbId=kb.kbId, kbName="产品知识库-客服版")

# 分页查询与详情
page = client.knowledge_bases.query(page=1, pageSize=20, keyword="客服")
detail = client.knowledge_bases.get(kb.kbId)

client.close()
```

## 异步客户端

```python
import asyncio
from open_ikc_sdk import AsyncOpenIKCClient

async def main():
    async with AsyncOpenIKCClient(base_url="http://127.0.0.1:18000", token="...") as client:
        kb = await client.knowledge_bases.create(kbName="产品知识库")
        page = await client.knowledge_bases.query(keyword="产品")
        print(kb.kbId, page.total)

asyncio.run(main())
```

同步与异步客户端共享同一套模型与错误映射；`request`/`raw`/`download` 低层调用、四类领域方法与重试/幂等语义一致。

领域封装方法当前进度：

- [x] 知识库：`knowledge_bases.create / update / query / get`（M2）
- [x] 文档：`documents.ingest / ingest_and_parse / get`（M3）
- [x] 解析：`parse.parse / query_result / issue_download_ticket / download`（M4）
- [x] 检索：`search.query`（M4；平台已真实落地，关键词进程内检索 + 数据权限过滤）
- [x] 异步客户端：`AsyncOpenIKCClient`（M5）

## MCP Server（LLM 工具调用）

将现有 REST 接口封装为 MCP 工具（stdio），供 Claude 等 LLM 直接调用。

```bash
# 安装 MCP 依赖
pip install "sdk/python[mcp]"

# stdio 运行（默认）
python -m open_ikc_sdk.mcp

# 指定参数
python -m open_ikc_sdk.mcp --base-url http://127.0.0.1:18000 --token <token>
```

- 工具清单（14 个）：`kb_create` / `kb_update` / `kb_query` / `kb_get` / `doc_ingest` / `doc_ingest_and_parse` / `doc_get` / `parse_start` / `parse_query` / `parse_issue_ticket` / `parse_download` / `search_query` / `sys_catalog` / `sys_error_codes`。
- 基于 mcp 2.x 的 `MCPServer` API 实现（`list_tools` 异步、`server_info`/`is_error` 等 snake_case 字段），依赖 `mcp>=2.0`。
- 复杂结构参数（`source`、`parseStrategy`、`metadataSchema` 等）在 MCP 中为原生 object/array 类型（mcp>=2.0 按 JSON Schema 校验并反序列化）。
- 完整定义见 `docs/MCP与CLI接口定义.md`；端到端冒烟见下文「MCP stdio 端到端冒烟」。

## CLI（命令行）

将现有 REST 接口封装为命令行子命令：

```bash
# 安装 CLI 依赖
pip install "sdk/python[cli]"

# 模块入口
python -m open_ikc_sdk.cli --help

# 安装后可直接使用（pyproject 注册了 ikc 入口）
ikc kb-list --keyword 产品
ikc kb-get kb_10001
ikc search-query --query "产品能力" --kb-id kb_10001
```

- 全局选项：`--base-url` / `--token` / `--user-id` / `--tenant-id` / `--roles` / `--json` / `--debug`。
- 退出码：`0` 成功；`2` 未认证（100401）；`3` 无权限（100403）；`4` 不存在（100404）；`5` 占位未实现（501001）；`6` 传输错误；`1` 其他业务错误。
- 完整子命令与示例见 `docs/MCP与CLI接口定义.md`。

## 联调冒烟

需先启动平台服务（`bash scripts/start_open_platform.sh`）并配置令牌：

```bash
export OPEN_PLATFORM_TOKEN=<token>

# 同步全链路：创建库 → 接入文档 → 解析 → 查询 → 下载 → 检索
python sdk/python/examples/quickstart.py

# 异步客户端示例
python sdk/python/examples/async_quickstart.py
```

冒烟脚本输出 `[1]`~`[8]` 步骤结果；检索接口已真实落地（关键词进程内检索），全链路真实返回。

### MCP stdio 端到端冒烟

需先启动平台服务（`bash scripts/start_open_platform.sh`）：

```bash
.venv/bin/python scripts/mcp_stdio_smoke.py [--token <token>]
```

以官方 mcp 2.0 `ClientSession` 走完整协议链路：`initialize -> list_tools（14 工具）-> call_tool(sys_catalog) -> call_tool(kb_create)`，验证 MCP Server 对真实平台的端到端可用性。

## 测试

```bash
cd /home/open-ikc
.venv/bin/python -m pytest sdk/python/tests -q
```

SDK 全量测试基线：**130 passed**（含 `test_bootstrap.py` / `test_mcp_tools.py` / `test_cli.py`）。
