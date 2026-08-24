"""Deterministic evaluation metrics for RegLens."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def recall_at_k(
    retrieved: Sequence[str],
    expected: Sequence[str],
    *,
    k: int,
) -> float | None:
    """Return expected-label recall at k, or None when no labels are expected."""

    if k <= 0:
        raise ValueError("k must be greater than zero")
    expected_set = set(expected)
    if not expected_set:
        return None
    retrieved_set = set(retrieved[:k])
    return len(expected_set.intersection(retrieved_set)) / len(expected_set)


def mrr_at_k(
    retrieved: Sequence[str],
    expected: Sequence[str],
    *,
    k: int,
) -> float | None:
    """Return reciprocal rank of the first relevant label at k."""

    if k <= 0:
        raise ValueError("k must be greater than zero")
    expected_set = set(expected)
    if not expected_set:
        return None
    for rank, label in enumerate(retrieved[:k], start=1):
        if label in expected_set:
            return 1.0 / rank
    return 0.0


def citation_precision(cited: Sequence[str], expected: Sequence[str]) -> float:
    """Return the share of citations that match expected support labels."""

    if not cited:
        return 1.0 if not expected else 0.0
    expected_set = set(expected)
    return sum(1 for label in cited if label in expected_set) / len(cited)


def binary_accuracy(actual: Iterable[bool], expected: Iterable[bool]) -> float:
    actual_list = list(actual)
    expected_list = list(expected)
    if len(actual_list) != len(expected_list):
        raise ValueError("actual and expected must have the same length")
    if not actual_list:
        return 0.0
    return sum(
        1 for left, right in zip(actual_list, expected_list, strict=True) if left == right
    ) / len(actual_list)


def mean(values: Iterable[float | None]) -> float:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return 0.0
    return sum(numeric) / len(numeric)
