# RegLens Agent Orchestration Notes

Last updated: 2026-08-24

Purpose: compact current-state notes for coordinating future AI agents without
drifting from the product goal.

## Active Product Goal

Build RegLens into a complete, tested regulatory/compliance RAG product across:

- fake mode: deterministic, no network, complete local demo
- local mode: local services such as Qdrant and optional local models
- real-provider mode: OpenAI-backed embeddings/generation and production-style integrations

The product promise is auditable regulatory answers: every answer should be
grounded in retrieved evidence with citations, quote verification, diagnostics,
portable exports, and tamper-evident audit records.

## Current Verified Capabilities

- FastAPI app with `/health`, `/ready`, `/docs`, and UI at `/`.
- Mock-mode settings and dependency-free fake providers.
- Explicit provider-name settings and factory wiring for embeddings, generation, and reranking.
- OpenAI embeddings/generation providers are implemented behind explicit provider settings, API-key validation, and the optional `openai` extra.
- OpenAI live-smoke defaults are cost-capped: `text-embedding-3-small`, `gpt-5.4-nano`, and `REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS=400`.
- Missing OpenAI keys fail closed before importing the SDK; missing SDK and request failures return structured `dependency_unavailable` diagnostics without leaking secrets.
- Live OpenAI smoke tests are isolated under the `live_openai` marker and the `scripts.verify openai` profile.
- Cross-encoder reranking is implemented behind explicit provider settings and the optional `rerank` extra.
- Cross-encoder defaults keep `trust_remote_code=false`; model-download tests are isolated under `requires_model_download` and `scripts.verify models`.
- `/ready` reports provider names, fake flags, model names, and gated startup errors.
- SQLite persistence for sources, sections, chunks, ingestion jobs, query audits, and evidence rows.
- SQLite connections are protected by a per-connection transaction lock for concurrent local/TestClient requests.
- Markdown, plain-text, basic HTML, and optional PDF ingestion.
- Allowlisted remote HTTPS ingestion is available through `/admin/ingest-url` and `/documents/url`; default allowed hosts are FINRA domains.
- PDF extraction uses lazy `pypdf` loading, one section per nonempty page, page-number metadata, checksum preservation, and structured missing-dependency/scanned-PDF failures.
- PDF extraction splits multiple title-like FINRA/FCA regulatory headings on the same page into separate cited sections while preserving same-page metadata and avoiding mid-sentence rule-reference false positives.
- Scanned/image-only PDFs remain fail-closed with documented OCR strategy in `docs/ocr-strategy.md`; no OCR dependencies are in the base install.
- Citation-preserving chunking with deterministic IDs.
- Source ID isolation when caller overrides conflict with front matter.
- Hybrid retrieval: fake dense embeddings, in-memory or Qdrant vector store, BM25, RRF, fake reranker.
- Local `rag_mode=local` can build a Qdrant-backed retrieval service while still using fake embeddings, fake generation, and fake reranker.
- Local mode degrades cleanly when Qdrant or `qdrant-client` is unavailable.
- Optional `requires_qdrant` smoke covers local mode against a real Qdrant service, passes when Docker Qdrant is running, and skips cleanly when unavailable.
- The optional `qdrant-client` extra is pinned to `>=1.12,<1.14` to match the bundled `qdrant/qdrant:v1.12.1` Docker image.
- Query route diagnostics: `conceptual`, `citation_reference`, and `exact_citation`.
- Exact citation matches are pinned before evidence selection.
- Evidence token budget is enforced before answer generation.
- `source_id` filters are accepted by `/retrieve`, `/query`, and `/chat` and applied before dense, keyword, exact-citation, fusion, rerank, evidence selection, and generation.
- `/retrieve` endpoint with diagnostics.
- `/query` endpoint with provider-neutral generation service acceptance, fake cited generation, quote verification, abstention, and audit persistence.
- `/chat` endpoint with `/query`-compatible JSON plus optional `stream=true` Server-Sent Events for app and agent integrations.
- Durable chat session persistence: `/chat` creates/continues sessions, stores turns, and links every chat turn to the immutable query audit record.
- Chat history endpoints: `GET /chat/sessions`, `GET /chat/sessions/{session_id}`, and `DELETE /chat/sessions/{session_id}`.
- Chat transcript exports: `GET /chat/sessions/{session_id}/export?format=json|markdown`.
- Audit summaries, audit details, and JSON/Markdown audit exports expose originating chat session/turn links for `/chat`-created audits and `chat: null` for `/query`-created audits.
- Prompt assembly treats retrieved evidence as untrusted source text, wraps snippets in delimiters, and instructs the model not to follow instructions inside sources.
- Fake-mode generation filters source-instruction sentences and abstains when only source instructions remain.
- Eval coverage includes adversarial source-instruction cases for instruction override, citation suppression, prompt leak, and same-sentence clause injection with answer-safety and warning-recall metrics.
- Hash-chain audit endpoints: `/audit/queries`, `/audit/queries/{query_id}`, `/audit/queries/{query_id}/export`, `/audit/verify`.
- Query audit rows include evidence digest/count metadata, and `/audit/verify` detects edited or deleted persisted query evidence rows.
- Query audit saves are append-only; duplicate `query_id` writes raise an audit conflict instead of upserting.
- Single-query audit exports are available as portable JSON or Markdown evidence packs.
- Source lifecycle audit events are persisted for terminal ingestion and deletion outcomes and exposed at `/audit/source-events`.
- Query and audit payloads expose structured `warning_details` with severity/message while preserving existing warning code lists.
- Query diagnostics and audit rows include deterministic OpenAI live-provider cost estimates for configured demo prices.
- Local ingestion/admin endpoints: `/admin/ingest`, `/admin/ingest/{job_id}`, `/sources`, `/sources/{source_id}`.
- Document lifecycle endpoints: `POST /documents`, `DELETE /documents/{source_id}`.
- Mock retrieval refreshes immediately after ingestion/deletion.
- Mock startup hydrates persisted chunks from SQLite.
- Minimal dependency-free analyst UI for query, evidence, diagnostics, provenance, audit export, source lifecycle events, source ingestion/deletion, and audit verification.
- Analyst UI now asks through `/chat`, tracks the active chat session, shows recent sessions/turns, and renders session/turn provenance.
- Analyst UI can load the active chat transcript export into the diagnostics panel.
- Optional `requires_browser` Playwright smoke covers the analyst UI flow, passes when Playwright Chromium is installed, and skips cleanly when unavailable.
- Optional Qdrant adapter exists with offline stub tests and local runtime wiring through injected or real Qdrant clients.
- `scripts.verify` provides reproducible verification profiles for agents: `default`, `browser`, `qdrant`, `openai`, `models`, and `full-local`.
- `scripts.verify container` provides optional static Docker/Compose packaging validation.
- OpenAI embeddings support an optional bounded in-memory cache; default enabled for live providers.
- Optional API-key auth and in-memory rate limiting protect operational routes when configured and are disabled by default.
- Default GitHub Actions workflow runs `python -m scripts.verify default` with dev dependencies only; optional browser/Qdrant and live OpenAI paths are not in default CI.
- GitHub Actions also runs a separate `container-verify` job for static packaging and Compose config validation without building images or starting services.
- Mock-safe Dockerfile and opt-in `docker compose --profile app up --build reglens` app service are available without OpenAI billing or secrets.

