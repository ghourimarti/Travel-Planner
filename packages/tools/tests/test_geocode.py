"""tp_tools.geocode — mocked Nominatim (no network)."""

from __future__ import annotations

import asyncio

import pytest
import respx
from httpx import Response
from tp_core.exceptions import RetryableToolError
from tp_tools.geocode import geocode

_URL = "https://nominatim.openstreetmap.org/search"


def test_parses_first_result() -> None:
    with respx.mock:
        respx.get(_URL).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "lat": "35.011",
                        "lon": "135.768",
                        "display_name": "Kyoto, Japan",
                        "address": {"country": "Japan"},
                    }
                ],
            )
        )
        result = asyncio.run(geocode("Kyoto"))
    assert result is not None
    assert result.latitude == pytest.approx(35.011)
    assert result.longitude == pytest.approx(135.768)
    assert result.country == "Japan"


def test_no_results_returns_none() -> None:
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json=[]))
        assert asyncio.run(geocode("Zzxqnowhereville")) is None


def test_retries_then_raises_on_server_error() -> None:
    with respx.mock:
        endpoint = respx.get(_URL).mock(return_value=Response(503))
        with pytest.raises(RetryableToolError):
            asyncio.run(geocode("Kyoto"))
    assert endpoint.call_count == 3  # tenacity retried twice after the first failure


def _result(cls: str, typ: str, *, lat: str = "1.0", name: str = "X", country: str = "Somewhere",
            importance: float | None = None, addresstype: str | None = None) -> dict:
    r: dict = {"class": cls, "type": typ, "lat": lat, "lon": "2.0",
               "display_name": f"{name}, {country}", "address": {"country": country}}
    if importance is not None:
        r["importance"] = importance
    if addresstype is not None:
        r["addresstype"] = addresstype
    return r


def test_infrastructure_only_is_not_a_destination() -> None:
    """Measured live: `Kyot` -> a TV studio, `Pariss` -> a residential lane. Both used to
    become a confident itinerary anchored on infrastructure."""
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json=[
            _result("amenity", "studio", name="KYOT-TV Cable Channel 21"),
            _result("highway", "residential", name="Pariss Lane"),
        ]))
        assert asyncio.run(geocode("Kyot")) is None


def test_landmark_without_a_settlement_is_still_accepted() -> None:
    """The deny list must not turn a real destination into a refusal."""
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json=[
            _result("highway", "primary", lat="9.0"),
            _result("tourism", "attraction", lat="-13.16", name="Machu Picchu", country="Peru"),
        ]))
        result = asyncio.run(geocode("Machu Picchu"))
    assert result is not None
    assert result.latitude == pytest.approx(-13.16)


def test_settlement_beats_infrastructure_listed_first() -> None:
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json=[
            _result("highway", "primary", lat="9.0"),
            _result("place", "city", lat="35.0", importance=0.709, addresstype="city"),
        ]))
        result = asyncio.run(geocode("Kyoto"))
    assert result is not None
    assert result.latitude == pytest.approx(35.0)
    assert result.kind == "city"
    assert result.importance == pytest.approx(0.709)


def test_obscure_match_carries_its_prominence() -> None:
    """`kyota` -> a real village in Uganda at importance 0.147 - the same score as Hallstatt,
    which is why this WARNS rather than refusing."""
    from tp_tools.geocode import is_low_prominence

    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json=[
            _result("place", "village", lat="0.613", name="Kyota", country="Uganda",
                    importance=0.147, addresstype="village"),
        ]))
        result = asyncio.run(geocode("kyota"))
    assert result is not None
    assert result.kind == "village"
    assert is_low_prominence(result)


def test_asks_for_english_names() -> None:
    with respx.mock:
        route = respx.get(_URL).mock(return_value=Response(200, json=[]))
        asyncio.run(geocode("Kyoto"))
    assert route.calls.last.request.url.params["accept-language"] == "en"


def test_429_is_not_retried() -> None:
    """A rate limit means slow down: retrying it made every refusal three (2026-09-30)."""
    from tp_core.exceptions import UpstreamRateLimitedError

    with respx.mock:
        endpoint = respx.get(_URL).mock(return_value=Response(429, headers={"Retry-After": "30"}))
        with pytest.raises(UpstreamRateLimitedError):
            asyncio.run(geocode("Kyoto"))
    assert endpoint.call_count == 1


def test_repeated_429_pauses_nominatim_without_calling_it() -> None:
    """After 3 refusals the breaker opens: the next lookup fails fast, no request sent."""
    from tp_core.exceptions import UpstreamRateLimitedError

    with respx.mock:
        endpoint = respx.get(_URL).mock(return_value=Response(429))
        for _ in range(3):
            with pytest.raises(UpstreamRateLimitedError):
                asyncio.run(geocode("Kyoto"))
        with pytest.raises(UpstreamRateLimitedError, match="paused"):
            asyncio.run(geocode("Kyoto"))
    assert endpoint.call_count == 3
