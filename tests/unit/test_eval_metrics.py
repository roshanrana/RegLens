import pytest

from app.evals.metrics import binary_accuracy, citation_precision, mean, mrr_at_k, recall_at_k


def test_recall_at_k_scores_expected_labels() -> None:
    assert recall_at_k(["A", "B", "C"], ["B", "D"], k=2) == 0.5
    assert recall_at_k(["A", "B", "C"], [], k=2) is None


def test_mrr_at_k_returns_first_relevant_rank() -> None:
    assert mrr_at_k(["A", "B", "C"], ["C"], k=3) == pytest.approx(1 / 3)
    assert mrr_at_k(["A", "B", "C"], ["C"], k=2) == 0.0
    assert mrr_at_k(["A", "B"], [], k=2) is None


def test_citation_precision_handles_refusals_and_wrong_citations() -> None:
    assert citation_precision([], []) == 1.0
    assert citation_precision([], ["A"]) == 0.0
    assert citation_precision(["A", "B"], ["A"]) == 0.5


def test_binary_accuracy_and_mean() -> None:
    assert binary_accuracy([True, False, True], [True, True, True]) == pytest.approx(2 / 3)
    assert mean([1.0, None, 0.5]) == 0.75
