"""Optional RAGAS-backed faithfulness judge. Install with `uv sync --extra ragas`.

RAGAS's context metrics (precision/recall) need retrieval contexts; here we pass the
provided POIs as contexts to get a RAGAS *faithfulness* number. The gateway judge
(``judge.py``) is the lighter default and also covers relevancy — this path exists for
cross-checking against a standard implementation.
"""

from __future__ import annotations

from typing import Any

from tp_agents.schemas import Itinerary, PlanRequest
from tp_core.control import record_spend
from tp_core.llm.models import cost_usd

from tp_eval.judge import JudgeResult


def usage_tokens(llm_output: dict[str, Any] | None) -> tuple[int, int]:
    """(prompt, completion) tokens from a LangChain chat result's ``llm_output``.

    ChatOpenAI reports them as ``{"token_usage": {...}}``. Anything else counts as
    zero rather than raising: a judge must never fail because its bookkeeping did.
    """
    usage = (llm_output or {}).get("token_usage") or {}
    try:
        return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0, 0


class RagasJudge:
    """Faithfulness via RAGAS (LLM-as-judge); relevancy is left to the gateway judge.

    RAGAS calls OpenAI DIRECTLY (LangChain), not through the gateway, so until
    2026-10-01 none of its spend reached a ledger. Every call it makes is now tallied,
    priced from tp_core.llm.models, added to today's spend total, and printed by the CLI.
    """

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        try:
            from langchain_core.callbacks import BaseCallbackHandler
            from langchain_openai import ChatOpenAI
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import Faithfulness
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("RAGAS not installed — run: uv sync --extra ragas") from exc
        self.model = model
        self.spent_usd = 0.0
        tokens = self._tokens = [0, 0]  # prompt, completion - over every RAGAS call

        class _Usage(BaseCallbackHandler):  # optional dep: see pyproject mypy overrides
            def on_llm_end(self, response: Any, **kwargs: Any) -> None:
                prompt, completion = usage_tokens(getattr(response, "llm_output", None))
                tokens[0] += prompt
                tokens[1] += completion

        llm = ChatOpenAI(model=model, callbacks=[_Usage()])
        self._faithfulness = Faithfulness(llm=LangchainLLMWrapper(llm))

    async def judge(
        self, request: PlanRequest, allowed_names: list[str], itinerary: Itinerary
    ) -> JudgeResult:
        from ragas.dataset_schema import SingleTurnSample

        sample = SingleTurnSample(
            user_input=(
                f"Plan a {request.days}-day trip to {request.city} "
                f"for: {', '.join(request.interests)}."
            ),
            response=itinerary.summary_markdown,
            retrieved_contexts=allowed_names or ["(no places were provided)"],
        )
        before = list(self._tokens)
        score = float(await self._faithfulness.single_turn_ascore(sample))
        spent = cost_usd(
            self.model, self._tokens[0] - before[0], self._tokens[1] - before[1]
        )
        self.spent_usd += spent
        await record_spend(spent)  # reaches today's total when REDIS_URL is the stack's
        return JudgeResult(
            faithful=score >= 0.99,
            violations=[],
            faithfulness_score=round(score, 3),
            relevance_score=0.0,  # RAGAS relevancy needs embeddings; gateway judge covers it
        )
