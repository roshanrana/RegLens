from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixture_rulebook_path() -> Path:
    return Path("app/evals/fixtures/synthetic_rulebook.md")

