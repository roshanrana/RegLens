# RegLens

RegLens is a cited regulatory intelligence system. The current implementation is a
fake-mode vertical slice: ingest a synthetic rulebook, preserve rule citations, create
deterministic chunks, retrieve evidence, generate grounded answers, and persist
hash-chained, evidence-digested query audits locally.

## Interview Snapshot

| | |
|---|---|
| Role signal | Forward deployed AI engineering for compliance and regulatory workflows: cited answers, inspectable evidence, source lifecycle controls, and audit replay. |
| Product features | FINRA-style document ingestion, citation-preserving chunking, hybrid retrieval, exact citation routing, grounded generation, quote verification, weak-evidence abstention, durable chat sessions, transcript exports, hash-chained audits. |
| Implementation stack | FastAPI, Python 3.11+, SQLite, BM25, Reciprocal Rank Fusion, deterministic fake embeddings/LLM/reranker, optional Qdrant, optional OpenAI providers, optional cross-encoder reranking, Docker/Compose. |
| Validation performed | Lint, mypy, deterministic fake-mode tests, offline eval harness, audit verification endpoint, adversarial source-instruction evals, optional browser/Qdrant/OpenAI/model/container profiles, GitHub Actions. |

## Current State

Wave 1 built the foundation and first local data contracts:

- FastAPI app with health/readiness endpoints
- typed configuration
- fake-mode validation
- sanitized application error shape
- request-id propagation
- deterministic domain IDs
- SQLite metadata repositories
- Markdown regulatory loader
- citation-preserving chunking
- synthetic rulebook fixture

Wave 2 adds the first fake-mode retrieval loop:

- deterministic fake lexical embeddings
- in-memory vector store
- rule-aware BM25 keyword index
- Reciprocal Rank Fusion for hybrid retrieval
- query route diagnostics for conceptual, citation-reference, and exact-citation questions
- exact citation match pinning before evidence selection
- evidence token budget trimming with diagnostics
- fixture-backed retrieval service
- `POST /retrieve` endpoint
- retrieval diagnostics with dense, keyword, and fusion scores

Wave 3 adds the first auditable answer loop:

- prompt assembly with prompt-local `[E1]` evidence markers
- deterministic fake LLM client for cited answers
- insufficient-evidence fallback
- citation and quote verification against retrieved snippets
- `POST /query` endpoint
- SQLite query audit and query evidence writes with hash-chain and evidence-digest metadata

Wave 4 adds quality gates and operational visibility:

- deterministic fake lexical reranker with rerank diagnostics
- weak-retrieval abstention before fake answer generation
- audit read/export endpoints: `GET /audit/queries`, `GET /audit/queries/{query_id}`, `GET /audit/queries/{query_id}/export`, and `GET /audit/verify`
- offline fake-mode eval fixture with retrieval, citation, quote, refusal, source-instruction safety, warning recall, and audit metrics
- `make eval` report generation under `reports/`

Wave 5 adds local ingestion and adapter readiness:

- optional `QdrantVectorStore` adapter with lazy `qdrant-client` dependency loading
- local `rag_mode=local` runtime wiring for Qdrant-backed dense retrieval with fake embeddings/generation
- local mode degrades cleanly when Qdrant is unavailable instead of crashing startup
- `POST /admin/ingest` for local Markdown, text, HTML, and optional PDF files under the workspace
- optional `pypdf` PDF extraction with page-number metadata and graceful missing-dependency/scanned-PDF errors
- fake-mode retrieval indexes refresh after ingestion so newly ingested corpora can be queried immediately
- fake-mode startup hydrates retrieval from persisted SQLite chunks so ingested corpora survive app restarts
- `POST /documents` as a user-facing ingestion alias and `DELETE /documents/{source_id}` for source removal
- `GET /admin/ingest/{job_id}` for ingestion job status
- `GET /sources` and `GET /sources/{source_id}` for persisted source, section, and chunk inspection
- `GET /` serves a dependency-free analyst UI for querying, citations, evidence, diagnostics, provenance, audit export, source lifecycle events, and document lifecycle actions

