"""Small bounded embedding cache for optional live-provider cost control."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from threading import RLock

from app.retrieval.embeddings import Vector


class EmbeddingCache:
    """Thread-safe least-recently-used cache keyed by provider/model/text hash."""

    def __init__(self, *, max_entries: int = 10_000) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        self.max_entries = max_entries
        self._values: OrderedDict[str, Vector] = OrderedDict()
        self._lock = RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Vector | None:
        with self._lock:
            value = self._values.get(key)
            if value is None:
                self.misses += 1
                return None
            self._values.move_to_end(key)
            self.hits += 1
            return list(value)

    def set(self, key: str, value: Vector) -> None:
        with self._lock:
            self._values[key] = list(value)
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries": len(self._values),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
            }


def embedding_cache_key(
    *,
    provider: str,
    model_name: str,
    dimensions: int,
    text: str,
) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return "|".join([provider, model_name, str(dimensions), digest])