## Most Recent Work Completed

1. Added allowlisted FINRA URL ingestion with local raw-source snapshots.
2. Added `source_id` filters to retrieval/query/chat.
3. Added OpenAI embedding cache, deterministic query cost estimates, optional API-key auth, and optional rate limiting.
4. Preserved fake/default gates: no OpenAI, billing, Qdrant, model download, or network call is required for default verification.

## Latest Verification Evidence

Commands run with:
`.venv\Scripts\python.exe`

- `python -m ruff check app tests scripts` passed.
- `python -m mypy app` passed.
- `python -m pytest tests\unit\test_config.py tests\unit\test_embedding_cache.py tests\unit\test_costing.py tests\unit\test_openai_embeddings.py tests\unit\test_id_generation.py tests\integration\test_auth_rate_limit.py tests\integration\test_retrieve_endpoint.py tests\integration\test_ingest_endpoints.py tests\integration\test_query_endpoint_fake_llm.py -q` passed: 65 passed.
- Focused hardening lint over touched app/test paths passed.
- `python -m mypy app` passed after the production-hardening slice: 44 source files.
- `python -m pytest tests\unit\test_config.py tests\unit\test_openai_llm.py tests\unit\test_provider_factories.py -q` passed: 27 passed.
- `python -m scripts.verify openai` passed with explicit cost-capped environment overrides: `gpt-5.4-nano`, `text-embedding-3-small`, and `REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS=400`; 2 selected live OpenAI tests passed.
- `gpt-5-nano` was tried as a lower-cost <=5.4 candidate and failed the structured cited-generation smoke with `insufficient_evidence`/`unparseable_openai_response`, including a focused retry with `REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS=1000`.
- `python -m scripts.verify default` passed after the OpenAI cost-cap change: lint, typecheck, 250 selected default tests with no warnings section, and eval.
- `python -m scripts.verify openai` passed after the production-hardening slice: 2 selected live OpenAI tests passed.
- `python -m scripts.verify default` passed after the production-hardening slice: lint, typecheck, 263 selected default tests with no warnings section, and eval.
- `python -m scripts.verify default` passed: lint, typecheck, 248 selected default tests with no warnings section, and eval.
- `python -m pytest tests\unit\test_id_generation.py tests\unit\test_domain_models.py tests\integration\test_repositories.py tests\integration\test_query_endpoint_fake_llm.py -q` passed: 32 passed.
- `python -m pytest tests\integration\test_ui_endpoint.py tests\integration\test_query_endpoint_fake_llm.py -q` passed: 10 passed.
- `python -m pytest tests\integration\test_query_endpoint_fake_llm.py -q` passed: 9 passed.
- `python -m pytest tests\integration\test_provider_startup.py tests\integration\test_query_provider_boundary.py -q` passed: 8 passed.
- `python -m pytest tests\integration\test_repositories.py tests\integration\test_audit_endpoints.py -q` passed: 17 passed.
- `python -m pytest tests\integration\test_query_endpoint_fake_llm.py tests\integration\test_ui_endpoint.py -q` passed: 11 passed.
- `python -m pytest tests\integration\test_ingest_endpoints.py tests\integration\test_query_endpoint_fake_llm.py -q` passed: 24 passed.
- `python -m pytest tests\integration\test_ingest_endpoints.py::test_concurrent_admin_ingests_do_not_clobber_mock_retrieval_state -q` passed 5 consecutive runs.
- `python -m pytest tests\unit\test_container_config.py -q` passed: 3 passed.
- `docker compose config` and `docker compose --profile app config` rendered successfully.
- `python -m pytest tests\unit\test_verify_script.py tests\unit\test_container_config.py -q` passed: 7 passed.
- `python -m scripts.verify container --dry-run` printed the expected static packaging and Compose config commands.
- `python -m scripts.verify container` passed.
- `python -m pytest tests\unit\test_ci_workflow.py tests\unit\test_verify_script.py tests\unit\test_container_config.py -q` passed: 9 passed.
- `docker build -t reglens:local .` passed after Docker Desktop's Linux engine was started.
- Containerized smoke on `http://127.0.0.1:8012` passed for `/ready`, two-turn `/chat`, session detail, audit linkage, and transcript export.
- Post-Docker `python -m scripts.verify default` passed: lint, typecheck, 248 selected default tests with no warnings section, and eval.
- `python -m pytest tests\integration\test_provider_startup.py tests\integration\test_query_endpoint_fake_llm.py tests\integration\test_query_provider_boundary.py -q` passed: 14 passed.
- `python -m ruff check app\api\routes_query.py tests\integration\test_provider_startup.py tests\integration\test_query_endpoint_fake_llm.py` passed.
- Mock server on `http://127.0.0.1:8011` returned `/ready` status `ready` with fake embedding, generation, and reranker providers.
- Live local `/chat` smoke returned a cited answer for `FINRA Rule 1030(b)` with verified quote text.
- Live local `/chat` streaming smoke returned `metadata`, `answer_delta`, `citations`, `evidence`, `final`, and `done` events.
- Latest live local chat-session smoke on `http://127.0.0.1:8011` returned `ready`, appended turn indexes `[0, 1]`, fetched `turn_count = 2`, deleted the chat session, and confirmed the linked audit remained readable.
- Latest UI HTML smoke confirmed RegLens, `/chat` wiring, chat sessions, and chat turns are present.
- Latest live local transcript-export smoke returned `reglens.chat_session.v1`, `turn_count = 2`, and Markdown containing the second query ID.
- `python -m scripts.verify models` selected 1 model-download test and skipped cleanly because `REGLENS_RUN_MODEL_DOWNLOAD_TESTS=true` was not set.
- `python -m pytest tests\unit\test_cross_encoder_reranker.py tests\unit\test_provider_factories.py tests\unit\test_config.py tests\unit\test_dependency_policy.py tests\unit\test_verify_script.py tests\integration\test_provider_startup.py -q` passed: 42 passed.
- `python -m scripts.verify openai` ran 2 selected live tests; both skipped cleanly because the OpenAI account returned `insufficient_quota`.
- `python -m pytest tests\unit\test_openai_embeddings.py tests\unit\test_openai_llm.py tests\unit\test_provider_factories.py -q` passed: 23 passed.
- `python -m pytest tests\unit\test_provider_factories.py tests\unit\test_dependency_policy.py tests\integration\test_provider_startup.py tests\integration\test_query_provider_boundary.py -q` passed: 15 passed.
- `python -m pytest tests\integration\test_health.py tests\integration\test_local_qdrant_runtime.py tests\integration\test_real_qdrant_smoke.py tests\integration\test_query_endpoint_fake_llm.py -q` passed: 9 passed, 1 skipped because `qdrant-client` is not installed.
- `python -m pytest -m requires_browser -q` skipped cleanly because Playwright is not installed in the current `.venv`.
- Previous `python -m scripts.verify browser` evidence is stale for this environment because the current `.venv` lacks Playwright.
- `python -m scripts.verify full-local --dry-run --reports-dir reports` printed the expected default/browser/Qdrant command matrix.
- `python -m scripts.verify qdrant --dry-run` printed the expected Qdrant smoke command.
- `python -m pytest -q` passed: 165 passed, 1 skipped because Qdrant was intentionally stopped.
- `python -m pytest tests/unit/test_pdf_loader.py tests/integration/test_ingest_endpoints.py::test_admin_ingest_pdf_splits_multiple_rules_on_one_page -q` passed: 7 passed.
- `python -m pytest tests/unit/test_verify_script.py -q` passed: 4 passed.
- `python -m pytest tests/unit/test_ci_workflow.py -q` passed: 2 passed.
- `python -m pytest tests/unit/test_ocr_strategy.py -q` passed: 3 passed.
- `python -m pytest tests/unit/test_prompt_assembly.py tests/unit/test_fake_llm.py -q` passed: 13 passed.
- Real generated-PDF split smoke passed: extracted 2 same-page sections, inferred `FINRA Rule 1030(b)` and `FINRA Rule 1045`, preserved page numbers `[1, 1]`.
- `python -m pytest tests/integration/test_query_endpoint_fake_llm.py::test_query_endpoint_filters_adversarial_source_instructions -q` passed.
- `python -m pytest tests/integration/test_eval_runner.py tests/integration/test_query_endpoint_fake_llm.py::test_query_endpoint_filters_adversarial_source_instructions -q` passed: 2 passed.
- `python -m ruff check scripts/run_evals.py tests/integration/test_eval_runner.py tests/integration/test_query_endpoint_fake_llm.py` passed.
- `python -m mypy app scripts` passed.
- `python -m pytest tests/unit/test_id_generation.py tests/integration/test_query_audit.py tests/integration/test_audit_endpoints.py -q` passed: 20 passed.
- `python -m ruff check app/domain/ids.py app/domain/models.py app/persistence/db.py app/persistence/repositories.py app/api/routes_audit.py app/api/routes_query.py tests/unit/test_id_generation.py tests/integration/test_query_audit.py tests/integration/test_audit_endpoints.py` passed.
- `python -m pytest tests/integration/test_ingest_endpoints.py tests/integration/test_document_endpoints.py tests/integration/test_audit_endpoints.py -q` passed: 25 passed.
- `python -m pytest tests/integration/test_eval_runner.py tests/unit/test_fake_llm.py -q` passed: 9 passed.
- `python -m pytest tests/integration/test_ui_endpoint.py -q` passed: 1 passed.
- `python -m pytest -m requires_browser -q` passed: 1 passed, 181 deselected.
- `python -m pytest tests/unit/test_warning_catalog.py tests/integration/test_query_endpoint_fake_llm.py tests/integration/test_audit_endpoints.py tests/integration/test_eval_runner.py -q` passed: 14 passed.
- `python -m scripts.run_evals --reports-dir reports` passed.

