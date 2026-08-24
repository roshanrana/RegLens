from app.retrieval.service import RetrievalService, build_fixture_retrieval_service


def test_fixture_retrieval_service_loads_synthetic_rulebook() -> None:
    service = build_fixture_retrieval_service()

    assert isinstance(service, RetrievalService)
    assert len(service.chunks) == 11
    assert {chunk.corpus_id for chunk in service.chunks} == {"finra-synthetic"}


def test_retrieve_uses_hybrid_rrf_and_returns_cited_evidence() -> None:
    service = build_fixture_retrieval_service()

    result = service.retrieve(
        "What disclosures are required when a retail communication compares fees?",
        top_k=3,
    )

    assert result.query_id.startswith("qry_")
    assert result.diagnostics.returned_evidence == 3
    assert result.diagnostics.dense_count > 0
    assert result.diagnostics.keyword_count > 0
    assert result.diagnostics.retrieval_config["fusion"] == "reciprocal_rank_fusion"
    assert result.evidence[0].citation_label == "FINRA Rule 1010(c)"
    assert "fee comparison" in result.evidence[0].snippet.lower()

    top_candidate = result.candidates[0]
    assert top_candidate.final_rank == 1
    assert top_candidate.dense_rank is not None
    assert top_candidate.keyword_rank is not None
    assert top_candidate.fusion_score > 0


def test_exact_citation_query_is_routed_and_pinned() -> None:
    service = build_fixture_retrieval_service()

    result = service.retrieve(
        "Please summarize FINRA Rule 1030(b).",
        corpus_id="finra-synthetic",
        corpus_version="2026-08-19",
        top_k=3,
    )

    assert result.evidence[0].citation_label == "FINRA Rule 1030(b)"
    assert result.diagnostics.retrieval_config["query_route"] == "exact_citation"
    assert result.diagnostics.retrieval_config["exact_citation_matches"] == 1
    assert result.diagnostics.retrieval_config["exact_citation_pinned"] == 1


def test_conceptual_query_route_does_not_pin_exact_citation_matches() -> None:
    service = build_fixture_retrieval_service()

    result = service.retrieve("How long must records be retained?", top_k=3)

    assert result.evidence[0].citation_label == "FINRA Rule 1030(b)"
    assert result.diagnostics.retrieval_config["query_route"] == "conceptual"
    assert result.diagnostics.retrieval_config["exact_citation_matches"] == 0


def test_retrieve_respects_evidence_token_budget() -> None:
    service = build_fixture_retrieval_service(default_top_k=4, max_evidence_tokens=60)

    result = service.retrieve("How long must records be retained?", top_k=4)

    selected_tokens = sum(candidate.chunk.token_count for candidate in result.candidates)
    assert 0 < len(result.evidence) < 4
    assert selected_tokens <= 60
    assert result.diagnostics.returned_evidence == len(result.evidence)
    assert result.diagnostics.retrieval_config["max_evidence_tokens"] == 60
    assert result.diagnostics.retrieval_config["selected_evidence_tokens"] == selected_tokens
    assert result.diagnostics.retrieval_config["evidence_truncated"] is True


def test_retrieve_applies_corpus_filters_before_scoring() -> None:
    service = build_fixture_retrieval_service()

    result = service.retrieve(
        "How often must supervisory policies be reviewed?",
        corpus_id="missing-corpus",
        top_k=3,
    )

    assert result.evidence == []
    assert result.candidates == []
    assert result.diagnostics.total_candidates == 0
    assert result.diagnostics.filters["corpus_id"] == "missing-corpus"


def test_query_ids_are_deterministic_for_same_query_and_filters() -> None:
    service = build_fixture_retrieval_service()

    first = service.retrieve(
        "How long must records be retained?",
        corpus_id="finra-synthetic",
        corpus_version="2026-08-19",
    )
    second = service.retrieve(
        "How long must records be retained?",
        corpus_id="finra-synthetic",
        corpus_version="2026-08-19",
    )

    assert first.query_id == second.query_id
    assert first.evidence[0].citation_label == "FINRA Rule 1030(b)"


def test_blank_questions_are_rejected() -> None:
    service = build_fixture_retrieval_service()

    try:
        service.retrieve("   ")
    except ValueError as exc:
        assert "question" in str(exc)
    else:
        raise AssertionError("blank question should raise ValueError")
