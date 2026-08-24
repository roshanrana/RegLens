import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(app_env="test", rag_mode="mock")
    return TestClient(create_app(settings))


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "RegLens",
        "version": "0.1.0",
        "mode": "mock",
    }
    assert response.headers["X-Request-ID"].startswith("req_")


def test_ready_endpoint_fake_mode(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == "mock"
    assert body["checks"]["configuration"]["status"] == "ok"
    assert body["checks"]["embedding_provider"]["status"] == "available"
    assert body["checks"]["embedding_provider"]["provider"] == "fake"
    assert body["checks"]["qdrant"]["status"] == "skipped"


def test_request_id_header_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req_test_agent_a"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_test_agent_a"
