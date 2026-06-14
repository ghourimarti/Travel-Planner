"""DB isolation for worker tests: a throwaway file-SQLite with tables created.

A FILE (not ``:memory:``) is required — the engine uses NullPool (fresh connection
per scope) and in-memory SQLite is per-connection, so writes wouldn't survive.
Tasks are invoked directly (their bodies run synchronously), so no broker is needed.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _db(monkeypatch, tmp_path):
    db_file = (tmp_path / "runs.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    import tp_core.db as db

    asyncio.run(db.init_models())
    yield
    asyncio.run(db.dispose_engine())
