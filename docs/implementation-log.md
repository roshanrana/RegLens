# Implementation Log

## 2026-08-24: Production Hardening Slice

Completed:

- Added explicit allowlisted HTTPS remote ingestion via `POST /admin/ingest-url` and `POST /documents/url`.
- Remote ingestion snapshots fetched source bytes under `REGLENS_DOCUMENT_STORAGE_PATH/remote`, preserves source URL/final URL/content type metadata, and uses the same source/chunk/audit persistence path as local ingestion.
- Added `source_id` filtering to `/retrieve`, `/query`, and `/chat`; the filter flows into dense search, BM25, exact-citation matching, query IDs, chat metadata, and diagnostics.
- Added bounded in-memory OpenAI embedding caching keyed by provider/model/dimensions/text hash.
- Added deterministic OpenAI live-provider cost estimates in query diagnostics and `query_audits.estimated_cost_usd`.
- Added optional API-key authentication and in-memory per-minute rate limiting for operational routes, disabled by default.
- Documented FINRA URL ingestion, OpenAI cache/cost controls, and API hardening settings.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_config.py tests\unit\test_embedding_cache.py tests\unit\test_costing.py tests\unit\test_openai_embeddings.py tests\unit\test_id_generation.py tests\integration\test_auth_rate_limit.py tests\integration\test_retrieve_endpoint.py tests\integration\test_ingest_endpoints.py tests\integration\test_query_endpoint_fake_llm.py -q`
- `.venv\Scripts\python.exe -m ruff check app\core app\retrieval app\api tests\unit\test_config.py tests\unit\test_embedding_cache.py tests\unit\test_costing.py tests\unit\test_openai_embeddings.py tests\unit\test_id_generation.py tests\integration\test_auth_rate_limit.py tests\integration\test_retrieve_endpoint.py tests\integration\test_ingest_endpoints.py tests\integration\test_query_endpoint_fake_llm.py`
- `.venv\Scripts\python.exe -m mypy app`
- `$env:REGLENS_OPENAI_GENERATION_MODEL = 'gpt-5.4-nano'; $env:REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS = '400'; $env:REGLENS_OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small'; $env:REGLENS_OPENAI_EMBEDDING_DIMENSIONS = '1536'; .\.venv\Scripts\python.exe -m scripts.verify openai`
- `.venv\Scripts\python.exe -m scripts.verify default`

Latest validation:

- Focused hardening suite passed: 65 tests.
- Focused lint passed.
- Typecheck passed: 44 source files.
- Live OpenAI smoke passed: 2 selected tests using the cost-capped OpenAI settings.
- Full default verifier passed: lint, typecheck, 263 selected default tests with no warnings section, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-24: Cost-Capped OpenAI Smoke Defaults

Completed:

- Switched the RegLens OpenAI generation default from the GPT-5.6 family to `gpt-5.4-nano` to honor the requested "no higher than GPT-5.4" cap while using the lowest-cost tested OpenAI generation model that satisfies RegLens' structured cited-answer smoke.
- Kept `text-embedding-3-small` as the default OpenAI embedding model for the cheapest documented OpenAI embedding path.
- Added `REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS` with a default of `400` and passed it through the OpenAI Responses client for bounded live smoke-test output.
- Updated tests and setup docs so future agents use the same cost-sensitive model selection.
- Official docs checked: OpenAI model catalog/pricing for GPT-5 nano, GPT-5.4 nano comparison, OpenAI embeddings guide for `text-embedding-3-small`, and Responses API output token limits.
- `gpt-5-nano` was tried as the lower-cost literal <=5.4 candidate, but it returned an unparseable/insufficient cited answer in the live structured-generation smoke even with a 1000-token cap. Keep `gpt-5.4-nano` unless the generation prompt/parser contract changes.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_config.py tests\unit\test_openai_llm.py tests\unit\test_provider_factories.py -q`
- `$env:REGLENS_OPENAI_GENERATION_MODEL = 'gpt-5.4-nano'; $env:REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS = '400'; $env:REGLENS_OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small'; $env:REGLENS_OPENAI_EMBEDDING_DIMENSIONS = '1536'; .\.venv\Scripts\python.exe -m scripts.verify openai`
- `.venv\Scripts\python.exe -m scripts.verify default`

Latest validation:

- Focused OpenAI/config suite passed: 27 tests.
- Live OpenAI smoke passed: 2 selected tests using `gpt-5.4-nano` and `text-embedding-3-small`.
- Full default verifier passed: lint, typecheck, 250 selected default tests with no warnings section, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-24: CI Container Verification Job

Completed:

- Added a separate GitHub Actions `container-verify` job that runs `python -m scripts.verify container`.
- Kept Docker build, Docker Compose service startup, browser installs, Qdrant extras, and OpenAI secrets out of CI.
- Updated CI workflow tests to assert both default and container verification profiles are present.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_ci_workflow.py tests\unit\test_verify_script.py tests\unit\test_container_config.py -q`
- `.venv\Scripts\python.exe -m ruff check tests\unit\test_ci_workflow.py tests\unit\test_verify_script.py tests\unit\test_container_config.py scripts\verify.py`
- `.venv\Scripts\python.exe -m scripts.verify container`
- `.venv\Scripts\python.exe -m scripts.verify default`

Latest validation:

- CI/verify/container focused suite passed: 9 tests.
- Focused lint passed.
- Container verifier passed.
- Full default verifier passed: lint, typecheck, 248 selected default tests with no warnings section, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-24: Container Verification Profile

Completed:

- Added `scripts.verify container` profile for static packaging tests and Docker Compose config rendering.
- Added `make test-container` and `make verify-container`.
- Kept container checks out of the default gate and `full-local` profile.
- Documented the optional container verification path in README.
- Confirmed a real `docker build` and containerized smoke once Docker Desktop's Linux engine was available.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_verify_script.py tests\unit\test_container_config.py -q`
- `.venv\Scripts\python.exe -m ruff check scripts\verify.py tests\unit\test_verify_script.py tests\unit\test_container_config.py`
- `.venv\Scripts\python.exe -m scripts.verify container --dry-run`
- `.venv\Scripts\python.exe -m scripts.verify container`
- `docker build -t reglens:local .`
- `docker run --rm -d --name reglens-smoke-20260824130531 -p 8012:8000 reglens:local`
- Containerized HTTP smoke against `http://127.0.0.1:8012`: `/ready`, two-turn `/chat`, session detail, audit linkage, and chat transcript export.
- `.venv\Scripts\python.exe -m scripts.verify default`

