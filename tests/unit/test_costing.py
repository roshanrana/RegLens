from app.core.costing import estimate_openai_query_cost


def test_cost_estimate_is_zero_for_fake_models() -> None:
    estimate = estimate_openai_query_cost(
        question="How long?",
        evidence_snippets=["Records are retained for six years."],
        answer_text="Six years. [E1]",
        generation_model="fake-cited-llm-v1",
        embedding_model="fake-hashed-lexical-v1",
    )

    assert estimate.estimated_cost_usd == 0.0
    assert estimate.payload()["method"] == "approx_chars_div_4"


def test_cost_estimate_uses_configured_openai_demo_prices() -> None:
    estimate = estimate_openai_query_cost(
        question="How long must records be retained?",
        evidence_snippets=["Records required by this rulebook must be retained for six years."],
        answer_text="Records must be retained for six years. [E1]",
        generation_model="gpt-5.4-nano",
        embedding_model="text-embedding-3-small",
    )

    assert estimate.estimated_cost_usd > 0
    assert estimate.input_tokens > 0
    assert estimate.output_tokens > 0
    assert estimate.embedding_tokens > 0
