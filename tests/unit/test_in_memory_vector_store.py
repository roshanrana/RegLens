from __future__ import annotations

import pytest

from app.domain.models import Chunk
from app.retrieval.embeddings import FakeEmbeddingConfig, FakeEmbeddingProvider
from app.retrieval.vector_store import InMemoryVectorStore


def _chunk(chunk_id: str, text: str, *, corpus_id: str = "finra-synthetic") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        section_id=f"sec_{chunk_id}",
        source_id="src_fixture",
        corpus_id=corpus_id,
        corpus_version="v1",
        citation_label=f"FINRA Rule {chunk_id[-4:]}",
        title=f"Rule {chunk_id[-4:]}",
        heading_path=["FINRA Synthetic Rulebook", f"Rule {chunk_id[-4:]}"],
        text=text,
        token_count=len(text.split()),
        chunk_index=0,
        section_chunk_count=1,
        source_checksum="checksum123",
    )


def test_upsert_and_search_returns_dense_candidates_in_rank_order() -> None:
    store = InMemoryVectorStore(
        FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=128))
    )
    policy_chunk = _chunk(
        "chk_1000",
        "FINRA Rule 1000(a) requires written supervisory policies and procedures.",
    )
    outage_chunk = _chunk(
        "chk_3000",
        "FINRA Rule 3000 requires business continuity plans for technology outages.",
    )
    store.upsert_chunks([outage_chunk, policy_chunk])

    results = store.search("What rule requires written policies?", top_k=2)

    assert [candidate.chunk.chunk_id for candidate in results] == ["chk_1000", "chk_3000"]
    assert [candidate.dense_rank for candidate in results] == [1, 2]
    assert [candidate.final_rank for candidate in results] == [1, 2]
    assert results[0].dense_score == pytest.approx(results[0].fusion_score)
    assert results[0].dense_score is not None
    assert results[0].dense_score > results[1].dense_score


def test_upsert_replaces_existing_chunk_embedding() -> None:
    store = InMemoryVectorStore(FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=64)))
    original = _chunk("chk_1000", "Written policies are required.")
    replacement = _chunk("chk_1000", "Annual review of policies is required.")

    store.upsert_chunk(original)
    store.upsert_chunk(replacement)

    assert store.count() == 1
    assert store.get("chk_1000") is not None
    assert store.get("chk_1000").chunk.text == replacement.text  # type: ignore[union-attr]
    assert store.search("annual review", top_k=1)[0].chunk.text == replacement.text


def test_search_filters_by_corpus_and_version() -> None:
    store = InMemoryVectorStore(FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=64)))
    matching = _chunk("chk_1000", "Written policies are required.", corpus_id="finra")
    other = _chunk("chk_2000", "Written policies are required.", corpus_id="fca")
    store.upsert_chunks([matching, other])

    results = store.search("written policies", corpus_id="finra")

    assert [candidate.chunk.chunk_id for candidate in results] == ["chk_1000"]


def test_search_accepts_precomputed_query_vector() -> None:
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=64))
    store = InMemoryVectorStore(provider)
    store.upsert_chunk(_chunk("chk_1000", "Annual compliance review is required."))

    query_vector = provider.embed_text("annual review")
    results = store.search(query_vector, top_k=1)

    assert results[0].chunk.chunk_id == "chk_1000"


def test_blank_query_returns_no_results() -> None:
    store = InMemoryVectorStore(FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)))
    store.upsert_chunk(_chunk("chk_1000", "Written policies are required."))

    assert store.search("   ") == []


def test_delete_and_clear_update_store_count() -> None:
    store = InMemoryVectorStore(FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)))
    store.upsert_chunks(
        [
            _chunk("chk_1000", "Written policies are required."),
            _chunk("chk_2000", "Records must be retained."),
        ]
    )

    assert store.delete_chunk("chk_1000") is True
    assert store.delete_chunk("missing") is False
    assert store.count() == 1

    store.clear()

    assert store.count() == 0


def test_invalid_top_k_and_dimension_mismatch_are_rejected() -> None:
    store = InMemoryVectorStore(FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)))
    with pytest.raises(ValueError, match="top_k"):
        store.search("written policies", top_k=0)
    with pytest.raises(ValueError, match="dimensions"):
        store.search([0.0, 1.0], top_k=1)
