from app.domain.models import Citation, Evidence
from app.generation.citations import (
    CITATION_TO_NON_RETRIEVED_CHUNK,
    EVIDENCE_CHUNK_MISMATCH,
    FABRICATED_EVIDENCE_ID,
    QUOTE_NOT_IN_EVIDENCE,
    verify_answer_citations,
)


def test_verify_answer_citations_marks_supported_quote_verified() -> None:
    evidence = _evidence(
        evidence_id="evd_1",
        chunk_id="chk_1",
        snippet="Firms must retain records for six years after creation.",
    )
    citation = _citation(
        chunk_id="chk_1",
        quoted_text="retain records for six years",
    )

    result = verify_answer_citations(
        answer_text="Firms must retain records for six years.",
        citations=[citation],
        answer_evidence=[evidence],
        retrieved_evidence=[evidence],
    )

    assert result.verified
    assert result.issues == []
    assert result.citations[0].verification_status == "verified"
    assert result.citations[0].source_span == {"start": 11, "end": 39}


def test_verify_answer_citations_rejects_fabricated_evidence_id() -> None:
    retrieved = _evidence(evidence_id="evd_real", chunk_id="chk_1")
    fabricated = _evidence(evidence_id="evd_fake", chunk_id="chk_1")
    citation = _citation(chunk_id="chk_1", quoted_text="written procedures")

    result = verify_answer_citations(
        answer_text="Firms must maintain written procedures.",
        citations=[citation],
        answer_evidence=[fabricated],
        retrieved_evidence=[retrieved],
    )

    assert not result.verified
    assert FABRICATED_EVIDENCE_ID in result.issue_codes


def test_verify_answer_citations_rejects_evidence_id_chunk_mismatch() -> None:
    retrieved = _evidence(evidence_id="evd_1", chunk_id="chk_1")
    tampered = _evidence(evidence_id="evd_1", chunk_id="chk_2")
    citation = _citation(chunk_id="chk_1", quoted_text="written procedures")

    result = verify_answer_citations(
        answer_text="Firms must maintain written procedures.",
        citations=[citation],
        answer_evidence=[tampered],
        retrieved_evidence=[retrieved],
    )

    assert not result.verified
    assert EVIDENCE_CHUNK_MISMATCH in result.issue_codes


def test_verify_answer_citations_rejects_non_retrieved_chunk_citation() -> None:
    evidence = _evidence(evidence_id="evd_1", chunk_id="chk_1")
    citation = _citation(chunk_id="chk_missing", quoted_text="written procedures")

    result = verify_answer_citations(
        answer_text="Firms must maintain written procedures.",
        citations=[citation],
        answer_evidence=[evidence],
        retrieved_evidence=[evidence],
    )

    assert not result.verified
    assert CITATION_TO_NON_RETRIEVED_CHUNK in result.issue_codes
    assert result.citations[0].verification_status == "unverified"


def test_verify_answer_citations_rejects_quote_absent_from_evidence() -> None:
    evidence = _evidence(
        evidence_id="evd_1",
        chunk_id="chk_1",
        snippet="Firms must retain records for six years.",
    )
    citation = _citation(chunk_id="chk_1", quoted_text="review procedures annually")

    result = verify_answer_citations(
        answer_text="Firms must review procedures annually.",
        citations=[citation],
        answer_evidence=[evidence],
        retrieved_evidence=[evidence],
    )

    assert not result.verified
    assert QUOTE_NOT_IN_EVIDENCE in result.issue_codes
    assert result.citations[0].verification_status == "unverified"


def _evidence(
    *,
    evidence_id: str,
    chunk_id: str,
    snippet: str = "Firms must maintain written procedures.",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        chunk_id=chunk_id,
        citation_label="FINRA Rule 1000(a)",
        title="Written Procedures",
        snippet=snippet,
        score=0.9,
    )


def _citation(*, chunk_id: str, quoted_text: str) -> Citation:
    return Citation(
        citation_id=f"cit_{chunk_id}",
        citation_label="FINRA Rule 1000(a)",
        chunk_id=chunk_id,
        source_id="src_1",
        supports_claim=quoted_text,
        quoted_text=quoted_text,
    )
