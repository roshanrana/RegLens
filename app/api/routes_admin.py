from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import uuid4

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, Field

from app.core.errors import (
    ChunkingError,
    CorpusLoadError,
    DependencyUnavailableError,
    RegLensError,
)
from app.domain.models import (
    Chunk,
    DocumentSection,
    DocumentSource,
    IngestionJob,
    SourceAuditAction,
    SourceAuditEvent,
    SourceAuditStatus,
)
from app.ingestion.chunking import Chunker
from app.ingestion.loaders import (
    CorpusLoader,
    HtmlCorpusLoader,
    LoadResult,
    MarkdownCorpusLoader,
    PdfCorpusLoader,
    PlainTextCorpusLoader,
)
from app.persistence.repositories import (
    DocumentChunkRepository,
    DocumentSectionRepository,
    IngestionJobRepository,
    SourceAuditEventRepository,
    SourceDocumentRepository,
)
from app.retrieval.qdrant_store import QdrantVectorStore
from app.retrieval.service import RetrievalService, build_fixture_retrieval_service

router = APIRouter(tags=["admin"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[2].parent
FIXTURE_ROOT = WORKSPACE_ROOT / "app" / "evals" / "fixtures"
SUPPORTED_INPUT_TYPES = {"markdown", "text", "html", "pdf"}


class IngestRequest(BaseModel):
    path: str = Field(..., min_length=1)
    input_type: str = Field(..., min_length=1)
    corpus_id: str | None = None
    corpus_name: str | None = None
    version: str | None = None


class IngestUrlRequest(BaseModel):
    url: str = Field(..., min_length=1)
    input_type: str = Field(..., min_length=1)
    corpus_id: str | None = None
    corpus_name: str | None = None
    version: str | None = None


@dataclass(frozen=True)
class RemoteSource:
    body: bytes
    content_type: str | None = None
    final_url: str | None = None


@router.post("/admin/ingest")
def ingest_local_file(payload: IngestRequest, request: Request) -> dict[str, Any]:
    input_type = _validate_input_type(payload.input_type)
    input_path = _validate_ingest_path(payload.path)
    job_repository = _ingestion_job_repository(request)
    source_repository = _source_repository(request)
    section_repository = _section_repository(request)
    chunk_repository = _chunk_repository(request)

    job = IngestionJob(
        job_id=f"ing_{uuid4().hex}",
        corpus_id=payload.corpus_id or "pending-corpus",
        corpus_name=payload.corpus_name or "Pending Corpus",
        corpus_version=payload.version or "pending-version",
        input_type=input_type,
        input_uri=input_path.as_posix(),
        status="running",
    )
    job_repository.save(job)

    loader = _loader_for_type(input_type)
    overrides = _loader_overrides(payload)
    try:
        load_result = loader.load(input_path, **overrides)
    except DependencyUnavailableError as exc:
        failed_job = _finish_failed_job(
            job,
            message=_dependency_failure_message(input_type),
            details={**exc.details, "path": input_path.as_posix()},
        )
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            job=failed_job,
            details=failed_job.error or {},
        )
        raise DependencyUnavailableError(
            exc.message,
            details={
                **exc.details,
                "job_id": job.job_id,
                "path": input_path.as_posix(),
            },
        ) from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        failed_job = _finish_failed_job(job, message="failed to load source file", exc=exc)
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            job=failed_job,
            details=failed_job.error or {},
        )
        raise CorpusLoadError(
            "failed to load source file",
            details={"job_id": job.job_id, "path": input_path.as_posix(), "reason": str(exc)},
        ) from exc

    return _complete_ingestion_from_load_result(
        request=request,
        input_type=input_type,
        input_uri=input_path.as_posix(),
        job=job,
        load_result=load_result,
        job_repository=job_repository,
        source_repository=source_repository,
        section_repository=section_repository,
        chunk_repository=chunk_repository,
    )


