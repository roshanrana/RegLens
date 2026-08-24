from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.domain.ids import make_chunk_id, make_query_id, make_section_id, make_source_id
from app.domain.models import (
    ChatSession,
    ChatTurn,
    Chunk,
    DocumentSection,
    DocumentSource,
    IngestionJob,
    QueryAudit,
    QueryEvidence,
)
from app.persistence.db import connect_db, initialize_database
from app.persistence.repositories import (
    AuditConflictError,
    ChatSessionRepository,
    DocumentChunkRepository,
    DocumentSectionRepository,
    IngestionJobRepository,
    QueryAuditRepository,
    SourceDocumentRepository,
)


def test_source_sections_and_chunks_round_trip_through_temp_sqlite(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)

    source, section, chunk = _fixture_source_section_chunk()
    source_repo = SourceDocumentRepository(connection)
    section_repo = DocumentSectionRepository(connection)
    chunk_repo = DocumentChunkRepository(connection)

    source_repo.upsert(source)
    section_repo.upsert(section)
    chunk_repo.upsert(chunk)

    assert source_repo.get(source.source_id) == source
    assert section_repo.get(section.section_id) == section
    assert chunk_repo.get(chunk.chunk_id) == chunk
    assert chunk_repo.list_all() == [chunk]
    assert chunk_repo.list_all(corpus_id="finra", corpus_version="wrong-version") == []
    assert source_repo.list(corpus_id="finra") == [source]
    assert section_repo.list_by_source(source.source_id) == [section]
    assert chunk_repo.list_by_corpus("finra", corpus_version="2026-08-19") == [chunk]


def test_chunk_upsert_is_idempotent_and_updates_metadata(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)

    source, section, chunk = _fixture_source_section_chunk()
    SourceDocumentRepository(connection).upsert(source)
    DocumentSectionRepository(connection).upsert(section)
    chunk_repo = DocumentChunkRepository(connection)

    chunk_repo.upsert(chunk)
    updated = replace(chunk, metadata={"updated": True})
    chunk_repo.upsert(updated)

    assert len(chunk_repo.list_by_source(source.source_id)) == 1
    assert chunk_repo.get(chunk.chunk_id).metadata == {"updated": True}


def test_delete_by_corpus_version_only_removes_matching_chunks(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)

    source, section, chunk = _fixture_source_section_chunk()
    SourceDocumentRepository(connection).upsert(source)
    DocumentSectionRepository(connection).upsert(section)
    chunk_repo = DocumentChunkRepository(connection)
    chunk_repo.upsert(chunk)

    removed = chunk_repo.delete_by_corpus_version("finra", "2026-08-19")

    assert removed == 1
    assert chunk_repo.list_by_corpus("finra", corpus_version="2026-08-19") == []
    assert SourceDocumentRepository(connection).get(source.source_id) == source


def test_query_audit_and_evidence_round_trip_with_hash_chain(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)
    audit_repo = QueryAuditRepository(connection)

    audit, evidence = _fixture_query_audit_and_evidence()

    saved = audit_repo.save(audit, [evidence])

    assert saved.payload_hash is not None
    assert saved.record_hash is not None
    assert saved.chain_index == 0
    assert audit_repo.get(audit.query_id) == saved
    assert audit_repo.list_evidence(audit.query_id) == [evidence]
    assert audit_repo.verify_chain() is True


def test_query_audit_repository_rejects_duplicate_query_id(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)
    audit_repo = QueryAuditRepository(connection)
    audit, evidence = _fixture_query_audit_and_evidence()

    saved = audit_repo.save(audit, [evidence])

    with pytest.raises(AuditConflictError, match=audit.query_id):
        audit_repo.save(replace(audit, answer="Changed answer."), [evidence])

    assert audit_repo.get(audit.query_id) == saved
    assert audit_repo.list_evidence(audit.query_id) == [evidence]
    assert audit_repo.count() == 1
    assert audit_repo.verify_chain() is True


def test_ingestion_job_round_trip(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)
    repo = IngestionJobRepository(connection)

    job = IngestionJob(
        job_id="job_1",
        corpus_id="finra",
        corpus_name="FINRA Rules",
        corpus_version="2026-08-19",
        input_type="markdown",
        input_uri="file://fixtures/finra.md",
        status="completed",
        report={"sections": 1, "chunks": 1},
        error=None,
    )

    repo.save(job)

    assert repo.get(job.job_id) == job


def test_chat_session_and_turns_round_trip(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)
    audit_repo = QueryAuditRepository(connection)
    chat_repo = ChatSessionRepository(connection)
    audit, evidence = _fixture_query_audit_and_evidence()
    saved_audit = audit_repo.save(audit, [evidence])
    session = ChatSession(
        session_id="cht_1",
        title="How long must records be retained?",
        metadata={"mode": "mock"},
    )
    turn = ChatTurn(
        turn_id="trn_1",
        session_id=session.session_id,
        query_id=saved_audit.query_id,
        turn_index=99,
        question=saved_audit.question,
        answer=saved_audit.answer,
        confidence=saved_audit.confidence,
        metadata={"citation_count": 1},
    )

    saved_session, saved_turn = chat_repo.append_turn(session, turn)

    assert saved_turn.turn_index == 0
    assert chat_repo.get_session(session.session_id) == saved_session
    assert chat_repo.list_sessions() == [saved_session]
    assert chat_repo.list_turns(session.session_id) == [saved_turn]
    assert chat_repo.get_turn_by_query_id(saved_audit.query_id) == (
        saved_session,
        saved_turn,
    )

    second_audit_input = replace(audit, query_id="qry_second")
    second_evidence = replace(
        evidence,
        query_id=second_audit_input.query_id,
        evidence_id="evd_2",
    )
    second_audit = audit_repo.save(second_audit_input, [second_evidence])
    second_turn = replace(
        turn,
        turn_id="trn_2",
        query_id=second_audit.query_id,
        question="Show me FINRA Rule 1030(b).",
    )

    updated_session, saved_second_turn = chat_repo.append_turn(saved_session, second_turn)

    assert saved_second_turn.turn_index == 1
    assert updated_session.updated_at >= saved_session.updated_at
    assert chat_repo.list_sessions()[0].turn_count == 2
    assert [item.turn_index for item in chat_repo.list_turns(session.session_id)] == [0, 1]
    assert chat_repo.get_turn_by_query_id("qry_missing") is None


