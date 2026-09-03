# LLM-Powered Regulatory & Compliance RAG System

Detailed implementation plan optimized for AI coding agents.

Date: 2026-08-19

## Optimization From The Source Project Plan

This version combines two complementary plans:

- Keep from the agent-first plan: fake-mode vertical slice, swappable provider interfaces, deterministic fixtures, endpoint contracts, explicit test gates, and parallel agent prompts.
- Add from the source project plan: production-grade document extraction, query routing, scope filtering before scoring, token budget management, caching, local model fallbacks, quote/span verification, hash-chained audit logs, streaming/document-management options, stricter eval gates, and cost/latency targets.

Design decisions for best results:

- Build the fake-mode vertical slice first. This lets agents develop ingestion, retrieval, generation, citations, audit, and evals without waiting on API keys or cloud services.
- Use direct typed interfaces over LangChain for the core path. LangChain can be added later for experiments, but the audit-critical path should stay explicit and easy to test.
- Use Qdrant as the primary vector store for the portfolio build because it is open-source and self-hostable. Keep Pinecone as an adapter option, not the default.
- Use SQLite for the first local slice, then PostgreSQL for production-style metadata, audit, full-text search, and hash-chain durability.
- Treat citation verification and abstention as product features, not polish. A retrieved-but-uncited answer is a failing response.

## 0. Agent Quick Start

Build a "RegLens" for financial regulation. The system ingests one regulatory rulebook, chunks it into auditable sections, embeds chunks, indexes them in Qdrant, retrieves relevant evidence with dense plus keyword search, reranks results with a cross-encoder, and generates grounded answers with citations.

Primary stack:

- Python 3.11+
- FastAPI
- Qdrant
- OpenAI API for generation and embeddings
- Sentence Transformers cross-encoder for reranking
- PostgreSQL or SQLite for metadata and audit logs; SQLite is acceptable for MVP
- Redis or local cache for embedding/query-result caching; optional for MVP
- File-system or object-storage abstraction for raw source documents
- Optional local embedding and LLM providers for sensitive-data demos
- pytest, ruff, mypy or pyright
- Docker Compose for local Qdrant and API

The project must be built so it can run in three modes:

- `mock`: no network calls; deterministic fake embeddings and fake LLM responses for tests
- `local`: Qdrant in Docker, OpenAI optional, local embedding/LLM/reranker optional
- `real`: Qdrant plus OpenAI plus real reranking

Do not require OpenAI credentials for unit tests or CI. Any agent who introduces a required live API key for normal tests has broken the implementation contract.

First build target:

- A complete fake-mode demo that ingests a synthetic rulebook, retrieves evidence, generates a cited answer, refuses unsupported questions, writes an audit record, and passes evals.

Second build target:

- Swap in Qdrant, OpenAI embeddings/generation, optional cross-encoder reranker, PostgreSQL, and hash-chain audit verification without changing API contracts.

## 1. Product Goal

Financial institutions must understand complex, changing rules. This application lets a compliance analyst ask natural-language questions against a specific regulatory rulebook and receive:

- a concise answer
- cited source sections
- quoted supporting snippets
- confidence and retrieval diagnostics
- warnings when evidence is weak or missing
- an audit trail of query, retrieved chunks, answer, model metadata, and timestamps

The core product promise is not "chat with regulations." The promise is "answer only from retrieved regulatory evidence and make every claim traceable."

## 2. Target User

Primary user:

- Compliance analyst at a broker-dealer, asset manager, fintech, bank, or consulting firm

Secondary users:

- Customer-facing implementation engineer demonstrating applied AI deployment
- Model risk, legal, or audit stakeholder reviewing traceability
- Engineering reviewer evaluating reliability, tests, and architecture

User expectations:

- They can inspect exact rule references.
- They can tell when the system does not know.
- They can export or copy the cited answer.
- They can reproduce prior answers through audit logs.
- They never see uncited legal-sounding assertions presented as fact.

## 3. Regulatory Corpus Choice

The implementation must be source-agnostic, but the MVP should start with one corpus.

Recommended MVP corpus:

- FINRA rules if the implementation agent wants simpler public web content and strong section numbering.

Alternative:

- FCA Handbook if the implementation agent wants a UK-focused corpus with more complex handbook structure.

Corpus adapter requirements:

- Every document unit must have a stable `source_id`.
- Every section must have a human-readable citation label.
- Every chunk must map back to source URL, rulebook name, section ID, heading, effective date if available, and character offsets where possible.
- Ingestion must be repeatable. Re-running ingestion for the same corpus version should not create duplicate chunks.

MVP can support only one corpus adapter, but the code must expose a `CorpusLoader` interface so additional rulebooks can be added later.

## 4. Functional Requirements

### 4.1 Ingestion

The system must:

- Load raw regulatory source content from local files or a configured URL fetcher.
- Normalize HTML, PDF text, or Markdown into structured `DocumentSection` records.
- Preserve raw source files or source snapshots for audit replay.
- Preserve hierarchical headings and rule numbers.
- Extract metadata such as document title, section number, publication/effective date, page number when available, and source version.
- Preserve tables as Markdown or structured text blocks instead of dropping them.
- Split sections into chunks with overlap.
- Store chunks, metadata, and embeddings.
- Support idempotent re-ingestion by corpus version.
- Produce an ingestion report with document counts, chunk counts, skipped sections, errors, and embedding usage.

MVP ingestion input formats:

- Markdown
- HTML
- plain text

Recommended hardening input formats:

- PDF text extraction with `pymupdf` or `pypdf`
- table extraction for regulatory schedules and threshold tables

Stretch input formats:

- PDF with layout-aware extraction if basic PDF parsing loses hierarchy
- OCR fallback for scanned PDFs using Tesseract
- crawl/sitemap ingestion
- version diff ingestion

### 4.2 Retrieval

The system must:

- Convert the user query into an embedding.
- Route exact citation queries, broad conceptual queries, and out-of-scope queries through explicit query-router logic.
- Apply corpus, version, jurisdiction, date, and source-scope filters before scoring whenever filters are supplied.
- Run dense vector search against Qdrant.
- Run keyword search using BM25 or SQLite/Postgres full-text search.
- Merge dense and keyword candidates.
- Rerank merged candidates with a cross-encoder.
- Enforce a token budget before sending evidence to the LLM.
- Return top evidence chunks with metadata and scores.
- Expose retrieval diagnostics for debugging and evaluation.

Expected default retrieval pipeline:

1. Query normalization
2. Query routing and scope-filter construction
3. Dense search top 50 to 100
4. Keyword search top 30 to 50
5. Candidate fusion using Reciprocal Rank Fusion
6. Cross-encoder rerank top 25 to 30
7. Evidence selection top 5 to 10 chunks
8. Neighbor expansion by section when selected chunks are too narrow
9. Token budget trimming with diagnostics

### 4.3 Generation

The system must:

- Generate an answer using only retrieved context.
- Include citations inline or as a citation list.
- Refuse to answer when retrieved evidence is insufficient.
- Abstain before calling the LLM if retrieval evidence is below the minimum threshold.
- Separate direct regulatory answer from caveats.
- Avoid legal advice language.
- Return structured JSON from the LLM adapter before rendering to API response.
- Verify every cited claim against retrieved evidence IDs.
- Verify quoted snippets against exact source text or recorded chunk spans.
- Drop or refuse unverifiable claims rather than serving them.

Required answer behavior:

- If evidence supports an answer: answer with citations.
- If evidence is ambiguous: say what the evidence suggests and what is unresolved.
- If evidence is missing: say the rulebook evidence was not found and suggest query refinements.
- If the user asks outside the corpus: explicitly say the system only answers from the ingested corpus.
- If the answer contains a claim whose citation cannot be verified: retry once, then return a safe fallback with evidence only.

### 4.4 API

FastAPI must expose:

- `GET /health`
- `GET /ready`
- `POST /admin/ingest`
- `GET /admin/ingest/{job_id}`
- `POST /documents` for source upload or registration; can wrap `/admin/ingest` in MVP
- `DELETE /documents/{source_id}` for removal or deactivation; production hardening
- `POST /query`
- `POST /retrieve`
- `POST /chat` as a streaming-compatible alias for `/query`; optional in MVP
- `GET /sources`
- `GET /sources/{source_id}`
- `GET /audit/queries`
- `GET /audit/queries/{query_id}`
- `GET /audit/verify` for hash-chain verification once hash-chain audit is enabled

`/retrieve` exists so agents can test retrieval separately from generation.

### 4.5 UI

MVP can be API-only, but a minimal web UI is strongly recommended.

UI must support:

- question input
- answer display
- citation list
- evidence snippets
- retrieval score details collapsible by default
- warning banner for low confidence or insufficient evidence
- source filter if multiple corpora are ingested

Use a restrained dashboard-style layout. This is a compliance tool, not a marketing page.

### 4.6 Evaluation

The project must include an eval harness that can be run without live OpenAI calls.

Required eval dimensions:

- retrieval recall at `k`
- retrieval MRR at `k`
- citation precision
- exact quote/span verification rate
- answer groundedness
- refusal accuracy
- latency budget
- cost per query estimate when using live providers
- deterministic regression tests over a small fixture corpus

