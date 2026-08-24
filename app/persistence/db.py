"""SQLite connection and schema management for RegLens."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

_TRANSACTION_LOCKS: dict[int, RLock] = {}
_TRANSACTION_LOCKS_GUARD = RLock()

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_documents (
    source_id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    corpus_name TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    title TEXT NOT NULL,
    source_uri TEXT,
    raw_storage_uri TEXT,
    retrieved_at TEXT,
    checksum TEXT NOT NULL,
    document_type TEXT,
    publication_date TEXT,
    effective_date TEXT,
    ingested_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_source_documents_corpus
    ON source_documents (corpus_id, corpus_version);

CREATE TABLE IF NOT EXISTS document_sections (
    section_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL,
    corpus_version TEXT,
    citation_label TEXT NOT NULL,
    title TEXT NOT NULL,
    heading_path_json TEXT NOT NULL,
    content TEXT NOT NULL,
    source_uri TEXT,
    effective_date TEXT,
    page_number INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(source_id) REFERENCES source_documents(source_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_sections_source
    ON document_sections (source_id);

CREATE INDEX IF NOT EXISTS idx_document_sections_citation
    ON document_sections (corpus_id, corpus_version, citation_label);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    section_chunk_count INTEGER NOT NULL,
    content TEXT NOT NULL,
    citation_label TEXT NOT NULL,
    section_title TEXT NOT NULL,
    heading_path_json TEXT NOT NULL,
    source_uri TEXT,
    page_number INTEGER,
    token_count INTEGER NOT NULL,
    start_char INTEGER,
    end_char INTEGER,
    source_checksum TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(source_id) REFERENCES source_documents(source_id) ON DELETE CASCADE,
    FOREIGN KEY(section_id) REFERENCES document_sections(section_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_corpus
    ON document_chunks (corpus_id, corpus_version);

CREATE INDEX IF NOT EXISTS idx_document_chunks_source
    ON document_chunks (source_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_section
    ON document_chunks (section_id, chunk_index);

CREATE TABLE IF NOT EXISTS query_audits (
    query_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    corpus_id TEXT,
    corpus_version TEXT,
    answer TEXT NOT NULL,
    confidence TEXT NOT NULL,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    generation_model TEXT,
    embedding_model TEXT,
    reranker_model TEXT,
    prompt_version TEXT,
    retrieval_config_json TEXT NOT NULL DEFAULT '{}',
    latency_ms INTEGER,
    estimated_cost_usd REAL,
    evidence_digest TEXT,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    payload_hash TEXT,
    previous_record_hash TEXT,
    record_hash TEXT,
    chain_index INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_audits_chain
    ON query_audits (chain_index);

CREATE TABLE IF NOT EXISTS query_evidence (
    query_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    citation_label TEXT NOT NULL,
    dense_rank INTEGER,
    dense_score REAL,
    keyword_rank INTEGER,
    keyword_score REAL,
    fusion_score REAL,
    rerank_score REAL,
    final_rank INTEGER,
    snippet TEXT NOT NULL,
    quoted_text TEXT,
    source_span_json TEXT,
    quote_hash TEXT,
    verification_status TEXT NOT NULL,
    PRIMARY KEY(query_id, evidence_id),
    FOREIGN KEY(query_id) REFERENCES query_audits(query_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_query_evidence_query_rank
    ON query_evidence (query_id, final_rank);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
    ON chat_sessions (updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    query_id TEXT NOT NULL UNIQUE,
    turn_index INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(session_id, turn_index),
    FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(query_id) REFERENCES query_audits(query_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_turns_session
    ON chat_turns (session_id, turn_index);

CREATE INDEX IF NOT EXISTS idx_chat_turns_query
    ON chat_turns (query_id);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    corpus_name TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    input_type TEXT NOT NULL,
    input_uri TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    report_json TEXT NOT NULL DEFAULT '{}',
    error_json TEXT
);

CREATE TABLE IF NOT EXISTS source_audit_events (
    event_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    request_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    source_id TEXT,
    source_checksum TEXT,
    corpus_id TEXT,
    corpus_version TEXT,
    job_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_audit_events_created
    ON source_audit_events (created_at);

CREATE INDEX IF NOT EXISTS idx_source_audit_events_source
    ON source_audit_events (source_id);

CREATE INDEX IF NOT EXISTS idx_source_audit_events_action_status
    ON source_audit_events (action, status);
"""


def connect_db(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection with row mapping and foreign keys enabled."""

    connection = sqlite3.connect(str(path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create or migrate the local SQLite schema."""

    connection.executescript(SCHEMA_SQL)
    _ensure_column(connection, "query_audits", "evidence_digest", "TEXT")
    _ensure_column(
        connection,
        "query_audits",
        "evidence_count",
        "INTEGER NOT NULL DEFAULT 0",
    )
    connection.commit()


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row[1] for row in rows}
    if column_name in existing_columns:
        return
    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit a unit of work, rolling back on error."""

    with _transaction_lock(connection):
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()


def _transaction_lock(connection: sqlite3.Connection) -> RLock:
    connection_key = id(connection)
    with _TRANSACTION_LOCKS_GUARD:
        lock = _TRANSACTION_LOCKS.get(connection_key)
        if lock is None:
            lock = RLock()
            _TRANSACTION_LOCKS[connection_key] = lock
        return lock
