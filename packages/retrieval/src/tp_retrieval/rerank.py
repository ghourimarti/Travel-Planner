"""Rerankers behind an interface (Decision 2).

The default is an LLM reranker on the CHEAP tier (keyless beyond OpenAI). Cohere
Rerank / bge-reranker swap in during hardening with no caller change.
"""

from __future__ import annotations

import json
import re

from tp_core.llm import LLMGateway, Message, Tier
from tp_tools.models import POI


class LLMReranker:
    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def rerank(
        self, city: str, interests: list[str], pois: list[POI], *, top_n: int
    ) -> list[POI]:
        if len(pois) <= top_n:
            return pois
        listing = "\n".join(f"{i}: {p.name} ({p.category})" for i, p in enumerate(pois))
        system = (
            "You rank candidate places for a trip. Return ONLY a JSON list of the "
            f"{top_n} best-matching candidate indices, best first, e.g. [3,0,7]."
        )
        user = f"CITY: {city}\nINTERESTS: {', '.join(interests)}\nCANDIDATES:\n{listing}"
        resp = await self._gateway.complete(
            [Message(role="system", content=system), Message(role="user", content=user)],
            Tier.CHEAP,
            max_tokens=120,
        )
        order = _parse_indices(resp.text, len(pois))
        if not order:
            return pois[:top_n]
        ranked = [pois[i] for i in order]
        seen = set(order)
        ranked.extend(p for i, p in enumerate(pois) if i not in seen)
        return ranked[:top_n]


def _parse_indices(text: str, n: int) -> list[int]:
    match = re.search(r"\[[^\]]*\]", text)
    if match is None:
        return []
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    out: list[int] = []
    for x in raw:
        if isinstance(x, int) and 0 <= x < n and x not in out:
            out.append(x)
    return out
