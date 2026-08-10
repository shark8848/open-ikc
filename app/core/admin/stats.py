from __future__ import annotations

"""SQLite 请求统计存储：请求明细 + 端点聚合 + token 维度聚合。

- ``request_stats``：请求明细（时间窗口滚动，可清理）。
- ``endpoint_agg``：按 path+method 的时间窗口聚合（总量/成功/错误/耗时）。
- ``token_agg``：按 token 的时间窗口聚合。
- 进程内并发计数器记录当前在线请求数。
"""

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.admin.token_store import _connect, _db_lock, _init_schema as _init_token_schema

_AGG_WINDOW_MS = 60_000  # 聚合窗口：1 分钟
_KEEP_WINDOWS = 120  # 保留最近 120 个窗口（2 小时）
_detail_keep_seconds = 3600  # 明细保留 1 小时


class ConcurrencyCounter:
    """进程内并发/在线请求计数器（线程安全）。"""

    def __init__(self) -> None:
        self._count = 0
        self._lock = threading.Lock()

    def inc(self) -> int:
        with self._lock:
            self._count += 1
            return self._count

    def dec(self) -> int:
        with self._lock:
            self._count = max(0, self._count - 1)
            return self._count

    @property
    def current(self) -> int:
        with self._lock:
            return self._count


_concurrency = ConcurrencyCounter()


def init_stats_schema() -> None:
    """初始化统计表（幂等）。"""
    conn = _connect()
    try:
        _init_token_schema(conn)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS request_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                path TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                err_code TEXT NOT NULL DEFAULT '',
                token_id INTEGER,
                user_id TEXT NOT NULL DEFAULT '',
                tenant_id TEXT NOT NULL DEFAULT '',
                duration_ms INTEGER NOT NULL DEFAULT 0,
                client_ip TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_request_stats_ts ON request_stats(ts);

            CREATE TABLE IF NOT EXISTS endpoint_agg (
                path TEXT NOT NULL,
                method TEXT NOT NULL,
                window_start INTEGER NOT NULL,
                window_end INTEGER NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                error INTEGER NOT NULL DEFAULT 0,
                total_ms INTEGER NOT NULL DEFAULT 0,
                min_ms INTEGER NOT NULL DEFAULT 0,
                max_ms INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (path, method, window_start)
            );

            CREATE TABLE IF NOT EXISTS token_agg (
                token_id INTEGER NOT NULL,
                window_start INTEGER NOT NULL,
                window_end INTEGER NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                success INTEGER NOT NULL DEFAULT 0,
                error INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (token_id, window_start)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _current_window() -> int:
    return int(time.time() * 1000) // _AGG_WINDOW_MS * _AGG_WINDOW_MS


def record_request(
    *,
    path: str,
    method: str,
    status_code: int,
    err_code: str = "",
    token_id: int | None = None,
    user_id: str = "",
    tenant_id: str = "",
    duration_ms: int = 0,
    client_ip: str = "",
) -> None:
    """记录一次请求（best-effort，异常静默）。"""
    try:
        init_stats_schema()
        window_start = _current_window()
        window_end = window_start + _AGG_WINDOW_MS
        ok = status_code < 400 and (not err_code or err_code == "000000")
        with _db_lock():
            conn = _connect()
            try:
                conn.execute(
                    "INSERT INTO request_stats"
                    " (ts, path, method, status_code, err_code, token_id, user_id, tenant_id,"
                    "  duration_ms, client_ip)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(time.time() * 1000),
                        path,
                        method,
                        status_code,
                        err_code,
                        token_id,
                        user_id,
                        tenant_id,
                        duration_ms,
                        client_ip,
                    ),
                )
                conn.execute(
                    "INSERT INTO endpoint_agg"
                    " (path, method, window_start, window_end, total, success, error,"
                    "  total_ms, min_ms, max_ms)"
                    " VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(path, method, window_start) DO UPDATE SET"
                    "   total = total + 1,"
                    "   success = success + excluded.success,"
                    "   error = error + excluded.error,"
                    "   total_ms = total_ms + excluded.total_ms,"
                    "   min_ms = MIN(min_ms, excluded.min_ms),"
                    "   max_ms = MAX(max_ms, excluded.max_ms)",
                    (
                        path,
                        method,
                        window_start,
                        window_end,
                        1 if ok else 0,
                        0 if ok else 1,
                        duration_ms,
                        duration_ms,
                        duration_ms,
                    ),
                )
                if token_id is not None:
                    conn.execute(
                        "INSERT INTO token_agg"
                        " (token_id, window_start, window_end, total, success, error)"
                        " VALUES (?, ?, ?, 1, ?, ?)"
                        " ON CONFLICT(token_id, window_start) DO UPDATE SET"
                        "   total = total + 1, success = success + excluded.success,"
                        "   error = error + excluded.error",
                        (token_id, window_start, window_end, 1 if ok else 0, 0 if ok else 1),
                    )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass


def current_concurrency() -> int:
    return _concurrency.current