Wave 6 adds provider-readiness scaffolding without enabling live calls:

- explicit provider-name settings for embeddings, generation, and reranking
- provider factories wired into app startup for mock and local modes
- readiness checks that report provider names, fake flags, models, and gated errors
- OpenAI embedding/generation selections fail closed without importing the OpenAI SDK
- cross-encoder reranker selection fails closed without model downloads
- `/retrieve` and `/query` surface provider startup failures as structured `dependency_unavailable` errors

Wave 7 activates the optional OpenAI provider layer:

- optional `openai` dependency extra
- `.env.local` loading for locally saved `OPENAI_API_KEY` values
- OpenAI embeddings provider using configurable embedding model and dimensions
- OpenAI Responses generation client with strict structured output parsing
- live-provider factories that instantiate only when provider names and API key are explicit
- sanitized OpenAI request failure diagnostics with provider error codes such as `insufficient_quota`
- explicit `live_openai` smoke tests and `scripts.verify openai` profile

Wave 8 activates the optional cross-encoder reranker layer:

- optional `rerank` dependency extra for `sentence-transformers`
- configurable cross-encoder model, batch size, max length, device, cache folder, local-files-only mode, and `trust_remote_code`
- lazy model loading only when `REGLENS_RERANKER_PROVIDER=cross_encoder` and fake reranking is disabled
- injectable fake-model tests for ranking, tie breaks, score parsing, top-k, diagnostics, and sanitized failures
- explicit `requires_model_download` smoke test and `scripts.verify models` profile

Wave 9 adds a chat-compatible API surface that still works without billing:

- `POST /chat` returns the same grounded, cited JSON payload as `/query`
- optional `stream=true` emits Server-Sent Events for UI/agent integrations
- streaming events include metadata, answer delta, citations, evidence, final payload, and done
- provider startup failures are surfaced through `/chat` with the same structured diagnostics as `/query`

Wave 10 adds durable chat sessions for app and agent workflows:

- `/chat` creates a session automatically when no `session_id` is supplied
- existing sessions can be continued by sending `session_id`
- chat turns are stored in SQLite and linked to immutable query audit records
- `GET /chat/sessions`, `GET /chat/sessions/{session_id}`, and `DELETE /chat/sessions/{session_id}` manage chat history
- the analyst UI now asks through `/chat`, tracks the active session, and shows recent sessions and turns

Wave 11 adds reverse audit-to-chat traceability:

- chat-created query audits expose the originating session and turn in audit summaries, audit detail, and JSON/Markdown exports
- `/query`-created audits remain unchanged except for an additive `chat: null`
- deleting a chat session removes chat history but preserves immutable query audit records

Wave 12 adds portable chat transcript exports:

- `GET /chat/sessions/{session_id}/export?format=json` returns a structured session transcript
- `GET /chat/sessions/{session_id}/export?format=markdown` returns a reviewer-friendly transcript with query audit paths
- the analyst UI can load the active chat transcript into the diagnostics panel

Wave 13 adds production-hardening controls from the original plan:

- `POST /admin/ingest-url` and `POST /documents/url` fetch allowlisted HTTPS regulatory URLs, snapshot raw source bytes locally, ingest the snapshot, and preserve the source URL for audit
- FINRA URL ingestion is allowlisted by default for `finra.org`, `www.finra.org`, and `rules.finra.org`
- `/retrieve`, `/query`, and `/chat` accept an optional `source_id` filter that is applied before dense and keyword scoring
- OpenAI embeddings can use a bounded in-memory cache keyed by provider/model/dimensions/text hash
- query diagnostics and audit rows include deterministic live-provider cost estimates for the cost-capped OpenAI demo models
- optional API-key authentication and in-memory per-minute rate limiting can protect operational routes while leaving health/readiness/docs/UI public

No OpenAI, billing, Qdrant, PDF extra, network calls, or model downloads are
required for mock mode, the UI, `/query`, `/chat`, or the default test suite.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
make install
```

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
make install
```

