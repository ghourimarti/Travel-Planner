"""CLI: run the golden set, print a scorecard, write the baseline JSON.

    uv run python -m tp_eval                 # deterministic metrics only (still calls compose LLM)
    uv run python -m tp_eval --judge gateway # + LLM-judge faithfulness/relevancy (costs ~cents)

Needs OPENAI_API_KEY (the real model composes each itinerary).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from tp_core.llm import LLMGateway

from tp_eval.golden import GOLDEN
from tp_eval.judge import GatewayJudge
from tp_eval.runner import EvalReport, Judge, run_eval

_DEFAULT_OUT = Path("packages/eval/baselines/baseline.json")


def _print_report(report: EvalReport) -> None:
    print("\n=== Eval scorecard ===")
    for r in report.results:
        c = r.scorecard
        line = (
            f"  {c.case_id:<22} success={c.success!s:<5} grounded={c.grounded!s:<5} "
            f"cov={c.poi_coverage:<5} cost=${c.cost_usd:.4f} honest={c.honest_on_degrade!s:<5}"
        )
        if r.judge is not None:
            viol = ",".join(r.judge.violations[:3]) or "-"
            line += f" faithful={r.judge.faithful!s} rel={r.judge.relevance_score:.2f}"
            line += f" invented=[{viol}]"
        print(line)
    a = report
    print("\n=== Aggregate ===")
    print(f"  cases={a.n_cases}  success={a.success_rate}  grounded={a.grounded_rate}")
    print(f"  mean_poi_coverage={a.mean_poi_coverage}  mean_cost=${a.mean_cost_usd}")
    print(f"  under_budget={a.under_budget_rate}  honest_on_degrade={a.honest_on_degrade_rate}")
    if a.faithfulness_rate is not None:
        print(f"  faithfulness={a.faithfulness_rate}  mean_relevance={a.mean_relevance}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Travel Planner eval harness")
    parser.add_argument("--judge", choices=["none", "gateway", "ragas"], default="none")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    gateway = LLMGateway.from_settings()
    judge: Judge | None
    if args.judge == "gateway":
        judge = GatewayJudge(gateway)
    elif args.judge == "ragas":
        from tp_eval.ragas_judge import RagasJudge  # lazy: needs `uv sync --extra ragas`

        judge = RagasJudge(model="gpt-4o-mini")
    else:
        judge = None

    report = asyncio.run(run_eval(GOLDEN, gateway=gateway, judge=judge))
    _print_report(report)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nBaseline written to {args.out}")


if __name__ == "__main__":
    main()
