"""Deterministic ID and hash helpers for RegLens.

These helpers are deliberately dependency-free so ingestion, retrieval, and
audit tests can run in fake mode without service credentials.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text_for_id(text: str) -> str:
    """Return a stable text form for content-derived IDs."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for hashing and audit payloads."""

    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_hexdigest(value: str | bytes) -> str:
    """Return a SHA-256 hex digest for text or bytes."""

    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def stable_hash(*parts: Any) -> str:
    """Hash an ordered tuple of scalar/JSON-serializable parts."""

    return sha256_hexdigest(canonical_json(parts))


def stable_id(prefix: str, *parts: Any, length: int = 40) -> str:
    """Return a prefixed deterministic ID."""

    if not prefix or not prefix.isidentifier():
        raise ValueError("prefix must be a valid identifier-like string")
    if length <= 0 or length > 64:
        raise ValueError("length must be between 1 and 64")
    return f"{prefix}_{stable_hash(*parts)[:length]}"


def make_content_hash(text: str) -> str:
    """Hash normalized content text."""

    return sha256_hexdigest(normalize_text_for_id(text))


def make_source_id(
    *,
    corpus_id: str,
    corpus_version: str,
    source_uri: str | None = None,
    title: str | None = None,
    checksum: str | None = None,
) -> str:
    """Create a stable source document ID for idempotent ingestion."""

    source_key = source_uri or title or checksum
    if not source_key:
        raise ValueError("source_uri, title, or checksum is required")
    return stable_id("src", corpus_id, corpus_version, source_key, checksum or "")


def make_section_id(
    *,
    corpus_id: str,
    source_id: str,
    citation_label: str,
    heading_path: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Create a stable section ID from its source and citation context."""

    return stable_id(
        "sec",
        corpus_id,
        source_id,
        normalize_text_for_id(citation_label),
        list(heading_path or []),
    )


def make_chunk_id(
    *,
    corpus_id: str,
    corpus_version: str,
    section_id: str,
    chunk_index: int,
    text: str,
) -> str:
    """Create the deterministic chunk ID specified in the implementation plan."""

    if chunk_index < 0:
        raise ValueError("chunk_index must be non-negative")
    return stable_id(
        "chk",
        corpus_id,
        corpus_version,
        section_id,
        chunk_index,
        normalize_text_for_id(text),
    )


def make_query_id(
    *,
    question: str,
    corpus_id: str | None = None,
    corpus_version: str | None = None,
    source_id: str | None = None,
    request_nonce: str | None = None,
) -> str:
    """Create a deterministic query ID.

    Pass a request nonce when repeated identical questions must produce distinct
    audit rows while staying reproducible in tests.
    """

    return stable_id(
        "qry",
        normalize_text_for_id(question),
        corpus_id or "",
        corpus_version or "",
        source_id or "",
        request_nonce or "",
    )


def make_chat_session_id(*, request_nonce: str) -> str:
    """Create a chat session ID from a caller/runtime nonce."""

    return stable_id("cht", normalize_text_for_id(request_nonce))


def make_chat_turn_id(*, session_id: str, query_id: str) -> str:
    """Create a stable chat turn ID linked to a persisted query audit."""

    return stable_id("trn", session_id, query_id)


def make_evidence_id(*, query_id: str, chunk_id: str, final_rank: int | None = None) -> str:
    """Create a stable evidence row ID for a query/chunk pair."""

    return stable_id("evd", query_id, chunk_id, final_rank if final_rank is not None else "")


def make_payload_hash(payload: Any) -> str:
    """Hash a canonical audit payload."""

    return sha256_hexdigest(canonical_json(payload))


def make_query_evidence_digest(evidence_rows: Sequence[Mapping[str, Any]]) -> str:
    """Hash persisted query evidence rows independent of row ordering."""

    canonical_rows = sorted(canonical_json(dict(row)) for row in evidence_rows)
    return sha256_hexdigest(canonical_json(canonical_rows))


def make_audit_record_hash(
    *,
    payload_hash: str,
    previous_record_hash: str | None,
    chain_index: int,
    created_at: datetime,
) -> str:
    """Hash the audit chain link fields."""

    return stable_hash(
        payload_hash,
        previous_record_hash or "",
        chain_index,
        created_at.isoformat(),
    )


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
