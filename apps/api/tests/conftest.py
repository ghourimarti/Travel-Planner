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
    # Hermetic settings: a dummy key so get_settings() succeeds, and local env so auth
    # is off by default (auth-specific tests opt back in via AUTH_ENABLED).
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "local")
    from tp_core.settings import get_settings

    get_settings.cache_clear()
    import tp_core.db as db

    asyncio.run(db.init_models())
    yield
    asyncio.run(db.dispose_engine())
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_ratelimit(monkeypatch):
    """Rate limiting is a no-op by default so unrelated API tests don't touch Redis."""
    import tp_api.main as main

    async def _allow(*args, **kwargs):
        return True

    monkeypatch.setattr(main, "allow_request", _allow)