Latest eval summary:

- case_count: 21
- retrieval_recall_at_3: 1.0
- retrieval_recall_at_5: 1.0
- retrieval_recall_at_10: 1.0
- retrieval_mrr_at_10: 1.0
- citation_precision: 1.0
- quote_verification_rate: 1.0
- refusal_accuracy: 1.0
- answer_safety: 1.0
- warning_recall: 1.0
- audit_completeness: 1.0

Recent optional PDF smoke:

- A scratch PDF generated with `reportlab` was loaded through `PdfCorpusLoader`.
- Latest result: 2 same-page sections, citations `FINRA Rule 1030(b)` and `FINRA Rule 1045`, page numbers `[1, 1]`.
- Earlier page-per-section smoke also passed with page numbers `[1, 2]`.

Recent optional Qdrant smoke:

- Docker was started, `qdrant/qdrant:v1.12.1` was brought up with Compose, and `python -m pytest -m requires_qdrant -q` passed.
- `qdrant-client 1.19.0` initially produced a compatibility warning against Qdrant 1.12.1. The repo now pins `qdrant-client>=1.12,<1.14`; with `qdrant-client 1.13.3`, the smoke passed without that warning.
- Qdrant was stopped afterward with `docker compose down`.

Previous optional browser smoke:

- `.[browser]` and Playwright Chromium were installed.
- `python -m pytest -m requires_browser -q` passed: 1 passed, 155 deselected.
- Current `.venv` does not have Playwright installed; the latest browser marker run skipped cleanly.

