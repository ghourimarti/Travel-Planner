"""Weather forecast via Open-Meteo (keyless)."""

from __future__ import annotations

from typing import Any

from tp_tools._http import get_json
from tp_tools.models import WeatherDaily

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _at(seq: Any, i: int) -> Any:
    if not isinstance(seq, list) or i >= len(seq):
        return None
    return seq[i]


async def forecast(lat: float, lon: float, *, days: int = 3) -> list[WeatherDaily]:
    """Daily forecast for the next ``days`` days at a coordinate."""
    data = await get_json(
        _OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    out: list[WeatherDaily] = []
    for i, date in enumerate(dates):
        out.append(
            WeatherDaily(
                date=date,
                temp_max_c=_at(daily.get("temperature_2m_max"), i),
                temp_min_c=_at(daily.get("temperature_2m_min"), i),
                precipitation_mm=_at(daily.get("precipitation_sum"), i),
                weather_code=_at(daily.get("weather_code"), i),
            )
        )
    return out
