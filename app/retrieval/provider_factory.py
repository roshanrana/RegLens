"""Provider factory wiring for retrieval components."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.retrieval.rerank import FakeReranker, Reranker


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake" and settings.use_fake_embeddings:
        return FakeEmbeddingProvider()
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise DependencyUnavailableError(
                "OpenAI API key is required for embeddings",
                details={
                    "provider": "openai",
                    "component": "embeddings",
                    "reason": "missing_api_key",
                    "env_var": "OPENAI_API_KEY",
                },
            )
        from app.retrieval.openai_embeddings import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model_name=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
            cache=(
                EmbeddingCache(max_entries=settings.embedding_cache_max_entries)
                if settings.enable_embedding_cache
                else None
            ),
        )
    raise DependencyUnavailableError(
        "embedding provider is not configured",
        details={
            "provider": settings.embedding_provider,
            "component": "embeddings",
            "reason": "provider_not_configured",
        },
    )


def build_reranker(settings: Settings) -> Reranker:
    if settings.reranker_provider == "fake" and settings.use_fake_reranker:
        return FakeReranker()
    if settings.reranker_provider == "cross_encoder":
        from app.retrieval.cross_encoder_reranker import CrossEncoderReranker

        return CrossEncoderReranker(
            model_name=settings.cross_encoder_model,
            batch_size=settings.cross_encoder_batch_size,
            max_length=settings.cross_encoder_max_length,
            device=settings.cross_encoder_device,
            cache_folder=settings.cross_encoder_cache_folder,
            local_files_only=settings.cross_encoder_local_files_only,
            trust_remote_code=settings.cross_encoder_trust_remote_code,
        )
    raise DependencyUnavailableError(
        "reranker provider is not configured",
        details={
            "provider": settings.reranker_provider,
            "component": "reranker",
            "reason": "provider_not_configured",
        },
    )
