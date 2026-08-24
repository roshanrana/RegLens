import builtins
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.generation.provider_factory import build_generation_service
from app.generation.service import FakeGenerationService
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.retrieval.provider_factory import build_embedding_provider, build_reranker
from app.retrieval.rerank import FakeReranker


def test_provider_factories_return_fake_providers_by_default() -> None:
    settings = Settings(app_env="test", rag_mode="mock")

    assert isinstance(build_embedding_provider(settings), FakeEmbeddingProvider)
    assert isinstance(build_reranker(settings), FakeReranker)
    assert isinstance(build_generation_service(settings), FakeGenerationService)


def test_openai_embedding_provider_fails_closed_without_api_key() -> None:
    settings = Settings(
        app_env="test",
        rag_mode="local",
        use_fake_embeddings=False,
        embedding_provider="openai",
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        build_embedding_provider(settings)

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }


def test_openai_llm_provider_fails_closed_without_api_key() -> None:
    settings = Settings(
        app_env="test",
        rag_mode="real",
        use_fake_llm=False,
        llm_provider="openai",
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        build_generation_service(settings)

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "llm",
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }


def test_cross_encoder_reranker_reports_missing_sdk_when_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.retrieval.cross_encoder_reranker as cross_encoder_reranker

    def missing_import(name: str) -> Any:
        if name == "sentence_transformers":
            raise ImportError("missing sentence-transformers")
        return __import__(name)

    monkeypatch.setattr(cross_encoder_reranker.importlib, "import_module", missing_import)
    settings = Settings(
        app_env="test",
        rag_mode="local",
        use_fake_reranker=False,
        reranker_provider="cross_encoder",
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        build_reranker(settings)

    assert exc_info.value.details == {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "package_missing",
        "package": "sentence-transformers",
        "extra": "rerank",
    }


def test_provider_factories_do_not_import_openai_sdk_when_api_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.modules.pop("openai", None)
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "openai" or name.startswith("openai."):
            raise AssertionError("OpenAI SDK should not be imported before key validation")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    embedding_settings = Settings(
        app_env="test",
        rag_mode="local",
        use_fake_embeddings=False,
        embedding_provider="openai",
    )
    llm_settings = Settings(
        app_env="test",
        rag_mode="real",
        use_fake_llm=False,
        llm_provider="openai",
    )

    with pytest.raises(DependencyUnavailableError):
        build_embedding_provider(embedding_settings)
    with pytest.raises(DependencyUnavailableError):
        build_generation_service(llm_settings)


def test_openai_embedding_provider_reports_missing_sdk_when_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.retrieval.openai_embeddings as openai_embeddings

    def missing_import(name: str) -> Any:
        if name == "openai":
            raise ImportError("missing openai")
        return __import__(name)

    monkeypatch.setattr(openai_embeddings.importlib, "import_module", missing_import)
    settings = Settings(
        app_env="test",
        rag_mode="local",
        use_fake_embeddings=False,
        embedding_provider="openai",
        openai_api_key="sk-test",
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        build_embedding_provider(settings)

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "embeddings",
        "reason": "package_missing",
        "package": "openai",
        "extra": "openai",
    }


def test_openai_llm_provider_reports_missing_sdk_when_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.generation.openai_llm as openai_llm

    def missing_import(name: str) -> Any:
        if name == "openai":
            raise ImportError("missing openai")
        return __import__(name)

    monkeypatch.setattr(openai_llm.importlib, "import_module", missing_import)
    settings = Settings(
        app_env="test",
        rag_mode="real",
        use_fake_llm=False,
        llm_provider="openai",
        openai_api_key="sk-test",
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        build_generation_service(settings)

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "llm",
        "reason": "package_missing",
        "package": "openai",
        "extra": "openai",
    }


def test_openai_factories_build_live_providers_with_explicit_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.generation.openai_llm as openai_llm
    import app.retrieval.openai_embeddings as openai_embeddings
    from app.generation.openai_llm import OpenAIResponsesLLMClient
    from app.retrieval.openai_embeddings import OpenAIEmbeddingProvider

    class FakeOpenAIClient:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key

    monkeypatch.setattr(
        openai_embeddings,
        "_load_openai_client_class",
        lambda: FakeOpenAIClient,
    )
    monkeypatch.setattr(openai_llm, "_load_openai_client_class", lambda: FakeOpenAIClient)
    settings = Settings(
        app_env="test",
        rag_mode="local",
        use_fake_embeddings=False,
        use_fake_llm=False,
        embedding_provider="openai",
        llm_provider="openai",
        openai_api_key="sk-test",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=8,
        openai_generation_model="gpt-5.4-nano",
        openai_generation_max_output_tokens=128,
    )

    embedding_provider = build_embedding_provider(settings)
    generation_service = build_generation_service(settings)

    assert isinstance(embedding_provider, OpenAIEmbeddingProvider)
    assert embedding_provider.model_name == "text-embedding-3-small"
    assert embedding_provider.dimensions == 8
    assert isinstance(generation_service.llm_client, OpenAIResponsesLLMClient)
    assert generation_service.llm_client.model_name == "gpt-5.4-nano"
    assert generation_service.llm_client.max_output_tokens == 128
    assert generation_service.prompt_version == "openai-responses-grounded-answer-v1"


def test_fake_reranker_default_does_not_import_model_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for package in ("sentence_transformers", "transformers", "torch"):
        sys.modules.pop(package, None)
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        blocked_packages = ("sentence_transformers", "transformers", "torch")
        if name in blocked_packages or name.startswith(
            tuple(f"{package}." for package in blocked_packages)
        ):
            raise AssertionError("fake reranker path should not import model packages")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    settings = Settings(app_env="test", rag_mode="local")

    assert isinstance(build_reranker(settings), FakeReranker)


def test_cross_encoder_factory_builds_reranker_with_explicit_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.retrieval.cross_encoder_reranker as cross_encoder_reranker
    from app.retrieval.cross_encoder_reranker import CrossEncoderReranker

    class FakeCrossEncoder:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            self.model_name = model_name
            self.kwargs = kwargs

    monkeypatch.setattr(
        cross_encoder_reranker,
        "_load_cross_encoder_class",
        lambda: FakeCrossEncoder,
    )
    settings = Settings(
        app_env="test",
        rag_mode="local",
        use_fake_reranker=False,
        reranker_provider="cross_encoder",
        cross_encoder_model="cross-encoder/test",
        cross_encoder_batch_size=3,
        cross_encoder_max_length=256,
        cross_encoder_device="cpu",
        cross_encoder_cache_folder=".cache/models",
        cross_encoder_local_files_only=True,
        cross_encoder_trust_remote_code=False,
    )

    reranker = build_reranker(settings)

    assert isinstance(reranker, CrossEncoderReranker)
    assert reranker.model_name == "cross-encoder/test"
    assert reranker.batch_size == 3
    assert reranker.max_length == 256
    assert reranker.device == "cpu"
    assert reranker.cache_folder == ".cache/models"
    assert reranker.local_files_only is True
    assert reranker.trust_remote_code is False


def test_openai_api_key_env_does_not_enable_live_providers_by_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REGLENS_APP_ENV", "test")
    monkeypatch.setenv("REGLENS_RAG_MODE", "mock")
    monkeypatch.setenv("REGLENS_OPENAI_API_KEY", "sk-test-placeholder")
    for name in (
        "REGLENS_EMBEDDING_PROVIDER",
        "REGLENS_LLM_PROVIDER",
        "REGLENS_RERANKER_PROVIDER",
        "REGLENS_USE_FAKE_EMBEDDINGS",
        "REGLENS_USE_FAKE_LLM",
        "REGLENS_USE_FAKE_RERANKER",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.openai_api_key == "sk-test-placeholder"
    assert settings.live_providers_enabled is False
    assert isinstance(build_embedding_provider(settings), FakeEmbeddingProvider)
    assert isinstance(build_reranker(settings), FakeReranker)
    assert isinstance(build_generation_service(settings), FakeGenerationService)
