const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.author = "Roshan Rana";
pres.title = "RegLens — AI Systems Architecture Review";

// Palette
const NAVY = "14213D", INK = "1B2A41", WHITE = "FFFFFF", ICE = "DCE7F5", MINT = "2EC4B6",
  GOLD = "F2B134", MUTED = "6B7A90", CARD = "F3F6FA", LINE = "C9D3E0", CARD_D = "1C2B4F", RED = "D64550";
const HF = "Cambria", BF = "Calibri";
const ASSETS = "C:/Code-Central/RegLens/docs/assets/";

let n = 0;
function base(title, kicker) {
  const s = pres.addSlide();
  n += 1;
  s.background = { color: WHITE };
  if (kicker) s.addText(kicker.toUpperCase(), { x: 0.5, y: 0.28, w: 6, h: 0.25, fontFace: BF, fontSize: 10, bold: true, color: MINT, charSpacing: 2, isTextBox: true, margin: 0 });
  s.addText(title, { x: 0.5, y: 0.5, w: 9, h: 0.6, fontFace: HF, fontSize: 26, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  s.addText(`RegLens · AI Systems Architecture Review · ${n}`, { x: 0.5, y: 5.25, w: 9, h: 0.25, fontFace: BF, fontSize: 8, color: MUTED, isTextBox: true, margin: 0 });
  return s;
}
function dark(title, sub) {
  const s = pres.addSlide();
  n += 1;
  s.background = { color: NAVY };
  s.addText(title, { x: 0.6, y: 1.9, w: 8.8, h: 0.9, fontFace: HF, fontSize: 34, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  if (sub) s.addText(sub, { x: 0.6, y: 2.85, w: 8.8, h: 0.6, fontFace: BF, fontSize: 15, italic: true, color: ICE, isTextBox: true, margin: 0 });
  return s;
}
function card(s, x, y, w, h, fill = CARD, line = LINE) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: line, width: 0.75 }, rectRadius: 0.06 });
}
function box(s, x, y, w, h, title, body, opt = {}) {
  const fill = opt.fill || CARD, tcol = opt.tcol || NAVY, bcol = opt.bcol || INK, line = opt.line || LINE;
  card(s, x, y, w, h, fill, line);
  s.addText(title, { x: x + 0.1, y: y + 0.06, w: w - 0.2, h: 0.28, fontFace: BF, fontSize: opt.ts || 11, bold: true, color: tcol, isTextBox: true, margin: 0 });
  if (body) s.addText(body, { x: x + 0.1, y: y + 0.34, w: w - 0.2, h: h - 0.4, fontFace: BF, fontSize: opt.bs || 8.5, color: bcol, isTextBox: true, margin: 0, valign: "top" });
}
function arrow(s, x1, y1, x2, y2, color = MUTED, w = 1.25) {
  const flipH = x2 < x1, flipV = y2 < y1;
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.01, h: Math.abs(y2 - y1) || 0.01, line: { color, width: w, endArrowType: "triangle" }, flipH, flipV });
}
function bullets(s, items, x, y, w, h, fs = 11, color = INK) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })), { x, y, w, h, fontFace: BF, fontSize: fs, color, isTextBox: true, margin: 0, paraSpaceAfter: 4, valign: "top" });
}
function table(s, rows, x, y, w, colW, fs = 8.5, rowH) {
  const data = rows.map((r, i) => r.map((c) => ({ text: c, options: i === 0 ? { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: fs } : { fontSize: fs, color: INK } })));
  s.addTable(data, { x, y, w, colW, fontFace: BF, border: { type: "solid", pt: 0.5, color: LINE }, autoPage: false, rowH });
}
function imgFit(s, path, x, y, maxW, maxH, pw, ph) {
  const r = Math.min(maxW / pw, maxH / ph);
  const w = pw * r, h = ph * r;
  s.addImage({ path, x: x + (maxW - w) / 2, y, w, h });
  return { w, h };
}
function caption(s, text, x, y, w) {
  s.addText(text, { x, y, w, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 1 Title
{
  const s = pres.addSlide(); n += 1; s.background = { color: NAVY };
  s.addText("RegLens", { x: 0.6, y: 1.35, w: 8, h: 0.9, fontFace: HF, fontSize: 48, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addText("AI Systems Architecture Review", { x: 0.6, y: 2.25, w: 8, h: 0.5, fontFace: BF, fontSize: 22, color: ICE, isTextBox: true, margin: 0 });
  s.addText("Auditable regulatory RAG — cited answers, verified quotes, and a hash-chained trail a reviewer can replay, fully offline", { x: 0.6, y: 2.8, w: 8.6, h: 0.5, fontFace: BF, fontSize: 13, italic: true, color: ICE, isTextBox: true, margin: 0 });
  s.addText("Release/ship date · 12 September 2026 · Roshan Rana", { x: 0.6, y: 4.6, w: 8.8, h: 0.3, fontFace: BF, fontSize: 10, color: MUTED, isTextBox: true, margin: 0 });
  s.addShape(pres.shapes.OVAL, { x: 8.2, y: 1.2, w: 1.1, h: 1.1, fill: { color: MINT }, line: { color: MINT } });
  s.addText("R", { x: 8.2, y: 1.2, w: 1.1, h: 1.1, fontFace: HF, fontSize: 40, bold: true, color: NAVY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}

// ---------- 2 Executive summary
{
  const s = base("Executive summary", "Overview");
  const cols = [
    ["What it is", ["A regulatory question-answering system for compliance teams: hybrid retrieval, exact-citation routing, quote-verified grounded generation, and abstention when evidence is weak.", "Every query is written to a hash-chained audit record with an evidence digest, so a reviewer can replay what the system read before it answered."]],
    ["What it proves", ["Verification is code, not a prompt: citations must resolve to retrieved chunks and quotes must appear in the cited text, checked after generation, every time.", "275 deterministic tests and an offline eval harness — including four adversarial source-instruction cases — run with no API key, no vector database, no model download."]],
    ["Why it is enterprise-ready", ["Fake embeddings, generation and reranking are real implementations bound by default; OpenAI, Qdrant and a cross-encoder reranker are optional layers that fail closed until explicitly configured.", "CI runs the full offline gate (lint, mypy, 275 tests, eval) plus a container-config check on every push."]],
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.9, 3.25);
    s.addText(c[0], { x: x + 0.15, y: 1.4, w: 2.6, h: 0.35, fontFace: HF, fontSize: 15, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    bullets(s, c[1], x + 0.15, 1.85, 2.6, 2.6, 11.5);
  });
  s.addText("Ask of the audience: agree the pilot scope for live OpenAI + Qdrant (cost, latency, model choice), the OCR opt-in path, and the production auth/rate-limit posture.", { x: 0.5, y: 4.7, w: 9, h: 0.45, fontFace: BF, fontSize: 10.5, italic: true, color: INK, isTextBox: true, margin: 0 });
}

// ---------- 3 Problem and users
{
  const s = base("The problem and the users", "Context");
  box(s, 0.5, 1.3, 4.3, 1.75, "The analyst's problem", "A compliance officer gets a question from the trading floor: can we do this? The answer lives in a rulebook, notices and internal policy. A general-purpose chatbot will retrieve roughly the right passage, paraphrase it, cite something, and answer even when the evidence is thin — and leave no record of what it read.", { bs: 10 });
  box(s, 5.2, 1.3, 4.3, 1.75, "The firm's constraints", "A wrong citation is a liability and an unsupported answer is worse than no answer. Anything the tool says may be relied on and later examined, so citations must be structural, evidence must be verified in code, and every answer needs a replayable audit trail.", { bs: 10 });
  table(s, [
    ["Actor", "Needs", "Frequency"],
    ["Compliance analyst (primary)", "A cited answer with retrieval diagnostics, or an honest refusal when evidence is weak", "Several times a day"],
    ["Legal / policy / model-risk reviewer", "Source-level traceability: what evidence, what model, what prompt version, replayable months later", "On review"],
    ["Engineering / platform reviewer", "Deterministic offline tests and eval, fail-closed optional providers, one command to verify", "Deploy / operate"],
    ["Automation and AI assistants", "The same grounded answers over HTTP: /query, /chat (with SSE streaming), audit export", "Ad hoc"],
  ], 0.5, 3.25, 9.0, [2.4, 5.0, 1.6], 9);
}

// ---------- 4 Solution at a glance
{
  const s = base("Solution at a glance", "Approach");
  const steps = [
    ["1", "Ingest", "Markdown, text, HTML, optional PDF, or an allowlisted FINRA URL, chunked so every chunk keeps its rule label and heading path."],
    ["2", "Retrieve & fuse", "BM25 keyword plus dense embeddings fused by Reciprocal Rank Fusion; an exact-citation route pins a named rule's chunks before fusion."],
    ["3", "Generate", "The model gets prompt-local [E1]…[En] evidence markers and must cite them; fake and OpenAI generation share one interface."],
    ["4", "Verify & audit", "Citations must resolve, quotes must appear in evidence, weak evidence abstains, and every query writes a hash-chained audit row."],
  ];
  steps.forEach((st, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.35, 2.15, 2.15, CARD_D, CARD_D);
    s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: 1.5, w: 0.4, h: 0.4, fill: { color: MINT }, line: { color: MINT } });
    s.addText(st[0], { x: x + 0.15, y: 1.5, w: 0.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: NAVY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.65, y: 1.52, w: 1.4, h: 0.36, fontFace: BF, fontSize: 12.5, bold: true, color: WHITE, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(st[2], { x: x + 0.15, y: 2.0, w: 1.85, h: 1.4, fontFace: BF, fontSize: 8.5, color: ICE, isTextBox: true, margin: 0, valign: "top" });
    if (i < 3) arrow(s, x + 2.15, 2.4, x + 2.3, 2.4, MINT, 2);
  });
  box(s, 0.5, 3.75, 4.4, 1.3, "Surfaces", "A dependency-free analyst UI served by FastAPI · JSON API (/retrieve, /query, /admin/ingest, /audit) · /chat with optional Server-Sent Events streaming for app and agent workflows.", { bs: 10 });
  box(s, 5.1, 3.75, 4.4, 1.3, "Two run modes, one contract", "Mock mode (default): fake embeddings, generation and reranker, fully offline, no key, no Qdrant. Local mode: the same code path with Qdrant and, optionally, OpenAI and a cross-encoder reranker behind explicit configuration.", { bs: 10 });
}

// ---------- 5 System context (C4 L1)
{
  const s = base("System context", "Architecture · C4 level 1");
  const actors = [["Compliance analyst", "browser, analyst UI"], ["Reviewer / auditor", "audit export"], ["Automation / agents", "HTTP + SSE client"]];
  actors.forEach((a, i) => { box(s, 0.5, 1.3 + i * 1.05, 1.9, 0.9, a[0], a[1], { bs: 8.5 }); arrow(s, 2.4, 1.75 + i * 1.05, 2.75, 2.85, MUTED, 1); });
  card(s, 2.8, 1.3, 3.5, 3.55, "EEF6F4", MINT);
  s.addText("RegLens", { x: 2.95, y: 1.38, w: 3.2, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  box(s, 2.95, 1.75, 3.2, 0.7, "Surfaces", "Analyst UI (/) · FastAPI JSON routes · /chat + SSE", { bs: 8.5 });
  box(s, 2.95, 2.55, 3.2, 1.15, "Core pipeline", "ingest → chunk → retrieve (BM25 + dense, RRF) → rerank → generate with [E1]… markers → verify citations/quotes → abstain or warn", { bs: 8.5 });
  box(s, 2.95, 3.8, 3.2, 0.9, "Persistence", "SQLite: sources, chunks, query audits, evidence, chat sessions/turns", { bs: 8.5 });
  box(s, 6.8, 1.3, 2.7, 0.8, "OpenAI (optional)", "text-embedding-3-small + gpt-5.4-nano; explicit provider name + key, fails closed otherwise", { bs: 8 });
  box(s, 6.8, 2.25, 2.7, 0.8, "Qdrant (optional)", "local vector store, collection regulatory_chunks, degrades to a structured error if unreachable", { bs: 8 });
  box(s, 6.8, 3.2, 2.7, 0.75, "sentence-transformers (optional)", "cross-encoder reranker, lazily loaded, local-files-only option", { bs: 8 });
  box(s, 6.8, 4.1, 2.7, 0.65, "FINRA URLs (allowlisted)", "finra.org / rules.finra.org, HTTPS only, snapshot stored locally", { bs: 8 });
  arrow(s, 6.3, 3.0, 6.8, 1.7, MUTED, 1); arrow(s, 6.3, 3.1, 6.8, 2.65, MUTED, 1); arrow(s, 6.3, 3.2, 6.8, 3.57, MUTED, 1); arrow(s, 6.3, 3.3, 6.8, 4.42, MUTED, 1);
  s.addText("Mock mode (default) never calls any of the four boxes on the right. Local mode adds Qdrant; OpenAI and the cross-encoder are opt-in extras layered on top, each gated by an explicit setting.", { x: 0.5, y: 4.95, w: 9, h: 0.32, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 6 Component architecture (C4 L2)
{
  const s = base("Component architecture", "Architecture · C4 level 2");
  const groups = [
    { t: "API (surfaces)", x: 0.5, items: [["routes_ui.py", "analyst UI, dependency-free HTML"], ["routes_query.py", "/retrieve, /query, /chat"], ["routes_admin.py", "ingest, ingest-url, documents"], ["routes_audit.py", "audit list/export/verify"]] },
    { t: "Ingestion", x: 2.85, items: [["loaders.py", "markdown/text/html/pdf"], ["chunking.py", "deterministic, citation-preserving"], ["normalizers.py", "citation-key extraction"]] },
    { t: "Retrieval", x: 5.2, items: [["keyword.py", "rule-aware BM25"], ["embeddings.py / qdrant_store.py", "fake or Qdrant-backed dense"], ["fusion.py", "Reciprocal Rank Fusion"], ["service.py", "routing, pinning, trimming"], ["rerank.py / cross_encoder_reranker.py", "fake or cross-encoder"]] },
    { t: "Generation & audit", x: 7.55, items: [["prompts.py", "[E1]… evidence markers"], ["llm.py / openai_llm.py", "fake or OpenAI Responses"], ["citations.py / quote_verifier.py", "resolve + verify"], ["persistence/repositories.py", "hash-chained audit rows"]] },
  ];
  groups.forEach((g) => {
    card(s, g.x, 1.3, 2.15, 3.55);
    s.addText(g.t, { x: g.x + 0.1, y: 1.36, w: 2, h: 0.3, fontFace: BF, fontSize: 10.5, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    const rowH = 3.1 / g.items.length;
    g.items.forEach((it, i) => {
      const y = 1.7 + i * rowH;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: g.x + 0.1, y, w: 1.95, h: rowH - 0.08, fill: { color: WHITE }, line: { color: LINE, width: 0.75 }, rectRadius: 0.05 });
      s.addText(it[0], { x: g.x + 0.17, y: y + 0.03, w: 1.82, h: rowH * 0.5, fontFace: "Courier New", fontSize: 7.5, bold: true, color: NAVY, isTextBox: true, margin: 0 });
      s.addText(it[1], { x: g.x + 0.17, y: y + rowH * 0.46, w: 1.82, h: rowH * 0.5, fontFace: BF, fontSize: 7.5, color: INK, isTextBox: true, margin: 0 });
    });
  });
  arrow(s, 2.65, 3.1, 2.85, 3.1, MINT, 2); arrow(s, 5.0, 3.1, 5.2, 3.1, MINT, 2); arrow(s, 7.35, 3.1, 7.55, 3.1, MINT, 2);
  s.addText("Dependency direction is left to right. Every retrieval and generation provider is chosen by explicit settings, not by which package happens to be importable.", { x: 0.5, y: 4.9, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 7 The critical flow: the answer path
{
  const s = base("The answer path", "Architecture · critical flow");
  const stages = [
    ["Route", "conceptual / citation reference / exact citation, from the question text"],
    ["Retrieve", "BM25 + dense fused by RRF; exact-citation matches pinned before fusion"],
    ["Rerank", "fake lexical reranker, or an optional cross-encoder"],
    ["Trim", "evidence token budget enforced with trim diagnostics on every response"],
    ["Generate", "prompt-local [E1]…[En] markers; fake or OpenAI, one interface"],
    ["Verify", "every citation resolves to a retrieved chunk; every quote is found in it"],
    ["Abstain / warn", "weak evidence → refusal with no citations; source instructions → warning"],
    ["Persist", "hash-chained audit row + evidence digest + deterministic cost estimate"],
  ];
  stages.forEach((st, i) => {
    const col = i % 4, row = Math.floor(i / 4);
    const x = 0.5 + col * 2.3, y = 1.4 + row * 1.7;
    card(s, x, y, 2.15, 1.35, row === 0 ? CARD : "EEF6F4", row === 0 ? LINE : MINT);
    s.addText(`${i + 1}. ${st[0]}`, { x: x + 0.1, y: y + 0.08, w: 1.95, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.1, y: y + 0.4, w: 1.95, h: 0.9, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
    if (col < 3) arrow(s, x + 2.15, y + 0.67, x + 2.3, y + 0.67, MUTED, 1.25);
  });
  arrow(s, 9.0, 2.75, 9.0, 3.1, MUTED, 1.25);
  s.addText("Refusal is a first-class outcome, not an error path: a refusal is the only answer allowed to carry no citations, and the eval measures it (refusal accuracy 100.0%, 0 false abstentions).", { x: 0.5, y: 4.85, w: 9, h: 0.35, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 8 Core mechanism: verify, don't trust
{
  const s = base("Verify, don't trust: the citation and quote contract", "Design · grounding");
  card(s, 0.5, 1.3, 4.6, 3.55, CARD_D, CARD_D);
  s.addText("What must be true for a non-refusal answer", { x: 0.65, y: 1.38, w: 4.3, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: MINT, isTextBox: true, margin: 0 });
  bullets(s, [
    "every cited [E1]…[En] marker must resolve to a chunk that was actually retrieved (citations.py)",
    "every quoted span must literally appear inside that chunk's text, case- and whitespace-normalised (quote_verifier.py)",
    "a non-refusal answer with no citations is rejected; a refusal is the only answer allowed to have none",
  ], 0.65, 1.72, 4.3, 1.9, 9.5, ICE);
  s.addText("Enforced by tests, not by prompt wording", { x: 0.65, y: 3.55, w: 4.3, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: MINT, isTextBox: true, margin: 0 });
  s.addText("test_verify_answer_citations_rejects_fabricated_evidence_id\ntest_verify_answer_citations_rejects_non_retrieved_chunk_citation\ntest_verify_answer_citations_rejects_quote_absent_from_evidence\ntest_non_refusal_answer_without_citations_is_rejected", { x: 0.65, y: 3.85, w: 4.3, h: 0.95, fontFace: "Courier New", fontSize: 7.5, color: WHITE, isTextBox: true, margin: 0, valign: "top" });
  const badges = [["✓ verified", "quote found in the cited, retrieved chunk", MINT], ["✗ rejected", "fabricated evidence id, or a quote not in the chunk", RED], ["⚠ warned", "source text tried to inject an instruction; fact kept, instruction dropped", GOLD], ["◇ abstained", "evidence too weak; refusal allowed to carry no citations", MUTED]];
  badges.forEach((b, i) => {
    const y = 1.3 + i * 0.75;
    card(s, 5.4, y, 4.1, 0.62);
    s.addText(b[0], { x: 5.55, y: y + 0.05, w: 1.5, h: 0.5, fontFace: BF, fontSize: 12, bold: true, color: b[2], isTextBox: true, margin: 0, valign: "middle" });
    s.addText(b[1], { x: 7.0, y: y + 0.05, w: 2.4, h: 0.5, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "middle" });
  });
  box(s, 5.4, 4.2, 4.1, 0.65, "Why this matters", "Citation faithfulness is the eval's headline KPI: 21/21 answers, every quote verified (100.0%).", { bs: 8.5 });
}

// ---------- 9 Data architecture
{
  const s = base("Data architecture: stores, retention, classification", "Architecture · data");
  box(s, 0.5, 1.3, 2.9, 1.9, "SQLite (metadata + audit)", "sources, sections, chunks, query audits, query evidence, chat sessions and turns. Query audit rows are append-only: re-saving an existing query_id is rejected, not updated.", { bs: 9 });
  box(s, 0.5, 3.35, 2.9, 1.5, "Vector store", "In-memory fake embeddings by default (mock mode); an optional Qdrant collection regulatory_chunks in local mode, degrading to a structured error if unreachable.", { bs: 9 });
  arrow(s, 3.4, 2.2, 4.1, 2.2, MINT, 2); arrow(s, 3.4, 4.0, 4.1, 3.2, MINT, 2);
  card(s, 4.1, 1.9, 2.3, 1.7, "EEF6F4", MINT);
  s.addText("Retention rules", { x: 4.2, y: 1.97, w: 2.1, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  bullets(s, ["deleting a source cascades its sections/chunks and refreshes retrieval", "deleting a chat session removes history but keeps its query audits", "audits are immutable by design; chat history is not"], 4.2, 2.3, 2.1, 1.2, 8);
  box(s, 6.6, 1.3, 2.9, 3.55, "Classification and provenance", "Every chunk carries its source_id, checksum, corpus_id/version and heading path. Remote (FINRA URL) ingestion snapshots raw bytes locally under REGLENS_DOCUMENT_STORAGE_PATH before chunking, so provenance does not depend on the live page. reglens.db and reports/ are demo-local and gitignored; a production deployment swaps SQLite for a managed store without touching the audit-hash contract.", { bs: 9 });
  s.addText("The bundled synthetic_rulebook.md fixture (11 sections/chunks) is what the eval and the screenshots in this deck run against; the schema is the same one a real rulebook would use.", { x: 0.5, y: 4.95, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 10 Integration / provider / live-mode design
{
  const s = base("Provider and live-mode design: fail closed by default", "Architecture · integration");
  box(s, 0.5, 1.3, 2.9, 1.7, "OpenAI (optional)", "install .[openai], set an explicit provider name and OPENAI_API_KEY; text-embedding-3-small + gpt-5.4-nano, capped output tokens, bounded embedding cache keyed by provider/model/dims/hash.", { bs: 8.5 });
  box(s, 3.55, 1.3, 2.9, 1.7, "Qdrant (optional)", "install .[qdrant], REGLENS_RAG_MODE=local; a separate collection per embedding-dimension change; unreachable Qdrant degrades /ready, not startup.", { bs: 8.5 });
  box(s, 6.6, 1.3, 2.9, 1.7, "Cross-encoder (optional)", "install .[rerank]; ms-marco-MiniLM-L-6-v2, lazily loaded on first use; REGLENS_CROSS_ENCODER_LOCAL_FILES_ONLY avoids a network fetch.", { bs: 8.5 });
  box(s, 0.5, 3.15, 4.65, 1.7, "The fail-closed test", "Mock mode rejects live-provider flags outright; setting OPENAI_API_KEY alone enables nothing. `test_openai_api_key_env_does_not_enable_live_providers_by_itself` and `test_provider_factories_do_not_import_openai_sdk_when_api_key_is_missing` make the boundary a test, not a convention.", { bs: 9 });
  box(s, 5.35, 3.15, 4.15, 1.7, "FINRA URL ingestion", "POST /admin/ingest-url accepts only HTTPS finra.org / www.finra.org / rules.finra.org, validates the final redirect host, caps response bytes, snapshots raw bytes locally, then runs the normal ingest/chunk/audit path.", { bs: 9 });
  s.addText("Every optional branch returns a structured dependency_unavailable error rather than crashing at startup when its package, key, quota or model is missing.", { x: 0.5, y: 4.95, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 11 Design choices
{
  const s = base("Design choices and why", "Design decisions");
  table(s, [
    ["Decision", "Alternatives considered", "Why this one"],
    ["Verification in code after generation, not in the prompt", "Trust the model to cite correctly; rely on prompt wording alone", "A wrong citation in compliance is a liability the prompt cannot guarantee away; a code check can be tested and is enforced on every answer"],
    ["Fake providers are real implementations, bound by default", "Mocked test doubles that do not resemble production behaviour", "275 tests, the eval harness and the UI all run offline with no key; the same interface later carries a live provider"],
    ["Hybrid BM25 + dense fused by RRF; Qdrant optional", "Dense-only retrieval; a vector database required from day one", "Works fully in-memory in mock mode; Qdrant is additive for local/production scale, not a hard dependency"],
    ["Prompt-local [E1]…[En] evidence markers", "Free-form citations inside the generated answer text", "Markers exist only in the prompt, so every citation the model produces must resolve to something the system actually retrieved"],
    ["Only a refusal may lack citations", "Allow any answer to omit citations when the model is unsure", "Makes 'no evidence' and 'unsupported claim' distinguishable in code, not just in tone"],
    ["OCR deferred, scanned PDFs fail closed", "Best-effort OCR bundled into default PDF ingestion", "Uncertain OCR text must not silently enter a compliance answer without an explicit confidence and audit policy (docs/ocr-strategy.md)"],
    ["SQLite for metadata and audit", "PostgreSQL from the first line of code", "Zero-infrastructure local development and CI; the audit hash-chain is a code invariant, not tied to a specific store"],
  ], 0.5, 1.3, 9.0, [2.7, 2.9, 3.4], 8.5);
}

// ---------- 12 Major features
{
  const s = base("Major features", "Product");
  const feats = [
    ["Citation-preserving ingestion", "Markdown, text, HTML, optional PDF with page numbers, plus allowlisted FINRA URL ingestion that snapshots raw bytes"],
    ["Hybrid retrieval with exposed diagnostics", "BM25 + dense fused by RRF, exact-citation pinning, optional reranking; every response carries dense/keyword/fusion scores"],
    ["Grounded, verified generation", "Prompt-local evidence markers; citation and quote verification in code after every generation call"],
    ["Weak-evidence abstention and safety warnings", "Refusal when evidence is thin; adversarial source-instruction text is filtered and warned on, never obeyed"],
    ["Hash-chained audit trail", "Append-only query audits with evidence digests; JSON/Markdown export; /audit/verify walks the chain"],
    ["Durable chat with SSE streaming", "/chat sessions persist in SQLite, link to immutable audits, and export as reviewer-friendly transcripts"],
  ];
  feats.forEach((f, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    box(s, 0.5 + col * 4.55, 1.3 + row * 1.28, 4.35, 1.14, f[0], f[1], { bs: 9 });
  });
}

// ---------- 13 Screenshot: cited answer
{
  const s = base("A cited answer, verified against retrieved evidence", "Screenshots · analyst UI, mock mode");
  imgFit(s, ASSETS + "13-cited-answer.png", 0.5, 1.25, 9.0, 3.55, 1440, 749);
  caption(s, "\"How long must records be retained?\" against the bundled synthetic rulebook. FINRA Rule 1030(b) is cited, its quote is verified, and the provenance panel shows the audit hash chain and evidence digest.", 0.5, 4.9, 9);
}

// ---------- 14 Screenshot: abstention
{
  const s = base("Weak evidence produces a refusal, not a guess", "Screenshots · analyst UI, mock mode");
  imgFit(s, ASSETS + "14-abstention.png", 0.5, 1.25, 9.0, 3.0, 1050, 581);
  box(s, 0.5, 4.4, 9.0, 0.75, "What you are looking at", "\"What is the weather like in Miami this weekend?\" retrieves only weakly related evidence; the system abstains with a weak_retrieval warning and zero citations, and the chat history shows both turns side by side.", { bs: 8.5 });
}

// ---------- 15 Screenshot: eval + test terminal
{
  const s = base("The offline gate: tests, eval and the audit chain", "Screenshots · terminal, this task run");
  imgFit(s, ASSETS + "15-eval-terminal.png", 0.5, 1.25, 9.0, 3.5, 1200, 630);
  caption(s, "Commands run for this deck: the default pytest marker set (275 passed, 5 deselected), the eval harness (writes metrics/headline.json), and /audit/verify against the running server.", 0.5, 4.85, 9);
}

// ---------- 16 Screenshot: OpenAPI docs
{
  const s = base("Every route is a typed, documented contract", "Screenshots · FastAPI /docs, mock mode");
  imgFit(s, ASSETS + "16-openapi-docs.png", 0.5, 1.25, 9.0, 3.55, 1440, 900);
  caption(s, "Auto-generated OpenAPI 3.1 documentation for the running service on port 8604: health/readiness, chat sessions, retrieval, query and audit routes.", 0.5, 4.9, 9);
}

// ---------- 17 Security and compliance
{
  const s = base("Security and compliance controls", "Enterprise readiness · controls");
  table(s, [
    ["Boundary", "Threat", "Control in the code", "Evidence"],
    ["B1 user question", "prompt injection through the question text", "question length bound; routing and retrieval do not execute instructions found in input", "eval safety cases"],
    ["B2 source documents", "instructions embedded inside ingested regulatory text", "instruction clauses are filtered and warned on without dropping the factual clause in the same sentence", "4 adversarial eval cases, warning_recall 100.0%"],
    ["B3 API auth and rate limit", "unauthenticated or unbounded access to operational routes", "optional API-key auth (header or bearer) + per-minute rate limiting; health/ready/docs stay exempt", "test_api_key_auth_protects_operational_routes_but_not_health"],
    ["B4 remote ingestion", "fetching or redirecting to an untrusted host", "HTTPS-only, FINRA domain allowlist, byte-size cap, final-redirect host validated, snapshot stored locally", "OPERATIONS.md ingest-url contract"],
    ["B5 live providers", "a stray key or flag silently enabling a live model", "mock mode rejects live-provider flags outright; a key alone enables nothing", "test_openai_api_key_env_does_not_enable_live_providers_by_itself"],
    ["B6 audit integrity", "edited or deleted evidence rows after the fact", "append-only query audits, hash chain plus evidence digest, /audit/verify detects tampering", "GET /audit/verify"],
  ], 0.5, 1.3, 9.0, [1.35, 2.3, 3.55, 1.8], 8);
  s.addText("Residual risks, stated: API-key auth and in-memory rate limiting are local controls, not an identity system; OCR for scanned PDFs is deferred and fails closed rather than guessing.", { x: 0.5, y: 4.7, w: 9, h: 0.4, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 18 Enterprise readiness: process
{
  const s = base("How it was built: 13 waves behind one gate", "Enterprise readiness · process");
  const waves = ["W1 foundation", "W2 retrieval loop", "W3 audited answers", "W4 quality gates", "W5 local ingestion", "W6 provider scaffold", "W7 OpenAI live", "W8 cross-encoder", "W9 chat API", "W10 chat sessions", "W11 audit↔chat", "W12 transcripts", "W13 hardening"];
  waves.forEach((g, i) => {
    const x = 0.5 + i * 0.71;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.35, w: 0.65, h: 0.62, fill: { color: i < 9 ? CARD_D : "1E5C57" }, line: { color: i < 9 ? CARD_D : "1E5C57" }, rectRadius: 0.05 });
    s.addText(g, { x: x + 0.02, y: 1.37, w: 0.61, h: 0.58, fontFace: BF, fontSize: 6, bold: true, color: WHITE, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  });
  const stats = [["275", "deterministic fake-mode tests, plus 5 deselected optional-profile tests"], ["13", "build waves, each shipped behind the same offline gate"], ["21", "eval fixture cases, including 4 adversarial source-instruction safety cases"], ["2", "CI jobs on every push: default-verify (lint, mypy, tests, eval, card-drift) and container-verify"]];
  stats.forEach((st, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 2.2, 2.15, 1.25);
    s.addText(st[0], { x: x + 0.12, y: 2.25, w: 1.9, h: 0.5, fontFace: HF, fontSize: 28, bold: true, color: GOLD, isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.12, y: 2.75, w: 1.9, h: 0.65, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
  });
  box(s, 0.5, 3.65, 4.4, 1.25, "One command validates everything", "`make verify` = ruff lint + mypy strict + the default pytest marker set + the eval harness. CI runs the same profile via `python -m scripts.verify default`, plus a README results-card drift check.", { bs: 9 });
  box(s, 5.1, 3.65, 4.4, 1.25, "Deterministic-first, live optional", "Fake embeddings, generation and reranker are real implementations satisfying the same interface as live providers, so the whole gate — UI included — never needs a key, a vector DB, or a model download.", { bs: 9 });
}

// ---------- 19 Quality metrics (native chart)
{
  const s = base("Quality metrics from the gate", "Enterprise readiness · measurement");
  s.addChart(pres.charts.BAR, [{ name: "Value", labels: ["Recall@5", "Citation faithfulness", "Refusal accuracy", "Answer safety", "Audit completeness"], values: [1.0, 1.0, 1.0, 1.0, 1.0] }], {
    x: 0.5, y: 1.3, w: 5.2, h: 3.5, barDir: "bar", chartColors: [MINT], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 9, dataLabelColor: INK,
    catAxisLabelColor: INK, catAxisLabelFontSize: 9, valAxisLabelColor: MUTED, valAxisLabelFontSize: 8, valAxisMinVal: 0, valAxisMaxVal: 1.1, valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, showTitle: true, title: "Ratios, 21-case fixture (1.0 = target met)", titleFontSize: 10, titleColor: NAVY,
  });
  table(s, [
    ["KPI", "Value", "How measured"],
    ["Tests", "275 passed, 5 deselected", "default pytest marker set, this run"],
    ["Abstention rate", "14.3% (3/21), 0 false abstentions", "make eval, this run"],
    ["Citation faithfulness", "100.0% (21/21)", "make eval, this run"],
    ["Recall@5 reranker ON vs OFF", "100.0% vs 94.4% (n=18)", "headline.json bars"],
    ["Cost / query (fake-run model)", "$0.000202", "repo costing model, observed"],
    ["Avg eval latency", "5.8 ms (in-process, fake providers)", "make eval, this run"],
    ["Live OpenAI cost / cross-encoder", "pending", "needs a key / a model download"],
  ], 5.9, 1.3, 3.6, [1.65, 1.15, 0.8], 7.5);
  s.addText("All five ratios read 1.0 on the 21-case offline fixture; the honest caveat is the corpus is 15 chunks and the embeddings are deterministic lexical hashes, not a production-scale semantic benchmark.", { x: 0.5, y: 4.9, w: 9, h: 0.35, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 20 Quirks and limitations
{
  const s = base("Quirks and known limitations (stated, not hidden)", "Honesty");
  const q = [
    ["100.0% recall/faithfulness is a small-fixture number", "21 queries over a 15-chunk synthetic corpus with deterministic lexical embeddings; not a production-scale or semantic benchmark."],
    ["Live OpenAI cost is pending", "The $0.000202/query figure is the repo's char/4-token costing model over fake-generated text, not a metered API call."],
    ["Cross-encoder reranker is unmeasured", "ms-marco-MiniLM-L-6-v2 needs sentence-transformers and a model weight download; the offline gate never fetches it."],
    ["OCR is a contract, not an implementation", "Scanned/image PDFs return corpus_load_error by design; docs/ocr-strategy.md is a deferred, explicit decision."],
    ["Local controls, not an identity system", "API-key auth and in-memory rate limiting are single-process; no SSO, no tenant isolation, no multi-instance limiter."],
    ["reglens.db, tmp/ and reports/ are gitignored", "The demo database and reports regenerate from `make eval`/ingestion; this deck's screenshots came from a fresh run."],
    ["The bundled rulebook is synthetic", "FINRA rule numbers and text in the fixture are illustrative for testing, not the live FINRA rulebook."],
    ["Container check is static", "`scripts.verify container` renders and validates Docker Compose config; this task did not build or run the image."],
  ];
  q.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    box(s, 0.5 + col * 4.6, 1.3 + row * 0.9, 4.45, 0.82, it[0], it[1], { bs: 8, ts: 9.5 });
  });
}

// ---------- 21 Cost and performance
{
  const s = base("Cost, performance and operability", "Enterprise readiness · operations");
  const cards = [["$0.0002", "mean fake-run cost per query, repo costing model, ~792 in / 34 out tokens"], ["5.8 ms", "average eval latency, in-process fake providers, 21 cases"], ["21", "fixture queries over a 15-chunk synthetic corpus, 2 corpora, seed 0"], ["0 keys", "needed for the full offline demo — mock mode, no OpenAI, no Qdrant"]];
  cards.forEach((c, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.3, 2.15, 1.35);
    s.addText(c[0], { x: x + 0.12, y: 1.35, w: 1.9, h: 0.5, fontFace: HF, fontSize: 22, bold: true, color: GOLD, isTextBox: true, margin: 0 });
    s.addText(c[1], { x: x + 0.12, y: 1.87, w: 1.9, h: 0.75, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
  });
  box(s, 0.5, 2.85, 4.4, 2.0, "Operability", "• /health and /ready with per-provider status, mode and gated errors\n• `make verify` is the one-command gate; CI runs the same profile\n• Docker + Compose default to mock-safe (no key, no Qdrant needed)\n• Rollback is an environment variable: REGLENS_RAG_MODE mock ↔ local\n• `scripts.verify container` statically checks the Compose config", { bs: 9 });
  box(s, 5.1, 2.85, 4.4, 2.0, "Observability and audit", "• Hash-chained query audit rows with an evidence digest per query\n• GET /audit/verify walks the chain and reports failures, if any\n• Request-ID propagation (X-Request-ID) through every response\n• Structured dependency_unavailable errors, never a bare crash\n• Deterministic cost estimate stored on every audit row", { bs: 9 });
}

// ---------- 22 Roadmap
{
  const s = base("Roadmap to a pilot", "Next steps");
  const phases = [["Weeks 1–2", "Harden data", ["OCR as an explicit opt-in extra, behind REGLENS_ENABLE_PDF_OCR", "PostgreSQL for production metadata and audit storage", "Richer corpus version diffing"]], ["Weeks 3–4", "Secure and scale", ["SSO / RBAC in front of the API", "Tenant isolation for multi-firm deployments", "Durable async ingestion workers for larger corpora"]], ["Weeks 5–6", "Measure on live", ["A live OpenAI cost and quality run to replace the pending figures", "Cross-encoder reranker evaluated on a non-synthetic corpus", "Source-page citation highlighting in the UI"]], ["Week 7+", "Operate", ["OpenTelemetry / Prometheus-style observability", "A tamper-evident audit sink (external anchor for the hash chain)", "Managed deployment path for client infrastructure"]]];
  phases.forEach((p, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.3, 2.15, 3.5, i === 0 ? "EEF6F4" : CARD, i === 0 ? MINT : LINE);
    s.addText(p[0], { x: x + 0.12, y: 1.36, w: 1.9, h: 0.28, fontFace: BF, fontSize: 9, bold: true, color: MINT, charSpacing: 1, isTextBox: true, margin: 0 });
    s.addText(p[1], { x: x + 0.12, y: 1.62, w: 1.9, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    bullets(s, p[2], x + 0.12, 2.05, 1.9, 2.7, 8.5);
  });
  s.addText("Everything above is additive: the verifier, the abstention rule and the audit-chain contract do not change.", { x: 0.5, y: 4.95, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 23 Appendix: decision log
{
  const s = base("Appendix A — Decision log (abridged)", "Appendix");
  table(s, [
    ["Area", "Decision", "Consequence"],
    ["Grounding", "Citations and quotes verified in code after generation, not asserted by the prompt", "citations.py / quote_verifier.py; four rejection tests; citation faithfulness is a measured KPI"],
    ["Refusal", "Only a refusal may carry zero citations; any other answer without one is rejected", "Weak evidence produces an honest abstention instead of a confident guess"],
    ["Providers", "Fake embeddings/LLM/reranker are real implementations bound by default", "275 tests + eval + UI run with no key, no Qdrant, no model download"],
    ["Providers", "Live providers fail closed: a key alone never enables them", "test_openai_api_key_env_does_not_enable_live_providers_by_itself"],
    ["Retrieval", "Hybrid BM25 + dense via RRF; exact-citation queries are pinned before fusion", "A question naming a rule number always sees that rule's chunks first"],
    ["Ingestion", "Remote ingestion is HTTPS-only and allowlisted to FINRA domains, with a local snapshot", "Provenance for remote sources does not depend on the live page staying reachable"],
    ["Audit", "Query audit rows are append-only; re-saving an existing query_id is rejected", "The audit trail cannot be silently edited by a retry or a bug"],
    ["Scope", "OCR is a documented, deferred decision; scanned PDFs fail closed", "No uncertain OCR text can enter a compliance answer without an explicit policy"],
  ], 0.5, 1.3, 9.0, [1.1, 4.6, 3.3], 8);
}

// ---------- 24 Appendix: process stats and lessons
{
  const s = base("Appendix B — Build statistics and lessons", "Appendix");
  table(s, [
    ["Item", "Value"],
    ["Build waves (docs/CHANGELOG.md)", "13, Wave 1 (foundation) through Wave 13 (production hardening)"],
    ["Tests, default marker set", "275 passed, 5 deselected (live_openai, requires_browser, requires_qdrant, requires_model_download)"],
    ["Eval fixture", "21 cases (14 answerable, 3 out-of-scope, 4 adversarial source-instruction safety) over 2 corpora"],
    ["CI jobs", "default-verify (lint, mypy, tests, eval, README card drift) and container-verify, on every push/PR"],
    ["Optional profiles", "test-browser, test-qdrant, test-models, test-container, verify-openai, verify-full-local"],
    ["Lines of code (app/ + tests/)", "≈ 19,600 across 123 files"],
  ], 0.5, 1.3, 9.0, [3.2, 5.8], 8.5);
  box(s, 0.5, 3.55, 9.0, 1.35, "Lessons the design carries forward", "• Verification belongs in code that runs after generation, not in prompt instructions the model can drift away from.\n• A fake provider must satisfy the real interface, or the tests it enables are not proving anything about production.\n• An audit trail is only trustworthy if the store rejects edits at the boundary (append-only), not by convention.\n• Optional heavy dependencies (Qdrant, OpenAI, cross-encoder) should fail closed with a structured error, never a crash.", { bs: 9 });
}

// ---------- 25 Appendix: repository map
{
  const s = base("Appendix C — Repository map and how to run", "Appendix");
  s.addText(["app/                FastAPI app: main.py, core (config, security,", "                    costing, errors), domain (ids, models)", "app/api/            routes_ui, routes_query, routes_admin, routes_audit", "app/ingestion/      loaders, chunking, normalizers", "app/retrieval/      keyword (BM25), embeddings, qdrant_store, fusion,", "                    rerank, cross_encoder_reranker, service", "app/generation/     prompts, llm, openai_llm, citations, quote_verifier,", "                    warnings, service", "app/persistence/    db, repositories (SQLite: sources, audits, chat)", "app/evals/          fixtures/, metrics.py, headline.py", "tests/              275 default tests (unit, integration, e2e)", "scripts/            run_evals.py, verify.py", "metrics/            headline.json, render.py (README card, drift-checked)", "docs/                OVERVIEW, SHOWCASE, OPERATIONS, CHANGELOG,", "                    ocr-strategy, project brief, this deck"].join("\n"), { x: 0.5, y: 1.3, w: 5.6, h: 3.3, fontFace: "Courier New", fontSize: 7.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
  card(s, 6.3, 1.3, 3.2, 3.55, CARD_D, CARD_D);
  s.addText("Run it", { x: 6.45, y: 1.38, w: 3, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: MINT, isTextBox: true, margin: 0 });
  s.addText(["python -m venv .venv", "make install", "make verify", "python -m uvicorn app.main:app --reload", "", "# ingest the bundled fixture", "curl -X POST :8000/admin/ingest \\", "  -d '{\"path\":\"app/evals/fixtures/...\"}'", "", "# optional: local mode with Qdrant", "export REGLENS_RAG_MODE=local", "make qdrant-up", "", "# optional: live OpenAI", "export OPENAI_API_KEY=<key>", "make verify-openai"].join("\n"), { x: 6.45, y: 1.72, w: 3, h: 3.05, fontFace: "Courier New", fontSize: 8, color: WHITE, isTextBox: true, margin: 0, valign: "top" });
}

// ---------- 26 Close
{
  const s = dark("Questions", "RegLens · roshanrana/RegLens · main branch · README, OVERVIEW, SHOWCASE and OPERATIONS in the repository");
}

pres.writeFile({ fileName: "C:/Code-Central/RegLens/docs/pitch/reglens-architecture-deck.pptx" }).then((f) => console.log("wrote", f, "slides", n));