@router.post("/admin/ingest-url")
def ingest_remote_url(payload: IngestUrlRequest, request: Request) -> dict[str, Any]:
    input_type = _validate_input_type(payload.input_type)
    settings = request.app.state.settings
    url = _validate_remote_ingest_url(payload.url, settings.allowed_ingest_url_hosts)
    job_repository = _ingestion_job_repository(request)
    source_repository = _source_repository(request)
    section_repository = _section_repository(request)
    chunk_repository = _chunk_repository(request)

    job = IngestionJob(
        job_id=f"ing_{uuid4().hex}",
        corpus_id=payload.corpus_id or "pending-corpus",
        corpus_name=payload.corpus_name or "Pending Corpus",
        corpus_version=payload.version or "pending-version",
        input_type=input_type,
        input_uri=url,
        status="running",
    )
    job_repository.save(job)

    try:
        remote_source = _read_remote_source(url, max_bytes=settings.remote_ingest_max_bytes)
        final_url = _validate_remote_ingest_url(
            remote_source.final_url or url,
            settings.allowed_ingest_url_hosts,
        )
        snapshot_path = _write_remote_snapshot(
            remote_source.body,
            input_type=input_type,
            document_storage_path=settings.document_storage_path,
        )
        loader = _loader_for_type(input_type)
        overrides = {
            **_loader_overrides(payload),
            "raw_storage_uri": snapshot_path.as_posix(),
            "url": final_url,
            "retrieved_at": _utcnow(),
            "metadata": {
                "remote_ingest": True,
                "source_url": url,
                "final_url": final_url,
                "content_type": remote_source.content_type,
            },
        }
        load_result = loader.load(snapshot_path, **overrides)
    except DependencyUnavailableError as exc:
        failed_job = _finish_failed_job(
            job,
            message=_dependency_failure_message(input_type),
            details={**exc.details, "url": url},
        )
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            job=failed_job,
            details=failed_job.error or {},
        )
        raise DependencyUnavailableError(
            exc.message,
            details={**exc.details, "job_id": job.job_id, "url": url},
        ) from exc
    except RegLensError as exc:
        failed_job = _finish_failed_job(
            job,
            message="failed to ingest remote source",
            details={"code": exc.code, **exc.details},
        )
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            job=failed_job,
            details=failed_job.error or {},
        )
        raise
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        failed_job = _finish_failed_job(job, message="failed to ingest remote source", exc=exc)
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            job=failed_job,
            details=failed_job.error or {},
        )
        raise CorpusLoadError(
            "failed to ingest remote source",
            details={"job_id": job.job_id, "url": url, "reason": str(exc)},
        ) from exc

    return _complete_ingestion_from_load_result(
        request=request,
        input_type=input_type,
        input_uri=url,
        job=job,
        load_result=load_result,
        job_repository=job_repository,
        source_repository=source_repository,
        section_repository=section_repository,
        chunk_repository=chunk_repository,
    )


@router.post("/documents/url")
def create_document_from_url(payload: IngestUrlRequest, request: Request) -> dict[str, Any]:
    return ingest_remote_url(payload, request)


def _complete_ingestion_from_load_result(
    *,
    request: Request,
    input_type: str,
    input_uri: str,
    job: IngestionJob,
    load_result: LoadResult,
    job_repository: IngestionJobRepository,
    source_repository: SourceDocumentRepository,
    section_repository: DocumentSectionRepository,
    chunk_repository: DocumentChunkRepository,
) -> dict[str, Any]:
    source = replace(load_result.source, document_type=input_type)
    sections = _sections_with_version(load_result.sections, corpus_version=source.version)
    if load_result.errors:
        failed_job = _finish_failed_job(
            replace(
                job,
                corpus_id=source.corpus_id,
                corpus_name=source.corpus_name,
                corpus_version=source.version,
            ),
            message="source file could not be converted into sections",
            details={"errors": load_result.errors},
        )
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            source=source,
            job=failed_job,
            details=failed_job.error or {"errors": load_result.errors},
        )
        raise CorpusLoadError(
            "source file could not be converted into sections",
            details={"job_id": job.job_id, "errors": load_result.errors},
        )

    try:
        chunks = Chunker().chunk_sections(
            sections,
            corpus_version=source.version,
            source_checksum=source.checksum,
        )
    except ValueError as exc:
        failed_job = _finish_failed_job(job, message="failed to chunk source sections", exc=exc)
        job_repository.save(failed_job)
        _save_source_audit_event(
            request,
            action="ingest",
            status_value="failed",
            source=source,
            job=failed_job,
            details=failed_job.error or {},
        )
        raise ChunkingError(
            "failed to chunk source sections",
            details={"job_id": job.job_id, "source_id": source.source_id, "reason": str(exc)},
        ) from exc

    source_repository.upsert(source)
    section_repository.upsert_many(sections)
    chunk_repository.upsert_many(chunks)
    retrieval_index_chunk_count = _refresh_active_retrieval_service(request, chunks)

    completed_job = replace(
        job,
        corpus_id=source.corpus_id,
        corpus_name=source.corpus_name,
        corpus_version=source.version,
        status="completed",
        finished_at=_utcnow(),
        report={
            "source_id": source.source_id,
            "sections_persisted": len(sections),
            "chunks_persisted": len(chunks),
            "retrieval_index_chunks": retrieval_index_chunk_count,
            "input_uri": input_uri,
            "input_path": input_uri,
        },
        error=None,
    )
    job_repository.save(completed_job)
    _save_source_audit_event(
        request,
        action="ingest",
        status_value="completed",
        source=source,
        job=completed_job,
        details=completed_job.report,
    )

    return {
        "job": _job_payload(completed_job),
        "source": _source_payload(
            source,
            section_count=len(sections),
            chunk_count=len(chunks),
        ),
    }


