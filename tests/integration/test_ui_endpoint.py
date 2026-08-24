from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_ui_homepage_serves_policy_copilot_shell() -> None:
    client = TestClient(create_app(Settings(app_env="test", rag_mode="mock", default_top_k=4)))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "RegLens" in response.text
    assert 'id="query-form"' in response.text
    assert 'id="ingest-form"' in response.text
    assert '<option value="pdf">PDF</option>' in response.text
    assert 'id="provenance"' in response.text
    assert 'id="source-events"' in response.text
    assert 'id="chat-session-label"' in response.text
    assert 'id="chat-sessions"' in response.text
    assert 'id="chat-turns"' in response.text
    assert 'id="export-chat"' in response.text
    assert 'api("/chat"' in response.text
    assert 'api("/chat/sessions"' in response.text
    assert "/export?format=markdown" in response.text
    assert 'api("/documents"' in response.text
    assert "/audit/source-events" in response.text
    assert "/export?format=${format}" in response.text
