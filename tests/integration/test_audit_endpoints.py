from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_audit_queries_lists_recent_query_summaries(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        first = _post_query(client, "How long must records be retained?")
        second = _post_query(client, "What must automated compliance tools include?")

        response = client.get("/audit/queries", params={"limit": 1})

        assert first.status_code == 200
        assert second.status_code == 200
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["limit"] == 1
        assert body["queries"][0]["query_id"] == second.json()["query_id"]
        assert body["queries"][0]["question"] == "What must automated compliance tools include?"
        assert body["queries"][0]["confidence"] == "high"
        assert "answer_preview" in body["queries"][0]
        assert body["queries"][0]["evidence_count"] == 4
        assert body["queries"][0]["audit"]["chain_index"] == 1
        assert len(body["queries"][0]["audit"]["record_hash"]) == 64
        assert body["queries"][0]["chat"] is None


def test_audit_query_detail_returns_record_and_evidence_rows(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        query_response = _post_query(client, "How long must records be retained?", top_k=3)
        query_body = query_response.json()

        response = client.get(f"/audit/queries/{query_body['query_id']}")

        assert query_response.status_code == 200
        assert response.status_code == 200
        body = response.json()
        assert body["audit"]["query_id"] == query_body["query_id"]
        assert body["audit"]["question"] == "How long must records be retained?"
        assert body["audit"]["answer"] == query_body["answer"]
        assert body["audit"]["confidence"] == "high"
        assert body["audit"]["generation_model"].startswith("fake-")
        assert body["audit"]["retrieval_config"]["mode"] == "mock"
        assert body["audit"]["chat"] is None
        assert (
            body["audit"]["audit"]["record_hash"]
            == query_body["diagnostics"]["audit"]["record_hash"]
        )
        assert len(body["evidence"]) == 3
        assert body["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
        assert body["evidence"][0]["verification_status"] == "verified"
        assert body["evidence"][0]["rank"] == 1
        assert body["evidence"][0]["scores"]["fusion_score"] > 0


def test_audit_query_export_returns_portable_json_pack(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        query_response = _post_query(client, "How long must records be retained?", top_k=3)
        query_body = query_response.json()

        response = client.get(
            f"/audit/queries/{query_body['query_id']}/export",
            params={"format": "json"},
        )

        assert response.status_code == 200
        body = response.json()
        export = body["export"]
        assert export["export_type"] == "reglens.query_audit.v1"
        assert export["query"]["query_id"] == query_body["query_id"]
        assert export["query"]["question"] == "How long must records be retained?"
        assert export["answer"]["text"] == query_body["answer"]
        assert export["answer"]["confidence"] == "high"
        assert export["answer"]["warnings"] == []
        assert export["chat"] is None
        assert export["models"]["generation_model"].startswith("fake-")
        assert (
            export["audit_chain"]["record_hash"]
            == query_body["diagnostics"]["audit"]["record_hash"]
        )
        assert export["verification"]["chain_verified"] is True
        assert export["verification"]["evidence_count"] == 3
        assert export["verification"]["verified_evidence_count"] == 1
        assert export["verification"]["unverified_evidence_count"] == 0
        assert len(export["verification"]["evidence_digest"]) == 64
        assert export["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
        assert export["evidence"][0]["verification_status"] == "verified"
        assert "six years" in export["evidence"][0]["quoted_text"]


def test_chat_created_audit_exposes_session_turn_linkage(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        chat_response = _post_chat(client, "How long must records be retained?", top_k=3)
        chat_body = chat_response.json()
        query_id = chat_body["query_id"]

        detail_response = client.get(f"/audit/queries/{query_id}")
        list_response = client.get("/audit/queries")
        export_response = client.get(
            f"/audit/queries/{query_id}/export",
            params={"format": "json"},
        )
        markdown_response = client.get(
            f"/audit/queries/{query_id}/export",
            params={"format": "markdown"},
        )

        assert chat_response.status_code == 200
        assert detail_response.status_code == 200
        assert list_response.status_code == 200
        assert export_response.status_code == 200
        assert markdown_response.status_code == 200
        expected_chat = {
            "session_id": chat_body["chat"]["session_id"],
            "session_title": "How long must records be retained?",
            "turn_id": chat_body["chat"]["turn_id"],
            "turn_index": 0,
            "session_path": chat_body["chat"]["session_path"],
            "audit_path": chat_body["chat"]["audit_path"],
        }
        assert detail_response.json()["audit"]["chat"] == expected_chat
        assert list_response.json()["queries"][0]["chat"] == expected_chat
        assert export_response.json()["export"]["chat"] == expected_chat
        assert f"Chat session: `{expected_chat['session_id']}`" in markdown_response.text
        assert f"Chat turn: `{expected_chat['turn_id']}`" in markdown_response.text


def test_audit_query_export_returns_markdown_pack(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        query_response = _post_query(client, "How long must records be retained?", top_k=3)
        query_id = query_response.json()["query_id"]

        response = client.get(f"/audit/queries/{query_id}/export", params={"format": "markdown"})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        text = response.text
        assert "# RegLens Query Audit Export" in text
        assert f"Query ID: `{query_id}`" in text
        assert "Question: How long must records be retained?" in text
        assert "FINRA Rule 1030(b)" in text
        assert "Verification: verified" in text
        assert "Record hash:" in text


def test_audit_query_export_rejects_unknown_format(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        query_response = _post_query(client, "How long must records be retained?", top_k=3)
        query_id = query_response.json()["query_id"]

        response = client.get(f"/audit/queries/{query_id}/export", params={"format": "pdf"})

        assert response.status_code == 422


def test_audit_verify_returns_hash_chain_status(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        first = _post_query(client, "How long must records be retained?")
        second = _post_query(client, "What must automated compliance tools include?")

        response = client.get("/audit/verify")

        assert first.status_code == 200
        assert second.status_code == 200
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "verified": True,
            "record_count": 2,
            "latest_record_hash": second.json()["diagnostics"]["audit"]["record_hash"],
            "latest_chain_index": 1,
            "failure_count": 0,
            "failures": [],
        }


def test_audit_verify_reports_evidence_integrity_failure(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        query_response = _post_query(client, "How long must records be retained?", top_k=3)
        query_id = query_response.json()["query_id"]
        app.state.db_connection.execute(
            """
            UPDATE query_evidence
            SET snippet = ?
            WHERE query_id = ? AND final_rank = 1
            """,
            ("tampered evidence", query_id),
        )
        app.state.db_connection.commit()

        response = client.get("/audit/verify")

        assert response.status_code == 200
        body = response.json()
        assert body["verified"] is False
        assert body["failure_count"] >= 1
        assert any(
            failure["code"] == "evidence_digest_mismatch"
            and failure["query_id"] == query_id
            for failure in body["failures"]
        )


def test_audit_query_detail_returns_reglens_404_for_unknown_query(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get(
            "/audit/queries/qry_missing",
            headers={"X-Request-ID": "req_audit_missing"},
        )

        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "code": "audit_query_not_found",
                "message": "query audit record was not found",
                "request_id": "req_audit_missing",
                "details": {"query_id": "qry_missing"},
            }
        }


def _post_query(
    client: TestClient,
    question: str,
    *,
    top_k: int | None = None,
) -> object:
    payload: dict[str, object] = {
        "question": question,
        "corpus_id": "finra-synthetic",
        "corpus_version": "2026-08-19",
    }
    if top_k is not None:
        payload["top_k"] = top_k
    return client.post("/query", json=payload)


def _post_chat(
    client: TestClient,
    question: str,
    *,
    top_k: int | None = None,
) -> object:
    payload: dict[str, object] = {
        "question": question,
        "corpus_id": "finra-synthetic",
        "corpus_version": "2026-08-19",
    }
    if top_k is not None:
        payload["top_k"] = top_k
    return client.post("/chat", json=payload)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        rag_mode="mock",
        default_top_k=4,
        database_url=f"sqlite:///{(tmp_path / 'audit-endpoints.db').as_posix()}",
    )
