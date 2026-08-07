"""Test isolation for tp_core.

Every test runs against a clean environment with no ``.env`` file, so a
developer's real local secrets can never leak in and make a "missing key"
test spuriously pass. The settings cache is cleared around each test.
"""

from __future__ import annotations

import asyncio

import pytest
from tp_core.settings import Settings, get_settings

_MANAGED_ENV = (
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "VOYAGE_API_KEY",
    "APP_ENV",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    # Point the settings at a non-existent .env so the real one is never read.
    monkeypatch.setattr(
        Settings,
        "model_config",
        {**Settings.model_config, "env_file": str(tmp_path / "absent.env")},
    )
    for key in _MANAGED_ENV:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db(monkeypatch, tmp_path):
    """Throwaway file-SQLite run-state DB with tables created."""
    db_file = (tmp_path / "runs.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    import tp_core.db as _db

    asyncio.run(_db.init_models())
    yield
    asyncio.run(_db.dispose_engine())
