"""Optional sentence-transformers cross-encoder reranker."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from app.core.errors import DependencyUnavailableError
from app.domain.models import RetrievalCandidate


class CrossEncoderReranker:
    """Rerank candidates with a sentence-transformers CrossEncoder model."""

    def __init__(
        self,
        *,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 16,
        max_length: int | None = None,
        device: str | None = None,
        cache_folder: str | None = None,
        local_files_only: bool = False,
        trust_remote_code: bool = False,
        model: Any | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if max_length is not None and max_length <= 0:
            raise ValueError("max_length must be greater than zero when provided")

        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.device = device
        self.cache_folder = cache_folder
        self.local_files_only = local_files_only
        self.trust_remote_code = trust_remote_code
        self._model = model or self._load_model()

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        *,
        top_k: int | None = None,
    ) -> list[RetrievalCandidate]:
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than zero when provided")
        if not candidates:
            return []

        pairs = [(query, _candidate_text(candidate)) for candidate in candidates]
        try:
            raw_scores = self._model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "cross-encoder reranker inference failed",
                details=_inference_failure_details(exc),
            ) from exc

        scores = _score_values(raw_scores)
        if len(scores) != len(candidates):
            raise DependencyUnavailableError(
                "cross-encoder reranker response count did not match candidate count",
                details=_unexpected_response_details(),
            )

        scored = list(zip(scores, range(len(candidates)), candidates, strict=True))
        scored.sort(key=_rerank_sort_key)
        if top_k is not None:
            scored = scored[:top_k]

        return [
            replace(candidate, rerank_score=float(score), final_rank=rank)
            for rank, (score, _index, candidate) in enumerate(scored, start=1)
        ]

    def diagnostics_config(self) -> dict[str, object]:
        return {
            "strategy": "sentence_transformers_cross_encoder",
            "model_name": self.model_name,
            "batch_size": self.batch_size,
            "max_length": self.max_length,
            "device": self.device,
            "cache_folder": self.cache_folder,
            "local_files_only": self.local_files_only,
            "trust_remote_code": self.trust_remote_code,
            "candidate_text_fields": ["citation_label", "title", "heading_path", "text"],
        }

    def _load_model(self) -> Any:
        cross_encoder_class = _load_cross_encoder_class()
        try:
            return cross_encoder_class(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_folder,
                trust_remote_code=self.trust_remote_code,
                local_files_only=self.local_files_only,
                max_length=self.max_length,
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "cross-encoder reranker model could not be loaded",
                details=_model_load_failure_details(exc),
            ) from exc


def _load_cross_encoder_class() -> Any:
    try:
        module = importlib.import_module("sentence_transformers")
    except ImportError as exc:
        raise DependencyUnavailableError(
            "sentence-transformers is not installed",
            details={
                "provider": "cross_encoder",
                "component": "reranker",
                "reason": "package_missing",
                "package": "sentence-transformers",
                "extra": "rerank",
            },
        ) from exc

    cross_encoder_class = getattr(module, "CrossEncoder", None)
    if cross_encoder_class is None:
        raise DependencyUnavailableError(
            "sentence-transformers does not expose the expected CrossEncoder class",
            details=_unexpected_package_details(),
        )
    return cross_encoder_class


def _candidate_text(candidate: RetrievalCandidate) -> str:
    chunk = candidate.chunk
    return "\n".join(
        [
            f"Citation: {chunk.citation_label}",
            f"Title: {chunk.title}",
            f"Heading: {' > '.join(chunk.heading_path)}",
            "Text:",
            chunk.text,
        ]
    )


def _score_values(raw_scores: object) -> list[float]:
    value = _tolist(raw_scores)
    if isinstance(value, int | float):
        return [float(value)]
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise DependencyUnavailableError(
            "cross-encoder reranker returned an unexpected score payload",
            details=_unexpected_response_details(),
        )

    scores: list[float] = []
    for item in value:
        item_value = _tolist(item)
        if isinstance(item_value, Sequence) and not isinstance(item_value, str | bytes):
            if not item_value:
                raise DependencyUnavailableError(
                    "cross-encoder reranker returned an empty score row",
                    details=_unexpected_response_details(),
                )
            item_value = item_value[0]
        scores.append(_float_score(item_value))
    return scores


def _tolist(value: object) -> object:
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return tolist()
    return value


def _float_score(value: object) -> float:
    if not isinstance(value, int | float | str):
        raise DependencyUnavailableError(
            "cross-encoder reranker returned a nonnumeric score",
            details=_unexpected_response_details(),
        )
    try:
        return float(value)
    except ValueError as exc:
        raise DependencyUnavailableError(
            "cross-encoder reranker returned a nonnumeric score",
            details=_unexpected_response_details(),
        ) from exc


def _rerank_sort_key(item: tuple[float, int, RetrievalCandidate]) -> tuple[float, int, float, str]:
    score, original_index, candidate = item
    prior_rank = candidate.final_rank or original_index + 1
    return (-score, prior_rank, -candidate.fusion_score, candidate.chunk.chunk_id)


def _unexpected_package_details() -> dict[str, str]:
    return {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "unexpected_package_shape",
        "package": "sentence-transformers",
    }


def _unexpected_response_details() -> dict[str, str]:
    return {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "unexpected_response",
    }


def _inference_failure_details(exc: Exception) -> dict[str, object]:
    return {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "inference_failed",
        "error_type": exc.__class__.__name__,
    }


def _model_load_failure_details(exc: Exception) -> dict[str, object]:
    return {
        "provider": "cross_encoder",
        "component": "reranker",
        "reason": "model_load_failed",
        "error_type": exc.__class__.__name__,
    }
