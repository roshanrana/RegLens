"""In-memory vector store for fake-mode dense retrieval."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    Vector,
    cosine_similarity,
    is_zero_vector,
)


@dataclass(frozen=True)
class VectorRecord:
    chunk: Chunk
    embedding: Vector


class InMemoryVectorStore:
    """Simple deterministic vector store for tests and local development."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider()
        self._records: dict[str, VectorRecord] = {}

    def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()

    def get(self, chunk_id: str) -> VectorRecord | None:
        return self._records.get(chunk_id)

    def upsert_chunk(self, chunk: Chunk, embedding: Sequence[float] | None = None) -> None:
        resolved_embedding = (
            list(embedding)
            if embedding is not None
            else self.embedding_provider.embed_text(chunk.text)
        )
        self._validate_embedding(resolved_embedding)
        self._records[chunk.chunk_id] = VectorRecord(chunk=chunk, embedding=resolved_embedding)

    def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        for chunk in chunks:
            self.upsert_chunk(chunk)

    def delete_chunk(self, chunk_id: str) -> bool:
        return self._records.pop(chunk_id, None) is not None

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
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        query_embedding = self._query_embedding(query)
        if is_zero_vector(query_embedding):
            return []

        scored: list[tuple[float, Chunk]] = []
        for record in self._records.values():
            if corpus_id is not None and record.chunk.corpus_id != corpus_id:
                continue
            if corpus_version is not None and record.chunk.corpus_version != corpus_version:
                continue
            if source_id is not None and record.chunk.source_id != source_id:
                continue

            score = cosine_similarity(query_embedding, record.embedding)
            if min_score is not None and score < min_score:
                continue
            scored.append((score, record.chunk))

        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        candidates: list[RetrievalCandidate] = []
        for rank, (score, chunk) in enumerate(scored[:top_k], start=1):
            candidates.append(
                RetrievalCandidate(
                    chunk=chunk,
                    fusion_score=score,
                    dense_rank=rank,
                    dense_score=score,
                    final_rank=rank,
                )
            )
        return candidates

    def _query_embedding(self, query: str | Sequence[float]) -> Vector:
        if isinstance(query, str):
            return self.embedding_provider.embed_text(query)
        query_embedding = list(query)
        self._validate_embedding(query_embedding)
        return query_embedding

    def _validate_embedding(self, embedding: Sequence[float]) -> None:
        if len(embedding) != self.embedding_provider.dimensions:
            raise ValueError(
                "embedding dimensions do not match store dimensions: "
                f"expected {self.embedding_provider.dimensions}, got {len(embedding)}"
            )
