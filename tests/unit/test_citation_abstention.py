from app.domain.models import Citation, Evidence
from app.generation.citations import (
    MISSING_CITATIONS,
    QUOTE_NOT_IN_EVIDENCE,
    verify_answer_citations,
)


def test_non_refusal_answer_without_citations_is_rejected() -> None:
    evidence = _evidence()

    result = verify_answer_citations(
        answer_text="Firms must retain records for six years.",
        citations=[],
        answer_evidence=[evidence],
        retrieved_evidence=[evidence],
        confidence="high",
    )

    assert not result.verified
    assert result.issue_codes == [MISSING_CITATIONS]


def test_refusal_answer_without_citations_is_allowed() -> None:
    result = verify_answer_citations(
        answer_text=(
            "I cannot answer from the retrieved material because "
            "there is insufficient evidence."
        ),
        citations=[],
        answer_evidence=[],
        retrieved_evidence=[],
        confidence="insufficient_evidence",
    )

    assert result.verified
    assert result.issue_codes == []


def test_non_refusal_answer_with_fabricated_quote_is_rejected_even_with_citation() -> None:
    evidence = _evidence(snippet="Firms must retain records for six years.")
    citation = Citation(
        citation_id="cit_1",
        citation_label="FINRA Rule 1030(b)",
        chunk_id=evidence.chunk_id,
        source_id="src_1",
        supports_claim="Firms must retain records permanently.",
        quoted_text="retain records permanently",
    )

    result = verify_answer_citations(
        answer_text="Firms must retain records permanently.",
        citations=[citation],
        answer_evidence=[evidence],
        retrieved_evidence=[evidence],
        confidence="high",
    )

    assert not result.verified
    assert QUOTE_NOT_IN_EVIDENCE in result.issue_codes


def _evidence(*, snippet: str = "Firms must retain records for six years.") -> Evidence:
    return Evidence(
        evidence_id="evd_1",
        chunk_id="chk_1",
        citation_label="FINRA Rule 1030(b)",
        title="Books and Records",
        snippet=snippet,
        score=0.88,
    )