def test_chat_session_delete_cascades_turns_not_audit(tmp_path) -> None:
    connection = connect_db(tmp_path / "reglens.db")
    initialize_database(connection)
    audit_repo = QueryAuditRepository(connection)
    chat_repo = ChatSessionRepository(connection)
    audit, evidence = _fixture_query_audit_and_evidence()
    saved_audit = audit_repo.save(audit, [evidence])
    session = ChatSession(session_id="cht_1", title="Session")
    turn = ChatTurn(
        turn_id="trn_1",
        session_id=session.session_id,
        query_id=saved_audit.query_id,
        turn_index=0,
        question=saved_audit.question,
        answer=saved_audit.answer,
        confidence=saved_audit.confidence,
    )
    chat_repo.append_turn(session, turn)

    assert chat_repo.delete_session(session.session_id) is True
    assert chat_repo.get_session(session.session_id) is None
    assert chat_repo.list_turns(session.session_id) == []
    assert audit_repo.get(saved_audit.query_id) == saved_audit
    assert chat_repo.delete_session(session.session_id) is False


def _fixture_query_audit_and_evidence() -> tuple[QueryAudit, QueryEvidence]:
    query_id = make_query_id(
        question="What must retail communications be?",
        corpus_id="finra",
        corpus_version="2026-08-19",
        request_nonce="1",
    )
    audit = QueryAudit(
        query_id=query_id,
        question="What must retail communications be?",
        normalized_question="what must retail communications be?",
        corpus_id="finra",
        corpus_version="2026-08-19",
        answer="They must be fair and balanced.",
        confidence="high",
        warnings=[],
        generation_model="fake-llm",
        embedding_model="fake-embeddings",
        reranker_model="fake-reranker",
        prompt_version="v1",
        retrieval_config={"top_k": 5},
        latency_ms=12,
        estimated_cost_usd=0.0,
        created_at=datetime(2026, 8, 19, tzinfo=UTC),
    )
    evidence = QueryEvidence(
        query_id=query_id,
        evidence_id="evd_1",
        chunk_id="chk_1",
        citation_label="FINRA Rule 2210(d)(1)(A)",
        snippet="Communications must be fair and balanced.",
        dense_rank=1,
        dense_score=0.8,
        keyword_rank=1,
        keyword_score=2.0,
        fusion_score=0.05,
        rerank_score=0.9,
        final_rank=1,
        quoted_text="fair and balanced",
        source_span={"start": 24, "end": 41},
        quote_hash="hash",
        verification_status="verified",
    )
    return audit, evidence


def _fixture_source_section_chunk() -> tuple[DocumentSource, DocumentSection, Chunk]:
    source_id = make_source_id(
        corpus_id="finra",
        corpus_version="2026-08-19",
        source_uri="file://finra-rule-2210.md",
        checksum="checksum-1",
    )
    section_id = make_section_id(
        corpus_id="finra",
        source_id=source_id,
        citation_label="FINRA Rule 2210(d)(1)(A)",
        heading_path=["FINRA Rule 2210", "Content Standards"],
    )
    text = "Communications with the public must be fair and balanced."
    chunk_id = make_chunk_id(
        corpus_id="finra",
        corpus_version="2026-08-19",
        section_id=section_id,
        chunk_index=0,
        text=text,
    )
    source = DocumentSource(
        source_id=source_id,
        corpus_id="finra",
        corpus_name="FINRA Rules",
        version="2026-08-19",
        title="FINRA Rule 2210",
        url="file://finra-rule-2210.md",
        checksum="checksum-1",
        document_type="rulebook",
        publication_date=date(2026, 1, 1),
        effective_date=date(2026, 1, 1),
        metadata={"jurisdiction": "US"},
    )
    section = DocumentSection(
        section_id=section_id,
        source_id=source.source_id,
        corpus_id=source.corpus_id,
        citation_label="FINRA Rule 2210(d)(1)(A)",
        title="Fair and balanced communications",
        heading_path=["FINRA Rule 2210", "Content Standards"],
        text=text,
        url=source.url,
        effective_date=source.effective_date,
        page_number=4,
        start_char=100,
        end_char=158,
        metadata={"kind": "rule"},
    )
    chunk = Chunk(
        chunk_id=chunk_id,
        section_id=section.section_id,
        source_id=source.source_id,
        corpus_id=source.corpus_id,
        corpus_version=source.version,
        citation_label=section.citation_label,
        title=section.title,
        heading_path=section.heading_path,
        text=section.text,
        token_count=8,
        chunk_index=0,
        section_chunk_count=1,
        char_start=section.start_char,
        char_end=section.end_char,
        page_number=section.page_number,
        source_checksum=source.checksum,
        url=section.url,
        metadata={"kind": "chunk"},
    )
    return source, section, chunk
