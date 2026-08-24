from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Self, TypeVar

from dotenv import load_dotenv

AppEnv = Literal["local", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
RagMode = Literal["mock", "local", "real"]
EmbeddingProviderName = Literal["fake", "openai"]
LLMProviderName = Literal["fake", "openai"]
RerankerProviderName = Literal["fake", "cross_encoder"]
T = TypeVar("T", bound=str)


def _env(name: str, default: str | None = None) -> str | None:
    prefixed = os.getenv(f"REGLENS_{name}")
    if prefixed is not None:
        return prefixed
    return os.getenv(name, default)


def _str_env(name: str, default: str) -> str:
    value = _env(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _secret_env(name: str) -> str | None:
    value = _env(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_str_env(name: str, default: str | None = None) -> str | None:
    value = _env(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or None


def _bool_env(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _choice_env(name: str, default: T, allowed: tuple[T, ...]) -> T:
    value = _str_env(name, default)
    if value not in allowed:
        allowed_values = ", ".join(allowed)
        raise ValueError(f"{name} must be one of: {allowed_values}")
    return value


def _tuple_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = _env(name)
    if value is None or value.strip() == "":
        return default

    stripped = value.strip()
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError(f"{name} must be a JSON array of strings")
        return tuple(item.strip() for item in parsed if item.strip())

    return tuple(item.strip() for item in stripped.split(",") if item.strip())


def _int_env(name: str, default: int) -> int:
    value = _env(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _optional_int_env(name: str, default: int | None = None) -> int | None:
    value = _env(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_name: str = "RegLens"
    app_env: AppEnv = "local"
    app_version: str = "0.1.0"
    rag_mode: RagMode = "mock"
    log_level: LogLevel = "INFO"
    database_url: str = "sqlite:///./reglens.db"
    document_storage_path: str = "./data/raw"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "regulatory_chunks"
    embedding_provider: EmbeddingProviderName = "fake"
    llm_provider: LLMProviderName = "fake"
    reranker_provider: RerankerProviderName = "fake"
    use_fake_embeddings: bool = True
    use_fake_llm: bool = True
    use_fake_reranker: bool = True
    max_query_chars: int = 2000
    default_top_k: int = 8
    max_evidence_tokens: int = 6000
    enable_hash_chain_audit: bool = True
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:8000")
    request_id_header: str = "X-Request-ID"
    api_key: str | None = None
    api_key_header: str = "X-RegLens-API-Key"
    auth_exempt_paths: tuple[str, ...] = ("/", "/health", "/ready", "/docs", "/openapi.json")
    rate_limit_per_minute: int = 0
    allowed_ingest_url_hosts: tuple[str, ...] = ("finra.org", "www.finra.org", "rules.finra.org")
    remote_ingest_max_bytes: int = 5_000_000
    enable_embedding_cache: bool = True
    embedding_cache_max_entries: int = 10_000
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    openai_generation_model: str = "gpt-5.4-nano"
    openai_generation_max_output_tokens: int = 400
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    cross_encoder_batch_size: int = 16
    cross_encoder_max_length: int | None = None
    cross_encoder_device: str | None = None
    cross_encoder_cache_folder: str | None = None
    cross_encoder_local_files_only: bool = False
    cross_encoder_trust_remote_code: bool = False

    def __post_init__(self) -> None:
        if self.rag_mode == "mock" and (
            not self.use_fake_embeddings or not self.use_fake_llm or not self.use_fake_reranker
        ):
            raise ValueError("mock mode requires fake embeddings, fake LLM, and fake reranker")
        if self.rag_mode == "mock" and (
            self.embedding_provider != "fake"
            or self.llm_provider != "fake"
            or self.reranker_provider != "fake"
        ):
            raise ValueError("mock mode requires fake provider selections")
        if self.max_query_chars <= 0:
            raise ValueError("max_query_chars must be greater than zero")
        if self.default_top_k <= 0:
            raise ValueError("default_top_k must be greater than zero")
        if self.max_evidence_tokens <= 0:
            raise ValueError("max_evidence_tokens must be greater than zero")
        if self.rate_limit_per_minute < 0:
            raise ValueError("rate_limit_per_minute must be zero or greater")
        if self.remote_ingest_max_bytes <= 0:
            raise ValueError("remote_ingest_max_bytes must be greater than zero")
        if self.embedding_cache_max_entries <= 0:
            raise ValueError("embedding_cache_max_entries must be greater than zero")
        if self.openai_embedding_dimensions <= 0:
            raise ValueError("openai_embedding_dimensions must be greater than zero")
        if self.openai_generation_max_output_tokens < 16:
            raise ValueError("openai_generation_max_output_tokens must be at least 16")
        if self.cross_encoder_batch_size <= 0:
            raise ValueError("cross_encoder_batch_size must be greater than zero")
        if self.cross_encoder_max_length is not None and self.cross_encoder_max_length <= 0:
            raise ValueError("cross_encoder_max_length must be greater than zero when provided")

    @classmethod
    def from_env(cls) -> Self:
        return cls(
            app_name=_str_env("APP_NAME", cls.app_name),
            app_env=_choice_env("APP_ENV", cls.app_env, ("local", "test", "production")),
            app_version=_str_env("APP_VERSION", cls.app_version),
            rag_mode=_choice_env("RAG_MODE", cls.rag_mode, ("mock", "local", "real")),
            log_level=_choice_env(
                "LOG_LEVEL",
                cls.log_level,
                ("DEBUG", "INFO", "WARNING", "ERROR"),
            ),
            database_url=_str_env("DATABASE_URL", cls.database_url),
            document_storage_path=_str_env("DOCUMENT_STORAGE_PATH", cls.document_storage_path),
            qdrant_url=_str_env("QDRANT_URL", cls.qdrant_url),
            qdrant_collection=_str_env("QDRANT_COLLECTION", cls.qdrant_collection),
            embedding_provider=_choice_env(
                "EMBEDDING_PROVIDER",
                cls.embedding_provider,
                ("fake", "openai"),
            ),
            llm_provider=_choice_env("LLM_PROVIDER", cls.llm_provider, ("fake", "openai")),
            reranker_provider=_choice_env(
                "RERANKER_PROVIDER",
                cls.reranker_provider,
                ("fake", "cross_encoder"),
            ),
            use_fake_embeddings=_bool_env("USE_FAKE_EMBEDDINGS", cls.use_fake_embeddings),
            use_fake_llm=_bool_env("USE_FAKE_LLM", cls.use_fake_llm),
            use_fake_reranker=_bool_env("USE_FAKE_RERANKER", cls.use_fake_reranker),
            max_query_chars=_int_env("MAX_QUERY_CHARS", cls.max_query_chars),
            default_top_k=_int_env("DEFAULT_TOP_K", cls.default_top_k),
            max_evidence_tokens=_int_env("MAX_EVIDENCE_TOKENS", cls.max_evidence_tokens),
            enable_hash_chain_audit=_bool_env(
                "ENABLE_HASH_CHAIN_AUDIT", cls.enable_hash_chain_audit
            ),
            cors_origins=_tuple_env("CORS_ORIGINS", cls.cors_origins),
            request_id_header=_str_env("REQUEST_ID_HEADER", cls.request_id_header),
            api_key=_secret_env("API_KEY"),
            api_key_header=_str_env("API_KEY_HEADER", cls.api_key_header),
            auth_exempt_paths=_tuple_env("AUTH_EXEMPT_PATHS", cls.auth_exempt_paths),
            rate_limit_per_minute=_int_env(
                "RATE_LIMIT_PER_MINUTE",
                cls.rate_limit_per_minute,
            ),
            allowed_ingest_url_hosts=_tuple_env(
                "ALLOWED_INGEST_URL_HOSTS",
                cls.allowed_ingest_url_hosts,
            ),
            remote_ingest_max_bytes=_int_env(
                "REMOTE_INGEST_MAX_BYTES",
                cls.remote_ingest_max_bytes,
            ),
            enable_embedding_cache=_bool_env(
                "ENABLE_EMBEDDING_CACHE",
                cls.enable_embedding_cache,
            ),
            embedding_cache_max_entries=_int_env(
                "EMBEDDING_CACHE_MAX_ENTRIES",
                cls.embedding_cache_max_entries,
            ),
            openai_api_key=_secret_env("OPENAI_API_KEY"),
            openai_embedding_model=_str_env(
                "OPENAI_EMBEDDING_MODEL",
                cls.openai_embedding_model,
            ),
            openai_embedding_dimensions=_int_env(
                "OPENAI_EMBEDDING_DIMENSIONS",
                cls.openai_embedding_dimensions,
            ),
            openai_generation_model=_str_env(
                "OPENAI_GENERATION_MODEL",
                cls.openai_generation_model,
            ),
            openai_generation_max_output_tokens=_int_env(
                "OPENAI_GENERATION_MAX_OUTPUT_TOKENS",
                cls.openai_generation_max_output_tokens,
            ),
            cross_encoder_model=_str_env("CROSS_ENCODER_MODEL", cls.cross_encoder_model),
            cross_encoder_batch_size=_int_env(
                "CROSS_ENCODER_BATCH_SIZE",
                cls.cross_encoder_batch_size,
            ),
            cross_encoder_max_length=_optional_int_env(
                "CROSS_ENCODER_MAX_LENGTH",
                cls.cross_encoder_max_length,
            ),
            cross_encoder_device=_optional_str_env(
                "CROSS_ENCODER_DEVICE",
                cls.cross_encoder_device,
            ),
            cross_encoder_cache_folder=_optional_str_env(
                "CROSS_ENCODER_CACHE_FOLDER",
                cls.cross_encoder_cache_folder,
            ),
            cross_encoder_local_files_only=_bool_env(
                "CROSS_ENCODER_LOCAL_FILES_ONLY",
                cls.cross_encoder_local_files_only,
            ),
            cross_encoder_trust_remote_code=_bool_env(
                "CROSS_ENCODER_TRUST_REMOTE_CODE",
                cls.cross_encoder_trust_remote_code,
            ),
        )

    @property
    def is_fake_mode(self) -> bool:
        return self.rag_mode == "mock"

    @property
    def live_providers_enabled(self) -> bool:
        return (
            not self.use_fake_embeddings
            or not self.use_fake_llm
            or not self.use_fake_reranker
            or self.embedding_provider != "fake"
            or self.llm_provider != "fake"
            or self.reranker_provider != "fake"
        )


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    load_dotenv(".env.local", override=False)
    return Settings.from_env()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
