"""CLI: run the golden set, print a scorecard, write a baseline JSON.

    uv run python -m tp_eval                             # deterministic metrics on fixtures
    uv run python -m tp_eval --judge gateway             # + LLM-judge (faithfulness/relevancy)
    uv run python -m tp_eval --judge gateway --retrieve  # ground via real corpus retrieval (S6)

Needs OPENAI_API_KEY (the real model composes each itinerary). With --retrieve, run
`make ingest` first. Fixture runs write baseline.json; --retrieve runs write
baseline-rag.json (so the two baselines don't clobber each other).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from tp_core.llm import LLMGateway
from tp_retrieval import get_retriever

from tp_eval.gate import GateResult, evaluate_gate, load_baseline
from tp_eval.golden import GOLDEN
from tp_eval.judge import GatewayJudge
from tp_eval.runner import EvalReport, Judge, PoiRetriever, run_eval

_BASELINE = Path("packages/eval/baselines/baseline.json")
_BASELINE_RAG = Path("packages/eval/baselines/baseline-rag.json")


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


def _print_gate(result: GateResult) -> None:
    print("\n=== Eval gate ===")
    for c in result.checks:
        mark = "PASS" if c.ok else "FAIL"
        print(f"  [{mark}] {c.metric:<24} ({c.kind}) observed={c.observed} need {c.detail}")
    verdict = "PASSED" if result.passed else f"FAILED ({len(result.failures)} check(s))"
    print(f"  --> gate {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Travel Planner eval harness")
    parser.add_argument("--judge", choices=["none", "gateway", "ragas"], default="none")
    parser.add_argument("--retrieve", action="store_true", help="ground via real retrieval (S6)")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--gate",
        action="store_true",
        help="CI mode: compare vs baseline + exit non-zero on regression (no baseline write)",
    )
    parser.add_argument("--baseline", type=Path, default=None, help="baseline to gate against")
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

    retriever: PoiRetriever | None = get_retriever(gateway) if args.retrieve else None
    report = asyncio.run(run_eval(GOLDEN, gateway=gateway, judge=judge, retriever=retriever))
    _print_report(report)

    if args.gate:
        # CI promotion gate: compare vs baseline, never overwrite it, exit non-zero on regression.
        base_path = args.baseline or (_BASELINE_RAG if args.retrieve else _BASELINE)
        result = evaluate_gate(report, baseline=load_baseline(base_path))
        _print_gate(result)
        raise SystemExit(0 if result.passed else 1)

    out = args.out or (_BASELINE_RAG if args.retrieve else _BASELINE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nBaseline written to {out}")


if __name__ == "__main__":
    main()
