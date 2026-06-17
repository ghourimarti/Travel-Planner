"""S11c: the metric helpers move the right time-series and render() exposes them.

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
