"""Qdrant-backed vector store for dense retrieval.

The adapter mirrors ``InMemoryVectorStore`` while keeping Qdrant optional. Tests
can inject a stub client and model namespace, so importing this module never
requires a running Qdrant service or the ``qdrant-client`` package.
"""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.errors import DependencyUnavailableError
from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    Vector,
    is_zero_vector,
)

_POINT_ID_NAMESPACE = uuid.UUID("8b4f35c4-2e7f-4d78-91d0-5f94e6f88b66")
_PAYLOAD_SCHEMA = "reglens_chunk_v1"


@dataclass(frozen=True)
class QdrantVectorStoreConfig:
    collection_name: str
    url: str = "http://localhost:6333"
    api_key: str | None = None
    distance: str = "Cosine"
    create_collection: bool = True
    prefer_grpc: bool = False
    timeout: float | None = None

    def __post_init__(self) -> None:
        if not self.collection_name.strip():
            raise ValueError("collection_name must be a non-empty string")
        if not self.url.strip():
            raise ValueError("url must be a non-empty string")
        if not self.distance.strip():
            raise ValueError("distance must be a non-empty string")


class QdrantVectorStore:
    """Dense vector store backed by Qdrant.

    Construct with an injected client for tests or local fakes. If no client is
    supplied, ``qdrant-client`` is imported lazily and a real client is created.
    """

    def __init__(
        self,
        *,
        collection_name: str,
        embedding_provider: EmbeddingProvider | None = None,
        client: Any | None = None,
        models: Any | None = None,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        distance: str = "Cosine",
        create_collection: bool = True,
        prefer_grpc: bool = False,
        timeout: float | None = None,
    ) -> None:
        self.config = QdrantVectorStoreConfig(
            collection_name=collection_name,
            url=url,
            api_key=api_key,
            distance=distance,
            create_collection=create_collection,
            prefer_grpc=prefer_grpc,
            timeout=timeout,
        )
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider()
        self.collection_name = self.config.collection_name
        self.dimensions = self.embedding_provider.dimensions

        if client is None:
            qdrant_client_class, qdrant_models = _load_qdrant_dependencies()
            self.client = qdrant_client_class(
                url=self.config.url,
                api_key=self.config.api_key,
                prefer_grpc=self.config.prefer_grpc,
                timeout=self.config.timeout,
            )
            self._models = qdrant_models
        else:
            self.client = client
            self._models = models or _FallbackModels

        if self.config.create_collection:
            self._ensure_collection()

    def count(self) -> int:
        result = self.client.count(collection_name=self.collection_name, exact=True)
        if isinstance(result, int):
            return result
        return int(result.count)

    def upsert_chunk(self, chunk: Chunk, embedding: Sequence[float] | None = None) -> None:
        resolved_embedding = (
            list(embedding)
            if embedding is not None
            else self.embedding_provider.embed_text(chunk.text)
        )
        self._validate_embedding(resolved_embedding)
        point = self._models.PointStruct(
            id=_point_id(chunk.chunk_id),
            vector=resolved_embedding,
            payload=_chunk_to_payload(chunk),
        )
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point],
            wait=True,
        )

    def upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        points = []
        for chunk in chunks:
            embedding = self.embedding_provider.embed_text(chunk.text)
            self._validate_embedding(embedding)
            points.append(
                self._models.PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector=embedding,
                    payload=_chunk_to_payload(chunk),
                )
            )
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

    def delete_chunk(self, chunk_id: str) -> bool:
        point_id = _point_id(chunk_id)
        existed = self._point_exists(point_id)
        if existed is False:
            return False

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=self._models.PointIdsList(points=[point_id]),
            wait=True,
        )
        return True

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

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=self._build_filter(
                corpus_id=corpus_id,
                corpus_version=corpus_version,
                source_id=source_id,
            ),
            limit=top_k,
            with_payload=True,
            score_threshold=min_score,
        )
        points = _response_points(response)

        candidates: list[RetrievalCandidate] = []
        for point in points:
            score = _point_score(point)
            if min_score is not None and score < min_score:
                continue
            rank = len(candidates) + 1
            candidates.append(
                RetrievalCandidate(
                    chunk=_payload_to_chunk(_point_payload(point)),
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
        if len(embedding) != self.dimensions:
            raise ValueError(
                "embedding dimensions do not match store dimensions: "
                f"expected {self.dimensions}, got {len(embedding)}"
            )

    def _ensure_collection(self) -> None:
        if self._collection_exists():
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=self._models.VectorParams(
                size=self.dimensions,
                distance=self._distance_value(),
            ),
        )

    def _collection_exists(self) -> bool:
        if hasattr(self.client, "collection_exists"):
            return bool(self.client.collection_exists(collection_name=self.collection_name))
        try:
            self.client.get_collection(collection_name=self.collection_name)
        except Exception:
            return False
        return True

    def _distance_value(self) -> Any:
        distance_model = getattr(self._models, "Distance", None)
        if distance_model is None:
            return self.config.distance
        normalized = self.config.distance.upper()
        return getattr(distance_model, normalized, self.config.distance)

    def _build_filter(
        self,
        *,
        corpus_id: str | None,
        corpus_version: str | None,
        source_id: str | None,
    ) -> Any | None:
        conditions = [
            self._field_condition("corpus_id", corpus_id),
            self._field_condition("corpus_version", corpus_version),
            self._field_condition("source_id", source_id),
        ]
        resolved_conditions = [condition for condition in conditions if condition is not None]
        if not resolved_conditions:
            return None
        return self._models.Filter(must=resolved_conditions)

    def _field_condition(self, key: str, value: str | None) -> Any | None:
        if value is None:
            return None
        return self._models.FieldCondition(
            key=key,
            match=self._models.MatchValue(value=value),
        )

    def _point_exists(self, point_id: str) -> bool | None:
        if not hasattr(self.client, "retrieve"):
            return None
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[point_id],
            with_payload=False,
            with_vectors=False,
        )
        return bool(points)


