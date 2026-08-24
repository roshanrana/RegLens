from __future__ import annotations

import json

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
