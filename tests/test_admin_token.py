from __future__ import annotations

import pytest

from app.core.admin import token_store


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """每个测试用独立 SQLite 库，避免污染。"""
    monkeypatch.setenv("OPEN_PLATFORM_DB_PATH", str(tmp_path / "test_tokens.db"))


def test_create_token_returns_plaintext_once() -> None:
    record, plain = token_store.create_token(name="测试token", owner="ops", scopes=["read"])
    assert plain and len(plain) >= 32
    assert record.status == "active"
    # 明文不在库里（只存哈希）
    row = token_store._connect().execute(
        "SELECT token_hash FROM api_tokens WHERE id = ?", (record.id,)
    ).fetchone()
    assert row["token_hash"] != plain
    assert row["token_hash"] == token_store._hash_token(plain)


def test_list_tokens_excludes_revoked_by_default() -> None:
    r1, _ = token_store.create_token(name="a")
    r2, _ = token_store.create_token(name="b")
    token_store.revoke_token(r1.id)

    active = token_store.list_tokens()
    ids = {r.id for r in active}
    assert r2.id in ids
    assert r1.id not in ids

    all_tokens = token_store.list_tokens(include_revoked=True)
    assert {r.id for r in all_tokens} == {r1.id, r2.id}


def test_revoke_token() -> None:
    record, _ = token_store.create_token(name="x")
    assert token_store.revoke_token(record.id) is True
    assert token_store.revoke_token(record.id) is False  # 已撤销
    assert token_store.get_token(record.id).status == "revoked"


def test_active_token_set_only_active_and_unexpired() -> None:
    r1, p1 = token_store.create_token(name="a")
    r2, p2 = token_store.create_token(name="b", expires_in_seconds=1)
    token_store.revoke_token(r2.id)

    active = token_store.active_token_set()
    assert token_store._hash_token(p1) in active
    assert token_store._hash_token(p2) not in active
    assert token_store._hash_token("unrelated") not in active
    assert token_store._hash_token(r1.name) not in active


def test_is_token_in_db_and_mark_used() -> None:
    record, plain = token_store.create_token(name="t", scopes=["read"])
    assert token_store.is_token_in_db(plain) is True
    updated = token_store.get_token(record.id)
    assert updated.last_used_at is not None
    # 已撤销后失效
    token_store.revoke_token(record.id)
    assert token_store.is_token_in_db(plain) is False


def test_expired_token_excluded() -> None:
    record, plain = token_store.create_token(name="e", expires_in_seconds=0)
    assert token_store.get_token(record.id).expired
    assert token_store.is_token_in_db(plain) is False
    assert token_store._hash_token(plain) not in token_store.active_token_set()


def test_security_merges_db_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """env token 与 DB token 合并校验。"""
    from app.core import security

    monkeypatch.setenv("OPEN_PLATFORM_TOKEN", "env-token")
    _, db_plain = token_store.create_token(name="db")

    assert security.is_token_valid("Bearer env-token") is True
    assert security.is_token_valid(f"Bearer {db_plain}") is True
    assert security.is_token_valid("Bearer wrong") is False


def test_security_falls_back_to_db_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import security

    monkeypatch.delenv("OPEN_PLATFORM_TOKEN", raising=False)
    monkeypatch.delenv("OPEN_PLATFORM_TOKENS", raising=False)
    _, db_plain = token_store.create_token(name="only-db")

    assert security.is_token_valid(f"Bearer {db_plain}") is True
    assert security.is_token_valid("Bearer wrong") is False
