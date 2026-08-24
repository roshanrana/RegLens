from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.errors import DependencyUnavailableError
from app.generation.llm import GeneratedAnswer
from app.generation.openai_llm import OpenAIGroundedAnswer, OpenAIResponsesLLMClient
from app.generation.prompts import PromptBundle, PromptEvidence


@dataclass(frozen=True)
class _ParsedContent:
    parsed: OpenAIGroundedAnswer
    type: str = "output_text"


@dataclass(frozen=True)
class _RefusalContent:
    type: str = "refusal"
    refusal: str = "cannot comply"


@dataclass(frozen=True)
class _MessageOutput:
    content: list[object]
    type: str = "message"


@dataclass(frozen=True)
class _ParseResponse:
    output_parsed: object | None = None
    output: list[object] | None = None


class _FakeResponsesEndpoint:
    def __init__(self, response: _ParseResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> _ParseResponse:
        self.calls.append(kwargs)
        return self.response


class _FailingResponsesEndpoint:
    def parse(self, **kwargs: object) -> object:
        raise RuntimeError("provider failure contained sk-test-secret")


class _QuotaError(RuntimeError):
    status_code = 429
    code = "insufficient_quota"


class _QuotaResponsesEndpoint:
    def parse(self, **kwargs: object) -> object:
        raise _QuotaError("quota failure contained sk-test-secret")


class _FakeOpenAIClient:
    def __init__(self, endpoint: object) -> None:
        self.responses = endpoint


def test_openai_responses_llm_client_parses_structured_answer() -> None:
    payload = OpenAIGroundedAnswer(
        answer="Rule 1030 requires registration before acting as a representative. [E1]",
        cited_markers=["E1"],
        claims=[
            {
                "marker": "E1",
                "claim": "Rule 1030 requires registration before acting as a representative.",
            }
        ],
        confidence="high",
        warnings=[],
    )
    endpoint = _FakeResponsesEndpoint(_ParseResponse(output_parsed=payload))
    client = OpenAIResponsesLLMClient(
        api_key="sk-test",
        model_name="gpt-5.4-nano",
        max_output_tokens=128,
        client=_FakeOpenAIClient(endpoint),
    )

    answer = client.generate(_prompt())

    assert answer == GeneratedAnswer(
        text="Rule 1030 requires registration before acting as a representative. [E1]",
        cited_markers=("E1",),
        claims_by_marker={
            "E1": "Rule 1030 requires registration before acting as a representative."
        },
        confidence="high",
        warnings=(),
        model_name="gpt-5.4-nano",
    )
    assert endpoint.calls[0]["model"] == "gpt-5.4-nano"
    assert endpoint.calls[0]["input"] == _prompt().as_messages()
    assert endpoint.calls[0]["text_format"] is OpenAIGroundedAnswer
    assert endpoint.calls[0]["max_output_tokens"] == 128
    assert endpoint.calls[0]["store"] is False


def test_openai_responses_llm_client_parses_nested_message_content() -> None:
    payload = {
        "answer": "The firm must retain specified records. [E1]",
        "cited_markers": ["E1"],
        "claims": [{"marker": "E1", "claim": "The firm must retain specified records."}],
        "confidence": "medium",
        "warnings": ["single_source"],
    }
    endpoint = _FakeResponsesEndpoint(
        _ParseResponse(output=[_MessageOutput(content=[_ParsedContent(parsed=payload)])])
    )
    client = OpenAIResponsesLLMClient(
        api_key="sk-test",
        client=_FakeOpenAIClient(endpoint),
    )

    answer = client.generate(_prompt())

    assert answer.text == "The firm must retain specified records. [E1]"
    assert answer.cited_markers == ("E1",)
    assert answer.confidence == "medium"
    assert answer.warnings == ("single_source",)


def test_openai_responses_llm_client_accepts_legacy_claims_by_marker_payload() -> None:
    payload = {
        "answer": "The firm must retain specified records. [E1]",
        "cited_markers": ["E1"],
        "claims_by_marker": {"E1": "The firm must retain specified records."},
        "confidence": "medium",
        "warnings": [],
    }
    endpoint = _FakeResponsesEndpoint(_ParseResponse(output_parsed=payload))
    client = OpenAIResponsesLLMClient(
        api_key="sk-test",
        client=_FakeOpenAIClient(endpoint),
    )

    answer = client.generate(_prompt())

    assert answer.claims_by_marker == {"E1": "The firm must retain specified records."}


def test_openai_responses_llm_client_returns_insufficient_answer_for_refusal() -> None:
    endpoint = _FakeResponsesEndpoint(
        _ParseResponse(output=[_MessageOutput(content=[_RefusalContent()])])
    )
    client = OpenAIResponsesLLMClient(
        api_key="sk-test",
        client=_FakeOpenAIClient(endpoint),
    )

    answer = client.generate(_prompt())

    assert answer.confidence == "insufficient_evidence"
    assert answer.cited_markers == ()
    assert answer.warnings == ("unparseable_openai_response",)


def test_openai_responses_llm_client_sanitizes_upstream_errors() -> None:
    secret = "sk-test-secret"
    client = OpenAIResponsesLLMClient(
        api_key=secret,
        client=_FakeOpenAIClient(_FailingResponsesEndpoint()),
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        client.generate(_prompt())

    serialized = str(exc_info.value.details)
    assert exc_info.value.message == "OpenAI generation request failed"
    assert exc_info.value.details == {
        "provider": "openai",
        "component": "llm",
        "reason": "request_failed",
        "error_type": "RuntimeError",
    }
    assert secret not in serialized


def test_openai_responses_llm_client_includes_sanitized_provider_error_code() -> None:
    client = OpenAIResponsesLLMClient(
        api_key="sk-test-secret",
        client=_FakeOpenAIClient(_QuotaResponsesEndpoint()),
    )

    with pytest.raises(DependencyUnavailableError) as exc_info:
        client.generate(_prompt())

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "llm",
        "reason": "request_failed",
        "error_type": "_QuotaError",
        "status_code": 429,
        "provider_error_code": "insufficient_quota",
    }
    assert "sk-test-secret" not in str(exc_info.value.details)


def test_openai_responses_llm_client_does_not_leak_secret_when_key_missing() -> None:
    with pytest.raises(DependencyUnavailableError) as exc_info:
        OpenAIResponsesLLMClient(
            api_key=" ",
            client=_FakeOpenAIClient(_FakeResponsesEndpoint(_ParseResponse())),
        )

    assert exc_info.value.details == {
        "provider": "openai",
        "component": "llm",
        "reason": "missing_api_key",
        "env_var": "OPENAI_API_KEY",
    }


def test_openai_responses_llm_client_rejects_too_small_output_limit() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        OpenAIResponsesLLMClient(
            api_key="sk-test",
            max_output_tokens=15,
            client=_FakeOpenAIClient(_FakeResponsesEndpoint(_ParseResponse())),
        )


def _prompt() -> PromptBundle:
    evidence = PromptEvidence(
        marker="E1",
        evidence_id="ev_1",
        chunk_id="chunk_1",
        citation_label="FINRA Rule 1030",
        title="Registration Requirements",
        snippet="Rule 1030 requires registration before acting as a representative.",
        score=0.91,
    )
    return PromptBundle(
        prompt_version="test-prompt",
        system_message="Use only evidence.",
        user_message="Question: What does Rule 1030 require?\n[E1] snippet...",
        question="What does Rule 1030 require?",
        evidence=(evidence,),
    )