Latest validation:

- Verify/container unit suite passed: 7 tests.
- Focused lint passed.
- Container verifier passed: static container tests, default Compose config, and app-profile Compose config.
- Docker image `reglens:local` built successfully.
- Containerized smoke returned `ready`, appended turn indexes `[0, 1]`, fetched `turn_count = 2`, verified audit-to-chat linkage, and exported `reglens.chat_session.v1`.
- Full default verifier passed: lint, typecheck, 248 selected default tests with no warnings section, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-24: Mock-Safe Container Packaging

Completed:

- Added a `Dockerfile` that runs RegLens in mock mode by default with fake embedding, generation, and reranker providers.
- Added `.dockerignore` entries to keep local secrets, virtualenvs, databases, reports, and temp files out of the build context.
- Added an opt-in `reglens` Compose service under the `app` profile with a persistent `/app/data` volume.
- Preserved existing default Compose behavior for Qdrant.
- Added static container-config tests proving the image/Compose defaults do not include OpenAI secrets or live-provider settings.
- Added README Docker run instructions.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_container_config.py -q`
- `.venv\Scripts\python.exe -m ruff check tests\unit\test_container_config.py`
- `docker compose config`
- `docker compose --profile app config`
- `.venv\Scripts\python.exe -m scripts.verify default`

Latest validation:

- Container-config unit suite passed: 3 tests.
- Container-config lint passed.
- Compose default and app-profile configs rendered successfully.
- Full default verifier passed: lint, typecheck, 248 selected default tests with no warnings section, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-24: SQLite Concurrency And Warning Cleanup

Completed:

- Updated SQLite connections to allow shared FastAPI/TestClient thread usage.
- Added a per-connection transaction lock so concurrent repository transactions cannot overlap commits on the same SQLite connection.
- Replaced deprecated Starlette `HTTP_422_UNPROCESSABLE_ENTITY` constants with `HTTP_422_UNPROCESSABLE_CONTENT` while preserving HTTP 422 behavior.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\integration\test_ingest_endpoints.py tests\integration\test_query_endpoint_fake_llm.py -q`
- `.venv\Scripts\python.exe -m ruff check app\persistence\db.py app\core\errors.py app\api\routes_admin.py app\api\routes_query.py tests\integration\test_ingest_endpoints.py tests\integration\test_query_endpoint_fake_llm.py`
- `.venv\Scripts\python.exe -m mypy app`
- Repeated `.venv\Scripts\python.exe -m pytest tests\integration\test_ingest_endpoints.py::test_concurrent_admin_ingests_do_not_clobber_mock_retrieval_state -q` five times.
- `.venv\Scripts\python.exe -m scripts.verify default`

Latest validation:

- Ingest/chat focused suite passed: 24 tests.
- Focused lint and mypy passed.
- Concurrent-ingest regression passed 5 consecutive runs.
- Full default verifier passed: lint, typecheck, 245 selected default tests with no warnings section, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-24: Chat Session Transcript Export

Completed:

- Added `GET /chat/sessions/{session_id}/export?format=json` for structured chat transcripts.
- Added `GET /chat/sessions/{session_id}/export?format=markdown` for reviewer-friendly chat transcripts with query audit paths.
- Added validation coverage for unsupported export formats.
- Added analyst UI control to load the active chat transcript into the diagnostics panel.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\integration\test_query_endpoint_fake_llm.py tests\integration\test_ui_endpoint.py -q`
- `.venv\Scripts\python.exe -m ruff check app\api\routes_query.py app\api\routes_ui.py tests\integration\test_query_endpoint_fake_llm.py tests\integration\test_ui_endpoint.py`
- `.venv\Scripts\python.exe -m mypy app`
- `.venv\Scripts\python.exe -m scripts.verify default`
- Live local mock smoke on `http://127.0.0.1:8011`: two-turn `/chat` session with JSON and Markdown transcript export.

Latest validation:

- Chat/UI focused suite passed: 11 tests.
- Focused lint and mypy passed.
- Full default verifier passed: lint, typecheck, 245 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Live local transcript-export smoke returned `reglens.chat_session.v1`, `turn_count = 2`, and Markdown containing the second query ID.

## 2026-08-24: Audit-To-Chat Traceability

Completed:

- Added repository lookup from query audit ID back to the originating chat session and turn.
- Added additive `chat` linkage to audit summaries and query audit details.
- Added `chat` linkage to JSON audit exports and Markdown evidence packs.
- Preserved `/query` audit behavior by returning `chat: null` when an audit was not created through `/chat`.
- Preserved immutable query audits when chat sessions are deleted.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\integration\test_repositories.py tests\integration\test_audit_endpoints.py -q`
- `.venv\Scripts\python.exe -m ruff check app\api\routes_audit.py app\persistence\repositories.py tests\integration\test_repositories.py tests\integration\test_audit_endpoints.py`
- `.venv\Scripts\python.exe -m mypy app`
- `.venv\Scripts\python.exe -m scripts.verify default`
- Live local mock smoke on `http://127.0.0.1:8011`: `/chat`, `/audit/queries/{query_id}`, and JSON audit export linkage check.

Latest validation:

- Repository/audit endpoint focused suite passed: 17 tests.
- Focused lint and mypy passed.
- Full default verifier passed: lint, typecheck, 244 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Live local audit-linkage smoke confirmed `/chat`, audit detail, and JSON audit export all reported the same `session_id`.

## 2026-08-24: Durable Chat Sessions

Completed:

