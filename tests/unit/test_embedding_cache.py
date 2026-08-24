from app.retrieval.embedding_cache import EmbeddingCache, embedding_cache_key


def test_embedding_cache_returns_copies_and_tracks_hits() -> None:
    cache = EmbeddingCache(max_entries=2)
    key = embedding_cache_key(
        provider="openai",
        model_name="text-embedding-3-small",
        dimensions=3,
        text="records retention",
    )

    assert cache.get(key) is None
    cache.set(key, [1.0, 2.0, 3.0])
    cached = cache.get(key)
    assert cached == [1.0, 2.0, 3.0]
    assert cached is not None
    cached[0] = 99.0

    assert cache.get(key) == [1.0, 2.0, 3.0]
    assert cache.stats() == {"entries": 1, "max_entries": 2, "hits": 2, "misses": 1}


def test_embedding_cache_evicts_least_recently_used_entry() -> None:
    cache = EmbeddingCache(max_entries=2)
    first = "first"
    second = "second"
    third = "third"

    cache.set(first, [1.0])
    cache.set(second, [2.0])
    assert cache.get(first) == [1.0]
    cache.set(third, [3.0])

    assert cache.get(second) is None
    assert cache.get(first) == [1.0]
    assert cache.get(third) == [3.0]
