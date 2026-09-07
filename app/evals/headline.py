"""Build and validate ``metrics/headline.json`` from observed fake-mode eval runs.

Every number emitted here is observed from a deterministic offline run over the
repo's eval fixtures. Anything that would require live providers, model weight
downloads, or hardware we do not have is reported in the ``facts`` panel with
``status: "pending"`` instead of a fabricated figure.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.costing import estimate_openai_query_cost
from app.domain.models import Chunk
from app.evals.metrics import mean, recall_at_k
from app.ingestion.chunking import Chunker
from app.ingestion.loaders import MarkdownCorpusLoader
from app.retrieval.service import RetrievalService

ACCENTS: frozenset[str] = frozenset({"teal", "blue", "amber", "violet", "red"})
STATUSES: frozenset[str] = frozenset({"ok", "pending", "blocked"})
KPI_ORDER: tuple[str, ...] = (
    "abstention_rate",
    "citation_faithfulness",
    "recall_at_5",
    "cost_per_query",
)
RERANKER_BAR_KS: tuple[int, ...] = (1, 3, 5, 10)
DEFAULT_RETRIEVAL_TOP_K = 10


@dataclass(frozen=True)
class RecallProbe:
    """A labeled retrieval question used for the reranker ON/OFF comparison."""

    question: str
    expected_citations: tuple[str, ...]
    corpus_id: str
    corpus_version: str


@dataclass(frozen=True)
class RerankerComparison:
    """Observed recall@k with the reranker enabled versus disabled."""

    recall_on: dict[int, float]
    recall_off: dict[int, float]
    labeled_cases: int
    total_cases: int
    chunk_count: int
    reranker_model: str


@dataclass(frozen=True)
class CostSummary:
    """Observed fake-run token counts priced with the repo's costing model."""

    query_count: int
    mean_priced_cost_usd: float
    mean_observed_cost_usd: float
    mean_input_tokens: float
    mean_output_tokens: float
    mean_embedding_tokens: float
    generation_model: str
    embedding_model: str


def load_fixture_chunks(fixture_paths: Sequence[Path]) -> list[Chunk]:
    """Chunk the Markdown eval fixtures exactly as the app does at ingest time."""

    chunker = Chunker()
    chunks: list[Chunk] = []
    for path in fixture_paths:
        load_result = MarkdownCorpusLoader().load(path)
        if load_result.errors:
            raise ValueError(f"fixture ingestion failed for {path}: {load_result.errors}")
        chunks.extend(
            chunker.chunk_sections(
                load_result.sections,
                corpus_version=load_result.source.version,
                source_checksum=load_result.source.checksum,
            )
        )
    return chunks


def compare_reranker_recall(
    probes: Sequence[RecallProbe],
    chunks: Sequence[Chunk],
    *,
    ks: Sequence[int] = RERANKER_BAR_KS,
    top_k: int = DEFAULT_RETRIEVAL_TOP_K,
) -> RerankerComparison:
    """Run hybrid retrieval twice, toggling only ``enable_reranking``."""

    if not probes:
        raise ValueError("at least one probe is required")
    enabled_service = RetrievalService(list(chunks), enable_reranking=True, default_top_k=top_k)
    disabled_service = RetrievalService(list(chunks), enable_reranking=False, default_top_k=top_k)
    recall_on = _recall_by_k(enabled_service, probes, ks=ks, top_k=top_k)
    recall_off = _recall_by_k(disabled_service, probes, ks=ks, top_k=top_k)
    labeled_cases = sum(1 for probe in probes if probe.expected_citations)
    return RerankerComparison(
        recall_on=recall_on,
        recall_off=recall_off,
        labeled_cases=labeled_cases,
        total_cases=len(probes),
        chunk_count=len(chunks),
        reranker_model=enabled_service.reranker.model_name,
    )


def price_case(
    *,
    question: str,
    evidence_snippets: Sequence[str],
    answer_text: str,
    generation_model: str,
    embedding_model: str,
) -> dict[str, float | int]:
    """Apply the repo costing model to observed fake-run text at configured OpenAI rates."""

    estimate = estimate_openai_query_cost(
        question=question,
        evidence_snippets=list(evidence_snippets),
        answer_text=answer_text,
        generation_model=generation_model,
        embedding_model=embedding_model,
    )
    return {
        "priced_cost_usd": estimate.estimated_cost_usd,
        "input_tokens": estimate.input_tokens,
        "output_tokens": estimate.output_tokens,
        "embedding_tokens": estimate.embedding_tokens,
    }


