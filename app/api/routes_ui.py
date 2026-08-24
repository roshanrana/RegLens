from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])


@router.get("/", include_in_schema=False, response_class=HTMLResponse)
def policy_copilot_ui() -> HTMLResponse:
    return HTMLResponse(_UI_HTML)


_UI_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RegLens Policy Copilot</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #18212f;
      --muted: #647086;
      --line: #d9e0ea;
      --panel: #ffffff;
      --soft: #f5f7fa;
      --accent: #0b6bcb;
      --accent-dark: #084f99;
      --ok: #166534;
      --warn: #9a3412;
      --bad: #991b1b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--soft);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 28px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 24px; font-weight: 700; }
    h2 { font-size: 16px; margin-bottom: 12px; }
    h3 { font-size: 14px; margin-bottom: 8px; }
    .status-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .shell {
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 18px;
      padding: 18px;
      max-width: 1500px;
      margin: 0 auto;
    }
    aside, main section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    aside { padding: 16px; align-self: start; }
    main { display: grid; gap: 18px; min-width: 0; }
    section { padding: 18px; }
    label {
      display: grid;
      gap: 6px;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    input, select, textarea {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      color: var(--ink);
      background: #fff;
      font: inherit;
      font-size: 14px;
    }
    textarea {
      min-height: 92px;
      resize: vertical;
      line-height: 1.45;
    }
    button {
      min-height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 8px 12px;
      color: #fff;
      background: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-dark); }
    button.secondary {
      color: var(--accent);
      background: #fff;
    }
    button.secondary:hover { color: var(--accent-dark); background: #edf5ff; }
    button.danger {
      border-color: #b91c1c;
      background: #b91c1c;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .muted { color: var(--muted); font-size: 13px; line-height: 1.45; }
    .notice {
      display: none;
      margin-top: 12px;
      border-radius: 6px;
      padding: 10px 12px;
      font-size: 13px;
      line-height: 1.45;
    }
    .notice.show { display: block; }
    .notice.ok { color: var(--ok); background: #ecfdf3; border: 1px solid #bbf7d0; }
    .notice.warn { color: var(--warn); background: #fff7ed; border: 1px solid #fed7aa; }
    .notice.bad { color: var(--bad); background: #fef2f2; border: 1px solid #fecaca; }
    .source-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
      max-height: 360px;
      overflow: auto;
    }
    .source-row {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .source-row strong { font-size: 13px; }
    .source-row small { color: var(--muted); overflow-wrap: anywhere; }
    .answer {
      white-space: pre-wrap;
      line-height: 1.55;
      font-size: 15px;
    }
    .result-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
      gap: 18px;
      align-items: start;
    }
    .item {
      border-top: 1px solid var(--line);
      padding-top: 12px;
      margin-top: 12px;
    }
    .item:first-child { border-top: 0; padding-top: 0; margin-top: 0; }
    .citation-title {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    .snippet {
      color: var(--muted);
      line-height: 1.45;
      overflow-wrap: anywhere;
    }
    .kv-grid {
      display: grid;
      grid-template-columns: minmax(90px, 130px) minmax(0, 1fr);
      gap: 6px 10px;
      font-size: 12px;
      line-height: 1.35;
    }
    .kv-grid dt { color: var(--muted); font-weight: 700; }
    .kv-grid dd { margin: 0; overflow-wrap: anywhere; }
    details {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fff;
    }
    summary { cursor: pointer; font-weight: 700; }
    pre {
      overflow: auto;
      margin: 12px 0 0;
      padding: 12px;
      border-radius: 6px;
      background: #101827;
      color: #dbeafe;
      font-size: 12px;
      line-height: 1.45;
    }
    .hidden { display: none; }
    @media (max-width: 920px) {
      header { align-items: flex-start; flex-direction: column; padding: 16px; }
      .shell { grid-template-columns: 1fr; padding: 12px; }
      .result-grid, .grid-2 { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>RegLens</h1>
      <p class="muted">Policy Copilot for cited regulatory answers</p>
    </div>
    <div class="status-row">
      <span class="pill" id="health-pill">Checking API</span>
      <span class="pill">Mock-safe</span>
      <span class="pill">Hash-chained audit</span>
    </div>
  </header>

  <div class="shell">
    <aside>
      <h2>Sources</h2>
      <form id="ingest-form">
        <label>Local path
          <input name="path" value="app/evals/fixtures/synthetic_rulebook.md" required>
        </label>
        <div class="grid-2">
          <label>Input type
            <select name="input_type">
              <option value="markdown">Markdown</option>
              <option value="text">Text</option>
              <option value="html">HTML</option>
              <option value="pdf">PDF</option>
            </select>
          </label>
          <label>Version
            <input name="version" value="2026-demo">
          </label>
        </div>
        <label>Corpus ID
          <input name="corpus_id" value="demo-finra">
        </label>
        <label>Corpus name
          <input name="corpus_name" value="Demo FINRA Rulebook">
        </label>
        <div class="actions">
          <button type="submit">Ingest</button>
          <button type="button" class="secondary" id="refresh-sources">Refresh</button>
        </div>
      </form>
      <div id="ingest-notice" class="notice"></div>
      <div id="source-list" class="source-list"></div>
      <div class="item">
        <h2>Lifecycle</h2>
        <div id="source-events"></div>
      </div>
    </aside>

    <main>
      <section>
        <h2>Ask</h2>
        <form id="query-form">
          <label>Question
            <textarea name="question" required>How long must records be retained?</textarea>
          </label>
          <div class="grid-2">
            <label>Source filter
              <select id="source-filter" name="source_filter">
                <option value="">All indexed sources</option>
              </select>
            </label>
            <label>Evidence count
              <input name="top_k" type="number" min="1" max="20" value="3">
            </label>
          </div>
          <div class="actions">
            <button type="submit">Ask</button>
            <button type="button" class="secondary" id="new-chat">New chat</button>
            <button type="button" class="secondary" id="refresh-chats">Refresh chats</button>
            <button type="button" class="secondary" id="export-chat">Export chat</button>
            <button type="button" class="secondary" id="verify-audit">Verify audit</button>
          </div>
        </form>
        <p class="muted" id="chat-session-label">New chat session</p>
        <div id="query-notice" class="notice"></div>
      </section>

      <section>
        <h2>Chat History</h2>
        <div class="grid-2">
          <div>
            <h3>Sessions</h3>
            <div id="chat-sessions" class="source-list"></div>
          </div>
          <div>
            <h3>Turns</h3>
            <div id="chat-turns" class="source-list"></div>
          </div>
        </div>
      </section>

      <section id="result-section" class="hidden">
        <div class="result-grid">
          <div>
            <h2>Answer</h2>
            <div id="answer" class="answer"></div>
            <div id="warnings"></div>
            <div class="item">
              <h3>Citations</h3>
              <div id="citations"></div>
            </div>
            <div class="item">
              <h3>Provenance</h3>
              <div id="provenance"></div>
              <div class="actions">
                <button type="button" class="secondary" id="export-json">JSON</button>
                <button type="button" class="secondary" id="export-markdown">Markdown</button>
              </div>
            </div>
          </div>
          <div>
            <h2>Evidence</h2>
            <div id="evidence"></div>
            <div class="item">
              <details>
                <summary>Diagnostics</summary>
                <pre id="diagnostics"></pre>
              </details>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const state = { sources: [], sessions: [], lastQuery: null, chatSessionId: null };

    const el = (id) => document.getElementById(id);

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      const payload = await response.json();
      if (!response.ok) {
        const message = payload.error?.message || `Request failed: ${response.status}`;
        throw new Error(message);
      }
      return payload;
    }

    function notice(target, kind, message) {
      target.className = `notice show ${kind}`;
      target.textContent = message;
    }

    function clearNotice(target) {
      target.className = "notice";
      target.textContent = "";
    }

    function formPayload(form) {
      return Object.fromEntries(new FormData(form).entries());
    }

    async function loadHealth() {
      try {
        const payload = await api("/ready");
        el("health-pill").textContent = `${payload.service}: ${payload.status}`;
      } catch {
        el("health-pill").textContent = "API unavailable";
      }
    }

    async function loadSources() {
      const payload = await api("/sources");
      state.sources = payload.sources || [];
      renderSources();
      await loadSourceEvents();
    }

    async function loadChatSessions() {
      const payload = await api("/chat/sessions");
      state.sessions = payload.sessions || [];
      renderChatSessions();
      if (state.chatSessionId) {
        await loadChatSession(state.chatSessionId);
      }
    }

    async function loadChatSession(sessionId) {
      const payload = await api(`/chat/sessions/${encodeURIComponent(sessionId)}`);
      state.chatSessionId = payload.session.session_id;
      updateChatLabel(payload.session);
      renderChatTurns(payload.turns || []);
    }

    async function loadSourceEvents(sourceId = "") {
      const suffix = sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : "";
      const payload = await api(`/audit/source-events${suffix}`);
      renderSourceEvents(payload.events || []);
    }

    function renderSources() {
      const list = el("source-list");
      const filter = el("source-filter");
      list.innerHTML = "";
      filter.innerHTML = '<option value="">All indexed sources</option>';

      if (state.sources.length === 0) {
        list.innerHTML = '<p class="muted">No persisted sources.</p>';
        return;
      }

      for (const source of state.sources) {
        const option = document.createElement("option");
        option.value = `${source.corpus_id}|||${source.corpus_version || ""}`;
        option.textContent = `${source.corpus_id} (${source.corpus_version || "unversioned"})`;
        filter.append(option);

        const row = document.createElement("div");
        row.className = "source-row";
        row.innerHTML = `
          <strong>${escapeHtml(source.title)}</strong>
          <small>${escapeHtml(source.corpus_id)} / ${escapeHtml(source.corpus_version)}</small>
          <small>${escapeHtml(source.source_id)}</small>
          <div class="actions">
            <button type="button" class="secondary select-source"
              data-filter="${escapeHtml(option.value)}">Select</button>
            <button type="button" class="danger delete-source"
              data-source-id="${escapeHtml(source.source_id)}">Delete</button>
          </div>
        `;
        list.append(row);
      }
    }

    function renderSourceEvents(events) {
      const target = el("source-events");
      if (!events.length) {
        target.innerHTML = '<p class="muted">No lifecycle events.</p>';
        return;
      }
      target.innerHTML = events.slice(0, 6).map((event) => `
        <div class="item">
          <div class="citation-title">
            <span>${escapeHtml(event.action)} / ${escapeHtml(event.status)}</span>
            <span>${escapeHtml(event.actor)}</span>
          </div>
          <p class="snippet">${escapeHtml(event.source_id || event.job_id || event.event_id)}</p>
          <p class="snippet">${escapeHtml(event.request_id)}</p>
        </div>
      `).join("");
    }

    function renderChatSessions() {
      const target = el("chat-sessions");
      if (!state.sessions.length) {
        target.innerHTML = '<p class="muted">No chat sessions.</p>';
        renderChatTurns([]);
        return;
      }
      target.innerHTML = state.sessions.slice(0, 8).map((session) => `
        <div class="source-row">
          <strong>${escapeHtml(session.title)}</strong>
          <small>${escapeHtml(session.turn_count)} turns</small>
          <small>${escapeHtml(session.session_id)}</small>
          <div class="actions">
            <button type="button" class="secondary select-chat"
              data-session-id="${escapeHtml(session.session_id)}">Select</button>
            <button type="button" class="danger delete-chat"
              data-session-id="${escapeHtml(session.session_id)}">Delete</button>
          </div>
        </div>
      `).join("");
    }

    function renderChatTurns(turns) {
      const target = el("chat-turns");
      if (!turns.length) {
        target.innerHTML = '<p class="muted">No turns selected.</p>';
        return;
      }
      target.innerHTML = turns.map((turn) => `
        <div class="source-row">
          <strong>${escapeHtml(turn.turn_index + 1)}. ${escapeHtml(turn.question)}</strong>
          <small>${escapeHtml(turn.confidence)} / ${escapeHtml(turn.query_id)}</small>
          <p class="snippet">${escapeHtml(turn.answer)}</p>
        </div>
      `).join("");
    }

    function updateChatLabel(session) {
      if (!session) {
        el("chat-session-label").textContent = "New chat session";
        return;
      }
      el("chat-session-label").textContent = `${session.title} / ${session.session_id}`;
    }

    function selectedScope() {
      const value = el("source-filter").value;
      if (!value) return {};
      const [corpusId, corpusVersion] = value.split("|||");
      return {
        corpus_id: corpusId || null,
        corpus_version: corpusVersion || null,
      };
    }

    function renderQueryResult(payload) {
      state.lastQuery = payload;
      el("result-section").classList.remove("hidden");
      el("answer").textContent = payload.answer;
      el("diagnostics").textContent = JSON.stringify(payload.diagnostics, null, 2);
      renderProvenance(payload);

      const warnings = el("warnings");
      warnings.innerHTML = "";
      const warningDetails = payload.warning_details || (payload.warnings || []).map((warning) => ({
        code: warning,
        severity: "medium",
        message: warning,
      }));
      for (const warning of warningDetails) {
        const item = document.createElement("div");
        const kind = warningKind(warning.severity);
        item.className = `notice show ${kind}`;
        item.textContent = `${warning.code}: ${warning.message}`;
        warnings.append(item);
      }

      el("citations").innerHTML = (payload.citations || []).map((citation) => `
        <div class="item">
          <div class="citation-title">
            <span>${escapeHtml(citation.citation_label)}</span>
            <span>${escapeHtml(citation.verification_status)}</span>
          </div>
          <p class="snippet">${escapeHtml(citation.quoted_text || "")}</p>
        </div>
      `).join("") || '<p class="muted">No citations returned.</p>';

      el("evidence").innerHTML = (payload.evidence || []).map((evidence) => `
        <div class="item">
          <div class="citation-title">
            <span>${escapeHtml(evidence.rank)}. ${escapeHtml(evidence.citation_label)}</span>
            <span>${Number(evidence.score || 0).toFixed(4)}</span>
          </div>
          <p class="snippet">${escapeHtml(evidence.snippet)}</p>
        </div>
      `).join("") || '<p class="muted">No evidence returned.</p>';
    }

    function warningKind(severity) {
      if (severity === "high") return "bad";
      if (severity === "info") return "ok";
      return "warn";
    }

    function renderProvenance(payload) {
      const audit = payload.diagnostics?.audit || {};
      const model = payload.model_info || {};
      const chat = payload.chat || {};
      el("provenance").innerHTML = `
        <dl class="kv-grid">
          <dt>Session</dt><dd>${escapeHtml(chat.session_id || "none")}</dd>
          <dt>Turn</dt><dd>${escapeHtml(chat.turn_id || "none")}</dd>
          <dt>Query</dt><dd>${escapeHtml(payload.query_id)}</dd>
          <dt>Record</dt><dd>${escapeHtml(audit.record_hash || "none")}</dd>
          <dt>Evidence</dt><dd>${escapeHtml(audit.evidence_digest || "none")}</dd>
          <dt>Prompt</dt><dd>${escapeHtml(model.prompt_version || "none")}</dd>
          <dt>Model</dt><dd>${escapeHtml(model.generation_model || "none")}</dd>
        </dl>
      `;
    }

    el("ingest-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const target = el("ingest-notice");
      clearNotice(target);
      try {
        const payload = formPayload(event.currentTarget);
        const result = await api("/documents", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        notice(target, "ok", `Ingested ${result.source.chunk_count} chunks.`);
        await loadSources();
      } catch (error) {
        notice(target, "bad", error.message);
      }
    });

    el("source-list").addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.classList.contains("select-source")) {
        el("source-filter").value = target.dataset.filter || "";
      }
      if (target.classList.contains("delete-source")) {
        const sourceId = target.dataset.sourceId;
        if (!sourceId) return;
        await api(`/documents/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
        await loadSources();
      }
    });

    el("refresh-sources").addEventListener("click", loadSources);
    el("refresh-chats").addEventListener("click", loadChatSessions);

    el("new-chat").addEventListener("click", () => {
      state.chatSessionId = null;
      updateChatLabel(null);
      renderChatTurns([]);
    });

    el("chat-sessions").addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const sessionId = target.dataset.sessionId;
      if (!sessionId) return;
      if (target.classList.contains("select-chat")) {
        await loadChatSession(sessionId);
      }
      if (target.classList.contains("delete-chat")) {
        await api(`/chat/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
        if (state.chatSessionId === sessionId) {
          state.chatSessionId = null;
          updateChatLabel(null);
          renderChatTurns([]);
        }
        await loadChatSessions();
      }
    });

    el("query-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const target = el("query-notice");
      clearNotice(target);
      try {
        const payload = formPayload(event.currentTarget);
        const scope = selectedScope();
        const result = await api("/chat", {
          method: "POST",
          body: JSON.stringify({
            question: payload.question,
            top_k: Number(payload.top_k || 3),
            session_id: state.chatSessionId,
            ...scope,
          }),
        });
        state.chatSessionId = result.chat.session_id;
        renderQueryResult(result);
        await loadChatSessions();
        notice(target, "ok", `Answered with ${result.citations.length} citations.`);
      } catch (error) {
        notice(target, "bad", error.message);
      }
    });

    el("verify-audit").addEventListener("click", async () => {
      const target = el("query-notice");
      clearNotice(target);
      try {
        const payload = await api("/audit/verify");
        const kind = payload.verified ? "ok" : "bad";
        notice(target, kind, `Audit records: ${payload.record_count}`);
      } catch (error) {
        notice(target, "bad", error.message);
      }
    });

    async function showExport(format) {
      const target = el("query-notice");
      clearNotice(target);
      if (!state.lastQuery?.query_id) {
        notice(target, "warn", "No query selected.");
        return;
      }
      const queryId = encodeURIComponent(state.lastQuery.query_id);
      const path = `/audit/queries/${queryId}/export?format=${format}`;
      try {
        if (format === "json") {
          const payload = await api(path);
          el("diagnostics").textContent = JSON.stringify(payload.export, null, 2);
        } else {
          const response = await fetch(path);
          if (!response.ok) throw new Error(`Request failed: ${response.status}`);
          el("diagnostics").textContent = await response.text();
        }
        notice(target, "ok", `Loaded ${format} export.`);
      } catch (error) {
        notice(target, "bad", error.message);
      }
    }

    el("export-json").addEventListener("click", () => showExport("json"));
    el("export-markdown").addEventListener("click", () => showExport("markdown"));

    el("export-chat").addEventListener("click", async () => {
      const target = el("query-notice");
      clearNotice(target);
      if (!state.chatSessionId) {
        notice(target, "warn", "No chat session selected.");
        return;
      }
      try {
        const sessionId = encodeURIComponent(state.chatSessionId);
        const response = await fetch(`/chat/sessions/${sessionId}/export?format=markdown`);
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        el("result-section").classList.remove("hidden");
        el("diagnostics").textContent = await response.text();
        notice(target, "ok", "Loaded chat export.");
      } catch (error) {
        notice(target, "bad", error.message);
      }
    });

    loadHealth();
    loadSources();
    loadChatSessions();
  </script>
</body>
</html>
"""
