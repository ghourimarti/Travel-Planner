"""Serving chains: an ordered failover preference over venues, per call-point.

TWO LEVELS, DELIBERATELY (Decision 24, as amended)
--------------------------------------------------
    SERVING_CHAIN     one baseline order for every tier
    CHAIN_<TIER>      overrides the baseline for that tier only

The baseline exists because most of the time one order is the whole policy and
three variables to say it is noise. The per-tier override exists because this
system is TIERED, and one line cannot say "local for the cheap fan-out, hosted
for the planner".

That distinction is not cosmetic. A single loaded 7-8B model serves *every* tier
identically — it cannot be three different models. So putting ``local`` first on
FRONTIER hands multi-city planning and the critic to a 7B, which is exactly where
itinerary quality is decided. The shipped default therefore leaves FRONTIER
hosted; going fully local is a one-line edit whose quality cost the eval gate
measures rather than hides.

    SERVING_CHAIN=local-sglang,groq,openai
    CHAIN_FRONTIER=openai:gpt-4o,anthropic:claude-opus-4-8

GRAMMAR
-------
    local                     the engine named by SERVING_ENGINE
    local-vllm / local-sglang that engine explicitly, whatever SERVING_ENGINE says
    groq / openai / anthropic hosted venue, this tier's default model
    venue:model               that venue, overriding the model for this call-point

A leg whose URL or key is missing is SKIPPED with a warning naming it — never a
runtime 401, and never a silent downgrade to a venue you did not choose.

WHY A LIST AND NOT PRIORITY NUMBERS
-----------------------------------
Numbers split identity from order into two places that can disagree, and
inserting a leg means renumbering the rest.

WHY A PAID LEG GOES LAST
------------------------
``openai`` is the leg that still answers when everything free is down. It is also
the tripwire: the moment it starts serving, its call counter climbs and cost per
itinerary stops reading ~$0 — which is how a dead local engine is discovered long
before a user reports slowness.
"""

from __future__ import annotations

from dataclasses import dataclass

from tp_core.exceptions import ConfigError
from tp_core.llm.types import Provider, Tier

#: Venues backed by a GPU we operate. Their model is whatever the engine loaded,
#: so it comes from the provider instance rather than a static catalog.
LOCAL_VENUES: frozenset[Provider] = frozenset(
    {Provider.LOCAL_VLLM, Provider.LOCAL_SGLANG}
)

#: Engine names that are NOT venues on their own. Naming one bare is the easy
#: mistake, and the resulting error must say so rather than "invalid entry".
_ENGINES = {"vllm", "sglang"}

_BY_NAME: dict[str, Provider] = {
    "local-vllm": Provider.LOCAL_VLLM,
    "local-sglang": Provider.LOCAL_SGLANG,
    "groq": Provider.GROQ,
    "openai": Provider.OPENAI,
    "anthropic": Provider.ANTHROPIC,
}


@dataclass(frozen=True)
class ChainLeg:
    """One rung of a failover chain."""

    venue: Provider
    #: Explicit ``venue:model`` override. None means "use this tier's default for
    #: the venue", or — for a local engine — whatever model it actually loaded.
    model: str | None = None


def parse_chain(raw: str, *, default_engine: str = "sglang") -> list[ChainLeg]:
    """Parse one chain string into ordered legs.

    Raises ConfigError naming the fix. A malformed chain otherwise surfaces as a
    container exiting non-zero behind a "dependency failed to start" message that
    identifies nothing.
    """
    entries = [e.strip().lower() for e in raw.split(",") if e.strip()]
    if not entries:
        raise ConfigError("chain is empty; name at least one venue.")

    legs: list[ChainLeg] = []
    seen: set[Provider] = set()
    for entry in entries:
        name, _, raw_override = entry.partition(":")
        name = name.strip()
        override: str | None = raw_override.strip() or None

        if name == "local":
            name = f"local-{default_engine}"
        if name in _ENGINES:
            raise ConfigError(
                f"chain entry '{name}' is an ENGINE, not a venue. Engines only "
                f"exist on the local venue, so write 'local-{name}' (or plain "
                f"'local' plus SERVING_ENGINE={name})."
            )
        venue = _BY_NAME.get(name)
        if venue is None:
            raise ConfigError(
                f"chain entry '{name}' is not a known venue. "
                f"Known: {', '.join(sorted(_BY_NAME))}."
            )
        if venue in seen:
            raise ConfigError(f"chain lists '{name}' twice; each venue may appear once.")
        seen.add(venue)
        legs.append(ChainLeg(venue=venue, model=override))
    return legs


def model_for(provider: Provider, tier: Tier) -> str | None:
    """The hosted model this provider serves for a tier, or None if it serves none.

    Local venues return None on purpose: their model is whatever the engine was
    started with, which only the provider instance knows.
    """
    if provider in LOCAL_VENUES:
        return None
    from tp_core.llm.models import TIER_ROUTING

    for p, model in TIER_ROUTING[tier]:
        if p is provider:
            return model
    return None


def raw_chain_for_tier(
    tier: Tier, *, baseline: str, per_tier: dict[Tier, str]
) -> str:
    """Pick the chain string that governs a tier.

    Precedence is deliberately narrow-beats-broad: a CHAIN_<TIER> override wins
    over the SERVING_CHAIN baseline, and an empty string means "not set" rather
    than "empty chain" — so clearing an override falls back instead of erroring.
    """
    specific = (per_tier.get(tier) or "").strip()
    return specific or (baseline or "").strip()