Recent live smoke on `http://127.0.0.1:8010` with
`REGLENS_RAG_MODE=local` and no Qdrant service:

- `/ready` returned `mode = local`, `status = degraded`, and
  `qdrant.status = unavailable`.
- `/retrieve` returned HTTP 503 with `dependency_unavailable`.

Previous live smoke on `http://127.0.0.1:8010` with
`REGLENS_MAX_EVIDENCE_TOKENS=60`:

- `/retrieve` for `Show me FINRA Rule 1030(b).` returned top citation
  `FINRA Rule 1030(b)`.
- diagnostics showed `query_route = exact_citation`,
  `exact_citation_matches = 1`, `selected_evidence_tokens = 53`,
  `evidence_truncated = true`.
- `/query` returned verified citation `FINRA Rule 1030(b)`.

## Important File Landmarks

- API startup and dependency wiring: `app/main.py`
- Query/retrieve endpoints: `app/api/routes_query.py`
- Admin, source, document lifecycle endpoints: `app/api/routes_admin.py`
- UI route: `app/api/routes_ui.py`
- Retrieval orchestration: `app/retrieval/service.py`
- BM25/citation-key logic: `app/retrieval/keyword.py`
- Qdrant adapter: `app/retrieval/qdrant_store.py`
- Fake generation/citations: `app/generation/service.py`, `app/generation/citations.py`
- Ingestion loaders/chunking: `app/ingestion/loaders.py`, `app/ingestion/chunking.py`
- Persistence: `app/persistence/repositories.py`, `app/persistence/db.py`
- Eval runner: `scripts/run_evals.py`
- Canonical plan: `AGENT_IMPLEMENTATION_PLAN.md`
- Historical log: `docs/implementation-log.md`

