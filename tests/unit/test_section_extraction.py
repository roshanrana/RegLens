from app.ingestion.loaders import DocumentSource, extract_markdown_sections


def _source() -> DocumentSource:
    return DocumentSource(
        source_id="src_test",
        corpus_id="finra-synthetic",
        corpus_name="FINRA Synthetic Rulebook",
        version="v1",
        title="Synthetic",
        url="https://example.test/source",
        raw_storage_uri="fixture.md",
        retrieved_at=None,
        checksum="abc123",
        metadata={"fixture": True},
    )


def test_section_extraction_skips_container_headings_and_keeps_leaf_sections() -> None:
    markdown = """
# FINRA Synthetic Rulebook

## Rule 2000. Container

### Rule 2000(a). Leaf

Leaf section body.

### Rule 2000(b). Second Leaf

Second section body.
"""

    sections = extract_markdown_sections(markdown, source=_source())

    assert [section.citation_label for section in sections] == [
        "FINRA Rule 2000(a)",
        "FINRA Rule 2000(b)",
    ]
    assert all(section.text for section in sections)


def test_section_extraction_preserves_markdown_tables() -> None:
    markdown = """
# FINRA Synthetic Rulebook

## Rule 2100. Tables

### Rule 2100(a). Disclosure Grid

Members must retain disclosure details.

| Item | Detail |
| --- | --- |
| Fee | Advisory fee |
"""

    sections = extract_markdown_sections(markdown, source=_source())

    assert len(sections) == 1
    assert "| Item | Detail |" in sections[0].text
    assert "| Fee | Advisory fee |" in sections[0].text


def test_section_ids_are_stable_for_same_heading_identity() -> None:
    markdown = """
# FINRA Synthetic Rulebook

## Rule 2200. Stable

### Rule 2200(a). Stable Identity

First body.
"""

    first = extract_markdown_sections(markdown, source=_source())
    second = extract_markdown_sections(
        markdown.replace("First body.", "Updated body."),
        source=_source(),
    )

    assert first[0].section_id == second[0].section_id
    assert first[0].start_char is not None
    assert first[0].end_char is not None
