# RegLens Forward Deployed Engineer Project Brief

## Executive Summary

RegLens is an LLM-powered regulatory and compliance RAG system designed as a
"Policy Copilot" for financial institutions. It ingests regulatory source
material, retrieves relevant rule sections, generates grounded answers, verifies
citations and quotes, and preserves an auditable record of every answer.

The project is useful because financial institutions cannot rely on opaque
AI-generated answers when dealing with regulations. A compliance analyst needs
to know exactly where an answer came from, what evidence supported it, whether
the system was uncertain, and whether the answer can be reproduced later for
audit or model-risk review.

RegLens demonstrates the type of end-to-end work expected from a Forward
Deployed Engineer:

- Translate an ambiguous business problem into a working technical system.
- Design architecture around client constraints such as auditability, cost,
  data locality, security, and reliability.
- Integrate AI models, retrieval systems, APIs, local services, tests, and UI
  workflows into a usable product.
- Build incrementally with deterministic test gates before enabling live
  providers.
- Produce a deployable, explainable solution that a client stakeholder can
  evaluate and trust.

## Real-World Problem Addressed

Financial firms operate in heavily regulated environments. Compliance teams
must interpret large rulebooks such as FINRA rules, FCA Handbook material,
internal policies, procedures, and supervisory guidance. The practical problems
are not only that the documents are long. The harder problems are:

- Regulations change and teams must stay current.
- Specific rule references matter, for example "FINRA Rule 2210" or "Rule
  1030(b)".
- Analysts need fast answers but cannot accept hallucinated legal-sounding text.
- Model-risk and audit teams need a record of what evidence was used.
- Internal stakeholders need to know when the system does not have enough
  evidence.
- Firms may need self-hosted or local options because of data sovereignty and
  confidentiality constraints.
- Cost must be managed when embedding documents or running live LLM queries.

RegLens addresses these problems by treating the core product promise as:

> Answer only from retrieved regulatory evidence, cite every material claim, and
> make the answer inspectable and auditable.

## Target Users

Primary user:

- Compliance analyst at a broker-dealer, bank, fintech, asset manager, or
  consulting firm.

Secondary users:

- Legal or policy reviewer who wants source-level traceability.
- Model-risk or audit stakeholder who needs reproducibility.
- Engineering reviewer evaluating reliability, architecture, and test quality.
- Forward Deployed Engineer demonstrating practical AI deployment skill.

## Core User Workflows

### 1. Ask a Regulatory Question

A user asks a natural-language question such as:

```text
What standards apply to communications with the public?
```

RegLens retrieves relevant evidence, generates a grounded response, returns
citations, and exposes retrieval diagnostics.

### 2. Inspect Citations and Evidence

The answer includes source-backed citations. Evidence rows include:

- evidence ID
- chunk ID
- citation label
- source URL
- supporting snippet
- retrieval rank
- dense, keyword, fusion, and rerank scores
- quote verification status

This lets a reviewer inspect not just the final answer, but why the system chose
the source material.

### 3. Ingest Regulatory Material

RegLens supports local ingestion for:

- Markdown
- plain text
- HTML
- optional PDF extraction with `pypdf`

It also supports explicit allowlisted remote ingestion for FINRA URLs through:

- `POST /admin/ingest-url`
- `POST /documents/url`

Remote ingestion snapshots fetched source bytes locally so future review is not
dependent only on the remote web page.

### 4. Use Chat With Persistent Sessions

The `/chat` endpoint provides a chat-compatible interface over the same
grounded `/query` logic. Chat sessions are durable and linked to immutable query
audits.

Supported chat operations include:

- create session automatically
- continue an existing session
- list sessions
- inspect turns
- delete chat history while preserving query audits
- export transcripts as JSON or Markdown
- stream responses through Server-Sent Events

### 5. Review Audit Trail

Every served query writes an audit record containing:

- question
- normalized question
- answer
- warnings
- selected evidence
- citation and quote verification metadata
- model names
- prompt version
- retrieval configuration
- latency
- estimated live-provider cost
- hash-chain metadata

The audit system can detect edited or deleted persisted query evidence rows.

## Functional Features

### API and Application Foundation

