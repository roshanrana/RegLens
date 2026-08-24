"""Keyword retrieval primitives for RegLens.

The MVP index is intentionally in-memory and dependency-free. It gives later
retrieval agents a deterministic BM25 backend for fake-mode tests while keeping
the important regulatory behavior: exact citation lookup and rule-aware tokens.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from app.domain.models import Chunk, RetrievalCandidate

_TOKEN_RE = re.compile(
    r"\d+(?:\([A-Za-z0-9]+\))+|(?:\([A-Za-z0-9]+\))+|[A-Za-z]{2,}(?:-[A-Za-z0-9]+)*|\d+"
)
_MARKER_RE = re.compile(r"\([A-Za-z0-9]+\)")
_NUMBER_RE = re.compile(r"^\d+")
_UPPERCASE_TERM_RE = re.compile(r"^[A-Z][A-Z0-9-]*[A-Z0-9]$")
_RULE_REFERENCE_RE = re.compile(
    r"\b(?:(?P<authority>[A-Z]{2,})\s+)?(?:(?P<rule>[Rr][Uu][Ll][Ee])\s+)?"
    r"(?P<number>\d+)(?P<markers>(?:\([A-Za-z0-9]+\))*)"
)
_CITATION_SIGNAL_RE = re.compile(r"\brule\s+\d+|\d+\([A-Za-z0-9]+\)", re.IGNORECASE)


@dataclass(frozen=True)
class KeywordSearchConfig:
    """Scoring and field-weight settings for the in-memory BM25 index."""

    k1: float = 1.5
    b: float = 0.75
    citation_weight: int = 6
    title_weight: int = 3
    heading_weight: int = 2
    exact_citation_boost: float = 25.0

    def __post_init__(self) -> None:
        if self.k1 <= 0:
            raise ValueError("k1 must be greater than zero")
        if not 0 <= self.b <= 1:
            raise ValueError("b must be between zero and one")
        if self.citation_weight <= 0:
            raise ValueError("citation_weight must be greater than zero")
        if self.title_weight <= 0:
            raise ValueError("title_weight must be greater than zero")
        if self.heading_weight <= 0:
            raise ValueError("heading_weight must be greater than zero")
        if self.exact_citation_boost < 0:
            raise ValueError("exact_citation_boost must be non-negative")


class KeywordTokenizer:
    """Rule-aware tokenizer for keyword retrieval.

    Normal words are lowercased. Uppercase regulatory abbreviations emit both
    the original token and a lowercase copy. Rule IDs and paragraph markers are
    expanded into searchable cumulative forms, so a query for ``1000(a)`` can
    match a more specific citation like ``1000(a)(1)``.
    """

    def tokenize(self, text: str) -> list[str]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        tokens: list[str] = []
        for match in _TOKEN_RE.finditer(text):
            tokens.extend(_expand_token(match.group(0)))
        return tokens


@dataclass(frozen=True)
class _IndexedDocument:
    chunk: Chunk
    term_freq: Counter[str]
    length: int
    citation_keys: frozenset[str]


class BM25KeywordIndex:
    """Small in-memory BM25 index over RegLens chunks."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        *,
        tokenizer: KeywordTokenizer | None = None,
        config: KeywordSearchConfig | None = None,
    ) -> None:
        self.tokenizer = tokenizer or KeywordTokenizer()
        self.config = config or KeywordSearchConfig()
        self._documents: dict[str, _IndexedDocument] = {}
        self._doc_freq: Counter[str] = Counter()
        self._chunk_order: list[str] = []

        for chunk in chunks:
            if chunk.chunk_id in self._documents:
                raise ValueError(f"duplicate chunk_id in keyword index: {chunk.chunk_id}")
            tokens = self._tokens_for_chunk(chunk)
            term_freq = Counter(tokens)
            document = _IndexedDocument(
                chunk=chunk,
                term_freq=term_freq,
                length=len(tokens),
                citation_keys=frozenset(extract_citation_keys(chunk.citation_label)),
            )
            self._documents[chunk.chunk_id] = document
            self._chunk_order.append(chunk.chunk_id)
            self._doc_freq.update(term_freq.keys())

        self._avg_doc_length = (
            sum(document.length for document in self._documents.values()) / len(self._documents)
            if self._documents
            else 0.0
        )

    @property
    def chunk_count(self) -> int:
        return len(self._documents)

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        corpus_id: str | None = None,
        corpus_version: str | None = None,
        source_ids: Collection[str] | None = None,
    ) -> list[RetrievalCandidate]:
        """Return BM25-ranked candidates with keyword rank and score fields set."""

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        query_tokens = _unique_preserving_order(self.tokenizer.tokenize(query))
        query_citation_keys = extract_citation_keys(query)
        has_citation_signal = _has_citation_signal(query)
        if not query_tokens and not query_citation_keys:
            return []

        source_id_filter = set(source_ids) if source_ids is not None else None
        if source_id_filter == set():
            return []

        scored: list[tuple[float, Chunk]] = []
        for chunk_id in self._chunk_order:
            document = self._documents[chunk_id]
            if not _passes_filters(
                document.chunk,
                corpus_id=corpus_id,
                corpus_version=corpus_version,
                source_ids=source_id_filter,
            ):
                continue

            score = self._bm25_score(document, query_tokens)
            if has_citation_signal and query_citation_keys.intersection(document.citation_keys):
                score += self.config.exact_citation_boost
            if score > 0:
                scored.append((score, document.chunk))

        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            RetrievalCandidate(
                chunk=chunk,
                fusion_score=score,
                keyword_rank=rank,
                keyword_score=score,
            )
            for rank, (score, chunk) in enumerate(scored[:top_k], start=1)
        ]

    def find_exact_citation_matches(
        self,
        query: str,
        *,
        corpus_id: str | None = None,
        corpus_version: str | None = None,
        source_ids: Collection[str] | None = None,
    ) -> list[Chunk]:
        """Return chunks whose citation label exactly matches a query reference."""

        query_citation_keys = extract_citation_keys(query)
        if not query_citation_keys:
            return []

        source_id_filter = set(source_ids) if source_ids is not None else None
        if source_id_filter == set():
            return []

        matches: list[Chunk] = []
        for chunk_id in self._chunk_order:
            document = self._documents[chunk_id]
            if not _passes_filters(
                document.chunk,
                corpus_id=corpus_id,
                corpus_version=corpus_version,
                source_ids=source_id_filter,
            ):
                continue
            if query_citation_keys.intersection(document.citation_keys):
                matches.append(document.chunk)

        matches.sort(key=lambda chunk: (chunk.citation_label, chunk.chunk_id))
        return matches

    def _tokens_for_chunk(self, chunk: Chunk) -> list[str]:
        tokens = self.tokenizer.tokenize(chunk.text)
        tokens.extend(self.tokenizer.tokenize(chunk.citation_label) * self.config.citation_weight)
        tokens.extend(self.tokenizer.tokenize(chunk.title) * self.config.title_weight)
        heading_text = " ".join(chunk.heading_path)
        tokens.extend(self.tokenizer.tokenize(heading_text) * self.config.heading_weight)
        return tokens

    def _bm25_score(self, document: _IndexedDocument, query_tokens: Sequence[str]) -> float:
        if self._avg_doc_length <= 0 or document.length == 0:
            return 0.0

        score = 0.0
        for token in query_tokens:
            term_frequency = document.term_freq.get(token, 0)
            if term_frequency == 0:
                continue
            idf = self._idf(token)
            denominator = term_frequency + self.config.k1 * (
                1 - self.config.b + self.config.b * document.length / self._avg_doc_length
            )
            score += idf * (term_frequency * (self.config.k1 + 1)) / denominator
        return score

    def _idf(self, token: str) -> float:
        document_frequency = self._doc_freq.get(token, 0)
        if document_frequency == 0 or not self._documents:
            return 0.0
        numerator = len(self._documents) - document_frequency + 0.5
        denominator = document_frequency + 0.5
        return math.log(1 + numerator / denominator)