- Added deterministic `cht_` and `trn_` ID helpers for chat sessions and turns.
- Added `ChatSession` and `ChatTurn` domain models with validation and metadata copying.
- Added SQLite `chat_sessions` and `chat_turns` tables with indexes, cascade-on-session-delete behavior, and query-audit foreign-key linkage.
- Implemented `ChatSessionRepository` for listing sessions, appending turns, reading turn history, and deleting sessions.
- Wired the chat repository into FastAPI startup.
- Updated `/chat` so calls without `session_id` create a session and calls with an existing `session_id` append a turn.
- Added `GET /chat/sessions`, `GET /chat/sessions/{session_id}`, and `DELETE /chat/sessions/{session_id}`.
- Added chat metadata to non-streaming and streaming `/chat` responses.
- Updated the analyst UI to call `/chat`, keep the active session, render recent sessions and turns, and show session/turn provenance.
- Preserved `/query` as the audit-first single-question contract.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_id_generation.py tests\unit\test_domain_models.py tests\integration\test_repositories.py tests\integration\test_query_endpoint_fake_llm.py -q`
- `.venv\Scripts\python.exe -m ruff check app\domain\ids.py app\domain\models.py app\persistence\db.py app\persistence\repositories.py app\main.py app\api\routes_query.py tests\unit\test_id_generation.py tests\unit\test_domain_models.py tests\integration\test_repositories.py tests\integration\test_query_endpoint_fake_llm.py`
- `.venv\Scripts\python.exe -m mypy app`
- `.venv\Scripts\python.exe -m pytest tests\integration\test_ui_endpoint.py tests\integration\test_query_endpoint_fake_llm.py -q`
- `.venv\Scripts\python.exe -m ruff check app\api\routes_ui.py app\api\routes_query.py tests\integration\test_ui_endpoint.py tests\integration\test_query_endpoint_fake_llm.py`
- `.venv\Scripts\python.exe -m pytest tests\integration\test_provider_startup.py tests\integration\test_query_provider_boundary.py -q`
- `.venv\Scripts\python.exe -m scripts.verify default`
- Live local mock smoke on `http://127.0.0.1:8011`: `/ready`, two-turn `/chat` session, session detail, session delete, and audit-preservation check.
- Live local UI HTML smoke on `http://127.0.0.1:8011/`.

Latest validation:

- Chat/domain/repository focused suite passed: 32 tests.
- UI/chat endpoint focused suite passed: 10 tests.
- Chat endpoint suite with streaming persistence passed: 9 tests.
- Provider boundary suite passed: 8 tests.
- Focused lint and mypy passed.
- Full default verifier passed: lint, typecheck, 243 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Live local smoke returned `ready`, appended turn indexes `[0, 1]`, fetched `turn_count = 2`, deleted the chat session, and confirmed the linked audit remained readable.
- UI HTML smoke confirmed RegLens, `/chat` wiring, chat sessions, and chat turns are present.

## 2026-08-24: No-Billing Chat Surface

Completed:

- Kept live OpenAI as an optional provider path and confirmed the default build does not require billing or quota.
- Added `POST /chat` as an app/agent-friendly alias over the grounded `/query` workflow.
- Added non-streaming `/chat` support that returns the same cited JSON payload, diagnostics, audit hash, and evidence digest metadata as `/query`.
- Added `stream=true` support with Server-Sent Events for `metadata`, `answer_delta`, `citations`, `evidence`, `final`, and `done`.
- Reused the same query dependency guardrails so `/chat` reports structured `dependency_unavailable` errors when optional providers are misconfigured.
- Added integration coverage for non-streaming chat, streaming event shape, empty-question validation, and provider-startup failure parity with `/query`.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\integration\test_provider_startup.py tests\integration\test_query_endpoint_fake_llm.py tests\integration\test_query_provider_boundary.py -q`
- `.venv\Scripts\python.exe -m ruff check app\api\routes_query.py tests\integration\test_provider_startup.py tests\integration\test_query_endpoint_fake_llm.py`
- `.venv\Scripts\python.exe -m scripts.verify default`
- `Invoke-RestMethod -Uri 'http://127.0.0.1:8011/ready' -Method Get`
- `Invoke-RestMethod -Uri 'http://127.0.0.1:8011/chat' -Method Post -ContentType 'application/json' -Body $body`
- `Invoke-WebRequest -Uri 'http://127.0.0.1:8011/chat' -Method Post -ContentType 'application/json' -Body $streamBody`

Latest validation:

- Focused chat/provider suite passed: 14 tests.
- Focused route/test lint passed.
- Full default verifier passed: lint, typecheck, 235 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Mock server on port 8011 returned `/ready` status `ready` with fake embedding, generation, and reranker providers.
- Live local `/chat` smoke returned a cited answer for `FINRA Rule 1030(b)` with verified quote text.
- Live local `/chat` streaming smoke returned `metadata`, `answer_delta`, `citations`, `evidence`, `final`, and `done` events.

## 2026-08-24: Optional Cross-Encoder Reranker Activation

Completed:

- Added optional `rerank` dependency extra for `sentence-transformers` while keeping base/dev installs free of model-download packages.
- Added cross-encoder settings for model name, batch size, max length, device, cache folder, local-files-only mode, and `trust_remote_code`.
- Implemented `CrossEncoderReranker` behind the existing `Reranker` protocol with lazy package/model loading.
- Passed citation label, title, heading path, and chunk text into the cross-encoder passage string.
- Added stable rerank ordering, top-k handling, score count/type validation, and serializable diagnostics.
- Added sanitized model-load and inference failure diagnostics.
- Updated the provider factory so explicit `cross_encoder` selection builds the real reranker when the optional dependency/runtime is available.
- Added `scripts.verify models`, `make test-models`, and `make verify-models` for explicit model-download smokes.
- Added optional `requires_model_download` smoke that stays skipped unless `REGLENS_RUN_MODEL_DOWNLOAD_TESTS=true`.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_cross_encoder_reranker.py tests\unit\test_provider_factories.py tests\unit\test_config.py tests\unit\test_dependency_policy.py tests\unit\test_verify_script.py tests\integration\test_provider_startup.py -q`
- `.venv\Scripts\python.exe -m scripts.verify default`
- `.venv\Scripts\python.exe -m scripts.verify models`

Latest validation:

- Cross-encoder focused suite passed: 42 tests.
- Full default verifier passed: lint, typecheck, 232 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Optional model-download profile selected one test and skipped cleanly because `REGLENS_RUN_MODEL_DOWNLOAD_TESTS=true` was not set.

## 2026-08-24: OpenAI Provider Activation

Completed:

- Added optional `openai` dependency extra while keeping base/dev installs OpenAI-free.
- Added `.env.local` loading through `get_settings()` without overriding existing environment variables.
- Added configurable OpenAI embedding and generation settings.
- Implemented `OpenAIEmbeddingProvider` with batch order/dimension validation and sanitized request failure diagnostics.
- Implemented `OpenAIResponsesLLMClient` with strict structured output parsing and cited-claim mapping.
- Updated provider factories so OpenAI providers instantiate only when provider names and `OPENAI_API_KEY` are explicit.
- Kept missing-key paths fail-closed before importing the OpenAI SDK.
- Added explicit `scripts.verify openai` profile for live OpenAI smoke tests.
- Added unit, startup, dependency-policy, and live-marker tests covering optional dependency gates, no-secret diagnostics, SDK-missing paths, and live-provider behavior.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_openai_embeddings.py tests\unit\test_openai_llm.py tests\unit\test_provider_factories.py -q`
- `.venv\Scripts\python.exe -m scripts.verify default`
- `.venv\Scripts\python.exe -m pip install -e ".[openai]"`
- `.venv\Scripts\python.exe -m scripts.verify openai`

Latest validation:

- Full default verifier passed: lint, typecheck, 218 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Live OpenAI profile ran two selected live tests; both skipped cleanly because the connected OpenAI account returned `insufficient_quota`.
- Earlier live run exposed an invalid structured-output dictionary schema; RegLens now uses a strict list-of-claims schema compatible with the Responses structured-output path.

## 2026-08-24: Provider Factory Readiness Scaffold

Completed:

- Added provider-name settings for embedding, LLM, and reranker providers while preserving fake defaults.
- Added fail-closed provider factories for OpenAI embeddings, OpenAI generation, and cross-encoder reranking.
- Wired provider factories into FastAPI startup for mock, local, and real-mode readiness paths.
- Added provider-neutral embedding and generation service boundaries so future real providers do not need to subclass fake implementations.
- Updated `/ready` to report provider names, fake flags, model names, and gated startup errors.
- Propagated provider startup failures through `/retrieve` and `/query` as structured `dependency_unavailable` responses.
- Added dependency-policy tests proving the default/base and dev installs do not include the OpenAI SDK.
- Added startup tests proving OpenAI provider selections fail closed without importing OpenAI or requiring credentials.
- Added cross-encoder import guards for `sentence_transformers`, `transformers`, and `torch`.
- Added readiness/error tests proving placeholder OpenAI API keys are not leaked in provider failure payloads.
- Added aggregate `/query` dependency diagnostics so multiple gated startup failures are returned in one structured payload.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit\test_provider_factories.py tests\unit\test_dependency_policy.py tests\integration\test_provider_startup.py tests\integration\test_query_provider_boundary.py -q`
- `.venv\Scripts\python.exe -m pytest tests\integration\test_health.py tests\integration\test_local_qdrant_runtime.py tests\integration\test_real_qdrant_smoke.py tests\integration\test_query_endpoint_fake_llm.py -q`
- `.venv\Scripts\python.exe -m ruff check app tests scripts`
- `.venv\Scripts\python.exe -m mypy app`
- `.venv\Scripts\python.exe -m scripts.verify default`
- `.venv\Scripts\python.exe -m pytest -m requires_browser -q`

Latest validation:

- Provider-focused suite: 15 passed.
- Readiness/local-Qdrant focused suite: 9 passed, 1 skipped because `qdrant-client` is not installed.
- Full default verifier passed: lint, typecheck, 199 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.
- Browser smoke skipped cleanly because Playwright is not installed in the current `.venv`.

## 2026-08-20: Structured Warning Severity

Completed:

- Added `app/generation/warnings.py` as a warning taxonomy with severity and messages.
- Added structured `warning_details` to `/query` responses while preserving the existing `warnings` string list.
- Added structured warning details to audit summaries, audit detail, and query audit export payloads.
- Updated the UI to render warning severity as high/medium/info visual states.
- Added tests for known and uncataloged warning codes plus adversarial query/audit warning details.

Verification:

- `python -m pytest tests/unit/test_warning_catalog.py tests/integration/test_query_endpoint_fake_llm.py::test_query_endpoint_filters_adversarial_source_instructions -q`
- `python -m ruff check app/generation/warnings.py app/api/routes_query.py app/api/routes_audit.py app/api/routes_ui.py tests/unit/test_warning_catalog.py tests/integration/test_query_endpoint_fake_llm.py tests/integration/test_ui_endpoint.py`
- `python -m mypy app`
- `python -m pytest tests/unit/test_warning_catalog.py tests/integration/test_query_endpoint_fake_llm.py tests/integration/test_audit_endpoints.py tests/integration/test_eval_runner.py -q`
- `python -m scripts.verify default`

Latest validation:

- Warning catalog/adversarial query focused tests: 3 passed.
- Warning/query/audit/eval focused suite: 14 passed.
- `scripts.verify default` passed: lint, typecheck, 182 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-20: UI Audit And Provenance Workstation

Completed:

- Added a compact provenance panel to the analyst UI showing query ID, audit record hash, evidence digest, prompt version, and generation model.
- Added UI export controls that load JSON or Markdown audit exports for the latest query into the diagnostics panel.
- Added a source lifecycle panel fed by `/audit/source-events`.
- Kept the UI dependency-free and compatible with the existing browser smoke.

Verification:

- `python -m pytest tests/integration/test_ui_endpoint.py -q`
- `python -m ruff check app/api/routes_ui.py tests/integration/test_ui_endpoint.py`
- `python -m pytest -m requires_browser -q`
- `python -m scripts.verify default`

Latest validation:

- UI endpoint test: 1 passed.
- Optional browser smoke: 1 passed, 181 deselected.
- `scripts.verify default` passed: lint, typecheck, 180 selected default tests, and eval.

## 2026-08-20: Expanded Adversarial Eval Variants

Completed:

- Added adversarial eval sections for citation suppression, prompt leak, and same-sentence source-instruction injection.
- Added eval questions and expected warnings/forbidden terms for the new adversarial sections.
- Added a fake-LLM unit test for preserving a same-sentence regulatory fact while filtering the injected instruction clause.
- Updated fake-mode source-instruction filtering to split semicolon-delimited clauses and keep quote text verifiable against the original source.
- Preserved exact quote verification at 1.0 after expanding the adversarial suite.

Verification:

- `python -m pytest tests/unit/test_fake_llm.py -q`
- `python -m scripts.run_evals --reports-dir reports`
- `python -m pytest tests/integration/test_eval_runner.py tests/unit/test_fake_llm.py -q`
- `python -m ruff check app/generation/llm.py tests/unit/test_fake_llm.py tests/integration/test_eval_runner.py`
- `python -m mypy app`
- `python -m scripts.verify default`

Latest validation:

- Fake LLM suite: 8 passed.
- Eval runner/fake LLM focused suite: 9 passed.
- `scripts.verify default` passed: lint, typecheck, 180 selected default tests, and eval.
- Eval summary: 21 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-20: Source Lifecycle Audit Events

