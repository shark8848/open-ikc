from __future__ import annotations

"""OpenIKC 开放平台 MCP 封装包（对外接口定义见 docs/MCP与CLI接口定义）。"""

from .server import SERVER_NAME, build_server

__all__ = ["SERVER_NAME", "build_server"]
