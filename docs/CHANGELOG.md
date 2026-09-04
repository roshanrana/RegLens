# RegLens — Build Log

How the system was built, wave by wave. Each wave shipped behind the same gate (`make verify`: lint, strict types, offline tests, eval) and left the default fake mode working without OpenAI, Qdrant, model downloads or network access.

---


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