Minimum eval fixture:

- 8 to 12 small synthetic regulatory sections
- 15 to 25 questions
- expected supporting section IDs for each question
- expected behavior class: answerable, ambiguous, insufficient evidence, out-of-scope

Minimum quality gates for the portfolio-ready build:

- retrieval recall@10 >= 0.85 on the fixture/eval set
- citation exact-span verification >= 0.95
- refusal accuracy >= 0.90
- audit completeness = 1 audit record per served query
- hallucination/unsupported-claim rate < 0.02 on the eval set

## 5. Non-Functional Requirements

Reliability:

- No uncaught exceptions from malformed documents or empty queries.
- Ingestion should continue past one failed document and report the failure.
- Query responses should include clear error messages without leaking secrets.

Security:

- Never expose API keys in frontend code, logs, audit records, or error responses.
- Load secrets only from environment variables or a server-side secret manager.
- Add request size limits for ingestion and query endpoints.
- Validate all incoming request bodies with Pydantic.
- Add rate limiting and API-key authentication before any hosted demo with public access.
- Keep CORS restrictive by default.

Compliance and audit:

- Store query text, selected evidence chunk IDs, answer, citation IDs, model names, latency, and timestamps.
- Store prompt template version.
- Store corpus version.
- Store retrieval configuration.
- Allow replaying retrieval for a historical query against the same corpus version when possible.
- Store previous-hash and record-hash values when hash-chain audit is enabled.
- Store exact quote spans or snippet hashes used for citation verification.

Performance targets for MVP:

- Query response under 3 seconds for the fixture corpus and under 8 seconds for a corpus up to 10,000 chunks on a laptop.
- Retrieval-only response under 2 seconds after embeddings are available.
- Ingestion should batch embeddings.
- No single embedding request should exceed provider token or batch limits.
- Track token usage and estimated cost for live provider calls.
- Target cost per query below $0.01 for the default demo configuration.

Data sovereignty:

- Keep Qdrant self-hosted by default.
- Provide local embedding and local LLM adapter seams for sensitive-data demonstrations.
- Do not send raw internal policy documents to a hosted provider unless `real` mode is explicitly configured.

Maintainability:

- Provider interfaces must be swappable.
- Business logic must be testable without FastAPI.
- Chunking, retrieval, reranking, and generation must be separate modules.
- Production-hardening features such as Redis, PostgreSQL, auth, streaming, and OCR must be additive rather than blocking the MVP vertical slice.

## 6. Architecture

### 6.1 Logical Components

Components:

- API service: FastAPI app and request/response schemas
- Query router: classifies exact-citation, semantic, multi-hop, ambiguous, and out-of-scope queries
- Corpus loader: fetches and parses regulatory documents
- Normalizer: converts raw documents into sections
- Chunker: creates citation-preserving chunks
- Embedding provider: OpenAI implementation plus deterministic fake implementation
- Embedding cache: content-hash based cache to avoid regenerating unchanged embeddings
- Vector store: Qdrant implementation plus in-memory fake implementation
- Keyword index: BM25 or SQLite FTS
- Retriever: hybrid search, fusion, and neighbor expansion
- Reranker: cross-encoder implementation plus no-op/fake reranker
- Answer generator: OpenAI implementation plus deterministic fake implementation
- Citation verifier: validates answer citations are backed by selected evidence
- Quote verifier: validates quoted spans or snippet hashes against source chunks
- Audit store: query and ingestion audit persistence
- Hash-chain audit verifier: detects audit record edits, deletions, or reordering
- Document storage: file-system abstraction for raw regulatory documents and source snapshots
- Cache layer: optional Redis/local cache for embeddings and repeated query results
- Eval runner: command-line scripts and reports

### 6.2 Suggested Repository Structure

Create this structure unless a future agent has a strong reason to adapt it:

```text
.
├── README.md
├── AGENT_IMPLEMENTATION_PLAN.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── Makefile
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_admin.py
│   │   ├── routes_documents.py
│   │   ├── routes_query.py
│   │   ├── routes_audit.py
│   │   └── routes_sources.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── errors.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── scoring.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── loaders.py
│   │   ├── normalizers.py
│   │   ├── extractors.py
│   │   ├── chunking.py
│   │   ├── pipeline.py
│   │   └── jobs.py
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── query_router.py
│   │   ├── embeddings.py
│   │   ├── embedding_cache.py
│   │   ├── keyword.py
│   │   ├── vector_store.py
│   │   ├── fusion.py
│   │   ├── rerank.py
│   │   └── service.py
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── prompts.py
│   │   ├── llm.py
│   │   ├── citations.py
│   │   ├── quote_verifier.py
│   │   └── service.py
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── chain.py
│   │   └── verifier.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── repositories.py
│   │   └── migrations/
│   ├── storage/
│   │   ├── __init__.py
│   │   └── documents.py
│   └── evals/
│       ├── __init__.py
│       ├── runner.py
│       ├── metrics.py
│       └── fixtures/
│           ├── synthetic_rulebook.md
│           └── questions.yaml
├── scripts/
│   ├── ingest.py
│   ├── query.py
│   ├── run_evals.py
│   └── seed_fixture.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/
    ├── architecture.md
    ├── api.md
    ├── eval-methodology.md
    └── demo-script.md
```

### 6.3 Data Flow

Ingestion:

```text
source files or URLs
  -> CorpusLoader
  -> raw source snapshot storage
  -> Normalizer
  -> DocumentSection[]
  -> Chunker
  -> Chunk[]
  -> embedding cache lookup by chunk hash
  -> EmbeddingProvider.embed_batch
  -> Qdrant upsert
  -> Keyword index upsert
  -> Metadata store
  -> Ingestion report
```

Query:

```text
user question
  -> validate request
  -> query router
  -> build scope filters before scoring
  -> embed query
  -> dense search
  -> keyword search
  -> candidate fusion
  -> cross-encoder rerank
  -> evidence selection
  -> token budget gate
  -> prompt assembly
  -> LLM structured answer
  -> citation verifier
  -> quote/span verifier
  -> audit log
  -> hash-chain update
  -> API response
```

## 7. Domain Models

Use Pydantic models for API schemas and dataclasses or Pydantic models for internal domain objects.

### 7.1 `DocumentSource`

Fields:

- `source_id: str`
- `corpus_id: str`
- `corpus_name: str`
- `version: str`
- `title: str`
- `url: str | None`
- `raw_storage_uri: str | None`
- `retrieved_at: datetime | None`
- `checksum: str`
- `metadata: dict[str, Any]`

### 7.2 `DocumentSection`

Fields:

- `section_id: str`
- `source_id: str`
- `corpus_id: str`
- `citation_label: str`
- `title: str`
- `heading_path: list[str]`
- `text: str`
- `url: str | None`
- `effective_date: date | None`
- `page_number: int | None`
- `start_char: int | None`
- `end_char: int | None`
- `metadata: dict[str, Any]`

Example `citation_label`:

- `FINRA Rule 2210(d)(1)(A)`
- `FCA COBS 4.2.1R`

### 7.3 `Chunk`

Fields:

- `chunk_id: str`
- `section_id: str`
- `source_id: str`
- `corpus_id: str`
- `corpus_version: str`
- `citation_label: str`
- `title: str`
- `heading_path: list[str]`
- `text: str`
- `token_count: int`
- `chunk_index: int`
- `section_chunk_count: int`
- `char_start: int | None`
- `char_end: int | None`
- `page_number: int | None`
- `source_checksum: str`
- `url: str | None`
- `metadata: dict[str, Any]`

`chunk_id` should be deterministic:

```text
sha256(corpus_id + corpus_version + section_id + chunk_index + normalized_text)
```

### 7.4 `RetrievalCandidate`

Fields:

- `chunk: Chunk`
- `dense_rank: int | None`
- `dense_score: float | None`
- `keyword_rank: int | None`
- `keyword_score: float | None`
- `fusion_score: float`
- `rerank_score: float | None`
- `final_rank: int | None`

### 7.5 `Evidence`

Fields:

- `evidence_id: str`
- `chunk_id: str`
- `citation_label: str`
- `url: str | None`
- `title: str`
- `snippet: str`
- `score: float`
- `source_span: dict[str, int] | None`

### 7.6 `Answer`

Fields:

- `query_id: str`
- `answer: str`
- `citations: list[Citation]`
- `evidence: list[Evidence]`
- `confidence: Literal["high", "medium", "low", "insufficient_evidence"]`
- `warnings: list[str]`
- `retrieval_diagnostics: RetrievalDiagnostics`
- `model_info: ModelInfo`
- `created_at: datetime`

### 7.7 `Citation`

Fields:

- `citation_id: str`
- `citation_label: str`
- `chunk_id: str`
- `source_id: str`
- `url: str | None`
- `supports_claim: str`
- `quoted_text: str | None`
- `source_span: dict[str, int] | None`
- `verification_status: Literal["verified", "unverified", "not_required"]`

### 7.8 `AuditHash`

Fields:

