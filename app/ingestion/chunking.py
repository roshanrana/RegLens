from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from app.domain.models import Chunk, DocumentSection
from app.ingestion.normalizers import normalize_text


@dataclass(frozen=True)
class ChunkingConfig:
    max_tokens: int = 700
    overlap_tokens: int = 120
    include_context_prefix: bool = True

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens must be zero or greater")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")


@dataclass(frozen=True)
class TokenSpan:
    text: str
    start: int
    end: int


class Tokenizer(Protocol):
    def spans(self, text: str) -> list[TokenSpan]:
        ...

    def count(self, text: str) -> int:
        ...


class ApproximateTokenizer:
    """Small deterministic tokenizer for tests and fake-mode ingestion."""

    _TOKEN_RE = re.compile(r"\S+")

    def spans(self, text: str) -> list[TokenSpan]:
        return [
            TokenSpan(match.group(0), match.start(), match.end())
            for match in self._TOKEN_RE.finditer(text)
        ]

    def count(self, text: str) -> int:
        return len(self.spans(text))


class Chunker:
    def __init__(
        self,
        config: ChunkingConfig | None = None,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        self.config = config or ChunkingConfig()
        self.tokenizer = tokenizer or ApproximateTokenizer()

    def chunk_sections(
        self,
        sections: list[DocumentSection],
        *,
        corpus_version: str | None = None,
        source_checksum: str | None = None,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        for section in sections:
            chunks.extend(
                self.chunk_section(
                    section,
                    corpus_version=corpus_version,
                    source_checksum=source_checksum,
                )
            )
        return chunks

    def chunk_section(
        self,
        section: DocumentSection,
        *,
        corpus_version: str | None = None,
        source_checksum: str | None = None,
    ) -> list[Chunk]:
        body_text = normalize_text(section.text)
        if not body_text:
            return []

        resolved_version = (
            corpus_version
            or _metadata_str(getattr(section, "corpus_version", None))
            or _metadata_str(section.metadata.get("corpus_version"))
            or _metadata_str(section.metadata.get("version"))
            or "unversioned"
        )
        resolved_checksum = (
            source_checksum or _metadata_str(section.metadata.get("source_checksum")) or ""
        )
        prefix = self._context_prefix(section) if self.config.include_context_prefix else ""
        prefix_tokens = self.tokenizer.count(prefix)
        body_budget = max(1, self.config.max_tokens - prefix_tokens)

        token_spans = self.tokenizer.spans(body_text)
        if not token_spans:
            return []

        windows = self._token_windows(token_spans, body_budget)
        section_chunk_count = len(windows)
        chunks: list[Chunk] = []

        for chunk_index, (start_index, end_index) in enumerate(windows):
            first_token = token_spans[start_index]
            last_token = token_spans[end_index - 1]
            chunk_body = body_text[first_token.start : last_token.end]
            chunk_text = self._compose_chunk_text(prefix, chunk_body)
            chunk_id = make_chunk_id(
                corpus_id=section.corpus_id,
                corpus_version=resolved_version,
                section_id=section.section_id,
                chunk_index=chunk_index,
                normalized_text=chunk_text,
            )
            char_base = section.start_char or 0
            chunk = Chunk(
                chunk_id=chunk_id,
                section_id=section.section_id,
                source_id=section.source_id,
                corpus_id=section.corpus_id,
                corpus_version=resolved_version,
                citation_label=section.citation_label,
                title=section.title,
                heading_path=list(section.heading_path),
                text=chunk_text,
                token_count=self.tokenizer.count(chunk_text),
                chunk_index=chunk_index,
                section_chunk_count=section_chunk_count,
                char_start=(
                    char_base + first_token.start
                    if section.start_char is not None
                    else first_token.start
                ),
                char_end=(
                    char_base + last_token.end
                    if section.start_char is not None
                    else last_token.end
                ),
                page_number=section.page_number,
                source_checksum=resolved_checksum,
                url=section.url,
                metadata={
                    "body_token_start": start_index,
                    "body_token_end": end_index,
                    "body_text": chunk_body,
                    "context_prefix": prefix,
                    "section_metadata": section.metadata,
                },
            )
            chunks.append(chunk)

        return chunks

    def _token_windows(
        self,
        token_spans: list[TokenSpan],
        body_budget: int,
    ) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        start = 0
        total = len(token_spans)
        step = max(1, body_budget - self.config.overlap_tokens)

        while start < total:
            end = min(total, start + body_budget)
            windows.append((start, end))
            if end == total:
                break
            start += step

        return windows

    def _context_prefix(self, section: DocumentSection) -> str:
        heading_path = " > ".join(section.heading_path)
        title_line = f"{section.citation_label}. {section.title}"
        return normalize_text(f"{title_line}\nHeading path: {heading_path}")

    def _compose_chunk_text(self, prefix: str, body: str) -> str:
        if not prefix:
            return normalize_text(body)
        return normalize_text(f"{prefix}\n\n{body}")


def make_chunk_id(
    *,
    corpus_id: str,
    corpus_version: str,
    section_id: str,
    chunk_index: int,
    normalized_text: str,
) -> str:
    seed = "|".join(
        [
            corpus_id,
            corpus_version,
            section_id,
            str(chunk_index),
            normalize_text(normalized_text),
        ]
    )
    return "chk_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def chunk_section(
    section: DocumentSection,
    *,
    source_checksum: str,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
    return Chunker(config=config).chunk_section(section, source_checksum=source_checksum)


def chunk_sections(
    sections: list[DocumentSection],
    *,
    source_checksum: str,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
    return Chunker(config=config).chunk_sections(sections, source_checksum=source_checksum)


def _metadata_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
