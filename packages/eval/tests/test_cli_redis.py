"""The eval CLI points tp_core's env-only Redis readers at the stack's Redis.

tp_core.control (spend ledger, kill switch), cache and events read REDIS_URL from the
environment. `make eval` does not export .env, so under eval they all fell back to an
unreachable default and eval spend reached no ledger (found 2026-10-01).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from tp_eval import cli


def test_eval_takes_the_redis_url_settings_read_from_env_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(
        cli, "get_settings", lambda: SimpleNamespace(redis_url="redis://localhost:3002/0")
    )
    cli._bridge_redis_url()
    assert os.environ["REDIS_URL"] == "redis://localhost:3002/0"


def test_a_redis_url_the_caller_exported_always_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://elsewhere:6379/0")
    monkeypatch.setattr(
        cli, "get_settings", lambda: SimpleNamespace(redis_url="redis://localhost:3002/0")
    )
    cli._bridge_redis_url()
    assert os.environ["REDIS_URL"] == "redis://elsewhere:6379/0"
