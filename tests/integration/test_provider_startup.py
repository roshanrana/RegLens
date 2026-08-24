from __future__ import annotations

import builtins
import importlib
import json
from collections.abc import Callable
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.generation.service import FakeGenerationService
from app.main import create_app
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.retrieval.rerank import FakeReranker


def test_create_app_mock_uses_provider_factories_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def build_embedding_provider(settings: Settings) -> FakeEmbeddingProvider:
        calls.append(f"embedding:{settings.embedding_provider}")
        return FakeEmbeddingProvider()

    def build_reranker(settings: Settings) -> FakeReranker:
        calls.append(f"reranker:{settings.reranker_provider}")
        return FakeReranker()

    def build_generation_service(settings: Settings) -> FakeGenerationService:
        calls.append(f"llm:{settings.llm_provider}")
        return FakeGenerationService()

    monkeypatch.setattr("app.main.build_embedding_provider", build_embedding_provider)
    monkeypatch.setattr("app.main.build_reranker", build_reranker)
    monkeypatch.setattr("app.main.build_generation_service", build_generation_service)

    client = TestClient(create_app(Settings(app_env="test", rag_mode="mock")))

    assert client.get("/ready").json()["status"] == "ready"
    assert calls == ["llm:fake", "embedding:fake", "reranker:fake"]


def test_local_mode_openai_embedding_selection_starts_degraded_without_importing_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _guard_openai_import(monkeypatch)
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                rag_mode="local",
                use_fake_embeddings=False,
                embedding_provider="openai",
            )
        )
    )

    ready = client.get("/ready")
    retrieve = client.post("/retrieve", json={"question": "How long must records be retained?"})

    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["status"] == "degraded"
    assert ready_body["checks"]["embedding_provider"] == {
        "status": "unavailable",
        "provider": "openai",
        "fake_enabled": False,
        "reason": "OpenAI API key is required for embeddings",
        "details": {
            "provider": "openai",
            "component": "embeddings",
            "reason": "missing_api_key",
            "env_var": "OPENAI_API_KEY",
        },
    }
    assert retrieve.status_code == 503
    assert retrieve.json()["error"]["details"] == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }


def test_real_mode_without_live_provider_setup_starts_degraded_and_query_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _guard_openai_import(monkeypatch)
    _force_cross_encoder_package_missing(monkeypatch)
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                rag_mode="real",
                use_fake_embeddings=False,
                use_fake_llm=False,
                use_fake_reranker=False,
                embedding_provider="openai",
                llm_provider="openai",
                reranker_provider="cross_encoder",
            )
        )
    )

    ready = client.get("/ready")
    query = client.post("/query", json={"question": "How long must records be retained?"})
    chat = client.post("/chat", json={"question": "How long must records be retained?"})

    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["status"] == "degraded"
    assert ready_body["checks"]["llm_provider"]["provider"] == "openai"
    assert ready_body["checks"]["llm_provider"]["status"] == "unavailable"
    assert query.status_code == 503
    assert query.json()["error"]["message"] == "required query dependencies are unavailable"
    assert _dependency_details_by_name(query.json()) == {
        "embedding_provider": {
            "provider": "openai",
            "component": "embeddings",
            "reason": "missing_api_key",
            "env_var": "OPENAI_API_KEY",
        },
        "llm_provider": {
            "provider": "openai",
            "component": "llm",
            "reason": "missing_api_key",
            "env_var": "OPENAI_API_KEY",
        },
        "reranker": {
            "provider": "cross_encoder",
            "component": "reranker",
            "reason": "package_missing",
            "package": "sentence-transformers",
            "extra": "rerank",
        },
    }
    assert chat.status_code == 503
    assert chat.json()["error"]["message"] == "required query dependencies are unavailable"
    assert _dependency_details_by_name(chat.json()) == _dependency_details_by_name(query.json())
    assert client.get("/chat/sessions").json()["count"] == 0


def test_query_reports_llm_provider_gate_when_generation_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _guard_openai_import(monkeypatch)
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                rag_mode="local",
                llm_provider="openai",
                use_fake_llm=False,
            ),
            qdrant_client=_FakeQdrantClient(),
            qdrant_models=_FakeModels,
        )
    )

    ready = client.get("/ready")
    query = client.post("/query", json={"question": "How long must records be retained?"})

    assert ready.status_code == 200
    assert ready.json()["status"] == "degraded"
    assert ready.json()["checks"]["qdrant"]["status"] == "available"
    assert ready.json()["checks"]["llm_provider"]["details"] == {
        "provider": "openai",
        "component": "llm",
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }
    assert query.status_code == 503
    assert query.json()["error"]["message"] == "required query dependencies are unavailable"
    assert _dependency_details_by_name(query.json()) == {
        "llm_provider": {
            "provider": "openai",
            "component": "llm",
            "reason": "missing_api_key",
            "env_var": "OPENAI_API_KEY",
        }
    }


