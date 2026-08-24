"""Answer generation service for RegLens."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.domain.ids import make_content_hash, stable_id
from app.domain.models import (
    Answer,
    Citation,
    Evidence,
    ModelInfo,
    QueryEvidence,
    RetrievalCandidate,
)
from app.generation.citations import verify_answer_citations
from app.generation.llm import FakeLLMClient, GeneratedAnswer, LLMClient
from app.generation.prompts import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    PROMPT_VERSION,
    PromptBundle,
    assemble_rag_prompt,
)
from app.retrieval.service import RetrievalResult

FAKE_PROMPT_VERSION = "fake-grounded-answer-v1"


class GenerationService:
    """Convert retrieved evidence into a grounded answer."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        max_prompt_evidence: int = 8,
        prompt_version: str = PROMPT_VERSION,
        min_answer_rerank_score: float | None = None,
    ) -> None:
        if max_prompt_evidence <= 0:
            raise ValueError("max_prompt_evidence must be greater than zero")
        if min_answer_rerank_score is not None and min_answer_rerank_score < 0:
            raise ValueError("min_answer_rerank_score must be non-negative when provided")
        self.llm_client = llm_client or FakeLLMClient()
        self.max_prompt_evidence = max_prompt_evidence
        self.prompt_version = prompt_version
        self.min_answer_rerank_score = min_answer_rerank_score

    def generate(self, question: str, retrieval_result: RetrievalResult) -> Answer:
        if not self._retrieval_is_sufficient(retrieval_result):
            return Answer(
                query_id=retrieval_result.query_id,
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                citations=[],
                evidence=list(retrieval_result.evidence),
                confidence="insufficient_evidence",
                warnings=["weak_retrieval"],
                retrieval_diagnostics=retrieval_result.diagnostics,
                model_info=_model_info(
                    model_name=self.llm_client.model_name,
                    prompt_version=self.prompt_version,
                    retrieval_result=retrieval_result,
                ),
            )

        prompt = assemble_rag_prompt(
            question,
            retrieval_result.evidence,
            max_evidence=self.max_prompt_evidence,
            prompt_version=self.prompt_version,
        )
        generated = self.llm_client.generate(prompt)

        evidence_by_marker = {item.marker: item for item in prompt.evidence}
        evidence_by_id = {item.evidence_id: item for item in retrieval_result.evidence}
        candidates_by_chunk_id = {
            candidate.chunk.chunk_id: candidate for candidate in retrieval_result.candidates
        }

        warnings = list(generated.warnings)
        citations: list[Citation] = []
        for marker in generated.cited_markers:
            prompt_evidence = evidence_by_marker.get(marker)
            if prompt_evidence is None:
                warnings.append(f"unknown_citation_marker:{marker}")
                continue
            evidence = evidence_by_id[prompt_evidence.evidence_id]
            candidate = candidates_by_chunk_id.get(evidence.chunk_id)
            if candidate is None:
                warnings.append(f"missing_candidate_for_citation:{marker}")
                continue
            citations.append(
                _citation_from_generation(
                    query_id=retrieval_result.query_id,
                    marker=marker,
                    evidence=evidence,
                    candidate=candidate,
                    supports_claim=generated.claims_by_marker.get(marker, evidence.snippet),
                )
            )

        verification = verify_answer_citations(
            answer_text=generated.text,
            citations=citations,
            answer_evidence=list(retrieval_result.evidence),
            retrieved_evidence=list(retrieval_result.evidence),
            confidence=generated.confidence,
        )
        if not verification.verified:
            warnings.extend(issue.code for issue in verification.issues)

        return Answer(
            query_id=retrieval_result.query_id,
            answer=generated.text,
            citations=verification.citations,
            evidence=list(retrieval_result.evidence),
            confidence=generated.confidence,
            warnings=warnings,
            retrieval_diagnostics=retrieval_result.diagnostics,
            model_info=_model_info(
                model_name=generated.model_name,
                prompt_version=prompt.prompt_version,
                retrieval_result=retrieval_result,
            ),
        )

    def _retrieval_is_sufficient(self, retrieval_result: RetrievalResult) -> bool:
        if self.min_answer_rerank_score is None:
            return True
        if not retrieval_result.candidates:
            return False
        best_score = max(
            candidate.rerank_score or 0.0 for candidate in retrieval_result.candidates
        )
        return best_score >= self.min_answer_rerank_score

    def query_evidence_rows(
        self,
        *,
        query_id: str,
        evidence: Sequence[Evidence],
        candidates: Sequence[RetrievalCandidate],
        citations: Sequence[Citation],
    ) -> list[QueryEvidence]:
        candidates_by_chunk_id = {
            candidate.chunk.chunk_id: candidate for candidate in candidates
        }
        citations_by_chunk_id = {citation.chunk_id: citation for citation in citations}
        rows: list[QueryEvidence] = []
        for item in evidence:
            candidate = candidates_by_chunk_id.get(item.chunk_id)
            citation = citations_by_chunk_id.get(item.chunk_id)
            quoted_text = citation.quoted_text if citation is not None else None
            rows.append(
                QueryEvidence(
                    query_id=query_id,
                    evidence_id=item.evidence_id,
                    chunk_id=item.chunk_id,
                    citation_label=item.citation_label,
                    snippet=item.snippet,
                    dense_rank=candidate.dense_rank if candidate is not None else None,
                    dense_score=candidate.dense_score if candidate is not None else None,
                    keyword_rank=candidate.keyword_rank if candidate is not None else None,
                    keyword_score=candidate.keyword_score if candidate is not None else None,
                    fusion_score=candidate.fusion_score if candidate is not None else None,
                    rerank_score=candidate.rerank_score if candidate is not None else None,
                    final_rank=candidate.final_rank if candidate is not None else None,
                    quoted_text=quoted_text,
                    source_span=(
                        citation.source_span
                        if citation is not None and citation.source_span is not None
                        else item.source_span
                    ),
                    quote_hash=make_content_hash(quoted_text) if quoted_text else None,
                    verification_status=(
                        citation.verification_status if citation is not None else "not_required"
                    ),
                )
            )
        return rows


