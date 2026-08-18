from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.admin import mcp_cli_test

app = main_module.app


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """管理面鉴权开关：本文件所有用例（含 HTTP 层）默认启用 admin token。"""
    monkeypatch.setenv("OPEN_PLATFORM_ADMIN_TOKEN", "test-admin-token")


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-admin-token"}


UNREACHABLE = "http://127.0.0.1:59999"


# ---------- CLI 白名单（单元层） ----------


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
        base_url=UNREACHABLE,  # 不存在的端口，避免真实调用
        timeout_seconds=2,
    )
    # 校验通过，但连接失败 → 传输错误（exit 6），不是参数错误
    assert result.ok is False
    assert "不在白名单" not in result.stderr


def test_cli_positional_arg_allowed_for_kb_get() -> None:
    """kb-get 允许 1 个位置参数（kbId），不应被参数校验拦截。"""
    result = mcp_cli_test.run_cli_command(
        command="kb-get",
        args=["kb_10001"],
        base_url=UNREACHABLE,
        timeout_seconds=2,
    )
    assert "不在白名单" not in result.stderr
    assert "位置参数过多" not in result.stderr


def test_cli_positional_overflow_rejected() -> None:
    """kb-get 最多 1 个位置参数，多余应被拒绝。"""
    result = mcp_cli_test.run_cli_command(command="kb-get", args=["a", "b"])
    assert result.ok is False
    assert "位置参数过多" in result.stderr


def test_cli_no_positional_for_other_commands() -> None:
    """无位置参数命令传位置参数时交由 CLI 自身拒绝（而非白名单校验误判 flag 值）。"""
    result = mcp_cli_test.run_cli_command(
        command="search-query",
        args=["--query", "产品能力", "--kb-id", "kb_10001"],
        base_url=UNREACHABLE,
        timeout_seconds=2,
    )
    assert "不在白名单" not in result.stderr
    assert "位置参数过多" not in result.stderr


def test_cli_kb_list_full_flag_set_allowed() -> None:
    """kb-list 的全部只读过滤参数都应放行。"""
    result = mcp_cli_test.run_cli_command(
        command="kb-list",
        args=["--page", "1", "--page-size", "10", "--kb-type", "team",
              "--team-id", "team_01", "--org-id", "org_01", "--owner-id", "u1", "--keyword", "客服"],
        base_url=UNREACHABLE,
        timeout_seconds=2,
    )
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


# ---------- MCP 白名单（单元层） ----------


def test_mcp_tool_whitelist_rejects_unknown() -> None:
    result = mcp_cli_test.run_mcp_smoke(tool="kb_delete", base_url=UNREACHABLE)
    assert result.ok is False
    assert "不在白名单" in result.stderr


def test_mcp_tool_args_unknown_key_rejected() -> None:
    result = mcp_cli_test.run_mcp_smoke(tool="kb_get", args={"evil": 1}, base_url=UNREACHABLE)
    assert result.ok is False
    assert "参数不在白名单" in result.stderr


def test_mcp_tool_args_allowed() -> None:
    """带参只读工具（kb_get）在白名单参数下应放行（不实际连通，但不被参数校验拦截）。"""
    result = mcp_cli_test.run_mcp_smoke(
        tool="kb_get",
        args={"kbId": "kb_10001"},
        base_url=UNREACHABLE,
        timeout_seconds=2,
    )
    assert "不在白名单" not in result.stderr


def test_mcp_allowed_tool_starts() -> None:
    """白名单工具允许执行（到不存在的端口，超时或连接失败，但不应被白名单拦截）。"""
    result = mcp_cli_test.run_mcp_smoke(
        tool="sys_catalog",
        base_url=UNREACHABLE,
        timeout_seconds=2,
    )
    assert result.ok is False
    assert "不在白名单" not in result.stderr


def test_mcp_whitelist_subset_of_sdk_tools() -> None:
    """MCP 白名单必须 ⊆ SDK 实际注册的工具，防止遗漏/残留。"""
    from open_ikc_sdk._bootstrap import client_from_env
    from open_ikc_sdk.mcp.server import build_server

    client = client_from_env(base_url=UNREACHABLE, token="x")
    server = build_server(client)
    sdk_tools = {t.name for t in server._tool_manager.list_tools()}
    assert sdk_tools, "SDK 工具集为空，白名单一致性校验失效"
    assert set(mcp_cli_test.MCP_TOOL_WHITELIST) <= sdk_tools


