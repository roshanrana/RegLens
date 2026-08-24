"""LLM client interfaces and deterministic fake-mode generation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.models import Confidence
from app.generation.prompts import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    PromptBundle,
    PromptEvidence,
)

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:\([A-Za-z0-9]+\))*")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_SOURCE_INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore (?:all |any |the |previous |prior )?instructions?\b", re.IGNORECASE),
    re.compile(r"\bdisregard (?:all |any |the |previous |prior )?instructions?\b", re.IGNORECASE),
    re.compile(r"\bforget (?:all |any |the |previous |prior )?instructions?\b", re.IGNORECASE),
    re.compile(
        r"\breveal (?:the )?(?:system|developer|hidden) (?:prompt|instructions?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdo not cite\b", re.IGNORECASE),
    re.compile(r"\banswer (?:that|with|as)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class GeneratedAnswer:
    """Provider-neutral answer text returned by an LLM client."""

    text: str
    cited_markers: tuple[str, ...]
    claims_by_marker: dict[str, str]
    confidence: Confidence
    warnings: tuple[str, ...] = ()
    model_name: str = "fake-reglens-llm-v1"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("text must be non-empty")
        object.__setattr__(self, "cited_markers", tuple(self.cited_markers))
        object.__setattr__(self, "claims_by_marker", dict(self.claims_by_marker))
        object.__setattr__(self, "warnings", tuple(self.warnings))


class LLMClient(Protocol):
    """Future-swappable answer generation client."""

    model_name: str

    def generate(self, prompt: PromptBundle) -> GeneratedAnswer:
        ...


class FakeLLMClient:
    """Deterministic fake LLM for offline tests.

    It deliberately uses only the structured prompt evidence. The goal is not
    linguistic sophistication; it is a stable contract for the later real LLM
    provider, citation verifier, and audit layers.
    """

    model_name = "fake-reglens-llm-v1"

    def __init__(
        self,
        *,
        max_cited_evidence: int = 2,
        min_evidence_score: float = 0.0,
    ) -> None:
        if max_cited_evidence <= 0:
            raise ValueError("max_cited_evidence must be greater than zero")
        if min_evidence_score < 0:
            raise ValueError("min_evidence_score must be non-negative")
        self.max_cited_evidence = max_cited_evidence
        self.min_evidence_score = min_evidence_score

    def generate(self, prompt: PromptBundle) -> GeneratedAnswer:
        usable_evidence = [
            item
            for item in prompt.evidence
            if item.score >= self.min_evidence_score and item.snippet.strip()
        ]
        if not usable_evidence:
            return _insufficient_answer(model_name=self.model_name)

        selected = usable_evidence[: self.max_cited_evidence]
        claims_by_marker: dict[str, str] = {}
        answer_sentences: list[str] = []
        warnings: set[str] = set()
        for item in selected:
            claim_result = _best_supported_claim(prompt.question, item)
            if not claim_result.claim:
                warnings.update(claim_result.warnings)
                continue
            claim = claim_result.claim
            warnings.update(claim_result.warnings)
            claims_by_marker[item.marker] = claim
            answer_sentences.append(
                f"{item.citation_label} states: {claim} {item.bracketed_marker}"
            )

        confidence: Confidence = "high" if len(selected) > 1 else "medium"
        if not answer_sentences:
            return GeneratedAnswer(
                text=INSUFFICIENT_EVIDENCE_ANSWER,
                cited_markers=(),
                claims_by_marker={},
                confidence="insufficient_evidence",
                warnings=tuple(sorted(warnings | {"insufficient_evidence"})),
                model_name=self.model_name,
            )
        return GeneratedAnswer(
            text=" ".join(answer_sentences),
            cited_markers=tuple(item.marker for item in selected),
            claims_by_marker=claims_by_marker,
            confidence=confidence,
            warnings=tuple(sorted(warnings)),
            model_name=self.model_name,
        )


def _insufficient_answer(*, model_name: str) -> GeneratedAnswer:
    return GeneratedAnswer(
        text=INSUFFICIENT_EVIDENCE_ANSWER,
        cited_markers=(),
        claims_by_marker={},
        confidence="insufficient_evidence",
        warnings=("insufficient_evidence",),
        model_name=model_name,
    )


@dataclass(frozen=True)
class _ClaimResult:
    claim: str
    warnings: tuple[str, ...] = ()


def _best_supported_claim(question: str, evidence: PromptEvidence) -> _ClaimResult:
    query_terms = _query_terms(question)
    sentences, warnings = _candidate_sentences(evidence.snippet)
    if not sentences:
        claim = "" if warnings else _ensure_sentence(evidence.snippet)
        return _ClaimResult(claim, warnings=tuple(warnings))

    best_sentence = max(
        sentences,
        key=lambda sentence: (
            _sentence_score(sentence, query_terms),
            _regulatory_signal_score(sentence),
            -len(sentence),
        ),
    )
    return _ClaimResult(_ensure_sentence(best_sentence), warnings=tuple(warnings))


def _candidate_sentences(text: str) -> tuple[list[str], list[str]]:
    normalized = " ".join(text.split())
    if not normalized:
        return [], []

    raw_sentences = _SENTENCE_BOUNDARY_RE.split(normalized)
    unfiltered_sentences = [sentence.strip() for sentence in raw_sentences if sentence.strip()]
    sentences: list[str] = []
    filtered_count = 0
    for sentence in unfiltered_sentences:
        parts = _sentence_parts(sentence)
        kept_parts = [part for part in parts if not _is_source_instruction(part)]
        filtered_count += len(parts) - len(kept_parts)
        if not kept_parts:
            continue
        sentences.append(_ensure_sentence(" ".join(kept_parts)))
    warnings = ["source_instruction_filtered"] if filtered_count else []
    if len(sentences) == 1 and len(sentences[0]) > 320:
        return _windowed_phrases(sentences[0]), warnings
    return sentences, warnings


def _sentence_parts(sentence: str) -> list[str]:
    raw_parts = sentence.split(";")
    parts: list[str] = []
    for index, part in enumerate(raw_parts):
        stripped = part.strip()
        if not stripped:
            continue
        if index < len(raw_parts) - 1:
            stripped = f"{stripped};"
        parts.append(stripped)
    return parts or [sentence]


def _is_source_instruction(sentence: str) -> bool:
    return any(pattern.search(sentence) for pattern in _SOURCE_INSTRUCTION_PATTERNS)


def _windowed_phrases(text: str, *, max_words: int = 34) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    phrases: list[str] = []
    step = max_words
    for start in range(0, len(words), step):
        phrase = " ".join(words[start : start + max_words]).strip()
        if phrase:
            phrases.append(phrase)
    return phrases


def _sentence_score(sentence: str, query_terms: set[str]) -> int:
    sentence_terms = set(_terms(sentence))
    return len(sentence_terms.intersection(query_terms))


def _regulatory_signal_score(sentence: str) -> int:
    lowered = sentence.lower()
    signals = ("must", "required", "require", "retain", "review", "disclose", "prohibit")
    return sum(1 for signal in signals if signal in lowered)


def _query_terms(text: str) -> set[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "how",
        "if",
        "in",
        "is",
        "must",
        "of",
        "or",
        "the",
        "to",
        "what",
        "when",
        "with",
    }
    return {term for term in _terms(text) if term not in stop_words}


def _terms(text: str) -> list[str]:
    return [_stem(match.group(0).lower()) for match in _WORD_RE.finditer(text)]


def _stem(term: str) -> str:
    for suffix in ("ing", "ed", "s"):
        if len(term) > len(suffix) + 3 and term.endswith(suffix):
            return term[: -len(suffix)]
    return term


def _ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped[-1] in ".!?;:":
        return stripped
    return stripped + "."


def cited_markers_from_text(text: str, *, allowed_markers: Sequence[str]) -> tuple[str, ...]:
    """Extract cited evidence markers from generated text in first-use order."""

    allowed = set(allowed_markers)
    markers: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"\[(E\d+)\]", text):
        marker = match.group(1)
        if marker in allowed and marker not in seen:
            seen.add(marker)
            markers.append(marker)
    return tuple(markers)
