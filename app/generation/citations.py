"""Citation verification for RegLens answer generation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from app.domain.models import Answer, Citation, Confidence, Evidence
from app.generation.quote_verifier import QuoteVerifier

FABRICATED_EVIDENCE_ID = "fabricated_evidence_id"
EVIDENCE_CHUNK_MISMATCH = "evidence_chunk_mismatch"
CITATION_TO_NON_RETRIEVED_CHUNK = "citation_to_non_retrieved_chunk"
MISSING_CITATIONS = "missing_citations"
QUOTE_NOT_IN_EVIDENCE = "quote_not_in_evidence"

_REFUSAL_MARKERS = (
    "insufficient evidence",
    "not enough evidence",
    "not enough information",
    "cannot answer",
    "can't answer",
    "unable to answer",
    "i do not have enough",
    "i don't have enough",
)


@dataclass(frozen=True)
class CitationVerificationIssue:
    code: str
    message: str
    citation_id: str | None = None
    evidence_id: str | None = None
    chunk_id: str | None = None


@dataclass(frozen=True)
class CitationVerificationResult:
    verified: bool
    issues: list[CitationVerificationIssue]
    citations: list[Citation]

    @property
    def issue_codes(self) -> list[str]:
        return [issue.code for issue in self.issues]


def verify_answer(
    answer: Answer,
    *,
    retrieved_evidence: Sequence[Evidence] | None = None,
) -> CitationVerificationResult:
    """Verify the citations and answer evidence on an ``Answer`` object."""

    return verify_answer_citations(
        answer_text=answer.answer,
        citations=answer.citations,
        answer_evidence=answer.evidence,
        retrieved_evidence=retrieved_evidence,
        confidence=answer.confidence,
    )


def verify_answer_citations(
    *,
    answer_text: str,
    citations: Sequence[Citation],
    answer_evidence: Sequence[Evidence],
    retrieved_evidence: Sequence[Evidence] | None = None,
    confidence: Confidence | None = None,
    evidence_text_by_chunk_id: Mapping[str, str] | None = None,
    quote_verifier: QuoteVerifier | None = None,
) -> CitationVerificationResult:
    """Verify answer citations against the evidence returned by retrieval.

    ``retrieved_evidence`` is the trusted retrieval output. ``answer_evidence``
    is what the generator returned alongside the answer. Passing both lets this
    function catch fabricated evidence IDs before audit records are written.
    """

    resolved_retrieved = list(
        retrieved_evidence if retrieved_evidence is not None else answer_evidence
    )
    answer_evidence_list = list(answer_evidence)
    citation_list = list(citations)
    text_by_chunk_id = dict(evidence_text_by_chunk_id or {})
    verifier = quote_verifier or QuoteVerifier()

    issues: list[CitationVerificationIssue] = []
    retrieved_by_id = {evidence.evidence_id: evidence for evidence in resolved_retrieved}
    retrieved_by_chunk_id: dict[str, list[Evidence]] = defaultdict(list)
    for evidence in resolved_retrieved:
        retrieved_by_chunk_id[evidence.chunk_id].append(evidence)

    for evidence in answer_evidence_list:
        retrieved = retrieved_by_id.get(evidence.evidence_id)
        if retrieved is None:
            issues.append(
                CitationVerificationIssue(
                    code=FABRICATED_EVIDENCE_ID,
                    message="answer references evidence_id that was not returned by retrieval",
                    evidence_id=evidence.evidence_id,
                    chunk_id=evidence.chunk_id,
                )
            )
        elif retrieved.chunk_id != evidence.chunk_id:
            issues.append(
                CitationVerificationIssue(
                    code=EVIDENCE_CHUNK_MISMATCH,
                    message="answer evidence_id is associated with a different retrieved chunk",
                    evidence_id=evidence.evidence_id,
                    chunk_id=evidence.chunk_id,
                )
            )

    if not citation_list and not is_refusal_answer(answer_text, confidence=confidence):
        issues.append(
            CitationVerificationIssue(
                code=MISSING_CITATIONS,
                message="non-refusal answers must include at least one citation",
            )
        )

    citation_issue_ids: dict[str, list[CitationVerificationIssue]] = defaultdict(list)
    verified_citations: list[Citation] = []
    for citation in citation_list:
        per_citation_issues: list[CitationVerificationIssue] = []
        evidence_for_chunk = retrieved_by_chunk_id.get(citation.chunk_id, [])
        if not evidence_for_chunk:
            per_citation_issues.append(
                CitationVerificationIssue(
                    code=CITATION_TO_NON_RETRIEVED_CHUNK,
                    message="citation references a chunk that was not returned by retrieval",
                    citation_id=citation.citation_id,
                    chunk_id=citation.chunk_id,
                )
            )
        elif citation.quoted_text:
            sources = _quote_sources(
                citation.chunk_id,
                evidence_for_chunk,
                evidence_text_by_chunk_id=text_by_chunk_id,
            )
            quote_result = verifier.verify(
                citation.quoted_text,
                sources,
                source_span=citation.source_span,
            )
            if not quote_result.verified:
                per_citation_issues.append(
                    CitationVerificationIssue(
                        code=QUOTE_NOT_IN_EVIDENCE,
                        message=(
                            "quoted_text is not supported by retrieved evidence: "
                            f"{quote_result.reason}"
                        ),
                        citation_id=citation.citation_id,
                        chunk_id=citation.chunk_id,
                    )
                )
            elif citation.source_span is None and quote_result.match is not None:
                citation = replace(citation, source_span=quote_result.match.source_span)

        issues.extend(per_citation_issues)
        citation_issue_ids[citation.citation_id].extend(per_citation_issues)
        verified_citations.append(
            replace(
                citation,
                verification_status=(
                    "unverified" if citation_issue_ids[citation.citation_id] else "verified"
                ),
            )
        )

    return CitationVerificationResult(
        verified=not issues,
        issues=issues,
        citations=verified_citations,
    )


def is_refusal_answer(answer_text: str, *, confidence: Confidence | None = None) -> bool:
    if confidence == "insufficient_evidence":
        return True
    normalized = " ".join(answer_text.casefold().split())
    return any(marker in normalized for marker in _REFUSAL_MARKERS)


def _quote_sources(
    chunk_id: str,
    evidence_for_chunk: Sequence[Evidence],
    *,
    evidence_text_by_chunk_id: Mapping[str, str],
) -> dict[str, str]:
    sources: dict[str, str] = {}
    full_text = evidence_text_by_chunk_id.get(chunk_id)
    if full_text:
        sources[f"chunk:{chunk_id}:text"] = full_text
    for evidence in evidence_for_chunk:
        sources[f"evidence:{evidence.evidence_id}:snippet"] = evidence.snippet
    return sources
