import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_env="test", rag_mode="mock", default_top_k=4)
    return TestClient(create_app(settings))


def test_retrieve_endpoint_returns_evidence_and_diagnostics(client: TestClient) -> None:
    response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_id"].startswith("qry_")
    assert body["normalized_question"] == "How long must records be retained?"
    assert len(body["evidence"]) == 3
    assert body["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
    assert body["evidence"][0]["rank"] == 1
    assert body["evidence"][0]["scores"]["fusion_score"] > 0
    assert body["diagnostics"]["returned_evidence"] == 3
    assert body["diagnostics"]["dense_count"] > 0
    assert body["diagnostics"]["keyword_count"] > 0
    assert body["diagnostics"]["retrieval_config"]["mode"] == "mock"


def test_retrieve_endpoint_honors_corpus_filters(client: TestClient) -> None:
    response = client.post(
        "/retrieve",
        json={
            "question": "What must automated compliance tools include?",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["evidence"]) == 2
    assert body["evidence"][0]["citation_label"] == "FINRA Rule 1040(a)"
    assert body["diagnostics"]["filters"] == {
        "corpus_id": "finra-synthetic",
        "corpus_version": "2026-08-19",
    }


def test_retrieve_endpoint_honors_source_id_filter(client: TestClient) -> None:
    source_id = client.app.state.retrieval_service.chunks[0].source_id
    blocked = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "source_id": "src_missing",
            "top_k": 2,
        },
    )
    allowed = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "source_id": source_id,
            "top_k": 2,
        },
    )

    assert blocked.status_code == 200
    assert blocked.json()["evidence"] == []
    assert blocked.json()["diagnostics"]["filters"]["source_id"] == "src_missing"
    assert allowed.status_code == 200
    assert allowed.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"


def test_retrieve_endpoint_exposes_exact_citation_route_diagnostics(client: TestClient) -> None:
    response = client.post(
        "/retrieve",
        json={
            "question": "Show me FINRA Rule 1030(b).",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
    assert body["diagnostics"]["retrieval_config"]["query_route"] == "exact_citation"
    assert body["diagnostics"]["retrieval_config"]["exact_citation_matches"] == 1


def test_retrieve_endpoint_rejects_empty_question(client: TestClient) -> None:
    response = client.post("/retrieve", json={"question": ""})

    assert response.status_code == 422