If you are running inside Codex Desktop on Windows and `python` is unavailable, use the bundled Python path reported by the app's workspace dependencies tool, or run Makefile commands with `PYTHON=<absolute-python-path>`.

## Run API

```bash
python -m uvicorn app.main:app --reload
```

Then open:

- `GET /`
- `GET /health`
- `GET /ready`
- `GET /docs`

`/ready` is a diagnostic endpoint: degraded startup states still return HTTP
200 with `"status": "degraded"` and detailed provider/service checks in the
body. Deployment probes should inspect the JSON status field.

## Run With Docker

The Docker image defaults to mock mode and does not require OpenAI billing,
Qdrant, model downloads, or local secret files.

```bash
docker build -t reglens:local .
docker run --rm -p 8000:8000 -v reglens_data:/app/data reglens:local
```

Compose keeps the existing Qdrant service as the default. Start the RegLens app
container explicitly with the `app` profile:

```bash
docker compose --profile app up --build reglens
```

## Retrieve Evidence

```bash
curl -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"question":"How long must records be retained?","corpus_id":"finra-synthetic","top_k":3}'
```

PowerShell:

```powershell
$body = @{ question = "How long must records be retained?"; corpus_id = "finra-synthetic"; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/retrieve" -Method Post -ContentType "application/json" -Body $body
```

The fixture query should return `FINRA Rule 1030(b)` as the top citation.

## Ask A Question

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How long must records be retained?","corpus_id":"finra-synthetic","corpus_version":"2026-08-19","top_k":3}'
```

PowerShell:

```powershell
$body = @{ question = "How long must records be retained?"; corpus_id = "finra-synthetic"; corpus_version = "2026-08-19"; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/query" -Method Post -ContentType "application/json" -Body $body
```

The fixture answer should cite `FINRA Rule 1030(b)`, include `six years`, and
return audit hash and evidence digest metadata under `diagnostics.audit`.

## Chat Endpoint

`POST /chat` is the app/agent-friendly alias for asking questions. Without
streaming it returns the same JSON contract as `/query`:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"How long must records be retained?","corpus_id":"finra-synthetic","corpus_version":"2026-08-19","top_k":3}'
```

PowerShell:

```powershell
$body = @{ question = "How long must records be retained?"; corpus_id = "finra-synthetic"; corpus_version = "2026-08-19"; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body $body
```

For stream-capable UIs, set `stream=true`. RegLens emits SSE events named
`metadata`, `answer_delta`, `citations`, `evidence`, `final`, and `done`.

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"How long must records be retained?","corpus_id":"finra-synthetic","corpus_version":"2026-08-19","top_k":3,"stream":true}'
```

Chat responses include a `chat` object with `session_id`, `turn_id`,
`turn_index`, `query_id`, `session_path`, and `audit_path`. To continue an
existing chat, pass the returned `session_id` in the next `/chat` request.

```bash
curl http://127.0.0.1:8000/chat/sessions
curl http://127.0.0.1:8000/chat/sessions/{session_id}
curl "http://127.0.0.1:8000/chat/sessions/{session_id}/export?format=json"
curl "http://127.0.0.1:8000/chat/sessions/{session_id}/export?format=markdown"
curl -X DELETE http://127.0.0.1:8000/chat/sessions/{session_id}
```

## Inspect Audit Records

```bash
curl http://127.0.0.1:8000/audit/queries
curl http://127.0.0.1:8000/audit/verify
curl http://127.0.0.1:8000/audit/source-events
curl "http://127.0.0.1:8000/audit/queries/{query_id}/export?format=json"
curl "http://127.0.0.1:8000/audit/queries/{query_id}/export?format=markdown"
```

PowerShell:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/audit/queries" -Method Get
Invoke-RestMethod -Uri "http://127.0.0.1:8000/audit/verify" -Method Get
Invoke-RestMethod -Uri "http://127.0.0.1:8000/audit/source-events" -Method Get
Invoke-RestMethod -Uri "http://127.0.0.1:8000/audit/queries/{query_id}/export?format=json" -Method Get
Invoke-RestMethod -Uri "http://127.0.0.1:8000/audit/queries/{query_id}/export?format=markdown" -Method Get
```

