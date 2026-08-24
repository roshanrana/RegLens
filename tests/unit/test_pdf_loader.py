from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.errors import DependencyUnavailableError
from app.ingestion import loaders
from app.ingestion.loaders import PdfCorpusLoader


def test_pdf_loader_extracts_page_sections_with_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "finra-rules.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake bytes for deterministic test")
    _install_fake_pypdf(
        monkeypatch,
        pages=[
            (
                "Rule 1030(b). Retention Period\n"
                "Records required by this rulebook must be retained for six years."
            ),
            (
                "Rule 1045. Supervisory Review\n"
                "Supervisory reviews must be documented and available for audit."
            ),
        ],
        metadata={"/Title": "FINRA PDF Rulebook"},
    )

    result = PdfCorpusLoader().load(
        pdf_path,
        corpus_id="pdf-finra",
        corpus_name="PDF FINRA Rulebook",
        version="2026-pdf",
    )

    assert result.errors == []
    assert result.source.document_type == "pdf"
    assert result.source.title == "FINRA PDF Rulebook"
    assert result.source.checksum
    assert result.source.metadata["pdf_metadata"]["title"] == "FINRA PDF Rulebook"
    assert len(result.sections) == 2

    first, second = result.sections
    assert first.title == "Rule 1030(b). Retention Period"
    assert first.citation_label == "FINRA Rule 1030(b)"
    assert first.page_number == 1
    assert first.metadata["page_number"] == 1
    assert first.metadata["extraction_method"] == "pypdf"
    assert first.metadata["source_checksum"] == result.source.checksum
    assert first.metadata["corpus_version"] == "2026-pdf"
    assert "six years" in first.text

    assert second.title == "Rule 1045. Supervisory Review"
    assert second.citation_label == "FINRA Rule 1045"
    assert second.page_number == 2


def test_pdf_loader_splits_multiple_rule_headings_on_same_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "multi-rule-page.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake bytes for deterministic multi-rule test")
    page_text = (
        "Rule 1030(b). Retention Period\n"
        "Records required by this rulebook must be retained for six years.\n\n"
        "Rule 1045. Supervisory Review\n"
        "Supervisory reviews must be documented and available for audit."
    )
    _install_fake_pypdf(
        monkeypatch,
        pages=[page_text],
        metadata={"/Title": "FINRA PDF Rulebook"},
    )

    result = PdfCorpusLoader().load(
        pdf_path,
        corpus_id="pdf-finra",
        corpus_name="PDF FINRA Rulebook",
        version="2026-pdf",
    )

    assert result.errors == []
    assert len(result.sections) == 2
    assert [section.title for section in result.sections] == [
        "Rule 1030(b). Retention Period",
        "Rule 1045. Supervisory Review",
    ]
    assert [section.citation_label for section in result.sections] == [
        "FINRA Rule 1030(b)",
        "FINRA Rule 1045",
    ]
    assert [section.page_number for section in result.sections] == [1, 1]
    assert [section.heading_path for section in result.sections] == [
        ["FINRA PDF Rulebook", "Rule 1030(b). Retention Period"],
        ["FINRA PDF Rulebook", "Rule 1045. Supervisory Review"],
    ]
    assert len({section.section_id for section in result.sections}) == 2
    assert result.sections[0].start_char == 0
    assert result.sections[0].end_char is not None
    assert result.sections[1].start_char is not None
    assert result.sections[1].end_char is not None
    assert result.sections[1].start_char >= result.sections[0].end_char
    assert result.sections[1].end_char <= len(page_text)
    assert "six years" in result.sections[0].text
    assert "Supervisory reviews" not in result.sections[0].text
    assert "Supervisory reviews" in result.sections[1].text
    assert result.sections[0].metadata["split_strategy"] == "rule_heading"
    assert result.sections[1].metadata["split_strategy"] == "rule_heading"
    assert result.sections[0].metadata["rule_number"] == "1030(b)"
    assert result.sections[1].metadata["rule_number"] == "1045"
    assert result.sections[0].metadata["page_number"] == 1
    assert result.sections[1].metadata["source_checksum"] == result.source.checksum

    repeat = PdfCorpusLoader().load(
        pdf_path,
        corpus_id="pdf-finra",
        corpus_name="PDF FINRA Rulebook",
        version="2026-pdf",
    )
    assert [section.section_id for section in repeat.sections] == [
        section.section_id for section in result.sections
    ]