def summarize_costs(
    cases: Sequence[Mapping[str, Any]],
    *,
    generation_model: str,
    embedding_model: str,
) -> CostSummary:
    if not cases:
        raise ValueError("at least one case is required")
    return CostSummary(
        query_count=len(cases),
        mean_priced_cost_usd=mean(float(case["priced_cost_usd"]) for case in cases),
        mean_observed_cost_usd=mean(float(case["observed_cost_usd"]) for case in cases),
        mean_input_tokens=mean(float(case["input_tokens"]) for case in cases),
        mean_output_tokens=mean(float(case["output_tokens"]) for case in cases),
        mean_embedding_tokens=mean(float(case["embedding_tokens"]) for case in cases),
        generation_model=generation_model,
        embedding_model=embedding_model,
    )


def build_headline(
    report: Mapping[str, Any],
    comparison: RerankerComparison,
    costs: CostSummary,
    *,
    seed: int,
) -> dict[str, Any]:
    """Assemble the headline document from observed eval outputs."""

    return {
        "kpis": _build_kpis(report, comparison, costs),
        "bars": _build_bars(comparison),
        "facts": _build_facts(report, comparison, costs, seed=seed),
    }


def _build_kpis(
    report: Mapping[str, Any],
    comparison: RerankerComparison,
    costs: CostSummary,
) -> dict[str, Any]:
    cases: Sequence[Mapping[str, Any]] = report["cases"]
    summary: Mapping[str, float] = report["summary"]
    total = len(cases)
    abstained = sum(1 for case in cases if case["actual_refusal"])
    expected_refusals = sum(1 for case in cases if case["expected_refusal"])
    false_abstentions = sum(
        1 for case in cases if case["actual_refusal"] and not case["expected_refusal"]
    )
    labeled = sum(1 for case in cases if case["expected_citations"])
    verified_cases = sum(1 for case in cases if case["quote_verified"])

    kpis = {
        "abstention_rate": {
            "label": "Abstention rate",
            "value": _pct(abstained / total),
            "note": (
                f"{abstained} of {total} fixture queries abstained "
                f"({expected_refusals} out-of-scope expected); "
                f"{false_abstentions} false abstentions; "
                f"refusal accuracy {_pct(summary['refusal_accuracy'])}"
            ),
            "accent": "teal",
        },
        "citation_faithfulness": {
            "label": "Citation faithfulness",
            "value": _pct(summary["quote_verification_rate"]),
            "note": (
                f"{verified_cases}/{total} answers had every quoted citation verified "
                f"against retrieved evidence; citation precision "
                f"{_pct(summary['citation_precision'])}"
            ),
            "accent": "blue",
        },
        "recall_at_5": {
            "label": "Recall@5",
            "value": _pct(summary["retrieval_recall_at_5"]),
            "note": (
                f"n={labeled} labeled of {total} queries over a "
                f"{comparison.chunk_count}-chunk synthetic corpus; "
                f"recall@3 {_pct(summary['retrieval_recall_at_3'])}, "
                f"recall@10 {_pct(summary['retrieval_recall_at_10'])}"
            ),
            "accent": "violet",
        },
        "cost_per_query": {
            "label": "Cost / query",
            "value": _usd(costs.mean_priced_cost_usd),
            "note": (
                f"repo costing model (chars/4 tokens) over observed fake-run text at "
                f"configured {costs.generation_model} + {costs.embedding_model} rates; "
                f"mean of {costs.query_count} queries, ~{costs.mean_input_tokens:.0f} in / "
                f"{costs.mean_output_tokens:.0f} out tokens; live-provider run pending"
            ),
            "accent": "amber",
        },
    }
    assert tuple(kpis) == KPI_ORDER
    return kpis


def _build_bars(comparison: RerankerComparison) -> dict[str, Any]:
    return {
        "title": (
            f"Recall with reranking ON vs OFF ({comparison.reranker_model}, "
            f"n={comparison.labeled_cases})"
        ),
        "rows": [
            row
            for k in RERANKER_BAR_KS
            for row in (
                _bar_row(f"R@{k} reranker ON", comparison.recall_on[k], "teal"),
                _bar_row(f"R@{k} reranker OFF", comparison.recall_off[k], "blue"),
            )
        ],
    }


def _build_facts(
    report: Mapping[str, Any],
    comparison: RerankerComparison,
    costs: CostSummary,
    *,
    seed: int,
) -> dict[str, Any]:
    summary: Mapping[str, float] = report["summary"]
    audit = report["audit_verify"]
    total = len(report["cases"])
    return {
        "title": "Run facts",
        "rows": [
            {
                "label": "Eval fixture",
                "value": (
                    f"{total} queries, {comparison.chunk_count} chunks, 2 corpora, "
                    f"fake LLM + fake embeddings, seed {seed}"
                ),
                "status": "ok",
            },
            {
                "label": "Observed fake-run cost",
                "value": _usd(costs.mean_observed_cost_usd) + " (fake providers)",
                "status": "ok",
            },
            {
                "label": "Answer safety / warning recall",
                "value": (
                    f"{_pct(summary['answer_safety'])} / {_pct(summary['warning_recall'])} "
                    f"on 4 adversarial source-instruction cases"
                ),
                "status": "ok",
            },
            {
                "label": "Audit hash chain",
                "value": (
                    f"{audit['record_count']} records, "
                    f"{audit['failure_count']} failures, verified={audit['verified']}"
                ),
                "status": "ok" if audit["verified"] else "blocked",
            },
            {
                "label": "Cross-encoder reranker (ms-marco-MiniLM-L-6-v2)",
                "value": (
                    "not measured: needs sentence-transformers and a model weight "
                    "download; harness is offline"
                ),
                "status": "pending",
            },
            {
                "label": "Live OpenAI cost per query",
                "value": "not measured: requires OPENAI_API_KEY; harness runs fake providers",
                "status": "pending",
            },
        ],
    }