## Constraints For Future Agents

- Do not require OpenAI, Qdrant, model downloads, or network calls for normal tests.
- Keep fake mode deterministic.
- Do not introduce direct OpenAI calls outside provider classes.
- Before adding OpenAI-backed code or running OpenAI-backed tests, follow the
  OpenAI API key setup skill and ask the explicit reuse/create decision.
- Preserve API contracts unless there is an explicit migration.
- Any new optional service test must skip gracefully when the service is absent.
- Keep audit answers grounded: unsupported or weak evidence should abstain, not bluff.

## Exact Next Steps

### Completed: CI Container Verification Job

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added CI `container-verify` job.
- Updated CI workflow tests.
- Confirmed the job does not run live-provider/browser/Qdrant smokes or Docker builds.

Follow-up:

- If CI minutes are a concern later, keep this as a separate job so it can be disabled without weakening the default Python gate.

### Completed: Container Verification Profile

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added optional `container` verifier profile.
- Added Make targets for container tests/verifier.
- Documented the profile.

Follow-up:

- Use `docker run --rm -p 8000:8000 -v reglens_data:/app/data reglens:local` for a persistent local container demo.

### Completed: Mock-Safe Container Packaging

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added Dockerfile.
- Added `.dockerignore`.
- Added opt-in Compose app profile.
- Added static packaging tests.

Follow-up:

- Optionally add an opt-in CI image build job later if build time and network access are acceptable.

### Completed: SQLite Concurrency And Warning Cleanup

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added per-connection transaction locking.
- Enabled explicit SQLite cross-thread connection use.
- Removed deprecated HTTP 422 constant warnings.
- Re-ran the concurrent-ingest regression repeatedly.

