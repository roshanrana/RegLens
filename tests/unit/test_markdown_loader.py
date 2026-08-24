from pathlib import Path

from app.ingestion.loaders import MarkdownCorpusLoader

FIXTURE_PATH = Path("app/evals/fixtures/synthetic_rulebook.md")


def test_markdown_loader_returns_sections_with_source_metadata() -> None:
    result = MarkdownCorpusLoader().load(FIXTURE_PATH)

    assert result.errors == []
    assert result.source.source_id == "finra-synthetic-rulebook"
    assert result.source.corpus_id == "finra-synthetic"
    assert result.source.version == "2026-08-19"
    assert result.source.checksum
    assert len(result.sections) >= 8


def test_markdown_loader_preserves_citation_labels_and_heading_paths() -> None:
    result = MarkdownCorpusLoader().load(FIXTURE_PATH)

    written_policies = next(
        section for section in result.sections if section.citation_label == "FINRA Rule 1000(a)"
    )

    assert written_policies.title == "Rule 1000(a). Written Policies"
    assert written_policies.heading_path == [
        "FINRA Synthetic Rulebook",
        "Rule 1000. General Standards",
        "Rule 1000(a). Written Policies",
    ]
    assert "written policies" in written_policies.text
    assert written_policies.metadata["source_checksum"] == result.source.checksum
    assert written_policies.metadata["corpus_version"] == "2026-08-19"


def test_markdown_loader_handles_empty_markdown_without_crashing() -> None:
    result = MarkdownCorpusLoader().load_text(
        "",
        corpus_id="empty",
        corpus_name="Empty",
        version="v1",
    )

    assert result.errors == []
    assert result.sections == []
    assert result.source.corpus_id == "empty"


def test_markdown_loader_regenerates_source_id_when_corpus_override_conflicts() -> None:
    first = MarkdownCorpusLoader().load(
        FIXTURE_PATH,
        corpus_id="override-a",
        corpus_name="Override A",
        version="2026-a",
    )
    second = MarkdownCorpusLoader().load(
        FIXTURE_PATH,
        corpus_id="override-b",
        corpus_name="Override B",
        version="2026-b",
    )

    assert first.errors == []
    assert second.errors == []
    assert first.source.source_id != "finra-synthetic-rulebook"
    assert second.source.source_id != "finra-synthetic-rulebook"
    assert first.source.source_id != second.source.source_id
    assert {section.source_id for section in first.sections} == {first.source.source_id}
    assert {section.source_id for section in second.sections} == {second.source.source_id}


def test_markdown_loader_preserves_front_matter_source_id_when_override_matches() -> None:
    result = MarkdownCorpusLoader().load(
        FIXTURE_PATH,
        corpus_id="finra-synthetic",
        corpus_name="FINRA Synthetic Rulebook",
        version="2026-08-19",
    )

    assert result.errors == []
    assert result.source.source_id == "finra-synthetic-rulebook"
