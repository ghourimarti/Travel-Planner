"""Optional RAGAS-backed faithfulness judge. Install with `uv sync --extra ragas`.

RAGAS's signature context metrics (precision/recall) need real retrieval contexts,
which arrive in S6 — so here we use POIs-as-contexts to get a RAGAS *faithfulness*
number for S5. The gateway judge (``judge.py``) is the lighter default and also
covers relevancy. This path is the named-tool option (Decision 19); it becomes the
primary judge in S6 once retrieval contexts exist.
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
