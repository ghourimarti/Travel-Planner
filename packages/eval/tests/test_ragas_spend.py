"""The RAGAS judge's spend bookkeeping (the judge itself needs `uv sync --extra ragas`).

RAGAS calls OpenAI directly, outside the gateway, so its spend reached no ledger until it
started counting the tokens of every call it makes. What can be tested without the
optional dependency is the part that turns a LangChain result into billable tokens.
"""

from __future__ import annotations

from tp_core.llm.models import cost_usd
from tp_eval.ragas_judge import usage_tokens


def test_reads_chatopenai_token_usage() -> None:
    llm_output = {"token_usage": {"prompt_tokens": 812, "completion_tokens": 64}}
    assert usage_tokens(llm_output) == (812, 64)
    # ...which prices like any other gpt-4o-mini call
    assert cost_usd("gpt-4o-mini", 812, 64) > 0


def test_missing_or_odd_usage_counts_as_zero_never_raises() -> None:
    """A judge must never fail because its bookkeeping did."""
    assert usage_tokens(None) == (0, 0)
    assert usage_tokens({}) == (0, 0)
    assert usage_tokens({"token_usage": None}) == (0, 0)
    assert usage_tokens({"token_usage": {"prompt_tokens": "n/a"}}) == (0, 0)
    assert usage_tokens({"token_usage": "not-a-dict"}) == (0, 0)