- `query_id: str`
- `payload_hash: str`
- `previous_record_hash: str | None`
- `record_hash: str`
- `chain_index: int`
- `created_at: datetime`

## 8. API Contract

### 8.1 `GET /health`

Purpose:

- Fast liveness check.

Response:

```json
{
  "status": "ok",
  "service": "reglens",
  "version": "0.1.0"
}
```

### 8.2 `GET /ready`

Purpose:

- Checks Qdrant, metadata DB, and required configuration.

Response:

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "vector_store": "ok",
    "embedding_provider": "configured",
    "llm_provider": "configured"
  }
}
```

### 8.3 `POST /admin/ingest`

Request:

```json
{
  "corpus_id": "finra",
  "corpus_name": "FINRA Rules",
  "version": "2026-08-19",
  "input_type": "markdown",
  "input_path": "data/raw/finra_rules.md",
  "force": false
}
```

Response:

```json
{
  "job_id": "ing_01h...",
  "status": "queued"
}
```

MVP can execute synchronously and still return a completed job record. If implemented synchronously, keep the same shape:

```json
{
  "job_id": "ing_01h...",
  "status": "completed",
  "report": {
    "sources": 1,
    "sections": 42,
    "chunks": 128,
    "errors": []
  }
}
```

### 8.4 `GET /admin/ingest/{job_id}`

Response:

```json
{
  "job_id": "ing_01h...",
  "status": "completed",
  "started_at": "2026-08-19T14:00:00Z",
  "finished_at": "2026-08-19T14:01:42Z",
  "report": {
    "sources": 1,
    "sections": 42,
    "chunks": 128,
    "embedded_chunks": 128,
    "skipped_chunks": 0,
    "errors": []
  }
}
```

### 8.5 `POST /retrieve`

Request:

```json
{
  "question": "What are the supervision requirements for retail communications?",
  "corpus_id": "finra",
  "top_k": 8,
  "filters": {
    "version": "2026-08-19"
  }
}
```

Response:

```json
{
  "query_id": "qry_01h...",
  "question": "What are the supervision requirements for retail communications?",
  "evidence": [
    {
      "evidence_id": "E1",
      "chunk_id": "chk_...",
      "citation_label": "FINRA Rule 2210(b)(1)",
      "title": "Communications with the Public",
      "snippet": "Each member must establish written procedures...",
      "url": "https://example.test/rules/2210",
      "score": 0.92
    }
  ],
  "diagnostics": {
    "dense_candidates": 50,
    "keyword_candidates": 50,
    "fused_candidates": 73,
    "reranked_candidates": 25,
    "latency_ms": 842
  }
}
```

### 8.6 `POST /query`

Request:

```json
{
  "question": "What are the supervision requirements for retail communications?",
  "corpus_id": "finra",
  "top_k": 8,
  "include_diagnostics": true
}
```

Response:

```json
{
  "query_id": "qry_01h...",
  "answer": "Members must establish written procedures for supervising retail communications and must approve certain communications before use. The specific approval and review requirements depend on the communication type and role of the approving principal.",
  "confidence": "high",
  "citations": [
    {
      "citation_id": "C1",
      "citation_label": "FINRA Rule 2210(b)(1)",
      "chunk_id": "chk_...",
      "source_id": "src_...",
      "url": "https://example.test/rules/2210",
      "supports_claim": "Written supervisory procedures requirement."
    }
  ],
  "evidence": [
    {
      "evidence_id": "E1",
      "chunk_id": "chk_...",
      "citation_label": "FINRA Rule 2210(b)(1)",
      "title": "Communications with the Public",
      "snippet": "Each member must establish written procedures...",
      "url": "https://example.test/rules/2210",
      "score": 0.92
    }
  ],
  "warnings": [],
  "retrieval_diagnostics": {
    "latency_ms": 842,
    "dense_candidates": 50,
    "keyword_candidates": 50,
    "fused_candidates": 73,
    "reranked_candidates": 25
  },
  "model_info": {
    "generation_model": "configured-model-name",
    "embedding_model": "configured-embedding-model-name",
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "prompt_version": "answer-v1"
  }
}
```

Insufficient evidence response:

```json
{
  "query_id": "qry_01h...",
  "answer": "I could not find enough support in the ingested rulebook to answer this question reliably.",
  "confidence": "insufficient_evidence",
  "citations": [],
  "evidence": [],
  "warnings": [
    "No retrieved section met the minimum evidence threshold."
  ]
}
```

### 8.7 `GET /sources`

Response:

```json
{
  "sources": [
    {
      "source_id": "src_...",
      "corpus_id": "finra",
      "corpus_name": "FINRA Rules",
      "version": "2026-08-19",
      "title": "FINRA Rule 2210",
      "url": "https://example.test/rules/2210",
      "section_count": 12,
      "chunk_count": 33
    }
  ]
}
```

### 8.8 `POST /documents`

Purpose:

- Register or upload a regulatory document and start ingestion.
- MVP may accept a local path or URL; production should support multipart upload and auth.

Request:

```json
{
  "corpus_id": "finra",
  "corpus_name": "FINRA Rules",
  "version": "2026-08-19",
  "source_type": "url",
  "uri": "https://example.test/rules/2210",
  "force": false
}
```

Response:

```json
{
  "source_id": "src_...",
  "ingestion_job_id": "ing_01h...",
  "status": "queued"
}
```

### 8.9 `GET /audit/verify`

Purpose:

- Verify hash-chain continuity for audit records.

Response:

```json
{
  "status": "valid",
  "checked_records": 128,
  "latest_record_hash": "sha256:..."
}
```

If verification fails, return the first broken chain index and affected query ID.

## 9. Configuration

Use environment variables loaded through Pydantic Settings.

Required variables:

```text
APP_ENV=local
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./reglens.db
DOCUMENT_STORAGE_PATH=./data/raw
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=regulatory_chunks
REDIS_URL=
OPENAI_API_KEY=
OPENAI_GENERATION_MODEL=gpt-5.6-luna
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
USE_FAKE_EMBEDDINGS=false
USE_FAKE_LLM=false
USE_FAKE_RERANKER=false
USE_LOCAL_EMBEDDINGS=false
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=llama3.1
MAX_QUERY_CHARS=2000
DEFAULT_TOP_K=8
DEFAULT_DENSE_TOP_K=100
DEFAULT_KEYWORD_TOP_K=50
DEFAULT_RERANK_TOP_N=30
MAX_EVIDENCE_TOKENS=6000
MIN_RERANK_SCORE=
ENABLE_HASH_CHAIN_AUDIT=true
ENABLE_STREAMING=false
QUERY_RESULT_CACHE_TTL_SECONDS=0
```

Important:

- Keep model names configurable.
- Do not hard-code API keys.
- Do not log API keys.
- Unit tests should set `USE_FAKE_EMBEDDINGS=true`, `USE_FAKE_LLM=true`, and `USE_FAKE_RERANKER=true`.
- Treat Redis, local LLM, OCR, streaming, and hash-chain audit as configurable features with safe fallbacks.

## 10. Dependencies

Recommended Python dependencies:

```text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
openai
qdrant-client
sentence-transformers
rank-bm25
beautifulsoup4
lxml
markdownify
pymupdf
pypdf
tiktoken
sqlalchemy
alembic
httpx
tenacity
python-dotenv
structlog
typer
pyyaml
redis
cachetools
pytest
pytest-asyncio
pytest-cov
respx
ruff
mypy
```

Use `uv` or Poetry if preferred, but keep setup commands documented in `README.md`.

Optional hardening dependencies:

```text
pytesseract
camelot-py
pdfplumber
slowapi
psycopg[binary]
pgvector
streamlit
playwright
```

## 11. Implementation Phases

Each phase should end with passing tests and a short note in `docs/implementation-log.md`.

Effort guidance:

- Agent-first MVP vertical slice: 60 to 90 focused engineering hours.
- Portfolio-ready build with Qdrant, OpenAI, cross-encoder, audit verification, evals, and UI: 120 to 180 hours.
- Production-hardening track with PostgreSQL, Redis, auth, streaming, OCR/table extraction, deployment, and cost monitoring: 200 to 280 hours.

Agents should optimize for the MVP vertical slice first, then add production-hardening work behind feature flags.

### Phase 1: Project Skeleton and Development Contract

Goal:

- Create a runnable, testable Python project with FastAPI, config, basic health endpoints, Docker Compose, and CI-ready commands.

Agent assignment:

- Agent A: backend skeleton and developer tooling.

Tasks:

- Create `pyproject.toml`.
- Configure ruff and mypy.
- Create `app/main.py` with FastAPI app factory.
- Add `GET /health`.
- Add `GET /ready` with stub checks.
- Add `.env.example`.
- Add `docker-compose.yml` with Qdrant.
- Add `Makefile` commands:
  - `make install`
  - `make lint`
  - `make typecheck`
  - `make test`
  - `make run`
  - `make qdrant-up`
- Add `README.md` with local setup.

Acceptance criteria:

- `make test` passes.
- `make lint` passes.
- `make typecheck` passes or has documented MVP exceptions.
- `uvicorn app.main:app --reload` starts.
- `GET /health` returns `200`.

Tests:

- `tests/unit/test_config.py`
- `tests/integration/test_health.py`

Definition of done:

- No live OpenAI or Qdrant required for unit tests.
- Qdrant readiness check is graceful if Qdrant is not running.

### Phase 2: Domain Models and Persistence

Goal:

- Establish stable domain objects and metadata/audit persistence.

Agent assignment:

- Agent B: domain and database.

Tasks:

- Implement domain models in `app/domain/models.py`.
- Implement SQLAlchemy models and repositories.
- Add migrations or simple `create_all` bootstrap for MVP.
- Store sources, sections, chunks, ingestion jobs, query audits.
- Add deterministic ID helpers.
- Add checksum helper for source content.

Database tables:

- `document_sources`
- `document_sections`
- `chunks`
- `ingestion_jobs`
- `query_audits`
- `query_evidence`

Acceptance criteria:

- Can insert and fetch source, section, chunk.
- Can create ingestion job and update status.
- Can create query audit with evidence IDs.
- Deterministic IDs are stable across runs.

Tests:

- `tests/unit/test_domain_models.py`
- `tests/unit/test_id_generation.py`
- `tests/integration/test_repositories.py`

Definition of done:

- Repository methods are typed.
- Tests use temporary SQLite DB.
- No Qdrant or OpenAI needed.

### Phase 3: Corpus Loading and Normalization

Goal:

- Convert raw rulebook text into clean, citation-preserving sections.

Agent assignment:

- Agent C: ingestion parser.

Tasks:

- Define `CorpusLoader` protocol.
- Implement `MarkdownCorpusLoader`.
- Implement `HtmlCorpusLoader`.
- Implement `PlainTextCorpusLoader`.
- Implement PDF extraction behind a separate `PdfExtractor` interface using `pymupdf` or `pypdf`; mark as recommended hardening if no real PDF corpus is selected.
- Implement text normalization:
  - remove navigation noise
  - preserve heading hierarchy
  - normalize whitespace
  - preserve rule numbers
- Implement metadata extraction for title, rule/section number, publication or effective date, page number when available, and source URL.
- Preserve cross-references as text and metadata hints; do not attempt graph reasoning in MVP.
- Preserve tables as Markdown blocks or structured text with clear row/column labels.
- Implement section extraction from Markdown headings.
- Implement synthetic FINRA-like fixture corpus.
- Generate `DocumentSection` records.
- Validate empty or malformed input gracefully.

Input fixture example:

```markdown
# FINRA Synthetic Rulebook

