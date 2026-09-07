"""Critic sub-agent: validates a draft itinerary, driving the corrective loop.

Runs on the FRONTIER tier — this is the quality gate, so it gets the best model.
It is the runtime counterpart to the offline grounding metric: it catches an
invented place and sends the draft back for a corrective re-compose. Fails OPEN
(passes) on an unparseable verdict or a degraded/ungrounded draft, so a critic
glitch never traps the user.
"""

from __future__ import annotations

import json
import re
from typing import Any

from tp_core.llm import LLMGateway, Tier

from tp_agents.prompts import build_critic_messages
from tp_agents.schemas import CriticVerdict, PlanRequest
from tp_agents.state import PlannerState


def _extract_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None
    try:
        parsed: Any = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def critic_node(state: PlannerState, gateway: LLMGateway) -> dict[str, Any]:
    itinerary = state.get("itinerary")
    pois = state.get("pois") or []
    # Nothing to ground against (degraded / no POIs) — already flagged honestly; pass.
    if itinerary is None or not pois:
        return {"critic_verdict": CriticVerdict(ok=True)}

    request: PlanRequest = state["request"]
    allowed = [p.name for p in pois]
    messages = build_critic_messages(request, allowed, itinerary.summary_markdown)
    resp = await gateway.complete(messages, Tier.FRONTIER, max_tokens=400)
    # The critic runs on the frontier tier, so its call is real money. Fold it into
    # the run's cost: otherwise the figure reported to the caller understates spend,
    # and the budget guard in `_should_revise` — which reads this number — would let a
    # run overshoot its cap by whatever the critic consumed. Charged even when the
    # verdict fails to parse below, because the tokens were spent either way.
    charged = itinerary.model_copy(
        update={
            "cost_usd": round(itinerary.cost_usd + resp.usage.cost_usd, 6),
            # The critic runs on FRONTIER, which may be a different venue than the
            # composer used. Recording it is what makes "the 7B wrote it, the
            # frontier model checked it" visible rather than assumed.
            "venues": sorted({resp.provider.value, *itinerary.venues}),
        }
    )
    data = _extract_json(resp.text)
    if data is None:
        return {"critic_verdict": CriticVerdict(ok=True), "itinerary": charged}  # fail open

    invented = [str(x) for x in data.get("invented_places", []) if str(x).strip()]
    issues = [str(x) for x in data.get("issues", []) if str(x).strip()]
    ok = not invented and not issues
    return {
        "critic_verdict": CriticVerdict(ok=ok, invented_places=invented, issues=issues),
        "itinerary": charged,
    }
