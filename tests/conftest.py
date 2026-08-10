import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolate_admin_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """每个测试使用独立的 SQLite DB，避免 token_store/stats 状态跨测试串扰。

    - 管理面 token/统计写 ``data/open_ikc_platform.db``，若测试共享真实 DB，
      已撤销 token 记录等状态会干扰业务鉴权测试（如「未配置 token 时放行」）。
    - 这里用 ``tmp_path`` 的临时 DB 隔离，保证测试可重复。
    """
    monkeypatch.setenv("OPEN_PLATFORM_DB_PATH", str(tmp_path / "test_platform.db"))