Completed:

- Added `SourceAuditEvent` domain records and SQLite persistence under `source_audit_events`.
- Wired `SourceAuditEventRepository` into FastAPI app startup.
- Added `GET /audit/source-events` with limit, source ID, and action filters.
- Emitted `ingest/completed` events after successful admin/document ingestion.
- Emitted `ingest/failed` events for terminal ingestion failures that reach the job lifecycle.
- Emitted `delete/completed` events for source deletion and `delete/failed` events for missing-source deletes.
- Captured request ID, source ID, source checksum, corpus/version, job ID, action, status, actor placeholder, and operation details.

Verification:

- `python -m pytest tests/integration/test_ingest_endpoints.py::test_admin_ingest_markdown_fixture_persists_job_source_sections_and_chunks tests/integration/test_document_endpoints.py::test_delete_document_removes_source_and_refreshes_mock_retrieval -q`
- `python -m pytest tests/integration/test_document_endpoints.py -q`
- `python -m ruff check app/domain/models.py app/persistence/db.py app/persistence/repositories.py app/main.py app/api/routes_audit.py app/api/routes_admin.py tests/integration/test_ingest_endpoints.py tests/integration/test_document_endpoints.py`
- `python -m mypy app`
- `python -m pytest tests/integration/test_ingest_endpoints.py tests/integration/test_document_endpoints.py tests/integration/test_audit_endpoints.py -q`
- `python -m scripts.verify default`

Latest validation:

- Focused lifecycle tests: 2 passed.
- Document lifecycle suite: 3 passed.
- Ingest/document/audit integration suite: 25 passed.
- `scripts.verify default` passed: lint, typecheck, 179 selected default tests, and eval.

## 2026-08-20: Append-Only Query Audit Guard

Completed:

- Added `AuditConflictError` for duplicate query audit writes.
- Made `QueryAuditRepository.save` reject existing `query_id` values before modifying audit or evidence rows.
- Mapped impossible duplicate query writes from `/query` to a sanitized `audit_conflict` HTTP 409.
- Added a repository test proving duplicate saves do not overwrite the original audit, evidence rows, record count, or verification state.

Verification:

- `python -m pytest tests/integration/test_repositories.py -q`
- `python -m pytest tests/integration/test_query_audit.py tests/integration/test_audit_endpoints.py tests/integration/test_query_endpoint_fake_llm.py -q`
- `python -m ruff check app/persistence/repositories.py app/api/routes_query.py tests/integration/test_repositories.py`
- `python -m mypy app`

Latest validation:

- Repository suite: 6 passed.
- Query/audit endpoint focused suite: 16 passed.
- `scripts.verify default` passed: lint, typecheck, 179 selected default tests, and eval.

## 2026-08-20: Audit Export And Evidence Integrity

Completed:

- Added `GET /audit/queries/{query_id}/export` with JSON and Markdown export formats for a portable single-query evidence pack.
- Added per-query evidence digests and evidence counts to audit records before computing payload and record hashes.
- Added SQLite schema migration guards for the new audit integrity columns.
- Extended `/audit/verify` to report detailed chain/evidence failures instead of only a boolean.
- Made `/audit/verify` detect edited query evidence snippets and deleted query evidence rows.
- Exposed evidence digest/count metadata in query diagnostics and audit detail/export payloads.

Verification:

- `python -m pytest tests/unit/test_id_generation.py tests/integration/test_query_audit.py tests/integration/test_audit_endpoints.py -q`
- `python -m ruff check app/domain/ids.py app/domain/models.py app/persistence/db.py app/persistence/repositories.py app/api/routes_audit.py app/api/routes_query.py tests/unit/test_id_generation.py tests/integration/test_query_audit.py tests/integration/test_audit_endpoints.py`
- `python -m mypy app`
- `python -m scripts.verify default`

Latest validation:

- Focused audit integrity/export suite: 20 passed.
- `scripts.verify default` passed: lint, typecheck, 178 selected default tests, and eval.
- Eval summary: 18 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-20: Adversarial Source-Instruction Eval Coverage

Completed:

- Added an end-to-end `/query` integration test that ingests adversarial regulatory text, asks against that corpus, and verifies the answer keeps the valid rule content while excluding injected instructions.
- Persisted source-instruction warnings through query responses and audit reads.
- Added `app/evals/fixtures/adversarial_rulebook.md` with a FINRA-style adversarial retention rule.
- Extended eval questions with per-case corpus/source ingestion, forbidden answer terms, and expected warnings.
- Added eval summary metrics for `answer_safety` and `warning_recall`.
- Updated eval reports to expose safe-answer and expected-warning outcomes per case.

Verification:

- `python -m pytest tests/integration/test_query_endpoint_fake_llm.py::test_query_endpoint_filters_adversarial_source_instructions -q`
- `python -m pytest tests/integration/test_eval_runner.py tests/integration/test_query_endpoint_fake_llm.py::test_query_endpoint_filters_adversarial_source_instructions -q`
- `python -m ruff check scripts/run_evals.py tests/integration/test_eval_runner.py tests/integration/test_query_endpoint_fake_llm.py`
- `python -m mypy app scripts`
- `python -m scripts.run_evals --reports-dir reports`
- `python -m scripts.verify default`

Latest validation:

- Focused adversarial `/query` test passed.
- Focused eval runner/adversarial endpoint suite: 2 passed.
- `scripts.verify default` passed: lint, typecheck, 171 selected default tests, and eval.
- Eval summary: 18 cases, retrieval/citation/quote/refusal/audit metrics at 1.0, `answer_safety = 1.0`, and `warning_recall = 1.0`.

## 2026-08-20: Prompt Injection And Source-Trust Hardening

Completed:

- Updated the RegLens system prompt to state that retrieved evidence is untrusted source text, not instructions.
- Wrapped prompt snippets in explicit `<snippet>` delimiters.
- Added answer requirements telling the model not to obey source text that asks it to ignore, alter, or reveal instructions.
- Added deterministic fake-mode filtering for source-instruction sentences such as "ignore previous instructions", "do not cite", or prompt-reveal requests.
- Made fake-mode generation abstain when only source-instruction text remains after filtering.
- Added tests for prompt wording/delimiters, adversarial evidence filtering, and fail-closed all-instruction snippets.

Verification:

