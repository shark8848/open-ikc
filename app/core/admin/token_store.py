from __future__ import annotations

"""SQLite token 管理：创建 / 撤销 / 列表 / 活跃集合。

- Token 明文仅在创建时返回一次，库中存储 sha256 哈希，不落明文。
- 与 ``app.core.security.configured_tokens()``（环境变量 token）合并构成有效 token 集合。
- 数据库路径由 ``OPEN_PLATFORM_DB_PATH`` 控制（默认 ``data/open_ikc_platform.db``）。
"""

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "data/open_ikc_platform.db"

_locks: dict[str, threading.Lock] = {}


def db_path() -> str:
    return os.getenv("OPEN_PLATFORM_DB_PATH", DEFAULT_DB_PATH)


def _db_lock() -> threading.Lock:
    path = db_path()
    lock = _locks.get(path)
    if lock is None:
        lock = threading.Lock()
        _locks[path] = lock
    return lock


def _connect() -> sqlite3.Connection:
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT '',
            scopes TEXT NOT NULL DEFAULT '',
            token_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',        -- active / revoked
            created_at INTEGER NOT NULL,
            expires_at INTEGER,                            -- epoch ms; NULL = 永不过期
            last_used_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_api_tokens_status ON api_tokens(status);
        """
    )
    conn.commit()


def _epoch_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class TokenRecord:
    """token 记录（不含明文）。"""

    id: int
    name: str
    owner: str
    scopes: list[str]
    status: str
    created_at: int
    expires_at: int | None
    last_used_at: int | None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and _epoch_ms() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "scopes": self.scopes,
            "status": self.status,
            "createdAt": self.created_at,
            "expiresAt": self.expires_at,
            "lastUsedAt": self.last_used_at,
            "expired": self.expired,
        }


def _row_to_record(row: sqlite3.Row) -> TokenRecord:
    scopes = row["scopes"].split(",") if row["scopes"] else []
    return TokenRecord(
        id=row["id"],
        name=row["name"],
        owner=row["owner"],
        scopes=scopes,
        status=row["status"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        last_used_at=row["last_used_at"],
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(
    *,
    name: str,
    owner: str = "",
    scopes: list[str] | None = None,
    expires_in_seconds: int | None = None,
    token_length: int = 32,
) -> tuple[TokenRecord, str]:
    """创建 token，返回 (记录, 明文)；明文仅此一次返回。"""
    plain = secrets.token_urlsafe(token_length)
    token_hash = _hash_token(plain)
    expires_at = (
        _epoch_ms() + expires_in_seconds * 1000
        if expires_in_seconds is not None
        else None
    )

    with _db_lock():
        conn = _connect()
        try:
            _init_schema(conn)
            cur = conn.execute(
                "INSERT INTO api_tokens (name, owner, scopes, token_hash, status, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, 'active', ?, ?)",
                (
                    name,
                    owner,
                    ",".join(scopes or []),
                    token_hash,
                    _epoch_ms(),
                    expires_at,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM api_tokens WHERE id = ?", (cur.lastrowid,)).fetchone()
            return _row_to_record(row), plain
        finally:
            conn.close()


def revoke_token(token_id: int) -> bool:
    """撤销 token；返回是否找到并撤销。"""
    with _db_lock():
        conn = _connect()
        try:
            _init_schema(conn)
            cur = conn.execute(
                "UPDATE api_tokens SET status = 'revoked' WHERE id = ? AND status = 'active'",
                (token_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_tokens(include_revoked: bool = False) -> list[TokenRecord]:
    with _db_lock():
        conn = _connect()
        try:
            _init_schema(conn)
            if include_revoked:
                rows = conn.execute("SELECT * FROM api_tokens ORDER BY id DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM api_tokens WHERE status = 'active' ORDER BY id DESC"
                ).fetchall()
            return [_row_to_record(row) for row in rows]
        finally:
            conn.close()


def get_token(token_id: int) -> TokenRecord | None:
    with _db_lock():
        conn = _connect()
        try:
            _init_schema(conn)
            row = conn.execute("SELECT * FROM api_tokens WHERE id = ?", (token_id,)).fetchone()
            return _row_to_record(row) if row else None
        finally:
            conn.close()


def active_token_set() -> set[str]:
    """返回当前有效（active 且未过期）token 的 sha256 哈希集合。"""
    result: set[str] = set()
    with _db_lock():
        conn = _connect()
        try:
            _init_schema(conn)
            now = _epoch_ms()
            rows = conn.execute(
                "SELECT token_hash FROM api_tokens WHERE status = 'active'"
                " AND (expires_at IS NULL OR expires_at > ?)",
                (now,),
            ).fetchall()
            result = {row["token_hash"] for row in rows}
        finally:
            conn.close()
    return result


def has_any_token_record() -> bool:
    """DB 中是否存在任何 token 记录（含已撤销）。

    用于区分「从未配置 DB token」（此时业务鉴权退化为仅要求 Bearer 存在）
    与「配置过但全部撤销/过期」（此时应拒绝所有 DB token）。
    """
    with _db_lock():
        conn = _connect()
        try:
            _init_schema(conn)
            row = conn.execute("SELECT 1 AS c FROM api_tokens LIMIT 1").fetchone()
            return row is not None
        finally:
            conn.close()


def mark_token_used(token_hash: str) -> None:
    """更新最近使用时间（best-effort，失败静默）。"""
    try:
        with _db_lock():
            conn = _connect()
            try:
                _init_schema(conn)
                conn.execute(
                    "UPDATE api_tokens SET last_used_at = ? WHERE token_hash = ? AND status = 'active'",
                    (_epoch_ms(), token_hash),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass


def is_token_in_db(token: str) -> bool:
    """校验明文 token 是否在活跃集合中；命中时更新 last_used_at。"""
    token_hash = _hash_token(token)
    if token_hash in active_token_set():
        mark_token_used(token_hash)
        return True
    return False
