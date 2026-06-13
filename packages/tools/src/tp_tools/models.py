"""Typed tool outputs — these Pydantic models ARE the tool contracts the agent reasons over."""

from __future__ import annotations

from pydantic import BaseModel


class GeoLocation(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    display_name: str | None = None


class POI(BaseModel):
    name: str
    category: str
    latitude: float
    longitude: float
    address: str | None = None


class WeatherDaily(BaseModel):
    date: str  # ISO date (YYYY-MM-DD)
    temp_max_c: float | None = None
    temp_min_c: float | None = None
    precipitation_mm: float | None = None
    weather_code: int | None = None


class RouteLeg(BaseModel):
    from_name: str
    to_name: str
    distance_m: float
    duration_s: float
