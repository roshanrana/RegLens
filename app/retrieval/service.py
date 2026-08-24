"""Fake-mode hybrid retrieval orchestration for RegLens."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Protocol

from app.domain.ids import make_evidence_id, make_query_id, normalize_text_for_id
from app.domain.models import Chunk, Evidence, RetrievalCandidate, RetrievalDiagnostics
from app.ingestion.chunking import Chunker, ChunkingConfig
from app.ingestion.loaders import MarkdownCorpusLoader
from app.retrieval.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.retrieval.fusion import DEFAULT_RRF_K, merge_candidates
from app.retrieval.keyword import BM25KeywordIndex, KeywordTokenizer, extract_citation_keys
from app.retrieval.rerank import FakeReranker, Reranker
from app.retrieval.vector_store import InMemoryVectorStore

_SNIPPET_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\([a-z0-9]+\))*")


class DenseVectorStore(Protocol):
    def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        ...

    def search(
        self,
        query: str | Sequence[float],
        *,
        top_k: int = 10,
        corpus_id: str | None = None,
        corpus_version: str | None = None,
        source_id: str | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalCandidate]:
        ...


@dataclass(frozen=True)
class RetrievalResult:
    query_id: str
    normalized_question: str
    evidence: list[Evidence]
    candidates: list[RetrievalCandidate]
    diagnostics: RetrievalDiagnostics


class RetrievalService:
    """Hybrid dense plus keyword retrieval over local chunks."""

    def __init__(
        self,
        chunks: list[Chunk],
        *,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: DenseVectorStore | None = None,
        keyword_index: BM25KeywordIndex | None = None,
        reranker: Reranker | None = None,
        mode: str = "mock",
        enable_reranking: bool = True,
        default_top_k: int = 8,
        max_evidence_tokens: int = 6000,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        if default_top_k <= 0:
            raise ValueError("default_top_k must be greater than zero")
        if max_evidence_tokens <= 0:
            raise ValueError("max_evidence_tokens must be greater than zero")
        if rrf_k <= 0:
            raise ValueError("rrf_k must be greater than zero")
        if not mode.strip():
            raise ValueError("mode must be a non-empty string")

        self.chunks = list(chunks)
        self.mode = mode
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider()
        self.vector_store = vector_store or InMemoryVectorStore(self.embedding_provider)
        if vector_store is None:
            self.vector_store.upsert_chunks(self.chunks)
        self.keyword_index = keyword_index or BM25KeywordIndex(self.chunks)
        self.reranker = reranker or FakeReranker()
        self.enable_reranking = enable_reranking
        self.default_top_k = default_top_k
        self.max_evidence_tokens = max_evidence_tokens
        self.rrf_k = rrf_k

    def retrieve(
        self,
        question: str,
        *,
        corpus_id: str | None = None,
        corpus_version: str | None = None,
        source_id: str | None = None,
        top_k: int | None = None,
        request_nonce: str | None = None,
    ) -> RetrievalResult:
        started_at = perf_counter()
        normalized_question = normalize_text_for_id(question)
        if not normalized_question:
            raise ValueError("question must be a non-empty string")

        resolved_top_k = top_k or self.default_top_k
        if resolved_top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        search_limit = max(resolved_top_k * 4, 10)
        query_id = make_query_id(
            question=normalized_question,
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            source_id=source_id,
            request_nonce=request_nonce,
        )

        dense_candidates = self.vector_store.search(
            normalized_question,
            top_k=search_limit,
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            source_id=source_id,
        )
        keyword_candidates = self.keyword_index.search(
            normalized_question,
            top_k=search_limit,
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            source_ids={source_id} if source_id is not None else None,
        )
        exact_citation_matches = self.keyword_index.find_exact_citation_matches(
            normalized_question,
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            source_ids={source_id} if source_id is not None else None,
        )
        candidate_limit = search_limit if self.enable_reranking else resolved_top_k
        fused_candidates = merge_candidates(
            dense_candidates,
            keyword_candidates,
            k=self.rrf_k,
            top_k=candidate_limit,
        )
        if self.enable_reranking:
            candidates = self.reranker.rerank(
                normalized_question,
                fused_candidates,
                top_k=resolved_top_k,
            )
            reranked_count = len(fused_candidates)
        else:
            candidates = fused_candidates
            reranked_count = 0

        query_route = _query_route(
            normalized_question,
            exact_citation_match_count=len(exact_citation_matches),
        )
        exact_pinned_count = 0
        if exact_citation_matches:
            candidates = _pin_exact_citation_matches(
                candidates,
                exact_citation_matches,
                top_k=max(resolved_top_k, len(exact_citation_matches)),
            )
            exact_pinned_count = len(
                {candidate.chunk.chunk_id for candidate in candidates}.intersection(
                    {chunk.chunk_id for chunk in exact_citation_matches}
                )
            )

        candidates, selected_evidence_tokens, evidence_truncated = _apply_evidence_token_budget(
            candidates,
            max_evidence_tokens=self.max_evidence_tokens,
            top_k=resolved_top_k,
        )

        evidence = self._evidence_from_candidates(
            query_id=query_id,
            question=normalized_question,
            candidates=candidates,
        )

        latency_ms = max(0, int(round((perf_counter() - started_at) * 1000)))
        filters: dict[str, str | None] = {
            "corpus_id": corpus_id,
            "corpus_version": corpus_version,
        }
        if source_id is not None:
            filters["source_id"] = source_id

        diagnostics = RetrievalDiagnostics(
            total_candidates=len(fused_candidates),
            returned_evidence=len(evidence),
            dense_count=len(dense_candidates),
            keyword_count=len(keyword_candidates),
            reranked_count=reranked_count,
            latency_ms=latency_ms,
            filters=filters,
            retrieval_config={
                "mode": self.mode,
                "top_k": resolved_top_k,
                "dense_limit": search_limit,
                "keyword_limit": search_limit,
                "rrf_k": self.rrf_k,
                "query_route": query_route,
                "exact_citation_matches": len(exact_citation_matches),
                "exact_citation_pinned": exact_pinned_count,
                "max_evidence_tokens": self.max_evidence_tokens,
                "selected_evidence_tokens": selected_evidence_tokens,
                "evidence_truncated": evidence_truncated,
                "embedding_model": self.embedding_provider.model_name,
                "keyword_index": self.keyword_index.__class__.__name__,
                "fusion": "reciprocal_rank_fusion",
                "reranker_enabled": self.enable_reranking,
                "reranker_model": self.reranker.model_name if self.enable_reranking else None,
                "reranker": (
                    self.reranker.diagnostics_config() if self.enable_reranking else None
                ),
                "rerank_candidate_limit": candidate_limit,
            },
        )
        return RetrievalResult(
            query_id=query_id,
            normalized_question=normalized_question,
            evidence=evidence,
            candidates=candidates,
            diagnostics=diagnostics,
        )

    def _evidence_from_candidates(
        self,
        *,
        query_id: str,
        question: str,
        candidates: list[RetrievalCandidate],
    ) -> list[Evidence]:
        query_terms = _snippet_terms(question)
        evidence: list[Evidence] = []
        for candidate in candidates:
            if candidate.final_rank is None:
                continue
            chunk = candidate.chunk
            evidence.append(
                Evidence(
                    evidence_id=make_evidence_id(
                        query_id=query_id,
                        chunk_id=chunk.chunk_id,
                        final_rank=candidate.final_rank,
                    ),
                    chunk_id=chunk.chunk_id,
                    citation_label=chunk.citation_label,
                    title=chunk.title,
                    snippet=_make_snippet(chunk.text, query_terms),
                    score=candidate.fusion_score,
                    url=chunk.url,
                    source_span=_chunk_span(chunk),
                )
            )
        return evidence


def build_fixture_retrieval_service(
    *,
    fixture_path: Path | None = None,
    chunking_config: ChunkingConfig | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    reranker: Reranker | None = None,
    default_top_k: int = 8,
    max_evidence_tokens: int = 6000,
) -> RetrievalService:
    resolved_path = fixture_path or (
        Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "synthetic_rulebook.md"
    )
    load_result = MarkdownCorpusLoader().load(resolved_path)
    if load_result.errors:
        raise ValueError(f"fixture ingestion failed: {load_result.errors}")

    chunks = Chunker(config=chunking_config).chunk_sections(
        load_result.sections,
        corpus_version=load_result.source.version,
        source_checksum=load_result.source.checksum,
    )
    return RetrievalService(
        chunks,
        embedding_provider=embedding_provider,
        reranker=reranker,
        mode="mock",
        default_top_k=default_top_k,
        max_evidence_tokens=max_evidence_tokens,
    )


def _query_route(question: str, *, exact_citation_match_count: int) -> str:
    if exact_citation_match_count > 0:
        return "exact_citation"
    if extract_citation_keys(question):
        return "citation_reference"
    return "conceptual"


def _pin_exact_citation_matches(
    candidates: list[RetrievalCandidate],
    exact_matches: list[Chunk],
    *,
    top_k: int,
) -> list[RetrievalCandidate]:
    candidates_by_chunk_id = {candidate.chunk.chunk_id: candidate for candidate in candidates}
    exact_chunk_ids = {chunk.chunk_id for chunk in exact_matches}
    exact_score = max((candidate.fusion_score for candidate in candidates), default=0.0) + 1.0

    pinned: list[RetrievalCandidate] = []
    for chunk in exact_matches:
        existing = candidates_by_chunk_id.get(chunk.chunk_id)
        if existing is None:
            pinned.append(
                RetrievalCandidate(
                    chunk=chunk,
                    fusion_score=exact_score,
                    keyword_score=exact_score,
                )
            )
            continue
        pinned.append(
            replace(
                existing,
                fusion_score=max(existing.fusion_score, exact_score),
                keyword_score=max(existing.keyword_score or 0.0, exact_score),
            )
        )

    remaining = [
        candidate for candidate in candidates if candidate.chunk.chunk_id not in exact_chunk_ids
    ]
    return _rank_candidates([*pinned, *remaining][:top_k])


def _apply_evidence_token_budget(
    candidates: list[RetrievalCandidate],
    *,
    max_evidence_tokens: int,
    top_k: int,
) -> tuple[list[RetrievalCandidate], int, bool]:
    selected: list[RetrievalCandidate] = []
    selected_tokens = 0

    for candidate in candidates:
        if len(selected) >= top_k:
            break
        candidate_tokens = candidate.chunk.token_count
        if selected_tokens + candidate_tokens > max_evidence_tokens:
            continue
        selected.append(candidate)
        selected_tokens += candidate_tokens

    evidence_truncated = len(selected) < min(len(candidates), top_k)
    return _rank_candidates(selected), selected_tokens, evidence_truncated


def _rank_candidates(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    return [
        replace(candidate, final_rank=rank)
        for rank, candidate in enumerate(candidates, start=1)
    ]


def _snippet_terms(text: str) -> list[str]:
    tokenizer = KeywordTokenizer()
    keyword_terms = [term.lower() for term in tokenizer.tokenize(text)]
    lexical_terms = [match.group(0).lower() for match in _SNIPPET_TOKEN_RE.finditer(text)]
    seen: set[str] = set()
    terms: list[str] = []
    for term in [*keyword_terms, *lexical_terms]:
        if term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _make_snippet(text: str, query_terms: list[str], *, max_chars: int = 360) -> str:
    normalized_text = text.strip()
    if len(normalized_text) <= max_chars:
        return normalized_text

    lowered = normalized_text.lower()
    positions = [lowered.find(term) for term in query_terms if lowered.find(term) >= 0]
    anchor = min(positions) if positions else 0
    start = max(0, anchor - max_chars // 3)
    end = min(len(normalized_text), start + max_chars)
    start = max(0, end - max_chars)
    snippet = normalized_text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(normalized_text):
        snippet += "..."
    return snippet


def _chunk_span(chunk: Chunk) -> dict[str, int] | None:
    if chunk.char_start is None or chunk.char_end is None:
        return None
    return {"start": chunk.char_start, "end": chunk.char_end}
