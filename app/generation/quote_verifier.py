"""Deterministic quote and span verification for grounded answers."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteMatch:
    source_name: str
    start: int
    end: int
    matched_text: str

    @property
    def source_span(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


@dataclass(frozen=True)
class QuoteVerification:
    verified: bool
    quote: str
    match: QuoteMatch | None = None
    reason: str | None = None


class QuoteVerifier:
    """Verify that quoted support appears verbatim in retrieved evidence text.

    Matching is case-insensitive and whitespace-normalized, but it does not
    remove punctuation or invent fuzzy matches. That makes failures predictable
    enough to use as an audit gate.
    """

    def verify(
        self,
        quote: str,
        sources: Mapping[str, str],
        *,
        source_span: dict[str, int] | None = None,
    ) -> QuoteVerification:
        if not isinstance(quote, str) or not quote.strip():
            return QuoteVerification(verified=False, quote=quote, reason="empty_quote")
        if not sources:
            return QuoteVerification(verified=False, quote=quote, reason="no_sources")

        if source_span is not None:
            return self._verify_with_span(quote, sources, source_span)

        for source_name, text in sources.items():
            match = find_quote_span(text, quote, source_name=source_name)
            if match is not None:
                return QuoteVerification(verified=True, quote=quote, match=match)

        return QuoteVerification(verified=False, quote=quote, reason="quote_not_found")

    def _verify_with_span(
        self,
        quote: str,
        sources: Mapping[str, str],
        source_span: dict[str, int],
    ) -> QuoteVerification:
        span = _coerce_span(source_span)
        if span is None:
            return QuoteVerification(verified=False, quote=quote, reason="invalid_source_span")

        start, end = span
        for source_name, text in sources.items():
            if end > len(text):
                continue
            candidate = text[start:end]
            if equivalent_text(candidate, quote):
                return QuoteVerification(
                    verified=True,
                    quote=quote,
                    match=QuoteMatch(
                        source_name=source_name,
                        start=start,
                        end=end,
                        matched_text=candidate,
                    ),
                )

        return QuoteVerification(verified=False, quote=quote, reason="source_span_mismatch")


def find_quote_span(text: str, quote: str, *, source_name: str = "text") -> QuoteMatch | None:
    """Return the original-text span for a normalized quote match."""

    if not isinstance(text, str) or not isinstance(quote, str):
        raise TypeError("text and quote must be strings")
    if not text or not quote.strip():
        return None

    normalized_text, text_map = _normalize_with_char_map(text)
    normalized_quote, _ = _normalize_with_char_map(quote)
    if not normalized_quote:
        return None

    normalized_start = normalized_text.find(normalized_quote)
    if normalized_start < 0:
        return None

    normalized_end = normalized_start + len(normalized_quote)
    original_start = text_map[normalized_start]
    original_end = text_map[normalized_end - 1] + 1
    return QuoteMatch(
        source_name=source_name,
        start=original_start,
        end=original_end,
        matched_text=text[original_start:original_end],
    )


def equivalent_text(left: str, right: str) -> bool:
    """Return whether two strings match after quote-verifier normalization."""

    normalized_left, _ = _normalize_with_char_map(left)
    normalized_right, _ = _normalize_with_char_map(right)
    return normalized_left == normalized_right


def _coerce_span(source_span: dict[str, int]) -> tuple[int, int] | None:
    if set(source_span) != {"start", "end"}:
        return None
    start = source_span["start"]
    end = source_span["end"]
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or end < start:
        return None
    return start, end


def _normalize_with_char_map(text: str) -> tuple[str, list[int]]:
    normalized_chars: list[str] = []
    char_map: list[int] = []
    previous_was_space = False

    for original_index, char in enumerate(text):
        for normalized_char in unicodedata.normalize("NFKC", char):
            if normalized_char.isspace():
                if normalized_chars and not previous_was_space:
                    normalized_chars.append(" ")
                    char_map.append(original_index)
                    previous_was_space = True
                continue

            for folded_char in normalized_char.casefold():
                normalized_chars.append(folded_char)
                char_map.append(original_index)
            previous_was_space = False

    if normalized_chars and normalized_chars[-1] == " ":
        normalized_chars.pop()
        char_map.pop()

    return "".join(normalized_chars), char_map