def snapshot() -> dict[str, Any]:
    """总览快照：在线并发、总请求、错误率、活跃端点数。"""
    try:
        init_stats_schema()
        now = int(time.time() * 1000)
        prune_old()
        with _db_lock():
            conn = _connect()
            try:
                total = conn.execute(
                    "SELECT COUNT(*) AS c FROM request_stats WHERE ts >= ?",
                    (now - _detail_keep_seconds * 1000,),
                ).fetchone()["c"]
                errors = conn.execute(
                    "SELECT COUNT(*) AS c FROM request_stats"
                    " WHERE ts >= ? AND (status_code >= 400 OR err_code NOT IN ('', '000000'))",
                    (now - _detail_keep_seconds * 1000,),
                ).fetchone()["c"]
                endpoints = conn.execute(
                    "SELECT COUNT(DISTINCT path || method) AS c FROM request_stats WHERE ts >= ?",
                    (now - _detail_keep_seconds * 1000,),
                ).fetchone()["c"]
            finally:
                conn.close()
        return {
            "concurrency": _concurrency.current,
            "totalRequests": int(total),
            "errorCount": int(errors),
            "errorRate": round(int(errors) / max(1, int(total)), 4),
            "activeEndpoints": int(endpoints),
            "detailWindowSeconds": _detail_keep_seconds,
        }
    except Exception:
        return {
            "concurrency": _concurrency.current,
            "totalRequests": 0,
            "errorCount": 0,
            "errorRate": 0.0,
            "activeEndpoints": 0,
            "detailWindowSeconds": _detail_keep_seconds,
        }


def endpoint_stats(window_minutes: int | None = None) -> list[dict[str, Any]]:
    """端点维度统计（近 N 分钟聚合，默认最近 2 小时）。"""
    try:
        init_stats_schema()
        minutes = window_minutes or 120
        since = _current_window() - minutes * _AGG_WINDOW_MS
        with _db_lock():
            conn = _connect()
            try:
                rows = conn.execute(
                    """
                    SELECT path, method, SUM(total) AS total, SUM(success) AS success,
                           SUM(error) AS error, SUM(total_ms) AS total_ms,
                           MIN(min_ms) AS min_ms, MAX(max_ms) AS max_ms,
                           MAX(window_end) AS last_window
                    FROM endpoint_agg WHERE window_start >= ?
                    GROUP BY path, method ORDER BY total DESC
                    """,
                    (since,),
                ).fetchall()
            finally:
                conn.close()
        result = []
        for row in rows:
            total = int(row["total"] or 0)
            total_ms = int(row["total_ms"] or 0)
            result.append(
                {
                    "path": row["path"],
                    "method": row["method"],
                    "total": total,
                    "success": int(row["success"] or 0),
                    "error": int(row["error"] or 0),
                    "errorRate": round(int(row["error"] or 0) / max(1, total), 4),
                    "avgMs": round(total_ms / max(1, total), 1),
                    "minMs": int(row["min_ms"] or 0),
                    "maxMs": int(row["max_ms"] or 0),
                }
            )
        return result
    except Exception:
        return []


def token_stats(window_minutes: int | None = None) -> list[dict[str, Any]]:
    """token 维度调用统计（含最近使用时间）。"""
    try:
        init_stats_schema()
        minutes = window_minutes or 120
        since = _current_window() - minutes * _AGG_WINDOW_MS
        with _db_lock():
            conn = _connect()
            try:
                rows = conn.execute(
                    """
                    SELECT a.token_id AS token_id,
                           COALESCE(t.name, 'token#' || a.token_id) AS token_name,
                           SUM(a.total) AS total, SUM(a.success) AS success,
                           SUM(a.error) AS error
                    FROM token_agg a
                    LEFT JOIN api_tokens t ON a.token_id = t.id
                    WHERE a.window_start >= ?
                    GROUP BY a.token_id ORDER BY total DESC
                    """,
                    (since,),
                ).fetchall()
            finally:
                conn.close()
        return [
            {
                "tokenId": row["token_id"],
                "tokenName": row["token_name"],
                "total": int(row["total"] or 0),
                "success": int(row["success"] or 0),
                "error": int(row["error"] or 0),
                "errorRate": round(int(row["error"] or 0) / max(1, int(row["total"] or 0)), 4),
            }
            for row in rows
        ]
    except Exception:
        return []


def recent_requests(limit: int = 50) -> list[dict[str, Any]]:
    """最近请求明细。"""
    try:
        init_stats_schema()
        with _db_lock():
            conn = _connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM request_stats ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
        return [
            {
                "ts": row["ts"],
                "path": row["path"],
                "method": row["method"],
                "statusCode": row["status_code"],
                "errCode": row["err_code"],
                "durationMs": row["duration_ms"],
                "clientIp": row["client_ip"],
            }
            for row in rows
        ]
    except Exception:
        return []


def prune_old() -> None:
    """清理过期窗口与明细（best-effort）。"""
    try:
        cutoff = _current_window() - _KEEP_WINDOWS * _AGG_WINDOW_MS
        detail_cutoff = int(time.time() * 1000) - _detail_keep_seconds * 1000
        with _db_lock():
            conn = _connect()
            try:
                conn.execute("DELETE FROM endpoint_agg WHERE window_start < ?", (cutoff,))
                conn.execute("DELETE FROM token_agg WHERE window_start < ?", (cutoff,))
                conn.execute("DELETE FROM request_stats WHERE ts < ?", (detail_cutoff,))
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass
