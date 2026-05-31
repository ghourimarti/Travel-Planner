"""Weather tool: contract (mocked) + live integration."""

from __future__ import annotations

from typing import Any

import pytest

import tp_tools.weather as weather_mod
from tp_tools.weather import get_daily_weather


async def test_weather_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "daily": {
                "time": ["2026-06-01"],
                "temperature_2m_max": [24.5],
                "temperature_2m_min": [15.0],
                "precipitation_sum": [0.0],
                "weather_code": [1],
            }
        }

    monkeypatch.setattr(weather_mod, "fetch_json", _fake)
    w = await get_daily_weather(48.85, 2.35)
    assert w.date == "2026-06-01"
    assert w.temp_max_c == 24.5
    assert w.description == "mainly clear"


@pytest.mark.integration
async def test_weather_live() -> None:
    w = await get_daily_weather(48.8566, 2.3522)
    assert w.date
    assert -50.0 < w.temp_min_c < 60.0
    assert w.temp_max_c >= w.temp_min_c
