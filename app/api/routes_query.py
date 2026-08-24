from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.costing import estimate_openai_query_cost
from app.core.errors import DependencyUnavailableError, RegLensError
from app.domain.ids import make_chat_session_id, make_chat_turn_id
from app.domain.models import (
    Answer,
    ChatSession,
    ChatTurn,
    Citation,
    Evidence,
    QueryAudit,
    QueryEvidence,
    RetrievalCandidate,
    RetrievalDiagnostics,
)
from app.generation.service import GenerationService
from app.generation.warnings import warning_details
from app.persistence.repositories import (
    AuditConflictError,
    ChatSessionRepository,
    QueryAuditRepository,
)
from app.retrieval.service import RetrievalResult, RetrievalService

router = APIRouter(tags=["query"])


class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=1)
    corpus_id: str | None = None
    corpus_version: str | None = None
    source_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class QueryRequest(RetrieveRequest):
    pass


class ChatRequest(QueryRequest):
    session_id: str | None = Field(default=None, min_length=1)
    stream: bool = False


@router.get("/chat/sessions")
def list_chat_sessions(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    repository = _chat_repository(request)
    sessions = list(repository.list_sessions(limit=limit))
    return {
        "sessions": [_chat_session_payload(session) for session in sessions],
        "count": len(sessions),
        "limit": limit,
    }


@router.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: str, request: Request) -> dict[str, Any]:
    repository = _chat_repository(request)
    session = _get_chat_session_or_404(repository, session_id)
    turns = list(repository.list_turns(session.session_id))
    return {
        "session": _chat_session_payload(session),
        "turns": [_chat_turn_payload(turn) for turn in turns],
    }


@router.get("/chat/sessions/{session_id}/export", response_model=None)
def export_chat_session(
    session_id: str,
    request: Request,
    export_format: Literal["json", "markdown"] = Query(default="json", alias="format"),
) -> Any:
    repository = _chat_repository(request)
    session = _get_chat_session_or_404(repository, session_id)
    turns = list(repository.list_turns(session.session_id))
    export = _chat_session_export_payload(session, turns)
    if export_format == "markdown":
        return PlainTextResponse(
            _chat_session_export_markdown(export),
            media_type="text/markdown",
        )
    return {"export": export}


@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str, request: Request) -> dict[str, Any]:
    repository = _chat_repository(request)
    deleted = repository.delete_session(session_id)
    if not deleted:
        raise RegLensError(
            "chat session was not found",
            code="chat_session_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id},
        )
    return {"session_id": session_id, "deleted": True}


