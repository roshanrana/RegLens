from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.core.errors import DependencyUnavailableError, RegLensError
from app.domain.models import ChatSession, ChatTurn, QueryAudit, QueryEvidence, SourceAuditEvent
from app.generation.warnings import warning_details
from app.persistence.repositories import (
    AuditVerificationFailure,
    ChatSessionRepository,
    QueryAuditRepository,
    SourceAuditEventRepository,
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/queries")
def list_query_audits(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    repository = _audit_repository(request)
    chat_repository = _chat_repository(request)
    audits = list(repository.list(limit=limit))
    return {
        "queries": [
            _audit_summary_payload(
                audit,
                evidence_count=len(repository.list_evidence(audit.query_id)),
                chat=_chat_link_for_audit(chat_repository, audit.query_id),
            )
            for audit in audits
        ],
        "count": len(audits),
        "limit": limit,
    }


@router.get("/source-events")
def list_source_audit_events(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    source_id: str | None = Query(default=None),
    action: Literal["ingest", "delete"] | None = Query(default=None),
) -> dict[str, Any]:
    repository = _source_audit_repository(request)
    events = list(repository.list(limit=limit, source_id=source_id, action=action))
    return {
        "events": [_source_audit_event_payload(event) for event in events],
        "count": len(events),
        "limit": limit,
        "filters": {"source_id": source_id, "action": action},
    }


@router.get("/queries/{query_id}")
def get_query_audit(query_id: str, request: Request) -> dict[str, Any]:
    repository = _audit_repository(request)
    chat_repository = _chat_repository(request)
    audit = _get_audit_or_404(repository, query_id)

    evidence = list(repository.list_evidence(query_id))
    return {
        "audit": _audit_detail_payload(
            audit,
            chat=_chat_link_for_audit(chat_repository, audit.query_id),
        ),
        "evidence": [_query_evidence_payload(item) for item in evidence],
    }


@router.get("/queries/{query_id}/export", response_model=None)
def export_query_audit(
    query_id: str,
    request: Request,
    export_format: Annotated[Literal["json", "markdown"], Query(alias="format")] = "json",
) -> Any:
    repository = _audit_repository(request)
    chat_repository = _chat_repository(request)
    audit = _get_audit_or_404(repository, query_id)
    evidence = list(repository.list_evidence(query_id))
    export = _audit_export_payload(
        audit,
        evidence,
        chain_verified=repository.verify_chain(),
        chat=_chat_link_for_audit(chat_repository, audit.query_id),
    )
    if export_format == "markdown":
        return PlainTextResponse(
            _audit_export_markdown(export),
            media_type="text/markdown",
        )
    return {"export": export}


@router.get("/verify")
def verify_query_audit_chain(request: Request) -> dict[str, Any]:
    repository = _audit_repository(request)
    latest = next(iter(repository.list(limit=1)), None)
    verification = repository.verify_chain_detailed()
    return {
        "verified": verification.verified,
        "record_count": repository.count(),
        "latest_record_hash": latest.record_hash if latest is not None else None,
        "latest_chain_index": latest.chain_index if latest is not None else None,
        "failure_count": len(verification.failures),
        "failures": [_verification_failure_payload(item) for item in verification.failures],
    }


def _audit_repository(request: Request) -> QueryAuditRepository:
    repository = getattr(request.app.state, "query_audit_repository", None)
    if isinstance(repository, QueryAuditRepository):
        return repository
    raise DependencyUnavailableError("query audit repository is not available")


def _source_audit_repository(request: Request) -> SourceAuditEventRepository:
    repository = getattr(request.app.state, "source_audit_event_repository", None)
    if isinstance(repository, SourceAuditEventRepository):
        return repository
    raise DependencyUnavailableError("source audit event repository is not available")


def _chat_repository(request: Request) -> ChatSessionRepository:
    repository = getattr(request.app.state, "chat_session_repository", None)
    if isinstance(repository, ChatSessionRepository):
        return repository
    raise DependencyUnavailableError("chat session repository is not available")


def _get_audit_or_404(repository: QueryAuditRepository, query_id: str) -> QueryAudit:
    audit = repository.get(query_id)
    if audit is None:
        raise RegLensError(
            "query audit record was not found",
            code="audit_query_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"query_id": query_id},
        )
    return audit


def _audit_summary_payload(
    audit: QueryAudit,
    *,
    evidence_count: int,
    chat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "query_id": audit.query_id,
        "question": audit.question,
        "normalized_question": audit.normalized_question,
        "corpus_id": audit.corpus_id,
        "corpus_version": audit.corpus_version,
        "confidence": audit.confidence,
        "answer_preview": _preview(audit.answer),
        "warnings": audit.warnings,
        "warning_details": warning_details(audit.warnings),
        "generation_model": audit.generation_model,
        "embedding_model": audit.embedding_model,
        "reranker_model": audit.reranker_model,
        "prompt_version": audit.prompt_version,
        "latency_ms": audit.latency_ms,
        "estimated_cost_usd": audit.estimated_cost_usd,
        "created_at": audit.created_at.isoformat(),
        "evidence_digest": audit.evidence_digest,
        "audited_evidence_count": audit.evidence_count,
        "evidence_count": evidence_count,
        "audit": _audit_hash_payload(audit),
        "chat": chat,
    }


def _audit_detail_payload(
    audit: QueryAudit,
    *,
    chat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "query_id": audit.query_id,
        "question": audit.question,
        "normalized_question": audit.normalized_question,
        "corpus_id": audit.corpus_id,
        "corpus_version": audit.corpus_version,
        "answer": audit.answer,
        "confidence": audit.confidence,
        "warnings": audit.warnings,
        "warning_details": warning_details(audit.warnings),
        "generation_model": audit.generation_model,
        "embedding_model": audit.embedding_model,
        "reranker_model": audit.reranker_model,
        "prompt_version": audit.prompt_version,
        "retrieval_config": audit.retrieval_config,
        "latency_ms": audit.latency_ms,
        "estimated_cost_usd": audit.estimated_cost_usd,
        "created_at": audit.created_at.isoformat(),
        "evidence_digest": audit.evidence_digest,
        "evidence_count": audit.evidence_count,
        "audit": _audit_hash_payload(audit),
        "chat": chat,
    }


def _audit_hash_payload(audit: QueryAudit) -> dict[str, Any]:
    return {
        "payload_hash": audit.payload_hash,
        "record_hash": audit.record_hash,
        "previous_record_hash": audit.previous_record_hash,
        "chain_index": audit.chain_index,
        "evidence_digest": audit.evidence_digest,
        "evidence_count": audit.evidence_count,
    }


def _query_evidence_payload(evidence: QueryEvidence) -> dict[str, Any]:
    return {
        "query_id": evidence.query_id,
        "evidence_id": evidence.evidence_id,
        "chunk_id": evidence.chunk_id,
        "citation_label": evidence.citation_label,
        "snippet": evidence.snippet,
        "quoted_text": evidence.quoted_text,
        "source_span": evidence.source_span,
        "quote_hash": evidence.quote_hash,
        "verification_status": evidence.verification_status,
        "rank": evidence.final_rank,
        "scores": {
            "dense_rank": evidence.dense_rank,
            "dense_score": evidence.dense_score,
            "keyword_rank": evidence.keyword_rank,
            "keyword_score": evidence.keyword_score,
            "fusion_score": evidence.fusion_score,
            "rerank_score": evidence.rerank_score,
        },
    }


def _source_audit_event_payload(event: SourceAuditEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "action": event.action,
        "status": event.status,
        "request_id": event.request_id,
        "actor": event.actor,
        "source_id": event.source_id,
        "source_checksum": event.source_checksum,
        "corpus_id": event.corpus_id,
        "corpus_version": event.corpus_version,
        "job_id": event.job_id,
        "details": event.details,
        "created_at": event.created_at.isoformat(),
    }


def _audit_export_payload(
    audit: QueryAudit,
    evidence: list[QueryEvidence],
    *,
    chain_verified: bool,
    chat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "export_type": "reglens.query_audit.v1",
        "query": {
            "query_id": audit.query_id,
            "question": audit.question,
            "normalized_question": audit.normalized_question,
            "corpus_id": audit.corpus_id,
            "corpus_version": audit.corpus_version,
            "created_at": audit.created_at.isoformat(),
        },
        "answer": {
            "text": audit.answer,
            "confidence": audit.confidence,
            "warnings": audit.warnings,
            "warning_details": warning_details(audit.warnings),
        },
        "models": {
            "generation_model": audit.generation_model,
            "embedding_model": audit.embedding_model,
            "reranker_model": audit.reranker_model,
            "prompt_version": audit.prompt_version,
        },
        "retrieval_config": audit.retrieval_config,
        "latency_ms": audit.latency_ms,
        "estimated_cost_usd": audit.estimated_cost_usd,
        "audit_chain": _audit_hash_payload(audit),
        "chat": chat,
        "verification": {
            "chain_verified": chain_verified,
            "evidence_digest": audit.evidence_digest,
            "evidence_count": len(evidence),
            "verified_evidence_count": _count_verification(evidence, "verified"),
            "unverified_evidence_count": _count_verification(evidence, "unverified"),
        },
        "evidence": [_query_evidence_payload(item) for item in evidence],
    }


def _chat_link_for_audit(
    repository: ChatSessionRepository,
    query_id: str,
) -> dict[str, Any] | None:
    result = repository.get_turn_by_query_id(query_id)
    if result is None:
        return None
    session, turn = result
    return _chat_link_payload(session, turn)


def _chat_link_payload(session: ChatSession, turn: ChatTurn) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "session_title": session.title,
        "turn_id": turn.turn_id,
        "turn_index": turn.turn_index,
        "session_path": f"/chat/sessions/{session.session_id}",
        "audit_path": f"/audit/queries/{turn.query_id}",
    }


def _count_verification(evidence: list[QueryEvidence], status_value: str) -> int:
    return sum(1 for item in evidence if item.verification_status == status_value)


def _verification_failure_payload(item: AuditVerificationFailure) -> dict[str, Any]:
    return {
        "query_id": item.query_id,
        "chain_index": item.chain_index,
        "code": item.code,
        "message": item.message,
        "expected": item.expected,
        "actual": item.actual,
    }


def _audit_export_markdown(export: dict[str, Any]) -> str:
    query = export["query"]
    answer = export["answer"]
    audit_chain = export["audit_chain"]
    verification = export["verification"]
    models = export["models"]
    evidence = export["evidence"]
    chat = export.get("chat")

    lines = [
        "# RegLens Query Audit Export",
        "",
        f"Query ID: `{query['query_id']}`",
        f"Created at: {query['created_at']}",
        f"Question: {query['question']}",
        f"Corpus: {_optional(query['corpus_id'])} / {_optional(query['corpus_version'])}",
        f"Confidence: {answer['confidence']}",
        f"Warnings: {_list_text(answer['warnings'])}",
        "",
    ]
    if chat:
        lines.extend(
            [
                f"Chat session: `{chat['session_id']}`",
                f"Chat turn: `{chat['turn_id']}`",
                f"Turn index: {chat['turn_index']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Answer",
            "",
            str(answer["text"]),
            "",
            "## Verification",
            "",
            f"- Chain verified: {str(verification['chain_verified']).lower()}",
            f"- Evidence count: {verification['evidence_count']}",
            f"- Verified evidence: {verification['verified_evidence_count']}",
            f"- Unverified evidence: {verification['unverified_evidence_count']}",
            "",
            "## Audit Chain",
            "",
            f"- Payload hash: `{audit_chain['payload_hash']}`",
            f"- Record hash: `{audit_chain['record_hash']}`",
            f"- Previous record hash: `{_optional(audit_chain['previous_record_hash'])}`",
            f"- Chain index: {audit_chain['chain_index']}",
            "",
            "## Models",
            "",
            f"- Generation: {_optional(models['generation_model'])}",
            f"- Embedding: {_optional(models['embedding_model'])}",
            f"- Reranker: {_optional(models['reranker_model'])}",
            f"- Prompt version: {_optional(models['prompt_version'])}",
            "",
            "## Evidence",
            "",
        ]
    )

    if not evidence:
        lines.append("No evidence rows were persisted.")
    for item in evidence:
        lines.extend(_evidence_markdown(item))
    return "\n".join(lines).rstrip() + "\n"


def _evidence_markdown(item: dict[str, Any]) -> list[str]:
    scores = item["scores"]
    lines = [
        f"### {_optional(item['rank'])}. {item['citation_label']}",
        "",
        f"- Evidence ID: `{item['evidence_id']}`",
        f"- Chunk ID: `{item['chunk_id']}`",
        f"- Verification: {item['verification_status']}",
        (
            "- Scores: "
            f"dense={_optional(scores['dense_score'])}, "
            f"keyword={_optional(scores['keyword_score'])}, "
            f"fusion={_optional(scores['fusion_score'])}, "
            f"rerank={_optional(scores['rerank_score'])}"
        ),
    ]
    if item["quoted_text"]:
        lines.extend(["", f"Quoted text: {item['quoted_text']}"])
    lines.extend(["", f"Snippet: {item['snippet']}", ""])
    return lines


def _optional(value: object) -> str:
    if value is None:
        return "none"
    return str(value)


def _list_text(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)


def _preview(text: str, *, max_chars: int = 240) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."
