"""Domain contracts for planning.

This is the boundary the API (S4), the eval harness (S5), and the frontend (S13)
all bind to — so it is settled now and only *extended* later (cheap), never
reshaped (expensive). The structured ``days`` list is defined now for forward
compatibility but populated by the model from S7/S8; the S4 slice fills
``summary_markdown`` + the deterministic grounding fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from tp_tools.models import POI, WeatherDaily


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
