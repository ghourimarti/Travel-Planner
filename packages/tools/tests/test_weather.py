"""tp_tools.weather — mocked Open-Meteo (no network)."""

from __future__ import annotations

import asyncio

import respx
from httpx import Response
from tp_tools.weather import forecast

_URL = "https://api.open-meteo.com/v1/forecast"


def test_parses_daily_forecast() -> None:
    with respx.mock:
        respx.get(_URL).mock(
            return_value=Response(
                200,
                json={
                    "daily": {
                        "time": ["2026-09-15", "2026-09-16"],
                        "temperature_2m_max": [28.0, 27.0],
                        "temperature_2m_min": [20.0, 19.0],
                        "precipitation_sum": [0.0, 4.2],
                        "weather_code": [1, 61],
                    }
                },
            )
        )
        days = asyncio.run(forecast(35.0, 135.7, days=2))
    assert len(days) == 2
    assert days[0].date == "2026-09-15"
    assert days[0].temp_max_c == 28.0
    assert days[1].precipitation_mm == 4.2
    assert days[1].weather_code == 61