def validate_headline(document: Mapping[str, Any]) -> list[str]:
    """Return schema violations for a headline document (empty when valid)."""

    errors: list[str] = []
    for key in ("kpis", "bars", "facts"):
        if key not in document:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors

    kpis = document["kpis"]
    if not isinstance(kpis, dict) or not kpis:
        errors.append("kpis must be a non-empty object")
    else:
        for key, kpi in kpis.items():
            errors.extend(_validate_kpi(key, kpi))

    errors.extend(_validate_panel(document["bars"], "bars", _validate_bar_row))
    errors.extend(_validate_panel(document["facts"], "facts", _validate_fact_row))
    return errors


def assert_valid_headline(document: Mapping[str, Any]) -> None:
    errors = validate_headline(document)
    if errors:
        raise ValueError("headline.json failed schema validation: " + "; ".join(errors))


def write_headline(document: Mapping[str, Any], path: Path) -> None:
    assert_valid_headline(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _recall_by_k(
    service: RetrievalService,
    probes: Sequence[RecallProbe],
    *,
    ks: Sequence[int],
    top_k: int,
) -> dict[int, float]:
    per_k: dict[int, list[float | None]] = {k: [] for k in ks}
    for probe in probes:
        result = service.retrieve(
            probe.question,
            corpus_id=probe.corpus_id,
            corpus_version=probe.corpus_version,
            top_k=top_k,
        )
        labels = [evidence.citation_label for evidence in result.evidence]
        for k in ks:
            per_k[k].append(recall_at_k(labels, probe.expected_citations, k=k))
    return {k: mean(values) for k, values in per_k.items()}


def _bar_row(label: str, ratio: float, accent: str) -> dict[str, Any]:
    return {
        "label": label,
        "value": round(ratio * 100, 1),
        "max": 100,
        "display": _pct(ratio),
        "accent": accent,
    }


def _pct(ratio: float) -> str:
    return f"{ratio * 100:.1f}%"


def _usd(value: float) -> str:
    return f"${value:.6f}"


def _validate_kpi(key: str, kpi: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(kpi, dict):
        return [f"kpis.{key} must be an object"]
    for field in ("label", "value", "note", "accent"):
        if not isinstance(kpi.get(field), str) or not kpi[field].strip():
            errors.append(f"kpis.{key}.{field} must be a non-empty string")
    if kpi.get("accent") not in ACCENTS:
        errors.append(f"kpis.{key}.accent must be one of {sorted(ACCENTS)}")
    return errors


def _validate_panel(
    panel: Any,
    name: str,
    validate_row: Any,
) -> list[str]:
    if not isinstance(panel, dict):
        return [f"{name} must be an object"]
    errors: list[str] = []
    if not isinstance(panel.get("title"), str) or not panel["title"].strip():
        errors.append(f"{name}.title must be a non-empty string")
    rows = panel.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append(f"{name}.rows must be a non-empty array")
        return errors
    for index, row in enumerate(rows):
        errors.extend(validate_row(f"{name}.rows[{index}]", row))
    return errors


def _validate_bar_row(prefix: str, row: Any) -> list[str]:
    if not isinstance(row, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    for field in ("label", "display"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    value = _as_number(row.get("value"))
    maximum = _as_number(row.get("max"))
    if value is None:
        errors.append(f"{prefix}.value must be a number")
    if maximum is None or maximum <= 0:
        errors.append(f"{prefix}.max must be a positive number")
    if value is not None and maximum is not None and (value < 0 or value > maximum):
        errors.append(f"{prefix}.value must satisfy 0 <= value <= max")
    if row.get("accent") not in ACCENTS:
        errors.append(f"{prefix}.accent must be one of {sorted(ACCENTS)}")
    return errors


def _validate_fact_row(prefix: str, row: Any) -> list[str]:
    if not isinstance(row, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    for field in ("label", "value"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    if row.get("status") not in STATUSES:
        errors.append(f"{prefix}.status must be one of {sorted(STATUSES)}")
    return errors


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
