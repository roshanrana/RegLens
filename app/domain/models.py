"""Domain models for the RegLens fake-mode vertical slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

Confidence = Literal["high", "medium", "low", "insufficient_evidence"]
VerificationStatus = Literal["verified", "unverified", "not_required"]
IngestionStatus = Literal["pending", "running", "completed", "failed", "skipped"]
SourceAuditAction = Literal["ingest", "delete"]
SourceAuditStatus = Literal["completed", "failed"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class DocumentSource:
    source_id: str
    corpus_id: str
    corpus_name: str
    version: str
    title: str
    checksum: str
    url: str | None = None
    raw_storage_uri: str | None = None
    retrieved_at: datetime | None = None
    document_type: str | None = None
    publication_date: date | str | None = None
    effective_date: date | str | None = None
    ingested_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.corpus_id, "corpus_id")
        _require_non_empty(self.corpus_name, "corpus_name")
        _require_non_empty(self.version, "version")
        _require_non_empty(self.title, "title")
        _require_non_empty(self.checksum, "checksum")
        object.__setattr__(self, "metadata", _dict_copy(self.metadata, "metadata"))


@dataclass(frozen=True)
class DocumentSection:
    section_id: str
    source_id: str
    corpus_id: str
    citation_label: str
    title: str
    heading_path: list[str]
    text: str
    corpus_version: str | None = None
    url: str | None = None
    effective_date: date | str | None = None
    page_number: int | None = None
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.section_id, "section_id")
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.corpus_id, "corpus_id")
        if self.corpus_version is not None:
            _require_non_empty(self.corpus_version, "corpus_version")
        _require_non_empty(self.citation_label, "citation_label")
        _require_non_empty(self.title, "title")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        _validate_optional_non_negative(self.page_number, "page_number")
        _validate_span(self.start_char, self.end_char)
        object.__setattr__(self, "heading_path", _string_list(self.heading_path, "heading_path"))
        object.__setattr__(self, "metadata", _dict_copy(self.metadata, "metadata"))


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section_id: str
    source_id: str
    corpus_id: str
    corpus_version: str
    citation_label: str
    title: str
    heading_path: list[str]
    text: str
    token_count: int
    chunk_index: int
    section_chunk_count: int
    source_checksum: str
    char_start: int | None = None
    char_end: int | None = None
    page_number: int | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.chunk_id, "chunk_id")
        _require_non_empty(self.section_id, "section_id")
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.corpus_id, "corpus_id")
        _require_non_empty(self.corpus_version, "corpus_version")
        _require_non_empty(self.citation_label, "citation_label")
        _require_non_empty(self.title, "title")
        _require_non_empty(self.text, "text")
        if not isinstance(self.source_checksum, str):
            raise TypeError("source_checksum must be a string")
        _validate_non_negative(self.token_count, "token_count")
        _validate_non_negative(self.chunk_index, "chunk_index")
        _validate_non_negative(self.section_chunk_count, "section_chunk_count")
        if self.section_chunk_count > 0 and self.chunk_index >= self.section_chunk_count:
            raise ValueError("chunk_index must be less than section_chunk_count")
        _validate_optional_non_negative(self.page_number, "page_number")
        _validate_span(self.char_start, self.char_end)
        object.__setattr__(self, "heading_path", _string_list(self.heading_path, "heading_path"))
        object.__setattr__(self, "metadata", _dict_copy(self.metadata, "metadata"))


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk: Chunk
    fusion_score: float
    dense_rank: int | None = None
    dense_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None
    rerank_score: float | None = None
    final_rank: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_positive_rank(self.dense_rank, "dense_rank")
        _validate_optional_positive_rank(self.keyword_rank, "keyword_rank")
        _validate_optional_positive_rank(self.final_rank, "final_rank")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    chunk_id: str
    citation_label: str
    title: str
    snippet: str
    score: float
    url: str | None = None
    source_span: dict[str, int] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.evidence_id, "evidence_id")
        _require_non_empty(self.chunk_id, "chunk_id")
        _require_non_empty(self.citation_label, "citation_label")
        _require_non_empty(self.title, "title")
        _require_non_empty(self.snippet, "snippet")
        object.__setattr__(self, "source_span", _span_dict_copy(self.source_span))


@dataclass(frozen=True)
class Citation:
    citation_id: str
    citation_label: str
    chunk_id: str
    source_id: str
    supports_claim: str
    url: str | None = None
    quoted_text: str | None = None
    source_span: dict[str, int] | None = None
    verification_status: VerificationStatus = "not_required"

    def __post_init__(self) -> None:
        _require_non_empty(self.citation_id, "citation_id")
        _require_non_empty(self.citation_label, "citation_label")
        _require_non_empty(self.chunk_id, "chunk_id")
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.supports_claim, "supports_claim")
        _validate_literal(
            self.verification_status,
            {"verified", "unverified", "not_required"},
            "verification_status",
        )
        object.__setattr__(self, "source_span", _span_dict_copy(self.source_span))


@dataclass(frozen=True)
class RetrievalDiagnostics:
    total_candidates: int = 0
    returned_evidence: int = 0
    dense_count: int = 0
    keyword_count: int = 0
    reranked_count: int = 0
    latency_ms: int | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    retrieval_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_negative(self.total_candidates, "total_candidates")
        _validate_non_negative(self.returned_evidence, "returned_evidence")
        _validate_non_negative(self.dense_count, "dense_count")
        _validate_non_negative(self.keyword_count, "keyword_count")
        _validate_non_negative(self.reranked_count, "reranked_count")
        _validate_optional_non_negative(self.latency_ms, "latency_ms")
        object.__setattr__(self, "filters", _dict_copy(self.filters, "filters"))
        object.__setattr__(
            self,
            "retrieval_config",
            _dict_copy(self.retrieval_config, "retrieval_config"),
        )


@dataclass(frozen=True)
class ModelInfo:
    generation_model: str | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None
    prompt_version: str | None = None
    mode: str = "mock"


@dataclass(frozen=True)
class Answer:
    query_id: str
    answer: str
    citations: list[Citation]
    evidence: list[Evidence]
    confidence: Confidence
    warnings: list[str]
    retrieval_diagnostics: RetrievalDiagnostics
    model_info: ModelInfo
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        _require_non_empty(self.query_id, "query_id")
        _require_non_empty(self.answer, "answer")
        _validate_literal(
            self.confidence,
            {"high", "medium", "low", "insufficient_evidence"},
            "confidence",
        )
        object.__setattr__(self, "citations", list(self.citations))
        object.__setattr__(self, "evidence", list(self.evidence))
        object.__setattr__(self, "warnings", _string_list(self.warnings, "warnings"))


@dataclass(frozen=True)
class AuditHash:
    query_id: str
    payload_hash: str
    previous_record_hash: str | None
    record_hash: str
    chain_index: int
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        _require_non_empty(self.query_id, "query_id")
        _require_non_empty(self.payload_hash, "payload_hash")
        _require_non_empty(self.record_hash, "record_hash")
        _validate_non_negative(self.chain_index, "chain_index")


@dataclass(frozen=True)
class QueryAudit:
    query_id: str
    question: str
    normalized_question: str
    answer: str
    confidence: Confidence
    corpus_id: str | None = None
    corpus_version: str | None = None
    warnings: list[str] = field(default_factory=list)
    generation_model: str | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None
    prompt_version: str | None = None
    retrieval_config: dict[str, Any] = field(default_factory=dict)
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    evidence_digest: str | None = None
    evidence_count: int = 0
    payload_hash: str | None = None
    previous_record_hash: str | None = None
    record_hash: str | None = None
    chain_index: int | None = None
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        _require_non_empty(self.query_id, "query_id")
        _require_non_empty(self.question, "question")
        _require_non_empty(self.normalized_question, "normalized_question")
        _validate_literal(
            self.confidence,
            {"high", "medium", "low", "insufficient_evidence"},
            "confidence",
        )
        _validate_optional_non_negative(self.latency_ms, "latency_ms")
        _validate_non_negative(self.evidence_count, "evidence_count")
        _validate_optional_non_negative(self.chain_index, "chain_index")
        if self.evidence_digest is not None:
            _require_non_empty(self.evidence_digest, "evidence_digest")
        object.__setattr__(self, "warnings", _string_list(self.warnings, "warnings"))
        object.__setattr__(
            self,
            "retrieval_config",
            _dict_copy(self.retrieval_config, "retrieval_config"),
        )


@dataclass(frozen=True)
class QueryEvidence:
    query_id: str
    evidence_id: str
    chunk_id: str
    citation_label: str
    snippet: str
    dense_rank: int | None = None
    dense_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    final_rank: int | None = None
    quoted_text: str | None = None
    source_span: dict[str, int] | None = None
    quote_hash: str | None = None
    verification_status: VerificationStatus = "not_required"

    def __post_init__(self) -> None:
        _require_non_empty(self.query_id, "query_id")
        _require_non_empty(self.evidence_id, "evidence_id")
        _require_non_empty(self.chunk_id, "chunk_id")
        _require_non_empty(self.citation_label, "citation_label")
        _require_non_empty(self.snippet, "snippet")
        _validate_optional_positive_rank(self.dense_rank, "dense_rank")
        _validate_optional_positive_rank(self.keyword_rank, "keyword_rank")
        _validate_optional_positive_rank(self.final_rank, "final_rank")
        _validate_literal(
            self.verification_status,
            {"verified", "unverified", "not_required"},
            "verification_status",
        )
        object.__setattr__(self, "source_span", _span_dict_copy(self.source_span))


@dataclass(frozen=True)
class ChatSession:
    session_id: str
    title: str
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0

    def __post_init__(self) -> None:
        _require_non_empty(self.session_id, "session_id")
        _require_non_empty(self.title, "title")
        _validate_non_negative(self.turn_count, "turn_count")
        object.__setattr__(self, "metadata", _dict_copy(self.metadata, "metadata"))


@dataclass(frozen=True)
class ChatTurn:
    turn_id: str
    session_id: str
    query_id: str
    turn_index: int
    question: str
    answer: str
    confidence: Confidence
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.turn_id, "turn_id")
        _require_non_empty(self.session_id, "session_id")
        _require_non_empty(self.query_id, "query_id")
        _validate_non_negative(self.turn_index, "turn_index")
        _require_non_empty(self.question, "question")
        _require_non_empty(self.answer, "answer")
        _validate_literal(
            self.confidence,
            {"high", "medium", "low", "insufficient_evidence"},
            "confidence",
        )
        object.__setattr__(self, "metadata", _dict_copy(self.metadata, "metadata"))


@dataclass(frozen=True)
class IngestionJob:
    job_id: str
    corpus_id: str
    corpus_name: str
    corpus_version: str
    input_type: str
    input_uri: str
    status: IngestionStatus
    started_at: datetime = field(default_factory=_utcnow)
    finished_at: datetime | None = None
    report: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.job_id, "job_id")
        _require_non_empty(self.corpus_id, "corpus_id")
        _require_non_empty(self.corpus_name, "corpus_name")
        _require_non_empty(self.corpus_version, "corpus_version")
        _require_non_empty(self.input_type, "input_type")
        _require_non_empty(self.input_uri, "input_uri")
        _validate_literal(
            self.status,
            {"pending", "running", "completed", "failed", "skipped"},
            "status",
        )
        object.__setattr__(self, "report", _dict_copy(self.report, "report"))
        if self.error is not None:
            object.__setattr__(self, "error", _dict_copy(self.error, "error"))


@dataclass(frozen=True)
class SourceAuditEvent:
    event_id: str
    action: SourceAuditAction
    status: SourceAuditStatus
    request_id: str
    actor: str = "local-user"
    source_id: str | None = None
    source_checksum: str | None = None
    corpus_id: str | None = None
    corpus_version: str | None = None
    job_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        _require_non_empty(self.event_id, "event_id")
        _validate_literal(self.action, {"ingest", "delete"}, "action")
        _validate_literal(self.status, {"completed", "failed"}, "status")
        _require_non_empty(self.request_id, "request_id")
        _require_non_empty(self.actor, "actor")
        if self.source_id is not None:
            _require_non_empty(self.source_id, "source_id")
        if self.source_checksum is not None:
            _require_non_empty(self.source_checksum, "source_checksum")
        if self.corpus_id is not None:
            _require_non_empty(self.corpus_id, "corpus_id")
        if self.corpus_version is not None:
            _require_non_empty(self.corpus_version, "corpus_version")
        if self.job_id is not None:
            _require_non_empty(self.job_id, "job_id")
        object.__setattr__(self, "details", _dict_copy(self.details, "details"))


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_non_negative(value: int | float, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _validate_optional_non_negative(value: int | float | None, field_name: str) -> None:
    if value is not None:
        _validate_non_negative(value, field_name)


def _validate_optional_positive_rank(value: int | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive when provided")


def _validate_span(start: int | None, end: int | None) -> None:
    _validate_optional_non_negative(start, "start_char")
    _validate_optional_non_negative(end, "end_char")
    if start is not None and end is not None and start > end:
        raise ValueError("start_char must be less than or equal to end_char")


def _span_dict_copy(value: dict[str, int] | None) -> dict[str, int] | None:
    if value is None:
        return None
    copied = _dict_copy(value, "source_span")
    if set(copied) != {"start", "end"}:
        raise ValueError("source_span must contain exactly start and end")
    _validate_span(copied["start"], copied["end"])
    return copied


def _string_list(value: list[str], field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    return list(value)


def _dict_copy(value: dict[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a dictionary")
    return dict(value)


def _validate_literal(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {allowed_values}")
