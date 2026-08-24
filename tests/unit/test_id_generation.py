from datetime import UTC, datetime

import pytest

from app.domain.ids import (
    canonical_json,
    make_audit_record_hash,
    make_chat_session_id,
    make_chat_turn_id,
    make_chunk_id,
    make_content_hash,
    make_query_evidence_digest,
    make_query_id,
    make_section_id,
    make_source_id,
    normalize_text_for_id,
)


def test_normalize_text_for_id_collapses_unicode_and_whitespace() -> None:
    assert (
        normalize_text_for_id(" Rule\u00a02210 \r\n\tfair   dealing ")
        == "Rule 2210 fair dealing"
    )


def test_chunk_id_is_deterministic_for_equivalent_text() -> None:
    first = make_chunk_id(
        corpus_id="finra",
        corpus_version="2026-08-19",
        section_id="sec_1",
        chunk_index=0,
        text="Communications must be fair and balanced.",
    )
    second = make_chunk_id(
        corpus_id="finra",
        corpus_version="2026-08-19",
        section_id="sec_1",
        chunk_index=0,
        text=" Communications   must be fair and balanced. ",
    )

    assert first == second
    assert first.startswith("chk_")


def test_chunk_id_changes_when_index_changes() -> None:
    base = {
        "corpus_id": "finra",
        "corpus_version": "2026-08-19",
        "section_id": "sec_1",
        "text": "same text",
    }

    assert make_chunk_id(chunk_index=0, **base) != make_chunk_id(chunk_index=1, **base)


def test_source_section_and_query_ids_are_stable() -> None:
    source_id = make_source_id(
        corpus_id="finra",
        corpus_version="v1",
        source_uri="file://rules.md",
        checksum="abc123",
    )
    section_id = make_section_id(
        corpus_id="finra",
        source_id=source_id,
        citation_label="FINRA Rule 2210(d)(1)(A)",
        heading_path=["Communications", "Standards"],
    )
    query_id = make_query_id(question="What must communications include?", corpus_id="finra")

    assert source_id == make_source_id(
        corpus_id="finra",
        corpus_version="v1",
        source_uri="file://rules.md",
        checksum="abc123",
    )
    assert section_id.startswith("sec_")
    assert query_id.startswith("qry_")


def test_chat_ids_are_stable_and_prefixed() -> None:
    session_id = make_chat_session_id(request_nonce="session nonce")
    turn_id = make_chat_turn_id(session_id=session_id, query_id="qry_1")

    assert session_id == make_chat_session_id(request_nonce=" session   nonce ")
    assert session_id.startswith("cht_")
    assert turn_id == make_chat_turn_id(session_id=session_id, query_id="qry_1")
    assert turn_id != make_chat_turn_id(session_id=session_id, query_id="qry_2")
    assert turn_id.startswith("trn_")


def test_query_id_changes_with_source_filter() -> None:
    unfiltered = make_query_id(question="What does Rule 2210 require?", corpus_id="finra")
    filtered = make_query_id(
        question="What does Rule 2210 require?",
        corpus_id="finra",
        source_id="src_rule_2210",
    )

    assert unfiltered != filtered


def test_content_and_audit_hashes_are_deterministic() -> None:
    created_at = datetime(2026, 8, 19, tzinfo=UTC)

    assert make_content_hash("A   B") == make_content_hash("A B")
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert make_audit_record_hash(
        payload_hash="payload",
        previous_record_hash=None,
        chain_index=0,
        created_at=created_at,
    ) == make_audit_record_hash(
        payload_hash="payload",
        previous_record_hash=None,
        chain_index=0,
        created_at=created_at,
    )


def test_query_evidence_digest_is_order_stable_and_content_sensitive() -> None:
    first = {
        "query_id": "qry_1",
        "evidence_id": "evd_2",
        "chunk_id": "chk_2",
        "snippet": "Second evidence.",
        "verification_status": "not_required",
    }
    second = {
        "query_id": "qry_1",
        "evidence_id": "evd_1",
        "chunk_id": "chk_1",
        "snippet": "First evidence.",
        "verification_status": "verified",
    }

    digest = make_query_evidence_digest([first, second])
    reordered_digest = make_query_evidence_digest([second, first])
    changed_digest = make_query_evidence_digest(
        [first, {**second, "snippet": "Changed evidence."}]
    )

    assert digest == reordered_digest
    assert digest != changed_digest
    assert len(digest) == 64


def test_invalid_chunk_index_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_chunk_id(
            corpus_id="finra",
            corpus_version="v1",
            section_id="sec_1",
            chunk_index=-1,
            text="text",
        )
