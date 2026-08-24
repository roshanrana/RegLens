from __future__ import annotations

import os

import pytest

from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.cross_encoder_reranker import CrossEncoderReranker

pytestmark = [pytest.mark.integration, pytest.mark.requires_model_download]


def test_optional_cross_encoder_model_ranks_relevant_candidate() -> None:
    if os.getenv("REGLENS_RUN_MODEL_DOWNLOAD_TESTS", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("set REGLENS_RUN_MODEL_DOWNLOAD_TESTS=true to allow model download")
    pytest.importorskip("sentence_transformers")
    model_name = os.getenv(
        "REGLENS_CROSS_ENCODER_MODEL",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    reranker = CrossEncoderReranker(model_name=model_name, batch_size=2)

    unrelated = _candidate(
        "chk_disclosure",
        "FINRA Rule 1010(c)",
        "Required Disclosure Table",
        "Retail communications with fee comparisons require disclosures.",
    )
    relevant = _candidate(
        "chk_retention",
        "FINRA Rule 1030(b)",
        "Retention Period",
        "Records required by this rulebook must be retained for six years.",
    )

    reranked = reranker.rerank(
        "How long must records be retained?",
        [unrelated, relevant],
    )

    assert reranked[0].chunk.chunk_id == "chk_retention"
    assert reranked[0].rerank_score is not None


def _candidate(
    chunk_id: str,
    citation_label: str,
    title: str,
    text: str,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=Chunk(
            chunk_id=chunk_id,
            section_id=f"sec_{chunk_id}",
            source_id="src_finra",
            corpus_id="finra-synthetic",
            corpus_version="2026-08-19",
            citation_label=citation_label,
            title=title,
            heading_path=["FINRA Synthetic Rulebook", title],
            text=text,
            token_count=len(text.split()),
            chunk_index=0,
            section_chunk_count=1,
            source_checksum="checksum",
        ),
        fusion_score=0.03,
    )
