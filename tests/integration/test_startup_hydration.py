from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_mock_startup_hydrates_retrieval_from_persisted_chunks(
    tmp_path: Path,
    fixture_rulebook_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        rag_mode="mock",
        default_top_k=4,
        database_url=f"sqlite:///{(tmp_path / 'hydration.db').as_posix()}",
    )

    with TestClient(create_app(settings)) as client:
        ingest_response = client.post(
            "/admin/ingest",
            json={
                "path": str(fixture_rulebook_path),
                "input_type": "markdown",
                "corpus_id": "hydrated-finra",
                "corpus_name": "Hydrated FINRA Rulebook",
                "version": "2026-hydrated",
            },
        )

        assert ingest_response.status_code == 200

    with TestClient(create_app(settings)) as restarted_client:
        retrieve_response = restarted_client.post(
            "/retrieve",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "hydrated-finra",
                "corpus_version": "2026-hydrated",
                "top_k": 2,
            },
        )

        assert retrieve_response.status_code == 200
        retrieve_body = retrieve_response.json()
        assert retrieve_body["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
        assert retrieve_body["diagnostics"]["filters"] == {
            "corpus_id": "hydrated-finra",
            "corpus_version": "2026-hydrated",
        }

        query_response = restarted_client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "hydrated-finra",
                "corpus_version": "2026-hydrated",
                "top_k": 2,
            },
        )

        assert query_response.status_code == 200
        query_body = query_response.json()
        assert query_body["citations"][0]["citation_label"] == "FINRA Rule 1030(b)"
        assert query_body["citations"][0]["verification_status"] == "verified"

        fixture_response = restarted_client.post(
            "/retrieve",
            json={
                "question": "What must automated compliance tools include?",
                "corpus_id": "finra-synthetic",
                "corpus_version": "2026-08-19",
                "top_k": 1,
            },
        )

        assert fixture_response.status_code == 200
        assert fixture_response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1040(a)"
