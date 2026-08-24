from __future__ import annotations

import pytest
from dotenv import load_dotenv

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.generation.openai_llm import OpenAIResponsesLLMClient
from app.generation.prompts import PromptBundle, PromptEvidence
from app.retrieval.openai_embeddings import OpenAIEmbeddingProvider

pytestmark = pytest.mark.live_openai


def test_live_openai_embedding_provider_returns_configured_dimensions() -> None:
    settings = _live_settings()
    pytest.importorskip("openai")

    provider = OpenAIEmbeddingProvider(
        api_key=_api_key(settings),
        model_name=settings.openai_embedding_model,
        dimensions=settings.openai_embedding_dimensions,
    )

    try:
        vector = provider.embed_text("regulatory records retention")
    except DependencyUnavailableError as exc:
        _skip_external_account_block(exc)

    assert len(vector) == settings.openai_embedding_dimensions
    assert any(value != 0.0 for value in vector)


def test_live_openai_responses_llm_client_returns_cited_structured_answer() -> None:
    settings = _live_settings()
    pytest.importorskip("openai")
    client = OpenAIResponsesLLMClient(
        api_key=_api_key(settings),
        model_name=settings.openai_generation_model,
    )

    try:
        answer = client.generate(_prompt())
    except DependencyUnavailableError as exc:
        _skip_external_account_block(exc)

    assert answer.confidence in {"high", "medium", "low"}
    assert answer.cited_markers == ("E1",)
    assert "[E1]" in answer.text


def _live_settings() -> Settings:
    load_dotenv(".env.local", override=False)
    settings = Settings.from_env()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY is not configured")
    return settings


def _api_key(settings: Settings) -> str:
    assert settings.openai_api_key is not None
    return settings.openai_api_key


def _skip_external_account_block(error: DependencyUnavailableError) -> None:
    provider_code = error.details.get("provider_error_code")
    if provider_code == "insufficient_quota":
        pytest.skip("OpenAI account returned insufficient_quota")
    raise error


def _prompt() -> PromptBundle:
    evidence = PromptEvidence(
        marker="E1",
        evidence_id="ev_live_1",
        chunk_id="chunk_live_1",
        citation_label="FINRA Rule 1030(b)",
        title="Registration Requirements",
        snippet=(
            "FINRA Rule 1030(b) states that a person engaged in investment banking or "
            "securities business for a member must be registered as a representative or "
            "principal in each registration category appropriate to that person's functions."
        ),
        score=0.97,
    )
    return PromptBundle(
        prompt_version="live-test-prompt",
        system_message=(
            "You are RegLens. Use only the supplied evidence and cite every answer sentence."
        ),
        user_message=(
            "Question: What does FINRA Rule 1030(b) require before a person acts for a "
            "member firm?\n\n[E1]\n"
            f"snippet:\n<snippet>\n{evidence.snippet}\n</snippet>"
        ),
        question="What does FINRA Rule 1030(b) require?",
        evidence=(evidence,),
    )
