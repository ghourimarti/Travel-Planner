"""Domain contracts for planning.

This is the boundary the API (S4), the eval harness (S5), and the frontend (S13)
all bind to — so it is settled now and only *extended* later (cheap), never
reshaped (expensive). The structured ``days`` list is defined now for forward
compatibility but populated by the model from S7/S8; the S4 slice fills
``summary_markdown`` + the deterministic grounding fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from tp_tools.models import POI, GeoLocation, RouteLeg, WeatherDaily


class PlanRequest(BaseModel):
    """A single planning request. Multi-city arrives in S8."""

    city: str = Field(min_length=1)
    interests: list[str] = Field(min_length=1)
    days: int = Field(default=1, ge=1, le=3)


class ItineraryItem(BaseModel):
    """One stop in a day, grounded to a real POI."""

    name: str
    category: str
    latitude: float
    longitude: float
    note: str | None = None


class DayPlan(BaseModel):
    day: int
    items: list[ItineraryItem] = []


class Itinerary(BaseModel):
    """The planner's output: grounded, honest, cost-tagged."""

    city: str
    summary_markdown: str
    days: list[DayPlan] = []  # structured per-day plan: S7/S8
    pois_used: list[POI] = []
    weather: list[WeatherDaily] = []
    warnings: list[str] = []
    grounded: bool = True
    cost_usd: float = 0.0
    corrections: int = 0  # corrective re-composes the critic triggered (S7)
    center: GeoLocation | None = None  # resolved city center, for inter-city routing (S8)


class CriticVerdict(BaseModel):
    """The critic sub-agent's verdict on a draft itinerary (S7, corrective RAG)."""

    ok: bool
    invented_places: list[str] = []
    issues: list[str] = []

    @property
    def has_issues(self) -> bool:
        return bool(self.invented_places or self.issues)


class TripRequest(BaseModel):
    """A multi-city trip request (S8)."""

    cities: list[str] = Field(min_length=1, max_length=5)
    interests: list[str] = Field(min_length=1)
    days: int = Field(default=3, ge=1, le=10)


class TripItinerary(BaseModel):
    """A merged multi-city plan: per-city itineraries + inter-city transitions."""

    summary_markdown: str
    cities: list[Itinerary] = []
    inter_city_legs: list[RouteLeg] = []
    failed_cities: list[str] = []
    warnings: list[str] = []
    cost_usd: float = 0.0
