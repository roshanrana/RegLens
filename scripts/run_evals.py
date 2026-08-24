from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.evals.metrics import citation_precision, mean, mrr_at_k, recall_at_k
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS_PATH = ROOT / "app" / "evals" / "fixtures" / "questions.json"
DEFAULT_REPORTS_DIR = ROOT / "reports"
DEFAULT_THRESHOLDS = {
    "retrieval_recall_at_3": 0.85,
    "retrieval_recall_at_5": 0.9,
    "retrieval_recall_at_10": 0.95,
    "retrieval_mrr_at_10": 0.85,
    "citation_precision": 0.85,
    "quote_verification_rate": 0.95,
    "refusal_accuracy": 0.9,
    "answer_safety": 1.0,
    "warning_recall": 1.0,
    "audit_completeness": 1.0,
}


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    behavior: str
    expected_citations: list[str]
    corpus_id: str = "finra-synthetic"
    corpus_version: str = "2026-08-19"
    source_path: str | None = None
    forbidden_answer_terms: list[str] | None = None
    expected_warnings: list[str] | None = None

    @property
    def expects_refusal(self) -> bool:
        return self.behavior in {"insufficient_evidence", "out_of_scope"}

    @property
    def forbidden_terms(self) -> list[str]:
        return list(self.forbidden_answer_terms or [])

    @property
    def warnings_expected(self) -> list[str]:
        return list(self.expected_warnings or [])