def test_provider_readiness_and_errors_do_not_leak_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_openai_package_missing(monkeypatch)
    secret = "sk-test-do-not-leak"
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                rag_mode="local",
                use_fake_embeddings=False,
                embedding_provider="openai",
                openai_api_key=secret,
            )
        )
    )

    ready = client.get("/ready")
    retrieve = client.post("/retrieve", json={"question": "How long must records be retained?"})

    assert ready.status_code == 200
    assert retrieve.status_code == 503
    assert secret not in json.dumps(ready.json())
    assert secret not in json.dumps(retrieve.json())
    assert retrieve.json()["error"]["details"]["reason"] == "package_missing"


def test_query_reports_unconfigured_real_retrieval_when_providers_are_available() -> None:
    client = TestClient(create_app(Settings(app_env="test", rag_mode="real")))

    query = client.post("/query", json={"question": "How long must records be retained?"})

    assert query.status_code == 503
    assert query.json()["error"]["message"] == "required query dependencies are unavailable"
    assert _dependency_details_by_name(query.json()) == {
        "retrieval": {
            "mode": "real",
            "reason": "retrieval_provider_not_configured",
        }
    }


def test_ready_reports_provider_name_and_gated_status() -> None:
    client = TestClient(create_app(Settings(app_env="test", rag_mode="mock")))

    ready_body = client.get("/ready").json()

    assert ready_body["checks"]["embedding_provider"]["provider"] == "fake"
    assert ready_body["checks"]["embedding_provider"]["status"] == "available"
    assert ready_body["checks"]["llm_provider"]["provider"] == "fake"
    assert ready_body["checks"]["llm_provider"]["status"] == "available"
    assert ready_body["checks"]["reranker"]["provider"] == "fake"
    assert ready_body["checks"]["reranker"]["status"] == "available"


def _guard_openai_import(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import: Callable[..., object] = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "openai" or name.startswith("openai."):
            raise AssertionError("startup should fail closed before importing OpenAI")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def _force_openai_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.generation.openai_llm as openai_llm
    import app.retrieval.openai_embeddings as openai_embeddings

    real_import_module = importlib.import_module

    def import_module(name: str, package: str | None = None) -> ModuleType:
        if name == "openai" or name.startswith("openai."):
            raise ImportError("missing openai")
        return real_import_module(name, package)

    monkeypatch.setattr(openai_embeddings.importlib, "import_module", import_module)
    monkeypatch.setattr(openai_llm.importlib, "import_module", import_module)


def _force_cross_encoder_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.retrieval.cross_encoder_reranker as cross_encoder_reranker

    real_import_module = importlib.import_module

    def import_module(name: str, package: str | None = None) -> ModuleType:
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise ImportError("missing sentence-transformers")
        return real_import_module(name, package)

    monkeypatch.setattr(cross_encoder_reranker.importlib, "import_module", import_module)


def _dependency_details_by_name(response_body: dict[str, object]) -> dict[str, object]:
    error = response_body["error"]
    assert isinstance(error, dict)
    details = error["details"]
    assert isinstance(details, dict)
    dependencies = details["dependencies"]
    assert isinstance(dependencies, list)
    return {
        str(dependency["name"]): dependency["details"]
        for dependency in dependencies
        if isinstance(dependency, dict)
    }


class _FakeModels:
    class Distance:
        COSINE = "Cosine"

    class VectorParams:
        def __init__(self, *, size: int, distance: str) -> None:
            self.size = size
            self.distance = distance

    class PointStruct:
        def __init__(self, *, id: str, vector: list[float], payload: dict[str, object]) -> None:
            self.id = id
            self.vector = vector
            self.payload = payload


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, _FakeModels.PointStruct]] = {}

    def collection_exists(self, *, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(
        self,
        *,
        collection_name: str,
        vectors_config: _FakeModels.VectorParams,
    ) -> None:
        self.collections[collection_name] = {}

    def upsert(
        self,
        *,
        collection_name: str,
        points: list[_FakeModels.PointStruct],
        wait: bool,
    ) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point in points:
            collection[point.id] = point
