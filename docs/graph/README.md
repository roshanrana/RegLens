# Code graph

RegLens carries an offline, queryable code knowledge graph built with
[graphify](https://pypi.org/project/graphifyy/) (tree-sitter AST extraction, no LLM, no API key).
It maps functions, classes and modules across the 123 Python files in `app/` and `tests/` into
nodes and edges — calls, references, imports, inheritance — clustered into communities. Agents
and reviewers should query it before grepping or reading files cold: it answers "what is X?",
"how does A reach B?" and "what depends on X?" with file:line citations in a few hundred tokens.

## Build and query

```bash
graphify update .                              # rebuild after code changes (AST only, seconds, no API cost)
graphify explain "<class or function>"         # neighbors of one node
graphify path "<A>" "<B>"                      # shortest relationship path between two nodes
graphify affected "<node id>" --depth 2        # reverse traversal: what breaks if this changes
```

`graphify update .` also regenerates `graphify-out/GRAPH_REPORT.md`, the human-readable map of
communities, hub nodes and cross-file links. Only `GRAPH_REPORT.md` is committed; `graph.json`,
`graph.html`, `cache/` and `manifest.json` are gitignored (1-2 MB, rebuilt in seconds, churns every
commit) — see `.graphifyignore` and the `graphify-out/*` rule in `.gitignore`.

## Three real queries

**1. Explain the hybrid retrieval service** (`app/retrieval/service.py`):

```
$ graphify explain "RetrievalService"
Node: RetrievalService
  Source:    app/api/routes_query.py L360
  Type:      code
  Community: 0
  Degree:    18

Connections (18):
  --> DependencyUnavailableError [uses] [INFERRED]
  --> RetrievalCandidate [uses] [INFERRED]
  --> RegLensError [uses] [INFERRED]
  --> QueryEvidence [uses] [INFERRED]
  --> QueryAuditRepository [uses] [INFERRED]
  --> ChatSession [uses] [INFERRED]
  --> ChatTurn [uses] [INFERRED]
  --> QueryAudit [uses] [INFERRED]
  --> GenerationService [uses] [INFERRED]
  --> Citation [uses] [INFERRED]
  --> RetrievalResult [uses] [INFERRED]
  --> Answer [uses] [INFERRED]
  --> RetrievalDiagnostics [uses] [INFERRED]
  <-- _query_dependencies() [references] [EXTRACTED]
  <-- _retrieval_service() [references] [EXTRACTED]
```

**2. Path from generation to citation verification** (`GenerationService` to
`verify_answer_citations` in `app/generation/citations.py`):

```
$ graphify path "GenerationService" "verify_answer_citations"
Shortest path (3 hops):
  GenerationService --uses [INFERRED]--> QueryEvidence
    <--imports [EXTRACTED]-- service.py --imports [EXTRACTED]--> verify_answer_citations()
```

This confirms the real production edge: `app/generation/service.py` is the module that imports and
calls the citation verifier, not a test file.

**3. Blast radius of the audit-chain repository** (`app/persistence/repositories.py`):

```
$ graphify affected "app_api_routes_audit_py_queryauditrepository" --depth 2
Affected nodes for QueryAuditRepository
- _audit_repository() [references] app/api/routes_audit.py:L115
- _get_audit_or_404() [references] app/api/routes_audit.py:L136
- list_query_audits() [calls] app/api/routes_audit.py:L22
- get_query_audit() [calls] app/api/routes_audit.py:L61
- export_query_audit() [calls] app/api/routes_audit.py:L77
- verify_query_audit_chain() [calls] app/api/routes_audit.py:L101
```

Every route that touches the hash-chained audit table shows up — the set to re-check whenever the
audit repository's schema or verification logic changes.

**One thing the graph got wrong:** `graphify path "query" "verify_answer_citations"` (using the
short, ambiguous names) routed through `test_citation_abstention.py`'s imports instead of the real
`app/generation/service.py` call site, because both are `[EXTRACTED]` import edges and the test
file happened to be shorter. Passing a less ambiguous source node (`GenerationService`) or the
fully-qualified node id (as in query 3) avoids this — a good default is to `explain` a name first
to get its exact node id before running `path` or `affected` on it.

## Counts and build time

- 1825 nodes, 6620 edges, 82 communities (70 shown, 12 thin omitted)
- 123 files, ~84,000 words extracted
- 64% EXTRACTED edges, 36% INFERRED, 0% AMBIGUOUS
- Build: `graphify update .` completed in under 10 seconds (AST-only, no LLM, no API key)

## What `.graphifyignore` excludes

`.venv/`, `node_modules/`, `graphify-out/` (self-reference), `.mypy_cache/`, `.pytest_cache/`,
`.ruff_cache/`, `reglens.egg-info/`, `reports/`, `tmp/`, `*.db` (the local SQLite dev database).
The evaluation fixtures under `app/evals/fixtures/` are small (~20 KB, two synthetic rulebooks and
a questions file) and are kept in the graph since they are part of the tested surface.

## Hooks (local opt-in, not committed)

`graphify install --project` also offers PreToolUse hooks that intercept `Read`/`Grep`/`Bash`
search calls and nudge the agent to query the graph first. Those hooks are personal workflow
config, not repository policy — they are not committed here (`.claude/settings.json` is left out
of version control for this repo). Run `graphify install --project --platform claude` locally to
opt in.

## Shipyard integration

Implementers query the graph before opening files for a task pack; Verifiers run
`graphify affected` on every symbol a diff touches and flag anything outside the pack's stated
scope as a finding.
