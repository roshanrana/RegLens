# Graph Report - RegLens  (2026-09-10)

## Corpus Check
- 123 files · ~84,133 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1825 nodes · 6620 edges · 82 communities (70 shown, 12 thin omitted)
- Extraction: 64% EXTRACTED · 36% INFERRED · 0% AMBIGUOUS · INFERRED: 2405 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2934ff72`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]

## God Nodes (most connected - your core abstractions)
1. `DependencyUnavailableError` - 215 edges
2. `Chunk` - 182 edges
3. `Settings` - 145 edges
4. `RetrievalCandidate` - 121 edges
5. `RegLensError` - 99 edges
6. `QdrantVectorStore` - 97 edges
7. `FakeEmbeddingProvider` - 95 edges
8. `QueryEvidence` - 87 edges
9. `create_app()` - 87 edges
10. `DocumentSection` - 86 edges

## Surprising Connections (you probably didn't know these)
- `RetrievalService` --uses--> `Settings`  [INFERRED]
  tests/integration/test_ingest_endpoints.py → app/core/config.py
- `Path` --uses--> `Settings`  [INFERRED]
  tests/integration/test_source_endpoints.py → app/core/config.py
- `Path` --uses--> `Settings`  [INFERRED]
  tests/unit/test_config.py → app/core/config.py
- `Distance` --uses--> `Settings`  [INFERRED]
  tests/integration/test_local_qdrant_runtime.py → app/core/config.py
- `FakeCountResult` --uses--> `Settings`  [INFERRED]
  tests/integration/test_local_qdrant_runtime.py → app/core/config.py

## Import Cycles
- 1-file cycle: `app/api/routes_admin.py -> app/api/routes_admin.py`
- 1-file cycle: `app/main.py -> app/main.py`
- 1-file cycle: `app/domain/ids.py -> app/domain/ids.py`
- 1-file cycle: `app/domain/models.py -> app/domain/models.py`
- 1-file cycle: `app/ingestion/loaders.py -> app/ingestion/loaders.py`
- 1-file cycle: `app/persistence/repositories.py -> app/persistence/repositories.py`

## Communities (82 total, 12 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (154): alias, _already_reported(), _audit_repository(), chat(), _chat_events(), _chat_repository(), _chat_session_export_markdown(), _chat_session_export_payload() (+146 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (144): _chunk_payload(), _chunk_repository(), _complete_ingestion_from_load_result(), create_document(), create_document_from_url(), _date_payload(), _delete_chunks_from_active_vector_store(), delete_document() (+136 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (100): PromptBundle, Any, Exception, GeneratedAnswer, PromptBundle, Evidence, BaseModel, DependencyUnavailableError (+92 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (86): Any, Chunk, Path, RetrievalService, _approx_tokens(), CostEstimate, estimate_openai_query_cost(), Deterministic live-provider cost estimates for audits and diagnostics. (+78 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (42): Vector, RetrievalCandidate, Any, Chunk, EmbeddingProvider, RetrievalCandidate, Vector, EmbeddingProvider (+34 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (36): Vector, Any, Exception, Vector, EmbeddingCache, embedding_cache_key(), EmbeddingCache, Small bounded embedding cache for optional live-provider cost control. (+28 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (41): Answer, Citation, Evidence, Confidence, CitationVerificationIssue, CitationVerificationResult, is_refusal_answer(), _quote_sources() (+33 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (45): Any, datetime, canonical_json(), _json_default(), make_audit_record_hash(), make_chat_session_id(), make_chat_turn_id(), make_chunk_id() (+37 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (35): Any, Exception, RetrievalCandidate, _candidate_text(), CrossEncoderReranker, _float_score(), _inference_failure_details(), _load_cross_encoder_class() (+27 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (33): cosine_similarity(), FakeEmbeddingConfig, FakeEmbeddingProvider, Small deterministic embedding provider for fake mode., Any, MonkeyPatch, test_empty_text_returns_zero_vector(), test_fake_embeddings_are_deterministic_and_normalized() (+25 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (36): _audit_detail_payload(), _audit_export_markdown(), _audit_export_payload(), _audit_hash_payload(), _audit_repository(), _audit_summary_payload(), _chat_link_for_audit(), _chat_link_payload() (+28 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (28): Chunk, Collection, _add_citation_reference_keys(), _append_unique(), BM25KeywordIndex, _expand_token(), extract_citation_keys(), _has_citation_signal() (+20 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (28): Chunk, EmbeddingProvider, Evidence, Path, Reranker, RetrievalCandidate, BM25KeywordIndex, ChunkingConfig (+20 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (36): 1. AI in the Product, 1. Ask a Regulatory Question, 2. AI in System Design, 2. Inspect Citations and Evidence, 3. AI in Development and Integration, 3. Ingest Regulatory Material, 4. Use Chat With Persistent Sessions, 5. Review Audit Trail (+28 more)

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (35): 2026-08-19: Wave 1 And Wave 2 Fake-Mode Vertical Slice, 2026-08-19: Wave 3 Auditable Answer Loop, 2026-08-19: Wave 4 Quality Gates And Audit Visibility, 2026-08-19: Wave 5 Local Ingestion And Qdrant Adapter Readiness, 2026-08-20: Adversarial Source-Instruction Eval Coverage, 2026-08-20: Agent Verification Guardrails, 2026-08-20: Append-Only Query Audit Guard, 2026-08-20: Audit Export And Evidence Integrity (+27 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (29): RetrievalCandidate, _candidate_rank(), _candidate_score(), _candidate_sort_key(), _CandidateState, merge_candidates(), _merge_one_source(), Candidate fusion helpers for RegLens hybrid retrieval. (+21 more)

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (23): _bool_env(), _choice_env(), _env(), get_settings(), _int_env(), _optional_int_env(), _optional_str_env(), reset_settings_cache() (+15 more)

### Community 17 - "Community 17"
Cohesion: 0.13
Nodes (19): Settings, test_api_key_auth_protects_operational_routes_but_not_health(), test_bearer_api_key_is_accepted(), test_rate_limit_returns_429_after_configured_limit(), test_delete_document_removes_source_and_refreshes_mock_retrieval(), test_delete_missing_document_returns_structured_error(), test_documents_create_alias_ingests_and_indexes_source(), test_local_mode_without_qdrant_dependency_starts_degraded() (+11 more)

### Community 18 - "Community 18"
Cohesion: 0.21
Nodes (26): client(), _ingest_fixture(), _install_fake_pypdf(), _install_missing_pypdf(), _retrieval_service(), test_admin_ingest_corpus_overrides_create_distinct_source_rows(), test_admin_ingest_finra_url_snapshots_and_indexes_html(), test_admin_ingest_markdown_fixture_persists_job_source_sections_and_chunks() (+18 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (11): Any, AuditHash, _dict_copy(), _require_non_empty(), _span_dict_copy(), _string_list(), _validate_literal(), _validate_non_negative() (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.18
Nodes (23): GenerationService, Settings, EmbeddingProvider, Reranker, Settings, build_generation_service(), Provider factory scaffolding for generation components., FakeGenerationService (+15 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (16): Distance, FakeCountResult, FakeModels, FakeQdrantClient, FakeQueryResponse, FakeScoredPoint, FieldCondition, Filter (+8 more)

### Community 22 - "Community 22"
Cohesion: 0.16
Nodes (12): Chunk, is_zero_vector(), InMemoryVectorStore, Simple deterministic vector store for tests and local development., _chunk(), test_blank_query_returns_no_results(), test_delete_and_clear_update_store_count(), test_invalid_top_k_and_dimension_mismatch_are_rejected() (+4 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (14): Chunk, RetrievalCandidate, KeywordTokenizer, _QueryFeatures, _bigrams(), FakeRerankerConfig, _overlap_ratio(), _QueryFeatures (+6 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (9): Chunk, DocumentSection, ApproximateTokenizer, chunk_section(), chunk_sections(), _metadata_str(), Small deterministic tokenizer for tests and fake-mode ingestion., Tokenizer (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (17): 0. Agent Quick Start, 10. Dependencies, 18. Security and Compliance Checklist, 19. Observability, 1. Product Goal, 20. Error Handling, 21. Demo Script, 22. Stretch Features (+9 more)

### Community 26 - "Community 26"
Cohesion: 0.21
Nodes (16): datetime, _clean_title(), _extract_pdf_page_texts(), extract_rule_number(), _first_non_empty_line(), _is_pdf_rule_heading(), _line_start_offsets(), _metadata_value() (+8 more)

### Community 27 - "Community 27"
Cohesion: 0.41
Nodes (16): create_app(), _post_chat(), _post_query(), _settings(), test_audit_queries_lists_recent_query_summaries(), test_audit_query_detail_returns_record_and_evidence_rows(), test_audit_query_detail_returns_reglens_404_for_unknown_query(), test_audit_query_export_rejects_unknown_format() (+8 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (18): API Hardening, Ask A Question, Chat Endpoint, Cross-Encoder Reranker, Environment, Ingest FINRA URLs, Ingest Local Sources, Inspect Audit Records (+10 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (17): FINRA Synthetic Rulebook, Rule 1000(a). Written Policies, Rule 1000(b). Annual Review, Rule 1000. General Standards, Rule 1010(a). Fair and Balanced Statements, Rule 1010(b). Prohibited Promissory Language, Rule 1010(c). Required Disclosure Table, Rule 1010. Communications with Retail Investors (+9 more)

### Community 30 - "Community 30"
Cohesion: 0.24
Nodes (14): DocumentSection, DocumentSource, extract_markdown_sections(), _front_matter_source_id(), _Heading, infer_citation_label(), _sha256_hex(), stable_section_id() (+6 more)

### Community 31 - "Community 31"
Cohesion: 0.12
Nodes (16): 11. Implementation Phases, Phase 10: Prompting and Answer Generation, Phase 11: Ingestion Pipeline Endpoint and CLI, Phase 12: Audit Logging, Phase 13: Evaluation Harness, Phase 14: Minimal UI, Phase 15: Documentation and Demo, Phase 1: Project Skeleton and Development Contract (+8 more)

### Community 32 - "Community 32"
Cohesion: 0.13
Nodes (15): 10. The analyst UI (`app/api/routes_ui.py`), 1. Ingestion that keeps citations (`app/ingestion/`), 2. Hybrid retrieval with exposed diagnostics (`app/retrieval/`), 3. Grounded generation, verified afterwards (`app/generation/`), 4. Adversarial sources (`app/evals/fixtures/adversarial_rulebook.md`), 5. The evaluation harness (`app/evals/metrics.py`, `make eval`), 6. Audit (`app/persistence/`, `app/api/routes_audit.py`), 7. Chat sessions (`app/api/routes_query.py`) (+7 more)

### Community 33 - "Community 33"
Cohesion: 0.25
Nodes (14): client(), _sse_events(), test_chat_endpoint_appends_turns_to_existing_session(), test_chat_endpoint_rejects_empty_question(), test_chat_endpoint_rejects_unknown_session_before_query_audit(), test_chat_endpoint_returns_query_compatible_json_payload(), test_chat_endpoint_streams_sse_events_with_final_query_payload(), test_chat_session_delete_removes_session_but_preserves_query_audit() (+6 more)

### Community 34 - "Community 34"
Cohesion: 0.24
Nodes (12): extract_front_matter(), first_markdown_heading(), _looks_like_markdown_table_row(), normalize_markdown(), normalize_newlines(), _normalize_table_row(), normalize_text(), Normalize common source encodings and newline styles. (+4 more)

### Community 35 - "Community 35"
Cohesion: 0.18
Nodes (6): Distance, _FakeModels, _FakeQdrantClient, PointStruct, test_create_app_mock_uses_provider_factories_without_network(), VectorParams

### Community 36 - "Community 36"
Cohesion: 0.21
Nodes (9): _hash_feature(), l2_normalize(), Deterministic fake embeddings for local retrieval tests.  The fake provider in, Return lowercase lexical tokens with regulatory citations split cleanly., Apply a conservative suffix trim to improve fake lexical recall., simple_stem(), _token_weight(), tokenize() (+1 more)

### Community 38 - "Community 38"
Cohesion: 0.21
Nodes (5): RegLens — Build Log, Current Contract, Deferred Decision, Recommended Future OCR Path, RegLens OCR Strategy

### Community 39 - "Community 39"
Cohesion: 0.30
Nodes (10): make_chunk_id(), DocumentSection, test_chunker_produces_stable_ids_for_same_section(), test_make_chunk_id_changes_for_version_index_or_text(), test_make_chunk_id_is_deterministic(), _section(), test_chunk_sections_preserves_section_order(), test_empty_section_returns_no_chunks() (+2 more)

### Community 40 - "Community 40"
Cohesion: 0.44
Nodes (11): Any, MonkeyPatch, Path, _install_fake_pypdf(), _install_missing_pypdf(), test_pdf_loader_does_not_split_mid_sentence_rule_references(), test_pdf_loader_extracts_page_sections_with_metadata(), test_pdf_loader_raises_dependency_error_when_pypdf_is_missing() (+3 more)

### Community 41 - "Community 41"
Cohesion: 0.18
Nodes (11): Agent C: Add Optional OCR Prototype, Completed: Audit-To-Chat Traceability, Completed: Chat Session Transcript Export, Completed: CI Container Verification Job, Completed: Container Verification Profile, Completed: Durable Chat Sessions, Completed: Mock-Safe Container Packaging, Completed: No-Billing Chat Surface (+3 more)

### Community 42 - "Community 42"
Cohesion: 0.31
Nodes (10): clip(), load(), main(), md_cell(), Path, Render metrics/headline.json into a results card.  Outputs:   docs/assets/met, render_markdown(), render_svg() (+2 more)

### Community 43 - "Community 43"
Cohesion: 0.29
Nodes (9): NoOpReranker, Reranker implementation for explicitly preserving fused order., RetrievalCandidate, _candidate(), _chunk(), test_fake_reranker_honors_top_k(), test_fake_reranker_is_deterministic_and_sets_scores_and_ranks(), test_fake_reranker_rejects_invalid_top_k() (+1 more)

### Community 44 - "Community 44"
Cohesion: 0.44
Nodes (9): build_commands(), main(), Path, run_commands(), VerifyCommand, test_default_verify_profile_runs_fake_mode_quality_gate(), test_full_local_verify_profile_keeps_optional_smokes_explicit(), test_optional_verify_profiles_run_only_marked_smokes() (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.20
Nodes (10): 8.1 `GET /health`, 8.2 `GET /ready`, 8.3 `POST /admin/ingest`, 8.4 `GET /admin/ingest/{job_id}`, 8.5 `POST /retrieve`, 8.6 `POST /query`, 8.7 `GET /sources`, 8.8 `POST /documents` (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.20
Nodes (9): Active Product Goal, Constraints For Future Agents, Current Known Non-Blocking Warnings, Current Verified Capabilities, Important File Landmarks, Latest Verification Evidence, Most Recent Work Completed, Recommended Orchestration Order (+1 more)

### Community 47 - "Community 47"
Cohesion: 0.33
Nodes (10): _dependency_details_by_name(), _force_cross_encoder_package_missing(), _force_openai_package_missing(), _guard_openai_import(), test_local_mode_openai_embedding_selection_starts_degraded_without_importing_openai(), test_provider_readiness_and_errors_do_not_leak_openai_api_key(), test_query_reports_llm_provider_gate_when_generation_is_unavailable(), test_query_reports_unconfigured_real_retrieval_when_providers_are_available() (+2 more)

### Community 48 - "Community 48"
Cohesion: 0.22
Nodes (9): 13.1 Foundation Agent Prompt, 13.2 Ingestion Agent Prompt, 13.3 Embedding and Vector Agent Prompt, 13.4 Retrieval Agent Prompt, 13.5 Generation Agent Prompt, 13.6 Evaluation Agent Prompt, 13.7 UI Agent Prompt, 13.8 Production Hardening Agent Prompt (+1 more)

### Community 49 - "Community 49"
Cohesion: 0.22
Nodes (9): 7.1 `DocumentSource`, 7.2 `DocumentSection`, 7.3 `Chunk`, 7.4 `RetrievalCandidate`, 7.5 `Evidence`, 7.6 `Answer`, 7.7 `Citation`, 7.8 `AuditHash` (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.61
Nodes (7): _settings(), test_audit_verify_detects_query_evidence_deletion(), test_audit_verify_detects_query_evidence_snippet_tampering(), test_query_audit_hash_chain_handles_repeated_questions(), test_query_audit_hash_chain_links_multiple_queries(), test_query_endpoint_writes_audit_and_evidence_rows(), Path

### Community 52 - "Community 52"
Cohesion: 0.43
Nodes (7): client(), test_retrieve_endpoint_exposes_exact_citation_route_diagnostics(), test_retrieve_endpoint_honors_corpus_filters(), test_retrieve_endpoint_honors_source_id_filter(), test_retrieve_endpoint_rejects_empty_question(), test_retrieve_endpoint_returns_evidence_and_diagnostics(), TestClient

### Community 53 - "Community 53"
Cohesion: 0.29
Nodes (7): 12. Parallel Agent Work Plan, Wave 1: Foundation, Wave 2: Indexing, Wave 3: Retrieval, Wave 4: Generation and Audit, Wave 5: Evaluation, UI, Docs, Wave 6: Production Hardening

### Community 54 - "Community 54"
Cohesion: 0.29
Nodes (7): 15.0 Query Routing and Scope, 15.1 Dense Search, 15.2 Keyword Search, 15.3 Fusion, 15.4 Reranking, 15.5 Evidence Selection, 15. Retrieval Design Details

### Community 55 - "Community 55"
Cohesion: 0.29
Nodes (7): 4.1 Ingestion, 4.2 Retrieval, 4.3 Generation, 4.4 API, 4.5 UI, 4.6 Evaluation, 4. Functional Requirements

### Community 56 - "Community 56"
Cohesion: 0.29
Nodes (7): Honest limits, RegLens — Overview, The design, The setting, What is measured, Where it sits among the other projects, Why fake mode is a feature

### Community 57 - "Community 57"
Cohesion: 0.29
Nodes (6): FINRA Adversarial Rulebook, Rule 9999(a). Retention Injection Test, Rule 9999(b). Citation Suppression Test, Rule 9999(c). Prompt Leak Test, Rule 9999(d). Same Sentence Injection Test, Rule 9999. Source Trust Controls

### Community 58 - "Community 58"
Cohesion: 0.43
Nodes (6): client(), test_missing_source_returns_structured_error(), test_sources_list_and_detail_after_ingest(), test_sources_list_is_empty_before_ingest(), Path, TestClient

### Community 59 - "Community 59"
Cohesion: 0.29
Nodes (6): Best Build Strategy, Decisions And Tradeoffs, Plan Comparison And Optimization Notes, Summary, What Stayed From The Agent-First Plan, What Was Integrated

### Community 60 - "Community 60"
Cohesion: 0.29
Nodes (7): At a glance, Documentation, Quick start, RegLens, Results, The answer path, What it is not

### Community 61 - "Community 61"
Cohesion: 0.33
Nodes (6): 17.1 `query_audits`, 17.2 `query_evidence`, 17.3 `ingestion_jobs`, 17.4 `source_documents`, 17.5 `document_chunks`, 17. Data and Audit Schema

### Community 63 - "Community 63"
Cohesion: 0.60
Nodes (5): _free_port(), _live_server(), test_ui_browser_ingest_query_and_delete_flow(), _wait_for_ready(), Path

### Community 64 - "Community 64"
Cohesion: 0.53
Nodes (5): client(), test_health_endpoint(), test_ready_endpoint_fake_mode(), test_request_id_header_is_preserved(), TestClient

### Community 65 - "Community 65"
Cohesion: 0.40
Nodes (5): 14.1 Test Pyramid, 14.2 Required Test Markers, 14.3 Golden Fixture Questions, 14.4 Quality Gates, 14. Testing Strategy

### Community 66 - "Community 66"
Cohesion: 0.40
Nodes (5): 16.1 Prompt Evidence Format, 16.2 Structured LLM Output, 16.3 Citation Verification, 16.4 Confidence, 16. Grounded Generation Design Details

### Community 67 - "Community 67"
Cohesion: 0.40
Nodes (5): date, Any, _parse_date(), _parse_int(), coerce_metadata_value()

### Community 68 - "Community 68"
Cohesion: 0.50
Nodes (4): 6.1 Logical Components, 6.2 Suggested Repository Structure, 6.3 Data Flow, 6. Architecture

### Community 70 - "Community 70"
Cohesion: 0.83
Nodes (3): _dependency_names(), test_base_and_dev_dependencies_do_not_include_model_download_packages(), test_base_and_dev_dependencies_do_not_include_openai_sdk()

## Knowledge Gaps
- **249 isolated node(s):** `HTMLResponse`, `T`, `Self`, `JSONResponse`, `Any` (+244 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DependencyUnavailableError` connect `Community 2` to `Community 0`, `Community 1`, `Community 67`, `Community 4`, `Community 5`, `Community 8`, `Community 40`, `Community 10`, `Community 9`, `Community 20`, `Community 62`, `Community 26`, `Community 27`, `Community 30`?**
  _High betweenness centrality (0.173) - this node is a cross-community bridge._
