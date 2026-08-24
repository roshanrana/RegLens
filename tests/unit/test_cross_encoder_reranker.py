from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.errors import DependencyUnavailableError
from app.domain.models import Chunk, RetrievalCandidate
from app.retrieval.cross_encoder_reranker import CrossEncoderReranker


class _FakeCrossEncoderModel:
    def __init__(self, scores: object) -> None:
        self.scores = scores
        self.calls: list[dict[str, object]] = []

    def predict(self, pairs: object, **kwargs: object) -> object:
        self.calls.append({"pairs": pairs, **kwargs})
        return self.scores


class _FailingCrossEncoderModel:
    def predict(self, pairs: object, **kwargs: object) -> object:
        raise RuntimeError("model failure contained private local path")


class _NonNumericCrossEncoderModel:
    def predict(self, pairs: object, **kwargs: object) -> object:
        return ["not-a-number"]


@dataclass(frozen=True)
class _ArrayLike:
    values: object

    def tolist(self) -> object:
        return self.values


def test_cross_encoder_reranker_orders_candidates_by_model_score() -> None:
    unrelated = _candidate(
        "chk_disclosure",
        "FINRA Rule 1010(c)",
        "Required Disclosure Table",
        "Retail communications with fee comparisons require disclosures.",
        fusion_score=0.99,
        final_rank=1,
    )
    relevant = _candidate(
        "chk_retention",
        "FINRA Rule 1030(b)",
        "Retention Period",
        "Records required by this rulebook must be retained for six years.",
        fusion_score=0.01,
        final_rank=2,
    )
    model = _FakeCrossEncoderModel(scores=[0.1, 0.9])
    reranker = CrossEncoderReranker(
        model_name="cross-encoder/test",
        batch_size=4,
        model=model,
    )

    reranked = reranker.rerank(
        "How long must records be retained?",
        [unrelated, relevant],
    )

    assert [candidate.chunk.chunk_id for candidate in reranked] == [
        "chk_retention",
        "chk_disclosure",
    ]
    assert [candidate.final_rank for candidate in reranked] == [1, 2]
    assert [candidate.rerank_score for candidate in reranked] == [0.9, 0.1]
    assert model.calls == [
        {
            "pairs": [
                (
                    "How long must records be retained?",
                    (
                        "Citation: FINRA Rule 1010(c)\n"
                        "Title: Required Disclosure Table\n"
                        "Heading: FINRA Synthetic Rulebook > Required Disclosure Table\n"
                        "Text:\n"
                        "Retail communications with fee comparisons require disclosures."
                    ),
                ),
                (
                    "How long must records be retained?",
                    (
                        "Citation: FINRA Rule 1030(b)\n"
                        "Title: Retention Period\n"
                        "Heading: FINRA Synthetic Rulebook > Retention Period\n"
                        "Text:\n"
                        "Records required by this rulebook must be retained for six years."
                    ),
                ),
            ],
            "batch_size": 4,
            "show_progress_bar": False,
        }
    ]


def test_cross_encoder_reranker_honors_top_k_and_tie_breaks_by_prior_rank() -> None:
    first = _candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies.")
    second = _candidate(
        "chk_b",
        "FINRA Rule 1030(b)",
        "Retention Period",
        "Records must be retained.",
    )
    reranker = CrossEncoderReranker(model=_FakeCrossEncoderModel(scores=[0.5, 0.5]))

    reranked = reranker.rerank("records retained", [first, second], top_k=1)

    assert [candidate.chunk.chunk_id for candidate in reranked] == ["chk_a"]
    assert reranked[0].final_rank == 1
    assert reranked[0].rerank_score == 0.5


def test_cross_encoder_reranker_accepts_array_like_scores() -> None:
    reranker = CrossEncoderReranker(
        model=_FakeCrossEncoderModel(scores=_ArrayLike([_ArrayLike([0.2]), _ArrayLike([0.8])]))
    )
    first = _candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies.")
    second = _candidate(
        "chk_b",
        "FINRA Rule 1030(b)",
        "Retention Period",
        "Records must be retained.",
    )

    reranked = reranker.rerank("records retained", [first, second])

    assert [candidate.chunk.chunk_id for candidate in reranked] == ["chk_b", "chk_a"]
    assert [candidate.rerank_score for candidate in reranked] == [0.8, 0.2]


def test_cross_encoder_reranker_rejects_invalid_top_k() -> None:
    reranker = CrossEncoderReranker(model=_FakeCrossEncoderModel(scores=[]))

    with pytest.raises(ValueError, match="top_k"):
        reranker.rerank("records", [], top_k=0)