- `python -m pytest tests/unit/test_prompt_assembly.py tests/unit/test_fake_llm.py -q`
- `python -m ruff check app/generation/llm.py app/generation/prompts.py tests/unit/test_prompt_assembly.py tests/unit/test_fake_llm.py`
- `python -m mypy app`
- `python -m scripts.verify default`

Latest validation:

- Focused source-trust tests: 13 passed.
- `scripts.verify default` passed: lint, typecheck, 170 selected default tests, and eval.
- Eval metrics remained at 1.0 for retrieval, citations, quote verification, refusal accuracy, and audit completeness.

## 2026-08-20: Scanned PDF OCR Strategy

Completed:

- Added `docs/ocr-strategy.md` documenting the current fail-closed scanned-PDF contract.
- Documented that OCR remains deferred and must be opt-in through a separate dependency/runtime decision.
- Added tests proving the OCR strategy mentions structured `corpus_load_error`, no persistence/indexing for scanned PDFs, opt-in OCR settings/dependencies, skip-clean optional OCR tests, and no OCR packages in base dependencies.
- Linked the OCR strategy from README.

Verification:

- `python -m pytest tests/unit/test_ocr_strategy.py -q`
- `python -m ruff check tests/unit/test_ocr_strategy.py`
- `python -m scripts.verify default`

Latest validation:

- OCR strategy tests: 3 passed.
- `scripts.verify default` passed: lint, typecheck, 167 selected default tests, and eval.
- Eval metrics remained at 1.0 for retrieval, citations, quote verification, refusal accuracy, and audit completeness.

## 2026-08-20: Agent Verification Guardrails

Completed:

- Added `scripts.verify` as a reproducible verification command matrix for AI agents and local development.
- Added profiles:
  - `default`: lint, mypy, marker-filtered deterministic tests, and eval.
  - `browser`: Playwright UI smoke only.
  - `qdrant`: real-Qdrant smoke only.
  - `full-local`: default gate plus browser and Qdrant smokes.
- Added `--dry-run`, `--reports-dir`, and `--python` options.
- Added Makefile targets: `verify`, `verify-browser`, `verify-qdrant`, and `verify-full-local`.
- Added unit tests for command composition so marker expressions do not drift.
- Added a default GitHub Actions workflow at `.github/workflows/ci.yml` that installs only `.[dev]` and runs `python -m scripts.verify default`.
- Added workflow tests proving default CI does not reference OpenAI secrets, live-provider markers, browser setup, Qdrant setup, or optional smoke markers.
- Ignored editable-install `*.egg-info/` metadata.
- Documented the workflow in README.

Verification:

- `python -m pytest tests/unit/test_verify_script.py -q`
- `python -m ruff check scripts/verify.py tests/unit/test_verify_script.py`
- `python -m scripts.verify full-local --dry-run --reports-dir reports`
- `python -m scripts.verify default`
- `python -m scripts.verify browser`
- `python -m scripts.verify qdrant --dry-run`
- `python -m pytest tests/unit/test_ci_workflow.py -q`
- `python -m pytest -q`

Latest validation:

- `scripts.verify default` passed: lint, typecheck, 164 selected default tests, and eval.
- `scripts.verify browser` passed: 1 browser smoke, 163 deselected.
- Raw suite with browser installed and Qdrant stopped: 165 passed, 1 skipped.
- Eval metrics remained at 1.0 for retrieval, citations, quote verification, refusal accuracy, and audit completeness.

## 2026-08-20: PDF Rule Heading Splitting

Completed:

- Split a single extracted PDF page into multiple `DocumentSection` objects when title-like regulatory headings appear at line boundaries.
- Supported FINRA-style `Rule ...` headings and FCA-style handbook headings such as `COBS 9.2.1R`.
- Preserved source checksum, corpus version, source metadata, extraction method, same-page `page_number`, heading path, monotonic source spans, and stable section IDs for split sections.
- Avoided false positives for mid-sentence rule references and non-heading sentence starts.
- Normalized PDF `metadata.rule_number` so `Rule 1045.` records `1045` instead of `1045.`.
- Verified split sections persist through `/admin/ingest`, show up under `/sources/{source_id}`, and retrieve independently.

Verification:

- `python -m pytest tests/unit/test_pdf_loader.py tests/integration/test_ingest_endpoints.py::test_admin_ingest_pdf_splits_multiple_rules_on_one_page -q`
- `python -m ruff check app/ingestion/loaders.py tests/unit/test_pdf_loader.py tests/integration/test_ingest_endpoints.py`
- `python -m ruff check app tests scripts`
- `python -m mypy app`
- `python -m pytest -m "not live_openai and not requires_browser and not requires_qdrant and not requires_model_download" -q`
- `python -m pytest -q`
- `python -m scripts.run_evals --reports-dir reports`
- Real generated-PDF split smoke using `reportlab` plus `PdfCorpusLoader`

Latest validation:

- Focused PDF split suite: 7 passed.
- Default marker-filtered suite: 158 passed, 2 deselected.
- Raw suite with browser installed and Qdrant stopped: 159 passed, 1 skipped.
- Eval metrics remained at 1.0 for retrieval, citations, quote verification, refusal accuracy, and audit completeness.
- Real generated-PDF split smoke extracted 2 same-page sections, inferred `FINRA Rule 1030(b)` and `FINRA Rule 1045`, and preserved page numbers `[1, 1]`.

## 2026-08-20: Optional PDF Ingestion

Completed:

- Added `PdfCorpusLoader` with lazy `pypdf` loading so default imports and tests do not require PDF extras.
- Extracted one section per nonempty PDF page, preserving page numbers, source checksum, corpus version, extraction method, and inferred FINRA/FCA citation labels where page headings expose rule identifiers.
- Wired `input_type = "pdf"` into `/admin/ingest`, `/documents`, source payloads, and the analyst UI selector.
- Persisted failed ingestion jobs for missing `pypdf` and returned structured `dependency_unavailable` responses with package, extra, install hint, job ID, and path details.
- Returned structured `corpus_load_error` jobs for scanned/image-only PDFs with no extractable text, without persisting source rows or refreshing retrieval.
- Added the optional `pdf` extra.

Verification:

- `python -m pytest tests/unit/test_pdf_loader.py tests/integration/test_ingest_endpoints.py tests/integration/test_ui_endpoint.py -q`
- `python -m ruff check app/ingestion/loaders.py app/api/routes_admin.py app/api/routes_ui.py tests/unit/test_pdf_loader.py tests/integration/test_ingest_endpoints.py tests/integration/test_ui_endpoint.py`
- `python -m ruff check app tests scripts`
- `python -m mypy app`
- `python -m pytest`
- `python -m pytest -m "not live_openai and not requires_browser and not requires_qdrant and not requires_model_download" -q`
- `python -m scripts.run_evals --reports-dir reports`
- Real generated-PDF smoke using `reportlab` plus `PdfCorpusLoader`

