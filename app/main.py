from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import admin_router, audit_router, query_router, ui_router
from app.core.config import Settings, get_settings
from app.core.errors import (
    ConfigurationError,
    DependencyUnavailableError,
    RegLensError,
    error_response,
)
from app.core.security import (
    InMemoryRateLimiter,
    access_error_for_request,
    rate_limit_error_for_request,
)
from app.domain.models import Chunk
from app.generation.provider_factory import build_generation_service
from app.generation.service import GenerationService
from app.persistence.db import initialize_database
from app.persistence.repositories import (
    ChatSessionRepository,
    DocumentChunkRepository,
    DocumentSectionRepository,
    IngestionJobRepository,
    QueryAuditRepository,
    SourceAuditEventRepository,
    SourceDocumentRepository,
)
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.provider_factory import build_embedding_provider, build_reranker
from app.retrieval.qdrant_store import QdrantVectorStore
from app.retrieval.rerank import Reranker
from app.retrieval.service import RetrievalService, build_fixture_retrieval_service


def create_app(
    settings: Settings | None = None,
    *,
    qdrant_client: Any | None = None,
    qdrant_models: Any | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            app.state.db_connection.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        description="RegLens API for cited regulatory question answering.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.db_connection = _open_sqlite_connection(resolved_settings)
    app.state.query_audit_repository = QueryAuditRepository(app.state.db_connection)
    app.state.source_document_repository = SourceDocumentRepository(app.state.db_connection)
    app.state.document_section_repository = DocumentSectionRepository(app.state.db_connection)
    document_chunk_repository = DocumentChunkRepository(app.state.db_connection)
    app.state.document_chunk_repository = document_chunk_repository
    app.state.ingestion_job_repository = IngestionJobRepository(app.state.db_connection)
    app.state.source_audit_event_repository = SourceAuditEventRepository(
        app.state.db_connection
    )
    app.state.chat_session_repository = ChatSessionRepository(app.state.db_connection)
    app.state.retrieval_refresh_lock = RLock()
    app.state.qdrant_status = "skipped" if resolved_settings.is_fake_mode else "not_configured"
    app.state.qdrant_reason = (
        "Fake mode does not require Qdrant."
        if resolved_settings.is_fake_mode
        else "Qdrant retrieval has not been configured for this mode."
    )
    app.state.embedding_provider = None
    app.state.embedding_startup_error = None
    app.state.reranker = None
    app.state.reranker_startup_error = None
    app.state.generation_service = None
    app.state.generation_startup_error = None
    app.state.retrieval_startup_error = None
    app.state.rate_limiter = (
        InMemoryRateLimiter(limit_per_minute=resolved_settings.rate_limit_per_minute)
        if resolved_settings.rate_limit_per_minute > 0
        else None
    )

    try:
        app.state.generation_service = build_generation_service(resolved_settings)
    except DependencyUnavailableError as exc:
        app.state.generation_startup_error = exc

    try:
        app.state.embedding_provider = build_embedding_provider(resolved_settings)
    except DependencyUnavailableError as exc:
        app.state.embedding_startup_error = exc

    try:
        app.state.reranker = build_reranker(resolved_settings)
    except DependencyUnavailableError as exc:
        app.state.reranker_startup_error = exc

    if resolved_settings.is_fake_mode:
        provider_error = _retrieval_provider_startup_error(app)
        if provider_error is None:
            app.state.retrieval_service = _build_mock_retrieval_service(
                chunk_repository=document_chunk_repository,
                embedding_provider=app.state.embedding_provider,
                reranker=app.state.reranker,
                default_top_k=resolved_settings.default_top_k,
                max_evidence_tokens=resolved_settings.max_evidence_tokens,
            )
        else:
            _mark_retrieval_unavailable(app, provider_error)
    elif resolved_settings.rag_mode == "local":
        try:
            provider_error = _retrieval_provider_startup_error(app)
            if provider_error is not None:
                raise provider_error
            app.state.retrieval_service = _build_local_qdrant_retrieval_service(
                settings=resolved_settings,
                chunk_repository=document_chunk_repository,
                embedding_provider=app.state.embedding_provider,
                reranker=app.state.reranker,
                qdrant_client=qdrant_client,
                qdrant_models=qdrant_models,
            )
            app.state.qdrant_status = "available"
            app.state.qdrant_reason = "Qdrant vector store is available."
        except DependencyUnavailableError as exc:
            _mark_retrieval_unavailable(app, exc)
        except Exception as exc:
            startup_error = DependencyUnavailableError(
                "Qdrant vector store is unavailable",
                details={"reason": str(exc), "type": exc.__class__.__name__},
            )
            _mark_retrieval_unavailable(app, startup_error)
    elif resolved_settings.rag_mode == "real":
        provider_error = _retrieval_provider_startup_error(app)
        if provider_error is None:
            provider_error = DependencyUnavailableError(
                "real RAG mode retrieval provider is not configured",
                details={"mode": "real", "reason": "retrieval_provider_not_configured"},
            )
        _mark_retrieval_unavailable(app, provider_error)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            resolved_settings.request_id_header,
            resolved_settings.api_key_header,
        ],
    )

    @app.middleware("http")
    async def add_request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(
            resolved_settings.request_id_header,
            f"req_{uuid4().hex}",
        )
        request.state.request_id = request_id
        started_at = perf_counter()

        access_error = access_error_for_request(request, resolved_settings)
        if access_error is not None:
            response: Response = error_response(access_error, request_id=request_id)
            response.headers[resolved_settings.request_id_header] = request_id
            return response

        rate_error, retry_after = rate_limit_error_for_request(
            request,
            resolved_settings,
            getattr(app.state, "rate_limiter", None),
        )
        if rate_error is not None:
            response = error_response(rate_error, request_id=request_id)
            response.headers[resolved_settings.request_id_header] = request_id
            if retry_after is not None:
                response.headers["Retry-After"] = str(retry_after)
            return response

        response = await call_next(request)
        response.headers[resolved_settings.request_id_header] = request_id
        response.headers["X-Response-Time-Ms"] = f"{(perf_counter() - started_at) * 1000:.2f}"
        return response

    @app.exception_handler(RegLensError)
    async def handle_reglens_error(request: Request, exc: RegLensError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req_{uuid4().hex}")
        return error_response(exc, request_id=request_id)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": resolved_settings.app_name,
            "version": resolved_settings.app_version,
            "mode": resolved_settings.rag_mode,
        }

    @app.get("/ready")
    def ready() -> dict[str, object]:
        retrieval_ready = isinstance(
            getattr(app.state, "retrieval_service", None),
            RetrievalService,
        )
        generation_ready = isinstance(
            getattr(app.state, "generation_service", None),
            GenerationService,
        )
        overall_status = (
            "ready"
            if retrieval_ready and generation_ready
            else "degraded"
        )

        return {
            "status": overall_status,
            "service": resolved_settings.app_name,
            "mode": resolved_settings.rag_mode,
            "checks": {
                "configuration": {"status": "ok"},
                "database": {"status": "configured", "url": resolved_settings.database_url},
                "embedding_provider": _provider_check(
                    provider=resolved_settings.embedding_provider,
                    fake_enabled=resolved_settings.use_fake_embeddings,
                    instance=getattr(app.state, "embedding_provider", None),
                    startup_error=getattr(app.state, "embedding_startup_error", None),
                ),
                "llm_provider": _provider_check(
                    provider=resolved_settings.llm_provider,
                    fake_enabled=resolved_settings.use_fake_llm,
                    instance=getattr(app.state, "generation_service", None),
                    startup_error=getattr(app.state, "generation_startup_error", None),
                ),
                "reranker": _provider_check(
                    provider=resolved_settings.reranker_provider,
                    fake_enabled=resolved_settings.use_fake_reranker,
                    instance=getattr(app.state, "reranker", None),
                    startup_error=getattr(app.state, "reranker_startup_error", None),
                ),
                "qdrant": {
                    "status": app.state.qdrant_status,
                    "url": resolved_settings.qdrant_url,
                    "collection": resolved_settings.qdrant_collection,
                    "reason": app.state.qdrant_reason,
                },
            },
        }

    app.include_router(query_router)
    app.include_router(audit_router)
    app.include_router(admin_router)
    app.include_router(ui_router)

    return app


