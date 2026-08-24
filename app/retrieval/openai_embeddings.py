"""OpenAI-backed embedding provider for live RegLens retrieval."""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from typing import Any

from app.core.errors import DependencyUnavailableError
from app.retrieval.embedding_cache import EmbeddingCache, embedding_cache_key
from app.retrieval.embeddings import Vector


class OpenAIEmbeddingProvider:
    """Embedding provider backed by the OpenAI embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "text-embedding-3-small",
        dimensions: int = 1536,
        cache: EmbeddingCache | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise DependencyUnavailableError(
                "OpenAI API key is required for embeddings",
                details=_missing_key_details("embeddings"),
            )
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")

        self.model_name = model_name
        self._dimensions = dimensions
        self.cache = cache
        self._client = client or _load_openai_client_class()(api_key=api_key)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> Vector:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Iterable[str]) -> list[Vector]:
        batch = list(texts)
        for text in batch:
            if not isinstance(text, str):
                raise TypeError("all texts must be strings")
        if not batch:
            return []

        vectors: list[Vector | None] = []
        uncached_texts: list[str] = []
        uncached_indexes: list[int] = []
        for index, text in enumerate(batch):
            cached = self._cached_vector(text)
            vectors.append(cached)
            if cached is None:
                uncached_texts.append(text)
                uncached_indexes.append(index)

        if not uncached_texts:
            return [list(vector) for vector in vectors if vector is not None]

        try:
            response = self._client.embeddings.create(
                model=self.model_name,
                input=uncached_texts,
                dimensions=self.dimensions,
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "OpenAI embeddings request failed",
                details=_request_failure_details("embeddings", exc),
            ) from exc
        data = list(getattr(response, "data", []))
        if len(data) != len(uncached_texts):
            raise DependencyUnavailableError(
                "OpenAI embeddings response count did not match input count",
                details=_unexpected_response_details("embeddings"),
            )

        for text, index, item in zip(uncached_texts, uncached_indexes, data, strict=True):
            embedding = getattr(item, "embedding", None)
            if not isinstance(embedding, list) or len(embedding) != self.dimensions:
                raise DependencyUnavailableError(
                    "OpenAI embeddings response had an unexpected vector shape",
                    details=_unexpected_response_details("embeddings"),
                )
            vector = [float(value) for value in embedding]
            vectors[index] = vector
            self._cache_vector(text, vector)
        if any(vector is None for vector in vectors):
            raise DependencyUnavailableError(
                "OpenAI embeddings response did not populate every requested vector",
                details=_unexpected_response_details("embeddings"),
            )
        return [list(vector) for vector in vectors if vector is not None]

    def cache_stats(self) -> dict[str, int] | None:
        return self.cache.stats() if self.cache is not None else None

    def _cached_vector(self, text: str) -> Vector | None:
        if self.cache is None:
            return None
        return self.cache.get(self._cache_key(text))

    def _cache_vector(self, text: str, vector: Vector) -> None:
        if self.cache is not None:
            self.cache.set(self._cache_key(text), vector)

    def _cache_key(self, text: str) -> str:
        return embedding_cache_key(
            provider="openai",
            model_name=self.model_name,
            dimensions=self.dimensions,
            text=text,
        )


def _load_openai_client_class() -> Any:
    try:
        module = importlib.import_module("openai")
    except ImportError as exc:
        raise DependencyUnavailableError(
            "OpenAI SDK is not installed",
            details={
                "provider": "openai",
                "component": "embeddings",
                "reason": "package_missing",
                "package": "openai",
                "extra": "openai",
            },
        ) from exc

    client_class = getattr(module, "OpenAI", None)
    if client_class is None:
        raise DependencyUnavailableError(
            "OpenAI SDK does not expose the expected client",
            details=_unexpected_response_details("embeddings"),
        )
    return client_class


def _missing_key_details(component: str) -> dict[str, str]:
    return {
        "provider": "openai",
        "component": component,
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }


def _unexpected_response_details(component: str) -> dict[str, str]:
    return {
        "provider": "openai",
        "component": component,
        "reason": "unexpected_response",
    }


def _request_failure_details(component: str, exc: Exception) -> dict[str, object]:
    details: dict[str, object] = {
        "provider": "openai",
        "component": component,
        "reason": "request_failed",
        "error_type": exc.__class__.__name__,
    }
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        details["status_code"] = status_code
    provider_error_code = getattr(exc, "code", None)
    if isinstance(provider_error_code, str) and provider_error_code.strip():
        details["provider_error_code"] = provider_error_code
    return details