Latest validation:

- Full raw test suite after optional browser setup: 155 passed, 1 skipped because Qdrant was intentionally stopped.
- Default marker-filtered suite: 154 passed, 2 deselected.
- Eval metrics remained at 1.0 for retrieval, citations, quote verification, refusal accuracy, and audit completeness.
- Real generated-PDF smoke extracted 2 sections, inferred `FINRA Rule 1030(b)`, and preserved page numbers `[1, 2]`.

## 2026-08-20: Optional Browser UI Smoke

Completed:

- Added a `requires_browser` Playwright smoke for the analyst UI.
- The smoke starts RegLens on an ephemeral port, opens `/`, ingests the fixture,
  selects the source, asks a cited question, verifies citations/evidence, deletes
  the source, and confirms the deleted corpus no longer retrieves.
- The smoke also clicks the UI audit verification control and checks the audit record count.
- Added the optional `browser` extra and `make test-browser`.
- The smoke skips cleanly when Playwright or browser binaries are unavailable.
- Installed `.[browser]` and Playwright Chromium in the current Codex runtime, then verified the smoke passes end to end.

Verification:

- `python -m pytest tests/e2e/test_ui_browser_smoke.py -q -rs`
- `python -m pytest -m requires_browser -q`
- `python -m ruff check app tests scripts`
- `python -m mypy app`

Latest validation:

- Optional browser smoke passed: 1 passed, 155 deselected.

## 2026-08-20: Optional Real Qdrant Smoke

Completed:

- Added a `requires_qdrant` integration smoke for real Qdrant-backed local mode.
- The smoke uses a unique temporary Qdrant collection, verifies `/ready`,
  `/retrieve`, `/query`, `POST /documents`, and `DELETE /documents/{source_id}`,
  then cleans up the collection.
- The smoke skips cleanly when `qdrant-client` or a reachable Qdrant service is unavailable.
- Added `make test-qdrant` so agents can intentionally run Qdrant-marked tests after `make qdrant-up`.
- Pinned the optional `qdrant-client` extra to `>=1.12,<1.14` to keep it compatible with the bundled `qdrant/qdrant:v1.12.1` Docker image.
- Installed `.[qdrant]`, started Qdrant with Docker Compose, verified the smoke passes, and stopped Qdrant.

Verification:

- `python -m pytest tests/integration/test_real_qdrant_smoke.py -q -rs`
- `python -m pytest -m requires_qdrant -q`

Latest validation:

- Optional Qdrant smoke passed: 1 passed, 155 deselected.
- Earlier `qdrant-client 1.19.0` produced a client/server compatibility warning against `qdrant/qdrant:v1.12.1`; after pinning to `qdrant-client 1.13.3`, the smoke passed without that warning.

## 2026-08-20: Local Qdrant Runtime Wiring

Completed:

- Wired `rag_mode=local` to build a Qdrant-backed `RetrievalService` using fake embeddings and fake generation.
- Added optional injected Qdrant client/model support to app startup for deterministic tests without a running Qdrant service.
- Made local mode degrade cleanly when Qdrant or `qdrant-client` is unavailable.
- Updated `/ready` to report Qdrant status, collection, URL, and overall local readiness.
- Preserved Qdrant-backed retrieval during document ingestion refreshes.
- Deleted Qdrant points during document removal so deleted corpora do not keep returning stale dense candidates.
- Generalized retrieval service vector-store typing and diagnostics so local Qdrant responses report `mode = local`.

Verification:

- `python -m pytest tests/integration/test_local_qdrant_runtime.py -q`
- `python -m pytest tests/integration/test_local_qdrant_runtime.py tests/unit/test_qdrant_store.py tests/unit/test_retrieval_service.py tests/integration/test_retrieve_endpoint.py tests/integration/test_query_endpoint_fake_llm.py tests/integration/test_document_endpoints.py tests/integration/test_ingest_endpoints.py tests/integration/test_health.py -q`
- `python -m ruff check app tests scripts`
- `python -m mypy app`
- `python -m pytest`
- `python -m scripts.run_evals --reports-dir reports`

Latest validation:

- Full test suite: 148 passed.
- Eval metrics remained at 1.0 for retrieval, citations, quote verification, refusal accuracy, and audit completeness.
- Live local-mode smoke without Qdrant: `/ready` returned `degraded` with `qdrant.status = unavailable`; `/retrieve` returned structured `dependency_unavailable`.

## 2026-08-20: Retrieval Routing And Evidence Budgeting

Completed:

- Added query route diagnostics for conceptual queries, citation references, and exact citation matches.
- Pinned exact citation matches ahead of broader hybrid candidates while preserving rerank and score diagnostics.
- Enforced a configurable evidence token budget before evidence construction and answer generation.
- Propagated `max_evidence_tokens` through startup, ingestion refresh, deletion refresh, and fixture retrieval builders.

Verification:

- `python -m pytest tests/unit/test_retrieval_service.py::test_exact_citation_query_is_routed_and_pinned tests/unit/test_retrieval_service.py::test_conceptual_query_route_does_not_pin_exact_citation_matches tests/unit/test_retrieval_service.py::test_retrieve_respects_evidence_token_budget tests/integration/test_retrieve_endpoint.py::test_retrieve_endpoint_exposes_exact_citation_route_diagnostics -q`
- `python -m pytest tests/unit/test_retrieval_service.py tests/integration/test_retrieve_endpoint.py tests/integration/test_query_endpoint_fake_llm.py tests/integration/test_eval_runner.py tests/integration/test_ingest_endpoints.py tests/integration/test_document_endpoints.py tests/integration/test_startup_hydration.py -q`

## 2026-08-20: Wave 5 Ingest-To-Query Completion

Completed:

