from __future__ import annotations

import pytest

from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.rerank import FakeReranker, NoOpReranker


def test_fake_reranker_is_deterministic_and_sets_scores_and_ranks() -> None:
    relevant = _candidate(
        "chk_retention",
        "FINRA Rule 1030(b)",
        "Retention Period",
        "Records required by this rulebook must be retained for six years.",
        fusion_score=0.01,
        final_rank=2,
    )
    unrelated = _candidate(
        "chk_disclosure",
        "FINRA Rule 1010(c)",
        "Required Disclosure Table",
        "Retail communications with fee comparisons require disclosures.",
        fusion_score=0.99,
        final_rank=1,
    )
    reranker = FakeReranker()

    first = reranker.rerank(
        "How long must records be retained?",
        [unrelated, relevant],
    )
    second = reranker.rerank(
        "How long must records be retained?",
        [unrelated, relevant],
    )

    assert first == second
    assert [candidate.chunk.chunk_id for candidate in first] == [
        "chk_retention",
        "chk_disclosure",
    ]
    assert [candidate.final_rank for candidate in first] == [1, 2]
    assert first[0].rerank_score is not None
    assert first[1].rerank_score is not None
    assert first[0].rerank_score > first[1].rerank_score
    assert reranker.model_name == "fake-lexical-reranker-v1"


def test_fake_reranker_honors_top_k() -> None:
    candidates = [
        _candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies."),
        _candidate("chk_b", "FINRA Rule 1030(b)", "Retention Period", "Retained records."),
    ]

    reranked = FakeReranker().rerank(
        "How long must records be retained?",
        candidates,
        top_k=1,
    )

    assert len(reranked) == 1
    assert reranked[0].final_rank == 1


def test_fake_reranker_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        FakeReranker().rerank("records", [], top_k=0)


def test_noop_reranker_preserves_fused_order_with_zero_scores() -> None:
    first = _candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies.")
    second = _candidate(
        "chk_b",
        "FINRA Rule 1030(b)",
        "Retention Period",
        "Records must be retained.",
    )

    reranked = NoOpReranker().rerank("records retained", [first, second])

    assert [candidate.chunk.chunk_id for candidate in reranked] == ["chk_a", "chk_b"]
    assert [candidate.final_rank for candidate in reranked] == [1, 2]
    assert [candidate.rerank_score for candidate in reranked] == [0.0, 0.0]


def _candidate(
    chunk_id: str,
    citation_label: str,
    title: str,
    text: str,
    *,
    fusion_score: float = 0.03,
    final_rank: int | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=_chunk(chunk_id, citation_label, title, text),
        fusion_score=fusion_score,
        final_rank=final_rank,
    )


def _chunk(chunk_id: str, citation_label: str, title: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        section_id=f"sec_{chunk_id}",
        source_id="src_finra",
        corpus_id="finra-synthetic",
        corpus_version="2026-08-19",
        citation_label=citation_label,
        title=title,
        heading_path=["FINRA Synthetic Rulebook", title],
        text=text,
        token_count=len(text.split()),
        chunk_index=0,
        section_chunk_count=1,
        source_checksum="checksum",
    )
