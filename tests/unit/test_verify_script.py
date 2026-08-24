from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify import build_commands


def test_default_verify_profile_runs_fake_mode_quality_gate() -> None:
    commands = build_commands(
        profile="default",
        python_executable="python",
        reports_dir=Path("out"),
    )

    assert [command.name for command in commands] == ["lint", "typecheck", "test", "eval"]
    assert commands[0].argv == ["python", "-m", "ruff", "check", "app", "tests", "scripts"]
    assert commands[1].argv == ["python", "-m", "mypy", "app"]
    assert commands[2].argv == [
        "python",
        "-m",
        "pytest",
        "-m",
        "not live_openai and not requires_browser and not requires_qdrant and not "
        "requires_model_download",
    ]
    assert commands[3].argv == [
        "python",
        "-m",
        "scripts.run_evals",
        "--reports-dir",
        "out",
    ]


def test_optional_verify_profiles_run_only_marked_smokes() -> None:
    browser_commands = build_commands(
        profile="browser",
        python_executable="python",
        reports_dir=Path("reports"),
    )
    qdrant_commands = build_commands(
        profile="qdrant",
        python_executable="python",
        reports_dir=Path("reports"),
    )
    openai_commands = build_commands(
        profile="openai",
        python_executable="python",
        reports_dir=Path("reports"),
    )
    models_commands = build_commands(
        profile="models",
        python_executable="python",
        reports_dir=Path("reports"),
    )
    container_commands = build_commands(
        profile="container",
        python_executable="python",
        reports_dir=Path("reports"),
    )

    assert [command.argv for command in browser_commands] == [
        ["python", "-m", "pytest", "-m", "requires_browser"]
    ]
    assert [command.argv for command in qdrant_commands] == [
        ["python", "-m", "pytest", "-m", "requires_qdrant"]
    ]
    assert [command.argv for command in openai_commands] == [
        ["python", "-m", "pytest", "-m", "live_openai"]
    ]
    assert [command.argv for command in models_commands] == [
        ["python", "-m", "pytest", "-m", "requires_model_download"]
    ]
    assert [command.name for command in container_commands] == [
        "test-container-config",
        "compose-config",
        "compose-app-config",
    ]
    assert [command.argv for command in container_commands] == [
        ["python", "-m", "pytest", "tests/unit/test_container_config.py"],
        ["docker", "compose", "config"],
        ["docker", "compose", "--profile", "app", "config"],
    ]


def test_full_local_verify_profile_keeps_optional_smokes_explicit() -> None:
    commands = build_commands(
        profile="full-local",
        python_executable="python",
        reports_dir=Path("reports"),
    )

    assert [command.name for command in commands] == [
        "lint",
        "typecheck",
        "test",
        "eval",
        "test-browser",
        "test-qdrant",
    ]


def test_unknown_verify_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown verification profile"):
        build_commands(
            profile="everything",
            python_executable="python",
            reports_dir=Path("reports"),
        )
