from pathlib import Path

import pytest

from app.core.config import Settings, get_settings, reset_settings_cache


def test_settings_defaults_to_fake_mode() -> None:
    settings = Settings.from_env()

    assert settings.app_name == "RegLens"
    assert settings.rag_mode == "mock"
    assert settings.is_fake_mode is True
    assert settings.use_fake_embeddings is True
    assert settings.use_fake_llm is True
    assert settings.use_fake_reranker is True
    assert settings.embedding_provider == "fake"
    assert settings.llm_provider == "fake"
    assert settings.reranker_provider == "fake"
    assert settings.live_providers_enabled is False


def test_settings_support_reglens_prefixed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGLENS_APP_ENV", "test")
    monkeypatch.setenv("REGLENS_RAG_MODE", "local")
    monkeypatch.setenv("REGLENS_USE_FAKE_EMBEDDINGS", "false")
    monkeypatch.setenv("REGLENS_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("REGLENS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("REGLENS_RERANKER_PROVIDER", "cross_encoder")
    monkeypatch.setenv("REGLENS_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    monkeypatch.setenv("REGLENS_API_KEY", "local-reglens-key")
    monkeypatch.setenv("REGLENS_API_KEY_HEADER", "X-Test-Key")
    monkeypatch.setenv("REGLENS_AUTH_EXEMPT_PATHS", "/health,/ready")
    monkeypatch.setenv("REGLENS_RATE_LIMIT_PER_MINUTE", "12")
    monkeypatch.setenv("REGLENS_ALLOWED_INGEST_URL_HOSTS", "www.finra.org,rules.finra.org")
    monkeypatch.setenv("REGLENS_REMOTE_INGEST_MAX_BYTES", "12345")
    monkeypatch.setenv("REGLENS_ENABLE_EMBEDDING_CACHE", "false")
    monkeypatch.setenv("REGLENS_EMBEDDING_CACHE_MAX_ENTRIES", "321")
    monkeypatch.setenv("REGLENS_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("REGLENS_OPENAI_EMBEDDING_DIMENSIONS", "1024")
    monkeypatch.setenv("REGLENS_OPENAI_GENERATION_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS", "128")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_MODEL", "cross-encoder/test")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_BATCH_SIZE", "7")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_MAX_LENGTH", "256")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_DEVICE", "cpu")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_CACHE_FOLDER", ".cache/models")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_LOCAL_FILES_ONLY", "true")
    monkeypatch.setenv("REGLENS_CROSS_ENCODER_TRUST_REMOTE_CODE", "false")

    settings = Settings.from_env()

    assert settings.app_env == "test"
    assert settings.rag_mode == "local"
    assert settings.use_fake_embeddings is False
    assert settings.embedding_provider == "openai"
    assert settings.llm_provider == "openai"
    assert settings.reranker_provider == "cross_encoder"
    assert settings.cors_origins == ("http://localhost:3000", "http://localhost:5173")
    assert settings.api_key == "local-reglens-key"
    assert settings.api_key_header == "X-Test-Key"
    assert settings.auth_exempt_paths == ("/health", "/ready")
    assert settings.rate_limit_per_minute == 12
    assert settings.allowed_ingest_url_hosts == ("www.finra.org", "rules.finra.org")
    assert settings.remote_ingest_max_bytes == 12345
    assert settings.enable_embedding_cache is False
    assert settings.embedding_cache_max_entries == 321
    assert settings.openai_embedding_model == "text-embedding-3-large"
    assert settings.openai_embedding_dimensions == 1024
    assert settings.openai_generation_model == "gpt-5.4-mini"
    assert settings.openai_generation_max_output_tokens == 128
    assert settings.cross_encoder_model == "cross-encoder/test"
    assert settings.cross_encoder_batch_size == 7
    assert settings.cross_encoder_max_length == 256
    assert settings.cross_encoder_device == "cpu"
    assert settings.cross_encoder_cache_folder == ".cache/models"
    assert settings.cross_encoder_local_files_only is True
    assert settings.cross_encoder_trust_remote_code is False


def test_settings_support_json_cors_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "REGLENS_CORS_ORIGINS",
        '["http://localhost:3000","http://localhost:8000"]',
    )

    settings = Settings.from_env()

    assert settings.cors_origins == ("http://localhost:3000", "http://localhost:8000")


def test_mock_mode_rejects_live_provider_flags() -> None:
    with pytest.raises(ValueError, match="mock mode requires fake embeddings"):
        Settings(rag_mode="mock", use_fake_embeddings=False)


def test_mock_mode_rejects_live_provider_names() -> None:
    with pytest.raises(ValueError, match="mock mode requires fake provider selections"):
        Settings(rag_mode="mock", embedding_provider="openai")


def test_settings_reject_invalid_cross_encoder_values() -> None:
    with pytest.raises(ValueError, match="cross_encoder_batch_size"):
        Settings(cross_encoder_batch_size=0)
    with pytest.raises(ValueError, match="cross_encoder_max_length"):
        Settings(cross_encoder_max_length=0)


def test_settings_reject_too_small_openai_generation_output_limit() -> None:
    with pytest.raises(ValueError, match="openai_generation_max_output_tokens"):
        Settings(openai_generation_max_output_tokens=15)


def test_settings_reject_invalid_hardening_values() -> None:
    with pytest.raises(ValueError, match="rate_limit_per_minute"):
        Settings(rate_limit_per_minute=-1)
    with pytest.raises(ValueError, match="remote_ingest_max_bytes"):
        Settings(remote_ingest_max_bytes=0)
    with pytest.raises(ValueError, match="embedding_cache_max_entries"):
        Settings(embedding_cache_max_entries=0)


def test_get_settings_loads_env_local_without_overriding_existing_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / ".env.local"
    path.write_text(
        "\n".join(
            [
                "REGLENS_APP_ENV=test",
                "REGLENS_OPENAI_GENERATION_MODEL=gpt-5.4-nano",
                "REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS=256",
                "OPENAI_API_KEY=sk-file-value",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-value")
    reset_settings_cache()

    try:
        settings = get_settings()
    finally:
        reset_settings_cache()

    assert settings.app_env == "test"
    assert settings.openai_generation_model == "gpt-5.4-nano"
    assert settings.openai_generation_max_output_tokens == 256
    assert settings.openai_api_key == "sk-env-value"
