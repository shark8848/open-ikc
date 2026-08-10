from __future__ import annotations

import pytest

from app.core.admin import mcp_cli_test


def test_cli_command_whitelist_rejects_unknown() -> None:
    result = mcp_cli_test.run_cli_command(command="rm-rf", args=[])
    assert result.ok is False
    assert "不在白名单" in result.stderr
    assert result.exit_code is None


def test_cli_unknown_flag_rejected() -> None:
    result = mcp_cli_test.run_cli_command(command="kb-list", args=["--evil-flag", "x"])
    assert result.ok is False
    assert "参数不在白名单" in result.stderr


def test_cli_allowed_flags_pass_validation() -> None:
    """白名单内命令与参数通过校验（不实际执行成功，但不应被参数校验拦截）。"""
    result = mcp_cli_test.run_cli_command(
        command="sys-catalog",
        args=[],
        token="",
        base_url="http://127.0.0.1:59999",  # 不存在的端口，避免真实调用
        timeout_seconds=2,
    )
    # 校验通过，但连接失败 → 传输错误（exit 6），不是参数错误
    assert result.ok is False
    assert "不在白名单" not in result.stderr


def test_mcp_tool_whitelist_rejects_unknown() -> None:
    result = mcp_cli_test.run_mcp_smoke(tool="kb_delete", base_url="http://127.0.0.1:59999")
    assert result.ok is False
    assert "不在白名单" in result.stderr


def test_mcp_allowed_tool_starts() -> None:
    """白名单工具允许执行（到不存在的端口，超时或连接失败，但不应被白名单拦截）。"""
    result = mcp_cli_test.run_mcp_smoke(
        tool="sys_catalog",
        base_url="http://127.0.0.1:59999",
        timeout_seconds=2,
    )
    assert result.ok is False
    assert "不在白名单" not in result.stderr


def test_timeout_handling() -> None:
    """超时场景返回结构化超时结果（不抛异常）。"""
    result = mcp_cli_test.run_cli_command(
        command="sys-catalog",
        args=[],
        base_url="http://10.255.255.1:1",  # 不可达地址
        timeout_seconds=1,
    )
    assert result.duration_ms >= 0
    assert isinstance(result.ok, bool)


def test_build_env_includes_token_and_identity() -> None:
    env = mcp_cli_test._build_env(
        token="t1",
        base_url="http://x:1",
        identity={"user_id": "u1", "tenant_id": "t1", "roles": "km_reader"},
    )
    assert env["OPEN_PLATFORM_TOKEN"] == "t1"
    assert env["OPEN_PLATFORM_USER_ID"] == "u1"
    assert env["OPEN_PLATFORM_TENANT_ID"] == "t1"
    assert env["OPEN_PLATFORM_ROLES"] == "km_reader"
    assert env["OPEN_PLATFORM_BASE_URL"] == "http://x:1"


def test_parse_mcp_steps() -> None:
    out = "[1/3] initialize -> open-ikc\n[2/3] tools/list -> 14 tools\n[3/3] call sys_catalog -> is_error=False\n"
    steps = mcp_cli_test._parse_mcp_steps(out)
    assert len(steps) == 3
    assert steps[0].startswith("[1/3]")
