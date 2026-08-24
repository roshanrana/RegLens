from app.generation.quote_verifier import QuoteVerifier, equivalent_text, find_quote_span


def test_find_quote_span_normalizes_case_and_whitespace() -> None:
    text = "Firms must maintain\nrecords for six years after creation."

    match = find_quote_span(text, "maintain records for SIX years")

    assert match is not None
    assert match.source_span == {"start": 11, "end": 41}
    assert match.matched_text == "maintain\nrecords for six years"


def test_quote_verifier_rejects_absent_quote() -> None:
    result = QuoteVerifier().verify(
        "written supervisory procedures",
        {"snippet": "Firms must retain records for six years."},
    )

    assert not result.verified
    assert result.reason == "quote_not_found"


def test_quote_verifier_accepts_correct_source_span() -> None:
    text = "Communications must be fair and balanced."
    result = QuoteVerifier().verify(
        "fair and balanced",
        {"snippet": text},
        source_span={"start": 23, "end": 40},
    )

    assert result.verified
    assert result.match is not None
    assert result.match.matched_text == "fair and balanced"


def test_quote_verifier_rejects_source_span_mismatch() -> None:
    text = "Communications must be fair and balanced."
    result = QuoteVerifier().verify(
        "fair and balanced",
        {"snippet": text},
        source_span={"start": 0, "end": 14},
    )

    assert not result.verified
    assert result.reason == "source_span_mismatch"


def test_equivalent_text_is_whitespace_and_case_insensitive_only() -> None:
    assert equivalent_text("Fair\nand Balanced", "fair and balanced")
    assert not equivalent_text("fair, and balanced", "fair and balanced")
