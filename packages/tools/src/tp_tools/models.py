"""Typed tool outputs — these Pydantic models ARE the tool contracts the agent reasons over."""

from __future__ import annotations

from pydantic import BaseModel


class GeoLocation(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    display_name: str | None = None
    # How prominent the matched place is (Nominatim `importance`, 0..1) and what kind
    # of place it is (`addresstype`, e.g. city / village / hamlet). Optional because a
    # cached lookup from before these existed has neither - absence means "unknown",
    # never "fine". Used to WARN when an obscure place was matched (see nodes.py).
    importance: float | None = None
    kind: str | None = None


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