def test_cli_whitelist_subset_of_sdk_commands() -> None:
    """CLI 白名单必须 ⊆ SDK 实际注册的命令，防止遗漏/残留。"""
    from open_ikc_sdk.cli import app as cli_app

    sdk_commands = {c.name for c in cli_app.registered_commands}
    assert sdk_commands, "SDK 命令集为空，白名单一致性校验失效"
    assert set(mcp_cli_test.CLI_WHITELIST) <= sdk_commands


def test_whitelist_payload_structure() -> None:
    payload = mcp_cli_test.whitelist_payload()
    assert "cli" in payload and "mcpTools" in payload
    assert "cliArgs" in payload and "mcpArgs" in payload
    assert "kb-list" in payload["cli"] and "sys_catalog" in payload["mcpTools"]
    assert payload["cliArgs"]["kb-get"]["positional"] == 1
    assert payload["mcpArgs"]["kb_get"] == ["kbId"]


def test_parse_mcp_steps() -> None:
    out = "[1/3] initialize -> open-ikc\n[2/3] tools/list -> 14 tools\n[3/3] call sys_catalog -> is_error=False\n"
    steps = mcp_cli_test._parse_mcp_steps(out)
    assert len(steps) == 3
    assert steps[0].startswith("[1/3]")


# ---------- HTTP 层（路由 / 鉴权 / 参数校验） ----------


def test_testlab_endpoints_require_admin() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/test/whitelist")
    assert resp.status_code == 200
    assert resp.json()["errCode"] == "100401"


def test_testlab_endpoints_disabled_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPEN_PLATFORM_ADMIN_TOKEN", raising=False)
    with TestClient(app) as client:
        resp = client.get("/admin/test/whitelist", headers=_admin_headers())
    assert resp.status_code == 503
    assert resp.json()["errCode"] == "503001"


def test_whitelist_endpoint() -> None:
    with TestClient(app) as client:
        resp = client.get("/admin/test/whitelist", headers=_admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["errCode"] == "000000"
    data = body["data"]
    assert "sys-catalog" in data["cli"]
    assert "sys_catalog" in data["mcpTools"]
    assert "cliArgs" in data and "mcpArgs" in data


def test_mcp_endpoint_rejects_unknown_tool() -> None:
    with TestClient(app) as client:
        resp = client.post("/admin/test/mcp", json={"tool": "kb_delete"}, headers=_admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["errCode"] == "200020"
    assert body["data"]["ok"] is False
    assert "不在白名单" in body["data"]["stderr"]


def test_mcp_endpoint_args_type_validation() -> None:
    """args 必须为对象，类型错误由参数校验映射 100001。"""
    with TestClient(app) as client:
        resp = client.post(
            "/admin/test/mcp",
            json={"tool": "kb_get", "args": ["kb_10001"]},
            headers=_admin_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["errCode"] == "100001"


def test_mcp_endpoint_execution_failure_reported() -> None:
    """合法请求进入真实执行：连不通的平台返回结构化 200020 而非崩溃。"""
    with TestClient(app) as client:
        resp = client.post(
            "/admin/test/mcp",
            json={"tool": "sys_catalog", "baseUrl": UNREACHABLE, "timeoutSeconds": 3},
            headers=_admin_headers(),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["errCode"] == "200020"
    assert body["data"]["ok"] is False
    # 子进程可能因连接失败快速退出，也可能在启动阶段被超时终止（exitCode=None）
    assert body["data"]["exitCode"] is None or isinstance(body["data"]["exitCode"], int)
    assert body["data"]["stderr"]
    assert isinstance(body["data"]["detail"], dict)


def test_cli_endpoint_rejects_unknown_command() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/admin/test/cli",
            json={"command": "rm-rf", "args": []},
            headers=_admin_headers(),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["errCode"] == "200020"
    assert "不在白名单" in body["data"]["stderr"]


def test_cli_endpoint_args_type_validation() -> None:
    """args 必须为字符串数组，类型错误映射 100001。"""
    with TestClient(app) as client:
        resp = client.post(
            "/admin/test/cli",
            json={"command": "kb-list", "args": "abc"},
            headers=_admin_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["errCode"] == "100001"


def test_cli_endpoint_execution_failure_reported() -> None:
    """合法请求进入真实执行：连不通的平台返回 200020（传输错误 exit 6）。"""
    with TestClient(app) as client:
        resp = client.post(
            "/admin/test/cli",
            json={"command": "sys-catalog", "args": [], "baseUrl": UNREACHABLE, "timeoutSeconds": 3},
            headers=_admin_headers(),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["errCode"] == "200020"
    assert body["data"]["ok"] is False
    assert body["data"]["exitCode"] == 6