def _build_mock_retrieval_service(
    *,
    chunk_repository: DocumentChunkRepository,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    default_top_k: int,
    max_evidence_tokens: int,
) -> RetrievalService:
    fixture_service = build_fixture_retrieval_service(
        embedding_provider=embedding_provider,
        reranker=reranker,
        default_top_k=default_top_k,
        max_evidence_tokens=max_evidence_tokens,
    )
    persisted_chunks = chunk_repository.list_all()
    if not persisted_chunks:
        return fixture_service

    chunks_by_id = {chunk.chunk_id: chunk for chunk in fixture_service.chunks}
    for chunk in persisted_chunks:
        chunks_by_id[chunk.chunk_id] = chunk

    return RetrievalService(
        list(chunks_by_id.values()),
        embedding_provider=fixture_service.embedding_provider,
        reranker=fixture_service.reranker,
        mode=fixture_service.mode,
        enable_reranking=fixture_service.enable_reranking,
        default_top_k=fixture_service.default_top_k,
        max_evidence_tokens=fixture_service.max_evidence_tokens,
        rrf_k=fixture_service.rrf_k,
    )


def _build_local_qdrant_retrieval_service(
    *,
    settings: Settings,
    chunk_repository: DocumentChunkRepository,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    qdrant_client: Any | None,
    qdrant_models: Any | None,
) -> RetrievalService:
    chunks = _chunks_for_retrieval_index(
        chunk_repository=chunk_repository,
        default_top_k=settings.default_top_k,
        max_evidence_tokens=settings.max_evidence_tokens,
    )
    vector_store = QdrantVectorStore(
        collection_name=settings.qdrant_collection,
        url=settings.qdrant_url,
        embedding_provider=embedding_provider,
        client=qdrant_client,
        models=qdrant_models,
    )
    vector_store.upsert_chunks(chunks)
    return RetrievalService(
        chunks,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        reranker=reranker,
        mode="local",
        default_top_k=settings.default_top_k,
        max_evidence_tokens=settings.max_evidence_tokens,
    )