def test_cross_encoder_reranker_handles_empty_candidates_without_model_call() -> None:
    model = _FakeCrossEncoderModel(scores=[])
    reranker = CrossEncoderReranker(model=model)

    assert reranker.rerank("records", []) == []
    assert model.calls == []


def test_cross_encoder_reranker_rejects_unexpected_score_count() -> None:
    reranker = CrossEncoderReranker(model=_FakeCrossEncoderModel(scores=[0.1]))
    candidates = [
        _candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies."),
        _candidate("chk_b", "FINRA Rule 1030(b)", "Retention Period", "Records retained."),
    ]

    with pytest.raises(DependencyUnavailableError) as exc_info:
        reranker.rerank("records", candidates)

    assert exc_info.value.details == {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "unexpected_response",
    }


def test_cross_encoder_reranker_rejects_nonnumeric_scores() -> None:
    reranker = CrossEncoderReranker(model=_NonNumericCrossEncoderModel())

    with pytest.raises(DependencyUnavailableError) as exc_info:
        reranker.rerank(
            "records",
            [_candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies.")],
        )

    assert exc_info.value.details["reason"] == "unexpected_response"


def test_cross_encoder_reranker_sanitizes_model_errors() -> None:
    reranker = CrossEncoderReranker(model=_FailingCrossEncoderModel())

    with pytest.raises(DependencyUnavailableError) as exc_info:
        reranker.rerank(
            "records",
            [_candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies.")],
        )

    assert exc_info.value.message == "cross-encoder reranker inference failed"
    assert exc_info.value.details == {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "inference_failed",
        "error_type": "RuntimeError",
    }
    assert "private local path" not in str(exc_info.value.details)


def test_cross_encoder_reranker_diagnostics_are_serializable() -> None:
    reranker = CrossEncoderReranker(
        model_name="cross-encoder/test",
        batch_size=2,
        max_length=256,
        device="cpu",
        cache_folder=".cache/sentence-transformers",
        local_files_only=True,
        trust_remote_code=False,
        model=_FakeCrossEncoderModel(scores=[]),
    )

    assert reranker.diagnostics_config() == {
        "strategy": "sentence_transformers_cross_encoder",
        "model_name": "cross-encoder/test",
        "batch_size": 2,
        "max_length": 256,
        "device": "cpu",
        "cache_folder": ".cache/sentence-transformers",
        "local_files_only": True,
        "trust_remote_code": False,
        "candidate_text_fields": ["citation_label", "title", "heading_path", "text"],
    }


def test_cross_encoder_reranker_loads_model_with_safe_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.retrieval.cross_encoder_reranker as module

    calls: list[dict[str, object]] = []

    class FakeCrossEncoder:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            calls.append({"model_name": model_name, **kwargs})

        def predict(self, pairs: object, **kwargs: object) -> list[float]:
            return [1.0]

    monkeypatch.setattr(module, "_load_cross_encoder_class", lambda: FakeCrossEncoder)

    reranker = CrossEncoderReranker(
        model_name="cross-encoder/test",
        max_length=128,
        device="cpu",
        cache_folder=".cache/models",
        local_files_only=True,
        trust_remote_code=False,
    )

    assert calls == [
        {
            "model_name": "cross-encoder/test",
            "device": "cpu",
            "cache_folder": ".cache/models",
            "trust_remote_code": False,
            "local_files_only": True,
            "max_length": 128,
        }
    ]
    assert reranker.rerank(
        "records",
        [_candidate("chk_a", "FINRA Rule 1000(a)", "Written Policies", "Written policies.")],
    )[0].rerank_score == 1.0


def test_cross_encoder_reranker_sanitizes_model_load_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.retrieval.cross_encoder_reranker as module

    class FailingCrossEncoder:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            raise RuntimeError("model load failure contained private local path")

    monkeypatch.setattr(module, "_load_cross_encoder_class", lambda: FailingCrossEncoder)

    with pytest.raises(DependencyUnavailableError) as exc_info:
        CrossEncoderReranker(model_name="cross-encoder/test")

    assert exc_info.value.message == "cross-encoder reranker model could not be loaded"
    assert exc_info.value.details == {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "model_load_failed",
        "error_type": "RuntimeError",
    }
    assert "private local path" not in str(exc_info.value.details)


def _candidate(
    chunk_id: str,
    citation_label: str,
    title: str,
    text: str,
    *,
    fusion_score: float = 0.03,
    final_rank: int | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=_chunk(chunk_id, citation_label, title, text),
        fusion_score=fusion_score,
        final_rank=final_rank,
    )


def _chunk(chunk_id: str, citation_label: str, title: str, text: str) -> Chunk:
    return Chunk(
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
    )