`/audit/verify` validates both the query audit hash chain and the persisted
query evidence digest/count, so edited or deleted evidence rows are reported as
integrity failures. The export endpoint returns a portable JSON or Markdown
evidence pack for a single answer. Query audit records are append-only:
attempting to save an existing `query_id` is rejected rather than updated.
`/audit/source-events` lists ingestion/deletion lifecycle events with request ID,
source checksum, corpus/version, job ID, action, status, and actor placeholder.
Query and audit payloads keep backward-compatible warning codes and add
structured `warning_details` with severity and reviewer-friendly messages.

## Ingest Local Sources

```bash
curl -X POST http://127.0.0.1:8000/admin/ingest \
  -H "Content-Type: application/json" \
  -d '{"path":"app/evals/fixtures/synthetic_rulebook.md","input_type":"markdown","corpus_id":"finra-synthetic","corpus_name":"FINRA Synthetic Rulebook","version":"2026-08-19"}'
```

PowerShell:

```powershell
$body = @{
  path = "app/evals/fixtures/synthetic_rulebook.md"
  input_type = "markdown"
  corpus_id = "finra-synthetic"
  corpus_name = "FINRA Synthetic Rulebook"
  version = "2026-08-19"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/ingest" -Method Post -ContentType "application/json" -Body $body
Invoke-RestMethod -Uri "http://127.0.0.1:8000/sources" -Method Get
```

In mock mode, a successful ingestion response includes
`job.report.retrieval_index_chunks` and the ingested `corpus_id`/`corpus_version`
can be used immediately with `/retrieve` and `/query`. When using a file-backed
SQLite database, the same persisted chunks are loaded into mock retrieval on the
next app startup.

Supported `input_type` values are `markdown`, `text`, `html`, and `pdf`.
PDF ingestion is optional and requires:

```bash
python -m pip install -e ".[pdf]"
```

PDF pages with extractable text become cited sections with `page_number`
metadata. When multiple title-like FINRA/FCA rule headings appear on the same
PDF page, RegLens splits them into separate cited sections while preserving the
same page number. Missing `pypdf` returns a structured
`dependency_unavailable` error, and scanned/image-only PDFs return a failed
ingestion job with `corpus_load_error`. OCR remains a deferred opt-in decision;
see [docs/ocr-strategy.md](docs/ocr-strategy.md).

## Ingest FINRA URLs

Remote ingestion is explicit and allowlisted. By default, RegLens accepts HTTPS
URLs under `finra.org`, `www.finra.org`, and `rules.finra.org`, writes a local
snapshot under `REGLENS_DOCUMENT_STORAGE_PATH/remote`, then runs the normal
ingestion/chunking/audit path.

```powershell
$body = @{
  url = "https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210"
  input_type = "html"
  corpus_id = "finra-rules"
  corpus_name = "FINRA Rules"
  version = "live-demo"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/ingest-url" -Method Post -ContentType "application/json" -Body $body
```

Use the returned `source.source_id` as a precise retrieval/query scope:

```powershell
$query = @{
  question = "What standards apply to communications with the public?"
  corpus_id = "finra-rules"
  corpus_version = "live-demo"
  source_id = "<source_id from ingest response>"
  top_k = 3
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/retrieve" -Method Post -ContentType "application/json" -Body $query
```

## OpenAI Providers

OpenAI support is optional and outside the default fake-mode gate. Billing or
quota is only needed for live OpenAI smoke tests and live-provider runs; the
mock product, default tests, ingestion, citations, audit trail, UI, and `/chat`
do not require it.

```bash
python -m pip install -e ".[openai]"
```

Save `OPENAI_API_KEY` in `.env.local` or the environment. Do not commit local
secret files. To select the live providers, set:

```env
REGLENS_RAG_MODE=local
REGLENS_EMBEDDING_PROVIDER=openai
REGLENS_LLM_PROVIDER=openai
REGLENS_USE_FAKE_EMBEDDINGS=false
REGLENS_USE_FAKE_LLM=false
REGLENS_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
REGLENS_OPENAI_EMBEDDING_DIMENSIONS=1536
REGLENS_OPENAI_GENERATION_MODEL=gpt-5.4-nano
REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS=400
REGLENS_ENABLE_EMBEDDING_CACHE=true
REGLENS_EMBEDDING_CACHE_MAX_ENTRIES=10000
```

The live OpenAI defaults are cost-sensitive and capped for smoke testing:
`text-embedding-3-small` for embeddings, and `gpt-5.4-nano` for generation.
OpenAI's model catalog lists `gpt-5.4-nano` as the cheapest GPT-5.4-class
model. `gpt-5-nano` is lower-cost on paper, but it did not satisfy RegLens'
structured cited-answer smoke test, so the project default uses the cheapest
tested model that passes. The Responses API `max_output_tokens` setting is used
to bound live test output.

Full local `/query` also needs Qdrant available because local mode indexes
chunks at startup. Use a separate Qdrant collection when changing embedding
dimensions.

Live-provider query responses include `diagnostics.cost_estimate`, and the
query audit row stores `estimated_cost_usd`. Estimates use deterministic
character-based token counts so audits stay reproducible.

## API Hardening

Operational routes are open by default for local development. To require an API
key for `/retrieve`, `/query`, `/chat`, admin ingestion, sources, and audit
routes, set:

```env
REGLENS_API_KEY=<local-demo-key>
REGLENS_RATE_LIMIT_PER_MINUTE=60
```

Clients can send the key as `X-RegLens-API-Key: <local-demo-key>` or
`Authorization: Bearer <local-demo-key>`. The default exempt paths are `/`,
`/health`, `/ready`, `/docs`, and `/openapi.json`.

## Cross-Encoder Reranker

Cross-encoder reranking is optional and outside the default fake-mode gate:

```bash
python -m pip install -e ".[rerank]"
```

To select it, set:

```env
REGLENS_RAG_MODE=local
REGLENS_RERANKER_PROVIDER=cross_encoder
REGLENS_USE_FAKE_RERANKER=false
REGLENS_CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
REGLENS_CROSS_ENCODER_BATCH_SIZE=16
REGLENS_CROSS_ENCODER_TRUST_REMOTE_CODE=false
```

The first model load may download weights from Hugging Face unless
`REGLENS_CROSS_ENCODER_LOCAL_FILES_ONLY=true`. The opt-in smoke is:

```powershell
$env:REGLENS_RUN_MODEL_DOWNLOAD_TESTS = "true"
.\.venv\Scripts\python.exe -m scripts.verify models
```

## Manage Documents

`POST /documents` accepts the same body as `/admin/ingest` and returns the same
job/source payload. `DELETE /documents/{source_id}` removes the source, cascades
its sections/chunks from SQLite, and refreshes mock retrieval so deleted corpora
are no longer returned.

## Quality Gates

```bash
make lint
make typecheck
make test
make verify
make test-browser
make test-qdrant
make test-models
make test-container
make verify-openai
make verify-models
make verify-container
python -m scripts.verify openai
make eval
```

Default tests exclude live OpenAI, Qdrant, browser, and model-download markers.
Unit and integration tests must stay deterministic in fake mode; PDF coverage
uses fake `pypdf` readers and does not require the `pdf` extra.
`make verify` runs the default agent gate: lint, typecheck, default tests, and
eval. The eval command writes `reports/eval-latest.json` and
`reports/eval-latest.md`. The fake-mode eval suite includes adversarial
source-instruction cases for instruction override, citation suppression, prompt
leak, and same-sentence clause injection, and reports `answer_safety` plus
`warning_recall` alongside retrieval, citation, quote, refusal, and audit
metrics.
`make test-browser` intentionally runs tests marked `requires_browser`; those
tests skip when Playwright or browser binaries are unavailable.
`make test-qdrant` intentionally runs tests marked `requires_qdrant`; those tests
skip when `qdrant-client` or a reachable Qdrant service is unavailable.
`python -m scripts.verify openai` intentionally runs tests marked
`live_openai`; those tests skip when credentials, the optional SDK, or external
account quota are unavailable.
`make test-models` and `make verify-models` intentionally run tests marked
`requires_model_download`; those tests skip unless model downloads are explicitly
enabled with `REGLENS_RUN_MODEL_DOWNLOAD_TESTS=true`.