@router.post("/retrieve")
def retrieve(payload: RetrieveRequest, request: Request) -> dict[str, Any]:
    _validate_question_length(payload.question, request)
    service = _retrieval_service(request)

    try:
        result = service.retrieve(
            payload.question,
            corpus_id=payload.corpus_id,
            corpus_version=payload.corpus_version,
            source_id=payload.source_id,
            top_k=payload.top_k,
        )
    except ValueError as exc:
        raise RegLensError(
            str(exc),
            code="invalid_retrieval_query",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    return _result_payload(result)


@router.post("/query")
def query(payload: QueryRequest, request: Request) -> dict[str, Any]:
    return _execute_query(payload, request)


@router.post("/chat", response_model=None)
def chat(payload: ChatRequest, request: Request) -> dict[str, Any] | StreamingResponse:
    chat_repository = _chat_repository(request)
    session = _chat_session_for_request(payload, chat_repository)
    response_payload = _execute_query(payload, request)
    response_payload = {
        **response_payload,
        "chat": _persist_chat_turn(
            payload=payload,
            response_payload=response_payload,
            session=session,
            repository=chat_repository,
        ),
    }
    if not payload.stream:
        return response_payload
    return StreamingResponse(
        _chat_events(response_payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _execute_query(payload: QueryRequest, request: Request) -> dict[str, Any]:
    started_at = perf_counter()
    _validate_question_length(payload.question, request)
    retrieval_service, generation_service, audit_repository = _query_dependencies(request)

    try:
        retrieval = retrieval_service.retrieve(
            payload.question,
            corpus_id=payload.corpus_id,
            corpus_version=payload.corpus_version,
            source_id=payload.source_id,
            top_k=payload.top_k,
            request_nonce=f"query_{uuid4().hex}",
        )
    except ValueError as exc:
        raise RegLensError(
            str(exc),
            code="invalid_retrieval_query",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    answer = generation_service.generate(payload.question, retrieval)
    cost_estimate = estimate_openai_query_cost(
        question=payload.question,
        evidence_snippets=[evidence.snippet for evidence in answer.evidence],
        answer_text=answer.answer,
        generation_model=answer.model_info.generation_model,
        embedding_model=answer.model_info.embedding_model,
    )
    query_evidence = generation_service.query_evidence_rows(
        query_id=answer.query_id,
        evidence=answer.evidence,
        candidates=retrieval.candidates,
        citations=answer.citations,
    )
    total_latency_ms = max(0, int(round((perf_counter() - started_at) * 1000)))
    audit = QueryAudit(
        query_id=answer.query_id,
        question=payload.question,
        normalized_question=retrieval.normalized_question,
        corpus_id=payload.corpus_id,
        corpus_version=payload.corpus_version,
        answer=answer.answer,
        confidence=answer.confidence,
        warnings=answer.warnings,
        generation_model=answer.model_info.generation_model,
        embedding_model=answer.model_info.embedding_model,
        reranker_model=answer.model_info.reranker_model,
        prompt_version=answer.model_info.prompt_version,
        retrieval_config=retrieval.diagnostics.retrieval_config,
        latency_ms=total_latency_ms,
        estimated_cost_usd=cost_estimate.estimated_cost_usd,
    )
    try:
        saved_audit = audit_repository.save(audit, query_evidence)
    except AuditConflictError as exc:
        raise RegLensError(
            "query audit record already exists",
            code="audit_conflict",
            status_code=status.HTTP_409_CONFLICT,
            details={"query_id": exc.query_id},
        ) from exc

    return _query_payload(
        answer=answer,
        retrieval=retrieval,
        audit=saved_audit,
        query_evidence=query_evidence,
        cost_estimate=cost_estimate.payload(),
    )


def _chat_events(payload: dict[str, Any]) -> Iterator[str]:
    yield _sse_event(
        "metadata",
        {
            "query_id": payload["query_id"],
            "confidence": payload["confidence"],
            "warnings": payload["warnings"],
            "warning_details": payload["warning_details"],
            "model_info": payload["model_info"],
            "chat": payload.get("chat"),
        },
    )
    yield _sse_event("answer_delta", {"text": payload["answer"]})
    yield _sse_event("citations", {"citations": payload["citations"]})
    yield _sse_event("evidence", {"evidence": payload["evidence"]})
    yield _sse_event("final", payload)
    yield _sse_event("done", {})


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _chat_session_for_request(
    payload: ChatRequest,
    repository: ChatSessionRepository,
) -> ChatSession:
    if payload.session_id is not None:
        session_id = payload.session_id.strip()
        if not session_id:
            raise RegLensError(
                "chat session id must be a non-empty string",
                code="invalid_chat_session",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        return _get_chat_session_or_404(repository, session_id)

    now = datetime.now(UTC)
    return ChatSession(
        session_id=make_chat_session_id(request_nonce=f"session_{uuid4().hex}"),
        title=_chat_title(payload.question),
        created_at=now,
        updated_at=now,
        metadata={"created_by": "chat_endpoint"},
    )


def _get_chat_session_or_404(
    repository: ChatSessionRepository,
    session_id: str,
) -> ChatSession:
    session = repository.get_session(session_id)
    if session is None:
        raise RegLensError(
            "chat session was not found",
            code="chat_session_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id},
        )
    return session


def _persist_chat_turn(
    *,
    payload: ChatRequest,
    response_payload: dict[str, Any],
    session: ChatSession,
    repository: ChatSessionRepository,
) -> dict[str, Any]:
    turn = ChatTurn(
        turn_id=make_chat_turn_id(
            session_id=session.session_id,
            query_id=response_payload["query_id"],
        ),
        session_id=session.session_id,
        query_id=response_payload["query_id"],
        turn_index=0,
        question=payload.question,
        answer=response_payload["answer"],
        confidence=response_payload["confidence"],
        metadata={
            "corpus_id": payload.corpus_id,
            "corpus_version": payload.corpus_version,
            "source_id": payload.source_id,
            "top_k": payload.top_k,
            "citation_count": len(response_payload["citations"]),
            "warning_count": len(response_payload["warnings"]),
            "stream": payload.stream,
        },
    )
    saved_session, saved_turn = repository.append_turn(session, turn)
    return {
        "session_id": saved_session.session_id,
        "turn_id": saved_turn.turn_id,
        "turn_index": saved_turn.turn_index,
        "query_id": saved_turn.query_id,
        "session_path": f"/chat/sessions/{saved_session.session_id}",
        "audit_path": f"/audit/queries/{saved_turn.query_id}",
    }


def _chat_title(question: str) -> str:
    normalized = " ".join(question.split())
    if len(normalized) <= 80:
        return normalized
    return f"{normalized[:77]}..."


def _validate_question_length(question: str, request: Request) -> None:
    settings = request.app.state.settings
    if len(question) <= settings.max_query_chars:
        return
    raise RegLensError(
        "question exceeds configured max_query_chars",
        code="query_too_long",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        details={
            "max_query_chars": settings.max_query_chars,
            "actual_chars": len(question),
        },
    )


def _retrieval_service(request: Request) -> RetrievalService:
    settings = request.app.state.settings
    service = getattr(request.app.state, "retrieval_service", None)
    if isinstance(service, RetrievalService):
        return service
    startup_error = getattr(request.app.state, "retrieval_startup_error", None)
    if isinstance(startup_error, DependencyUnavailableError):
        raise startup_error
    raise DependencyUnavailableError(
        "retrieval service is not available",
        details={"mode": settings.rag_mode},
    )


def _query_dependencies(
    request: Request,
) -> tuple[RetrievalService, GenerationService, QueryAuditRepository]:
    settings = request.app.state.settings
    retrieval_service = getattr(request.app.state, "retrieval_service", None)
    generation_service = getattr(request.app.state, "generation_service", None)
    dependency_errors = _query_dependency_errors(
        request,
        retrieval_service=retrieval_service,
        generation_service=generation_service,
    )
    if dependency_errors:
        raise DependencyUnavailableError(
            "required query dependencies are unavailable",
            details={
                "mode": settings.rag_mode,
                "dependencies": dependency_errors,
            },
        )
    if not isinstance(retrieval_service, RetrievalService):
        raise DependencyUnavailableError(
            "retrieval service is not available",
            details={"mode": settings.rag_mode},
        )
    if not isinstance(generation_service, GenerationService):
        raise DependencyUnavailableError(
            "generation service is not available",
            details={"mode": settings.rag_mode},
        )
    return retrieval_service, generation_service, _audit_repository(request)


def _query_dependency_errors(
    request: Request,
    *,
    retrieval_service: object | None,
    generation_service: object | None,
) -> list[dict[str, Any]]:
    provider_errors: list[dict[str, Any]] = []
    for name, attribute in (
        ("embedding_provider", "embedding_startup_error"),
        ("llm_provider", "generation_startup_error"),
        ("reranker", "reranker_startup_error"),
    ):
        startup_error = getattr(request.app.state, attribute, None)
        if isinstance(startup_error, DependencyUnavailableError):
            provider_errors.append(_dependency_error_payload(name, startup_error))

    if not isinstance(retrieval_service, RetrievalService):
        retrieval_error = getattr(request.app.state, "retrieval_startup_error", None)
        if isinstance(retrieval_error, DependencyUnavailableError):
            if not _already_reported(provider_errors, retrieval_error):
                provider_errors.append(_dependency_error_payload("retrieval", retrieval_error))
        elif not provider_errors:
            provider_errors.append(
                {
                    "name": "retrieval",
                    "message": "retrieval service is not available",
                    "details": {"mode": request.app.state.settings.rag_mode},
                }
            )

    if not isinstance(generation_service, GenerationService):
        generation_error = getattr(request.app.state, "generation_startup_error", None)
        if isinstance(generation_error, DependencyUnavailableError):
            if not _already_reported(provider_errors, generation_error):
                provider_errors.append(_dependency_error_payload("llm_provider", generation_error))
        elif not any(error["name"] == "llm_provider" for error in provider_errors):
            provider_errors.append(
                {
                    "name": "llm_provider",
                    "message": "generation service is not available",
                    "details": {"mode": request.app.state.settings.rag_mode},
                }
            )

    return provider_errors


def _dependency_error_payload(
    name: str,
    error: DependencyUnavailableError,
) -> dict[str, Any]:
    return {
        "name": name,
        "message": error.message,
        "details": error.details,
    }


def _already_reported(
    errors: list[dict[str, Any]],
    error: DependencyUnavailableError,
) -> bool:
    return any(item.get("details") == error.details for item in errors)


def _generation_service(request: Request) -> GenerationService:
    settings = request.app.state.settings
    service = getattr(request.app.state, "generation_service", None)
    if isinstance(service, GenerationService):
        return service
    startup_error = getattr(request.app.state, "generation_startup_error", None)
    if isinstance(startup_error, DependencyUnavailableError):
        raise startup_error
    raise DependencyUnavailableError(
        "generation service is not available",
        details={"mode": settings.rag_mode},
    )


def _audit_repository(request: Request) -> QueryAuditRepository:
    repository = getattr(request.app.state, "query_audit_repository", None)
    if isinstance(repository, QueryAuditRepository):
        return repository
    raise DependencyUnavailableError("query audit repository is not available")


def _chat_repository(request: Request) -> ChatSessionRepository:
    repository = getattr(request.app.state, "chat_session_repository", None)
    if isinstance(repository, ChatSessionRepository):
        return repository
    raise DependencyUnavailableError("chat session repository is not available")


def _result_payload(result: RetrievalResult) -> dict[str, Any]:
    candidates_by_chunk_id = {
        candidate.chunk.chunk_id: candidate for candidate in result.candidates
    }
    return {
        "query_id": result.query_id,
        "normalized_question": result.normalized_question,
        "evidence": [
            _evidence_payload(evidence, candidates_by_chunk_id[evidence.chunk_id])
            for evidence in result.evidence
        ],
        "diagnostics": _diagnostics_payload(result.diagnostics),
    }


def _query_payload(
    *,
    answer: Answer,
    retrieval: RetrievalResult,
    audit: QueryAudit,
    query_evidence: list[QueryEvidence],
    cost_estimate: dict[str, object],
) -> dict[str, Any]:
    candidates_by_chunk_id = {
        candidate.chunk.chunk_id: candidate for candidate in retrieval.candidates
    }
    query_evidence_by_id = {item.evidence_id: item for item in query_evidence}
    return {
        "query_id": answer.query_id,
        "normalized_question": retrieval.normalized_question,
        "answer": answer.answer,
        "confidence": answer.confidence,
        "warnings": answer.warnings,
        "warning_details": warning_details(answer.warnings),
        "citations": [_citation_payload(citation) for citation in answer.citations],
        "evidence": [
            _evidence_payload(
                evidence,
                candidates_by_chunk_id[evidence.chunk_id],
                query_evidence_by_id.get(evidence.evidence_id),
            )
            for evidence in answer.evidence
        ],
        "diagnostics": {
            **_diagnostics_payload(answer.retrieval_diagnostics),
            "generation": {
                "mode": answer.model_info.mode,
                "generation_model": answer.model_info.generation_model,
                "prompt_version": answer.model_info.prompt_version,
                "citation_count": len(answer.citations),
            },
            "audit": {
                "record_hash": audit.record_hash,
                "payload_hash": audit.payload_hash,
                "previous_record_hash": audit.previous_record_hash,
                "chain_index": audit.chain_index,
                "evidence_digest": audit.evidence_digest,
                "evidence_count": audit.evidence_count,
                "evidence_rows": len(query_evidence),
            },
            "cost_estimate": cost_estimate,
        },
        "model_info": {
            "mode": answer.model_info.mode,
            "generation_model": answer.model_info.generation_model,
            "embedding_model": answer.model_info.embedding_model,
            "reranker_model": answer.model_info.reranker_model,
            "prompt_version": answer.model_info.prompt_version,
        },
    }


def _evidence_payload(
    evidence: Evidence,
    candidate: RetrievalCandidate,
    query_evidence: QueryEvidence | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "evidence_id": evidence.evidence_id,
        "chunk_id": evidence.chunk_id,
        "citation_label": evidence.citation_label,
        "title": evidence.title,
        "snippet": evidence.snippet,
        "score": evidence.score,
        "url": evidence.url,
        "source_span": evidence.source_span,
        "rank": candidate.final_rank,
        "scores": {
            "dense_rank": candidate.dense_rank,
            "dense_score": candidate.dense_score,
            "keyword_rank": candidate.keyword_rank,
            "keyword_score": candidate.keyword_score,
            "fusion_score": candidate.fusion_score,
            "rerank_score": candidate.rerank_score,
        },
    }
    if query_evidence is not None:
        payload["quoted_text"] = query_evidence.quoted_text
        payload["quote_hash"] = query_evidence.quote_hash
        payload["verification_status"] = query_evidence.verification_status
    return payload


def _citation_payload(citation: Citation) -> dict[str, Any]:
    return {
        "citation_id": citation.citation_id,
        "citation_label": citation.citation_label,
        "chunk_id": citation.chunk_id,
        "source_id": citation.source_id,
        "supports_claim": citation.supports_claim,
        "url": citation.url,
        "quoted_text": citation.quoted_text,
        "source_span": citation.source_span,
        "verification_status": citation.verification_status,
    }


def _diagnostics_payload(diagnostics: RetrievalDiagnostics) -> dict[str, Any]:
    return {
        "total_candidates": diagnostics.total_candidates,
        "returned_evidence": diagnostics.returned_evidence,
        "dense_count": diagnostics.dense_count,
        "keyword_count": diagnostics.keyword_count,
        "reranked_count": diagnostics.reranked_count,
        "latency_ms": diagnostics.latency_ms,
        "filters": diagnostics.filters,
        "retrieval_config": diagnostics.retrieval_config,
    }


def _chat_session_payload(session: ChatSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "metadata": session.metadata,
        "turn_count": session.turn_count,
        "session_path": f"/chat/sessions/{session.session_id}",
    }


def _chat_turn_payload(turn: ChatTurn) -> dict[str, Any]:
    return {
        "turn_id": turn.turn_id,
        "session_id": turn.session_id,
        "query_id": turn.query_id,
        "turn_index": turn.turn_index,
        "question": turn.question,
        "answer": turn.answer,
        "confidence": turn.confidence,
        "created_at": turn.created_at.isoformat(),
        "metadata": turn.metadata,
        "audit_path": f"/audit/queries/{turn.query_id}",
    }


def _chat_session_export_payload(
    session: ChatSession,
    turns: list[ChatTurn],
) -> dict[str, Any]:
    return {
        "export_type": "reglens.chat_session.v1",
        "session": _chat_session_payload(session),
        "turn_count": len(turns),
        "turns": [_chat_turn_payload(turn) for turn in turns],
    }


def _chat_session_export_markdown(export: dict[str, Any]) -> str:
    session = export["session"]
    turns = export["turns"]
    lines = [
        "# RegLens Chat Session Export",
        "",
        f"Session ID: `{session['session_id']}`",
        f"Title: {session['title']}",
        f"Created at: {session['created_at']}",
        f"Updated at: {session['updated_at']}",
        f"Turn count: {export['turn_count']}",
        "",
    ]
    if not turns:
        lines.append("No turns were persisted.")
    for turn in turns:
        lines.extend(
            [
                f"## Turn {turn['turn_index'] + 1}",
                "",
                f"Turn ID: `{turn['turn_id']}`",
                f"Query ID: `{turn['query_id']}`",
                f"Audit: `{turn['audit_path']}`",
                f"Confidence: {turn['confidence']}",
                "",
                f"Question: {turn['question']}",
                "",
                "Answer:",
                "",
                str(turn["answer"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
