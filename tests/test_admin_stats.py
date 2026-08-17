from __future__ import annotations

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.admin import stats
from app.core.admin import monitor
from app.core.admin.token_store import _connect


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPEN_PLATFORM_DB_PATH", str(tmp_path / "test_stats.db"))
    stats.init_stats_schema()


def test_record_and_snapshot() -> None:
    stats.record_request(path="/api/v1/knowledge-bases/query", method="POST", status_code=200, duration_ms=12)
    stats.record_request(path="/api/v1/knowledge-bases/query", method="POST", status_code=500, duration_ms=8)
    snap = stats.snapshot()
    assert snap["totalRequests"] == 2
    assert snap["errorCount"] == 1
    assert snap["errorRate"] == 0.5
    assert snap["activeEndpoints"] == 1
    assert snap["concurrency"] == 0


def test_concurrency_counter() -> None:
    assert stats.current_concurrency() == 0
    stats._concurrency.inc()
    stats._concurrency.inc()
    assert stats.current_concurrency() == 2
    stats._concurrency.dec()
    assert stats.current_concurrency() == 1
    stats._concurrency.dec()
    assert stats.current_concurrency() == 0


def test_monitor_exception_path_decrements_and_propagates(monkeypatch) -> None:
    """端点抛异常时：并发计数归零、原异常不被 UnboundLocalError 掩盖、不落统计。"""
    middleware = monitor.build_monitor_middleware(logging.getLogger("test-monitor"))
    recorded = {"called": False}

    def _fail_record(*_args, **_kwargs) -> None:
        recorded["called"] = True

    monkeypatch.setattr(monitor, "_record", _fail_record)

    class _State:
        skip_stats = False

    class _Request:
        state = _State()

    async def _call_next(_request) -> None:
        raise RuntimeError("boom")

    before = stats.current_concurrency()
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(middleware(_Request(), _call_next))
    assert stats.current_concurrency() == before
    assert recorded["called"] is False


def test_endpoint_stats_aggregation() -> None:
    stats.record_request(path="/a", method="GET", status_code=200, duration_ms=10)
    stats.record_request(path="/a", method="GET", status_code=200, duration_ms=30)
    stats.record_request(path="/a", method="GET", status_code=404, duration_ms=5)
    stats.record_request(path="/b", method="POST", status_code=200, duration_ms=100)

    ep = {row["path"]: row for row in stats.endpoint_stats()}
    assert ep["/a"]["total"] == 3
    assert ep["/a"]["success"] == 2
    assert ep["/a"]["error"] == 1
    assert ep["/a"]["errorRate"] == pytest.approx(1 / 3, abs=1e-4)
    assert ep["/a"]["avgMs"] == pytest.approx(15.0)
    assert ep["/a"]["minMs"] == 5
    assert ep["/a"]["maxMs"] == 30
    assert ep["/b"]["total"] == 1


def test_token_stats_aggregation() -> None:
    stats.record_request(path="/a", method="GET", status_code=200, token_id=1)
    stats.record_request(path="/a", method="GET", status_code=200, token_id=1)
    stats.record_request(path="/b", method="GET", status_code=500, token_id=1)
    stats.record_request(path="/c", method="GET", status_code=200, token_id=2)

    ts = {row["tokenId"]: row for row in stats.token_stats()}
    assert ts[1]["total"] == 3
    assert ts[1]["error"] == 1
    assert ts[2]["total"] == 1


def test_recent_requests() -> None:
    stats.record_request(path="/x", method="GET", status_code=200, duration_ms=7, client_ip="10.0.0.1")
    rows = stats.recent_requests(limit=10)
    assert len(rows) == 1
    assert rows[0]["path"] == "/x"
    assert rows[0]["statusCode"] == 200
    assert rows[0]["clientIp"] == "10.0.0.1"


def test_prune_old_keeps_recent() -> None:
    old_ts = stats._current_window() - stats._KEEP_WINDOWS * stats._AGG_WINDOW_MS - 1000
    # 直接插入一条过期窗口数据
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO endpoint_agg (path, method, window_start, window_end, total, success, error,"
            " total_ms, min_ms, max_ms) VALUES ('/old', 'GET', ?, ?, 1, 1, 0, 5, 5, 5)",
            (old_ts, old_ts + stats._AGG_WINDOW_MS),
        )
        conn.commit()
    finally:
        conn.close()
    stats.record_request(path="/new", method="GET", status_code=200)
    stats.prune_old()
    ep = [row["path"] for row in stats.endpoint_stats(window_minutes=10000)]
    assert "/new" in ep
    assert "/old" not in ep


def test_monitor_middleware_records_requests() -> None:
    """真实 HTTP 请求经中间件产生统计。"""
    import app.main as main_module

    app = main_module.app
    with TestClient(app) as client:
        # 业务接口需要 token；health 免鉴权，用它验证中间件采集
        resp = client.get("/health")
        assert resp.status_code == 200
    snap = stats.snapshot()
    # /health 已被记录（其他并发测试可能叠加，至少 >0）
    assert snap["totalRequests"] >= 1