@router.post("/documents")
def create_document(payload: IngestRequest, request: Request) -> dict[str, Any]:
    return ingest_local_file(payload, request)


@router.delete("/documents/{source_id}")
def delete_document(source_id: str, request: Request) -> dict[str, Any]:
    source_repository = _source_repository(request)
    chunk_repository = _chunk_repository(request)
    source = source_repository.get(source_id)
    if source is None:
        _save_source_audit_event(
            request,
            action="delete",
            status_value="failed",
            source_id=source_id,
            details={"reason": "source_not_found"},
        )
        raise RegLensError(
            "source document was not found",
            code="source_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"source_id": source_id},
        )

    chunks = chunk_repository.list_by_source(source_id)
    source_repository.delete(source_id)
    _delete_chunks_from_active_vector_store(request, chunks)
    retrieval_index_chunk_count = _reload_active_retrieval_service_from_repository(request)
    _save_source_audit_event(
        request,
        action="delete",
        status_value="completed",
        source=source,
        details={
            "chunks_removed": len(chunks),
            "retrieval_index_chunks": retrieval_index_chunk_count,
        },
    )

    return {
        "deleted": True,
        "source_id": source_id,
        "corpus_id": source.corpus_id,
        "corpus_version": source.version,
        "chunks_removed": len(chunks),
        "retrieval_index_chunks": retrieval_index_chunk_count,
    }


@router.get("/admin/ingest/{job_id}")
def get_ingestion_job(job_id: str, request: Request) -> dict[str, Any]:
    job = _ingestion_job_repository(request).get(job_id)
    if job is None:
        raise RegLensError(
            "ingestion job was not found",
            code="ingestion_job_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"job_id": job_id},
        )
    return {"job": _job_payload(job)}


@router.get("/sources")
def list_sources(
    request: Request,
    corpus_id: str | None = Query(default=None),
    corpus_version: str | None = Query(default=None),
) -> dict[str, Any]:
    source_repository = _source_repository(request)
    section_repository = _section_repository(request)
    chunk_repository = _chunk_repository(request)

    sources = source_repository.list(corpus_id=corpus_id, corpus_version=corpus_version)
    return {
        "sources": [
            _source_payload(
                source,
                section_count=len(section_repository.list_by_source(source.source_id)),
                chunk_count=len(chunk_repository.list_by_source(source.source_id)),
            )
            for source in sources
        ],
        "count": len(sources),
        "filters": {"corpus_id": corpus_id, "corpus_version": corpus_version},
    }


@router.get("/sources/{source_id}")
def get_source(source_id: str, request: Request) -> dict[str, Any]:
    source_repository = _source_repository(request)
    section_repository = _section_repository(request)
    chunk_repository = _chunk_repository(request)

    source = source_repository.get(source_id)
    if source is None:
        raise RegLensError(
            "source document was not found",
            code="source_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"source_id": source_id},
        )

    sections = section_repository.list_by_source(source_id)
    chunks = chunk_repository.list_by_source(source_id)
    return {
        "source": _source_payload(
            source,
            section_count=len(sections),
            chunk_count=len(chunks),
        ),
        "sections": [_section_payload(section) for section in sections],
        "chunks": [_chunk_payload(chunk) for chunk in chunks],
    }


