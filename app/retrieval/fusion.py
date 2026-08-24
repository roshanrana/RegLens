"""Candidate fusion helpers for RegLens hybrid retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import Chunk, RetrievalCandidate

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    rank_lists: Sequence[Sequence[str]],
    *,
    k: int = DEFAULT_RRF_K,
) -> dict[str, float]:
    """Compute Reciprocal Rank Fusion scores for ranked chunk ID lists."""

    if k <= 0:
        raise ValueError("k must be greater than zero")

    scores: dict[str, float] = {}
    for ranked_ids in rank_lists:
        seen_in_list: set[str] = set()
        for zero_based_rank, chunk_id in enumerate(ranked_ids):
            if not chunk_id:
                raise ValueError("ranked IDs must be non-empty strings")
            if chunk_id in seen_in_list:
                continue
            seen_in_list.add(chunk_id)
            rank = zero_based_rank + 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


def merge_candidates(
    dense_candidates: Sequence[RetrievalCandidate],
    keyword_candidates: Sequence[RetrievalCandidate],
    *,
    k: int = DEFAULT_RRF_K,
    top_k: int | None = None,
) -> list[RetrievalCandidate]:
    """Merge dense and keyword candidates by chunk ID using RRF.

    Individual dense and keyword ranks/scores are preserved on the returned
    ``RetrievalCandidate`` objects. ``final_rank`` is assigned after fusion.
    """

    if k <= 0:
        raise ValueError("k must be greater than zero")
    if top_k is not None and top_k <= 0:
        raise ValueError("top_k must be greater than zero when provided")

    states: dict[str, _CandidateState] = {}
    _merge_one_source(states, dense_candidates, source="dense")
    _merge_one_source(states, keyword_candidates, source="keyword")

    fused: list[RetrievalCandidate] = []
    for state in states.values():
        fusion_score = _rrf_score(
            dense_rank=state.dense_rank,
            keyword_rank=state.keyword_rank,
            k=k,
        )
        fused.append(
            RetrievalCandidate(
                chunk=state.chunk,
                fusion_score=fusion_score,
                dense_rank=state.dense_rank,
                dense_score=state.dense_score,
                keyword_rank=state.keyword_rank,
                keyword_score=state.keyword_score,
            )
        )

    fused.sort(key=_candidate_sort_key)
    if top_k is not None:
        fused = fused[:top_k]

    return [
        RetrievalCandidate(
            chunk=candidate.chunk,
            fusion_score=candidate.fusion_score,
            dense_rank=candidate.dense_rank,
            dense_score=candidate.dense_score,
            keyword_rank=candidate.keyword_rank,
            keyword_score=candidate.keyword_score,
            rerank_score=candidate.rerank_score,
            final_rank=rank,
        )
        for rank, candidate in enumerate(fused, start=1)
    ]


@dataclass
class _CandidateState:
    chunk: Chunk
    dense_rank: int | None = None
    dense_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None


def _merge_one_source(
    states: dict[str, _CandidateState],
    candidates: Sequence[RetrievalCandidate],
    *,
    source: str,
) -> None:
    for index, candidate in enumerate(candidates, start=1):
        chunk_id = candidate.chunk.chunk_id
        state = states.setdefault(chunk_id, _CandidateState(chunk=candidate.chunk))
        rank = _candidate_rank(candidate, source=source, fallback=index)
        score = _candidate_score(candidate, source=source)

        if source == "dense":
            if state.dense_rank is None or rank < state.dense_rank:
                state.dense_rank = rank
                state.dense_score = score
        elif source == "keyword":
            if state.keyword_rank is None or rank < state.keyword_rank:
                state.keyword_rank = rank
                state.keyword_score = score
        else:
            raise ValueError(f"unsupported candidate source: {source}")


def _candidate_rank(candidate: RetrievalCandidate, *, source: str, fallback: int) -> int:
    if source == "dense":
        return candidate.dense_rank or fallback
    if source == "keyword":
        return candidate.keyword_rank or fallback
    raise ValueError(f"unsupported candidate source: {source}")


def _candidate_score(candidate: RetrievalCandidate, *, source: str) -> float:
    if source == "dense":
        return (
            candidate.dense_score
            if candidate.dense_score is not None
            else candidate.fusion_score
        )
    if source == "keyword":
        return (
            candidate.keyword_score
            if candidate.keyword_score is not None
            else candidate.fusion_score
        )
    raise ValueError(f"unsupported candidate source: {source}")


def _rrf_score(*, dense_rank: int | None, keyword_rank: int | None, k: int) -> float:
    score = 0.0
    if dense_rank is not None:
        score += 1.0 / (k + dense_rank)
    if keyword_rank is not None:
        score += 1.0 / (k + keyword_rank)
    return score


def _candidate_sort_key(candidate: RetrievalCandidate) -> tuple[float, int, str]:
    ranks = [
        rank
        for rank in (candidate.dense_rank, candidate.keyword_rank)
        if rank is not None
    ]
    best_rank = min(ranks) if ranks else 1_000_000
    return (-candidate.fusion_score, best_rank, candidate.chunk.chunk_id)