def _load_qdrant_dependencies() -> tuple[Any, Any]:
    try:
        qdrant_client_module = importlib.import_module("qdrant_client")
        qdrant_models = importlib.import_module("qdrant_client.models")
    except ImportError as error:
        raise DependencyUnavailableError(
            "qdrant-client is required to construct QdrantVectorStore without "
            "an injected client. Install RegLens with the qdrant extra or install "
            "qdrant-client.",
            details={"package": "qdrant-client", "extra": "qdrant"},
        ) from error
    return qdrant_client_module.QdrantClient, qdrant_models


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, chunk_id))


def _chunk_to_payload(chunk: Chunk) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": _PAYLOAD_SCHEMA,
        "chunk_id": chunk.chunk_id,
        "section_id": chunk.section_id,
        "source_id": chunk.source_id,
        "corpus_id": chunk.corpus_id,
        "corpus_version": chunk.corpus_version,
        "citation_label": chunk.citation_label,
        "title": chunk.title,
        "heading_path": list(chunk.heading_path),
        "text": chunk.text,
        "token_count": chunk.token_count,
        "chunk_index": chunk.chunk_index,
        "section_chunk_count": chunk.section_chunk_count,
        "source_checksum": chunk.source_checksum,
        "metadata": dict(chunk.metadata),
    }
    optional_fields: dict[str, int | str | None] = {
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "page_number": chunk.page_number,
        "url": chunk.url,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    return payload


def _payload_to_chunk(payload: dict[str, Any]) -> Chunk:
    schema = payload.get("schema")
    if schema != _PAYLOAD_SCHEMA:
        raise ValueError(f"unsupported qdrant chunk payload schema: {schema!r}")

    heading_path = payload.get("heading_path", [])
    if not isinstance(heading_path, list):
        raise ValueError("qdrant chunk payload heading_path must be a list")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("qdrant chunk payload metadata must be a dictionary")

    return Chunk(
        chunk_id=_required_str(payload, "chunk_id"),
        section_id=_required_str(payload, "section_id"),
        source_id=_required_str(payload, "source_id"),
        corpus_id=_required_str(payload, "corpus_id"),
        corpus_version=_required_str(payload, "corpus_version"),
        citation_label=_required_str(payload, "citation_label"),
        title=_required_str(payload, "title"),
        heading_path=[str(item) for item in heading_path],
        text=_required_str(payload, "text"),
        token_count=_required_int(payload, "token_count"),
        chunk_index=_required_int(payload, "chunk_index"),
        section_chunk_count=_required_int(payload, "section_chunk_count"),
        source_checksum=_required_str(payload, "source_checksum"),
        char_start=_optional_int(payload, "char_start"),
        char_end=_optional_int(payload, "char_end"),
        page_number=_optional_int(payload, "page_number"),
        url=_optional_str(payload, "url"),
        metadata=dict(metadata),
    )


def _response_points(response: Any) -> list[Any]:
    points = getattr(response, "points", response)
    return list(points)


def _point_payload(point: Any) -> dict[str, Any]:
    payload = _attr_or_item(point, "payload")
    if not isinstance(payload, dict):
        raise ValueError("qdrant point payload must be a dictionary")
    return payload


def _point_score(point: Any) -> float:
    return float(_attr_or_item(point, "score"))


def _attr_or_item(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value[key]
    return getattr(value, key)


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"qdrant chunk payload {key} must be a non-empty string")
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"qdrant chunk payload {key} must be a non-empty string when provided")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"qdrant chunk payload {key} must be an integer")
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"qdrant chunk payload {key} must be an integer when provided")
    return value


class _FallbackModels:
    class Distance:
        COSINE = "Cosine"
        DOT = "Dot"
        EUCLID = "Euclid"
        MANHATTAN = "Manhattan"

    @dataclass(frozen=True)
    class VectorParams:
        size: int
        distance: Any

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
        match: _FallbackModels.MatchValue

    @dataclass(frozen=True)
    class Filter:
        must: list[_FallbackModels.FieldCondition]

    @dataclass(frozen=True)
    class PointIdsList:
        points: list[str]
