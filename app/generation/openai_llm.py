"""OpenAI Responses-backed grounded answer generation."""

from __future__ import annotations

import importlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import DependencyUnavailableError
from app.domain.models import Confidence
from app.generation.llm import GeneratedAnswer
from app.generation.prompts import INSUFFICIENT_EVIDENCE_ANSWER, PromptBundle

GroundedConfidence = Literal["high", "medium", "low", "insufficient_evidence"]


class OpenAIEvidenceClaim(BaseModel):
    """One source-supported claim associated with an evidence marker."""

    model_config = ConfigDict(extra="forbid")

    marker: str = Field(description="Evidence marker, such as E1.")
    claim: str = Field(description="Short claim supported by the evidence marker.")


class OpenAIGroundedAnswer(BaseModel):
    """Structured answer shape required from the OpenAI Responses API."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        description=(
            "Grounded answer text. Every supported sentence must include one or more supplied "
            "evidence markers such as [E1]."
        )
    )
    cited_markers: list[str] = Field(
        description="Evidence markers cited in the answer, such as E1 or E2."
    )
    claims: list[OpenAIEvidenceClaim] = Field(
        description="Short supported claim text for each cited evidence marker."
    )
    confidence: GroundedConfidence = Field(
        description="Confidence based only on the retrieved evidence."
    )
    warnings: list[str] = Field(
        description="Provider warnings, or an empty list when none apply."
    )


class OpenAIResponsesLLMClient:
    """LLM client that asks OpenAI for schema-constrained cited answers."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "gpt-5.4-nano",
        max_output_tokens: int = 400,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise DependencyUnavailableError(
                "OpenAI API key is required for generation",
                details=_missing_key_details("llm"),
            )
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        if max_output_tokens < 16:
            raise ValueError("max_output_tokens must be at least 16")

        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self._client = client or _load_openai_client_class()(api_key=api_key)

    def generate(self, prompt: PromptBundle) -> GeneratedAnswer:
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                input=prompt.as_messages(),
                text_format=OpenAIGroundedAnswer,
                max_output_tokens=self.max_output_tokens,
                store=False,
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "OpenAI generation request failed",
                details=_request_failure_details("llm", exc),
            ) from exc
        payload = _extract_payload(response)
        if payload is None:
            return GeneratedAnswer(
                text=INSUFFICIENT_EVIDENCE_ANSWER,
                cited_markers=(),
                claims_by_marker={},
                confidence="insufficient_evidence",
                warnings=("unparseable_openai_response",),
                model_name=self.model_name,
            )

        return GeneratedAnswer(
            text=payload.answer,
            cited_markers=tuple(payload.cited_markers),
            claims_by_marker={claim.marker: claim.claim for claim in payload.claims},
            confidence=_confidence(payload.confidence),
            warnings=tuple(payload.warnings),
            model_name=self.model_name,
        )


def _extract_payload(response: object) -> OpenAIGroundedAnswer | None:
    output_parsed = getattr(response, "output_parsed", None)
    payload = _coerce_payload(output_parsed)
    if payload is not None:
        return payload

    for output in getattr(response, "output", []) or []:
        if getattr(output, "type", None) != "message":
            continue
        for item in getattr(output, "content", []) or []:
            if getattr(item, "type", None) == "refusal":
                return None
            payload = _coerce_payload(getattr(item, "parsed", None))
            if payload is not None:
                return payload
    return None


def _coerce_payload(candidate: object) -> OpenAIGroundedAnswer | None:
    if isinstance(candidate, OpenAIGroundedAnswer):
        return candidate
    if isinstance(candidate, dict):
        return OpenAIGroundedAnswer.model_validate(_normalize_payload(candidate))
    return None


def _normalize_payload(candidate: dict[str, object]) -> dict[str, object]:
    if "claims" in candidate or "claims_by_marker" not in candidate:
        return candidate
    raw_claims = candidate["claims_by_marker"]
    if not isinstance(raw_claims, dict):
        return candidate
    normalized = dict(candidate)
    normalized["claims"] = [
        {"marker": str(marker), "claim": str(claim)} for marker, claim in raw_claims.items()
    ]
    normalized.pop("claims_by_marker", None)
    return normalized


def _confidence(value: GroundedConfidence) -> Confidence:
    return value


def _load_openai_client_class() -> Any:
    try:
        module = importlib.import_module("openai")
    except ImportError as exc:
        raise DependencyUnavailableError(
            "OpenAI SDK is not installed",
            details={
                "provider": "openai",
                "component": "llm",
                "reason": "package_missing",
                "package": "openai",
                "extra": "openai",
            },
        ) from exc

    client_class = getattr(module, "OpenAI", None)
    if client_class is None:
        raise DependencyUnavailableError(
            "OpenAI SDK does not expose the expected client",
            details={
                "provider": "openai",
                "component": "llm",
                "reason": "unexpected_response",
            },
        )
    return client_class


def _missing_key_details(component: str) -> dict[str, str]:
    return {
        "provider": "openai",
        "component": component,
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }


def _request_failure_details(component: str, exc: Exception) -> dict[str, object]:
    details: dict[str, object] = {
        "provider": "openai",
        "component": component,
        "reason": "request_failed",
        "error_type": exc.__class__.__name__,
    }
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        details["status_code"] = status_code
    provider_error_code = getattr(exc, "code", None)
    if isinstance(provider_error_code, str) and provider_error_code.strip():
        details["provider_error_code"] = provider_error_code
    return details
