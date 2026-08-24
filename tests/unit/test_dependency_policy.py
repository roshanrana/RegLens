import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_base_and_dev_dependencies_do_not_include_openai_sdk() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    base_dependencies = project.get("dependencies", [])
    dev_dependencies = project.get("optional-dependencies", {}).get("dev", [])

    assert "openai" not in _dependency_names(base_dependencies)
    assert "openai" not in _dependency_names(dev_dependencies)


def test_base_and_dev_dependencies_do_not_include_model_download_packages() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    base_dependencies = project.get("dependencies", [])
    dev_dependencies = project.get("optional-dependencies", {}).get("dev", [])
    disallowed = {"sentence-transformers", "transformers", "torch"}

    assert _dependency_names(base_dependencies).isdisjoint(disallowed)
    assert _dependency_names(dev_dependencies).isdisjoint(disallowed)


def _dependency_names(dependencies: list[str]) -> set[str]:
    names = set()
    for dependency in dependencies:
        normalized = dependency.split(";", maxsplit=1)[0].strip().lower()
        for separator in ("[", "<", ">", "=", "!", "~"):
            normalized = normalized.split(separator, maxsplit=1)[0]
        names.add(normalized.replace("_", "-"))
    return names
