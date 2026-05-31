"""Shared test fixtures for tp_core.

Unit tests must not read the developer's real environment or ``.env`` (that is
what leaked a key earlier). This autouse fixture makes every *non-integration*
test hermetic: it clears provider env vars and disables ``.env`` loading.
Integration tests are exempt so they can use the real ``.env``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tp_core.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def hermetic_settings(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker("integration"):
        yield  # live tests use the real environment / .env
        return
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
