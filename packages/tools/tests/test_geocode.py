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