def _validate_input_type(input_type: str) -> str:
    normalized = input_type.strip().lower()
    if normalized in SUPPORTED_INPUT_TYPES:
        return normalized
    allowed_values = ", ".join(sorted(SUPPORTED_INPUT_TYPES))
    raise RegLensError(
        f"input_type must be one of: {allowed_values}",
        code="invalid_input_type",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        details={"input_type": input_type, "allowed": sorted(SUPPORTED_INPUT_TYPES)},
    )


def _validate_ingest_path(raw_path: str) -> Path:
    stripped = raw_path.strip()
    if not stripped or "://" in stripped:
        raise RegLensError(
            "ingest path must be a local filesystem path",
            code="invalid_ingest_path",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"path": raw_path},
        )

    path = Path(stripped).expanduser()
    candidate_paths = [path] if path.is_absolute() else [Path.cwd() / path, WORKSPACE_ROOT / path]
    resolved: Path | None = None
    last_error: OSError | None = None
    for candidate_path in candidate_paths:
        try:
            resolved = candidate_path.resolve(strict=True)
            break
        except OSError as exc:
            last_error = exc
            continue
    if resolved is None:
        assert last_error is not None
        raise RegLensError(
            "ingest path does not exist or is not readable",
            code="ingest_path_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"path": raw_path},
        ) from last_error

    allowed_roots = (WORKSPACE_ROOT.resolve(), FIXTURE_ROOT.resolve())
    if not resolved.is_file() or not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise RegLensError(
            "ingest path must be under the RegLens workspace or fixture directory",
            code="invalid_ingest_path",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={
                "path": resolved.as_posix(),
                "allowed_roots": [root.as_posix() for root in allowed_roots],
            },
        )
    return resolved


def _validate_remote_ingest_url(
    raw_url: str,
    allowed_hosts: tuple[str, ...],
) -> str:
    stripped = raw_url.strip()
    parsed = urlparse(stripped)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise RegLensError(
            "remote ingest URL must be an HTTPS URL",
            code="invalid_ingest_url",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"url": raw_url},
        )

    normalized_hosts = tuple(hostname.strip().lower() for hostname in allowed_hosts if hostname)
    if not any(host == allowed or host.endswith(f".{allowed}") for allowed in normalized_hosts):
        raise RegLensError(
            "remote ingest URL host is not allowed",
            code="ingest_url_host_not_allowed",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"host": host, "allowed_hosts": list(normalized_hosts)},
        )
    return stripped


def _read_remote_source(url: str, *, max_bytes: int) -> RemoteSource:
    request = UrlRequest(
        url,
        headers={"User-Agent": "RegLens/0.1 remote-ingest"},
        method="GET",
    )
    with urlopen(request, timeout=20) as response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError(f"remote source exceeded configured limit of {max_bytes} bytes")
        headers = getattr(response, "headers", None)
        content_type = headers.get("Content-Type") if headers is not None else None
        final_url = getattr(response, "url", None)
        return RemoteSource(
            body=body,
            content_type=str(content_type) if content_type is not None else None,
            final_url=str(final_url) if final_url is not None else url,
        )


def _write_remote_snapshot(
    body: bytes,
    *,
    input_type: str,
    document_storage_path: str,
) -> Path:
    digest = hashlib.sha256(body).hexdigest()
    suffix = {
        "markdown": ".md",
        "text": ".txt",
        "html": ".html",
        "pdf": ".pdf",
    }[input_type]
    root = Path(document_storage_path).expanduser()
    snapshot_dir = root / "remote"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{digest[:24]}{suffix}"
    snapshot_path.write_bytes(body)
    return snapshot_path.resolve()


def _loader_for_type(input_type: str) -> CorpusLoader:
    if input_type == "markdown":
        return MarkdownCorpusLoader()
    if input_type == "text":
        return PlainTextCorpusLoader()
    if input_type == "html":
        return HtmlCorpusLoader()
    return PdfCorpusLoader()


def _dependency_failure_message(input_type: str) -> str:
    if input_type == "pdf":
        return "PDF ingestion dependency is unavailable"
    return "ingestion dependency is unavailable"


def _loader_overrides(payload: IngestRequest | IngestUrlRequest) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if payload.corpus_id is not None:
        overrides["corpus_id"] = payload.corpus_id
    if payload.corpus_name is not None:
        overrides["corpus_name"] = payload.corpus_name
    if payload.version is not None:
        overrides["version"] = payload.version
    return overrides