def run_evals(
    *,
    questions_path: Path = DEFAULT_QUESTIONS_PATH,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    top_k: int = 10,
) -> dict[str, Any]:
    questions = _load_questions(questions_path)
    reports_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        app_env="test",
        rag_mode="mock",
        default_top_k=top_k,
        database_url="sqlite:///:memory:",
    )
    app = create_app(settings)
    case_results: list[dict[str, Any]] = []

    with TestClient(app) as client:
        _ingest_question_sources(client, questions)
        for item in questions:
            started_at = perf_counter()
            response = client.post(
                "/query",
                json={
                    "question": item.question,
                    "corpus_id": item.corpus_id,
                    "corpus_version": item.corpus_version,
                    "top_k": top_k,
                },
            )
            latency_ms = int(round((perf_counter() - started_at) * 1000))
            case_results.append(
                _case_result(item, response.json(), response.status_code, latency_ms)
            )

        audit_verify = client.get("/audit/verify").json()

    summary = _summary(case_results)
    thresholds = dict(DEFAULT_THRESHOLDS)
    threshold_results = {
        name: summary[name] >= threshold for name, threshold in thresholds.items()
    }
    report = {
        "passed": all(threshold_results.values()),
        "summary": summary,
        "thresholds": thresholds,
        "threshold_results": threshold_results,
        "audit_verify": audit_verify,
        "cases": case_results,
    }
    _write_reports(report, reports_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic RegLens fake-mode evals.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args(argv)

    report = run_evals(
        questions_path=args.questions,
        reports_dir=args.reports_dir,
        top_k=args.top_k,
    )
    print(json.dumps({"passed": report["passed"], "summary": report["summary"]}, indent=2))
    return 0 if report["passed"] else 1


def _load_questions(path: Path) -> list[EvalQuestion]:
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    questions: list[EvalQuestion] = []
    for item in raw_items:
        questions.append(
            EvalQuestion(
                id=str(item["id"]),
                question=str(item["question"]),
                behavior=str(item["behavior"]),
                expected_citations=[str(label) for label in item["expected_citations"]],
                corpus_id=str(item.get("corpus_id", "finra-synthetic")),
                corpus_version=str(item.get("corpus_version", "2026-08-19")),
                source_path=(
                    str(item["source_path"])
                    if item.get("source_path") is not None
                    else None
                ),
                forbidden_answer_terms=[
                    str(term) for term in item.get("forbidden_answer_terms", [])
                ],
                expected_warnings=[
                    str(warning) for warning in item.get("expected_warnings", [])
                ],
            )
        )
    return questions


def _ingest_question_sources(client: TestClient, questions: list[EvalQuestion]) -> None:
    ingested_paths: set[str] = set()
    for question in questions:
        if question.source_path is None or question.source_path in ingested_paths:
            continue
        response = client.post(
            "/admin/ingest",
            json={
                "path": question.source_path,
                "input_type": "markdown",
            },
        )
        if response.status_code != 200:
            raise RuntimeError(
                "failed to ingest eval source "
                f"{question.source_path}: {response.status_code} {response.text}"
            )
        ingested_paths.add(question.source_path)


def _case_result(
    question: EvalQuestion,
    body: dict[str, Any],
    status_code: int,
    latency_ms: int,
) -> dict[str, Any]:
    evidence_labels = [str(item["citation_label"]) for item in body.get("evidence", [])]
    cited_labels = [str(item["citation_label"]) for item in body.get("citations", [])]
    confidence = str(body.get("confidence", ""))
    expected = question.expected_citations
    actual_refusal = confidence == "insufficient_evidence"
    expected_refusal = question.expects_refusal
    citations = body.get("citations", [])
    warnings = [str(warning) for warning in body.get("warnings", [])]
    answer = str(body.get("answer", ""))
    forbidden_terms = question.forbidden_terms
    expected_warnings = question.warnings_expected
    answer_safe = _answer_excludes_terms(answer, forbidden_terms)
    expected_warnings_present = all(warning in warnings for warning in expected_warnings)

    return {
        "id": question.id,
        "question": question.question,
        "behavior": question.behavior,
        "status_code": status_code,
        "expected_citations": expected,
        "retrieved_citations": evidence_labels,
        "cited_citations": cited_labels,
        "warnings": warnings,
        "expected_warnings": expected_warnings,
        "forbidden_answer_terms": forbidden_terms,
        "confidence": confidence,
        "answer": answer,
        "recall_at_3": recall_at_k(evidence_labels, expected, k=3),
        "recall_at_5": recall_at_k(evidence_labels, expected, k=5),
        "recall_at_10": recall_at_k(evidence_labels, expected, k=10),
        "mrr_at_10": mrr_at_k(evidence_labels, expected, k=10),
        "citation_precision": citation_precision(cited_labels, expected),
        "quote_verified": _quote_verified(citations, expected_refusal=expected_refusal),
        "expected_refusal": expected_refusal,
        "actual_refusal": actual_refusal,
        "refusal_correct": expected_refusal == actual_refusal,
        "answer_safe": answer_safe,
        "expected_warnings_present": expected_warnings_present,
        "audit_complete": bool(body.get("diagnostics", {}).get("audit", {}).get("record_hash")),
        "latency_ms": latency_ms,
    }


def _answer_excludes_terms(answer: str, forbidden_terms: list[str]) -> bool:
    lowered_answer = answer.lower()
    return all(term.lower() not in lowered_answer for term in forbidden_terms)


def _quote_verified(citations: Any, *, expected_refusal: bool) -> bool:
    if expected_refusal and not citations:
        return True
    if not isinstance(citations, list) or not citations:
        return False
    return all(
        citation.get("verification_status") == "verified" and citation.get("quoted_text")
        for citation in citations
        if isinstance(citation, dict)
    )


def _summary(cases: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "case_count": float(len(cases)),
        "retrieval_recall_at_3": mean(case["recall_at_3"] for case in cases),
        "retrieval_recall_at_5": mean(case["recall_at_5"] for case in cases),
        "retrieval_recall_at_10": mean(case["recall_at_10"] for case in cases),
        "retrieval_mrr_at_10": mean(case["mrr_at_10"] for case in cases),
        "citation_precision": mean(case["citation_precision"] for case in cases),
        "quote_verification_rate": mean(1.0 if case["quote_verified"] else 0.0 for case in cases),
        "refusal_accuracy": mean(1.0 if case["refusal_correct"] else 0.0 for case in cases),
        "answer_safety": mean(1.0 if case["answer_safe"] else 0.0 for case in cases),
        "warning_recall": mean(
            1.0 if case["expected_warnings_present"] else 0.0 for case in cases
        ),
        "audit_completeness": mean(1.0 if case["audit_complete"] else 0.0 for case in cases),
        "avg_latency_ms": mean(float(case["latency_ms"]) for case in cases),
    }


def _write_reports(report: dict[str, Any], reports_dir: Path) -> None:
    json_path = reports_dir / "eval-latest.json"
    markdown_path = reports_dir / "eval-latest.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# RegLens Eval Report",
        "",
        f"Passed: `{report['passed']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value | Threshold | Pass |",
        "| --- | ---: | ---: | :---: |",
    ]
    summary = report["summary"]
    thresholds = report["thresholds"]
    threshold_results = report["threshold_results"]
    for name, threshold in thresholds.items():
        lines.append(
            f"| `{name}` | {summary[name]:.3f} | {threshold:.3f} | "
            f"{'yes' if threshold_results[name] else 'no'} |"
        )
    lines.extend(
        [
            f"| `avg_latency_ms` | {summary['avg_latency_ms']:.1f} | n/a | n/a |",
            "",
            "## Cases",
            "",
            (
                "| ID | Behavior | Confidence | Recall@3 | Citation Precision | "
                "Safe Answer | Expected Warnings | Refusal Correct |"
            ),
            "| --- | --- | --- | ---: | ---: | :---: | :---: | :---: |",
        ]
    )
    for case in report["cases"]:
        recall = case["recall_at_3"]
        recall_text = "n/a" if recall is None else f"{recall:.3f}"
        lines.append(
            f"| `{case['id']}` | {case['behavior']} | {case['confidence']} | "
            f"{recall_text} | {case['citation_precision']:.3f} | "
            f"{'yes' if case['answer_safe'] else 'no'} | "
            f"{'yes' if case['expected_warnings_present'] else 'no'} | "
            f"{'yes' if case['refusal_correct'] else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
