"""LLM-judge faithfulness + relevancy through our own gateway (no heavy deps, our cost accounting).

Faithfulness is the metric that matters for this product: does the itinerary name any
place that was NOT in the provided POIs ("invented")? Generic phrases ("a local cafe")
are not violations. Runs on the CHEAP tier — judging is high-volume and low-difficulty.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel
from tp_agents.schemas import Itinerary, PlanRequest
from tp_core.llm import LLMGateway, Message, Tier

_SYSTEM = (
    "You are a strict travel-itinerary evaluator. You are given the ONLY allowed real "
    "places and an itinerary. Find every specific named attraction, venue, or landmark in "
    "the itinerary that is NOT in the allowed list (an 'invented' place). Generic phrases "
    "like 'a local restaurant' or 'a nearby temple' are NOT violations. Also rate, from 0 to "
    "1, how well the itinerary addresses the requested city and interests. "
    'Respond with ONLY JSON: {"invented_places": [string], "relevance_0_1": number}.'
)


class JudgeResult(BaseModel):
    faithful: bool
    violations: list[str]
    faithfulness_score: float  # 1.0 if no invented places else 0.0
    relevance_score: float
    parse_error: bool = False


def _extract_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None
    try:
        parsed: Any = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class GatewayJudge:
    """LLM-as-judge running through the project's own gateway."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def judge(
        self, request: PlanRequest, allowed_names: list[str], itinerary: Itinerary
    ) -> JudgeResult:
        user = (
            f"ALLOWED PLACES: {allowed_names}\n"
            f"CITY: {request.city}\n"
            f"INTERESTS: {request.interests}\n\n"
            f"ITINERARY:\n{itinerary.summary_markdown}"
        )
        resp = await self._gateway.complete(
            [Message(role="system", content=_SYSTEM), Message(role="user", content=user)],
            Tier.CHEAP,
            max_tokens=400,
        )
        data = _extract_json(resp.text)
        if data is None:
            return JudgeResult(
                faithful=False,
                violations=[],
                faithfulness_score=0.0,
                relevance_score=0.0,
                parse_error=True,
            )
        invented = [str(x) for x in data.get("invented_places", []) if str(x).strip()]
        try:
            relevance = float(data.get("relevance_0_1", 0.0))
        except (TypeError, ValueError):
            relevance = 0.0
        faithful = len(invented) == 0
        return JudgeResult(
            faithful=faithful,
            violations=invented,
            faithfulness_score=1.0 if faithful else 0.0,
            relevance_score=max(0.0, min(1.0, relevance)),
        )
