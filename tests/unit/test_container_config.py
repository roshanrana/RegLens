from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_runs_mock_safe_reglens_api_without_secrets() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "REGLENS_RAG_MODE=mock" in dockerfile
    assert "REGLENS_EMBEDDING_PROVIDER=fake" in dockerfile
    assert "REGLENS_LLM_PROVIDER=fake" in dockerfile
    assert "REGLENS_RERANKER_PROVIDER=fake" in dockerfile
    assert "REGLENS_DATABASE_URL=sqlite:////app/data/reglens.db" in dockerfile
    assert "OPENAI_API_KEY" not in dockerfile
    assert "COPY .env" not in dockerfile
    assert 'CMD ["python", "-m", "uvicorn", "app.main:app"' in dockerfile


def test_dockerignore_excludes_local_secrets_and_runtime_state() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in dockerignore
    assert ".env.*" in dockerignore
    assert ".venv/" in dockerignore
    assert "*.db" in dockerignore
    assert "reports/" in dockerignore
    assert "tmp/" in dockerignore


def test_compose_app_profile_keeps_default_services_mock_safe() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "reglens:" in compose
    assert "profiles:" in compose
    assert "- app" in compose
    assert "REGLENS_RAG_MODE: mock" in compose
    assert "REGLENS_DATABASE_URL: sqlite:////app/data/reglens.db" in compose
    assert "OPENAI_API_KEY" not in compose
    assert "qdrant/qdrant:v1.12.1" in compose