- Refreshed the fake-mode retrieval service after successful local ingestion.
- Preserved the built-in fixture corpus while adding newly ingested chunks to the active retrieval indexes.
- Hydrated fake-mode retrieval from persisted SQLite chunks on startup so ingested corpora survive app restarts.
- Added an app-level lock around fake-mode retrieval refreshes so concurrent admin ingests do not clobber active retrieval state.
- Regenerated source IDs when caller-supplied corpus/version overrides conflict with front matter, preventing cross-corpus source-row clobbering while preserving matching front-matter IDs.
- Added `POST /documents` as a user-facing ingestion alias and `DELETE /documents/{source_id}` for source removal.
- Rebuilt mock retrieval from fixture plus remaining persisted chunks after document deletion so deleted corpora stop retrieving immediately.
- Added `GET /` as a dependency-free analyst UI for queries, citations, evidence snippets, diagnostics, source ingestion, source deletion, and audit verification.
- Added integration coverage proving an ingested corpus can be used immediately through `/retrieve` and `/query`.
- Added edge coverage for idempotent re-ingest, corpus-version filter isolation, failed-ingest no-op refresh behavior, and concurrent ingest refreshes.

Verification:

- `python -m pytest tests/integration/test_ingest_endpoints.py::test_admin_ingest_refreshes_mock_retrieval_for_retrieve_and_query -q`
- `python -m pytest tests/integration/test_ingest_endpoints.py -q`
- `python -m pytest tests/integration/test_startup_hydration.py tests/integration/test_repositories.py -q`
- `python -m pytest tests/unit/test_markdown_loader.py tests/integration/test_ingest_endpoints.py tests/integration/test_source_endpoints.py tests/integration/test_startup_hydration.py -q`
- `python -m pytest tests/integration/test_document_endpoints.py tests/integration/test_ingest_endpoints.py tests/integration/test_source_endpoints.py tests/integration/test_retrieve_endpoint.py tests/integration/test_query_endpoint_fake_llm.py tests/integration/test_startup_hydration.py -q`
- `python -m pytest tests/integration/test_ui_endpoint.py -q`
- `python -m pytest tests/integration/test_ingest_endpoints.py tests/integration/test_source_endpoints.py tests/integration/test_retrieve_endpoint.py tests/integration/test_query_endpoint_fake_llm.py -q`

## 2026-08-19: Wave 5 Local Ingestion And Qdrant Adapter Readiness

Completed:

- Added an optional Qdrant vector store adapter with lazy dependency loading and offline stub-client tests.
- Added local admin ingestion for Markdown, text, and HTML files under the workspace.
- Added ingestion job status, source list, and source detail endpoints.
- Wired source, section, chunk, and ingestion job repositories into app startup.
- Added repository locks for HTTP-safe SQLite access through shared app-state repositories.

Verification:

- focused Qdrant, ingestion, source, and repository pytest suites
- `.\.venv\Scripts\python.exe -m ruff check app tests scripts`
- `.\.venv\Scripts\python.exe -m mypy app`

Notes:

- Qdrant remains optional; default tests do not import `qdrant-client` unless an adapter is constructed without an injected client.
- OpenAI provider work is deferred until the explicit API key reuse/create decision is made.

## 2026-08-19: Wave 4 Quality Gates And Audit Visibility

Completed:

- Added a dependency-free fake lexical reranker and integrated it into retrieval diagnostics.
- Added weak-retrieval abstention before fake answer generation.
- Added audit visibility endpoints for recent query summaries, query details with evidence rows, and hash-chain verification.
- Added an offline eval fixture with 17 synthetic questions.
- Added eval metrics for recall@k, MRR@k, citation precision, quote verification, refusal accuracy, and audit completeness.
- Added `scripts.run_evals`, `make eval`, and JSON/Markdown eval reports under `reports/`.
- Added per-request `/query` IDs and serialized SQLite audit repository access so repeated or concurrent query writes preserve the hash chain.

Verification:

- `.\.venv\Scripts\python.exe -m scripts.run_evals --reports-dir reports`
- `.\.venv\Scripts\python.exe -m ruff check app tests scripts`
- focused eval, audit, and reranker pytest suites

Latest eval summary:

- retrieval recall@3/5/10: 1.0
- retrieval MRR@10: 1.0
- citation precision: 1.0
- quote verification rate: 1.0
- refusal accuracy: 1.0
- audit completeness: 1.0

Notes:

- This wave remains fake-mode only: no OpenAI, Qdrant, model downloads, or network calls.
- The next wave should add Qdrant and provider adapters behind the existing fake-mode contracts.

## 2026-08-19: Wave 3 Auditable Answer Loop

Completed:

- Added prompt assembly with prompt-local evidence markers such as `[E1]`.
- Added deterministic fake LLM generation with an insufficient-evidence fallback.
- Added citation verification and quote/span verification against retrieved snippets.
- Added a generation service that returns domain `Answer` objects and audit-ready query evidence rows.
- Added `POST /query` for retrieve-generate-verify-audit execution.
- Wired SQLite query audit persistence into app startup.
- Added integration tests for cited answers and hash-chained query audit writes.

Verification:

- `.\.venv\Scripts\python.exe -m ruff check app tests`
- `.\.venv\Scripts\python.exe -m mypy app`
- `.\.venv\Scripts\python.exe -m pytest`

Notes:

- This wave remains fake-mode only: no OpenAI, Qdrant, model downloads, or network calls.
- The fake LLM model identity is `fake-reglens-llm-v1`.
- Reranking is implemented in Wave 4 with the fake lexical reranker.

## 2026-08-19: Wave 1 And Wave 2 Fake-Mode Vertical Slice

Completed:

- Created RegLens project skeleton with FastAPI health and readiness endpoints.
- Added typed settings, mock-mode defaults, request IDs, CORS, and sanitized app errors.
- Added domain models and deterministic ID/hash helpers.
- Added SQLite schema and repositories for source documents, sections, chunks, ingestion jobs, query audits, and query evidence.
- Added hash-chain-ready audit helpers in persistence.
- Added Markdown/plain-text/basic HTML ingestion, front matter extraction, citation inference, heading-path preservation, table-preserving normalization, and deterministic chunking.
- Added synthetic FINRA-like fixture rulebook.
- Added fake lexical embeddings and in-memory vector store.
- Added rule-aware BM25 keyword retrieval and Reciprocal Rank Fusion.
- Added fixture-backed retrieval service and `POST /retrieve`.

Verification:

- `ruff check app tests`
- `mypy app`
- `pytest`

Notes:

- This slice intentionally avoids OpenAI, Qdrant, model downloads, and network calls.
- Reranking is not implemented yet; retrieval diagnostics report `reranked_count = 0`.
- The next wave should add real-provider adapters and Qdrant indexing.
