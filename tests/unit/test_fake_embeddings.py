from __future__ import annotations

import pytest

from app.retrieval.embeddings import (
    FakeEmbeddingConfig,
    FakeEmbeddingProvider,
    cosine_similarity,
    tokenize,
)


def test_fake_embeddings_are_deterministic_and_normalized() -> None:
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=64))

    first = provider.embed_text("Members must maintain written supervisory policies.")
    second = provider.embed_text("Members must maintain written supervisory policies.")

    assert first == second
    assert len(first) == 64
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_related_regulatory_text_is_closer_than_unrelated_text() -> None:
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=128))
    query = provider.embed_text("written supervisory policies")
    related = provider.embed_text(
        "The member maintains written policies and supervision procedures."
    )
    unrelated = provider.embed_text(
        "Backup systems preserve customer notifications during outages."
    )

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_numeric_rule_citations_have_lexical_signal() -> None:
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=128))
    query = provider.embed_text("FINRA Rule 1000 annual review")
    matching_rule = provider.embed_text("FINRA Rule 1000(b) requires an annual review.")
    other_rule = provider.embed_text("FINRA Rule 2000 covers retention of communications.")

    assert cosine_similarity(query, matching_rule) > cosine_similarity(query, other_rule)


def test_empty_text_returns_zero_vector() -> None:
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=16))

    assert provider.embed_text(" \n\t ") == [0.0] * 16


def test_invalid_dimensions_are_rejected() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        FakeEmbeddingConfig(dimensions=0)


def test_tokenize_splits_citations_predictably() -> None:
    assert tokenize("FINRA Rule 1000(a): Written Policies") == [
        "finra",
        "rule",
        "1000",
        "a",
        "written",
        "policies",
    ]
