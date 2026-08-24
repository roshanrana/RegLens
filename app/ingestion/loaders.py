from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from app.core.errors import DependencyUnavailableError
from app.domain.models import DocumentSection, DocumentSource
from app.ingestion.normalizers import (
    coerce_metadata_value,
    extract_front_matter,
    first_markdown_heading,
    normalize_markdown,
    normalize_text,
    strip_html_to_markdown,
)

_PDF_RULE_HEADING_RE = re.compile(
    r"(?i)^(?:(?:FINRA|FCA)\s+)?Rule\s+"
    r"[A-Za-z0-9.\-]+(?:\([^)]+\))*(?:\.(?:\s+.+)?|)$"
)
_PDF_FCA_HEADING_RE = re.compile(
    r"(?i)^(?:COBS|SYSC|PRIN|MAR)\s+\d+(?:\.\d+)*(?:[A-Z])?(?:\s+.+)?$"
)


@dataclass(frozen=True)
class LoadResult:
    source: DocumentSource
    sections: list[DocumentSection]
    errors: list[str] = field(default_factory=list)


class CorpusLoader(Protocol):
    def load(self, location: str | Path, **overrides: Any) -> LoadResult:
        ...


class MarkdownCorpusLoader:
    def load(self, location: str | Path, **overrides: Any) -> LoadResult:
        path = Path(location)
        options = dict(overrides)
        encoding = options.pop("encoding", "utf-8")
        raw_markdown = path.read_text(encoding=encoding)
        raw_storage_uri = options.pop("raw_storage_uri", None) or path.as_posix()
        return self.load_text(raw_markdown, raw_storage_uri=raw_storage_uri, **options)

    def load_text(
        self,
        markdown: str,
        *,
        raw_storage_uri: str | None = None,
        corpus_id: str | None = None,
        corpus_name: str | None = None,
        version: str | None = None,
        source_id: str | None = None,
        url: str | None = None,
        retrieved_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> LoadResult:
        front_matter, body = extract_front_matter(markdown)
        source_metadata = {**front_matter, **(metadata or {})}
        normalized_body = normalize_markdown(body)
        checksum = _sha256_hex(markdown)

        resolved_corpus_id = corpus_id or front_matter.get("corpus_id") or "default-corpus"
        resolved_corpus_name = corpus_name or front_matter.get("corpus_name") or "Default Corpus"
        resolved_version = version or front_matter.get("version") or "unversioned"
        resolved_url = url or front_matter.get("source_url") or front_matter.get("url")
        title = (
            front_matter.get("title")
            or first_markdown_heading(normalized_body)
            or resolved_corpus_name
        )
        resolved_source_id = source_id or _front_matter_source_id(
            front_matter,
            requested_corpus_id=corpus_id,
            requested_version=version,
        )
        if resolved_source_id is None:
            resolved_source_id = stable_source_id(
                corpus_id=resolved_corpus_id,
                version=resolved_version,
                raw_storage_uri=raw_storage_uri,
                title=title,
                url=resolved_url,
            )

        source = DocumentSource(
            source_id=resolved_source_id,
            corpus_id=resolved_corpus_id,
            corpus_name=resolved_corpus_name,
            version=resolved_version,
            title=title,
            url=resolved_url,
            raw_storage_uri=raw_storage_uri,
            retrieved_at=retrieved_at,
            checksum=checksum,
            metadata=source_metadata,
        )

        try:
            sections = extract_markdown_sections(
                normalized_body,
                source=source,
                effective_date=_parse_date(front_matter.get("effective_date")),
                page_number=_parse_int(front_matter.get("page_number")),
            )
            return LoadResult(source=source, sections=sections)
        except ValueError as exc:
            return LoadResult(source=source, sections=[], errors=[str(exc)])


class PlainTextCorpusLoader:
    def load(self, location: str | Path, **overrides: Any) -> LoadResult:
        path = Path(location)
        options = dict(overrides)
        encoding = options.pop("encoding", "utf-8")
        raw_text = path.read_text(encoding=encoding)
        raw_storage_uri = options.pop("raw_storage_uri", None) or path.as_posix()
        return self.load_text(raw_text, raw_storage_uri=raw_storage_uri, **options)

    def load_text(
        self,
        text: str,
        *,
        raw_storage_uri: str | None = None,
        corpus_id: str | None = None,
        corpus_name: str | None = None,
        version: str | None = None,
        source_id: str | None = None,
        url: str | None = None,
        title: str | None = None,
        retrieved_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> LoadResult:
        normalized = normalize_text(text)
        checksum = _sha256_hex(text)
        resolved_corpus_id = corpus_id or "default-corpus"
        resolved_corpus_name = corpus_name or "Default Corpus"
        resolved_version = version or "unversioned"
        resolved_title = title or _first_non_empty_line(normalized) or resolved_corpus_name
        resolved_source_id = source_id or stable_source_id(
            corpus_id=resolved_corpus_id,
            version=resolved_version,
            raw_storage_uri=raw_storage_uri,
            title=resolved_title,
            url=url,
        )

        source = DocumentSource(
            source_id=resolved_source_id,
            corpus_id=resolved_corpus_id,
            corpus_name=resolved_corpus_name,
            version=resolved_version,
            title=resolved_title,
            url=url,
            raw_storage_uri=raw_storage_uri,
            retrieved_at=retrieved_at,
            checksum=checksum,
            metadata=metadata or {},
        )

        if not normalized:
            return LoadResult(source=source, sections=[])

        citation_label = infer_citation_label(resolved_title, corpus_name=resolved_corpus_name)
        section = DocumentSection(
            section_id=stable_section_id(
                corpus_id=resolved_corpus_id,
                version=resolved_version,
                source_id=resolved_source_id,
                citation_label=citation_label,
                heading_path=[resolved_title],
            ),
            source_id=resolved_source_id,
            corpus_id=resolved_corpus_id,
            citation_label=citation_label,
            title=resolved_title,
            heading_path=[resolved_title],
            text=normalized,
            url=url,
            effective_date=None,
            page_number=None,
            start_char=0,
            end_char=len(normalized),
            metadata={
                "source_checksum": checksum,
                "corpus_version": resolved_version,
                "source_metadata": metadata or {},
            },
        )
        return LoadResult(source=source, sections=[section])


class PdfCorpusLoader:
    def load(self, location: str | Path, **overrides: Any) -> LoadResult:
        path = Path(location)
        options = dict(overrides)
        raw_storage_uri = options.pop("raw_storage_uri", None) or path.as_posix()
        raw_bytes = path.read_bytes()
        reader_class = _pypdf_reader_class()
        try:
            reader = reader_class(path)
        except Exception as exc:
            raise ValueError(f"failed to read PDF source: {exc}") from exc

        return self.load_reader(
            reader,
            raw_storage_uri=raw_storage_uri,
            fallback_title=path.stem,
            checksum=_sha256_bytes(raw_bytes),
            **options,
        )

    def load_reader(
        self,
        reader: Any,
        *,
        raw_storage_uri: str | None = None,
        fallback_title: str = "PDF document",
        checksum: str | None = None,
        corpus_id: str | None = None,
        corpus_name: str | None = None,
        version: str | None = None,
        source_id: str | None = None,
        url: str | None = None,
        title: str | None = None,
        retrieved_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> LoadResult:
        resolved_corpus_id = corpus_id or "default-corpus"
        resolved_corpus_name = corpus_name or "Default Corpus"
        resolved_version = version or "unversioned"
        pdf_metadata = _pdf_metadata(reader)
        resolved_title = (
            title
            or pdf_metadata.get("title")
            or _clean_title(fallback_title)
            or resolved_corpus_name
        )

        page_texts = _extract_pdf_page_texts(reader)
        resolved_checksum = checksum or _sha256_hex(
            "\n\n".join(page_text for _, page_text in page_texts)
        )
        source_metadata: dict[str, Any] = {
            **(metadata or {}),
            "extraction_method": "pypdf",
            "pdf_metadata": pdf_metadata,
        }
        resolved_source_id = source_id or stable_source_id(
            corpus_id=resolved_corpus_id,
            version=resolved_version,
            raw_storage_uri=raw_storage_uri,
            title=resolved_title,
            url=url,
        )

        source = DocumentSource(
            source_id=resolved_source_id,
            corpus_id=resolved_corpus_id,
            corpus_name=resolved_corpus_name,
            version=resolved_version,
            title=resolved_title,
            url=url,
            raw_storage_uri=raw_storage_uri,
            retrieved_at=retrieved_at,
            document_type="pdf",
            checksum=resolved_checksum,
            metadata=source_metadata,
        )

        if not page_texts:
            return LoadResult(
                source=source,
                sections=[],
                errors=["PDF did not contain extractable text"],
            )

        sections: list[DocumentSection] = []
        page_start = 0
        for page_number, page_text in page_texts:
            page_sections = _split_pdf_page_sections(
                page_text,
                source_title=resolved_title,
                page_number=page_number,
            )
            for page_section in page_sections:
                heading_path = _pdf_heading_path(
                    source_title=resolved_title,
                    page_number=page_number,
                    section_title=page_section.title,
                )
                citation_label = infer_citation_label(
                    page_section.title,
                    corpus_name=resolved_corpus_name,
                )
                sections.append(
                    DocumentSection(
                        section_id=stable_section_id(
                            corpus_id=resolved_corpus_id,
                            version=resolved_version,
                            source_id=resolved_source_id,
                            citation_label=citation_label,
                            heading_path=heading_path,
                        ),
                        source_id=resolved_source_id,
                        corpus_id=resolved_corpus_id,
                        corpus_version=resolved_version,
                        citation_label=citation_label,
                        title=page_section.title,
                        heading_path=heading_path,
                        text=page_section.text,
                        url=url,
                        effective_date=None,
                        page_number=page_number,
                        start_char=page_start + page_section.start_char,
                        end_char=page_start + page_section.end_char,
                        metadata={
                            "source_checksum": resolved_checksum,
                            "corpus_version": resolved_version,
                            "source_metadata": source_metadata,
                            "page_number": page_number,
                            "extraction_method": "pypdf",
                            "split_strategy": page_section.split_strategy,
                            "rule_number": extract_rule_number(page_section.title),
                        },
                    )
                )
            page_start += len(page_text) + 2

        return LoadResult(source=source, sections=sections)


class HtmlCorpusLoader(MarkdownCorpusLoader):
    def load(self, location: str | Path, **overrides: Any) -> LoadResult:
        path = Path(location)
        options = dict(overrides)
        encoding = options.pop("encoding", "utf-8")
        raw_html = path.read_text(encoding=encoding)
        raw_storage_uri = options.pop("raw_storage_uri", None) or path.as_posix()
        return self.load_text(raw_html, raw_storage_uri=raw_storage_uri, **options)

    def load_text(  # type: ignore[override]
        self,
        html: str,
        **overrides: Any,
    ) -> LoadResult:
        markdown = strip_html_to_markdown(html)
        return super().load_text(markdown, **overrides)


def extract_markdown_sections(
    markdown: str,
    *,
    source: DocumentSource,
    effective_date: date | None = None,
    page_number: int | None = None,
) -> list[DocumentSection]:
    normalized = normalize_markdown(markdown)
    if not normalized:
        return []

    line_starts = _line_start_offsets(normalized)
    lines = normalized.split("\n")
    headings: list[_Heading] = []
    heading_stack: dict[int, str] = {}

    for line_number, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        for existing_level in list(heading_stack):
            if existing_level >= level:
                del heading_stack[existing_level]
        heading_stack[level] = title
        heading_path = [heading_stack[index] for index in sorted(heading_stack)]

        heading_start = line_starts[line_number]
        body_start = heading_start + len(line)
        if body_start < len(normalized) and normalized[body_start] == "\n":
            body_start += 1

        headings.append(
            _Heading(
                level=level,
                title=title,
                heading_path=heading_path,
                heading_start=heading_start,
                body_start=body_start,
            )
        )

    sections: list[DocumentSection] = []
    for index, heading in enumerate(headings):
        next_heading_start = (
            headings[index + 1].heading_start if index + 1 < len(headings) else len(normalized)
        )
        raw_body = normalized[heading.body_start : next_heading_start]
        text = normalize_text(raw_body)

        if heading.level < 2 or not text:
            continue

        start_char = normalized.find(text, heading.body_start, next_heading_start)
        if start_char == -1:
            start_char = heading.body_start
        end_char = start_char + len(text)
        citation_label = infer_citation_label(heading.title, corpus_name=source.corpus_name)
        section_id = stable_section_id(
            corpus_id=source.corpus_id,
            version=source.version,
            source_id=source.source_id,
            citation_label=citation_label,
            heading_path=heading.heading_path,
        )

        sections.append(
            DocumentSection(
                section_id=section_id,
                source_id=source.source_id,
                corpus_id=source.corpus_id,
                citation_label=citation_label,
                title=heading.title,
                heading_path=heading.heading_path,
                text=text,
                url=source.url,
                effective_date=effective_date,
                page_number=page_number,
                start_char=start_char,
                end_char=end_char,
                metadata={
                    "heading_level": heading.level,
                    "source_checksum": source.checksum,
                    "corpus_version": source.version,
                    "source_metadata": source.metadata,
                    "rule_number": extract_rule_number(heading.title),
                },
            )
        )

    return sections


def infer_citation_label(title: str, *, corpus_name: str | None = None) -> str:
    title = title.strip()
    rule_match = re.match(
        r"(?i)^(?:(FINRA|FCA)\s+)?(Rule\s+[A-Za-z0-9.\-]+(?:\([^)]+\))*)",
        title,
    )
    if rule_match:
        prefix = (rule_match.group(1) or "").upper()
        rule = rule_match.group(2).rstrip(".")
        if prefix:
            return f"{prefix} {rule}"
        if corpus_name and "FINRA" in corpus_name.upper():
            return f"FINRA {rule}"
        return rule

    fca_match = re.match(r"(?i)^((?:COBS|SYSC|PRIN|MAR)\s+\d+(?:\.\d+)*(?:[A-Z])?)", title)
    if fca_match:
        return f"FCA {fca_match.group(1).upper()}"

    return title


def extract_rule_number(title: str) -> str | None:
    match = re.match(
        r"(?i)^(?:(?:FINRA|FCA)\s+)?Rule\s+([A-Za-z0-9.\-]+(?:\([^)]+\))*)",
        title.strip(),
    )
    return match.group(1).rstrip(".") if match else None


def _front_matter_source_id(
    front_matter: dict[str, str],
    *,
    requested_corpus_id: str | None,
    requested_version: str | None,
) -> str | None:
    source_id = front_matter.get("source_id")
    if not source_id:
        return None

    front_matter_corpus_id = front_matter.get("corpus_id")
    front_matter_version = front_matter.get("version")
    corpus_conflicts = (
        requested_corpus_id is not None and requested_corpus_id != front_matter_corpus_id
    )
    version_conflicts = requested_version is not None and requested_version != front_matter_version
    if corpus_conflicts or version_conflicts:
        return None
    return source_id


def stable_source_id(
    *,
    corpus_id: str,
    version: str,
    raw_storage_uri: str | None,
    title: str,
    url: str | None,
) -> str:
    seed = "|".join([corpus_id, version, url or "", raw_storage_uri or "", title])
    return "src_" + _sha256_hex(seed)[:16]


def stable_section_id(
    *,
    corpus_id: str,
    version: str,
    source_id: str,
    citation_label: str,
    heading_path: list[str],
) -> str:
    seed = "|".join([corpus_id, version, source_id, citation_label, " > ".join(heading_path)])
    return "sec_" + _sha256_hex(normalize_text(seed))[:24]


@dataclass(frozen=True)
class _Heading:
    level: int
    title: str
    heading_path: list[str]
    heading_start: int
    body_start: int


@dataclass(frozen=True)
class _PdfHeading:
    title: str
    start_char: int


@dataclass(frozen=True)
class _PdfPageSection:
    title: str
    text: str
    start_char: int
    end_char: int
    split_strategy: str


def _line_start_offsets(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer("\n", text):
        starts.append(match.end())
    return starts


def _parse_date(value: str | None) -> date | None:
    value = coerce_metadata_value(value)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    value = coerce_metadata_value(value)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _pypdf_reader_class() -> Any:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise DependencyUnavailableError(
            "pypdf is required for PDF ingestion",
            details={
                "package": "pypdf",
                "extra": "pdf",
                "install_hint": 'pip install -e ".[pdf]"',
            },
        ) from exc

    reader_class = getattr(pypdf, "PdfReader", None)
    if reader_class is None:
        raise DependencyUnavailableError(
            "pypdf.PdfReader is required for PDF ingestion",
            details={
                "package": "pypdf",
                "extra": "pdf",
                "install_hint": 'pip install -e ".[pdf]"',
            },
        )
    return reader_class


def _extract_pdf_page_texts(reader: Any) -> list[tuple[int, str]]:
    pages = getattr(reader, "pages", None)
    if pages is None:
        raise ValueError("PDF reader did not expose pages")

    page_texts: list[tuple[int, str]] = []
    try:
        enumerated_pages = enumerate(pages, start=1)
    except TypeError as exc:
        raise ValueError("PDF reader pages are not iterable") from exc

    for page_number, page in enumerated_pages:
        try:
            raw_text = page.extract_text()
        except Exception as exc:
            raise ValueError(f"failed to extract text from PDF page {page_number}: {exc}") from exc
        normalized = normalize_text(str(raw_text)) if raw_text is not None else ""
        if normalized:
            page_texts.append((page_number, normalized))
    return page_texts


def _pdf_metadata(reader: Any) -> dict[str, str]:
    raw_metadata = getattr(reader, "metadata", None)
    if raw_metadata is None:
        return {}

    fields = {
        "title": ("/Title", "Title", "title"),
        "author": ("/Author", "Author", "author"),
        "subject": ("/Subject", "Subject", "subject"),
        "creator": ("/Creator", "Creator", "creator"),
        "producer": ("/Producer", "Producer", "producer"),
        "creation_date": ("/CreationDate", "CreationDate", "creation_date"),
        "modification_date": ("/ModDate", "ModDate", "modification_date"),
    }
    parsed: dict[str, str] = {}
    for normalized_key, candidate_keys in fields.items():
        value = _metadata_value(raw_metadata, candidate_keys)
        if value is not None:
            parsed[normalized_key] = value
    return parsed


def _metadata_value(metadata: Any, candidate_keys: tuple[str, ...]) -> str | None:
    getter = getattr(metadata, "get", None)
    for key in candidate_keys:
        value: Any = None
        found = False
        if callable(getter):
            try:
                value = getter(key)
                found = value is not None
            except Exception:
                found = False
        if not found:
            try:
                value = metadata[key]
                found = value is not None
            except Exception:
                found = False
        if found:
            normalized = normalize_text(str(value))
            if normalized:
                return normalized
    return None


def _pdf_page_title(page_text: str, *, source_title: str, page_number: int) -> str:
    first_line = _first_non_empty_line(page_text)
    if first_line and (extract_rule_number(first_line) or len(first_line) <= 160):
        return first_line
    return f"{source_title} Page {page_number}"


def _split_pdf_page_sections(
    page_text: str,
    *,
    source_title: str,
    page_number: int,
) -> list[_PdfPageSection]:
    headings = _pdf_rule_headings(page_text)
    if not headings:
        return [
            _PdfPageSection(
                title=_pdf_page_title(
                    page_text,
                    source_title=source_title,
                    page_number=page_number,
                ),
                text=page_text,
                start_char=0,
                end_char=len(page_text),
                split_strategy="page",
            )
        ]

    sections: list[_PdfPageSection] = []
    for index, heading in enumerate(headings):
        start_char = 0 if index == 0 else heading.start_char
        end_char = (
            headings[index + 1].start_char if index + 1 < len(headings) else len(page_text)
        )
        section_text = normalize_text(page_text[start_char:end_char])
        if not section_text:
            continue
        sections.append(
            _PdfPageSection(
                title=heading.title,
                text=section_text,
                start_char=start_char,
                end_char=end_char,
                split_strategy="rule_heading",
            )
        )

    if sections:
        return sections
    return [
        _PdfPageSection(
            title=_pdf_page_title(
                page_text,
                source_title=source_title,
                page_number=page_number,
            ),
            text=page_text,
            start_char=0,
            end_char=len(page_text),
            split_strategy="page",
        )
    ]


def _pdf_rule_headings(page_text: str) -> list[_PdfHeading]:
    line_starts = _line_start_offsets(page_text)
    headings: list[_PdfHeading] = []
    for line_number, line in enumerate(page_text.split("\n")):
        title = line.strip()
        if not title or len(title) > 160:
            continue
        if not _is_pdf_rule_heading(title):
            continue
        start_char = line_starts[line_number] + (len(line) - len(line.lstrip()))
        headings.append(_PdfHeading(title=title, start_char=start_char))
    return headings


def _is_pdf_rule_heading(title: str) -> bool:
    return bool(_PDF_RULE_HEADING_RE.match(title) or _PDF_FCA_HEADING_RE.match(title))


def _pdf_heading_path(
    *,
    source_title: str,
    page_number: int,
    section_title: str,
) -> list[str]:
    del page_number
    if section_title == source_title:
        return [source_title]
    return [source_title, section_title]


def _clean_title(value: str) -> str | None:
    normalized = normalize_text(value)
    return normalized or None


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _first_non_empty_line(text: str) -> str | None:
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped
    return None