## Rule 1000. General Standards

### Rule 1000(a). Written Policies

Members must maintain written policies reasonably designed to supervise regulated activity.
```

Acceptance criteria:

- Loader returns stable section IDs and citation labels.
- Heading paths are preserved.
- Source version, checksum, and raw storage URI are recorded.
- Malformed files produce structured errors, not crashes.
- Section text is non-empty and normalized.
- Tables are not silently discarded when present.

Tests:

- `tests/unit/test_markdown_loader.py`
- `tests/unit/test_html_normalizer.py`
- `tests/unit/test_section_extraction.py`
- `tests/unit/test_metadata_extraction.py`
- `tests/unit/test_table_preservation.py`
- `tests/integration/test_pdf_extractor_optional.py`

Definition of done:

- Fixture corpus has at least 8 sections.
- Each section has citation label, title, text, source ID.
- Optional PDF tests are skipped unless PDF dependencies and fixtures are available.

### Phase 4: Chunking

Goal:

- Split sections into chunks that preserve citations and minimize retrieval noise.

Agent assignment:

- Agent C or D: chunking.

Tasks:

- Implement tokenizer abstraction.
- Use `tiktoken` if available; fallback to approximate token counting in tests.
- Implement configurable chunk size and overlap:
  - default chunk size: 700 tokens
  - default overlap: 120 tokens
- Keep short sections as single chunks.
- Prefix chunk text internally with citation and heading context for embedding:
  - `FINRA Rule 1000(a). Written Policies\n...`
- Store original chunk text separately if needed.
- Implement deterministic chunk IDs.

Acceptance criteria:

- Chunking is deterministic.
- Chunks never exceed configured token budget except unavoidable long tokens.
- Adjacent chunks overlap.
- Citation metadata survives chunking.

Tests:

- `tests/unit/test_chunking.py`
- `tests/unit/test_chunk_ids.py`

Definition of done:

- Chunker handles empty sections, short sections, and long sections.
- No network required.

### Phase 5: Embedding Provider

Goal:

- Add swappable embedding providers with deterministic test behavior.

Agent assignment:

- Agent D: embeddings.

Tasks:

- Define `EmbeddingProvider` protocol:

```python
class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

- Implement `FakeEmbeddingProvider`:
  - deterministic
  - fixed dimension
  - enough lexical signal for tests
- Implement `OpenAIEmbeddingProvider`:
  - batches inputs
  - default batch size configurable, target 100 to 200 chunks when token limits allow
  - retries transient errors
  - respects max batch size and token constraints
  - logs usage without logging input text at debug by default
- Implement optional `LocalSentenceTransformerEmbeddingProvider`.
- Implement embedding cache keyed by provider name, dimensions, normalized text hash, and corpus version.
- Add provider factory based on config.

Acceptance criteria:

- Unit tests use fake provider.
- Integration test can be skipped unless `OPENAI_API_KEY` is set.
- OpenAI errors are wrapped in domain-specific exceptions.
- Empty input is rejected before API call.
- Re-ingesting unchanged chunks reuses cached embeddings when cache is enabled.
- Local embedding provider can be selected without changing ingestion code.

Tests:

- `tests/unit/test_fake_embeddings.py`
- `tests/unit/test_embedding_provider_factory.py`
- `tests/unit/test_embedding_cache.py`
- `tests/integration/test_openai_embeddings_optional.py`
- `tests/integration/test_local_embeddings_optional.py`

Definition of done:

- No OpenAI calls during normal `make test`.
- Provider exposes model name and dimensions for audit logs.
- Cache hits, misses, and estimated token savings are logged without storing secrets.

### Phase 6: Qdrant Vector Store

Goal:

- Store and search chunk embeddings.

Agent assignment:

- Agent E: vector storage.

Tasks:

- Define `VectorStore` protocol:

```python
class VectorStore(Protocol):
    async def ensure_collection(self, dimension: int) -> None: ...
    async def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None: ...
    async def search(self, query_embedding: list[float], filters: SearchFilters, top_k: int) -> list[VectorHit]: ...
    async def delete_by_corpus_version(self, corpus_id: str, version: str) -> None: ...
```

- Implement `InMemoryVectorStore` for tests.
- Implement `QdrantVectorStore`.
- Store chunk metadata payloads:
  - `chunk_id`
  - `section_id`
  - `source_id`
  - `corpus_id`
  - `corpus_version`
  - `citation_label`
  - `title`
  - `url`
- Use cosine distance.
- Add collection creation and dimension checks.

Acceptance criteria:

- In-memory vector search works in tests.
- Qdrant integration test passes when Qdrant is running.
- Dimension mismatch returns clear error.
- Re-ingestion updates existing chunk IDs.

Tests:

- `tests/unit/test_in_memory_vector_store.py`
- `tests/integration/test_qdrant_vector_store.py`

Definition of done:

- Qdrant tests are marked integration and can be skipped locally if service unavailable.

### Phase 7: Keyword Index

Goal:

- Add keyword retrieval for exact rule terms, citations, and regulatory phrases.

Agent assignment:

- Agent F: keyword retrieval.

Tasks:

- Define `KeywordIndex` protocol.
- Implement BM25 index using `rank-bm25` for MVP.
- Tokenization must preserve:
  - rule numbers like `2210`
  - terms like `COBS`
  - paragraph markers like `(a)(1)`
- Add citation-label boosting.
- Add title/heading boosting.
- Store index in memory for MVP; rebuild on app start from metadata DB.
- Optional stretch: SQLite FTS5 or Postgres full-text search.

Acceptance criteria:

- Keyword search finds exact citation references.
- Keyword search finds phrases that dense search may miss.
- Index can rebuild from stored chunks.

Tests:

- `tests/unit/test_keyword_tokenizer.py`
- `tests/unit/test_bm25_index.py`
- `tests/integration/test_keyword_rebuild.py`

Definition of done:

- Query `Rule 1000(a)` returns the matching synthetic section in top 3.

### Phase 8: Hybrid Retrieval and Fusion

Goal:

- Combine dense and keyword retrieval robustly.

Agent assignment:

- Agent G: retrieval service.

Tasks:

- Implement `QueryRouter`:
  - exact citation lookup
  - semantic policy question
  - multi-section synthesis
  - ambiguous query
  - out-of-scope query
- Implement scope filter construction for corpus ID, version, jurisdiction, date range, source IDs, and document type.
- Ensure scope filters are applied before dense and keyword scoring whenever the backing store supports pre-filtering.
- Implement Reciprocal Rank Fusion:

```text
rrf_score = sum(1 / (k + rank_i))
default k = 60
```

