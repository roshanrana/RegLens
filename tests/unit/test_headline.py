from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.evals.headline import (
    KPI_ORDER,
    CostSummary,
    RerankerComparison,
    assert_valid_headline,
    build_headline,
    validate_headline,
    write_headline,
)

COMMITTED_HEADLINE = Path("metrics/headline.json")


def _report() -> dict[str, Any]:
    answerable = {
        "expected_citations": ["FINRA Rule 1000(a)"],
        "actual_refusal": False,
        "expected_refusal": False,
        "quote_verified": True,
    }
    refusal = {
        "expected_citations": [],
        "actual_refusal": True,
        "expected_refusal": True,
        "quote_verified": True,
    }
    return {
        "summary": {
            "refusal_accuracy": 1.0,
            "quote_verification_rate": 1.0,
            "citation_precision": 1.0,
            "retrieval_recall_at_3": 1.0,
            "retrieval_recall_at_5": 1.0,
            "retrieval_recall_at_10": 1.0,
            "answer_safety": 1.0,
            "warning_recall": 1.0,
        },
        "audit_verify": {"record_count": 3, "failure_count": 0, "verified": True},
        "cases": [answerable, answerable, refusal],
    }


def _comparison() -> RerankerComparison:
    return RerankerComparison(
        recall_on={1: 1.0, 3: 1.0, 5: 1.0, 10: 1.0},
        recall_off={1: 0.5, 3: 1.0, 5: 1.0, 10: 1.0},
        labeled_cases=2,
        total_cases=3,
        chunk_count=15,
        reranker_model="fake-lexical-reranker-v1",
    )


def _costs() -> CostSummary:
    return CostSummary(
        query_count=3,
        mean_priced_cost_usd=0.000031,
        mean_observed_cost_usd=0.0,
        mean_input_tokens=120.0,
        mean_output_tokens=20.0,
        mean_embedding_tokens=8.0,
        generation_model="gpt-5.4-nano",
        embedding_model="text-embedding-3-small",
    )


def test_build_headline_leads_with_abstention_and_matches_schema() -> None:
    headline = build_headline(_report(), _comparison(), _costs(), seed=0)

    assert tuple(headline["kpis"]) == KPI_ORDER
    assert KPI_ORDER[0] == "abstention_rate"
    assert headline["kpis"]["abstention_rate"]["value"] == "33.3%"
    assert "1 of 3" in headline["kpis"]["abstention_rate"]["note"]
    assert headline["kpis"]["cost_per_query"]["value"] == "$0.000031"
    assert headline["bars"]["rows"][0] == {
        "label": "R@1 reranker ON",
        "value": 100.0,
        "max": 100,
        "display": "100.0%",
        "accent": "teal",
    }
    assert headline["bars"]["rows"][1]["value"] == 50.0
    pending = [row for row in headline["facts"]["rows"] if row["status"] == "pending"]
    assert {row["label"].split(" (")[0] for row in pending} == {
        "Cross-encoder reranker",
        "Live OpenAI cost per query",
    }
    assert validate_headline(headline) == []


@pytest.mark.parametrize(
    ("mutate", "expected_fragment"),
    [
        (lambda doc: doc.pop("facts"), "missing top-level key: facts"),
        (lambda doc: doc["kpis"]["recall_at_5"].update(accent="green"), "accent must be one of"),
        (lambda doc: doc["kpis"]["recall_at_5"].pop("note"), "note must be a non-empty string"),
        (lambda doc: doc["bars"]["rows"][0].update(value=101), "0 <= value <= max"),
        (lambda doc: doc["bars"]["rows"][0].update(value="100"), "value must be a number"),
        (lambda doc: doc["facts"]["rows"][0].update(status="done"), "status must be one of"),
        (lambda doc: doc["bars"].update(rows=[]), "rows must be a non-empty array"),
    ],
)
def test_validate_headline_reports_schema_violations(mutate: Any, expected_fragment: str) -> None:
    document = copy.deepcopy(build_headline(_report(), _comparison(), _costs(), seed=0))

    mutate(document)
    errors = validate_headline(document)

    assert any(expected_fragment in error for error in errors), errors
    with pytest.raises(ValueError, match="schema validation"):
        assert_valid_headline(document)


def test_write_headline_refuses_invalid_document(tmp_path: Path) -> None:
    document = build_headline(_report(), _comparison(), _costs(), seed=0)
    document["facts"]["rows"][0]["status"] = "unknown"

    with pytest.raises(ValueError, match="schema validation"):
        write_headline(document, tmp_path / "headline.json")

    assert not (tmp_path / "headline.json").exists()


def test_committed_headline_is_valid_and_ordered() -> None:
    document = json.loads(COMMITTED_HEADLINE.read_text(encoding="utf-8"))

    assert validate_headline(document) == []
    assert tuple(document["kpis"]) == KPI_ORDER
