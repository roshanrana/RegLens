# Plan Comparison And Optimization Notes

Date: 2026-08-19

## Summary

The attached project plan is stronger on production realism: PDF/OCR/table extraction, Redis caching, local model fallbacks, hash-chained audit logs, cost targets, and explicit compliance-grade citation-abstention behavior.

The agent implementation plan is stronger on execution: clean module boundaries, fake-mode development, deterministic tests, API contracts, parallel agent waves, copy-paste agent prompts, and a clear vertical slice.

The optimized plan keeps the agent-first execution model and incorporates the best production and compliance controls from the attached plan.

## What Was Integrated

- Added comparison-based optimization notes at the top of `AGENT_IMPLEMENTATION_PLAN.md`.
- Added production-ready extraction requirements:
  - raw source snapshot storage
  - source checksums
  - PDF extractor interface
  - table preservation
  - page number metadata
  - optional OCR fallback
- Added query-router requirements:
  - exact citation lookup
  - semantic policy question
  - multi-section synthesis
  - ambiguous query
  - out-of-scope query
- Added pre-score scope filtering for corpus, version, source, jurisdiction, document type, and date filters.
- Added token budget tracking and evidence trimming before generation.
- Added embedding cache and optional local embedding provider.
- Added optional local LLM provider configuration.
- Added quote/span verification, not just citation ID verification.
- Added citation-abstention behavior:
  - weak retrieval abstains before LLM call
  - fabricated quotes are rejected
  - citations to non-retrieved chunks are refused
  - unsupported claims are dropped or trigger fallback
- Added hash-chained audit logging and `/audit/verify`.
- Added document registration/upload endpoint requirements.
- Added optional streaming `/chat` alias.
- Added cost and latency targets.
- Added eval metrics:
  - recall@10
  - MRR@5 and MRR@10
  - exact quote verification rate
  - unsupported claim rate
  - audit completeness
  - estimated cost per query
- Added portfolio-ready quality thresholds:
  - recall@10 >= 0.85
  - exact quote/span verification >= 0.95
  - unsupported claim rate < 0.02
  - audit completeness = 1.00
  - default live cost per query < $0.01
- Added production-hardening agent wave and prompt.

## What Stayed From The Agent-First Plan

- Fake-mode testing remains mandatory.
- Unit tests and CI do not require OpenAI, Qdrant, model downloads, Redis, or PostgreSQL.
- Qdrant remains the default vector store.
- Provider interfaces remain explicit and swappable.
- Retrieval, reranking, generation, citation verification, audit, and API layers remain separate.
- `/retrieve` remains a first-class endpoint so retrieval can be tested independently from generation.
- Eval fixtures are deterministic and small enough for rapid regression testing.

## Decisions And Tradeoffs

- LangChain was not added to the core path. It can be used later for experiments, but compliance-critical RAG benefits from explicit, typed components that are easier to audit and test.
- PostgreSQL and Redis are production-hardening targets, not blockers for the first vertical slice.
- Streamlit is recommended as the fastest useful UI demo, with React/Vite kept as a richer optional path.
- PDF/OCR/table extraction is included, but agents should not let it block the fake-mode synthetic corpus demo.
- Pinecone is kept as an adapter option, but Qdrant is preferred for self-hosted data locality.

## Best Build Strategy

1. Build the complete fake-mode vertical slice.
2. Add Qdrant and real vector indexing.
3. Add OpenAI embeddings and generation providers.
4. Add cross-encoder reranking.
5. Add quote/span verification and hash-chain audit as hard gates.
6. Add eval thresholds and reports.
7. Add UI and demo docs.
8. Add production hardening: PostgreSQL, Redis, auth, streaming, PDF/OCR, deployment.

The optimized plan is now the canonical implementation plan:

- `AGENT_IMPLEMENTATION_PLAN.md`

