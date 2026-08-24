from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.errors import DependencyUnavailableError
from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.openai_embeddings import OpenAIEmbeddingProvider


@dataclass(frozen=True)
class _EmbeddingItem:
    embedding: list[float]


@dataclass(frozen=True)
class _EmbeddingResponse:
    data: list[_EmbeddingItem]


class _FakeEmbeddingsEndpoint:
    def __init__(self, *, response: _EmbeddingResponse | None = None) -> None:
        self.response = response or _EmbeddingResponse(
            data=[
                _EmbeddingItem([1.0, 0.0, 0.0]),
                _EmbeddingItem([0.0, 1.0, 0.0]),
            ]
        )
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _EmbeddingResponse:
        self.calls.append(kwargs)
        return self.response


class _FailingEmbeddingsEndpoint:
    def create(self, **kwargs: object) -> object:
        raise RuntimeError("provider failure contained sk-test-secret")


class _QuotaError(RuntimeError):
    status_code = 429
    code = "insufficient_quota"


class _QuotaEmbeddingsEndpoint:
    def create(self, **kwargs: object) -> object:
        raise _QuotaError("quota failure contained sk-test-secret")


class _FakeOpenAIClient:
    def __init__(self, endpoint: object) -> None:
        self.embeddings = endpoint


def test_openai_embedding_provider_calls_embeddings_api_with_model_and_dimensions() -> None:
    endpoint = _FakeEmbeddingsEndpoint()
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model_name="text-embedding-3-small",
        dimensions=3,
        client=_FakeOpenAIClient(endpoint),
    )

    vectors = provider.embed_texts(["records retention", "supervisory procedures"])

    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert endpoint.calls == [
        {
            "model": "text-embedding-3-small",
            "input": ["records retention", "supervisory procedures"],
            "dimensions": 3,
        }
    ]
    assert provider.model_name == "text-embedding-3-small"
    assert provider.dimensions == 3


def test_openai_embedding_provider_handles_empty_batches_without_network_call() -> None:
    endpoint = _FakeEmbeddingsEndpoint()
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        dimensions=3,
        client=_FakeOpenAIClient(endpoint),
    )

    assert provider.embed_texts([]) == []
    assert endpoint.calls == []


def test_openai_embedding_provider_reuses_cached_vectors() -> None:
    endpoint = _FakeEmbeddingsEndpoint(
        response=_EmbeddingResponse(data=[_EmbeddingItem([1.0, 0.0, 0.0])])
    )
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        dimensions=3,
        cache=EmbeddingCache(max_entries=10),
        client=_FakeOpenAIClient(endpoint),
    )

    assert provider.embed_text("records retention") == [1.0, 0.0, 0.0]
    assert provider.embed_text("records retention") == [1.0, 0.0, 0.0]

    assert len(endpoint.calls) == 1
    assert provider.cache_stats() == {"entries": 1, "max_entries": 10, "hits": 1, "misses": 1}


def test_openai_embedding_provider_validates_text_inputs() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        dimensions=3,
        client=_FakeOpenAIClient(_FakeEmbeddingsEndpoint()),
    )

    with pytest.raises(TypeError, match="all texts must be strings"):
        provider.embed_texts(["good", object()])  # type: ignore[list-item]


def test_openai_embedding_provider_rejects_unexpected_response_count() -> None:
    endpoint = _FakeEmbeddingsEndpoint(response=_EmbeddingResponse(data=[_EmbeddingItem([1.0])]))
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        dimensions=1,
        client=_FakeOpenAIClient(endpoint),
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        provider.embed_texts(["one", "two"])

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "unexpected_response",
    }


def test_openai_embedding_provider_rejects_unexpected_vector_shape() -> None:
    endpoint = _FakeEmbeddingsEndpoint(
        response=_EmbeddingResponse(data=[_EmbeddingItem([1.0, 2.0])])
    )
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        dimensions=3,
        client=_FakeOpenAIClient(endpoint),
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        provider.embed_text("records")

    assert exc_info.value.details["reason"] == "unexpected_response"


def test_openai_embedding_provider_sanitizes_upstream_errors() -> None:
    secret = "sk-test-secret"
    provider = OpenAIEmbeddingProvider(
        api_key=secret,
        dimensions=3,
        client=_FakeOpenAIClient(_FailingEmbeddingsEndpoint()),
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        provider.embed_text("records")

    serialized = str(exc_info.value.details)
    assert exc_info.value.message == "OpenAI embeddings request failed"
    assert exc_info.value.details == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "request_failed",
        "error_type": "RuntimeError",
    }
    assert secret not in serialized


def test_openai_embedding_provider_includes_sanitized_provider_error_code() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test-secret",
        dimensions=3,
        client=_FakeOpenAIClient(_QuotaEmbeddingsEndpoint()),
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        provider.embed_text("records")

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "request_failed",
        "error_type": "_QuotaError",
        "status_code": 429,
        "provider_error_code": "insufficient_quota",
    }
    assert "sk-test-secret" not in str(exc_info.value.details)


def test_openai_embedding_provider_does_not_leak_secret_when_key_missing() -> None:
    with pytest.raises(DependencyUnavailableError) as exc_info:
        OpenAIEmbeddingProvider(api_key=" ", client=_FakeOpenAIClient(_FakeEmbeddingsEndpoint()))

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }
