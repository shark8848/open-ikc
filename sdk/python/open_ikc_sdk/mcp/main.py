from __future__ import annotations

"""MCP Server 运行入口：``python -m open_ikc_sdk.mcp``。

默认 stdio 传输；可通过参数覆盖环境变量（见 open_ikc_sdk._bootstrap）。

示例：
    python -m open_ikc_sdk.mcp
    OPEN_PLATFORM_BASE_URL=http://127.0.0.1:18000 OPEN_PLATFORM_TOKEN=<token> python -m open_ikc_sdk.mcp
"""

import argparse

from .._bootstrap import client_from_env
from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenIKC 开放平台 MCP Server（stdio）")
    parser.add_argument("--base-url", default=None, help="平台地址（默认取 OPEN_PLATFORM_BASE_URL）")
    parser.add_argument("--token", default=None, help="平台访问 token（默认取 OPEN_PLATFORM_TOKEN）")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="MCP 传输方式（默认 stdio）",
    )
    args = parser.parse_args()

    client = client_from_env(base_url=args.base_url, token=args.token)
    server = build_server(client)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
