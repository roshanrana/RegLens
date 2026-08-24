from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.retrieval.embeddings import cosine_similarity
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
        self.deleted_point_count = 0

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
        collection = self.collections.get(collection_name, {})
        for point_id in points_selector.points:
            if point_id in collection:
                self.deleted_point_count += 1
            collection.pop(point_id, None)


def test_local_mode_without_qdrant_dependency_starts_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None) -> Any:
        if name.startswith("qdrant_client"):
            raise ImportError("qdrant-client missing")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    app = create_app(Settings(app_env="test", rag_mode="local", default_top_k=4))
    client = TestClient(app)

    ready = client.get("/ready")
    retrieve = client.post("/retrieve", json={"question": "How long must records be retained?"})

    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["status"] == "degraded"
    assert ready_body["checks"]["qdrant"]["status"] == "unavailable"
    assert retrieve.status_code == 503
    assert retrieve.json()["error"]["code"] == "dependency_unavailable"


def test_local_mode_with_injected_qdrant_client_retrieves_fixture_evidence() -> None:
    qdrant_client = FakeQdrantClient()
    app = create_app(
        Settings(app_env="test", rag_mode="local", default_top_k=4),
        qdrant_client=qdrant_client,
        qdrant_models=FakeModels,
    )
    client = TestClient(app)

    ready = client.get("/ready")
    response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "top_k": 2,
        },
    )

    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["qdrant"]["status"] == "available"
    assert qdrant_client.count(collection_name="regulatory_chunks", exact=True).count == 11
    assert isinstance(app.state.retrieval_service.vector_store, QdrantVectorStore)
    assert response.status_code == 200
    assert response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"


def test_local_mode_document_lifecycle_preserves_qdrant_vector_store(
    fixture_rulebook_path,
) -> None:
    qdrant_client = FakeQdrantClient()
    app = create_app(
        Settings(app_env="test", rag_mode="local", default_top_k=4),
        qdrant_client=qdrant_client,
        qdrant_models=FakeModels,
    )
    client = TestClient(app)
    ingest_response = client.post(
        "/documents",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": "local-qdrant-finra",
            "corpus_name": "Local Qdrant FINRA Rulebook",
            "version": "2026-local-qdrant",
        },
    )

    assert ingest_response.status_code == 200
    assert isinstance(app.state.retrieval_service.vector_store, QdrantVectorStore)
    assert qdrant_client.count(collection_name="regulatory_chunks", exact=True).count == 22

    retrieve_response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "local-qdrant-finra",
            "corpus_version": "2026-local-qdrant",
            "top_k": 1,
        },
    )

    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"

    source_id = ingest_response.json()["source"]["source_id"]
    delete_response = client.delete(f"/documents/{source_id}")

    assert delete_response.status_code == 200
    assert isinstance(app.state.retrieval_service.vector_store, QdrantVectorStore)
    assert qdrant_client.deleted_point_count == 11

    deleted_retrieve = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "local-qdrant-finra",
            "corpus_version": "2026-local-qdrant",
            "top_k": 1,
        },
    )

    assert deleted_retrieve.status_code == 200
    assert deleted_retrieve.json()["evidence"] == []


def _matches_filter(payload: dict[str, Any], query_filter: FakeModels.Filter | None) -> bool:
    if query_filter is None:
        return True
    return all(
        payload.get(condition.key) == condition.match.value
        for condition in query_filter.must
    )
