"""DB isolation for API tests: a throwaway file-SQLite with tables created (S9).

The TestClient is used without a lifespan context, so this fixture (not the app
lifespan) creates the schema. Celery dispatch is mocked per-test.
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