- FastAPI backend.
- `/health` endpoint.
- `/ready` endpoint with provider and service checks.
- Request ID propagation through `X-Request-ID`.
- Sanitized domain-specific error responses.
- Typed configuration with environment variable support.
- Dependency-free mock mode for deterministic local development.
- Local developer UI served at `/`.

### Ingestion

- Local file ingestion through `POST /admin/ingest`.
- User-facing document registration through `POST /documents`.
- URL ingestion through `POST /admin/ingest-url` and `POST /documents/url`.
- Default URL allowlist for FINRA domains:
  - `finra.org`
  - `www.finra.org`
  - `rules.finra.org`
- Local source snapshots for remote URL ingestion.
- Markdown loader.
- HTML-to-Markdown loader.
- plain-text loader.
- optional PDF loader using `pypdf`.
- PDF page-number metadata.
- PDF rule-heading split for pages containing multiple regulatory sections.
- fail-closed scanned/image-only PDF behavior.
- structured missing-dependency errors.
- source checksum preservation.
- stable source, section, chunk, query, and evidence IDs.
- persisted ingestion job records.
- ingestion lifecycle audit events.
- immediate retrieval refresh after ingestion.
- mock startup hydration from persisted chunks.
- source deletion with retrieval refresh.

### Chunking and Metadata

- Citation-preserving chunking.
- Deterministic chunk IDs.
- heading path preservation.
- section title preservation.
- corpus ID and version metadata.
- source ID metadata.
- source checksum metadata.
- page number and source span metadata when available.
- token count tracking.
- evidence token budget trimming before generation.

### Retrieval

- Dense retrieval through deterministic fake embeddings in mock mode.
- Optional OpenAI embeddings.
- Optional Qdrant vector store in local mode.
- In-memory vector store for tests and mock mode.
- BM25 keyword retrieval.
- regulatory-aware tokenizer for rule references.
- citation-label boosting.
- title and heading boosting.
- hybrid retrieval through Reciprocal Rank Fusion.
- exact citation route detection.
- exact citation pinning before evidence selection.
- query route diagnostics:
  - conceptual
  - citation reference
  - exact citation
- optional source-level scope filter through `source_id`.
- corpus ID and corpus version filters.
- retrieval diagnostics with dense, keyword, fusion, and rerank metadata.
- graceful degradation when Qdrant is unavailable.

### Reranking

- deterministic fake lexical reranker for mock mode.
- optional cross-encoder reranker with `sentence-transformers`.
- configurable model name, batch size, max length, device, cache folder, local
  files only, and `trust_remote_code`.
- model-download tests isolated behind an explicit marker.
- sanitized failure handling for missing packages or model errors.

### Generation and Grounding

- Provider-neutral generation service.
- deterministic fake LLM for default testing.
- optional OpenAI Responses API generation client.
- strict structured output parsing for OpenAI responses.
- prompt assembly that treats source text as untrusted evidence.
- evidence markers such as `[E1]`.
- instruction filtering for malicious source text.
- insufficient-evidence fallback.
- weak-retrieval abstention before answer generation.
- citation verifier.
- quote verifier.
- warnings for low-confidence or source-instruction risks.
- cost-capped OpenAI generation default:
  - `gpt-5.4-nano`
  - `REGLENS_OPENAI_GENERATION_MAX_OUTPUT_TOKENS=400`
- cheapest tested OpenAI embedding default:
  - `text-embedding-3-small`

### Chat and Transcripts

- `/chat` endpoint compatible with `/query` response shape.
- optional `stream=true` Server-Sent Events.
- streaming events:
  - metadata
  - answer delta
  - citations
  - evidence
  - final
  - done
- persistent chat sessions.
- persistent chat turns.
- query audit links from every chat turn.
- reverse audit-to-chat traceability.
- JSON transcript export.
- Markdown transcript export.
- UI integration for chat sessions and transcript loading.

### Audit and Compliance Review

- append-only query audit records.
- hash-chain audit metadata.
- evidence digest metadata.
- query evidence persistence.
- audit list endpoint.
- audit detail endpoint.
- audit export as JSON or Markdown.
- audit verification endpoint.
- source lifecycle audit events.
- detection of edited or deleted persisted query evidence rows.
- audit-to-chat links for chat-created queries.
- `chat: null` for non-chat `/query` audit records.

### Cost, Caching, and Provider Controls

