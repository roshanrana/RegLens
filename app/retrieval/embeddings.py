"""Deterministic fake embeddings for local retrieval tests.

The fake provider intentionally behaves like a tiny lexical embedding model:
similar text lands close together, exact regulatory terms matter, and every
output is stable across processes. It is not a semantic model, but it gives
fake-mode retrieval enough signal to develop ranking and API behavior before
OpenAI or Qdrant are introduced.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

Vector = list[float]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "must",
    "of",
    "on",
    "or",
    "shall",
    "that",
    "the",
    "their",
    "to",
    "with",
}


class EmbeddingProvider(Protocol):
    """Swappable interface for embedding providers."""

    model_name: str

    @property
    def dimensions(self) -> int:
        ...

    def embed_text(self, text: str) -> Vector:
        ...

    def embed_texts(self, texts: Iterable[str]) -> list[Vector]:
        ...


@dataclass(frozen=True)
class FakeEmbeddingConfig:
    dimensions: int = 256
    include_bigrams: bool = True
    include_stems: bool = True

    def __post_init__(self) -> None:
        if self.dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")


class FakeEmbeddingProvider:
    """Small deterministic embedding provider for fake mode."""

    model_name = "fake-hashed-lexical-v1"

    def __init__(self, config: FakeEmbeddingConfig | None = None) -> None:
        self.config = config or FakeEmbeddingConfig()

    @property
    def dimensions(self) -> int:
        return self.config.dimensions

    def embed_text(self, text: str) -> Vector:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        features = list(self._features(text))
        vector = [0.0] * self.dimensions
        if not features:
            return vector

        for feature, weight in features:
            index, sign = _hash_feature(feature, self.dimensions)
            vector[index] += sign * weight

        return l2_normalize(vector)

    def embed_texts(self, texts: Iterable[str]) -> list[Vector]:
        return [self.embed_text(text) for text in texts]

    def _features(self, text: str) -> Iterable[tuple[str, float]]:
        tokens = tokenize(text)
        if not tokens:
            return

        for token in tokens:
            if token in _STOPWORDS:
                continue
            yield f"tok:{token}", _token_weight(token)
            if self.config.include_stems:
                stem = simple_stem(token)
                if stem != token and stem not in _STOPWORDS:
                    yield f"stem:{stem}", 0.65 * _token_weight(stem)

        if self.config.include_bigrams:
            content_tokens = [token for token in tokens if token not in _STOPWORDS]
            for first, second in zip(content_tokens, content_tokens[1:], strict=False):
                yield f"bigram:{first}|{second}", 0.55


def tokenize(text: str) -> list[str]:
    """Return lowercase lexical tokens with regulatory citations split cleanly."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [match.group(0) for match in _TOKEN_RE.finditer(text.lower())]


def simple_stem(token: str) -> str:
    """Apply a conservative suffix trim to improve fake lexical recall."""

    if len(token) <= 4:
        return token
    for suffix in ("ies", "ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            if suffix == "ies":
                return token[: -len(suffix)] + "y"
            return token[: -len(suffix)]
    return token


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def l2_normalize(vector: Sequence[float]) -> Vector:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [value / norm for value in vector]


def is_zero_vector(vector: Sequence[float]) -> bool:
    return all(value == 0.0 for value in vector)


def _hash_feature(feature: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], byteorder="big") % dimensions
    sign = 1.0 if digest[8] % 2 == 0 else -1.0
    return index, sign


def _token_weight(token: str) -> float:
    if token.isdigit():
        return 1.4
    if any(character.isdigit() for character in token):
        return 1.25
    if len(token) >= 8:
        return 1.15
    return 1.0
