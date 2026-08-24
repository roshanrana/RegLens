import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import routes_admin
from app.core.config import Settings
from app.main import create_app
from app.retrieval.service import RetrievalService


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_env="test", rag_mode="mock", default_top_k=4)
    return TestClient(create_app(settings))


def test_admin_ingest_markdown_fixture_persists_job_source_sections_and_chunks(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    response = client.post(
        "/admin/ingest",
        headers={"X-Request-ID": "req_ingest_audit"},
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": "admin-finra",
            "corpus_name": "Admin FINRA Rulebook",
            "version": "2026-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["job_id"].startswith("ing_")
    assert body["job"]["status"] == "completed"
    assert body["job"]["corpus_id"] == "admin-finra"
    assert body["job"]["corpus_version"] == "2026-test"
    assert body["job"]["report"]["source_id"] == body["source"]["source_id"]
    assert body["source"]["corpus_id"] == "admin-finra"
    assert body["source"]["corpus_version"] == "2026-test"
    assert body["source"]["document_type"] == "markdown"
    assert body["source"]["section_count"] > 0
    assert body["source"]["chunk_count"] > 0

    job_response = client.get(f"/admin/ingest/{body['job']['job_id']}")

    assert job_response.status_code == 200
    assert job_response.json()["job"] == body["job"]

    audit_response = client.get("/audit/source-events")
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["count"] == 1
    event = audit_body["events"][0]
    assert event["action"] == "ingest"
    assert event["status"] == "completed"
    assert event["request_id"] == "req_ingest_audit"
    assert event["job_id"] == body["job"]["job_id"]
    assert event["source_id"] == body["source"]["source_id"]
    assert event["source_checksum"] == body["source"]["checksum"]
    assert event["corpus_id"] == "admin-finra"
    assert event["corpus_version"] == "2026-test"
    assert event["actor"] == "local-user"
    assert event["details"]["chunks_persisted"] == body["source"]["chunk_count"]


def test_admin_ingest_refreshes_mock_retrieval_for_retrieve_and_query(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    ingest_response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": "queryable-finra",
            "corpus_name": "Queryable FINRA Rulebook",
            "version": "2026-queryable",
        },
    )

    assert ingest_response.status_code == 200
    ingest_body = ingest_response.json()
    assert ingest_body["job"]["report"]["retrieval_index_chunks"] >= (
        ingest_body["source"]["chunk_count"]
    )

    retrieve_response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "queryable-finra",
            "corpus_version": "2026-queryable",
            "top_k": 2,
        },
    )

    assert retrieve_response.status_code == 200
    retrieve_body = retrieve_response.json()
    assert retrieve_body["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
    assert "six years" in retrieve_body["evidence"][0]["snippet"]
    assert retrieve_body["diagnostics"]["filters"] == {
        "corpus_id": "queryable-finra",
        "corpus_version": "2026-queryable",
    }

    wrong_version_response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "queryable-finra",
            "corpus_version": "wrong-version",
            "top_k": 2,
        },
    )

    assert wrong_version_response.status_code == 200
    assert wrong_version_response.json()["evidence"] == []

    query_response = client.post(
        "/query",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "queryable-finra",
            "corpus_version": "2026-queryable",
            "top_k": 2,
        },
    )

    assert query_response.status_code == 200
    query_body = query_response.json()
    assert "six years" in query_body["answer"]
    assert query_body["citations"][0]["citation_label"] == "FINRA Rule 1030(b)"
    assert query_body["citations"][0]["verification_status"] == "verified"

    fixture_response = client.post(
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


def test_admin_ingest_finra_url_snapshots_and_indexes_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <body>
        <h1>FINRA Rules</h1>
        <h2>Rule 2210. Communications with the Public</h2>
        <p>Communications must be fair and balanced and must provide a sound basis
        for evaluating the facts about any product or service.</p>
      </body>
    </html>
    """

    def fake_read_remote_source(url: str, *, max_bytes: int) -> routes_admin.RemoteSource:
        assert url == "https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210"
        assert max_bytes == 5_000_000
        return routes_admin.RemoteSource(
            body=html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
            final_url=url,
        )

    monkeypatch.setattr(routes_admin, "_read_remote_source", fake_read_remote_source)
    settings = Settings(
        app_env="test",
        rag_mode="mock",
        default_top_k=4,
        document_storage_path=tmp_path.as_posix(),
        database_url=f"sqlite:///{(tmp_path / 'remote-ingest.db').as_posix()}",
    )
    with TestClient(create_app(settings)) as test_client:
        response = test_client.post(
            "/admin/ingest-url",
            json={
                "url": "https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210",
                "input_type": "html",
                "corpus_id": "finra-rules",
                "corpus_name": "FINRA Rules",
                "version": "2026-demo",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["source"]["source_uri"] == (
            "https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210"
        )
        assert body["source"]["metadata"]["remote_ingest"] is True
        assert body["job"]["report"]["input_uri"].startswith("https://www.finra.org/")
        assert list((tmp_path / "remote").glob("*.html"))

        retrieve_response = test_client.post(
            "/retrieve",
            json={
                "question": "What must communications with the public be?",
                "corpus_id": "finra-rules",
                "corpus_version": "2026-demo",
                "top_k": 1,
            },
        )

        assert retrieve_response.status_code == 200
        evidence = retrieve_response.json()["evidence"][0]
        assert evidence["citation_label"] == "FINRA Rule 2210"
        assert "fair and balanced" in evidence["snippet"]


def test_admin_ingest_url_rejects_unapproved_hosts(client: TestClient) -> None:
    response = client.post(
        "/admin/ingest-url",
        json={
            "url": "https://example.com/rules/2210",
            "input_type": "html",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ingest_url_host_not_allowed"


def test_admin_ingest_refresh_is_idempotent(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    first = _ingest_fixture(
        client,
        fixture_rulebook_path,
        corpus_id="idempotent-finra",
        corpus_name="Idempotent FINRA Rulebook",
        version="2026-idempotent",
    )
    second = _ingest_fixture(
        client,
        fixture_rulebook_path,
        corpus_id="idempotent-finra",
        corpus_name="Idempotent FINRA Rulebook",
        version="2026-idempotent",
    )

    assert (
        second["job"]["report"]["retrieval_index_chunks"]
        == first["job"]["report"]["retrieval_index_chunks"]
    )

    service = _retrieval_service(client)
    chunk_ids = [chunk.chunk_id for chunk in service.chunks]
    assert len(chunk_ids) == len(set(chunk_ids))

    response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "idempotent-finra",
            "corpus_version": "2026-idempotent",
            "top_k": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"


def test_concurrent_admin_ingests_do_not_clobber_mock_retrieval_state(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    corpora = [
        ("parallel-finra-a", "Parallel FINRA Rulebook A", "2026-parallel-a"),
        ("parallel-finra-b", "Parallel FINRA Rulebook B", "2026-parallel-b"),
    ]

    def ingest(corpus: tuple[str, str, str]) -> dict[str, Any]:
        corpus_id, corpus_name, version = corpus
        return _ingest_fixture(
            client,
            fixture_rulebook_path,
            corpus_id=corpus_id,
            corpus_name=corpus_name,
            version=version,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        bodies = list(executor.map(ingest, corpora))

    assert [body["job"]["status"] for body in bodies] == ["completed", "completed"]

    for corpus_id, _, version in corpora:
        response = client.post(
            "/retrieve",
            json={
                "question": "How long must records be retained?",
                "corpus_id": corpus_id,
                "corpus_version": version,
                "top_k": 1,
            },
        )

        assert response.status_code == 200
        assert response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"


def test_failed_admin_ingest_does_not_refresh_mock_retrieval(
    client: TestClient,
    tmp_path: Path,
) -> None:
    initial_chunk_ids = [chunk.chunk_id for chunk in _retrieval_service(client).chunks]
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside\n\n## Rule 1\n\nNope.", encoding="utf-8")

    response = client.post(
        "/admin/ingest",
        json={"path": str(outside_file), "input_type": "markdown"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_ingest_path"
    assert [chunk.chunk_id for chunk in _retrieval_service(client).chunks] == initial_chunk_ids

    fixture_response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "finra-synthetic",
            "corpus_version": "2026-08-19",
            "top_k": 1,
        },
    )

    assert fixture_response.status_code == 200
    assert fixture_response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"


def test_admin_ingest_corpus_overrides_create_distinct_source_rows(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    first = _ingest_fixture(
        client,
        fixture_rulebook_path,
        corpus_id="source-isolated-a",
        corpus_name="Source Isolated FINRA A",
        version="2026-source-a",
    )
    second = _ingest_fixture(
        client,
        fixture_rulebook_path,
        corpus_id="source-isolated-b",
        corpus_name="Source Isolated FINRA B",
        version="2026-source-b",
    )

    assert first["source"]["source_id"] != second["source"]["source_id"]

    first_sources = client.get(
        "/sources",
        params={"corpus_id": "source-isolated-a", "corpus_version": "2026-source-a"},
    )
    second_sources = client.get(
        "/sources",
        params={"corpus_id": "source-isolated-b", "corpus_version": "2026-source-b"},
    )

    assert first_sources.status_code == 200
    assert second_sources.status_code == 200
    assert first_sources.json()["count"] == 1
    assert second_sources.json()["count"] == 1
    assert first_sources.json()["sources"][0]["source_id"] == first["source"]["source_id"]
    assert second_sources.json()["sources"][0]["source_id"] == second["source"]["source_id"]


def test_admin_ingest_pdf_with_fake_pypdf_persists_pages_and_refreshes_query(
    client: TestClient,
    fixture_rulebook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pypdf(
        monkeypatch,
        pages=[
            (
                "Rule 1030(b). Retention Period\n"
                "Records required by this rulebook must be retained for six years."
            ),
            (
                "Rule 1045. Supervisory Review\n"
                "Supervisory reviews must be documented and available for audit."
            ),
        ],
        metadata={"/Title": "FINRA PDF Rulebook"},
    )

    response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "pdf",
            "corpus_id": "pdf-finra",
            "corpus_name": "PDF FINRA Rulebook",
            "version": "2026-pdf",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "completed"
    assert body["source"]["document_type"] == "pdf"
    assert body["source"]["section_count"] == 2
    assert body["source"]["chunk_count"] >= 2

    source_response = client.get(f"/sources/{body['source']['source_id']}")
    assert source_response.status_code == 200
    sections = source_response.json()["sections"]
    assert [section["page_number"] for section in sections] == [1, 2]
    assert sections[0]["citation_label"] == "FINRA Rule 1030(b)"
    assert sections[0]["metadata"]["extraction_method"] == "pypdf"

    retrieve_response = client.post(
        "/retrieve",
        json={
            "question": "How long must records be retained?",
            "corpus_id": "pdf-finra",
            "corpus_version": "2026-pdf",
            "top_k": 1,
        },
    )

    assert retrieve_response.status_code == 200
    assert retrieve_response.json()["evidence"][0]["citation_label"] == "FINRA Rule 1030(b)"
    assert "six years" in retrieve_response.json()["evidence"][0]["snippet"]


def test_admin_ingest_pdf_splits_multiple_rules_on_one_page(
    client: TestClient,
    fixture_rulebook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pypdf(
        monkeypatch,
        pages=[
            (
                "Rule 1030(b). Retention Period\n"
                "Records required by this rulebook must be retained for six years.\n\n"
                "Rule 1045. Supervisory Review\n"
                "Supervisory reviews must be documented and available for audit."
            ),
        ],
        metadata={"/Title": "FINRA PDF Rulebook"},
    )

    response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "pdf",
            "corpus_id": "pdf-split-finra",
            "corpus_name": "PDF Split FINRA Rulebook",
            "version": "2026-pdf-split",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["section_count"] == 2

    source_response = client.get(f"/sources/{body['source']['source_id']}")
    assert source_response.status_code == 200
    sections = source_response.json()["sections"]
    assert [section["citation_label"] for section in sections] == [
        "FINRA Rule 1030(b)",
        "FINRA Rule 1045",
    ]
    assert [section["page_number"] for section in sections] == [1, 1]
    assert sections[0]["metadata"]["split_strategy"] == "rule_heading"

    retrieve_response = client.post(
        "/retrieve",
        json={
            "question": "What must supervisory reviews include?",
            "corpus_id": "pdf-split-finra",
            "corpus_version": "2026-pdf-split",
            "top_k": 1,
        },
    )

    assert retrieve_response.status_code == 200
    evidence = retrieve_response.json()["evidence"][0]
    assert evidence["citation_label"] == "FINRA Rule 1045"
    assert "Supervisory reviews" in evidence["snippet"]


def test_admin_ingest_pdf_missing_dependency_marks_job_failed(
    client: TestClient,
    fixture_rulebook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_chunk_ids = [chunk.chunk_id for chunk in _retrieval_service(client).chunks]
    _install_missing_pypdf(monkeypatch)

    response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "pdf",
            "corpus_id": "missing-pdf",
            "corpus_name": "Missing PDF Dependency",
            "version": "2026-pdf",
        },
    )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "dependency_unavailable"
    assert error["details"]["package"] == "pypdf"
    assert error["details"]["job_id"].startswith("ing_")

    job_response = client.get(f"/admin/ingest/{error['details']['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()["job"]
    assert job["status"] == "failed"
    assert job["error"]["message"] == "PDF ingestion dependency is unavailable"
    assert job["error"]["package"] == "pypdf"
    assert [chunk.chunk_id for chunk in _retrieval_service(client).chunks] == initial_chunk_ids


def test_admin_ingest_scanned_pdf_marks_job_failed_without_persisting_source(
    client: TestClient,
    fixture_rulebook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_chunk_ids = [chunk.chunk_id for chunk in _retrieval_service(client).chunks]
    _install_fake_pypdf(
        monkeypatch,
        pages=["", None],
        metadata={"/Title": "Scanned FINRA Rulebook"},
    )

    response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "pdf",
            "corpus_id": "scanned-pdf",
            "corpus_name": "Scanned PDF Rulebook",
            "version": "2026-scan",
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "corpus_load_error"
    assert error["details"]["errors"] == ["PDF did not contain extractable text"]

    job_response = client.get(f"/admin/ingest/{error['details']['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()["job"]
    assert job["status"] == "failed"
    assert job["error"]["message"] == "source file could not be converted into sections"
    assert job["error"]["errors"] == ["PDF did not contain extractable text"]

    sources_response = client.get(
        "/sources",
        params={"corpus_id": "scanned-pdf", "corpus_version": "2026-scan"},
    )
    assert sources_response.status_code == 200
    assert sources_response.json()["count"] == 0
    assert [chunk.chunk_id for chunk in _retrieval_service(client).chunks] == initial_chunk_ids


def test_admin_ingest_rejects_invalid_input_type(
    client: TestClient,
    fixture_rulebook_path: Path,
) -> None:
    response = client.post(
        "/admin/ingest",
        json={"path": str(fixture_rulebook_path), "input_type": "docx"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input_type"


def test_admin_ingest_rejects_local_paths_outside_allowed_roots(
    client: TestClient,
    tmp_path: Path,
) -> None:
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside\n\n## Rule 1\n\nNope.", encoding="utf-8")

    response = client.post(
        "/admin/ingest",
        json={"path": str(outside_file), "input_type": "markdown"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_ingest_path"


def test_admin_ingest_rejects_remote_url(
    client: TestClient,
) -> None:
    response = client.post(
        "/admin/ingest",
        json={"path": "https://example.test/rules.md", "input_type": "markdown"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_ingest_path"


def test_get_missing_ingestion_job_returns_structured_error(client: TestClient) -> None:
    response = client.get("/admin/ingest/ing_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ingestion_job_not_found"


def _ingest_fixture(
    client: TestClient,
    fixture_rulebook_path: Path,
    *,
    corpus_id: str,
    corpus_name: str,
    version: str,
) -> dict[str, Any]:
    response = client.post(
        "/admin/ingest",
        json={
            "path": str(fixture_rulebook_path),
            "input_type": "markdown",
            "corpus_id": corpus_id,
            "corpus_name": corpus_name,
            "version": version,
        },
    )

    assert response.status_code == 200
    return response.json()


def _retrieval_service(client: TestClient) -> RetrievalService:
    service = client.app.state.retrieval_service
    assert isinstance(service, RetrievalService)
    return service


def _install_fake_pypdf(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pages: list[str | None],
    metadata: dict[str, Any] | None = None,
) -> None:
    from app.ingestion import loaders

    original_import_module = importlib.import_module

    class FakePage:
        def __init__(self, text: str | None) -> None:
            self._text = text

        def extract_text(self) -> str | None:
            return self._text

    class FakePdfReader:
        def __init__(self, _: str | Path) -> None:
            self.metadata = metadata or {}
            self.pages = [FakePage(text) for text in pages]

    def fake_import_module(name: str, package: str | None = None) -> Any:
        if name == "pypdf":
            return SimpleNamespace(PdfReader=FakePdfReader)
        return original_import_module(name, package)

    monkeypatch.setattr(loaders.importlib, "import_module", fake_import_module)


def _install_missing_pypdf(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ingestion import loaders

    original_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None) -> Any:
        if name == "pypdf":
            raise ImportError("No module named pypdf")
        return original_import_module(name, package)

    monkeypatch.setattr(loaders.importlib, "import_module", fake_import_module)