def _retrieval_provider_startup_error(app: FastAPI) -> DependencyUnavailableError | None:
    for attribute in ("embedding_startup_error", "reranker_startup_error"):
        startup_error = getattr(app.state, attribute, None)
        if isinstance(startup_error, DependencyUnavailableError):
            return startup_error
    return None


def _mark_retrieval_unavailable(app: FastAPI, error: DependencyUnavailableError) -> None:
    app.state.retrieval_startup_error = error
    app.state.qdrant_status = "unavailable"
    app.state.qdrant_reason = error.message


def _provider_check(
    *,
    provider: str,
    fake_enabled: bool,
    instance: object | None,
    startup_error: object | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "available" if instance is not None else "unavailable",
        "provider": provider,
        "fake_enabled": fake_enabled,
    }
    model_name = getattr(instance, "model_name", None)
    if isinstance(model_name, str):
        payload["model"] = model_name
    if instance is None:
        if isinstance(startup_error, DependencyUnavailableError):
            payload["reason"] = startup_error.message
            if startup_error.details:
                payload["details"] = startup_error.details
        else:
            payload["reason"] = "provider has not been configured"
    return payload


def _chunks_for_retrieval_index(
    *,
    chunk_repository: DocumentChunkRepository,
    default_top_k: int,
    max_evidence_tokens: int,
) -> list[Chunk]:
    fixture_service = build_fixture_retrieval_service(
        default_top_k=default_top_k,
        max_evidence_tokens=max_evidence_tokens,
    )
    chunks_by_id = {chunk.chunk_id: chunk for chunk in fixture_service.chunks}
    for chunk in chunk_repository.list_all():
        chunks_by_id[chunk.chunk_id] = chunk
    return list(chunks_by_id.values())


def _open_sqlite_connection(settings: Settings) -> sqlite3.Connection:
    path = _sqlite_path_from_database_url(settings)
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize_database(connection)
    return connection


def _sqlite_path_from_database_url(settings: Settings) -> str:
    database_url = settings.database_url.strip()
    if settings.app_env == "test" and database_url == "sqlite:///./reglens.db":
        return ":memory:"
    if database_url == ":memory:":
        return database_url

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ConfigurationError(
            "only sqlite database_url values are supported in the current RegLens slice",
            details={"database_url": settings.database_url},
        )

    path = database_url.removeprefix(prefix)
    if not path:
        raise ConfigurationError("sqlite database_url must include a database path")
    return path


app = create_app()
