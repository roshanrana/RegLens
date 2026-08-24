from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

_BLANK_LINE_RE = re.compile(r"\n{3,}")
_HORIZONTAL_SPACE_RE = re.compile(r"[ \t]+")


def normalize_newlines(text: str) -> str:
    """Normalize common source encodings and newline styles."""
    return text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")


def normalize_text(text: str) -> str:
    """Normalize free text while preserving Markdown-ish structure."""
    text = normalize_newlines(text).replace("\xa0", " ")
    normalized_lines: list[str] = []
    in_fence = False

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_fence = not in_fence
            normalized_lines.append(stripped)
            continue

        if in_fence:
            normalized_lines.append(line)
            continue

        if _looks_like_markdown_table_row(stripped):
            normalized_lines.append(_normalize_table_row(stripped))
        else:
            normalized_lines.append(_HORIZONTAL_SPACE_RE.sub(" ", stripped))

    normalized = "\n".join(normalized_lines).strip()
    return _BLANK_LINE_RE.sub("\n\n", normalized)


def normalize_markdown(markdown: str) -> str:
    """Normalize Markdown source without removing headings, rules, or tables."""
    return normalize_text(markdown)


def extract_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    """Extract a small YAML-like front matter block.

    This intentionally supports only simple `key: value` pairs so the ingestion
    slice has no PyYAML dependency.
    """
    markdown = normalize_newlines(markdown)
    lines = markdown.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, markdown

    metadata: dict[str, str] = {}
    end_index: int | None = None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            metadata[key] = value

    if end_index is None:
        return {}, markdown

    body = "\n".join(lines[end_index + 1 :])
    return metadata, body


def first_markdown_heading(markdown: str) -> str | None:
    for line in normalize_newlines(markdown).split("\n"):
        match = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def strip_html_to_markdown(html: str) -> str:
    parser = _MarkdownHTMLParser()
    parser.feed(html)
    parser.close()
    return normalize_markdown(parser.markdown)


def _looks_like_markdown_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _normalize_table_row(line: str) -> str:
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    return "| " + " | ".join(cells) + " |"


class _MarkdownHTMLParser(HTMLParser):
    _HEADING_LEVELS = {f"h{level}": level for level in range(1, 7)}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._tag_stack: list[str] = []
        self._table_row: list[str] | None = None
        self._table_rows: list[list[str]] = []

    @property
    def markdown(self) -> str:
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)

        if tag in self._HEADING_LEVELS:
            self._parts.append("\n\n" + "#" * self._HEADING_LEVELS[tag] + " ")
        elif tag in {"p", "div", "section", "article"}:
            self._parts.append("\n\n")
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag == "tr":
            self._table_row = []
        elif tag in {"td", "th"} and self._table_row is not None:
            self._table_row.append("")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in self._HEADING_LEVELS or tag in {"p", "div", "section", "article", "li"}:
            self._parts.append("\n")
        elif tag == "tr" and self._table_row is not None:
            self._table_rows.append(self._table_row)
            self._table_row = None
        elif tag == "table":
            self._flush_table()

        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == tag:
                del self._tag_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if not data:
            return
        text = data.strip()
        if not text:
            return

        if self._table_row is not None and self._current_tag() in {"td", "th"}:
            self._table_row[-1] = (self._table_row[-1] + " " + text).strip()
        else:
            self._parts.append(text + " ")

    def _current_tag(self) -> str | None:
        return self._tag_stack[-1] if self._tag_stack else None

    def _flush_table(self) -> None:
        if not self._table_rows:
            return

        max_columns = max(len(row) for row in self._table_rows)
        rows = [row + [""] * (max_columns - len(row)) for row in self._table_rows]
        header = rows[0]
        separator = ["---"] * max_columns

        self._parts.append("\n\n")
        self._parts.append("| " + " | ".join(header) + " |\n")
        self._parts.append("| " + " | ".join(separator) + " |\n")
        for row in rows[1:]:
            self._parts.append("| " + " | ".join(row) + " |\n")
        self._parts.append("\n")
        self._table_rows = []


def coerce_metadata_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
