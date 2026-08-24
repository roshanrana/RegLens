from fastapi.testclient import TestClient

from app.core.config import Settings
from app.generation.service import GenerationService
from app.main import create_app


def test_query_accepts_generation_service_base_class_not_fake_subclass() -> None:
    app = create_app(Settings(app_env="test", rag_mode="mock", default_top_k=4))
    app.state.generation_service = GenerationService()
    client = TestClient(app)

    response = client.post("/query", json={"question": "How long must records be retained?"})

    assert response.status_code == 200
    assert response.json()["model_info"]["generation_model"] == "fake-reglens-llm-v1"