def _sections_with_version(
    sections: list[DocumentSection],
    *,
    corpus_version: str,
) -> list[DocumentSection]:
    return [
        section
        if section.corpus_version is not None
        else replace(section, corpus_version=corpus_version)
        for section in sections
    ]


def _finish_failed_job(
    job: IngestionJob,
    *,
    message: str,
    exc: Exception | None = None,
    details: dict[str, Any] | None = None,
) -> IngestionJob:
    error_details = dict(details or {})
    if exc is not None:
        error_details["reason"] = str(exc)
    return replace(
        job,
        status="failed",
        finished_at=_utcnow(),
        error={"message": message, **error_details},
    )


def _refresh_active_retrieval_service(request: Request, chunks: list[Chunk]) -> int | None:
    if not chunks:
        return None

    lock = getattr(request.app.state, "retrieval_refresh_lock", None)
    if lock is None:
        return _rebuild_active_retrieval_service(request, chunks)

    with lock:
        return _rebuild_active_retrieval_service(request, chunks)


def _rebuild_active_retrieval_service(request: Request, chunks: list[Chunk]) -> int | None:
    current_service = getattr(request.app.state, "retrieval_service", None)
    if not isinstance(current_service, RetrievalService):
        return None

    if isinstance(current_service.vector_store, QdrantVectorStore):
        current_service.vector_store.upsert_chunks(chunks)

    chunks_by_id = {chunk.chunk_id: chunk for chunk in current_service.chunks}
    for chunk in chunks:
        chunks_by_id[chunk.chunk_id] = chunk

    refreshed_service = RetrievalService(
        list(chunks_by_id.values()),
        embedding_provider=current_service.embedding_provider,
        vector_store=current_service.vector_store,
        reranker=current_service.reranker,
        mode=current_service.mode,
        enable_reranking=current_service.enable_reranking,
        default_top_k=current_service.default_top_k,
        max_evidence_tokens=current_service.max_evidence_tokens,
        rrf_k=current_service.rrf_k,
    )
    request.app.state.retrieval_service = refreshed_service
    return len(refreshed_service.chunks)


def _delete_chunks_from_active_vector_store(request: Request, chunks: list[Chunk]) -> None:
    current_service = getattr(request.app.state, "retrieval_service", None)
    if not isinstance(current_service, RetrievalService):
        return
    if not isinstance(current_service.vector_store, QdrantVectorStore):
        return

    for chunk in chunks:
        current_service.vector_store.delete_chunk(chunk.chunk_id)


def _reload_active_retrieval_service_from_repository(request: Request) -> int | None:
    lock = getattr(request.app.state, "retrieval_refresh_lock", None)
    if lock is None:
        return _rebuild_active_retrieval_service_from_repository(request)

    with lock:
        return _rebuild_active_retrieval_service_from_repository(request)


def _rebuild_active_retrieval_service_from_repository(request: Request) -> int | None:
    current_service = getattr(request.app.state, "retrieval_service", None)
    if not isinstance(current_service, RetrievalService):
        return None

    fixture_service = build_fixture_retrieval_service(
        default_top_k=current_service.default_top_k,
        max_evidence_tokens=current_service.max_evidence_tokens,
    )
    chunks_by_id = {chunk.chunk_id: chunk for chunk in fixture_service.chunks}
    for chunk in _chunk_repository(request).list_all():
        chunks_by_id[chunk.chunk_id] = chunk
    chunks = list(chunks_by_id.values())

    vector_store = current_service.vector_store
    if isinstance(vector_store, QdrantVectorStore):
        vector_store.upsert_chunks(chunks)

    refreshed_service = RetrievalService(
        chunks,
        embedding_provider=current_service.embedding_provider,
        vector_store=vector_store,
        reranker=current_service.reranker,
        mode=current_service.mode,
        enable_reranking=current_service.enable_reranking,
        default_top_k=current_service.default_top_k,
        max_evidence_tokens=current_service.max_evidence_tokens,
        rrf_k=current_service.rrf_k,
    )
    request.app.state.retrieval_service = refreshed_service
    return len(refreshed_service.chunks)


def _source_repository(request: Request) -> SourceDocumentRepository:
    repository = getattr(request.app.state, "source_document_repository", None)
    if isinstance(repository, SourceDocumentRepository):
        return repository
    raise DependencyUnavailableError("source document repository is not available")


