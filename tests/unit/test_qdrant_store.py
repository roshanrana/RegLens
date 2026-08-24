from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import pytest

from app.core.errors import DependencyUnavailableError
from app.domain.models import Chunk
from app.retrieval.embeddings import (
    FakeEmbeddingConfig,
    FakeEmbeddingProvider,
    cosine_similarity,
)
from app.retrieval.qdrant_store import QdrantVectorStore


class FakeModels:
    class Distance:
        COSINE = "Cosine"

    @dataclass(frozen=True)
    class VectorParams:
        size: int
        distance: str

    @dataclass(frozen=True)
    class PointStruct:
        id: str
        vector: list[float]
        payload: dict[str, Any]

    @dataclass(frozen=True)
    class MatchValue:
        value: str

    @dataclass(frozen=True)
    class FieldCondition:
        key: str
        match: FakeModels.MatchValue

    @dataclass(frozen=True)
    class Filter:
        must: list[FakeModels.FieldCondition]

    @dataclass(frozen=True)
    class PointIdsList:
        points: list[str]


@dataclass(frozen=True)
class FakeScoredPoint:
    id: str
    payload: dict[str, Any]
    score: float


@dataclass(frozen=True)
class FakeQueryResponse:
    points: list[FakeScoredPoint]


@dataclass(frozen=True)
class FakeCountResult:
    count: int


class FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, FakeModels.PointStruct]] = {}
        self.created_collections: list[tuple[str, FakeModels.VectorParams]] = []
        self.last_query_filter: FakeModels.Filter | None = None
        self.last_deleted_selector: FakeModels.PointIdsList | None = None

    def collection_exists(self, *, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(
        self,
        *,
        collection_name: str,
        vectors_config: FakeModels.VectorParams,
    ) -> None:
        self.collections[collection_name] = {}
        self.created_collections.append((collection_name, vectors_config))

    def upsert(
        self,
        *,
        collection_name: str,
        points: list[FakeModels.PointStruct],
        wait: bool,
    ) -> None:
        assert wait is True
        collection = self.collections.setdefault(collection_name, {})
        for point in points:
            collection[point.id] = point

    def query_points(
        self,
        *,
        collection_name: str,
        query: list[float],
        query_filter: FakeModels.Filter | None,
        limit: int,
        with_payload: bool,
        score_threshold: float | None,
    ) -> FakeQueryResponse:
        assert with_payload is True
        self.last_query_filter = query_filter
        scored: list[FakeScoredPoint] = []
        for point in self.collections[collection_name].values():
            if not _matches_filter(point.payload, query_filter):
                continue
            score = cosine_similarity(query, point.vector)
            if score_threshold is not None and score < score_threshold:
                continue
            scored.append(FakeScoredPoint(id=point.id, payload=point.payload, score=score))
        scored.sort(key=lambda point: (-point.score, point.id))
        return FakeQueryResponse(points=scored[:limit])

    def count(self, *, collection_name: str, exact: bool) -> FakeCountResult:
        assert exact is True
        return FakeCountResult(count=len(self.collections.get(collection_name, {})))

    def retrieve(
        self,
        *,
        collection_name: str,
        ids: list[str],
        with_payload: bool,
        with_vectors: bool,
    ) -> list[FakeModels.PointStruct]:
        assert with_payload is False
        assert with_vectors is False
        collection = self.collections.get(collection_name, {})
        return [collection[point_id] for point_id in ids if point_id in collection]

    def delete(
        self,
        *,
        collection_name: str,
        points_selector: FakeModels.PointIdsList,
        wait: bool,
    ) -> None:
        assert wait is True
        self.last_deleted_selector = points_selector
        collection = self.collections.get(collection_name, {})
        for point_id in points_selector.points:
            collection.pop(point_id, None)


def test_construct_with_injected_client_creates_collection_once() -> None:
    client = FakeQdrantClient()
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32))

    QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        models=FakeModels,
        embedding_provider=provider,
    )
    QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        models=FakeModels,
        embedding_provider=provider,
    )

    assert len(client.created_collections) == 1
    collection_name, vector_params = client.created_collections[0]
    assert collection_name == "reglens_chunks"
    assert vector_params.size == 32
    assert vector_params.distance == "Cosine"


def test_injected_client_does_not_require_model_namespace() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        embedding_provider=FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)),
    )

    store.upsert_chunk(_chunk("chk_1000", "Written supervisory policies are required."))

    assert store.count() == 1
    assert store.search("written policies", top_k=1)[0].chunk.chunk_id == "chk_1000"


