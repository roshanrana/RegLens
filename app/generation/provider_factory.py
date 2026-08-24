"""Provider factory scaffolding for generation components."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.generation.service import FakeGenerationService, GenerationService


def build_generation_service(settings: Settings) -> GenerationService:
    if settings.llm_provider == "fake" and settings.use_fake_llm:
        return FakeGenerationService()
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise DependencyUnavailableError(
                "OpenAI API key is required for generation",
                details={
                    "provider": "openai",
                    "component": "llm",
                    "reason": "missing_api_key",
                    "env_var": "OPENAI_API_KEY",
                },
            )
        from app.generation.openai_llm import OpenAIResponsesLLMClient

        return GenerationService(
            llm_client=OpenAIResponsesLLMClient(
                api_key=settings.openai_api_key,
                model_name=settings.openai_generation_model,
                max_output_tokens=settings.openai_generation_max_output_tokens,
            ),
            prompt_version="openai-responses-grounded-answer-v1",
            min_answer_rerank_score=0.5,
        )
    raise DependencyUnavailableError(
        "LLM provider is not configured",
        details={
            "provider": settings.llm_provider,
            "component": "llm",
            "reason": "provider_not_configured",
        },
    )