- Merge dense and keyword candidates by `chunk_id`.
- Preserve individual scores and ranks.
- Add search filters for corpus ID and version.
- Add retrieval diagnostics.
- Add minimum evidence threshold.
- Add token budget tracking:
  - count selected evidence tokens
  - trim lowest-value evidence before prompt assembly
  - expose trimming decisions in diagnostics
- Add neighbor expansion:
  - If top chunk belongs to a section with adjacent chunks, include previous/next chunk when useful.
  - Do not exceed prompt token budget.

Acceptance criteria:

- Retrieval service returns ranked `RetrievalCandidate` objects.
- Diagnostics include counts and latency.
- Works with fake vector store and fake keyword index.
- Query with no hits returns empty evidence cleanly.
- Out-of-scope queries can abstain before embedding/generation when confidently classified.
- Exact citation queries return the matching citation in top 3 when it exists.
- Retrieval never returns chunks outside explicit corpus/version filters.
- Evidence sent to generation stays within `MAX_EVIDENCE_TOKENS`.

Tests:

- `tests/unit/test_rrf.py`
- `tests/unit/test_query_router.py`
- `tests/unit/test_scope_filters.py`
- `tests/unit/test_candidate_merge.py`
- `tests/unit/test_token_budget.py`
- `tests/unit/test_retrieval_service.py`
- `tests/integration/test_retrieve_endpoint.py`

Definition of done:

- `/retrieve` endpoint can run end-to-end on synthetic corpus without OpenAI.

### Phase 9: Cross-Encoder Reranking

Goal:

- Rerank fused candidates for better precision.

Agent assignment:

- Agent H: reranking.

Tasks:

- Define `Reranker` protocol:

```python
class Reranker(Protocol):
    async def rerank(self, query: str, candidates: list[RetrievalCandidate], top_n: int) -> list[RetrievalCandidate]: ...
```

- Implement `NoOpReranker`.
- Implement `FakeReranker` for deterministic tests.
- Implement `SentenceTransformersCrossEncoderReranker`.
- Default model: `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- Batch candidate pairs.
- Gracefully fall back to no-op reranker if configured.

Acceptance criteria:

- Tests do not download models unless explicitly enabled.
- Reranking updates `rerank_score` and `final_rank`.
- Reranker does not mutate input unexpectedly unless documented.

Tests:

- `tests/unit/test_fake_reranker.py`
- `tests/unit/test_rerank_ordering.py`
- `tests/integration/test_cross_encoder_optional.py`

Definition of done:

- `/retrieve` includes rerank scores when real or fake reranker is enabled.

### Phase 10: Prompting and Answer Generation

Goal:

- Generate grounded, auditable answers using retrieved evidence.

Agent assignment:

- Agent I: generation and citations.

Tasks:

- Define `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    async def generate_answer(self, prompt: AnswerPrompt) -> LLMAnswer: ...
```

- Implement `FakeLLMProvider`.
- Implement `OpenAILLMProvider`.
- Use structured output with a strict schema when provider supports it.
- Implement prompt template `answer-v1`.
- Prompt must include:
  - role: compliance policy copilot
  - scope: answer only from evidence
  - no legal advice
  - cite every material claim
  - if insufficient evidence, refuse
  - evidence list with stable evidence IDs
- Implement citation verifier:
  - every citation in answer must map to provided evidence
  - no unknown citation IDs
  - if answer has claims but no citations, downgrade confidence or reject response
- Implement quote/span verifier:
  - cited quote text must appear in the retrieved chunk or match a recorded source span
  - citation source spans must map to the same `chunk_id`
  - unsupported claim citations are rejected
- Implement citation-abstention behavior:
  - weak retrieval abstains before LLM call
  - unverifiable generated claims are dropped or cause safe fallback
  - citations to chunks that were not retrieved are refused
- Add answer post-processing.

Prompt skeleton:

```text
You are RegLens for financial regulatory research.

Rules:
- Answer only from the evidence below.
- Do not use outside knowledge.
- Do not provide legal advice.
- Cite every material claim using evidence IDs like [E1].
- If the evidence is insufficient, say so.
- If evidence conflicts or is ambiguous, explain the ambiguity.

Question:
{question}

Evidence:
{evidence_blocks}

Return JSON with:
- answer
- confidence
- cited_evidence_ids
- warnings
```

Acceptance criteria:

- Fake LLM enables deterministic tests.
- OpenAI provider is optional in tests.
- Citation verifier catches fabricated citations.
- Quote verifier catches fabricated quotes and citations to non-retrieved chunks.
- Insufficient evidence returns safe response.
- Weak retrieval can return abstention without calling the LLM provider.

Tests:

- `tests/unit/test_prompt_assembly.py`
- `tests/unit/test_fake_llm.py`
- `tests/unit/test_citation_verifier.py`
- `tests/unit/test_quote_verifier.py`
- `tests/unit/test_citation_abstention.py`
- `tests/integration/test_query_endpoint_fake_llm.py`
- `tests/integration/test_openai_generation_optional.py`

Required high-risk tests:

- `test_fabricated_quote_is_rejected`
- `test_citation_to_a_chunk_not_retrieved_is_refused`
- `test_claim_whose_content_is_absent_from_its_quote_is_unsupported`
- `test_weak_retrieval_abstains_before_calling_model`
- `test_every_request_writes_one_audit_record`

Definition of done:

- `/query` works end-to-end on synthetic corpus with fake providers.
- `/query` answer includes citations for answerable fixture questions.
- `/query` never serves a non-refusal answer with unverified citation IDs.

### Phase 11: Ingestion Pipeline Endpoint and CLI

Goal:

- Wire loading, chunking, embedding, vector indexing, keyword indexing, and persistence.

Agent assignment:

- Agent J: ingestion orchestration.

Tasks:

- Implement `IngestionPipeline`.
- Add `scripts/ingest.py`.
- Add `POST /admin/ingest`.
- Add `GET /admin/ingest/{job_id}`.
- Persist ingestion job status.
- Add idempotency:
  - If same corpus/version/checksum already ingested and `force=false`, skip.
  - If `force=true`, delete old vectors and metadata for corpus/version first.
- Add ingestion report.
- Add partial failure reporting.

Acceptance criteria:

- Synthetic corpus can be ingested by CLI.
- Synthetic corpus can be ingested by API.
- Running ingestion twice does not duplicate chunks.
- Force re-ingestion replaces chunks.

Tests:

- `tests/integration/test_ingestion_pipeline.py`
- `tests/integration/test_ingest_endpoint.py`
- `tests/e2e/test_ingest_then_retrieve.py`

Definition of done:

- A new developer can run one command to seed the fixture corpus.

### Phase 12: Audit Logging

Goal:

- Make answers reproducible and inspectable.

Agent assignment:

- Agent B or K: audit trail.

Tasks:

- Log query request.
- Log retrieval config.
- Log selected evidence chunk IDs and scores.
- Log generated answer and citations.
- Log model names, prompt version, corpus version, latency.
- Compute canonical audit payload JSON.
- Add hash-chained audit fields:
  - `payload_hash = sha256(canonical_payload)`
  - `record_hash = sha256(previous_record_hash + payload_hash + created_at + query_id)`
  - `previous_record_hash` nullable only for the first record
- Implement chain verification that detects edited, deleted, or reordered records.
- Expose `GET /audit/queries`.
- Expose `GET /audit/queries/{query_id}`.
- Expose `GET /audit/verify`.
- Redact or omit sensitive data.

Acceptance criteria:

- Every `/query` call creates one audit record.
- Audit detail returns evidence and answer.
- Audit endpoints support pagination.
- Audit records do not include API keys or raw system prompts if configured to hide them.
- Hash-chain verification passes after normal query traffic.
- If a test mutates a stored audit payload, verification fails at the changed record.

Tests:

- `tests/integration/test_query_audit.py`
- `tests/integration/test_audit_endpoints.py`
- `tests/unit/test_audit_hash_chain.py`
- `tests/integration/test_audit_verify_endpoint.py`

Definition of done:

- Reviewer can inspect why an answer was produced.
- Reviewer can verify the audit chain has not been tampered with in the local database.

### Phase 13: Evaluation Harness

Goal:

- Quantify retrieval and grounded answer quality.

Agent assignment:

- Agent L: evals.

Tasks:

- Create `app/evals/fixtures/synthetic_rulebook.md`.
- Create `app/evals/fixtures/questions.yaml`.
- Implement `scripts/run_evals.py`.
- Metrics:
  - retrieval recall@3
  - retrieval recall@5
  - retrieval recall@10
  - MRR@5
  - MRR@10
  - citation precision
  - exact quote verification rate
  - refusal accuracy
  - answer contains required citation IDs
  - unsupported claim rate
  - mean latency
  - estimated cost per query for live runs
- Output JSON and Markdown report.
- Add regression thresholds.

Example `questions.yaml`:

```yaml
- id: q001
  question: What written policies must members maintain?
  expected_sections:
    - SYN-1000-a
  behavior: answerable
- id: q002
  question: What are the capital requirements?
  expected_sections: []
  behavior: insufficient_evidence
