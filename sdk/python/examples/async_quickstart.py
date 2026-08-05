#!/usr/bin/env python3
"""open-ikc-sdk 异步客户端联调示例。

用法：
    export OPEN_PLATFORM_TOKEN=<token>
    python sdk/python/examples/async_quickstart.py
"""

from __future__ import annotations

import asyncio
import os
import time

from open_ikc_sdk import AsyncOpenIKCClient, CallerIdentity


async def main() -> None:
    base_url = os.environ.get("OPEN_PLATFORM_BASE_URL", "http://127.0.0.1:18000")
    token = os.environ.get("OPEN_PLATFORM_TOKEN", "")
    identity = CallerIdentity(user_id="async_user", tenant_id="async_tenant")

    async with AsyncOpenIKCClient(base_url=base_url, token=token, identity=identity) as client:
        kb = await client.knowledge_bases.create(kbName=f"异步冒烟-{int(time.time())}")
        print(f"async create -> kbId={kb.kbId}")
        page = await client.knowledge_bases.query(keyword="异步冒烟")
        print(f"async query -> total={page.total}")


if __name__ == "__main__":
    asyncio.run(main())
