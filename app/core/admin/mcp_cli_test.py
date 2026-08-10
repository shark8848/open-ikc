from __future__ import annotations

"""MCP / CLI 在线测试执行器。

- 通过 subprocess 真实执行 SDK 的 MCP / CLI 入口，返回结构化结果（不打印）。
- 命令白名单：仅允许只读/低风险命令与受限参数，禁止任意 shell。
- 超时控制，避免挂死。
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# CLI 白名单：仅只读命令（不含写操作，避免在线测试污染数据）
CLI_WHITELIST: dict[str, list[str]] = {
    "kb-list": ["--page", "--page-size", "--keyword", "--kb-type"],
    "kb-get": [],
    "sys-catalog": [],
    "sys-error-codes": [],
    "search-query": ["--query", "--kb-id", "--kb-ids", "--owner-id", "--org-path"],
}

MCP_TOOL_WHITELIST: set[str] = {
    "sys_catalog",
    "sys_error_codes",
    "kb_get",
    "kb_query",
}

DEFAULT_TIMEOUT_SECONDS = 20


@dataclass
class TestResult:
    """结构化测试结果。"""

    ok: bool
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": self.command,
            "exitCode": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "durationMs": self.duration_ms,
            "detail": self.detail,
        }


def _python_executable() -> str:
    """使用项目虚拟环境的 Python（内含 SDK）。"""
    candidates = [
        os.getenv("OPEN_PLATFORM_PYTHON", ""),
        os.path.join(os.getcwd(), ".venv", "bin", "python"),
        sys.executable,
    ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return sys.executable


def _build_env(*, token: str, base_url: str, identity: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if token:
        env["OPEN_PLATFORM_TOKEN"] = token
    if base_url:
        env["OPEN_PLATFORM_BASE_URL"] = base_url
    identity = identity or {}
    if identity.get("user_id"):
        env["OPEN_PLATFORM_USER_ID"] = identity["user_id"]
    if identity.get("tenant_id"):
        env["OPEN_PLATFORM_TENANT_ID"] = identity["tenant_id"]
    if identity.get("roles"):
        env["OPEN_PLATFORM_ROLES"] = identity["roles"]
    return env


def run_mcp_smoke(
    *,
    token: str = "",
    base_url: str = "http://127.0.0.1:18000",
    tool: str = "sys_catalog",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> TestResult:
    """执行 MCP 端到端冒烟（initialize -> list_tools -> call 指定只读工具）。

    通过 subprocess 启动 ``python -m open_ikc_sdk.mcp --transport stdio``，
    用官方 mcp 2.0 客户端完成协议握手。与 ``scripts/mcp_stdio_smoke.py`` 语义一致。
    """
    if tool not in MCP_TOOL_WHITELIST:
        return TestResult(
            ok=False,
            command=f"mcp smoke (tool={tool})",
            exit_code=None,
            stdout="",
            stderr=f"工具不在白名单: {tool}",
            duration_ms=0,
        )

    script = _MCP_SMOKE_SCRIPT.replace("__TOOL__", tool)
    env = _build_env(token=token, base_url=base_url)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [_python_executable(), "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            cwd=os.getcwd(),
        )
        duration = int((time.monotonic() - start) * 1000)
        ok = proc.returncode == 0
        return TestResult(
            ok=ok,
            command=f"mcp smoke (tool={tool})",
            exit_code=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            duration_ms=duration,
            detail={"tool": tool, "steps": _parse_mcp_steps(proc.stdout)},
        )
    except subprocess.TimeoutExpired:
        duration = int((time.monotonic() - start) * 1000)
        return TestResult(
            ok=False,
            command=f"mcp smoke (tool={tool})",
            exit_code=None,
            stdout="",
            stderr=f"MCP 冒烟超时（>{timeout_seconds}s）",
            duration_ms=duration,
        )


def run_cli_command(
    *,
    command: str,
    args: list[str] | None = None,
    token: str = "",
    base_url: str = "http://127.0.0.1:18000",
    identity: dict[str, str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> TestResult:
    """执行白名单内的 CLI 命令，捕获输出与退出码。"""
    args = args or []
    if command not in CLI_WHITELIST:
        return TestResult(
            ok=False,
            command=command,
            exit_code=None,
            stdout="",
            stderr=f"命令不在白名单: {command}",
            duration_ms=0,
        )
    # 校验参数名均在白名单内
    allowed_flags = CLI_WHITELIST[command]
    for arg in args:
        if arg.startswith("-") and arg not in allowed_flags:
            return TestResult(
                ok=False,
                command=command,
                exit_code=None,
                stdout="",
                stderr=f"参数不在白名单: {arg}（允许: {', '.join(allowed_flags) or '无参数'}）",
                duration_ms=0,
            )

    argv = [_python_executable(), "-m", "open_ikc_sdk.cli", command, *args]
    env = _build_env(token=token, base_url=base_url, identity=identity)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            cwd=os.getcwd(),
        )
        duration = int((time.monotonic() - start) * 1000)
        return TestResult(
            ok=proc.returncode == 0,
            command=" ".join(["ikc", command, *args]),
            exit_code=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            duration_ms=duration,
        )
    except subprocess.TimeoutExpired:
        duration = int((time.monotonic() - start) * 1000)
        return TestResult(
            ok=False,
            command=" ".join(["ikc", command, *args]),
            exit_code=None,
            stdout="",
            stderr=f"CLI 执行超时（>{timeout_seconds}s）",
            duration_ms=duration,
        )


def _parse_mcp_steps(stdout: str) -> list[str]:
    """解析冒烟输出中的步骤标记行（[n/4] ...）。"""
    return [line.strip() for line in stdout.splitlines() if line.strip().startswith("[")]


_MCP_SMOKE_SCRIPT = r"""
import asyncio, os, sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def main():
    env = dict(os.environ)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "open_ikc_sdk.mcp", "--transport", "stdio",
              "--base-url", env.get("OPEN_PLATFORM_BASE_URL", "http://127.0.0.1:18000")],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await asyncio.wait_for(session.initialize(), 10)
            print(f"[1/3] initialize -> {init.server_info.name}")
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"[2/3] tools/list -> {len(names)} tools")
            res = await session.call_tool("__TOOL__", {})
            print(f"[3/3] call __TOOL__ -> is_error={res.is_error}")
            if res.is_error:
                sys.exit(2)

asyncio.run(main())
"""