def test_upsert_and_search_reconstructs_chunks_with_dense_ranks_and_filters() -> None:
    client = FakeQdrantClient()
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=64))
    store = QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        models=FakeModels,
        embedding_provider=provider,
    )
    policy_chunk = _chunk(
        "chk_1000",
        "FINRA Rule 1000(a) requires written supervisory policies and procedures.",
        corpus_id="finra",
        metadata={"rule_type": "supervision"},
    )
    outage_chunk = _chunk(
        "chk_3000",
        "FINRA Rule 3000 requires business continuity plans for technology outages.",
        corpus_id="finra",
    )
    fca_chunk = _chunk(
        "chk_fca",
        "FCA firms must maintain written compliance policies.",
        corpus_id="fca",
    )

    store.upsert_chunks([outage_chunk, fca_chunk, policy_chunk])

    results = store.search("What rule requires written policies?", top_k=3, corpus_id="finra")

    assert [candidate.chunk.chunk_id for candidate in results] == ["chk_1000", "chk_3000"]
    assert [candidate.dense_rank for candidate in results] == [1, 2]
    assert [candidate.final_rank for candidate in results] == [1, 2]
    assert results[0].dense_score == pytest.approx(results[0].fusion_score)
    assert results[0].chunk.metadata == {"rule_type": "supervision"}
    assert results[0].chunk.url == "https://example.test/chk_1000"
    assert results[0].chunk.page_number == 7
    assert client.last_query_filter is not None
    assert [condition.key for condition in client.last_query_filter.must] == ["corpus_id"]


def test_search_accepts_precomputed_query_vector_and_source_filter() -> None:
    client = FakeQdrantClient()
    provider = FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=64))
    store = QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        models=FakeModels,
        embedding_provider=provider,
    )
    matching = _chunk(
        "chk_1000",
        "Annual compliance review is required.",
        source_id="src_finra",
    )
    other = _chunk(
        "chk_2000",
        "Annual compliance review is required.",
        source_id="src_archive",
    )
    store.upsert_chunks([matching, other])

    query_vector = provider.embed_text("annual review")
    results = store.search(query_vector, top_k=2, source_id="src_finra")

    assert [candidate.chunk.chunk_id for candidate in results] == ["chk_1000"]


def test_upsert_replaces_count_and_delete() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        models=FakeModels,
        embedding_provider=FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)),
    )
    original = _chunk("chk_1000", "Written policies are required.")
    replacement = _chunk("chk_1000", "Annual policy review is required.")

    store.upsert_chunk(original)
    store.upsert_chunk(replacement)

    assert store.count() == 1
    assert store.search("annual review", top_k=1)[0].chunk.text == replacement.text
    assert store.delete_chunk("chk_1000") is True
    assert store.delete_chunk("chk_1000") is False
    assert store.count() == 0
    assert client.last_deleted_selector is not None


def test_invalid_top_k_and_dimension_mismatch_are_rejected() -> None:
    store = QdrantVectorStore(
        collection_name="reglens_chunks",
        client=FakeQdrantClient(),
        models=FakeModels,
        embedding_provider=FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)),
    )

    with pytest.raises(ValueError, match="top_k"):
        store.search("written policies", top_k=0)
    with pytest.raises(ValueError, match="dimensions"):
        store.search([0.0, 1.0], top_k=1)


def test_blank_query_returns_no_results_without_calling_qdrant() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(
        collection_name="reglens_chunks",
        client=client,
        models=FakeModels,
        embedding_provider=FakeEmbeddingProvider(FakeEmbeddingConfig(dimensions=32)),
    )
    store.upsert_chunk(_chunk("chk_1000", "Written policies are required."))

    assert store.search("   ") == []
    assert client.last_query_filter is None


def test_missing_dependency_raises_clear_error_when_real_client_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None) -> Any:
        if name.startswith("qdrant_client"):
            raise ImportError("qdrant-client missing")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(DependencyUnavailableError, match="qdrant-client"):
        QdrantVectorStore(collection_name="reglens_chunks")


def _matches_filter(payload: dict[str, Any], query_filter: FakeModels.Filter | None) -> bool:
    if query_filter is None:
        return True
    return all(
        payload.get(condition.key) == condition.match.value
        for condition in query_filter.must
    )


def _chunk(
    chunk_id: str,
    text: str,
    *,
    corpus_id: str = "finra-synthetic",
    corpus_version: str = "v1",
    source_id: str = "src_fixture",
    metadata: dict[str, Any] | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        section_id=f"sec_{chunk_id}",
        source_id=source_id,
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        citation_label=f"FINRA Rule {chunk_id[-4:]}",
        title=f"Rule {chunk_id[-4:]}",
        heading_path=["FINRA Synthetic Rulebook", f"Rule {chunk_id[-4:]}"],
        text=text,
        token_count=len(text.split()),
        chunk_index=0,
        section_chunk_count=1,
        source_checksum="checksum123",
        char_start=10,
        char_end=10 + len(text),
        page_number=7,
        url=f"https://example.test/{chunk_id}",
        metadata=metadata or {},
    )
