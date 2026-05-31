"""Geocode tool: contract (mocked) + live integration."""

from __future__ import annotations

from typing import Any

import pytest

import tp_tools.geocode as geocode_mod
from tp_tools._http import ToolError
from tp_tools.geocode import geocode_city


async def test_geocode_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "results": [
                {"name": "Paris", "latitude": 48.8534, "longitude": 2.3488, "country": "France"}
            ]
        }

    monkeypatch.setattr(geocode_mod, "fetch_json", _fake)
    loc = await geocode_city("Paris")
    assert loc.name == "Paris"
    assert loc.country == "France"
    assert round(loc.latitude, 1) == 48.9


async def test_geocode_no_results_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {"results": []}

    monkeypatch.setattr(geocode_mod, "fetch_json", _fake)
    with pytest.raises(ToolError):
        await geocode_city("Nowhereville-XYZ-123")


@pytest.mark.integration
async def test_geocode_live() -> None:
    loc = await geocode_city("Paris")
    assert 48.0 < loc.latitude < 49.0
    assert 2.0 < loc.longitude < 3.0
