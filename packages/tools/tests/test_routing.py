"""Routing tool: contract (mocked) + live integration."""

from __future__ import annotations

from typing import Any

import pytest

import tp_tools.routing as routing_mod
from tp_tools._http import ToolError
from tp_tools.routing import route_matrix


async def test_route_matrix_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "code": "Ok",
            "durations": [[0.0, 600.0], [600.0, 0.0]],
            "distances": [[0.0, 5000.0], [5000.0, 0.0]],
        }

    monkeypatch.setattr(routing_mod, "fetch_json", _fake)
    matrix = await route_matrix([(48.85, 2.35), (48.86, 2.34)])
    assert matrix.durations_s[0][1] == 600.0
    assert matrix.distances_m[1][0] == 5000.0


async def test_route_matrix_needs_two_points() -> None:
    with pytest.raises(ToolError):
        await route_matrix([(48.85, 2.35)])


@pytest.mark.integration
async def test_route_matrix_live() -> None:
    # Paris center -> Louvre
    matrix = await route_matrix([(48.8566, 2.3522), (48.8606, 2.3376)])
    assert len(matrix.durations_s) == 2
    assert matrix.durations_s[0][1] > 0.0
