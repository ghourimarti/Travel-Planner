"""Typed inputs/outputs for the agent's tools.

These Pydantic models are the *contracts* the agent depends on. The underlying
provider (Open-Meteo / OSM / OSRM) can be swapped without changing these shapes.
"""

from __future__ import annotations

from pydantic import BaseModel


class GeoLocation(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None


class POI(BaseModel):
    name: str
    category: str  # e.g. "tourism:museum"
    latitude: float
    longitude: float


class DailyWeather(BaseModel):
    date: str  # ISO date (YYYY-MM-DD)
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float
    weather_code: int
    description: str


class RouteMatrix(BaseModel):
    """Pairwise travel matrix between the input coordinates (row i -> col j)."""

    durations_s: list[list[float]]
    distances_m: list[list[float]]