Follow-up:

- Keep an eye on multi-request tests that share one in-process SQLite connection; prefer repository-level transactions for grouped write workflows.

### Completed: Chat Session Transcript Export

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added structured JSON chat transcript exports.
- Added Markdown chat transcript exports.
- Added UI control for active-session transcript loading.

Follow-up:

- Add browser-level UI smoke for creating a chat session and loading transcript export once Playwright Chromium is installed again.

### Completed: Audit-To-Chat Traceability

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added query-audit-to-chat reverse lookup.
- Added chat linkage to audit list/detail/export payloads.
- Added Markdown evidence pack chat lines.
- Kept `/query` audits additive with `chat: null`.

Follow-up:

- Add browser-level UI smoke for session selection and audit export once Playwright Chromium is installed again.

### Completed: Durable Chat Sessions

Status: code-complete and focused-verified. Full default verification should be re-run after any docs/code touch.

Completed:

- Added persisted chat sessions and turns linked to query audits.
- Added session list/detail/delete endpoints.
- Added chat metadata to non-streaming and streaming `/chat`.
- Updated the UI to use `/chat` and display chat history.
- Added tests for ID/domain validation, repository behavior, append flow, unknown sessions, stream persistence, delete behavior, and provider-failure parity.

Follow-up:

- Add browser-level UI smoke for creating and selecting chat sessions when Playwright is installed.
- Add explicit multi-turn context rewriting only if product requirements call for follow-up questions that depend on prior turns.

### Completed: No-Billing Chat Surface

Status: code-complete and offline-verified with focused tests. Full default verification should be re-run after any docs/code touch.

Completed:

- Added `/chat` as a `/query`-compatible endpoint for agent and UI callers.
- Added optional SSE streaming with deterministic event names.
- Added tests for non-streaming payload compatibility, streaming event shape, validation, and provider-failure parity.
- Confirmed this path runs fully in mock mode without OpenAI billing or quota.

Follow-up:

- Use `/chat` as the integration target for a richer frontend/chat client.
- Keep `/query` as the stable audit-first API contract.

### Completed: Optional Cross-Encoder Reranker Activation

Status: code-complete and offline-verified. Full real-model validation is opt-in because it may download model weights.

Completed:

- Added cross-encoder settings/factory wiring and provider implementation.
- Proved default/base and dev dependencies do not include `sentence-transformers`, `transformers`, or `torch`.
- Proved default fake reranker path does not import model packages.
- Proved missing-package, model-load, inference, and malformed-score failures return structured sanitized errors.
- Added optional model-download smoke behind `requires_model_download` and `REGLENS_RUN_MODEL_DOWNLOAD_TESTS=true`.

Follow-up when model downloads are acceptable:

- Install `.venv\Scripts\python.exe -m pip install -e ".[rerank]"`.
- Run `$env:REGLENS_RUN_MODEL_DOWNLOAD_TESTS="true"; .venv\Scripts\python.exe -m scripts.verify models`.
- Run a local-mode `/query` smoke with fake embeddings/generation plus `REGLENS_RERANKER_PROVIDER=cross_encoder` after the model is cached.

### Agent C: Add Optional OCR Prototype

Goal: implement OCR only if the user explicitly chooses an OCR dependency/runtime path.

Write scope:

- optional dependency group
- PDF loader/factory changes behind a disabled-by-default setting
- skip-clean optional OCR tests

Requirements:

- Do not add OCR dependencies to the default install.
- Keep scanned PDFs as structured `corpus_load_error` unless OCR is explicitly enabled.
- Preserve page/citation metadata and mark OCR-derived sections with `extraction_method = "ocr"`.

## Recommended Orchestration Order

1. Add browser-level UI smoke for chat sessions once Playwright Chromium is installed again.
2. Add deterministic multi-turn context rewriting only if follow-up questions need prior-turn references.
3. Run the opt-in cross-encoder model smoke when model downloads are acceptable.
4. Run a Qdrant-backed local smoke with fake or OpenAI providers after optional profiles pass.
5. Re-run the OpenAI live profile only after quota/billing is enabled on the connected OpenAI project.
6. Agent C only after explicit OCR dependency/runtime decision if scanned PDF support becomes important.
7. Keep default verification fake/offline after every slice.

## Current Known Non-Blocking Warnings

- No warnings were emitted by the latest `python -m scripts.verify default` run.
- Docker image build and throwaway container smoke now pass locally.
