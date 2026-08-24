from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_env="test", rag_mode="mock", default_top_k=4)
    return TestClient(create_app(settings))


def test_sources_list_and_detail_after_ingest(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    ingest_response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": "source-finra",
            "corpus_name": "Source FINRA Rulebook",
            "version": "2026-source-test",
        },
    )
    assert ingest_response.status_code == 200
    ingested_source = ingest_response.json()["source"]

    list_response = client.get(
        "/sources",
        params={"corpus_id": "source-finra", "corpus_version": "2026-source-test"},
    )

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["count"] == 1
    source_summary = list_body["sources"][0]
    assert source_summary["source_id"] == ingested_source["source_id"]
    assert source_summary["section_count"] == ingested_source["section_count"]
    assert source_summary["chunk_count"] == ingested_source["chunk_count"]

    detail_response = client.get(f"/sources/{ingested_source['source_id']}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["source"]["source_id"] == ingested_source["source_id"]
    assert detail_body["source"]["title"] == "FINRA Synthetic Rulebook"
    assert len(detail_body["sections"]) == ingested_source["section_count"]
    assert len(detail_body["chunks"]) == ingested_source["chunk_count"]
    assert detail_body["sections"][0]["corpus_version"] == "2026-source-test"
    assert detail_body["chunks"][0]["corpus_version"] == "2026-source-test"


def test_sources_list_is_empty_before_ingest(client: TestClient) -> None:
    response = client.get("/sources")

    assert response.status_code == 200
    assert response.json() == {
        "sources": [],
        "count": 0,
        "filters": {"corpus_id": None, "corpus_version": None},
    }


def test_missing_source_returns_structured_error(client: TestClient) -> None:
    response = client.get("/sources/src_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"
