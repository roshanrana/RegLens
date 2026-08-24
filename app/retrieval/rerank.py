"""Dependency-free reranking primitives for RegLens fake mode."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.keyword import KeywordTokenizer, extract_citation_keys


class Reranker(Protocol):
    """Swappable interface for candidate reranking."""

    model_name: str

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalCandidate]:
        """Return reranked candidates with ``rerank_score`` and ``final_rank`` set."""

    def diagnostics_config(self) -> dict[str, object]:
        """Return serializable configuration for retrieval diagnostics."""


@dataclass(frozen=True)
class FakeRerankerConfig:
    """Weights for the deterministic lexical reranker."""

    body_weight: float = 1.0
    title_weight: float = 0.45
    heading_weight: float = 0.35
    citation_weight: float = 0.8
    citation_exact_match_boost: float = 3.0
    bigram_weight: float = 0.55

    def __post_init__(self) -> None:
        for field_name, value in (
            ("body_weight", self.body_weight),
            ("title_weight", self.title_weight),
            ("heading_weight", self.heading_weight),
            ("citation_weight", self.citation_weight),
            ("citation_exact_match_boost", self.citation_exact_match_boost),
            ("bigram_weight", self.bigram_weight),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")


class FakeReranker:
    """Fast lexical reranker used for tests and local fake-mode development.

    The score is computed only from the query and candidate chunk fields. It is
    intentionally simple, deterministic, and dependency-free so tests never need
    model downloads or network access.
    """

    model_name = "fake-lexical-reranker-v1"

    def __init__(
        self,
        *,
        tokenizer: KeywordTokenizer | None = None,
        config: FakeRerankerConfig | None = None,
    ) -> None:
        self.tokenizer = tokenizer or KeywordTokenizer()
        self.config = config or FakeRerankerConfig()

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalCandidate]:
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than zero when provided")

        features = self._query_features(query)
        scored = [
            (self.score(query_features=features, chunk=candidate.chunk), index, candidate)
            for index, candidate in enumerate(candidates)
        ]
        scored.sort(key=_rerank_sort_key)

        if top_k is not None:
            scored = scored[:top_k]

        return [
            replace(candidate, rerank_score=score, final_rank=rank)
            for rank, (score, _index, candidate) in enumerate(scored, start=1)
        ]

    def score(self, *, query_features: _QueryFeatures, chunk: Chunk) -> float:
        """Score one chunk against precomputed query features."""

        if not query_features.tokens and not query_features.citation_keys:
            return 0.0

        body_tokens = frozenset(self.tokenizer.tokenize(chunk.text))
        title_tokens = frozenset(self.tokenizer.tokenize(chunk.title))
        heading_tokens = frozenset(self.tokenizer.tokenize(" ".join(chunk.heading_path)))
        citation_tokens = frozenset(self.tokenizer.tokenize(chunk.citation_label))

        denominator = max(1, len(query_features.token_set))
        body_overlap = _overlap_ratio(query_features.token_set, body_tokens, denominator)
        title_overlap = _overlap_ratio(query_features.token_set, title_tokens, denominator)
        heading_overlap = _overlap_ratio(query_features.token_set, heading_tokens, denominator)
        citation_overlap = _overlap_ratio(query_features.token_set, citation_tokens, denominator)

        score = (
            body_overlap * self.config.body_weight
            + title_overlap * self.config.title_weight
            + heading_overlap * self.config.heading_weight
            + citation_overlap * self.config.citation_weight
        )

        chunk_citation_keys = extract_citation_keys(chunk.citation_label)
        if query_features.citation_keys.intersection(chunk_citation_keys):
            score += self.config.citation_exact_match_boost

        body_bigrams = frozenset(_bigrams(tuple(self.tokenizer.tokenize(chunk.text))))
        if query_features.bigrams and body_bigrams:
            score += (
                len(query_features.bigrams.intersection(body_bigrams))
                / len(query_features.bigrams)
                * self.config.bigram_weight
            )

        return round(score, 8)

    def diagnostics_config(self) -> dict[str, object]:
        return {
            "strategy": "lexical_overlap",
            "body_weight": self.config.body_weight,
            "title_weight": self.config.title_weight,
            "heading_weight": self.config.heading_weight,
            "citation_weight": self.config.citation_weight,
            "citation_exact_match_boost": self.config.citation_exact_match_boost,
            "bigram_weight": self.config.bigram_weight,
        }

    def _query_features(self, query: str) -> _QueryFeatures:
        tokens = tuple(_unique_preserving_order(self.tokenizer.tokenize(query)))
        return _QueryFeatures(
            tokens=tokens,
            token_set=frozenset(tokens),
            citation_keys=frozenset(extract_citation_keys(query)),
            bigrams=frozenset(_bigrams(tokens)),
        )


class NoOpReranker:
    """Reranker implementation for explicitly preserving fused order."""

    model_name = "noop-reranker-v1"

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalCandidate]:
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than zero when provided")

        selected = list(candidates[:top_k])
        return [
            replace(candidate, rerank_score=0.0, final_rank=rank)
            for rank, candidate in enumerate(selected, start=1)
        ]

    def diagnostics_config(self) -> dict[str, object]:
        return {"strategy": "preserve_fused_order"}


@dataclass(frozen=True)
class _QueryFeatures:
    tokens: tuple[str, ...]
    token_set: frozenset[str]
    citation_keys: frozenset[str]
    bigrams: frozenset[tuple[str, str]]


def _rerank_sort_key(item: tuple[float, int, RetrievalCandidate]) -> tuple[float, int, float, str]:
    score, original_index, candidate = item
    prior_rank = candidate.final_rank or original_index + 1
    return (-score, prior_rank, -candidate.fusion_score, candidate.chunk.chunk_id)


def _overlap_ratio(
    query_tokens: frozenset[str],
    field_tokens: frozenset[str],
    denominator: int,
) -> float:
    if not query_tokens or not field_tokens:
        return 0.0
    return len(query_tokens.intersection(field_tokens)) / denominator


def _bigrams(tokens: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(tokens[index], tokens[index + 1]) for index in range(len(tokens) - 1)]


def _unique_preserving_order(tokens: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return unique
