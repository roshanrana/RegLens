from __future__ import annotations

import pytest

from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.fusion import merge_candidates


def test_merge_candidates_combines_dense_and_keyword_matches_by_chunk_id() -> None:
    chunk_a = _chunk("chk_a")
    chunk_b = _chunk("chk_b")
    dense_candidates = [
        RetrievalCandidate(chunk=chunk_a, fusion_score=0.91, dense_rank=1, dense_score=0.91),
        RetrievalCandidate(chunk=chunk_b, fusion_score=0.80, dense_rank=2, dense_score=0.80),
    ]
    keyword_candidates = [
        RetrievalCandidate(chunk=chunk_b, fusion_score=12.0, keyword_rank=1, keyword_score=12.0),
        RetrievalCandidate(chunk=chunk_a, fusion_score=8.0, keyword_rank=2, keyword_score=8.0),
    ]

    merged = merge_candidates(dense_candidates, keyword_candidates, k=60)

    assert [candidate.chunk.chunk_id for candidate in merged] == ["chk_a", "chk_b"]
    assert merged[0].final_rank == 1
    assert merged[0].dense_rank == 1
    assert merged[0].keyword_rank == 2
    assert merged[0].dense_score == pytest.approx(0.91)
    assert merged[0].keyword_score == pytest.approx(8.0)
    assert merged[0].fusion_score == pytest.approx(1 / 61 + 1 / 62)
    assert merged[1].fusion_score == pytest.approx(1 / 62 + 1 / 61)


def test_merge_candidates_includes_single_source_candidates_and_applies_top_k() -> None:
    chunk_a = _chunk("chk_a")
    chunk_b = _chunk("chk_b")
    chunk_c = _chunk("chk_c")

    merged = merge_candidates(
        [RetrievalCandidate(chunk=chunk_a, fusion_score=0.9, dense_rank=1, dense_score=0.9)],
        [
            RetrievalCandidate(chunk=chunk_b, fusion_score=8.0, keyword_rank=1, keyword_score=8.0),
            RetrievalCandidate(chunk=chunk_c, fusion_score=7.0, keyword_rank=2, keyword_score=7.0),
        ],
        top_k=2,
    )

    assert len(merged) == 2
    assert [candidate.final_rank for candidate in merged] == [1, 2]
    assert {candidate.chunk.chunk_id for candidate in merged} == {"chk_a", "chk_b"}
    assert merged[0].chunk.chunk_id == "chk_a"


def test_merge_candidates_uses_fallback_ranks_and_scores() -> None:
    chunk_a = _chunk("chk_a")

    merged = merge_candidates(
        [RetrievalCandidate(chunk=chunk_a, fusion_score=0.7)],
        [],
        k=10,
    )

    assert merged[0].dense_rank == 1
    assert merged[0].dense_score == pytest.approx(0.7)
    assert merged[0].fusion_score == pytest.approx(1 / 11)


def test_merge_candidates_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="k"):
        merge_candidates([], [], k=0)

    with pytest.raises(ValueError, match="top_k"):
        merge_candidates([], [], top_k=0)


def _chunk(chunk_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        section_id=f"sec_{chunk_id}",
        source_id="src_finra",
        corpus_id="finra",
        corpus_version="v1",
        citation_label=f"FINRA Rule {chunk_id[-1]}",
        title=f"Title {chunk_id}",
        heading_path=[f"Title {chunk_id}"],
        text=f"Text for {chunk_id}",
        token_count=3,
        chunk_index=0,
        section_chunk_count=1,
        source_checksum="checksum",
    )
