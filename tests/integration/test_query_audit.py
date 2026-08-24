from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_query_endpoint_writes_audit_and_evidence_rows(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "finra-synthetic",
                "corpus_version": "2026-08-19",
                "top_k": 3,
            },
        )

        assert response.status_code == 200
        body = response.json()
        audit_repository = app.state.query_audit_repository
        audit = audit_repository.get(body["query_id"])
        evidence_rows = list(audit_repository.list_evidence(body["query_id"]))

        assert audit is not None
        assert audit.query_id == body["query_id"]
        assert audit.question == "How long must records be retained?"
        assert audit.answer == body["answer"]
        assert audit.confidence == body["confidence"]
        assert audit.generation_model == body["model_info"]["generation_model"]
        assert audit.generation_model is not None
        assert audit.generation_model.startswith("fake-")
        assert audit.embedding_model == "fake-hashed-lexical-v1"
        assert audit.prompt_version == body["model_info"]["prompt_version"]
        assert audit.estimated_cost_usd == 0.0
        assert audit.record_hash == body["diagnostics"]["audit"]["record_hash"]
        assert audit.payload_hash == body["diagnostics"]["audit"]["payload_hash"]
        assert len(evidence_rows) == len(body["evidence"]) == 3
        assert evidence_rows[0].citation_label == "FINRA Rule 1030(b)"
        assert evidence_rows[0].verification_status == "verified"
        assert evidence_rows[0].quote_hash is not None
        assert audit.evidence_count == 3
        assert audit.evidence_digest is not None
        assert audit_repository.verify_chain() is True


def test_query_audit_hash_chain_links_multiple_queries(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        first = client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "finra-synthetic",
            },
        )
        second = client.post(
            "/query",
            json={
                "question": "What must automated compliance tools include?",
                "corpus_id": "finra-synthetic",
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        audit_repository = app.state.query_audit_repository
        first_audit = audit_repository.get(first.json()["query_id"])
        second_audit = audit_repository.get(second.json()["query_id"])

        assert first_audit is not None
        assert second_audit is not None
        assert first_audit.chain_index == 0
        assert second_audit.chain_index == 1
        assert second_audit.previous_record_hash == first_audit.record_hash
        assert audit_repository.verify_chain() is True


def test_query_audit_hash_chain_handles_repeated_questions(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        first = client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "finra-synthetic",
            },
        )
        second = client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "finra-synthetic",
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["query_id"] != second.json()["query_id"]
        assert app.state.query_audit_repository.verify_chain() is True


def test_audit_verify_detects_query_evidence_snippet_tampering(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "finra-synthetic",
                "corpus_version": "2026-08-19",
                "top_k": 3,
            },
        )

        assert response.status_code == 200
        app.state.db_connection.execute(
            """
            UPDATE query_evidence
            SET snippet = ?
            WHERE query_id = ? AND final_rank = 1
            """,
            ("tampered evidence", response.json()["query_id"]),
        )
        app.state.db_connection.commit()

        result = app.state.query_audit_repository.verify_chain_detailed()

        assert result.verified is False
        assert any(
            issue.code == "evidence_digest_mismatch"
            and issue.query_id == response.json()["query_id"]
            for issue in result.failures
        )


def test_audit_verify_detects_query_evidence_deletion(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/query",
            json={
                "question": "How long must records be retained?",
                "corpus_id": "finra-synthetic",
                "corpus_version": "2026-08-19",
                "top_k": 3,
            },
        )

        assert response.status_code == 200
        app.state.db_connection.execute(
            "DELETE FROM query_evidence WHERE query_id = ? AND final_rank = 1",
            (response.json()["query_id"],),
        )
        app.state.db_connection.commit()

        result = app.state.query_audit_repository.verify_chain_detailed()

        assert result.verified is False
        failure_codes = {issue.code for issue in result.failures}
        assert "evidence_count_mismatch" in failure_codes
        assert "evidence_digest_mismatch" in failure_codes


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        rag_mode="mock",
        default_top_k=4,
        database_url=f"sqlite:///{(tmp_path / 'query-audit.db').as_posix()}",
    )