def extract_citation_keys(text: str) -> set[str]:
    """Extract normalized citation keys from rule references in text."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    keys: set[str] = set()
    for match in _RULE_REFERENCE_RE.finditer(text):
        authority = (match.group("authority") or "").lower()
        has_rule_word = bool(match.group("rule"))
        number = match.group("number")
        markers = [marker.lower() for marker in _MARKER_RE.findall(match.group("markers"))]
        full_reference = number + "".join(markers)

        if not has_rule_word and not authority and not markers:
            continue

        _add_citation_reference_keys(
            keys,
            authority=authority,
            has_rule_word=has_rule_word,
            number=number,
            markers=markers,
            full_reference=full_reference,
        )

    return keys


def _add_citation_reference_keys(
    keys: set[str],
    *,
    authority: str,
    has_rule_word: bool,
    number: str,
    markers: Sequence[str],
    full_reference: str,
) -> None:
    keys.add(full_reference)
    if markers:
        cumulative = number
        for marker in markers:
            cumulative += marker
            keys.add(cumulative)
    if has_rule_word:
        keys.add(f"rule{full_reference}")
    if authority:
        keys.add(f"{authority}{full_reference}")
        if has_rule_word:
            keys.add(f"{authority}rule{full_reference}")


def _expand_token(raw: str) -> list[str]:
    expanded: list[str] = []
    lowered = raw.lower()

    if _NUMBER_RE.match(raw) and "(" in raw:
        _append_unique(expanded, raw)
        _append_unique(expanded, lowered)
        number_match = _NUMBER_RE.match(raw)
        if number_match is None:
            return expanded
        number = number_match.group(0)
        _append_unique(expanded, number)
        cumulative = number
        for marker in _MARKER_RE.findall(raw):
            normalized_marker = marker.lower()
            cumulative += normalized_marker
            _append_unique(expanded, cumulative)
            _append_unique(expanded, normalized_marker)
        return expanded

    if raw.startswith("("):
        _append_unique(expanded, raw)
        _append_unique(expanded, lowered)
        for marker in _MARKER_RE.findall(raw):
            _append_unique(expanded, marker.lower())
        return expanded

    if _UPPERCASE_TERM_RE.match(raw) and any(character.isalpha() for character in raw):
        _append_unique(expanded, raw)
        _append_unique(expanded, lowered)
        return expanded

    _append_unique(expanded, lowered)
    return expanded


def _append_unique(tokens: list[str], token: str) -> None:
    if token and token not in tokens:
        tokens.append(token)


def _unique_preserving_order(tokens: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return unique


def _has_citation_signal(text: str) -> bool:
    return bool(_CITATION_SIGNAL_RE.search(text))


def _passes_filters(
    chunk: Chunk,
    *,
    corpus_id: str | None,
    corpus_version: str | None,
    source_ids: set[str] | None,
) -> bool:
    if corpus_id is not None and chunk.corpus_id != corpus_id:
        return False
    if corpus_version is not None and chunk.corpus_version != corpus_version:
        return False
    if source_ids is not None and chunk.source_id not in source_ids:
        return False
    return True
