"""P6.4a: the eval gate turns an EvalReport into a CI pass/fail verdict, hermetically.

No LLM — we construct EvalReport aggregates directly and assert the gate's logic
(hard floors + regression-vs-baseline). This is the layer CI calls to block a bad
model/prompt before it promotes.
"""

from __future__ import annotations

from tp_eval.gate import evaluate_gate
from tp_eval.runner import EvalReport

# A healthy baseline (mirrors the committed baselines/baseline.json shape).
_BASELINE = EvalReport(
    n_cases=7,
    success_rate=1.0,
    grounded_rate=0.7143,
    mean_poi_coverage=1.0,
    mean_cost_usd=0.0015,
    under_budget_rate=1.0,
    honest_on_degrade_rate=1.0,
    faithfulness_rate=1.0,
    mean_relevance=0.8,
    results=[],
)


def _report(**overrides: float) -> EvalReport:
    base = dict(
        n_cases=7,
        success_rate=1.0,
        grounded_rate=0.7143,
        mean_poi_coverage=1.0,
        mean_cost_usd=0.006,  # realistic per-itinerary cost, well under the $0.30 ceiling
        under_budget_rate=1.0,
        honest_on_degrade_rate=1.0,
        faithfulness_rate=1.0,
        mean_relevance=0.8,
    )
    base.update(overrides)
    return EvalReport(results=[], **base)  # type: ignore[arg-type]


def test_healthy_run_passes() -> None:
    result = evaluate_gate(_report(), baseline=_BASELINE)
    assert result.passed
    assert result.failures == []


def test_cost_above_budget_ceiling_fails() -> None:
    result = evaluate_gate(_report(mean_cost_usd=0.5), baseline=_BASELINE)
    assert not result.passed
    assert any(c.metric == "mean_cost_usd" and not c.ok for c in result.checks)


def test_under_budget_breach_fails_even_within_baseline() -> None:
    result = evaluate_gate(_report(under_budget_rate=0.85), baseline=_BASELINE)
    assert not result.passed
    assert any(c.metric == "under_budget_rate" and not c.ok for c in result.checks)


def test_grounded_regression_beyond_tolerance_fails() -> None:
    # baseline 0.7143; a drop to 0.57 is >0.05 below -> regression failure
    result = evaluate_gate(_report(grounded_rate=0.57), baseline=_BASELINE)
    assert not result.passed
    assert any(
        c.metric == "grounded_rate" and c.kind == "regression" and not c.ok for c in result.checks
    )


def test_grounded_dip_within_tolerance_passes() -> None:
    # 0.04 below baseline is inside the 0.05 tolerance band
    result = evaluate_gate(_report(grounded_rate=0.6743), baseline=_BASELINE)
    assert result.passed


def test_no_baseline_applies_floors_only() -> None:
    # Without a baseline, only the hard floors run; a healthy report still passes...
    assert evaluate_gate(_report(), baseline=None).passed
    # ...and a floor breach still fails.
    assert not evaluate_gate(_report(success_rate=0.8), baseline=None).passed
    # ...but a quality dip is NOT caught (no baseline to regress against).
    assert evaluate_gate(_report(grounded_rate=0.1), baseline=None).passed