class FakeGenerationService(GenerationService):
    """Compatibility wrapper for fake-mode app wiring."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        max_prompt_evidence: int = 8,
        prompt_version: str = FAKE_PROMPT_VERSION,
        min_answer_rerank_score: float = 0.5,
    ) -> None:
        super().__init__(
            llm_client=llm_client or FakeCitedLLMClient(),
            max_prompt_evidence=max_prompt_evidence,
            prompt_version=prompt_version,
            min_answer_rerank_score=min_answer_rerank_score,
        )


class FakeCitedLLMClient(FakeLLMClient):
    """Fake LLM identity used by the cited `/query` endpoint."""

    model_name = "fake-reglens-llm-v1"

    def __init__(self, *, min_evidence_score: float = 0.0) -> None:
        super().__init__(max_cited_evidence=1, min_evidence_score=min_evidence_score)

    def generate(self, prompt: PromptBundle) -> GeneratedAnswer:
        generated = super().generate(prompt)
        if generated.confidence == "medium" and generated.cited_markers:
            return replace(generated, confidence="high")
        return generated


def _citation_from_generation(
    *,
    query_id: str,
    marker: str,
    evidence: Evidence,
    candidate: RetrievalCandidate,
    supports_claim: str,
) -> Citation:
    return Citation(
        citation_id=stable_id("cit", query_id, marker, evidence.evidence_id),
        citation_label=evidence.citation_label,
        chunk_id=evidence.chunk_id,
        source_id=candidate.chunk.source_id,
        supports_claim=supports_claim,
        url=evidence.url,
        quoted_text=supports_claim,
        verification_status="not_required",
    )


def _config_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _model_info(
    *,
    model_name: str,
    prompt_version: str,
    retrieval_result: RetrievalResult,
) -> ModelInfo:
    return ModelInfo(
        generation_model=model_name,
        embedding_model=_config_string(
            retrieval_result.diagnostics.retrieval_config.get("embedding_model")
        ),
        reranker_model=_config_string(
            retrieval_result.diagnostics.retrieval_config.get("reranker_model")
        ),
        prompt_version=prompt_version,
        mode=_config_string(retrieval_result.diagnostics.retrieval_config.get("mode")) or "mock",
    )
