from __future__ import annotations

from app.retrieval.keyword import KeywordTokenizer, extract_citation_keys


def test_keyword_tokenizer_preserves_rule_ids_and_paragraph_markers() -> None:
    tokens = KeywordTokenizer().tokenize(
        "FINRA Rule 1000(a)(1) and paragraph (b)(2) require AML controls."
    )

    assert "FINRA" in tokens
    assert "finra" in tokens
    assert "1000(a)(1)" in tokens
    assert "1000(a)" in tokens
    assert "1000" in tokens
    assert "(a)" in tokens
    assert "(b)(2)" in tokens
    assert "(b)" in tokens
    assert "(2)" in tokens
    assert "AML" in tokens
    assert "aml" in tokens
    assert "controls" in tokens


def test_extract_citation_keys_normalizes_authority_rule_and_prefixes() -> None:
    keys = extract_citation_keys("FINRA Rule 2210(d)(1)(A)")

    assert "finrarule2210(d)(1)(a)" in keys
    assert "rule2210(d)(1)(a)" in keys
    assert "2210(d)(1)(a)" in keys
    assert "2210(d)(1)" in keys
    assert "2210(d)" in keys


def test_extract_citation_keys_ignores_plain_numbers_without_rule_signal() -> None:
    assert extract_citation_keys("The requirement applies within 30 days of notice.") == set()
