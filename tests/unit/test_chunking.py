from types import SimpleNamespace

from app.ingestion.chunking import Chunker, ChunkingConfig
from app.ingestion.loaders import DocumentSection


def _section(text: str) -> DocumentSection:
    return DocumentSection(
        section_id="sec_test",
        source_id="src_test",
        corpus_id="finra-synthetic",
        citation_label="FINRA Rule 1000(a)",
        title="Rule 1000(a). Written Policies",
        heading_path=[
            "FINRA Synthetic Rulebook",
            "Rule 1000. General Standards",
            "Rule 1000(a). Written Policies",
        ],
        text=text,
        url="https://example.test/rule-1000-a",
        effective_date=None,
        page_number=None,
        start_char=100,
        end_char=100 + len(text),
        metadata={"corpus_version": "v1", "source_checksum": "checksum123"},
    )


def test_short_section_becomes_single_contextual_chunk() -> None:
    chunks = Chunker().chunk_section(_section("Members must maintain written policies."))

    assert len(chunks) == 1
    assert chunks[0].section_chunk_count == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].citation_label == "FINRA Rule 1000(a)"
    assert chunks[0].source_id == "src_test"
    assert chunks[0].corpus_id == "finra-synthetic"
    assert chunks[0].corpus_version == "v1"
    assert chunks[0].source_checksum == "checksum123"
    assert chunks[0].text.startswith("FINRA Rule 1000(a). Rule 1000(a). Written Policies")
    assert "Heading path:" in chunks[0].text
    assert "Members must maintain written policies." in chunks[0].text


def test_long_section_chunks_with_overlap_and_budget() -> None:
    words = [f"token{i}" for i in range(90)]
    text = " ".join(words)
    chunker = Chunker(ChunkingConfig(max_tokens=35, overlap_tokens=5))

    chunks = chunker.chunk_section(_section(text))

    assert len(chunks) > 1
    assert all(chunk.section_chunk_count == len(chunks) for chunk in chunks)
    assert all(chunk.token_count <= 35 for chunk in chunks)

    first_body_tokens = chunks[0].metadata["body_text"].split()
    second_body_tokens = chunks[1].metadata["body_text"].split()
    assert first_body_tokens[-5:] == second_body_tokens[:5]


def test_empty_section_returns_no_chunks() -> None:
    empty_section = SimpleNamespace(**{**_section("placeholder").__dict__, "text": "   \n\n  "})
    assert Chunker().chunk_section(empty_section) == []


def test_chunk_sections_preserves_section_order() -> None:
    first = _section("first section body")
    second = DocumentSection(
        **{
            **first.__dict__,
            "section_id": "sec_second",
            "citation_label": "FINRA Rule 1000(b)",
            "title": "Rule 1000(b). Annual Review",
            "text": "second section body",
        }
    )

    chunks = Chunker().chunk_sections([first, second])

    assert [chunk.section_id for chunk in chunks] == ["sec_test", "sec_second"]