- Optional bounded in-memory OpenAI embedding cache.
- cache keys include provider, model, dimensions, and text hash.
- deterministic live-provider cost estimates.
- query diagnostics include `cost_estimate`.
- audit rows persist `estimated_cost_usd`.
- OpenAI live-provider tests are isolated from default CI.
- missing OpenAI keys fail closed before importing the SDK.
- request failures include sanitized provider error codes.
- fake mode requires no billing or OpenAI credentials.

### Security and Operational Hardening

- Optional API-key authentication.
- supported API key locations:
  - `X-RegLens-API-Key`
  - `Authorization: Bearer ...`
- public exempt paths by default:
  - `/`
  - `/health`
  - `/ready`
  - `/docs`
  - `/openapi.json`
- optional in-memory per-minute rate limiting.
- CORS configuration.
- local path validation for file ingestion.
- HTTPS-only remote ingestion.
- remote ingestion host allowlist.
- remote ingestion max byte limit.
- final redirect URL host validation.
- no secrets in error bodies.

### UI

- dependency-free analyst UI served by FastAPI.
- question input.
- cited answer display.
- evidence and citation panels.
- diagnostics panel.
- source ingestion controls.
- document deletion controls.
- source lifecycle event display.
- audit export controls.
- audit verification display.
- active chat session tracking.
- recent chat session list.
- chat transcript export display.

### Testing, Verification, and CI Readiness

- deterministic fake-mode default tests.
- no OpenAI, Qdrant, browser, model download, or network calls required for the
  default verifier.
- `scripts.verify` profiles:
  - `default`
  - `browser`
  - `qdrant`
  - `openai`
  - `models`
  - `container`
  - `full-local`
- offline eval harness.
- eval metrics:
  - retrieval recall at 3, 5, and 10
  - retrieval MRR at 10
  - citation precision
  - quote verification rate
  - refusal accuracy
  - answer safety
  - warning recall
  - audit completeness
- adversarial source-instruction eval cases.
- browser smoke test marker.
- Qdrant smoke test marker.
- OpenAI live smoke marker.
- model-download smoke marker.
- container verification profile.
- GitHub Actions default verification.
- separate static container verification CI job.

### Packaging and Local Deployment

- Dockerfile.
- `.dockerignore`.
- Docker Compose for Qdrant.
- optional Docker Compose app profile.
- mock-safe container defaults.
- Make targets for install, lint, typecheck, test, eval, Qdrant, browser, model,
  OpenAI, and container verification.

## Architecture

RegLens follows a layered architecture:

```text
User / UI / API Client
        |
FastAPI routes: /retrieve, /query, /chat, /admin/ingest, /audit
        |
Application services
        |
Ingestion -> Chunking -> Embeddings -> Vector Store + BM25
        |
Hybrid retrieval -> RRF fusion -> Reranking -> Evidence selection
        |
Prompt assembly -> LLM generation -> Citation and quote verification
        |
Audit persistence -> Hash-chain verification -> Export
```

Key design principle:

> Keep the audit-critical path explicit and typed rather than hiding it behind a
> large orchestration framework.

This makes the system easier to test, debug, explain, and adapt for a client.

## How RegLens Uses AI

RegLens uses AI in three distinct ways.

### 1. AI in the Product

The application uses AI to turn natural-language questions into grounded
regulatory answers.

AI capabilities in the product include:

- semantic retrieval through embeddings
- LLM-based answer generation
- structured output parsing
- evidence-conditioned prompting
- answer abstention when evidence is insufficient
- citation-aware responses
- optional cross-encoder reranking

Importantly, AI is constrained by retrieval evidence and verification. The LLM
does not get to act as an unchecked source of truth.

### 2. AI in System Design

The project was designed around AI-agent-friendly implementation waves:

- build mock mode first
- define stable contracts
- add deterministic tests
- add provider interfaces
- enable live providers only behind explicit configuration
- isolate optional services behind markers
- document every wave in implementation notes

This is useful for real-world engineering because production AI systems often
fail when teams try to connect models before they have reliable data contracts,
evals, and fallback behavior.

### 3. AI in Development and Integration

The build process demonstrates how AI agents can be used as engineering
partners:

- compare and optimize project plans
- break implementation into waves
- implement scoped features
- add tests before and after integrations
- run focused and full verification profiles
- keep a running implementation log
- use sidecar review agents for gap analysis
- preserve deterministic defaults while integrating live providers

