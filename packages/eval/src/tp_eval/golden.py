"""Versioned golden set — FIXED fixtures (not live tools) so the baseline is reproducible.

Each case pins the POIs/weather the planner is given, so the eval measures the real
model on deterministic inputs. Includes an empty-POI case to assert honest
degradation (and to surface the S4 grounding leak the judge will quantify).
"""

from __future__ import annotations

from pydantic import BaseModel
from tp_agents.schemas import PlanRequest
from tp_tools.models import POI, WeatherDaily

_FAIR = [WeatherDaily(date="2026-09-15", temp_max_c=24.0, temp_min_c=18.0, precipitation_mm=0.0)]


class GoldenCase(BaseModel):
    id: str
    request: PlanRequest
    pois: list[POI]
    weather: list[WeatherDaily]
    notes: str = ""


GOLDEN: list[GoldenCase] = [
    GoldenCase(
        id="tokyo-temples-food",
        request=PlanRequest(city="Tokyo", interests=["temples", "food"], days=1),
        pois=[
            POI(name="Senso-ji", category="temples", latitude=35.715, longitude=139.797),
            POI(name="Meiji Shrine", category="temples", latitude=35.676, longitude=139.699),
            POI(name="Tsukiji Outer Market", category="food", latitude=35.665, longitude=139.770),
            POI(name="Ichiran Shibuya", category="food", latitude=35.661, longitude=139.701),
        ],
        weather=_FAIR,
    ),
    GoldenCase(
        id="paris-museums",
        request=PlanRequest(city="Paris", interests=["museums"], days=1),
        pois=[
            POI(name="Louvre Museum", category="museums", latitude=48.861, longitude=2.338),
            POI(name="Musee d'Orsay", category="museums", latitude=48.860, longitude=2.327),
            POI(name="Centre Pompidou", category="museums", latitude=48.861, longitude=2.352),
        ],
        weather=_FAIR,
    ),
    GoldenCase(
        id="kyoto-temples",
        request=PlanRequest(city="Kyoto", interests=["temples"], days=1),
        pois=[
            POI(name="Kinkaku-ji", category="temples", latitude=35.039, longitude=135.729),
            POI(name="Kiyomizu-dera", category="temples", latitude=34.995, longitude=135.785),
            POI(
                name="Fushimi Inari Taisha", category="temples", latitude=34.967, longitude=135.773
            ),
        ],
        weather=_FAIR,
    ),
    GoldenCase(
        id="rome-history",
        request=PlanRequest(city="Rome", interests=["history"], days=1),
        pois=[
            POI(name="Colosseum", category="history", latitude=41.890, longitude=12.492),
            POI(name="Roman Forum", category="history", latitude=41.892, longitude=12.485),
            POI(name="Pantheon", category="history", latitude=41.899, longitude=12.477),
        ],
        weather=_FAIR,
    ),
    GoldenCase(
        id="barcelona-nature",
        request=PlanRequest(city="Barcelona", interests=["nature"], days=1),
        pois=[
            POI(name="Park Guell", category="nature", latitude=41.414, longitude=2.153),
            POI(name="Montjuic", category="nature", latitude=41.363, longitude=2.165),
        ],
        weather=_FAIR,
    ),
    GoldenCase(
        id="tinyville-empty",
        request=PlanRequest(city="Tinyville", interests=["nightlife"], days=1),
        pois=[],  # empty on purpose: must degrade honestly; judge should catch any invented venue
        weather=_FAIR,
        notes="No POIs — asserts honest degradation + surfaces the grounding-leak failure mode.",
    ),
    GoldenCase(
        id="kyoto-empty",
        request=PlanRequest(city="Kyoto", interests=["temples"], days=1),
        pois=[],  # adversarial: famous city, NO POIs given
        weather=_FAIR,
        notes="Famous city + empty POIs: catches the grounding leak (S4 finding).",
    ),
]