Agents can inspect or run the same command matrix directly:

```bash
python -m scripts.verify default --dry-run
python -m scripts.verify default
python -m scripts.verify browser
python -m scripts.verify qdrant
python -m scripts.verify openai
python -m scripts.verify models
python -m scripts.verify container
```

`python -m scripts.verify full-local` runs the default gate plus browser and
Qdrant smokes; start Qdrant first when you want that profile to pass rather than
skip/fail on service availability.
`python -m scripts.verify container` runs static packaging tests and Docker
Compose config rendering. It does not build an image or require OpenAI billing.

## Optional Browser Smoke

The UI has an optional browser-level smoke for the end-to-end analyst workflow.

```bash
python -m pip install -e ".[browser]"
python -m playwright install chromium
make test-browser
```

The smoke starts the API on an ephemeral local port, opens the UI, ingests the
fixture, selects the source, asks a cited question, verifies citations/evidence,
deletes the source, and confirms the deleted corpus no longer retrieves.

## Local Qdrant Mode

Qdrant is optional. Fake mode and default tests do not require the
`qdrant-client` package or a running Qdrant service. For local Qdrant-backed
dense retrieval, install the optional extra and start Qdrant. The `qdrant`
extra is pinned to the client range compatible with the bundled
`qdrant/qdrant:v1.12.1` compose image.

```bash
python -m pip install -e ".[qdrant]"
make qdrant-up
REGLENS_RAG_MODE=local python -m uvicorn app.main:app --reload
make test-qdrant
```

PowerShell:

```powershell
python -m pip install -e ".[qdrant]"
make qdrant-up
$env:REGLENS_RAG_MODE = "local"
python -m uvicorn app.main:app --reload
make test-qdrant
```

In local mode, RegLens still uses fake embeddings, fake generation, and the fake
reranker by default. Provider names are explicit in `/ready`; selecting OpenAI
embeddings/generation requires `.[openai]`, `OPENAI_API_KEY`, available account
quota, and non-fake provider settings. Selecting the cross-encoder reranker
requires `.[rerank]`; first model load may download weights unless
`REGLENS_CROSS_ENCODER_LOCAL_FILES_ONLY=true`. If Qdrant is unavailable, startup
succeeds and `/ready` reports a degraded Qdrant check; retrieval returns a
structured `dependency_unavailable` error.
The optional Qdrant smoke uses a unique temporary collection and cleans it up
after verifying local-mode retrieve, query, ingest, and document deletion.

Stop services:

```bash
make qdrant-down
```

## Environment

Settings are read from process environment variables. `.env` and `.env.local`
files are loaded automatically for local runs. Prefer the `REGLENS_` prefix,
though the first Wave 1 variables remain backward-compatible with their
unprefixed names.

Important defaults:

- `REGLENS_RAG_MODE=mock`
- `REGLENS_EMBEDDING_PROVIDER=fake`
- `REGLENS_LLM_PROVIDER=fake`
- `REGLENS_RERANKER_PROVIDER=fake`
- `REGLENS_USE_FAKE_EMBEDDINGS=true`
- `REGLENS_USE_FAKE_LLM=true`
- `REGLENS_USE_FAKE_RERANKER=true`

Mock mode rejects live-provider flags and non-fake provider names because it
must never require OpenAI, Qdrant, or model downloads. Setting
`REGLENS_OPENAI_API_KEY` alone does not enable live providers; provider names
and fake flags must be changed deliberately. Optional provider branches return
structured `dependency_unavailable` errors when their package, key, quota, or
model runtime is unavailable.

## Project Plan

The canonical agent implementation plan is:

- `AGENT_IMPLEMENTATION_PLAN.md`
