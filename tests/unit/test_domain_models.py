from datetime import date

import pytest

from app.domain.models import (
    Answer,
    ChatSession,
    ChatTurn,
    Chunk,
    Citation,
    DocumentSection,
    DocumentSource,
    Evidence,
    ModelInfo,
    QueryAudit,
    QueryEvidence,
    RetrievalDiagnostics,
)


def test_document_models_accept_required_regulatory_metadata() -> None:
    source = DocumentSource(
        source_id="src_1",
        corpus_id="finra",
        corpus_name="FINRA Rules",
        version="2026-08-19",
        title="FINRA Rule 2210",
        checksum="checksum",
        url="https://example.test/rule-2210",
        document_type="rulebook",
        effective_date=date(2026, 1, 1),
        metadata={"jurisdiction": "US"},
    )
    section = DocumentSection(
        section_id="sec_1",
        source_id=source.source_id,
        corpus_id=source.corpus_id,
        citation_label="FINRA Rule 2210(d)(1)(A)",
        title="Fair and balanced communications",
        heading_path=["FINRA Rule 2210", "Content Standards"],
        text="Communications must be fair and balanced.",
        start_char=10,
        end_char=52,
    )
    chunk = Chunk(
        chunk_id="chk_1",
        section_id=section.section_id,
        source_id=source.source_id,
        corpus_id=source.corpus_id,
        corpus_version=source.version,
        citation_label=section.citation_label,
        title=section.title,
        heading_path=section.heading_path,
        text=section.text,
        token_count=6,
        chunk_index=0,
        section_chunk_count=1,
        char_start=section.start_char,
        char_end=section.end_char,
        source_checksum=source.checksum,
        metadata={"source": "fixture"},
    )

    assert source.metadata == {"jurisdiction": "US"}
    assert section.heading_path == ["FINRA Rule 2210", "Content Standards"]
    assert chunk.corpus_version == "2026-08-19"


def test_domain_models_defensively_copy_mutable_inputs() -> None:
    heading_path = ["A"]
    metadata = {"k": "v"}

    section = DocumentSection(
        section_id="sec_1",
        source_id="src_1",
        corpus_id="finra",
        citation_label="Rule 1",
        title="Title",
        heading_path=heading_path,
        text="Text",
        metadata=metadata,
    )
    heading_path.append("B")
    metadata["k"] = "changed"

    assert section.heading_path == ["A"]
    assert section.metadata == {"k": "v"}


def test_chat_models_capture_session_and_turn_metadata() -> None:
    session_metadata = {"mode": "mock"}
    turn_metadata = {"citation_count": 1}
    session = ChatSession(
        session_id="cht_1",
        title="How long must records be retained?",
        metadata=session_metadata,
        turn_count=2,
    )
    turn = ChatTurn(
        turn_id="trn_1",
        session_id=session.session_id,
        query_id="qry_1",
        turn_index=1,
        question="How long must records be retained?",
        answer="Records must be retained for six years.",
        confidence="high",
        metadata=turn_metadata,
    )

    session_metadata["mode"] = "changed"
    turn_metadata["citation_count"] = 99

    assert session.metadata == {"mode": "mock"}
    assert session.turn_count == 2
    assert turn.metadata == {"citation_count": 1}
    assert turn.confidence == "high"


def test_invalid_chat_models_are_rejected() -> None:
    with pytest.raises(ValueError, match="session_id"):
        ChatSession(session_id="", title="Session")

    with pytest.raises(ValueError, match="turn_index"):
        ChatTurn(
            turn_id="trn_1",
            session_id="cht_1",
            query_id="qry_1",
            turn_index=-1,
            question="Question?",
            answer="Answer.",
            confidence="high",
        )

    with pytest.raises(ValueError, match="confidence"):
        ChatTurn(
            turn_id="trn_1",
            session_id="cht_1",
            query_id="qry_1",
            turn_index=0,
            question="Question?",
            answer="Answer.",
            confidence="certain",  # type: ignore[arg-type]
        )


def test_invalid_spans_and_chunk_indexes_are_rejected() -> None:
    with pytest.raises(ValueError, match="start_char"):
        DocumentSection(
            section_id="sec_1",
            source_id="src_1",
            corpus_id="finra",
            citation_label="Rule 1",
            title="Title",
            heading_path=[],
            text="Text",
            start_char=10,
            end_char=5,
        )

    with pytest.raises(ValueError, match="chunk_index"):
        Chunk(
            chunk_id="chk_1",
            section_id="sec_1",
            source_id="src_1",
            corpus_id="finra",
            corpus_version="v1",
            citation_label="Rule 1",
            title="Title",
            heading_path=[],
            text="Text",
            token_count=1,
            chunk_index=1,
            section_chunk_count=1,
            source_checksum="checksum",
        )


def test_answer_and_audit_models_capture_citations_and_diagnostics() -> None:
    citation = Citation(
        citation_id="cit_1",
        citation_label="FINRA Rule 2210(d)(1)(A)",
        chunk_id="chk_1",
        source_id="src_1",
        supports_claim="Communications must be fair and balanced.",
        quoted_text="fair and balanced",
        source_span={"start": 24, "end": 41},
        verification_status="verified",
    )
    evidence = Evidence(
        evidence_id="evd_1",
        chunk_id="chk_1",
        citation_label=citation.citation_label,
        title="Fair and balanced communications",
        snippet="Communications must be fair and balanced.",
        score=0.91,
        source_span={"start": 0, "end": 42},
    )
    answer = Answer(
        query_id="qry_1",
        answer="Communications must be fair and balanced.",
        citations=[citation],
        evidence=[evidence],
        confidence="high",
        warnings=[],
        retrieval_diagnostics=RetrievalDiagnostics(total_candidates=3, returned_evidence=1),
        model_info=ModelInfo(generation_model="fake-llm", embedding_model="fake-embeddings"),
    )
    audit = QueryAudit(
        query_id=answer.query_id,
        question="What is required?",
        normalized_question="What is required?",
        answer=answer.answer,
        confidence=answer.confidence,
        retrieval_config={"top_k": 5},
    )
    query_evidence = QueryEvidence(
        query_id=answer.query_id,
        evidence_id=evidence.evidence_id,
        chunk_id=evidence.chunk_id,
        citation_label=evidence.citation_label,
        snippet=evidence.snippet,
        final_rank=1,
        verification_status="verified",
    )

    assert answer.citations[0].verification_status == "verified"
    assert audit.retrieval_config == {"top_k": 5}
    assert query_evidence.final_rank == 1


def test_invalid_confidence_and_verification_status_are_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        QueryAudit(
            query_id="qry_1",
            question="Question?",
            normalized_question="Question?",
            answer="Answer",
            confidence="certain",  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="verification_status"):
        Citation(
            citation_id="cit_1",
            citation_label="Rule 1",
            chunk_id="chk_1",
            source_id="src_1",
            supports_claim="Claim",
            verification_status="maybe",  # type: ignore[arg-type]
        )
