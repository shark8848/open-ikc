from __future__ import annotations

"""管理面在线测试请求模型（/admin/test/mcp、/admin/test/cli）。"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.admin.mcp_cli_test import DEFAULT_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS

DEFAULT_BASE_URL = "http://127.0.0.1:18000"


class McpTestRequest(BaseModel):
    """MCP 在线冒烟请求：执行 initialize -> list_tools -> call_tool(白名单工具)。"""

    tool: str = Field("sys_catalog", description="MCP 工具名（须在白名单内）")
    args: dict[str, Any] = Field(default_factory=dict, description="工具调用参数（key 须在白名单允许范围）")
    token: str = Field("", description="平台访问 token；为空时沿用平台服务端 token 环境")
    baseUrl: str = Field(DEFAULT_BASE_URL, description="平台地址")
    timeoutSeconds: int | None = Field(
        None,
        ge=1,
        le=MAX_TIMEOUT_SECONDS,
        description=f"子进程超时秒数（默认 {DEFAULT_TIMEOUT_SECONDS}，上限 {MAX_TIMEOUT_SECONDS}）",
    )


class CliTestRequest(BaseModel):
    """CLI 在线测试请求：执行白名单内的只读命令。"""

    command: str = Field(..., description="CLI 命令（须在白名单内）")
    args: list[str] = Field(default_factory=list, description="命令参数（flag 须在白名单允许范围）")
    token: str = Field("", description="平台访问 token；为空时沿用平台服务端 token 环境")
    baseUrl: str = Field(DEFAULT_BASE_URL, description="平台地址")
    identity: dict[str, str] | None = Field(None, description="AUTHZ 身份头映射（user_id/tenant_id/roles）")
    timeoutSeconds: int | None = Field(
        None,
        ge=1,
        le=MAX_TIMEOUT_SECONDS,
        description=f"子进程超时秒数（默认 {DEFAULT_TIMEOUT_SECONDS}，上限 {MAX_TIMEOUT_SECONDS}）",
    )
