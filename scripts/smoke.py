"""One in-corpus plan and one that cannot be grounded, side by side.

The point is not "did the API answer" - it is whether the two answers DIFFER in the way
the product promises. An itinerary for a city the corpus has never seen must come back
with `venues == []` and `grounded == False`. An empty venue list is the evidence that no
model was called to invent one: text with no venue behind it is the failure mode this
whole pipeline exists to prevent.

Dispatch and polling are imported from the inspection module rather than reimplemented,
so this can never drift from how `scripts/inspect_stack_*.py` submits a run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _inspect_common import API, run_plan, venues_of  # noqa: E402

IN_CORPUS = "Kyoto"
OFF_CORPUS = "Zzyzxville"


def _row(label: str, rec: dict) -> tuple[str, list[str], bool | None]:
    res = rec.get("result") or {}
    status = str(rec.get("status"))
    venues = venues_of(rec)
    grounded = res.get("grounded")
    days = len(res.get("days") or [])
    print(
        f"  {label:<24} status={status:<10} venues={venues} "
        f"grounded={grounded} days={days} cost=${rec.get('cost_usd')}"
    )
    return status, venues, grounded


def main() -> int:
    print(f"\nSMOKE - two plans against {API}\n")

    ok_status, ok_venues, ok_grounded = _row(
        f"in-corpus {IN_CORPUS}", run_plan(IN_CORPUS, ["temples"], 1)
    )
    no_status, no_venues, no_grounded = _row(
        f"off-corpus {OFF_CORPUS}", run_plan(OFF_CORPUS, ["food"], 1)
    )

    print()
    failures = []
    if ok_status != "succeeded" or not ok_venues:
        failures.append(
            f"{IN_CORPUS} should have grounded and named a venue, got "
            f"status={ok_status} venues={ok_venues}"
        )
    if no_venues or no_grounded:
        failures.append(
            f"{OFF_CORPUS} is not in the corpus and must DECLINE, but came back "
            f"grounded={no_grounded} venues={no_venues} - text was produced with "
            "nothing behind it"
        )

    if failures:
        for f in failures:
            print(f"  FAIL  {f}")
        return 1

    print("  PASS  grounded where it can be, declined where it cannot.")
    print("        venues=[] on the second run is the proof no model was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
