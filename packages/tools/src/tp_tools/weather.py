"""Daily weather forecast (Open-Meteo forecast API, no key)."""

from __future__ import annotations

from typing import Any

from tp_tools._http import fetch_json
from tp_tools.models import DailyWeather

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes (subset).
_WEATHER_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
}


async def get_daily_weather(latitude: float, longitude: float) -> DailyWeather:
    """Return today's forecast for a location."""
    payload: Any = await fetch_json(
        "GET",
        _FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    daily = payload["daily"]
    code = int(daily["weather_code"][0])
    return DailyWeather(
        date=daily["time"][0],
        temp_max_c=float(daily["temperature_2m_max"][0]),
        temp_min_c=float(daily["temperature_2m_min"][0]),
        precipitation_mm=float(daily["precipitation_sum"][0]),
        weather_code=code,
        description=_WEATHER_CODES.get(code, "unknown"),
    )
