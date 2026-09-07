from __future__ import annotations

import json

from app.evals.headline import KPI_ORDER, validate_headline
from scripts.run_evals import run_evals


def test_eval_runner_writes_json_and_markdown_reports(tmp_path) -> None:
    report = run_evals(reports_dir=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["retrieval_recall_at_10"] >= 0.95
    assert report["summary"]["answer_safety"] == 1.0
    assert report["summary"]["warning_recall"] == 1.0
    assert report["summary"]["audit_completeness"] == 1.0
    assert any(case["id"] == "source_instruction_injection" for case in report["cases"])
    assert (tmp_path / "eval-latest.json").exists()
    assert (tmp_path / "eval-latest.md").exists()

    persisted = json.loads((tmp_path / "eval-latest.json").read_text(encoding="utf-8"))
    assert persisted["summary"] == report["summary"]
    assert "RegLens Eval Report" in (tmp_path / "eval-latest.md").read_text(encoding="utf-8")
    assert not (tmp_path / "headline.json").exists()


def test_eval_runner_writes_schema_valid_headline_from_observed_values(tmp_path) -> None:
    headline_path = tmp_path / "metrics" / "headline.json"

    report = run_evals(reports_dir=tmp_path, headline_path=headline_path)
    headline = json.loads(headline_path.read_text(encoding="utf-8"))

    assert report["seed"] == 0
    assert validate_headline(headline) == []
    assert tuple(headline["kpis"]) == KPI_ORDER
    abstained = sum(1 for case in report["cases"] if case["actual_refusal"])
    assert headline["kpis"]["abstention_rate"]["value"] == (
        f"{abstained / len(report['cases']) * 100:.1f}%"
    )
    assert all(case["observed_cost_usd"] == 0.0 for case in report["cases"])
    assert all(case["priced_cost_usd"] > 0 for case in report["cases"])
    assert len(headline["bars"]["rows"]) == 8
    assert all(row["value"] <= row["max"] for row in headline["bars"]["rows"])


def test_eval_runner_headline_is_deterministic(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    run_evals(reports_dir=tmp_path / "a", headline_path=first)
    run_evals(reports_dir=tmp_path / "b", headline_path=second)

    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
