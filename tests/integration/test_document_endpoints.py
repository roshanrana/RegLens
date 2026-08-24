from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_documents_create_alias_ingests_and_indexes_source(
    fixture_rulebook_path: Path,
) -> None:
    client = TestClient(create_app(Settings(app_env="test", rag_mode="mock", default_top_k=4)))

    response = client.post(
        "/documents",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": "documents-finra",
            "corpus_name": "Documents FINRA Rulebook",
            "version": "2026-documents",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "completed"
    assert body["source"]["corpus_id"] == "documents-finra"

    retrieve_response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "documents-finra",
            "corpus_version": "2026-documents",
            "top_k": 1,
        },
    )

    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"


def test_delete_document_removes_source_and_refreshes_mock_retrieval(
    fixture_rulebook_path: Path,
) -> None:
    client = TestClient(create_app(Settings(app_env="test", rag_mode="mock", default_top_k=4)))
    ingest_response = client.post(
        "/documents",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": "deletable-finra",
            "corpus_name": "Deletable FINRA Rulebook",
            "version": "2026-delete",
        },
    )
    source_id = ingest_response.json()["source"]["source_id"]

    delete_response = client.delete(
        f"/documents/{source_id}",
        headers={"X-Request-ID": "req_delete_audit"},
    )

    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["deleted"] is True
    assert delete_body["source_id"] == source_id
    assert delete_body["chunks_removed"] > 0

    assert client.get(f"/sources/{source_id}").status_code == 404

    deleted_retrieve = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "deletable-finra",
            "corpus_version": "2026-delete",
            "top_k": 1,
        },
    )

    assert deleted_retrieve.status_code == 200
    assert deleted_retrieve.json()["evidence"] == []

    fixture_retrieve = client.post(
        "/retrieve",
        json={
            "question": "What must automated compliance tools include?",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "top_k": 1,
        },
    )

    assert fixture_retrieve.status_code == 200
    assert fixture_retrieve.json()["evidence"][0]["citation_label"] == "FINRA Rule 1040(a)"

    audit_response = client.get("/audit/source-events", params={"source_id": source_id})
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["count"] == 2
    delete_event = audit_body["events"][0]
    assert delete_event["action"] == "delete"
    assert delete_event["status"] == "completed"
    assert delete_event["request_id"] == "req_delete_audit"
    assert delete_event["source_id"] == source_id
    assert delete_event["corpus_id"] == "deletable-finra"
    assert delete_event["corpus_version"] == "2026-delete"
    assert delete_event["details"]["chunks_removed"] == delete_body["chunks_removed"]


def test_delete_missing_document_returns_structured_error() -> None:
    client = TestClient(create_app(Settings(app_env="test", rag_mode="mock", default_top_k=4)))

    response = client.delete("/documents/src_missing", headers={"X-Request-ID": "req_missing"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"

    audit_response = client.get("/audit/source-events", params={"action": "delete"})
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["count"] == 1
    event = audit_body["events"][0]
    assert event["action"] == "delete"
    assert event["status"] == "failed"
    assert event["request_id"] == "req_missing"
    assert event["source_id"] == "src_missing"
    assert event["details"] == {"reason": "source_not_found"}