def _section_repository(request: Request) -> DocumentSectionRepository:
    repository = getattr(request.app.state, "document_section_repository", None)
    if isinstance(repository, DocumentSectionRepository):
        return repository
    raise DependencyUnavailableError("document section repository is not available")


def _chunk_repository(request: Request) -> DocumentChunkRepository:
    repository = getattr(request.app.state, "document_chunk_repository", None)
    if isinstance(repository, DocumentChunkRepository):
        return repository
    raise DependencyUnavailableError("document chunk repository is not available")


def _ingestion_job_repository(request: Request) -> IngestionJobRepository:
    repository = getattr(request.app.state, "ingestion_job_repository", None)
    if isinstance(repository, IngestionJobRepository):
        return repository
    raise DependencyUnavailableError("ingestion job repository is not available")


def _source_audit_repository(request: Request) -> SourceAuditEventRepository:
    repository = getattr(request.app.state, "source_audit_event_repository", None)
    if isinstance(repository, SourceAuditEventRepository):
        return repository
    raise DependencyUnavailableError("source audit event repository is not available")


def _save_source_audit_event(
    request: Request,
    *,
    action: SourceAuditAction,
    status_value: SourceAuditStatus,
    source: DocumentSource | None = None,
    job: IngestionJob | None = None,
    source_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    _source_audit_repository(request).save(
        SourceAuditEvent(
            event_id=f"sev_{uuid4().hex}",
            action=action,
            status=status_value,
            request_id=getattr(request.state, "request_id", f"req_{uuid4().hex}"),
            source_id=source.source_id if source is not None else source_id,
            source_checksum=source.checksum if source is not None else None,
            corpus_id=_event_corpus_id(source, job),
            corpus_version=_event_corpus_version(source, job),
            job_id=job.job_id if job is not None else None,
            details=details or {},
        )
    )


def _event_corpus_id(source: DocumentSource | None, job: IngestionJob | None) -> str | None:
    if source is not None:
        return source.corpus_id
    if job is not None:
        return job.corpus_id
    return None


def _event_corpus_version(
    source: DocumentSource | None,
    job: IngestionJob | None,
) -> str | None:
    if source is not None:
        return source.version
    if job is not None:
        return job.corpus_version
    return None


def _job_payload(job: IngestionJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "corpus_id": job.corpus_id,
        "corpus_name": job.corpus_name,
        "corpus_version": job.corpus_version,
        "input_type": job.input_type,
        "input_uri": job.input_uri,
        "status": job.status,
        "started_at": job.started_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at is not None else None,
        "report": job.report,
        "error": job.error,
    }


def _source_payload(
    source: DocumentSource,
    *,
    section_count: int,
    chunk_count: int,
) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "corpus_id": source.corpus_id,
        "corpus_name": source.corpus_name,
        "corpus_version": source.version,
        "title": source.title,
        "source_uri": source.url,
        "raw_storage_uri": source.raw_storage_uri,
        "checksum": source.checksum,
        "document_type": source.document_type,
        "publication_date": _date_payload(source.publication_date),
        "effective_date": _date_payload(source.effective_date),
        "ingested_at": source.ingested_at.isoformat(),
        "metadata": source.metadata,
        "section_count": section_count,
        "chunk_count": chunk_count,
    }


def _section_payload(section: DocumentSection) -> dict[str, Any]:
    return {
        "section_id": section.section_id,
        "source_id": section.source_id,
        "corpus_id": section.corpus_id,
        "corpus_version": section.corpus_version,
        "citation_label": section.citation_label,
        "title": section.title,
        "heading_path": section.heading_path,
        "text": section.text,
        "source_uri": section.url,
        "effective_date": _date_payload(section.effective_date),
        "page_number": section.page_number,
        "start_char": section.start_char,
        "end_char": section.end_char,
        "metadata": section.metadata,
    }


def _chunk_payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "section_id": chunk.section_id,
        "source_id": chunk.source_id,
        "corpus_id": chunk.corpus_id,
        "corpus_version": chunk.corpus_version,
        "citation_label": chunk.citation_label,
        "title": chunk.title,
        "heading_path": chunk.heading_path,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "chunk_index": chunk.chunk_index,
        "section_chunk_count": chunk.section_chunk_count,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "page_number": chunk.page_number,
        "source_checksum": chunk.source_checksum,
        "source_uri": chunk.url,
        "metadata": chunk.metadata,
    }


def _date_payload(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _utcnow() -> datetime:
    return datetime.now(UTC)
