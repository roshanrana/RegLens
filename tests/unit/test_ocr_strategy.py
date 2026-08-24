from __future__ import annotations

import tomllib
from pathlib import Path

OCR_STRATEGY_PATH = Path("docs/ocr-strategy.md")
PYPROJECT_PATH = Path("pyproject.toml")


def test_ocr_strategy_documents_fail_closed_scanned_pdf_contract() -> None:
    strategy = OCR_STRATEGY_PATH.read_text(encoding="utf-8")

    assert "scanned or image-only PDFs" in strategy
    assert "corpus_load_error" in strategy
    assert "No source, section, chunk, vector, or retrieval index state is persisted" in strategy
    assert "fail" in strategy.lower()
    assert "closed" in strategy.lower()


def test_ocr_strategy_requires_opt_in_optional_dependencies() -> None:
    strategy = OCR_STRATEGY_PATH.read_text(encoding="utf-8")

    assert "REGLENS_ENABLE_PDF_OCR=false" in strategy
    assert "optional dependency group" in strategy
    assert "Default install and default verification must not require OCR packages" in strategy
    assert "skip cleanly" in strategy


def test_base_dependencies_do_not_include_ocr_packages() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    dependency_names = {
        dependency.split("[", 1)[0].split(">=", 1)[0] for dependency in dependencies
    }

    assert "pytesseract" not in dependency_names
    assert "easyocr" not in dependency_names
    assert "paddleocr" not in dependency_names
