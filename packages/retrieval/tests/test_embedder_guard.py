"""The index/query embedder mismatch guard.

This is the one RAG failure that produces no error, no exception and no dimension
mismatch — `text-embedding-3-large` at 1024 dims and `voyage-3` both emit 1024-d
vectors, so every structural check passes while the query vector lives in a different
space from the index. Retrieval still ranks, still returns, just quietly worse.

These tests pin the three properties that make the guard useful rather than annoying.
"""

from __future__ import annotations

import asyncio
from typing import Any

import tp_retrieval.retrieve as retrieve


class _Store:
    def __init__(self, meta: dict[str, Any] | None) -> None:
        self._meta = meta

    async def read_meta(self) -> dict[str, Any] | None:
        return self._meta


class _Embedder:
    dim = 1024

    def __init__(self, model: str) -> None:
        self.model = model


def _warn(meta, model, monkeypatch) -> list[tuple]:
    seen: list[tuple] = []
    monkeypatch.setattr(retrieve, "record_error", lambda t: seen.append(("metric", t)))
    monkeypatch.setattr(
        retrieve._log, "warning", lambda ev, **kw: seen.append(("log", ev, kw))
    )
    retrieve._warn_on_embedder_mismatch(_Embedder(model), _Store(meta))  # type: ignore[arg-type]
    return seen


def test_mismatch_warns_and_counts(monkeypatch):
    seen = _warn({"embedder_model": "voyage-3"}, "text-embedding-3-large", monkeypatch)
    kinds = {s[0] for s in seen}
    assert kinds == {"metric", "log"}, seen
    assert ("metric", "embedder_mismatch") in seen
    log = next(s for s in seen if s[0] == "log")
    # The warning must name BOTH models — "something is wrong" is not actionable.
    assert log[2]["indexed_with"] == "voyage-3"
    assert log[2]["querying_with"] == "text-embedding-3-large"


def test_mismatch_does_not_raise(monkeypatch):
    """LOUD, NEVER FATAL. Raising would take a working app down over a quality smell."""
    monkeypatch.setattr(retrieve, "record_error", lambda t: None)
    retrieve._warn_on_embedder_mismatch(  # must simply return
        _Embedder("text-embedding-3-large"), _Store({"embedder_model": "voyage-3"})  # type: ignore[arg-type]
    )


def test_matching_embedder_is_silent(monkeypatch):
    assert _warn({"embedder_model": "voyage-3"}, "voyage-3", monkeypatch) == []


def test_missing_stamp_is_not_a_mismatch(monkeypatch):
    """Indexes built before provenance existed have no stamp.

    Treating absence as failure would cry wolf on every pre-existing collection, and a
    guard that fires constantly is one people learn to ignore — which costs more than
    not having it.
    """
    assert _warn(None, "voyage-3", monkeypatch) == []
    assert _warn({}, "voyage-3", monkeypatch) == []


def test_unreadable_store_never_breaks_startup(monkeypatch):
    class _Broken:
        async def read_meta(self):
            raise RuntimeError("qdrant down")

    monkeypatch.setattr(retrieve, "record_error", lambda t: None)
    retrieve._warn_on_embedder_mismatch(_Embedder("x"), _Broken())  # type: ignore[arg-type]


def test_meta_roundtrip_shape():
    """What ingest writes is what the guard reads."""
    store = _Store({"_meta": True, "embedder_model": "voyage-3", "dim": 1024})
    meta = asyncio.run(store.read_meta())
    assert meta is not None
    assert meta["embedder_model"] == "voyage-3"
    assert meta["dim"] == 1024