- **Why does `Chunk` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 37`, `Community 8`, `Community 9`, `Community 11`, `Community 12`, `Community 43`, `Community 15`, `Community 19`, `Community 22`, `Community 23`, `Community 24`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 17` to `Community 64`, `Community 1`, `Community 2`, `Community 35`, `Community 33`, `Community 5`, `Community 3`, `Community 47`, `Community 16`, `Community 18`, `Community 51`, `Community 20`, `Community 21`, `Community 52`, `Community 58`, `Community 27`, `Community 63`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 161 inferred relationships involving `DependencyUnavailableError` (e.g. with `alias` and `IngestRequest`) actually correct?**
  _`DependencyUnavailableError` has 161 INFERRED edges - model-reasoned connections that need verification._
- **Are the 146 inferred relationships involving `Chunk` (e.g. with `IngestRequest` and `IngestUrlRequest`) actually correct?**
  _`Chunk` has 146 INFERRED edges - model-reasoned connections that need verification._
- **Are the 70 inferred relationships involving `Settings` (e.g. with `Request` and `Settings`) actually correct?**
  _`Settings` has 70 INFERRED edges - model-reasoned connections that need verification._
- **Are the 96 inferred relationships involving `RetrievalCandidate` (e.g. with `ChatRequest` and `QueryRequest`) actually correct?**
  _`RetrievalCandidate` has 96 INFERRED edges - model-reasoned connections that need verification._