```

Acceptance criteria:

- Eval can run entirely with fake providers.
- Eval exits non-zero if quality thresholds fail.
- Eval report is human-readable.

Suggested thresholds for MVP:

- recall@5 >= 0.80 on fixture set
- refusal accuracy >= 0.90
- citation precision >= 0.90

Portfolio-ready thresholds:

- recall@10 >= 0.85
- MRR@10 >= 0.70
- exact quote/span verification >= 0.95
- unsupported claim rate < 0.02
- audit completeness = 1.00
- mean fixture latency < 3 seconds in fake/local mode
- estimated default live cost per query < $0.01

Tests:

- `tests/unit/test_eval_metrics.py`
- `tests/integration/test_eval_runner.py`

Definition of done:

- `make eval` runs and produces `reports/eval-latest.md`.

### Phase 14: Minimal UI

Goal:

- Provide a usable demo interface.

Agent assignment:

- Agent M: frontend.

Recommended options:

- Streamlit for the fastest useful MVP demo
- Server-rendered FastAPI templates for a lightweight no-build alternative
- React/Vite if agent wants richer UI

MVP screen:

- Top navigation with product name and corpus status
- Query panel
- Answer panel
- Citations panel
- Evidence snippets panel
- Source document panel with citation highlight support when source spans are available
- Diagnostics collapsible panel
- Optional document upload/register panel

UI behavior:

- Disable submit while request is in progress.
- Show low-confidence warning clearly.
- Clicking a citation scrolls to evidence.
- Evidence shows citation label, title, score, and URL.
- Do not hide citations behind hover-only UI.

Acceptance criteria:

- User can ask a question from browser.
- User can inspect evidence.
- UI handles loading, success, insufficient evidence, and error states.
- UI works against fake provider mode.

Tests:

- Backend template tests or frontend component tests.
- Optional Playwright smoke test:
  - load page
  - submit fixture question
  - see answer and citation

Definition of done:

- Demo can be run locally without live OpenAI if fixture corpus is seeded.

### Phase 15: Documentation and Demo

Goal:

- Make the project easy for reviewers and future agents to run and understand.

Agent assignment:

- Agent N: docs and final polish.

Tasks:

- Update `README.md`.
- Add architecture diagram in Mermaid.
- Add API docs.
- Add eval methodology.
- Add demo script.
- Add troubleshooting.
- Add known limitations.
- Add "how to add a new corpus adapter."

README must include:

- project purpose
- architecture overview
- setup commands
- fake mode workflow
- real OpenAI workflow
- ingest command
- query command
- eval command
- test command
- security notes

Acceptance criteria:

- A fresh agent can follow README and run fixture demo.
- Docs mention that answers are not legal advice.
- Docs explain how citations are generated and verified.

Tests:

- Manual command checklist in `docs/demo-script.md`.

Definition of done:

- Reviewer can evaluate the project in under 10 minutes.

## 12. Parallel Agent Work Plan

Use parallel agents only where interfaces are stable. The recommended sequence:

### Wave 1: Foundation

Can run in parallel:

- Agent A: project skeleton, config, health endpoints
- Agent B: domain models and persistence
- Agent C: fixture corpus, loaders, normalizers

Integration checkpoint:

- Domain models compile.
- Loader outputs `DocumentSection`.
- DB can persist sections and chunks.

### Wave 2: Indexing

Can run in parallel after Wave 1:

- Agent D: embeddings
- Agent E: vector store
- Agent F: keyword index
- Agent C/D: chunking

Integration checkpoint:

- Ingestion pipeline can chunk fixture corpus.
- Fake embeddings can be stored in in-memory vector store.
- Keyword index can search fixture chunks.

### Wave 3: Retrieval

Can run after Wave 2:

- Agent G: hybrid retrieval and `/retrieve`
- Agent H: reranker

Integration checkpoint:

- Fixture query returns expected section in top 5.
- `/retrieve` returns diagnostics.

### Wave 4: Generation and Audit

Can run after Wave 3:

- Agent I: prompt, LLM provider, citation verifier, `/query`
- Agent K: audit logging endpoints

Integration checkpoint:

- Fixture answer includes citation.
- Insufficient evidence fixture refuses.
- Audit record is created.

### Wave 5: Evaluation, UI, Docs

Can run after Wave 4:

- Agent L: eval harness
- Agent M: minimal UI
- Agent N: docs and demo polish

Integration checkpoint:

- `make test`, `make eval`, and local demo pass.

### Wave 6: Production Hardening

Can run after Wave 5 or in parallel with docs if interfaces are stable:

- Agent O: PostgreSQL migration, hash-chain persistence, and audit verification
- Agent P: Redis/local cache, cost tracking, and rate limiting
- Agent Q: PDF/table/OCR extraction and document upload flow
- Agent R: streaming `/chat`, auth, and deployment packaging

Integration checkpoint:

- Existing fake-mode tests still pass.
- Production features are behind config flags where appropriate.
- Demo path remains under 10 minutes for a reviewer.

## 13. Agent Task Prompt Templates

Use these prompts when delegating to coding agents.

### 13.1 Foundation Agent Prompt

```text
You are implementing Phase 1 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Create Python project skeleton, FastAPI app, config, health/ready endpoints, Docker Compose for Qdrant, Makefile, and README setup.

Constraints:
- Do not implement ingestion, retrieval, or LLM logic yet.
- Unit tests must not require Qdrant or OpenAI.
- Keep settings model typed and environment-driven.

Required tests:
- tests/unit/test_config.py
- tests/integration/test_health.py

Definition of done:
- make lint, make typecheck, and make test pass, or document any typecheck exception.
- uvicorn app.main:app --reload starts.
```

### 13.2 Ingestion Agent Prompt

```text
You are implementing Phases 3 and 4 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Implement corpus loader protocols, Markdown/plain-text loaders, HTML normalizer, optional PDF extractor, section extraction, chunking, deterministic IDs, metadata extraction, table preservation, and fixture corpus.

Constraints:
- Preserve citation labels and heading hierarchy.
- Record source version, source checksum, raw storage URI, and page number when available.
- Chunking must be deterministic.
- Do not call OpenAI or Qdrant.

Required tests:
- tests/unit/test_markdown_loader.py
- tests/unit/test_html_normalizer.py
- tests/unit/test_section_extraction.py
- tests/unit/test_metadata_extraction.py
- tests/unit/test_table_preservation.py
- tests/unit/test_chunking.py
- tests/unit/test_chunk_ids.py

Definition of done:
- Fixture corpus yields at least 8 sections.
- Each chunk maps to source_id, section_id, citation_label, corpus_id, and version.
- Optional PDF tests are skipped unless dependencies and fixtures are available.
```

### 13.3 Embedding and Vector Agent Prompt

```text
You are implementing Phases 5 and 6 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Implement EmbeddingProvider protocol, FakeEmbeddingProvider, optional OpenAIEmbeddingProvider, optional local SentenceTransformer provider, embedding cache, VectorStore protocol, InMemoryVectorStore, and QdrantVectorStore.

Constraints:
- Normal tests must use fake embeddings.
- Live OpenAI tests must be skipped unless OPENAI_API_KEY is present.
- Qdrant tests must be marked integration.
- Do not log secrets or raw API keys.
- Cache keys must include provider name, dimensions, normalized text hash, and corpus version.

Required tests:
- tests/unit/test_fake_embeddings.py
- tests/unit/test_embedding_provider_factory.py
- tests/unit/test_embedding_cache.py
- tests/unit/test_in_memory_vector_store.py
- tests/integration/test_qdrant_vector_store.py

Definition of done:
- In-memory vector store can upsert and search fixture chunks.
- Qdrant collection creation handles existing collection cleanly.
```

### 13.4 Retrieval Agent Prompt

```text
You are implementing Phases 7, 8, and 9 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Implement query router, keyword BM25 index, scope filters, token budget tracking, RRF fusion, retrieval service, reranker protocol, fake/no-op reranker, optional cross-encoder reranker, and /retrieve endpoint.

Constraints:
- Preserve dense, keyword, fusion, and rerank diagnostics.
- Apply corpus/version/source filters before scoring when possible.
- Do not send evidence beyond MAX_EVIDENCE_TOKENS to generation.
- Tests must not download model weights unless explicitly enabled.
- Retrieval must work with fixture corpus and fake embeddings.

Required tests:
- tests/unit/test_keyword_tokenizer.py
- tests/unit/test_bm25_index.py
- tests/unit/test_query_router.py
- tests/unit/test_scope_filters.py
- tests/unit/test_token_budget.py
- tests/unit/test_rrf.py
- tests/unit/test_candidate_merge.py
- tests/unit/test_retrieval_service.py
- tests/integration/test_retrieve_endpoint.py

Definition of done:
- Query for exact rule citation returns expected section in top 3.
- Fixture semantic query returns expected section in top 5.
```

### 13.5 Generation Agent Prompt

```text
You are implementing Phase 10 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Implement prompt assembly, LLMProvider protocol, fake LLM, optional OpenAI LLM, structured answer schema, citation verifier, quote/span verifier, citation-abstention behavior, and /query endpoint.