This mirrors how an FDE can use AI internally to accelerate discovery,
implementation, testing, documentation, and client demos.

## Why This Matters for a Forward Deployed Engineer Role

Forward Deployed Engineers work at the boundary between client problems and
production software. RegLens demonstrates that skill set because it is not only
a model demo. It is a usable, tested system with integration boundaries,
operational controls, and stakeholder-facing auditability.

### Skill Mapping

| FDE Skill | How RegLens Demonstrates It |
| --- | --- |
| Problem framing | Converts "chat with regulations" into auditable regulatory question answering. |
| Client empathy | Prioritizes compliance analyst needs: citations, warnings, source inspection, audit exports. |
| Systems design | Separates ingestion, retrieval, reranking, generation, verification, audit, and UI. |
| AI integration | Integrates embeddings, LLM generation, structured outputs, and reranking behind provider interfaces. |
| Data engineering | Normalizes source documents, preserves metadata, chunks sections, stores sources/chunks/audits. |
| Security mindset | Adds API-key auth, rate limiting, local path validation, URL allowlists, and secret-safe errors. |
| Reliability | Uses deterministic fake mode, optional service gates, and graceful degradation. |
| Evaluation | Includes retrieval, citation, quote, refusal, safety, warning, and audit metrics. |
| Deployment readiness | Includes Docker, Compose, CI-friendly verification, and mock-safe container defaults. |
| Client enablement | Provides README, implementation notes, API docs, UI, and exportable evidence packs. |

## Client-Facing Value

RegLens can be presented to a financial services client as a prototype for:

- regulatory research assistant
- internal policy copilot
- supervision and compliance QA tool
- audit evidence pack generator
- policy-to-regulation mapping assistant
- model-risk-friendly RAG reference architecture

The client value is not only faster answers. The main value is faster answers
that are easier to inspect, challenge, verify, and reproduce.

## Example Demo Narrative

A strong demo flow for interviews or portfolio review:

1. Start RegLens in mock mode.
2. Open the UI at `http://127.0.0.1:8011`.
3. Ask: `How long must records be retained?`
4. Show the cited answer and evidence.
5. Open retrieval diagnostics and explain dense plus keyword retrieval.
6. Export the audit evidence pack.
7. Ask an unsupported question and show safe refusal.
8. Ingest a FINRA URL or a local rulebook fixture.
9. Query with `source_id` to show source-scoped retrieval.
10. Show `/audit/verify` proving the audit trail is intact.
11. Explain that OpenAI, Qdrant, browser tests, and cross-encoder models are
    optional profiles rather than requirements for local development.

This tells a complete FDE story: discover the problem, build the system, prove
quality, and explain operational behavior.

## Real-World Deployment Considerations

The project already includes many production-oriented controls. The next
extensions for a real deployment would be:

- PostgreSQL for production metadata and audit storage.
- Redis or managed cache for embeddings and repeated query results.
- durable async ingestion workers for larger corpora.
- stronger role-based access control.
- tenant isolation.
- richer corpus version diffing.
- OCR for scanned PDFs behind an explicit opt-in dependency group.
- source-page citation highlighting.
- OpenTelemetry or Prometheus-style observability.
- managed deployment path for cloud or client infrastructure.

These are deliberately additive. The current system remains useful as a local
demo and testable reference implementation without requiring those services.

## Verification Status

The current build has been verified with:

- full lint
- full typecheck
- full default offline test suite
- offline eval harness
- live OpenAI smoke tests
- focused hardening tests
- Docker and container profile checks

Recent default verification passed with:

- 263 selected default tests
- 5 deselected optional tests
- eval metrics at 1.0 for retrieval, citation, quote verification, refusal,
  answer safety, warning recall, and audit completeness

## Summary

RegLens is a practical AI engineering project because it demonstrates the
complete lifecycle of an applied AI product:

- understand a high-stakes user problem
- design for trust and auditability
- build a deterministic local vertical slice
- integrate live AI providers safely
- validate with tests and evals
- expose useful APIs and UI
- add operational controls
- document the product for future agents and stakeholders

For a Forward Deployed Engineer role, this project shows more than the ability
to call an LLM API. It shows the ability to turn AI into a reliable, testable,
client-ready system that addresses a real business problem.
