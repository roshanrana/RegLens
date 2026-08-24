from __future__ import annotations

from app.domain.models import Chunk
from app.retrieval.keyword import BM25KeywordIndex


def test_bm25_keyword_search_prioritizes_exact_citation_queries() -> None:
    chunks = [
        _chunk(
            "chk_1000a",
            "FINRA Rule 1000(a)",
            "Definitions",
            "FINRA Rule 1000(a). Definitions include member and associated person.",
        ),
        _chunk(
            "chk_1000b",
            "FINRA Rule 1000(b)",
            "Applicability",
            "FINRA Rule 1000(b). Applicability standards for members.",
        ),
        _chunk(
            "chk_2210",
            "FINRA Rule 2210(d)(1)(A)",
            "Fair and balanced communications",
            "Retail communications must be fair and balanced.",
        ),
    ]

    results = BM25KeywordIndex(chunks).search("What does Rule 1000(a) say?", top_k=3)

    assert [candidate.chunk.chunk_id for candidate in results][:2] == ["chk_1000a", "chk_1000b"]
    assert results[0].keyword_rank == 1
    assert results[0].keyword_score is not None
    assert results[0].keyword_score > results[1].keyword_score


def test_bm25_keyword_search_finds_regulatory_phrase() -> None:
    chunks = [
        _chunk("chk_defs", "FINRA Rule 1000(a)", "Definitions", "Definitions of members."),
        _chunk(
            "chk_comm",
            "FINRA Rule 2210(d)(1)(A)",
            "Fair and balanced communications",
            "Communications with the public must be fair and balanced.",
        ),
    ]

    results = BM25KeywordIndex(chunks).search("fair and balanced communications", top_k=1)

    assert len(results) == 1
    assert results[0].chunk.chunk_id == "chk_comm"


def test_bm25_keyword_search_applies_scope_filters_before_scoring() -> None:
    chunks = [
        _chunk("chk_v1", "FINRA Rule 1000(a)", "Old definitions", "legacy definition", "v1"),
        _chunk("chk_v2", "FINRA Rule 1000(a)", "New definitions", "current definition", "v2"),
    ]

    results = BM25KeywordIndex(chunks).search(
        "Rule 1000(a)",
        top_k=5,
        corpus_id="finra",
        corpus_version="v2",
    )

    assert [candidate.chunk.chunk_id for candidate in results] == ["chk_v2"]


def test_bm25_keyword_index_supports_exact_citation_lookup() -> None:
    chunks = [
        _chunk("chk_1000a", "FINRA Rule 1000(a)", "Definitions", "Definitions."),
        _chunk("chk_2210", "FINRA Rule 2210(d)(1)(A)", "Communications", "Communications."),
    ]

    matches = BM25KeywordIndex(chunks).find_exact_citation_matches("Rule 2210(d)(1)")

    assert [chunk.chunk_id for chunk in matches] == ["chk_2210"]


def test_bm25_keyword_search_returns_empty_for_empty_query() -> None:
    index = BM25KeywordIndex(
        [_chunk("chk_1000a", "FINRA Rule 1000(a)", "Definitions", "Definitions.")]
    )

    assert index.search("   ") == []


def _chunk(
    chunk_id: str,
    citation_label: str,
    title: str,
    text: str,
    corpus_version: str = "v1",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        section_id=f"sec_{chunk_id}",
        source_id="src_finra",
        corpus_id="finra",
        corpus_version=corpus_version,
        citation_label=citation_label,
        title=title,
        heading_path=[citation_label, title],
        text=text,
        token_count=len(text.split()),
        chunk_index=0,
        section_chunk_count=1,
        source_checksum="checksum",
    )
