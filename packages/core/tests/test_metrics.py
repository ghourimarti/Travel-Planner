"""The metric helpers move the right time-series and render() exposes them.

Counters accumulate process-wide, so each test asserts a DELTA via the registry's
``get_sample_value`` rather than an absolute value.
"""

from __future__ import annotations

from prometheus_client import REGISTRY
from tp_core import metrics


def _value(name: str, labels: dict[str, str] | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_render_returns_prometheus_text():
    payload, content_type = metrics.render()
    assert content_type.startswith("text/plain")
    assert b"tp_runs_total" in payload


def test_record_run_counts_status_duration_and_cost():
    before = _value("tp_runs_total", {"status": "succeeded"})
    cost_before = _value("tp_run_cost_usd_count")
    dur_before = _value("tp_run_duration_seconds_count")

    metrics.record_run("succeeded", 12.5, 0.05)

    assert _value("tp_runs_total", {"status": "succeeded"}) == before + 1
    assert _value("tp_run_cost_usd_count") == cost_before + 1
    assert _value("tp_run_duration_seconds_count") == dur_before + 1


def test_failed_run_counts_but_records_no_cost():
    before = _value("tp_runs_total", {"status": "failed"})
    cost_before = _value("tp_run_cost_usd_count")

    metrics.record_run("failed", 3.0, 0.0)

    assert _value("tp_runs_total", {"status": "failed"}) == before + 1
    assert _value("tp_run_cost_usd_count") == cost_before  # no cost observed on failure


def test_record_llm_revision_and_dispatch():
    llm = {"tier": "frontier", "provider": "openai"}
    llm_before = _value("tp_llm_calls_total", llm)
    metrics.record_llm("frontier", "openai")
    assert _value("tp_llm_calls_total", llm) == llm_before + 1

    rev_before = _value("tp_critic_revisions_total")
    metrics.record_revision()
    assert _value("tp_critic_revisions_total") == rev_before + 1

    disp = {"endpoint": "plan", "outcome": "queued"}
    disp_before = _value("tp_dispatch_total", disp)
    metrics.record_dispatch("plan", "queued")
    assert _value("tp_dispatch_total", disp) == disp_before + 1


def test_known_series_exist_before_anything_happens():
    """Absence used to be read as "missing": verify-all failed BECAUSE no error had
    occurred, and Prometheus dropped every count before a series' first scrape."""
    for error_type in metrics.KNOWN_ERROR_TYPES:
        assert REGISTRY.get_sample_value("tp_errors_total", {"type": error_type}) is not None
    for series in (
        ("tp_dispatch_total", {"endpoint": "plan", "outcome": "rate_limited"}),
        ("tp_dispatch_total", {"endpoint": "trip", "outcome": "failed"}),
        ("tp_rate_limit_events_total", {"scope": "tenant_min", "outcome": "refused"}),
        ("tp_itinerary_outcome_total", {"kind": "not_found"}),
        ("tp_cache_events_total", {"tool": "geo", "result": "error"}),
        ("tp_stage_duration_seconds_count", {"stage": "critic"}),
        ("tp_runs_total", {"status": "failed"}),
    ):
        assert REGISTRY.get_sample_value(*series) is not None, series


def test_venue_series_are_never_primed():
    """Grafana's venue blocks read "not served since restart" from NO DATA, so a venue
    must have no series until it is actually called. Priming them at 0 erased that
    signal (2026-09-29) - this pins the revert."""
    venue_families = {
        "tp_llm_calls", "tp_llm_tokens", "tp_llm_cost_usd",
        "tp_venue_circuit_state", "tp_venue_latency_seconds",
    }

    def venue_samples() -> set[tuple[str, tuple[tuple[str, str], ...]]]:
        return {
            (s.name, tuple(sorted(s.labels.items())))
            for family in REGISTRY.collect()
            if family.name in venue_families
            for s in family.samples
        }

    before = venue_samples()
    metrics._prime_bounded()
    assert venue_samples() == before
    assert not hasattr(metrics, "prime_venue_metrics")


def test_spend_today_is_a_level_set_from_the_ledger():
    """A gauge, set (not added to): each scrape replaces it with the day's ledger total."""
    metrics.record_spend_today(0.0042)
    metrics.record_spend_today(0.0055)
    assert _value("tp_spend_today_usd") == 0.0055
