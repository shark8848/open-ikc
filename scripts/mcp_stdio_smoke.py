#!/usr/bin/env python3
"""MCP stdio 端到端冒烟测试。

以官方 mcp 2.0 ClientSession + stdio_client 作为客户端，连接
``python -m open_ikc_sdk.mcp --transport stdio``，完成完整链路：

  initialize -> list_tools -> call_tool(sys_catalog) -> call_tool(kb_create)

前置条件：平台已在运行（scripts/start_open_platform.sh）。

用法：
  .venv/bin/python scripts/mcp_stdio_smoke.py [--token <token>]

环境变量：
  OPEN_PLATFORM_TOKEN  平台访问 token（默认 test-platform-token，平台缺省测试值）
"""

import argparse
import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _smoke(base_url: str, token: str) -> int:
    env = dict(os.environ)
    env["OPEN_PLATFORM_TOKEN"] = token
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "open_ikc_sdk.mcp",
            "--transport",
            "stdio",
            "--base-url",
            base_url,
        ],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. initialize
            init = await asyncio.wait_for(session.initialize(), 15)
            assert init.server_info.name == "open-ikc", init.server_info
            print("[1/4] initialize ->", init.server_info.name)

            # 2. tools/list
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"[2/4] tools/list -> {len(names)} tools: {','.join(names)}")
            expected = {
                "kb_create", "kb_update", "kb_query", "kb_get",
                "wiki_tree", "wiki_page", "wiki_search",
                "doc_ingest", "doc_ingest_and_parse", "doc_get",
                "parse_start", "parse_direct", "parse_query", "parse_issue_ticket", "parse_download",
                "search_query", "deep_search", "sys_catalog", "sys_error_codes",
            }
            missing = expected - set(names)
            assert not missing, f"missing tools: {missing}"

            # 3. tools/call: sys_catalog（只读）
            res = await session.call_tool("sys_catalog", {})
            assert res.is_error is not True, f"sys_catalog errored: {res}"
            print("[3/4] tools/call sys_catalog -> ok")

            # 4. tools/call: kb_create（写路径，端到端全链路）
            res2 = await session.call_tool(
                "kb_create",
                {"kbName": "smoke-kb-stdio", "kbDesc": "stdio e2e smoke"},
            )
            assert res2.is_error is not True, f"kb_create errored: {res2}"
            print("[4/4] tools/call kb_create -> ok")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP stdio 端到端冒烟")
    parser.add_argument("--base-url", default=os.getenv("OPEN_PLATFORM_BASE_URL", "http://127.0.0.1:18000"))
    parser.add_argument("--token", default=os.getenv("OPEN_PLATFORM_TOKEN", "test-platform-token"))
    args = parser.parse_args()
    return asyncio.run(_smoke(args.base_url, args.token))


if __name__ == "__main__":
    sys.exit(main())
