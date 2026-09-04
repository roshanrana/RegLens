# RegLens — Overview

**What it is:** a retrieval-augmented question-answering system for regulatory text, built on the premise that in compliance work a wrong citation is a liability and an unsupported answer is worse than no answer.

**Read this if** you want the problem and the design reasoning. [SHOWCASE.md](SHOWCASE.md) tours the features; [OPERATIONS.md](OPERATIONS.md) is the reference for running it.

---

## The setting

A compliance officer at a broker-dealer gets a question from the trading floor: *can we do this?* The answer lives in a rulebook, a set of regulatory notices, an internal policy and, often, an interpretive letter from a decade ago. Finding it is slow. Getting it wrong is expensive. Every answer the officer gives will be relied upon, and some of them will be examined later by someone whose job is to ask what the officer knew and when.

Retrieval-augmented generation looks like the obvious tool, and in its naive form it is the wrong one. A general-purpose RAG pipeline will retrieve roughly the right passage, paraphrase it fluently, and cite something. The paraphrase may drift from the rule text. The citation may point at the wrong rule, or at nothing. If the evidence is thin the model will answer anyway, because that is what it was trained to do. And when the officer is asked six months later why she gave the answer she gave, there is no record of what the system read.

RegLens is built against each of those failure modes specifically.

## The design

**Citations are structural, not decorative.** Ingestion preserves rule labels and heading paths through chunking, so every chunk knows which rule it belongs to. Questions are routed: a conceptual question retrieves broadly; a question that mentions a rule number pins that rule's chunks before anything else is considered. `test_exact_citation_query_is_routed_and_pinned` and `test_conceptual_query_route_does_not_pin_exact_citation_matches` cover both directions.

**Retrieval is hybrid, and the diagnostics are exposed.** BM25 keyword scoring and dense embeddings are fused by Reciprocal Rank Fusion, with optional cross-encoder reranking on top. Every response carries the dense, keyword and fusion scores for each piece of evidence, and the trim decisions made to fit the evidence budget. A reviewer can see why a passage was chosen.

**Generation is verified in code, after the fact.** The prompt gives the model prompt-local evidence markers (`[E1]`, `[E2]`, …) and requires it to cite them. After generation, `citations.py` checks that every cited marker resolves to a retrieved chunk, and `quote_verifier.py` checks that every quoted span actually appears in that chunk's text. A fabricated evidence id, a citation to a chunk that was not retrieved, or a quote that is not in the source each cause rejection: `test_verify_answer_citations_rejects_fabricated_evidence_id`, `…rejects_non_retrieved_chunk_citation`, `…rejects_quote_absent_from_evidence`.

**Weak evidence produces a refusal, and a refusal is allowed to have no citations; nothing else is.** `test_non_refusal_answer_without_citations_is_rejected` and `test_refusal_answer_without_citations_is_allowed` are the two halves of that rule.

**Instructions found inside source documents are treated as data.** The eval fixture includes an adversarial rulebook whose text tries to override the system, suppress citations, leak the prompt, and inject a clause into an otherwise factual sentence. The system filters the instruction clause without dropping the fact in the same sentence, and abstains when nothing but instruction text remains: `test_fake_llm_filters_instruction_clause_without_dropping_same_sentence_fact`, `test_fake_llm_abstains_when_only_source_instruction_text_remains`. The eval reports `answer_safety` and `warning_recall` for these cases.

**Every query is an audit record.** Content hash, evidence digest, a hash chain across records, retrieval diagnostics, provider names, and a deterministic cost estimate for live providers. `GET /audit/verify` walks the chain. Chat sessions link to the immutable audit records they created; deleting a session removes the conversation and preserves the audit.

**Live providers fail closed.** Fake mode is the default and rejects live-provider flags outright. Selecting OpenAI embeddings or generation requires the optional extra, an explicit provider name, and a key; setting the key alone enables nothing (`test_openai_api_key_env_does_not_enable_live_providers_by_itself`). When a provider's package, key, quota or model is unavailable, the API returns a structured `dependency_unavailable` error rather than crashing at startup.

## Why fake mode is a feature

The deterministic embeddings, generator and reranker are not stubs. They implement the same interfaces as the live providers and produce stable, inspectable behaviour, which is what makes 268 tests and an evaluation harness runnable in CI with no credentials and no network. The eval measures retrieval, citation precision, quote fidelity, refusal correctness, answer safety, warning recall and audit integrity against a fixture set, and writes a report every run. When a live provider is enabled, the same harness measures it.

## What is measured

| Claim | Evidence |
|---|---|
| Citations resolve and quotes are real | `tests/unit/test_citation_verifier.py`, `test_quote_verifier.py` |
| Exact citations are pinned; conceptual questions are not | `tests/unit/test_retrieval_service.py`, `test_bm25_index.py` |
| RRF is correct and does not double-count | `tests/unit/test_rrf.py` |
| Source instructions cannot override the system | `tests/unit/test_fake_llm.py`, `test_citation_abstention.py`, and the eval's safety cases |
| Audit hashes are deterministic and the chain verifies | `tests/integration/test_query_audit.py`, `test_audit_endpoints.py` |
| Live providers fail closed | `tests/unit/test_provider_factories.py`, `tests/integration/test_provider_startup.py` |
| Auth protects operational routes but not health | `tests/integration/test_auth_rate_limit.py` |
| Ingested corpora survive restart | `tests/integration/test_startup_hydration.py` |
| The UI works end to end | `tests/e2e/test_ui_browser_smoke.py` (opt-in, Playwright) |

## Honest limits

The bundled rulebook is synthetic. Evidence retrieval in fake mode uses deterministic lexical embeddings, which are stable but not semantic; the live path uses real embeddings. OCR for scanned PDFs is documented as a fail-closed contract, not implemented. The cost estimates use character-based token counts so that audits stay reproducible; they are estimates. API-key auth and in-memory rate limiting are local controls, not an identity system.

## Where it sits among the other projects

RegLens is the application-level counterpart to [PROVENANCE](https://github.com/roshanrana/PROVENANCE): PROVENANCE asks whether the inference platform can be trusted; RegLens asks whether a specific answer can be. Its habits (hash-chained audits, deterministic stand-ins bound by default, adversarial fixtures with names, refusal over guessing) are the same ones that run through [HARBORMASTER](https://github.com/roshanrana/Harbormaster) and [LEDGERLENS](https://github.com/roshanrana/LedgerLens).
