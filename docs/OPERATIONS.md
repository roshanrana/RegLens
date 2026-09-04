# RegLens — Operations Guide

Every way to run, configure, verify and extend RegLens. The [README](../README.md) is the front door; [OVERVIEW.md](OVERVIEW.md) explains the design; [SHOWCASE.md](SHOWCASE.md) tours the features. This document is the reference.

---

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

If `python` is not on your PATH, run Makefile commands with `PYTHON=<absolute-python-path>`.

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
see [docs/ocr-strategy.md](ocr-strategy.md).

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

The same command matrix can be inspected or run directly:

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
