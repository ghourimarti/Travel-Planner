"""Tool tests run without Redis: no shared call slot, and no breaker state between tests."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest
from tp_core.llm.circuit import reset_infra_breakers

# The MODULE, not `tp_tools.geocode` as an attribute: the package re-exports the
# `geocode` FUNCTION under that name, which shadows the submodule on attribute lookup.
_GEOCODE_MODULE = importlib.import_module("tp_tools.geocode")


@pytest.fixture(autouse=True)
def _no_slot_wait_and_fresh_breakers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def _no_wait(*_: object, **__: object) -> None:
        return None

    # The app-wide Nominatim slot needs Redis; without it the per-process fallback
    # would add up to a second between the lookups of consecutive tests.
    monkeypatch.setattr(_GEOCODE_MODULE, "acquire_slot", _no_wait)
    # Breakers are process-wide: a test that provokes failures must not open one for
    # the next test (tp_core.llm.circuit.reset_infra_breakers documents the seam).
    reset_infra_breakers()
    yield
    reset_infra_breakers()
