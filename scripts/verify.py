from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

VerifyProfile = Literal[
    "default",
    "browser",
    "qdrant",
    "openai",
    "models",
    "container",
    "full-local",
]

DEFAULT_TEST_MARKER = (
    "not live_openai and not requires_browser and not requires_qdrant and not "
    "requires_model_download"
)


@dataclass(frozen=True)
class VerifyCommand:
    name: str
    argv: list[str]


def build_commands(
    *,
    profile: str,
    python_executable: str,
    reports_dir: Path,
) -> list[VerifyCommand]:
    default_commands = [
        VerifyCommand(
            name="lint",
            argv=[python_executable, "-m", "ruff", "check", "app", "tests", "scripts"],
        ),
        VerifyCommand(name="typecheck", argv=[python_executable, "-m", "mypy", "app"]),
        VerifyCommand(
            name="test",
            argv=[python_executable, "-m", "pytest", "-m", DEFAULT_TEST_MARKER],
        ),
        VerifyCommand(
            name="eval",
            argv=[
                python_executable,
                "-m",
                "scripts.run_evals",
                "--reports-dir",
                str(reports_dir),
            ],
        ),
    ]
    optional_commands = {
        "browser": [
            VerifyCommand(
                name="test-browser",
                argv=[python_executable, "-m", "pytest", "-m", "requires_browser"],
            )
        ],
        "qdrant": [
            VerifyCommand(
                name="test-qdrant",
                argv=[python_executable, "-m", "pytest", "-m", "requires_qdrant"],
            )
        ],
        "openai": [
            VerifyCommand(
                name="test-openai",
                argv=[python_executable, "-m", "pytest", "-m", "live_openai"],
            )
        ],
        "models": [
            VerifyCommand(
                name="test-model-downloads",
                argv=[python_executable, "-m", "pytest", "-m", "requires_model_download"],
            )
        ],
        "container": [
            VerifyCommand(
                name="test-container-config",
                argv=[python_executable, "-m", "pytest", "tests/unit/test_container_config.py"],
            ),
            VerifyCommand(name="compose-config", argv=["docker", "compose", "config"]),
            VerifyCommand(
                name="compose-app-config",
                argv=["docker", "compose", "--profile", "app", "config"],
            ),
        ],
    }

    if profile == "default":
        return default_commands
    if profile == "browser":
        return optional_commands["browser"]
    if profile == "qdrant":
        return optional_commands["qdrant"]
    if profile == "openai":
        return optional_commands["openai"]
    if profile == "models":
        return optional_commands["models"]
    if profile == "container":
        return optional_commands["container"]
    if profile == "full-local":
        return default_commands + optional_commands["browser"] + optional_commands["qdrant"]
    raise ValueError(
        "unknown verification profile: "
        f"{profile}. Expected one of: default, browser, qdrant, openai, models, "
        "container, full-local"
    )


def run_commands(commands: Sequence[VerifyCommand], *, dry_run: bool = False) -> int:
    for command in commands:
        printable = " ".join(command.argv)
        print(f"[{command.name}] {printable}", flush=True)
        if dry_run:
            continue
        completed = subprocess.run(command.argv, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run RegLens verification profiles for agents and local development."
    )
    parser.add_argument(
        "profile",
        choices=[
            "default",
            "browser",
            "qdrant",
            "openai",
            "models",
            "container",
            "full-local",
        ],
        nargs="?",
        default="default",
        help="Verification profile to run.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Directory for eval reports in the default/full-local profiles.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run module-based commands.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    args = parser.parse_args(argv)
    commands = build_commands(
        profile=args.profile,
        python_executable=args.python,
        reports_dir=args.reports_dir,
    )
    return run_commands(commands, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
