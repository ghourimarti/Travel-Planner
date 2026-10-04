"""The destination a prompt names must be the place the plan is anchored on.

Given only `kyota`, the model auto-corrected the typo in prose and described Kyoto,
Japan over the weather of the Ugandan village the plan was anchored on - right under a
warning naming that village (found live, 2026-09-29).
"""

from __future__ import annotations

from tp_agents.nodes import _fallback_intro
from tp_agents.prompts import build_critic_messages, build_messages, prompt_place
from tp_agents.schemas import PlanRequest
from tp_tools.models import GeoLocation

KYOTA = GeoLocation(name="kyota", latitude=0.613, longitude=31.454, country="Uganda",
                    display_name="Kyota, Mubende, Central Region, Uganda",
                    importance=0.147, kind="village")
KYOTO = GeoLocation(name="Kyoto", latitude=35.01, longitude=135.77, country="Japan",
                    display_name="Kyoto, Kyoto Prefecture, Japan",
                    importance=0.709, kind="city")


def test_obscure_anchor_is_named_in_every_prompt() -> None:
    req = PlanRequest(city="kyota", interests=["temples"])
    place = prompt_place(KYOTA)
    assert place == "Kyota, Uganda"

    system, human = (m.content for m in build_messages(req, [], [], place=place))
    assert "trip to Kyota, Uganda" in system
    assert "City: Kyota, Uganda" in human

    critic_user = build_critic_messages(req, ["x"], "draft", place=place)[1].content
    assert "CITY: Kyota, Uganda" in critic_user

    intro = _fallback_intro(req, grounded=False, place=place)
    assert intro.startswith("A short guide to Kyota, Uganda.")


def test_prominent_anchor_leaves_every_prompt_unchanged() -> None:
    req = PlanRequest(city="Kyoto", interests=["temples"])
    assert prompt_place(KYOTO) is None
    assert prompt_place(None) is None

    before = [m.content for m in build_messages(req, [], [])]
    after = [m.content for m in build_messages(req, [], [], place=prompt_place(KYOTO))]
    assert after == before