Constraints:
- Answer only from evidence.
- Every material claim must cite evidence IDs.
- Fabricated citation IDs must be rejected.
- Fabricated quotes and citations to non-retrieved chunks must be rejected.
- Weak retrieval should abstain before calling the LLM.
- Tests must run without OpenAI.

Required tests:
- tests/unit/test_prompt_assembly.py
- tests/unit/test_fake_llm.py
- tests/unit/test_citation_verifier.py
- tests/unit/test_quote_verifier.py
- tests/unit/test_citation_abstention.py
- tests/integration/test_query_endpoint_fake_llm.py

Definition of done:
- Answerable fixture question returns cited answer.
- Insufficient-evidence fixture returns refusal.
- Non-refusal answers never contain unverified citation IDs.
```

### 13.6 Evaluation Agent Prompt

```text
You are implementing Phase 13 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Implement eval fixtures, eval runner, metrics, quality thresholds, Markdown/JSON reports, and make eval command.

Constraints:
- Eval must run with fake providers.
- Use deterministic fixture corpus and question set.
- Exit non-zero when thresholds fail.

Required tests:
- tests/unit/test_eval_metrics.py
- tests/integration/test_eval_runner.py

Definition of done:
- make eval creates reports/eval-latest.md and reports/eval-latest.json.
- Metrics include recall@3, recall@5, recall@10, MRR@5, MRR@10, citation precision, exact quote verification, refusal accuracy, unsupported claim rate, audit completeness, cost estimate, and latency.
```

### 13.7 UI Agent Prompt

```text
You are implementing Phase 14 of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Build minimal web UI for querying, answer display, citations, evidence snippets, and diagnostics.

Constraints:
- This is a compliance dashboard, not a landing page.
- Do not expose secrets client-side.
- UI must handle loading, error, insufficient evidence, and success states.
- Use existing backend API contracts.

Required tests:
- Add appropriate UI smoke tests for the chosen frontend approach.

Definition of done:
- User can query fixture corpus in fake mode from browser.
- Citations are visible and linked to evidence snippets.
```

### 13.8 Production Hardening Agent Prompt

```text
You are implementing the production-hardening track of AGENT_IMPLEMENTATION_PLAN.md.

Scope:
- Add one clearly bounded hardening feature: PostgreSQL migration, Redis/cache, PDF/table/OCR extraction, streaming /chat, API-key auth/rate limiting, hash-chain audit verification, or deployment packaging.

Constraints:
- Do not break fake-mode MVP tests.
- Keep the feature behind configuration if it introduces external services or network calls.
- Preserve existing API contracts.
- Add integration tests that skip gracefully when optional services are unavailable.
- Do not log secrets or raw API keys.