def test_pdf_loader_does_not_split_mid_sentence_rule_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "rule-reference-page.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake bytes for deterministic reference test")
    _install_fake_pypdf(
        monkeypatch,
        pages=[
            (
                "Rule 1030(b). Retention Period\n"
                "Records required by this rulebook must be retained for six years.\n"
                "This paragraph mentions Rule 9999 mid-sentence for cross-reference only.\n"
                "Rule 8888 is mentioned at the start of a sentence but is not a heading."
            ),
        ],
        metadata={"/Title": "FINRA PDF Rulebook"},
    )

    result = PdfCorpusLoader().load(
        pdf_path,
        corpus_id="pdf-finra",
        corpus_name="PDF FINRA Rulebook",
        version="2026-pdf",
    )

    assert result.errors == []
    assert len(result.sections) == 1
    assert result.sections[0].citation_label == "FINRA Rule 1030(b)"
    assert "Rule 9999" in result.sections[0].text
    assert "Rule 8888" in result.sections[0].text


def test_pdf_loader_splits_fca_headings_on_same_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "fca-rules.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake bytes for deterministic fca test")
    _install_fake_pypdf(
        monkeypatch,
        pages=[
            (
                "COBS 9.2.1R Suitability reports\n"
                "A firm must take reasonable steps to ensure a personal "
                "recommendation is suitable.\n\n"
                "SYSC 6.1.1R Compliance oversight\n"
                "A firm must establish and maintain adequate policies and procedures."
            ),
        ],
        metadata={"/Title": "FCA PDF Handbook"},
    )

    result = PdfCorpusLoader().load(
        pdf_path,
        corpus_id="pdf-fca",
        corpus_name="PDF FCA Handbook",
        version="2026-pdf",
    )

    assert result.errors == []
    assert [section.citation_label for section in result.sections] == [
        "FCA COBS 9.2.1R",
        "FCA SYSC 6.1.1R",
    ]
    assert [section.page_number for section in result.sections] == [1, 1]
    assert "personal recommendation" in result.sections[0].text
    assert "adequate policies" in result.sections[1].text


def test_pdf_loader_reports_unextractable_pdf_without_crashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake scanned bytes")
    _install_fake_pypdf(monkeypatch, pages=["", None], metadata={"/Title": "Scanned Rules"})

    result = PdfCorpusLoader().load(
        pdf_path,
        corpus_id="scanned",
        corpus_name="Scanned Rulebook",
        version="2026-scan",
    )

    assert result.sections == []
    assert result.errors == ["PDF did not contain extractable text"]
    assert result.source.title == "Scanned Rules"


def test_pdf_loader_raises_dependency_error_when_pypdf_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "rules.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    _install_missing_pypdf(monkeypatch)

    with pytest.raises(DependencyUnavailableError) as exc_info:
        PdfCorpusLoader().load(pdf_path)

    assert "pypdf" in exc_info.value.message
    assert exc_info.value.details["package"] == "pypdf"
    assert exc_info.value.details["extra"] == "pdf"
    assert ".[pdf]" in exc_info.value.details["install_hint"]


def _install_fake_pypdf(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pages: list[str | None],
    metadata: dict[str, Any] | None = None,
) -> None:
    original_import_module = importlib.import_module

    class FakePage:
        def __init__(self, text: str | None) -> None:
            self._text = text

        def extract_text(self) -> str | None:
            return self._text

    class FakePdfReader:
        def __init__(self, _: str | Path) -> None:
            self.metadata = metadata or {}
            self.pages = [FakePage(text) for text in pages]

    def fake_import_module(name: str, package: str | None = None) -> Any:
        if name == "pypdf":
            return SimpleNamespace(PdfReader=FakePdfReader)
        return original_import_module(name, package)

    monkeypatch.setattr(loaders.importlib, "import_module", fake_import_module)


def _install_missing_pypdf(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None) -> Any:
        if name == "pypdf":
            raise ImportError("No module named pypdf")
        return original_import_module(name, package)

    monkeypatch.setattr(loaders.importlib, "import_module", fake_import_module)
