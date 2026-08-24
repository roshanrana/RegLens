from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_api_key_auth_protects_operational_routes_but_not_health() -> None:
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                rag_mode="mock",
                api_key="test-secret",
            )
        )
    )

    assert client.get("/health").status_code == 200

    missing = client.post("/retrieve", json={"question": "How long?"})
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"
    assert "test-secret" not in missing.text

    allowed = client.post(
        "/retrieve",
        headers={"X-RegLens-API-Key": "test-secret"},
        json={"question": "How long must records be retained?", "top_k": 1},
    )
    assert allowed.status_code == 200


def test_bearer_api_key_is_accepted() -> None:
    client = TestClient(
        create_app(Settings(app_env="test", rag_mode="mock", api_key="test-secret"))
    )

    response = client.post(
        "/retrieve",
        headers={"Authorization": "Bearer test-secret"},
        json={"question": "How long must records be retained?", "top_k": 1},
    )

    assert response.status_code == 200


def test_rate_limit_returns_429_after_configured_limit() -> None:
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                rag_mode="mock",
                rate_limit_per_minute=1,
            )
        )
    )

    first = client.post("/retrieve", json={"question": "How long?", "top_k": 1})
    second = client.post("/retrieve", json={"question": "How long?", "top_k": 1})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    assert int(second.headers["Retry-After"]) > 0
