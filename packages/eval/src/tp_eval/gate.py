"""Eval gate (P6.4a): turn an :class:`EvalReport` into a pass/fail CI verdict.

Two kinds of check:

* **Hard floors** — absolute invariants that must hold on every run regardless of
  history: every case produces an itinerary, nothing breaches the per-itinerary
  budget, degraded runs stay honest, and mean cost stays under the Phase-1 ceiling.
* **Regression** — a fresh run's *quality rates* must not drop more than a small
  tolerance below the committed baseline (``baselines/baseline.json``).

Cost is deliberately gated on the **absolute budget ceiling**, not a relative delta
vs baseline: the baseline mean cost is fractions of a cent and real composes vary
with tokens/model, so a tight relative cost gate would only flap. The budget is the
NFR that actually matters. Given a report this is free + deterministic, so CI can
block a bad model/prompt before it ever promotes.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from tp_core.settings import DEFAULT_MAX_COST_USD

from tp_eval.runner import EvalReport

DEFAULT_BASELINE = Path("packages/eval/baselines/baseline.json")

_RATE_TOL = 0.05  # a quality rate may sit at most 5 points below baseline before it fails
_EPS = 1e-9


class GateCheck(BaseModel):
    metric: str
    kind: str  # "floor" | "regression"
    observed: float
    threshold: float
    ok: bool
    detail: str


class GateResult(BaseModel):
    passed: bool
    checks: list[GateCheck]

    @property
    def failures(self) -> list[GateCheck]:
        return [c for c in self.checks if not c.ok]


def load_baseline(path: Path = DEFAULT_BASELINE) -> EvalReport | None:
    """Load the committed baseline report, or ``None`` if there isn't one yet."""
    if not path.exists():
        return None
    return EvalReport.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_gate(
    report: EvalReport,
    *,
    baseline: EvalReport | None = None,
    budget_usd: float = DEFAULT_MAX_COST_USD,
) -> GateResult:
    """Score ``report`` against hard floors + (optional) baseline regression checks."""
    checks: list[GateCheck] = []

    def at_least(metric: str, kind: str, observed: float, threshold: float, detail: str) -> None:
        checks.append(
            GateCheck(
                metric=metric,
                kind=kind,
                observed=round(observed, 4),
                threshold=round(threshold, 4),
                ok=observed >= threshold - _EPS,
                detail=detail,
            )
        )

    def at_most(metric: str, kind: str, observed: float, threshold: float, detail: str) -> None:
        checks.append(
            GateCheck(
                metric=metric,
                kind=kind,
                observed=round(observed, 4),
                threshold=round(threshold, 4),
                ok=observed <= threshold + _EPS,
                detail=detail,
            )
        )

    # --- hard floors (absolute invariants) ---
    at_least(
        "success_rate", "floor", report.success_rate, 1.0, "every case must produce an itinerary"
    )
    at_least(
        "under_budget_rate", "floor", report.under_budget_rate, 1.0, "no case may exceed the budget"
    )
    at_least(
        "honest_on_degrade_rate", "floor", report.honest_on_degrade_rate, 1.0,
        "degraded (no-POI) runs must warn",
    )
    at_most(
        "mean_cost_usd", "floor", report.mean_cost_usd, budget_usd,
        f"mean cost must stay <= ${budget_usd:.2f} ceiling",
    )

    # --- regression vs baseline (quality rates only) ---
    if baseline is not None:
        def regress(metric: str, observed: float, base: float) -> None:
            at_least(
                metric, "regression", observed, base - _RATE_TOL,
                f"within {_RATE_TOL} of baseline {round(base, 4)}",
            )

        regress("grounded_rate", report.grounded_rate, baseline.grounded_rate)
        regress("mean_poi_coverage", report.mean_poi_coverage, baseline.mean_poi_coverage)
        if baseline.faithfulness_rate is not None and report.faithfulness_rate is not None:
            regress("faithfulness_rate", report.faithfulness_rate, baseline.faithfulness_rate)
        if baseline.mean_relevance is not None and report.mean_relevance is not None:
            regress("mean_relevance", report.mean_relevance, baseline.mean_relevance)

    return GateResult(passed=all(c.ok for c in checks), checks=checks)
