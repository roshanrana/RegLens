from __future__ import annotations

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_scores_ranked_lists() -> None:
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]], k=60)

    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["c"] == pytest.approx(1 / 63)
    assert scores["d"] == pytest.approx(1 / 62)


def test_reciprocal_rank_fusion_does_not_double_count_duplicates_in_one_list() -> None:
    scores = reciprocal_rank_fusion([["a", "a"], ["a"]], k=10)

    assert scores["a"] == pytest.approx(1 / 11 + 1 / 11)


def test_reciprocal_rank_fusion_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="k"):
        reciprocal_rank_fusion([["a"]], k=0)

    with pytest.raises(ValueError, match="non-empty"):
        reciprocal_rank_fusion([[""]])
