# open-ikc-sdk

OpenIKC 开放平台（知识库 / 文档 / 解析 / 检索）应用集成 SDK。

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
- [x] 检索：`search.query`（M4；平台占位期调用返回 `OpenIKCNotImplementedError`）
- [x] 异步客户端：`AsyncOpenIKCClient`（M5）

## 联调冒烟

需先启动平台服务（`bash scripts/start_open_platform.sh`）并配置令牌：

```bash
export OPEN_PLATFORM_TOKEN=<token>

# 同步全链路：创建库 → 接入文档 → 解析 → 查询 → 下载 → 检索
python sdk/python/examples/quickstart.py

# 异步客户端示例
python sdk/python/examples/async_quickstart.py
```

冒烟脚本输出 `[1]`~`[8]` 步骤结果；检索接口当前为平台占位（`501001`），脚本会打印提示而非报错。

## 测试

```bash
cd /home/open-ikc
/home/ikc-log-center/.venv/bin/python -m pytest sdk/python/tests -q
```
