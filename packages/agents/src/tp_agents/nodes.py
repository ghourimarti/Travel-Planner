"""Async graph nodes.

Each node degrades honestly on failure (Decision 21) — a failed tool becomes a
warning + a thinner plan, never an unhandled 500. The compose node short-circuits
(no LLM spend) when the city couldn't be resolved.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from tp_core.exceptions import ToolError
from tp_core.llm import LLMGateway, Tier
from tp_tools import find_pois, forecast, geocode
from tp_tools.models import POI, WeatherDaily

from tp_agents.prompts import build_messages
from tp_agents.schemas import Itinerary, PlanRequest
from tp_agents.state import PlannerState


async def geocode_node(state: PlannerState) -> dict[str, Any]:
    request: PlanRequest = state["request"]
    warnings = list(state.get("warnings", []))
    try:
        geo = await geocode(request.city)
    except ToolError as exc:
        warnings.append("Geocoding service failed.")
        return {"geo": None, "error": f"geocode failed: {exc}", "warnings": warnings}
    if geo is None:
        warnings.append(f"Could not find a place named '{request.city}'.")
        return {"geo": None, "error": f"city not found: {request.city}", "warnings": warnings}
    return {"geo": geo}


async def gather_node(state: PlannerState) -> dict[str, Any]:
    geo = state.get("geo")
    warnings = list(state.get("warnings", []))
    if geo is None:
        return {"pois": [], "weather": [], "warnings": warnings}

    request: PlanRequest = state["request"]
    poi_tasks = [find_pois(geo.latitude, geo.longitude, interest) for interest in request.interests]
    weather_task = forecast(geo.latitude, geo.longitude, days=request.days)
    *poi_results, weather_result = await asyncio.gather(
        *poi_tasks, weather_task, return_exceptions=True
    )

    pois: list[POI] = []
    for interest, result in zip(request.interests, poi_results, strict=True):
        if isinstance(result, BaseException):
            warnings.append(f"POI lookup failed for '{interest}'.")
        else:
            pois.extend(cast(list[POI], result))

    weather: list[WeatherDaily] = []
    if isinstance(weather_result, BaseException):
        warnings.append("Weather lookup failed.")
    else:
        weather = cast(list[WeatherDaily], weather_result)

    if not pois:
        warnings.append("No POIs found — the itinerary will be limited.")
    return {"pois": pois, "weather": weather, "warnings": warnings}


async def compose_node(state: PlannerState, gateway: LLMGateway) -> dict[str, Any]:
    request: PlanRequest = state["request"]
    warnings = list(state.get("warnings", []))
    geo = state.get("geo")
    pois = list(state.get("pois", []))
    weather = list(state.get("weather", []))

    if geo is None:
        itinerary = Itinerary(
            city=request.city,
            summary_markdown=(
                f"We couldn't find a place named **{request.city}**, so no itinerary could be "
                "created. Please check the spelling or try a nearby city."
            ),
            warnings=warnings,
            grounded=False,
        )
        return {"itinerary": itinerary}

    messages = build_messages(request, pois, weather)
    response = await gateway.complete(messages, Tier.MID, max_tokens=1200)
    itinerary = Itinerary(
        city=request.city,
        summary_markdown=response.text,
        pois_used=pois,
        weather=weather,
        warnings=warnings,
        grounded=bool(pois),
        cost_usd=response.usage.cost_usd,
    )
    return {"itinerary": itinerary}
