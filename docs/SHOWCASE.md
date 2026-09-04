# RegLens — Showcase

A guided tour with the commands that show each feature and the files where it lives. [OVERVIEW.md](OVERVIEW.md) has the reasoning; [OPERATIONS.md](OPERATIONS.md) has every option.

## Ten minutes, nothing to install but Python

```bash
python -m venv .venv && source .venv/bin/activate
make install
make verify                                  # lint, typecheck, 268 tests, eval
python -m uvicorn app.main:app --reload      # then open http://127.0.0.1:8000/
```

In the UI: ingest the bundled synthetic rulebook, ask a conceptual question, then ask one that names a rule number, and compare the diagnostics panel for the two. The second one shows the exact-citation route pinning the rule's chunks before fusion. Then export the audit record as Markdown; that is what a reviewer would read.

`make verify` leaves `reports/eval-latest.md` behind. Its safety section is the most interesting part of the repository.

## Feature tour

### 1. Ingestion that keeps citations (`app/ingestion/`)

| Look at | What it shows |
|---|---|
| `loaders.py` | Markdown, text, HTML and optional PDF (with page numbers) loaders; `test_markdown_loader_preserves_citation_labels_and_heading_paths` |
| `chunking.py` | Deterministic chunks that carry their rule label and heading path; deterministic ids so re-ingestion is idempotent |
| `normalizers.py` | Citation-key extraction that recognises rule references and ignores plain numbers: `test_extract_citation_keys_ignores_plain_numbers_without_rule_signal` |
| `app/api/routes_admin.py` | `POST /admin/ingest`, `POST /documents`, `DELETE /documents/{id}`, job status, and allowlisted FINRA URL ingestion that snapshots raw bytes |

### 2. Hybrid retrieval with exposed diagnostics (`app/retrieval/`)

| Look at | What it shows |
|---|---|
| `keyword.py` | Rule-aware BM25 that prioritises exact citation queries |
| `embeddings.py`, `vector_store.py`, `qdrant_store.py` | Fake and Qdrant-backed dense retrieval behind one interface |
| `fusion.py` | Reciprocal Rank Fusion; `test_reciprocal_rank_fusion_does_not_double_count_duplicates_in_one_list` |
| `service.py` | Routing (conceptual / citation reference / exact citation), pinning, evidence budget trimming with diagnostics, optional `source_id` filtering |
| `rerank.py`, `cross_encoder_reranker.py` | Fake reranker by default; a lazily loaded cross-encoder behind explicit configuration |
| `embedding_cache.py` | A bounded cache keyed by provider, model, dimensions and text hash, so live embeddings are not paid for twice |

Ask through `POST /retrieve` to see the fused ranking with every score.

### 3. Grounded generation, verified afterwards (`app/generation/`)

| Look at | What it shows |
|---|---|
| `prompts.py` | Prompt assembly with `[E1]`…`[En]` markers that exist only inside the prompt |
| `llm.py`, `openai_llm.py` | The deterministic generator and the OpenAI Responses client, same interface, strict structured output |
| `citations.py` | Every cited marker must resolve to a retrieved chunk; four rejection tests in `test_citation_verifier.py` |
| `quote_verifier.py` | Every quoted span must appear in its evidence, with case and whitespace normalisation; `test_quote_verifier_rejects_absent_quote` |
| `warnings.py` | The warning catalogue, including source-instruction warnings |
| `service.py` | Abstention when retrieval is weak, and the rule that only refusals may lack citations |

### 4. Adversarial sources (`app/evals/fixtures/adversarial_rulebook.md`)

A rulebook that tries to override the system, suppress citations, leak the prompt, and inject an instruction into a factual sentence. `test_fake_llm_filters_instruction_clause_without_dropping_same_sentence_fact` is the precise behaviour: keep the fact, drop the instruction, warn.

### 5. The evaluation harness (`app/evals/metrics.py`, `make eval`)

Retrieval recall, citation precision (which handles refusals and wrong citations distinctly), quote fidelity, refusal correctness, answer safety, warning recall and audit integrity, from `questions.json` against both rulebooks. `tests/integration/test_eval_runner.py` runs it; `reports/eval-latest.md` is the output.

### 6. Audit (`app/persistence/`, `app/api/routes_audit.py`)

Hash-chained query audits with an evidence digest and a deterministic content hash (`test_content_and_audit_hashes_are_deterministic`). `GET /audit/queries`, `GET /audit/queries/{id}`, `…/export?format=json|markdown`, and `GET /audit/verify` to walk the chain. Chat-created audits carry their session and turn.

### 7. Chat sessions (`app/api/routes_query.py`)

`POST /chat` returns the same grounded payload as `/query`, optionally streamed as Server-Sent Events (metadata, answer deltas, citations, evidence, final payload, done). Sessions persist in SQLite, link to their audit records, and export as JSON or reviewer-friendly Markdown. Deleting a session keeps the audits.

### 8. Fail-closed providers (`app/generation/provider_factory.py`, `app/retrieval/provider_factory.py`)

Fake mode rejects live flags. Live selection requires the extra, an explicit provider name and a key. `test_provider_factories_do_not_import_openai_sdk_when_api_key_is_missing` and `test_openai_api_key_env_does_not_enable_live_providers_by_itself` are the two tests that make the boundary honest. `/ready` reports every provider's name, fake flag and gated errors.

### 9. Hardening (`app/core/security.py`, `costing.py`)

Optional API-key auth (`X-RegLens-API-Key` or bearer) and per-minute rate limiting on operational routes with health, readiness, docs and UI exempt: `test_api_key_auth_protects_operational_routes_but_not_health`. Deterministic cost estimates for the cost-capped live models, stored on the audit row.

### 10. The analyst UI (`app/api/routes_ui.py`)

Dependency-free HTML served from `/`: query, citations, evidence, diagnostics, provenance, audit export, source lifecycle, chat sessions and transcripts. `tests/e2e/test_ui_browser_smoke.py` ingests, asks, verifies citations, deletes a source and confirms it no longer retrieves.

## Things worth noticing

- **Verification is code, not prompt.** The model is asked to cite; the system checks. Those are different guarantees.
- **The safety fixture is part of the gate.** Prompt injection through source documents is measured on every `make verify`, in CI, offline.
- **Fake mode is a full implementation.** That is why the whole system, UI included, runs and tests without a key.
- **Deleting a conversation does not delete the record.** Audit is immutable by design; chat history is not.

## Questions this project answers, and where

| Question | Where the answer lives |
|---|---|
| How do you stop a RAG system inventing citations? | `generation/citations.py`: markers only exist in the prompt and must resolve to retrieved chunks |
| How do you know the quote is real? | `generation/quote_verifier.py`, span search against the evidence text |
| What happens when the evidence is thin? | `generation/service.py`: abstention, and only refusals may lack citations |
| What if a source document contains instructions? | `evals/fixtures/adversarial_rulebook.md` and the `answer_safety` metric |
| How would a reviewer reconstruct an answer a year later? | `GET /audit/queries/{id}/export?format=markdown` and `GET /audit/verify` |
| How do you keep a key in the environment from silently enabling a live model? | `test_openai_api_key_env_does_not_enable_live_providers_by_itself` |
| How much does a live answer cost? | `core/costing.py`, on every audit row |
