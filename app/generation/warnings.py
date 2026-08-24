"""Warning taxonomy for RegLens API and audit payloads."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, TypedDict

WarningSeverity = Literal["info", "medium", "high"]


class WarningDetail(TypedDict):
    code: str
    severity: WarningSeverity
    message: str


_WARNING_CATALOG: dict[str, tuple[WarningSeverity, str]] = {
    "source_instruction_filtered": (
        "high",
        "Retrieved source text contained instructions that were filtered.",
    ),
    "weak_retrieval": (
        "medium",
        "Retrieved evidence was too weak to answer safely.",
    ),
    "insufficient_evidence": (
        "info",
        "The system did not find enough evidence to answer from the corpus.",
    ),
    "missing_citations": (
        "high",
        "A non-refusal answer was generated without required citations.",
    ),
    "quote_not_in_evidence": (
        "high",
        "A cited quote could not be verified against retrieved evidence.",
    ),
    "fabricated_evidence_id": (
        "high",
        "Answer evidence referenced an ID that retrieval did not return.",
    ),
    "evidence_chunk_mismatch": (
        "high",
        "Answer evidence did not match the retrieved chunk.",
    ),
    "citation_to_non_retrieved_chunk": (
        "high",
        "A citation referenced a chunk that retrieval did not return.",
    ),
}


def warning_details(codes: Sequence[str]) -> list[WarningDetail]:
    return [_warning_detail(code) for code in codes]


def _warning_detail(code: str) -> WarningDetail:
    severity, message = _WARNING_CATALOG.get(
        code,
        ("medium", f"Uncataloged warning: {code}."),
    )
    return {"code": code, "severity": severity, "message": message}
