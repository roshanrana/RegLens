from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.retrieval.qdrant_store import QdrantVectorStore


@pytest.mark.requires_qdrant
def test_local_mode_real_qdrant_retrieve_ingest_query_and_delete(
    tmp_path: Path,
    fixture_rulebook_path: Path,
) -> None:
    qdrant_url = os.getenv("REGLENS_QDRANT_URL", "http://localhost:6333")
    qdrant_client = _qdrant_client_or_skip(qdrant_url)
    collection_name = f"reglens_test_{uuid4().hex}"
    _delete_collection_if_exists(qdrant_client, collection_name)

    try:
        settings = Settings(
            app_env="test",
            rag_mode="local",
            default_top_k=4,
            qdrant_url=qdrant_url,
            qdrant_collection=collection_name,
            database_url=f"sqlite:///{(tmp_path / 'real-qdrant-smoke.db').as_posix()}",
        )
        with TestClient(create_app(settings)) as client:
            ready = client.get("/ready")

            assert ready.status_code == 200
            assert ready.json()["status"] == "ready"
            assert ready.json()["checks"]["qdrant"]["status"] == "available"
            assert ready.json()["checks"]["qdrant"]["collection"] == collection_name
            assert isinstance(client.app.state.retrieval_service.vector_store, QdrantVectorStore)

            fixture_retrieve = client.post(
                "/retrieve",
                json={
                    "question": "How long must records be retained?",
                    "corpus_id": "finra-synthetic",
                    "corpus_version": "2026-08-19",
                    "top_k": 2,
                },
            )

            assert fixture_retrieve.status_code == 200
            fixture_body = fixture_retrieve.json()
            assert fixture_body["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
            assert fixture_body["diagnostics"]["retrieval_config"]["mode"] == "local"
            assert fixture_body["diagnostics"]["dense_count"] > 0

            ingest_response = client.post(
                "/documents",
                json={
                    "path": str(fixture_rulebook_path),
                    "input_type": "markdown",
                    "corpus_id": "real-qdrant-finra",
                    "corpus_name": "Real Qdrant FINRA Rulebook",
                    "version": "2026-real-qdrant",
                },
            )

            assert ingest_response.status_code == 200
            source_id = ingest_response.json()["source"]["source_id"]

            ingested_query = client.post(
                "/query",
                json={
                    "question": "How long must records be retained?",
                    "corpus_id": "real-qdrant-finra",
                    "corpus_version": "2026-real-qdrant",
                    "top_k": 2,
                },
            )

            assert ingested_query.status_code == 200
            query_body = ingested_query.json()
            assert query_body["citations"][0]["citation_label"] == "FINRA Rule 1030(b)"
            assert query_body["citations"][0]["verification_status"] == "verified"
            assert query_body["diagnostics"]["retrieval_config"]["mode"] == "local"
            assert query_body["diagnostics"]["dense_count"] > 0

            delete_response = client.delete(f"/documents/{source_id}")

            assert delete_response.status_code == 200
            assert delete_response.json()["deleted"] is True

            deleted_retrieve = client.post(
                "/retrieve",
                json={
                    "question": "How long must records be retained?",
                    "corpus_id": "real-qdrant-finra",
                    "corpus_version": "2026-real-qdrant",
                    "top_k": 1,
                },
            )

            assert deleted_retrieve.status_code == 200
            assert deleted_retrieve.json()["evidence"] == []
    finally:
        _delete_collection_if_exists(qdrant_client, collection_name)


def _qdrant_client_or_skip(qdrant_url: str) -> Any:
    qdrant_client_module = pytest.importorskip(
        "qdrant_client",
        reason="qdrant-client is not installed; install RegLens with .[qdrant]",
    )
    client = qdrant_client_module.QdrantClient(url=qdrant_url, timeout=2.0)
    try:
        client.get_collections()
    except Exception as exc:
        pytest.skip(f"Qdrant is not reachable at {qdrant_url}: {exc}")
    return client


def _delete_collection_if_exists(qdrant_client: Any, collection_name: str) -> None:
    try:
        if qdrant_client.collection_exists(collection_name=collection_name):
            qdrant_client.delete_collection(collection_name=collection_name)
    except Exception:
        pass
