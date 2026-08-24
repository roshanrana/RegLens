"""Deterministic live-provider cost estimates for audits and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    estimated_cost_usd: float
    input_tokens: int
    output_tokens: int
    embedding_tokens: int
    generation_model: str | None
    embedding_model: str | None

    def payload(self) -> dict[str, object]:
        return {
            "estimated_cost_usd": self.estimated_cost_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "embedding_tokens": self.embedding_tokens,
            "generation_model": self.generation_model,
            "embedding_model": self.embedding_model,
            "method": "approx_chars_div_4",
        }


GENERATION_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-5.4-nano": (0.20, 1.25),
}
EMBEDDING_PRICES_PER_MTOK: dict[str, float] = {
    "text-embedding-3-small": 0.02,
}


def estimate_openai_query_cost(
    *,
    question: str,
    evidence_snippets: list[str],
    answer_text: str,
    generation_model: str | None,
    embedding_model: str | None,
) -> CostEstimate:
    """Estimate OpenAI cost using conservative character-based token counts."""

    if generation_model not in GENERATION_PRICES_PER_MTOK:
        return CostEstimate(
            estimated_cost_usd=0.0,
            input_tokens=0,
            output_tokens=0,
            embedding_tokens=0,
            generation_model=generation_model,
            embedding_model=embedding_model,
        )

    input_tokens = _approx_tokens("\n\n".join([question, *evidence_snippets]))
    output_tokens = _approx_tokens(answer_text)
    embedding_tokens = (
        _approx_tokens(question)
        if embedding_model in EMBEDDING_PRICES_PER_MTOK
        else 0
    )
    input_price, output_price = GENERATION_PRICES_PER_MTOK[generation_model]
    embedding_price = (
        EMBEDDING_PRICES_PER_MTOK[embedding_model]
        if embedding_model in EMBEDDING_PRICES_PER_MTOK
        else 0.0
    )
    cost = (
        input_tokens * input_price
        + output_tokens * output_price
        + embedding_tokens * embedding_price
    ) / 1_000_000
    return CostEstimate(
        estimated_cost_usd=round(cost, 8),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        embedding_tokens=embedding_tokens,
        generation_model=generation_model,
        embedding_model=embedding_model,
    )


def _approx_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)
