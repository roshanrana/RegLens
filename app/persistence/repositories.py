"""SQLite repositories for RegLens domain objects."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from threading import RLock
from typing import Any

from app.domain.ids import (
    canonical_json,
    make_audit_record_hash,
    make_content_hash,
    make_payload_hash,
    make_query_evidence_digest,
)
from app.domain.models import (
    ChatSession,
    ChatTurn,
    Chunk,
    DocumentSection,
    DocumentSource,
    IngestionJob,
    QueryAudit,
    QueryEvidence,
    SourceAuditEvent,
)
from app.persistence.db import transaction


@dataclass(frozen=True)
class AuditVerificationFailure:
    query_id: str
    chain_index: int | None
    code: str
    message: str
    expected: str | int | None = None
    actual: str | int | None = None


@dataclass(frozen=True)
class AuditVerificationResult:
    verified: bool
    failures: list[AuditVerificationFailure]


class AuditConflictError(RuntimeError):
    def __init__(self, query_id: str) -> None:
        super().__init__(f"query audit record already exists: {query_id}")
        self.query_id = query_id


class SourceDocumentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def upsert(self, source: DocumentSource) -> None:
        with self._lock:
            with transaction(self.connection) as connection:
                connection.execute(
                    """
                    INSERT INTO source_documents (
                        source_id, corpus_id, corpus_name, corpus_version, title,
                        source_uri, raw_storage_uri, retrieved_at, checksum, document_type,
                        publication_date, effective_date, ingested_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        corpus_id = excluded.corpus_id,
                        corpus_name = excluded.corpus_name,
                        corpus_version = excluded.corpus_version,
                        title = excluded.title,
                        source_uri = excluded.source_uri,
                        raw_storage_uri = excluded.raw_storage_uri,
                        retrieved_at = excluded.retrieved_at,
                        checksum = excluded.checksum,
                        document_type = excluded.document_type,
                        publication_date = excluded.publication_date,
                        effective_date = excluded.effective_date,
                        ingested_at = excluded.ingested_at,
                        metadata_json = excluded.metadata_json
                    """,
                    _source_to_row(source),
                )

    def get(self, source_id: str) -> DocumentSource | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM source_documents WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        return _source_from_row(row) if row else None

    def list(
        self,
        *,
        corpus_id: str | None = None,
        corpus_version: str | None = None,
    ) -> list[DocumentSource]:
        clauses: list[str] = []
        params: list[str] = []
        if corpus_id is not None:
            clauses.append("corpus_id = ?")
            params.append(corpus_id)
        if corpus_version is not None:
            clauses.append("corpus_version = ?")
            params.append(corpus_version)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self.connection.execute(
                f"SELECT * FROM source_documents {where} ORDER BY corpus_id, corpus_version, title",
                params,
            ).fetchall()
        return [_source_from_row(row) for row in rows]

    def delete(self, source_id: str) -> None:
        with self._lock:
            with transaction(self.connection) as connection:
                connection.execute(
                    "DELETE FROM source_documents WHERE source_id = ?",
                    (source_id,),
                )


class DocumentSectionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def upsert(self, section: DocumentSection) -> None:
        self.upsert_many([section])

    def upsert_many(self, sections: list[DocumentSection]) -> None:
        with self._lock:
            with transaction(self.connection) as connection:
                connection.executemany(
                    """
                    INSERT INTO document_sections (
                        section_id, source_id, corpus_id, corpus_version, citation_label, title,
                        heading_path_json, content, source_uri, effective_date,
                        page_number, start_char, end_char, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(section_id) DO UPDATE SET
                        source_id = excluded.source_id,
                        corpus_id = excluded.corpus_id,
                        corpus_version = excluded.corpus_version,
                        citation_label = excluded.citation_label,
                        title = excluded.title,
                        heading_path_json = excluded.heading_path_json,
                        content = excluded.content,
                        source_uri = excluded.source_uri,
                        effective_date = excluded.effective_date,
                        page_number = excluded.page_number,
                        start_char = excluded.start_char,
                        end_char = excluded.end_char,
                        metadata_json = excluded.metadata_json
                    """,
                    [_section_to_row(section) for section in sections],
                )

    def get(self, section_id: str) -> DocumentSection | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM document_sections WHERE section_id = ?",
                (section_id,),
            ).fetchone()
        return _section_from_row(row) if row else None

    def list_by_source(self, source_id: str) -> list[DocumentSection]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM document_sections
                WHERE source_id = ?
                ORDER BY start_char, citation_label
                """,
                (source_id,),
            ).fetchall()
        return [_section_from_row(row) for row in rows]

    def list_by_corpus(
        self,
        corpus_id: str,
        *,
        corpus_version: str | None = None,
    ) -> list[DocumentSection]:
        if corpus_version is None:
            rows = self.connection.execute(
                """
                SELECT * FROM document_sections
                WHERE corpus_id = ?
                ORDER BY source_id, start_char, citation_label
                """,
                (corpus_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM document_sections
                WHERE corpus_id = ? AND corpus_version = ?
                ORDER BY source_id, start_char, citation_label
                """,
                (corpus_id, corpus_version),
            ).fetchall()
        return [_section_from_row(row) for row in rows]


class DocumentChunkRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def upsert(self, chunk: Chunk) -> None:
        self.upsert_many([chunk])

    def upsert_many(self, chunks: list[Chunk]) -> None:
        with self._lock:
            with transaction(self.connection) as connection:
                connection.executemany(
                    """
                    INSERT INTO document_chunks (
                        chunk_id, source_id, section_id, corpus_id, corpus_version,
                        chunk_index, section_chunk_count, content, citation_label,
                        section_title, heading_path_json, source_uri, page_number,
                        token_count, start_char, end_char, source_checksum,
                        content_hash, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        source_id = excluded.source_id,
                        section_id = excluded.section_id,
                        corpus_id = excluded.corpus_id,
                        corpus_version = excluded.corpus_version,
                        chunk_index = excluded.chunk_index,
                        section_chunk_count = excluded.section_chunk_count,
                        content = excluded.content,
                        citation_label = excluded.citation_label,
                        section_title = excluded.section_title,
                        heading_path_json = excluded.heading_path_json,
                        source_uri = excluded.source_uri,
                        page_number = excluded.page_number,
                        token_count = excluded.token_count,
                        start_char = excluded.start_char,
                        end_char = excluded.end_char,
                        source_checksum = excluded.source_checksum,
                        content_hash = excluded.content_hash,
                        metadata_json = excluded.metadata_json
                    """,
                    [_chunk_to_row(chunk) for chunk in chunks],
                )

    def get(self, chunk_id: str) -> Chunk | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM document_chunks WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
        return _chunk_from_row(row) if row else None

    def list_all(
        self,
        *,
        corpus_id: str | None = None,
        corpus_version: str | None = None,
    ) -> list[Chunk]:
        clauses: list[str] = []
        params: list[str] = []
        if corpus_id is not None:
            clauses.append("corpus_id = ?")
            params.append(corpus_id)
        if corpus_version is not None:
            clauses.append("corpus_version = ?")
            params.append(corpus_version)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self.connection.execute(
                f"""
                SELECT * FROM document_chunks
                {where}
                ORDER BY corpus_id, corpus_version, source_id, section_id, chunk_index
                """,
                params,
            ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def list_by_corpus(
        self,
        corpus_id: str,
        *,
        corpus_version: str | None = None,
    ) -> list[Chunk]:
        if corpus_version is None:
            with self._lock:
                rows = self.connection.execute(
                    """
                    SELECT * FROM document_chunks
                    WHERE corpus_id = ?
                    ORDER BY source_id, section_id, chunk_index
                    """,
                    (corpus_id,),
                ).fetchall()
        else:
            with self._lock:
                rows = self.connection.execute(
                    """
                    SELECT * FROM document_chunks
                    WHERE corpus_id = ? AND corpus_version = ?
                    ORDER BY source_id, section_id, chunk_index
                    """,
                    (corpus_id, corpus_version),
                ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def list_by_source(self, source_id: str) -> list[Chunk]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM document_chunks
                WHERE source_id = ?
                ORDER BY section_id, chunk_index
                """,
                (source_id,),
            ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def delete_by_corpus_version(self, corpus_id: str, corpus_version: str) -> int:
        with self._lock:
            with transaction(self.connection) as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE corpus_id = ? AND corpus_version = ?
                    """,
                    (corpus_id, corpus_version),
                )
        return cursor.rowcount


class QueryAuditRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def save(self, audit: QueryAudit, evidence: list[QueryEvidence] | None = None) -> QueryAudit:
        evidence_rows = list(evidence or [])
        with self._lock:
            self._raise_if_query_exists(audit.query_id)
            audit = self._with_evidence_integrity(audit, evidence_rows)
            audit = self._with_chain_fields(audit)
            with transaction(self.connection) as connection:
                try:
                    connection.execute(
                        """
                        INSERT INTO query_audits (
                            query_id, question, normalized_question, corpus_id,
                            corpus_version, answer, confidence, warnings_json,
                            generation_model, embedding_model, reranker_model,
                            prompt_version, retrieval_config_json, latency_ms,
                            estimated_cost_usd, evidence_digest, evidence_count,
                            payload_hash, previous_record_hash, record_hash,
                            chain_index, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        _query_audit_to_row(audit),
                    )
                except sqlite3.IntegrityError as exc:
                    raise AuditConflictError(audit.query_id) from exc
                connection.execute(
                    "DELETE FROM query_evidence WHERE query_id = ?",
                    (audit.query_id,),
                )
                connection.executemany(
                    """
                    INSERT INTO query_evidence (
                        query_id, evidence_id, chunk_id, citation_label, dense_rank,
                        dense_score, keyword_rank, keyword_score, fusion_score,
                        rerank_score, final_rank, snippet, quoted_text,
                        source_span_json, quote_hash, verification_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [_query_evidence_to_row(item) for item in evidence_rows],
                )
        return audit

    def get(self, query_id: str) -> QueryAudit | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM query_audits WHERE query_id = ?",
                (query_id,),
            ).fetchone()
        return _query_audit_from_row(row) if row else None

    def list(self, *, limit: int = 100) -> Sequence[QueryAudit]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM query_audits
                ORDER BY chain_index DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_query_audit_from_row(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count FROM query_audits"
            ).fetchone()
        return int(row["count"])

    def list_evidence(self, query_id: str) -> Sequence[QueryEvidence]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM query_evidence
                WHERE query_id = ?
                ORDER BY COALESCE(final_rank, 999999), evidence_id
                """,
                (query_id,),
            ).fetchall()
        return [_query_evidence_from_row(row) for row in rows]

    def verify_chain(self) -> bool:
        return self.verify_chain_detailed().verified

    def verify_chain_detailed(self) -> AuditVerificationResult:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM query_audits
                WHERE chain_index IS NOT NULL
                ORDER BY chain_index
                """
            ).fetchall()
        previous: str | None = None
        failures: list[AuditVerificationFailure] = []
        for index, row in enumerate(rows):
            query_id = row["query_id"]
            chain_index = row["chain_index"]
            if row["chain_index"] != index:
                failures.append(
                    AuditVerificationFailure(
                        query_id=query_id,
                        chain_index=chain_index,
                        code="chain_index_mismatch",
                        message="query audit chain index is not contiguous",
                        expected=index,
                        actual=chain_index,
                    )
                )
            if row["previous_record_hash"] != previous:
                failures.append(
                    AuditVerificationFailure(
                        query_id=query_id,
                        chain_index=chain_index,
                        code="previous_record_hash_mismatch",
                        message="query audit previous hash does not match prior record",
                        expected=previous,
                        actual=row["previous_record_hash"],
                    )
                )
            expected_payload_hash = make_payload_hash(_audit_payload_from_row(row))
            if row["payload_hash"] != expected_payload_hash:
                failures.append(
                    AuditVerificationFailure(
                        query_id=query_id,
                        chain_index=chain_index,
                        code="payload_hash_mismatch",
                        message="query audit payload hash does not match row content",
                        expected=expected_payload_hash,
                        actual=row["payload_hash"],
                    )
                )
            expected_record_hash = make_audit_record_hash(
                payload_hash=row["payload_hash"],
                previous_record_hash=previous,
                chain_index=row["chain_index"],
                created_at=_parse_datetime(row["created_at"]),
            )
            if row["record_hash"] != expected_record_hash:
                failures.append(
                    AuditVerificationFailure(
                        query_id=query_id,
                        chain_index=chain_index,
                        code="record_hash_mismatch",
                        message="query audit record hash does not match chain link fields",
                        expected=expected_record_hash,
                        actual=row["record_hash"],
                    )
                )
            evidence = list(self.list_evidence(query_id))
            actual_count = len(evidence)
            actual_digest = _query_evidence_digest(evidence)
            if row["evidence_count"] != actual_count:
                failures.append(
                    AuditVerificationFailure(
                        query_id=query_id,
                        chain_index=chain_index,
                        code="evidence_count_mismatch",
                        message="persisted query evidence count does not match audit payload",
                        expected=row["evidence_count"],
                        actual=actual_count,
                    )
                )
            if row["evidence_digest"] != actual_digest:
                failures.append(
                    AuditVerificationFailure(
                        query_id=query_id,
                        chain_index=chain_index,
                        code="evidence_digest_mismatch",
                        message="persisted query evidence digest does not match audit payload",
                        expected=row["evidence_digest"],
                        actual=actual_digest,
                    )
                )
            previous = row["record_hash"]
        return AuditVerificationResult(verified=not failures, failures=failures)

    def _raise_if_query_exists(self, query_id: str) -> None:
        row = self.connection.execute(
            "SELECT 1 FROM query_audits WHERE query_id = ? LIMIT 1",
            (query_id,),
        ).fetchone()
        if row is not None:
            raise AuditConflictError(query_id)

    def _with_evidence_integrity(
        self,
        audit: QueryAudit,
        evidence: Sequence[QueryEvidence],
    ) -> QueryAudit:
        return replace(
            audit,
            evidence_digest=_query_evidence_digest(evidence),
            evidence_count=len(evidence),
        )

    def _with_chain_fields(self, audit: QueryAudit) -> QueryAudit:
        expected_payload_hash = make_payload_hash(_audit_payload(audit))
        if (
            audit.payload_hash == expected_payload_hash
            and audit.record_hash
            and audit.chain_index is not None
        ):
            return audit
        latest = self.connection.execute(
            """
            SELECT record_hash, chain_index FROM query_audits
            WHERE chain_index IS NOT NULL
            ORDER BY chain_index DESC
            LIMIT 1
            """
        ).fetchone()
        previous_hash = latest["record_hash"] if latest else None
        chain_index = int(latest["chain_index"]) + 1 if latest else 0
        record_hash = make_audit_record_hash(
            payload_hash=expected_payload_hash,
            previous_record_hash=previous_hash,
            chain_index=chain_index,
            created_at=audit.created_at,
        )
        return replace(
            audit,
            payload_hash=expected_payload_hash,
            previous_record_hash=previous_hash,
            record_hash=record_hash,
            chain_index=chain_index,
        )


class ChatSessionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def get_session(self, session_id: str) -> ChatSession | None:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT s.*, COUNT(t.turn_id) AS turn_count
                FROM chat_sessions s
                LEFT JOIN chat_turns t ON t.session_id = s.session_id
                WHERE s.session_id = ?
                GROUP BY s.session_id
                """,
                (session_id,),
            ).fetchone()
        return _chat_session_from_row(row) if row else None

    def list_sessions(self, *, limit: int = 100) -> Sequence[ChatSession]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT s.*, COUNT(t.turn_id) AS turn_count
                FROM chat_sessions s
                LEFT JOIN chat_turns t ON t.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC, s.created_at DESC, s.session_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_chat_session_from_row(row) for row in rows]

    def list_turns(self, session_id: str) -> Sequence[ChatTurn]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM chat_turns
                WHERE session_id = ?
                ORDER BY turn_index, created_at, turn_id
                """,
                (session_id,),
            ).fetchall()
        return [_chat_turn_from_row(row) for row in rows]

    def get_turn_by_query_id(self, query_id: str) -> tuple[ChatSession, ChatTurn] | None:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT
                    s.session_id,
                    s.title,
                    s.created_at AS session_created_at,
                    s.updated_at AS session_updated_at,
                    s.metadata_json AS session_metadata_json,
                    (
                        SELECT COUNT(*)
                        FROM chat_turns turn_count
                        WHERE turn_count.session_id = s.session_id
                    ) AS turn_count,
                    t.turn_id,
                    t.query_id,
                    t.turn_index,
                    t.question,
                    t.answer,
                    t.confidence,
                    t.created_at AS turn_created_at,
                    t.metadata_json AS turn_metadata_json
                FROM chat_turns t
                JOIN chat_sessions s ON s.session_id = t.session_id
                WHERE t.query_id = ?
                """,
                (query_id,),
            ).fetchone()
        if row is None:
            return None
        session = ChatSession(
            session_id=row["session_id"],
            title=row["title"],
            created_at=_parse_datetime(row["session_created_at"]),
            updated_at=_parse_datetime(row["session_updated_at"]),
            metadata=_json_loads(row["session_metadata_json"]),
            turn_count=int(row["turn_count"]),
        )
        turn = ChatTurn(
            turn_id=row["turn_id"],
            session_id=row["session_id"],
            query_id=row["query_id"],
            turn_index=row["turn_index"],
            question=row["question"],
            answer=row["answer"],
            confidence=row["confidence"],
            created_at=_parse_datetime(row["turn_created_at"]),
            metadata=_json_loads(row["turn_metadata_json"]),
        )
        return session, turn

    def append_turn(self, session: ChatSession, turn: ChatTurn) -> tuple[ChatSession, ChatTurn]:
        with self._lock:
            with transaction(self.connection) as connection:
                existing_row = connection.execute(
                    "SELECT * FROM chat_sessions WHERE session_id = ?",
                    (session.session_id,),
                ).fetchone()
                stored_session = (
                    _chat_session_from_row(existing_row) if existing_row else session
                )
                next_index_row = connection.execute(
                    """
                    SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_index
                    FROM chat_turns
                    WHERE session_id = ?
                    """,
                    (session.session_id,),
                ).fetchone()
                next_index = int(next_index_row["next_index"])
                saved_turn = replace(turn, turn_index=next_index)
                saved_session = replace(
                    stored_session,
                    updated_at=saved_turn.created_at,
                    turn_count=next_index + 1,
                )
                connection.execute(
                    """
                    INSERT INTO chat_sessions (
                        session_id, title, created_at, updated_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        updated_at = excluded.updated_at
                    """,
                    _chat_session_to_row(saved_session),
                )
                connection.execute(
                    """
                    INSERT INTO chat_turns (
                        turn_id, session_id, query_id, turn_index, question,
                        answer, confidence, created_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _chat_turn_to_row(saved_turn),
                )
        return saved_session, saved_turn

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            with transaction(self.connection) as connection:
                cursor = connection.execute(
                    "DELETE FROM chat_sessions WHERE session_id = ?",
                    (session_id,),
                )
        return cursor.rowcount > 0


class IngestionJobRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def save(self, job: IngestionJob) -> None:
        with self._lock:
            with transaction(self.connection) as connection:
                connection.execute(
                    """
                    INSERT INTO ingestion_jobs (
                        job_id, corpus_id, corpus_name, corpus_version, input_type,
                        input_uri, status, started_at, finished_at, report_json, error_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        corpus_id = excluded.corpus_id,
                        corpus_name = excluded.corpus_name,
                        corpus_version = excluded.corpus_version,
                        input_type = excluded.input_type,
                        input_uri = excluded.input_uri,
                        status = excluded.status,
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at,
                        report_json = excluded.report_json,
                        error_json = excluded.error_json
                    """,
                    _ingestion_job_to_row(job),
                )

    def get(self, job_id: str) -> IngestionJob | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return _ingestion_job_from_row(row) if row else None


class SourceAuditEventRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._lock = RLock()

    def save(self, event: SourceAuditEvent) -> None:
        with self._lock:
            with transaction(self.connection) as connection:
                connection.execute(
                    """
                    INSERT INTO source_audit_events (
                        event_id, action, status, request_id, actor, source_id,
                        source_checksum, corpus_id, corpus_version, job_id,
                        details_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _source_audit_event_to_row(event),
                )

    def list(
        self,
        *,
        limit: int = 100,
        source_id: str | None = None,
        action: str | None = None,
    ) -> Sequence[SourceAuditEvent]:
        clauses: list[str] = []
        params: list[str | int] = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if action is not None:
            clauses.append("action = ?")
            params.append(action)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self.connection.execute(
                f"""
                SELECT * FROM source_audit_events
                {where}
                ORDER BY created_at DESC, event_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_source_audit_event_from_row(row) for row in rows]


def _source_to_row(source: DocumentSource) -> tuple[Any, ...]:
    return (
        source.source_id,
        source.corpus_id,
        source.corpus_name,
        source.version,
        source.title,
        source.url,
        source.raw_storage_uri,
        _datetime_to_text(source.retrieved_at),
        source.checksum,
        source.document_type,
        _date_to_text(source.publication_date),
        _date_to_text(source.effective_date),
        _datetime_to_text(source.ingested_at),
        _json_dumps(source.metadata),
    )


def _source_from_row(row: sqlite3.Row) -> DocumentSource:
    return DocumentSource(
        source_id=row["source_id"],
        corpus_id=row["corpus_id"],
        corpus_name=row["corpus_name"],
        version=row["corpus_version"],
        title=row["title"],
        url=row["source_uri"],
        raw_storage_uri=row["raw_storage_uri"],
        retrieved_at=_parse_datetime(row["retrieved_at"]) if row["retrieved_at"] else None,
        checksum=row["checksum"],
        document_type=row["document_type"],
        publication_date=_parse_date(row["publication_date"]),
        effective_date=_parse_date(row["effective_date"]),
        ingested_at=_parse_datetime(row["ingested_at"]),
        metadata=_json_loads(row["metadata_json"]),
    )


def _section_to_row(section: DocumentSection) -> tuple[Any, ...]:
    return (
        section.section_id,
        section.source_id,
        section.corpus_id,
        section.corpus_version,
        section.citation_label,
        section.title,
        _json_dumps(section.heading_path),
        section.text,
        section.url,
        _date_to_text(section.effective_date),
        section.page_number,
        section.start_char,
        section.end_char,
        _json_dumps(section.metadata),
    )


def _section_from_row(row: sqlite3.Row) -> DocumentSection:
    return DocumentSection(
        section_id=row["section_id"],
        source_id=row["source_id"],
        corpus_id=row["corpus_id"],
        corpus_version=row["corpus_version"],
        citation_label=row["citation_label"],
        title=row["title"],
        heading_path=_json_loads(row["heading_path_json"]),
        text=row["content"],
        url=row["source_uri"],
        effective_date=_parse_date(row["effective_date"]),
        page_number=row["page_number"],
        start_char=row["start_char"],
        end_char=row["end_char"],
        metadata=_json_loads(row["metadata_json"]),
    )


def _chunk_to_row(chunk: Chunk) -> tuple[Any, ...]:
    return (
        chunk.chunk_id,
        chunk.source_id,
        chunk.section_id,
        chunk.corpus_id,
        chunk.corpus_version,
        chunk.chunk_index,
        chunk.section_chunk_count,
        chunk.text,
        chunk.citation_label,
        chunk.title,
        _json_dumps(chunk.heading_path),
        chunk.url,
        chunk.page_number,
        chunk.token_count,
        chunk.char_start,
        chunk.char_end,
        chunk.source_checksum,
        make_content_hash(chunk.text),
        _json_dumps(chunk.metadata),
    )


def _chunk_from_row(row: sqlite3.Row) -> Chunk:
    return Chunk(
        chunk_id=row["chunk_id"],
        source_id=row["source_id"],
        section_id=row["section_id"],
        corpus_id=row["corpus_id"],
        corpus_version=row["corpus_version"],
        chunk_index=row["chunk_index"],
        section_chunk_count=row["section_chunk_count"],
        text=row["content"],
        citation_label=row["citation_label"],
        title=row["section_title"],
        heading_path=_json_loads(row["heading_path_json"]),
        url=row["source_uri"],
        page_number=row["page_number"],
        token_count=row["token_count"],
        char_start=row["start_char"],
        char_end=row["end_char"],
        source_checksum=row["source_checksum"],
        metadata=_json_loads(row["metadata_json"]),
    )


def _query_audit_to_row(audit: QueryAudit) -> tuple[Any, ...]:
    return (
        audit.query_id,
        audit.question,
        audit.normalized_question,
        audit.corpus_id,
        audit.corpus_version,
        audit.answer,
        audit.confidence,
        _json_dumps(audit.warnings),
        audit.generation_model,
        audit.embedding_model,
        audit.reranker_model,
        audit.prompt_version,
        _json_dumps(audit.retrieval_config),
        audit.latency_ms,
        audit.estimated_cost_usd,
        audit.evidence_digest,
        audit.evidence_count,
        audit.payload_hash,
        audit.previous_record_hash,
        audit.record_hash,
        audit.chain_index,
        _datetime_to_text(audit.created_at),
    )


def _query_audit_from_row(row: sqlite3.Row) -> QueryAudit:
    return QueryAudit(
        query_id=row["query_id"],
        question=row["question"],
        normalized_question=row["normalized_question"],
        corpus_id=row["corpus_id"],
        corpus_version=row["corpus_version"],
        answer=row["answer"],
        confidence=row["confidence"],
        warnings=_json_loads(row["warnings_json"]),
        generation_model=row["generation_model"],
        embedding_model=row["embedding_model"],
        reranker_model=row["reranker_model"],
        prompt_version=row["prompt_version"],
        retrieval_config=_json_loads(row["retrieval_config_json"]),
        latency_ms=row["latency_ms"],
        estimated_cost_usd=row["estimated_cost_usd"],
        evidence_digest=row["evidence_digest"],
        evidence_count=row["evidence_count"],
        payload_hash=row["payload_hash"],
        previous_record_hash=row["previous_record_hash"],
        record_hash=row["record_hash"],
        chain_index=row["chain_index"],
        created_at=_parse_datetime(row["created_at"]),
    )


def _query_evidence_to_row(evidence: QueryEvidence) -> tuple[Any, ...]:
    return (
        evidence.query_id,
        evidence.evidence_id,
        evidence.chunk_id,
        evidence.citation_label,
        evidence.dense_rank,
        evidence.dense_score,
        evidence.keyword_rank,
        evidence.keyword_score,
        evidence.fusion_score,
        evidence.rerank_score,
        evidence.final_rank,
        evidence.snippet,
        evidence.quoted_text,
        _json_dumps(evidence.source_span) if evidence.source_span is not None else None,
        evidence.quote_hash,
        evidence.verification_status,
    )


def _query_evidence_from_row(row: sqlite3.Row) -> QueryEvidence:
    return QueryEvidence(
        query_id=row["query_id"],
        evidence_id=row["evidence_id"],
        chunk_id=row["chunk_id"],
        citation_label=row["citation_label"],
        dense_rank=row["dense_rank"],
        dense_score=row["dense_score"],
        keyword_rank=row["keyword_rank"],
        keyword_score=row["keyword_score"],
        fusion_score=row["fusion_score"],
        rerank_score=row["rerank_score"],
        final_rank=row["final_rank"],
        snippet=row["snippet"],
        quoted_text=row["quoted_text"],
        source_span=_json_loads(row["source_span_json"]) if row["source_span_json"] else None,
        quote_hash=row["quote_hash"],
        verification_status=row["verification_status"],
    )


def _chat_session_to_row(session: ChatSession) -> tuple[Any, ...]:
    return (
        session.session_id,
        session.title,
        _datetime_to_text(session.created_at),
        _datetime_to_text(session.updated_at),
        _json_dumps(session.metadata),
    )


def _chat_session_from_row(row: sqlite3.Row) -> ChatSession:
    return ChatSession(
        session_id=row["session_id"],
        title=row["title"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        metadata=_json_loads(row["metadata_json"]),
        turn_count=int(row["turn_count"]) if "turn_count" in row.keys() else 0,
    )


def _chat_turn_to_row(turn: ChatTurn) -> tuple[Any, ...]:
    return (
        turn.turn_id,
        turn.session_id,
        turn.query_id,
        turn.turn_index,
        turn.question,
        turn.answer,
        turn.confidence,
        _datetime_to_text(turn.created_at),
        _json_dumps(turn.metadata),
    )


def _chat_turn_from_row(row: sqlite3.Row) -> ChatTurn:
    return ChatTurn(
        turn_id=row["turn_id"],
        session_id=row["session_id"],
        query_id=row["query_id"],
        turn_index=row["turn_index"],
        question=row["question"],
        answer=row["answer"],
        confidence=row["confidence"],
        created_at=_parse_datetime(row["created_at"]),
        metadata=_json_loads(row["metadata_json"]),
    )


def _ingestion_job_to_row(job: IngestionJob) -> tuple[Any, ...]:
    return (
        job.job_id,
        job.corpus_id,
        job.corpus_name,
        job.corpus_version,
        job.input_type,
        job.input_uri,
        job.status,
        _datetime_to_text(job.started_at),
        _datetime_to_text(job.finished_at),
        _json_dumps(job.report),
        _json_dumps(job.error) if job.error is not None else None,
    )


def _ingestion_job_from_row(row: sqlite3.Row) -> IngestionJob:
    return IngestionJob(
        job_id=row["job_id"],
        corpus_id=row["corpus_id"],
        corpus_name=row["corpus_name"],
        corpus_version=row["corpus_version"],
        input_type=row["input_type"],
        input_uri=row["input_uri"],
        status=row["status"],
        started_at=_parse_datetime(row["started_at"]),
        finished_at=_parse_datetime(row["finished_at"]) if row["finished_at"] else None,
        report=_json_loads(row["report_json"]),
        error=_json_loads(row["error_json"]) if row["error_json"] else None,
    )


def _source_audit_event_to_row(event: SourceAuditEvent) -> tuple[Any, ...]:
    return (
        event.event_id,
        event.action,
        event.status,
        event.request_id,
        event.actor,
        event.source_id,
        event.source_checksum,
        event.corpus_id,
        event.corpus_version,
        event.job_id,
        _json_dumps(event.details),
        _datetime_to_text(event.created_at),
    )


def _source_audit_event_from_row(row: sqlite3.Row) -> SourceAuditEvent:
    return SourceAuditEvent(
        event_id=row["event_id"],
        action=row["action"],
        status=row["status"],
        request_id=row["request_id"],
        actor=row["actor"],
        source_id=row["source_id"],
        source_checksum=row["source_checksum"],
        corpus_id=row["corpus_id"],
        corpus_version=row["corpus_version"],
        job_id=row["job_id"],
        details=_json_loads(row["details_json"]),
        created_at=_parse_datetime(row["created_at"]),
    )


def _audit_payload(audit: QueryAudit) -> dict[str, Any]:
    return {
        "query_id": audit.query_id,
        "question": audit.question,
        "normalized_question": audit.normalized_question,
        "corpus_id": audit.corpus_id,
        "corpus_version": audit.corpus_version,
        "answer": audit.answer,
        "confidence": audit.confidence,
        "warnings": audit.warnings,
        "generation_model": audit.generation_model,
        "embedding_model": audit.embedding_model,
        "reranker_model": audit.reranker_model,
        "prompt_version": audit.prompt_version,
        "retrieval_config": audit.retrieval_config,
        "latency_ms": audit.latency_ms,
        "estimated_cost_usd": audit.estimated_cost_usd,
        "evidence_digest": audit.evidence_digest,
        "evidence_count": audit.evidence_count,
        "created_at": audit.created_at,
    }


def _audit_payload_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "question": row["question"],
        "normalized_question": row["normalized_question"],
        "corpus_id": row["corpus_id"],
        "corpus_version": row["corpus_version"],
        "answer": row["answer"],
        "confidence": row["confidence"],
        "warnings": _json_loads(row["warnings_json"]),
        "generation_model": row["generation_model"],
        "embedding_model": row["embedding_model"],
        "reranker_model": row["reranker_model"],
        "prompt_version": row["prompt_version"],
        "retrieval_config": _json_loads(row["retrieval_config_json"]),
        "latency_ms": row["latency_ms"],
        "estimated_cost_usd": row["estimated_cost_usd"],
        "evidence_digest": row["evidence_digest"],
        "evidence_count": row["evidence_count"],
        "created_at": _parse_datetime(row["created_at"]),
    }


def _query_evidence_digest(evidence: Sequence[QueryEvidence]) -> str:
    return make_query_evidence_digest(
        [_query_evidence_digest_payload(item) for item in evidence]
    )


def _query_evidence_digest_payload(evidence: QueryEvidence) -> dict[str, Any]:
    return {
        "query_id": evidence.query_id,
        "evidence_id": evidence.evidence_id,
        "chunk_id": evidence.chunk_id,
        "citation_label": evidence.citation_label,
        "dense_rank": evidence.dense_rank,
        "dense_score": evidence.dense_score,
        "keyword_rank": evidence.keyword_rank,
        "keyword_score": evidence.keyword_score,
        "fusion_score": evidence.fusion_score,
        "rerank_score": evidence.rerank_score,
        "final_rank": evidence.final_rank,
        "snippet": evidence.snippet,
        "quoted_text": evidence.quoted_text,
        "source_span": evidence.source_span,
        "quote_hash": evidence.quote_hash,
        "verification_status": evidence.verification_status,
    }


def _json_dumps(value: Any) -> str:
    return canonical_json(value)


def _json_loads(value: str) -> Any:
    return json.loads(value)


def _datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _date_to_text(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None
