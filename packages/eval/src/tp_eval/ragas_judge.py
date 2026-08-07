"""Optional RAGAS-backed faithfulness judge. Install with `uv sync --extra ragas`.

RAGAS's context metrics (precision/recall) need retrieval contexts; here we pass the
provided POIs as contexts to get a RAGAS *faithfulness* number. The gateway judge
(``judge.py``) is the lighter default and also covers relevancy — this path exists for
cross-checking against a standard implementation.
"""

from __future__ import annotations

from tp_agents.schemas import Itinerary, PlanRequest

from tp_eval.judge import JudgeResult


class RagasJudge:
    """Faithfulness via RAGAS (LLM-as-judge); relevancy is left to the gateway judge."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        try:
            from langchain_openai import ChatOpenAI
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import Faithfulness
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("RAGAS not installed — run: uv sync --extra ragas") from exc
        self._faithfulness = Faithfulness(llm=LangchainLLMWrapper(ChatOpenAI(model=model)))

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
        score = float(await self._faithfulness.single_turn_ascore(sample))
        return JudgeResult(
            faithful=score >= 0.99,
            violations=[],
            faithfulness_score=round(score, 3),
            relevance_score=0.0,  # RAGAS relevancy needs embeddings; gateway judge covers it
        )
