from __future__ import annotations

from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def test_ci_workflow_runs_default_and_container_verify_profiles() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "python -m scripts.verify default" in workflow
    assert "python -m scripts.verify container" in workflow
    assert "requires_browser" not in workflow
    assert "requires_qdrant" not in workflow
    assert "live_openai" not in workflow
    assert "OPENAI_API_KEY" not in workflow


def test_ci_workflow_keeps_optional_smokes_out_of_default_job() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "docker compose up" not in workflow
    assert "docker build" not in workflow
    assert "playwright install" not in workflow
    assert ".[browser]" not in workflow
    assert ".[qdrant]" not in workflow