Definition of done:
- make test still passes in fake mode.
- The new feature has unit tests and at least one integration or smoke test.
- README documents how to enable and disable the feature.
```

## 14. Testing Strategy

### 14.1 Test Pyramid

Unit tests:

- domain models
- config
- loaders
- normalizers
- chunker
- fake embeddings
- keyword tokenizer
- RRF
- prompt assembly
- citation verifier
- quote/span verifier
- hash-chain audit verifier
- eval metrics

Integration tests:

- FastAPI endpoints
- SQLite repositories
- ingestion pipeline with fake providers
- retrieve endpoint with fake providers
- query endpoint with fake providers
- Qdrant vector store when available
- audit hash-chain verification
- document upload/register endpoint

Optional live tests:

- OpenAI embeddings
- OpenAI generation
- cross-encoder reranker download/inference
- local LLM provider
- PDF/OCR extraction dependencies

E2E tests:

- seed fixture corpus
- ask answerable question
- verify answer, citation, evidence, audit log
- ask out-of-scope question
- verify refusal

### 14.2 Required Test Markers

Use pytest markers:

```python
@pytest.mark.integration
@pytest.mark.live_openai
@pytest.mark.requires_qdrant
@pytest.mark.requires_model_download
```

Default `make test` should exclude live/network-heavy tests.

Suggested commands:

```bash
pytest -m "not live_openai and not requires_model_download"
pytest -m live_openai
pytest -m requires_qdrant
```

### 14.3 Golden Fixture Questions

Create fixture questions that cover:

- exact citation lookup
- synonym-heavy semantic lookup
- multi-section answer
- ambiguous requirement
- missing topic
- out-of-scope general finance question
- citation-like string that does not exist
- question with irrelevant distracting terms

Each fixture question must specify:

- `id`
- `question`
- `behavior`
- `expected_sections`
- `expected_citation_spans` when exact spans are known
- `must_include_citations`
- `must_not_include_phrases`

### 14.4 Quality Gates

Before merging any agent work:

- `make lint`
- `make test`
- `make eval` once eval exists
- `docker compose up -d qdrant` plus Qdrant integration tests for vector changes
- optional live OpenAI smoke only when credentials are configured
- audit verification passes after e2e query tests
- default eval thresholds meet or exceed the current baseline

Do not accept:

- uncited generated answers
- answers with fabricated quote text
- answers citing chunks that were not provided as evidence
- tests that require network by default
- retrieval code embedded directly in API route handlers
- direct OpenAI calls outside provider classes
- hard-coded model names outside config defaults
- corpus-specific parsing mixed into generic chunking/retrieval modules
- post-score filtering that allows out-of-scope chunks to influence ranking

## 15. Retrieval Design Details

### 15.0 Query Routing and Scope

Before scoring, classify the query and build filters.

Router labels:

- `exact_citation`: query mentions a rule, article, chapter, or paragraph ID
- `semantic_policy`: query asks conceptually about an obligation or permission
- `multi_section`: query likely needs more than one rule section
- `ambiguous`: query is underspecified but still in scope
- `out_of_scope`: query is clearly outside the ingested corpus

Scope filters:

- corpus ID
- corpus version
- source ID
- jurisdiction
- document type
- effective or publication date

Filters must be applied before scoring whenever supported by Qdrant, BM25/FTS, or the in-memory test stores. If a backend cannot pre-filter, the implementation must document this and ensure post-filtered candidates are not used for answer generation.

### 15.1 Dense Search

Dense search should prioritize semantic matches. It is best for:

- paraphrases
- conceptual questions
- queries with non-exact wording

Implementation:

- Embed query using same embedding model/dimensions as chunks.
- Search Qdrant top 50 by cosine similarity.
- Filter by corpus/version when provided.

### 15.2 Keyword Search

Keyword search should prioritize exact references. It is best for:

- rule numbers
- defined terms
- section labels
- exact regulatory phrases

Token rules:

- Lowercase normal words.
- Preserve uppercase regulatory abbreviations as searchable tokens and lowercase copies.
- Preserve numeric rule IDs.
- Split punctuation but keep paragraph markers in a normalized token form.

### 15.3 Fusion

Use Reciprocal Rank Fusion to combine candidates. RRF is robust when dense and keyword scores are not on the same scale.

Pseudo-code:

```python
def reciprocal_rank_fusion(rank_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked_ids in rank_lists:
        for zero_based_rank, chunk_id in enumerate(ranked_ids):
            rank = zero_based_rank + 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores
```

### 15.4 Reranking

Reranking should score query/chunk pairs for direct relevance.

Default behavior:

- Rerank top 25 fused candidates.
- Return top 8 evidence chunks.
- Store rerank score.

Fallback:

- If cross-encoder is disabled, use fused ranking.

### 15.5 Evidence Selection

Evidence selection must avoid dumping redundant chunks.

Rules:

- Prefer diversity across sections unless top results clearly belong to same section.
- Include adjacent chunk if top chunk starts mid-thought.
- Cap total evidence context by token budget.
- Drop chunks below minimum score threshold unless needed for ambiguity explanation.

## 16. Grounded Generation Design Details

### 16.1 Prompt Evidence Format

Each evidence block should be compact and stable:

```text
[E1]
Citation: FINRA Rule 1000(a)
Title: Written Policies
Source: https://example.test/rules/1000
Text:
Members must maintain written policies reasonably designed to supervise regulated activity.
```

### 16.2 Structured LLM Output

Target internal schema:

```json
{
  "answer": "string",
  "confidence": "high | medium | low | insufficient_evidence",
  "abstention_reason": "string | null",
  "cited_evidence_ids": ["E1"],
  "claim_citations": [
    {
      "claim": "Members must maintain written policies.",
      "evidence_ids": ["E1"],
      "quoted_support": "Members must maintain written policies reasonably designed to supervise regulated activity."
    }
  ],
  "warnings": []
}
```

### 16.3 Citation Verification

Verifier checks:

- `cited_evidence_ids` all exist.
- Every claim citation maps to existing evidence.
- `answer` contains citation markers when confidence is not `insufficient_evidence`.
- No citations to evidence that was not included in prompt.
- If no evidence exists, answer must be refusal.
- Quoted support appears in the retrieved chunk text or matches the stored source span.
- A non-refusal answer has at least one verified supporting citation.

If verification fails:

- Retry once with corrective prompt if using real LLM.
- Drop unsupported claims only if the remaining answer is still coherent and fully cited.
- If still invalid, return safe fallback:

```text
The system retrieved evidence but could not produce a citation-valid answer. Please inspect the evidence below.
```

Abstention reasons should be machine-readable where possible:

- `out_of_scope`
- `no_retrieval_hits`
- `weak_retrieval`
- `citation_verification_failed`
- `quote_verification_failed`
- `ambiguous_evidence`

### 16.4 Confidence

Confidence should be based on retrieval and generation signals:

- high: strong rerank scores, direct evidence, citations verified
- medium: relevant evidence but some ambiguity
- low: weak or partial evidence
- insufficient_evidence: no adequate support

Do not ask the LLM to invent confidence alone. Combine LLM output with retrieval thresholds.

## 17. Data and Audit Schema

### 17.1 `query_audits`

Columns:

- `query_id`
- `question`
- `normalized_question`
- `corpus_id`
- `corpus_version`
- `answer`
- `confidence`
- `warnings_json`
- `generation_model`
- `embedding_model`
- `reranker_model`
- `prompt_version`
- `retrieval_config_json`
- `latency_ms`
- `estimated_cost_usd`
- `payload_hash`
- `previous_record_hash`
- `record_hash`
- `chain_index`
- `created_at`

### 17.2 `query_evidence`

Columns:

- `query_id`
- `evidence_id`
- `chunk_id`
- `citation_label`
- `dense_rank`
- `dense_score`
- `keyword_rank`
- `keyword_score`
- `fusion_score`
- `rerank_score`
- `final_rank`
- `snippet`
- `quoted_text`
- `source_span_json`
- `quote_hash`
- `verification_status`

### 17.3 `ingestion_jobs`

Columns:

- `job_id`
- `corpus_id`
- `corpus_name`
- `corpus_version`
- `input_type`
- `input_uri`
- `status`
- `started_at`
- `finished_at`
- `report_json`
- `error_json`

### 17.4 `source_documents`

Columns:

- `source_id`
- `corpus_id`
- `corpus_name`
- `corpus_version`
- `title`
- `source_uri`
- `raw_storage_uri`
- `checksum`
- `document_type`
- `publication_date`
- `effective_date`
- `ingested_at`
- `metadata_json`

### 17.5 `document_chunks`

Columns:

- `chunk_id`
- `source_id`
- `section_id`
- `corpus_id`
- `corpus_version`
- `chunk_index`
- `content`
- `citation_label`
- `section_title`
- `heading_path_json`
- `page_number`
- `token_count`
- `start_char`
- `end_char`
- `content_hash`
- `metadata_json`

## 18. Security and Compliance Checklist

Agents must verify:

- `.env` is gitignored.
- `.env.example` has placeholder values only.
- API keys are never logged.
- Exceptions returned to clients are sanitized.
- Admin ingestion endpoints are clearly marked; add auth before production.
- Audit logs avoid storing secrets.
- The UI and API include "not legal advice" wording in docs or footer.
- CORS is restrictive by default.
- Request body size limits exist.
- Dependencies are pinned or constrained enough for reproducible installs.

Production stretch:

- Authentication and role-based access.
- Per-user audit trails.
- Data retention controls.
- Encryption at rest.
- Redaction of sensitive queries.
- SSO integration.

## 19. Observability

Add structured logs for:

- ingestion started/completed/failed
- source parsed
- chunks created
- embedding batch started/completed
- vector upsert count
- query received
- dense/keyword/rerank latency
- LLM latency
- citation verification result
- quote verification result
- audit write result
- audit hash-chain update and verification result
- cache hit/miss for embeddings and query results
- estimated token and cost usage for live provider calls

Metrics to expose eventually:

- query count
- average query latency
- retrieval latency
- generation latency
- ingestion duration
- chunks indexed
- insufficient evidence rate
- citation verification failure rate
- provider error rate
- retrieval recall and MRR from latest eval
- citation exact-span verification rate
- audit chain verification status
- cost per query
- cache hit rate

MVP can log metrics rather than expose Prometheus.

## 20. Error Handling

Use domain-specific exceptions:

- `ConfigurationError`
- `CorpusLoadError`
- `NormalizationError`
- `ChunkingError`
- `EmbeddingError`
- `VectorStoreError`
- `KeywordIndexError`
- `RetrievalError`
- `RerankerError`
- `GenerationError`
- `CitationVerificationError`
- `QuoteVerificationError`
- `AuditChainError`
- `CacheError`

API error responses:

```json
{
  "error": {
    "code": "retrieval_error",
    "message": "Retrieval failed. Please try again or contact support with the request ID.",
    "request_id": "req_..."
  }
}
```

Never return raw provider stack traces to clients.

## 21. Demo Script

The final project should support this demo:

1. Start Qdrant:

```bash
docker compose up -d qdrant
```

2. Install dependencies:

```bash
make install
```

3. Seed fixture corpus in fake mode:

```bash
make seed-fixture
```

4. Run API:

```bash
make run
```

5. Retrieve evidence:

```bash
python scripts/query.py "What written policies must members maintain?" --fake
```

6. Run eval:

```bash
make eval
```

7. Verify audit chain after at least one query:

```bash
python scripts/query.py "What written policies must members maintain?" --fake
curl http://localhost:8000/audit/verify
```

8. Optional UI:

```bash
make ui
```

9. Optional real OpenAI mode:

```bash
export OPENAI_API_KEY=...
export USE_FAKE_EMBEDDINGS=false
export USE_FAKE_LLM=false
python scripts/ingest.py --corpus finra --input data/raw/finra_rules.md
python scripts/query.py "What are the supervision requirements for retail communications?"
```

On Windows PowerShell, use:

```powershell
$env:OPENAI_API_KEY="..."
$env:USE_FAKE_EMBEDDINGS="false"
$env:USE_FAKE_LLM="false"
```

## 22. Stretch Features

Prioritize only after MVP works:

- Corpus version diffing and change summaries.
- Multi-corpus search.
- User-uploaded internal policies and regulatory mapping.
- Control testing suggestions.
- Citation highlighting against original source pages.
- Human feedback capture.
- Answer comparison across corpus versions.
- Access control and tenant isolation.
- Async ingestion workers with Redis/RQ/Celery.
- OpenTelemetry traces.
- Postgres FTS instead of in-memory BM25.
- Streaming answer generation.
- Export answer and citations to PDF or Word.

## 23. Known Risks and Mitigations

Risk: Hallucinated or unsupported answer.

- Mitigation: strict prompt, structured output, citation verifier, quote/span verifier, refusal behavior, evals.

Risk: Retrieval misses exact rule references.

- Mitigation: hybrid search, citation-label boosting, keyword tokenizer tests.

Risk: Dense and keyword scores are incomparable.

- Mitigation: use rank-based fusion rather than raw score blending.

Risk: Tests become flaky due to live APIs.

- Mitigation: fake providers by default and live tests behind markers.

Risk: Audit log is edited after the fact.

- Mitigation: hash-chained audit records and verification endpoint.

Risk: Out-of-scope documents influence ranking.

- Mitigation: pre-score scope filters and tests that fail if filtered chunks affect retrieval.

Risk: Costs climb during ingestion or repeated demos.

- Mitigation: embedding cache, batch embeddings, token/cost logging, fake mode by default.

Risk: Corpus parsing loses hierarchy.

- Mitigation: fixture tests for heading paths and citation labels.

Risk: Model or provider changes.

- Mitigation: provider interfaces and environment-configured model names.

Risk: Cross-encoder model download slows CI.

- Mitigation: fake/no-op reranker by default; optional marked tests.

## 24. Final Acceptance Criteria

The project is complete when:

- A user can ingest the fixture rulebook.
- A user can ask answerable questions and receive cited answers.
- A user can ask unsupported questions and receive safe refusals.
- `/retrieve` and `/query` work.
- Audit logs record evidence and answer details.
- Audit chain verification passes after query traffic.
- Citation and quote/span verification reject fabricated support.
- Hybrid retrieval uses dense plus keyword search.
- Scope filters are applied before scoring for corpus/version/source filters.
- Reranking is implemented or cleanly configurable.
- Eval harness reports retrieval and citation quality.
- Eval harness meets portfolio thresholds or clearly reports unmet thresholds.
- Live-provider runs log estimated token usage and cost.
- Tests run without live OpenAI.
- README contains a working demo path.
- Code is organized around swappable providers.

## 25. Recommended First Build Order for a Single AI Agent

If one agent is building everything, use this exact order:

1. Create skeleton and tests.
2. Create domain models.
3. Create fixture corpus.
4. Implement Markdown loader.
5. Implement chunker.
6. Implement fake embeddings.
7. Implement in-memory vector store.
8. Implement BM25 keyword index.
9. Implement RRF retrieval.
10. Implement `/retrieve`.
11. Implement fake LLM and citation verifier.
12. Implement quote/span verifier and citation-abstention behavior.
13. Implement `/query`.
14. Add SQLite persistence and audit.
15. Add hash-chain audit verification.
16. Add ingestion CLI.
17. Add Qdrant implementation.
18. Add OpenAI providers.
19. Add optional cross-encoder reranker.
20. Add eval harness and thresholds.
21. Add minimal UI.
22. Add optional cache/local-provider hardening.
23. Finish docs and demo.

This order intentionally creates a fully testable fake-mode vertical slice before adding live providers.
