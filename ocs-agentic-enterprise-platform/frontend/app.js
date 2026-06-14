/* OCS Agentic Enterprise Platform - frontend Fase 3 (vanilla JS, offline) */
"use strict";

const API = "";
let AGENTS = [];
let SQUADS = [];
let CONNECTORS = [];
let LAST_EXECUTION_ID = null;

// --------------------------------------------------------------------------
// Iconos (SVG inline, stroke currentColor)
// --------------------------------------------------------------------------
const ICONS = {
  dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>',
  assistant: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 21h6"/></svg>',
  executions: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/></svg>',
  documents: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h6"/></svg>',
  tools: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2-2 2.5-2.5z"/></svg>',
  agents: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="7" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3 2.7-5 6-5s6 2 6 5"/><path d="M16 14c2.5 0 5 1.6 5 4.5"/></svg>',
  scheduler: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2"/><path d="M5 3 2 6M19 3l3 3"/></svg>',
  pentest: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6c.06-.33.1-.66.1-1z"/></svg>',
  reports: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/></svg>',
};

const VIEWS = [
  { id: "dashboard", label: "Dashboard", sub: "Visión general de la plataforma" },
  { id: "assistant", label: "Asistente", sub: "Lanza una tarea a un agente o equipo" },
  { id: "agents", label: "Agentes", sub: "Catálogo por áreas y equipos" },
  { id: "executions", label: "Ejecuciones", sub: "Histórico y trazabilidad" },
  { id: "reports", label: "Informes", sub: "Informes completos: descarga y borrado" },
  { id: "scheduler", label: "Programador", sub: "Tareas puntuales y periódicas" },
  { id: "pentest", label: "Pentest", sub: "Escaneo autorizado con Kali" },
  { id: "documents", label: "Documentos", sub: "RAG local: subida y búsqueda" },
  { id: "tools", label: "Herramientas", sub: "Catálogo de herramientas locales" },
  { id: "settings", label: "Ajustes", sub: "Modelo, pentest y entorno de ejecución" },
];

// --------------------------------------------------------------------------
// Utilidades
// --------------------------------------------------------------------------
function el(id) { return document.getElementById(id); }

function escapeHtml(t) {
  return String(t ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const b = await res.json(); if (b.detail) detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail); } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

function toast(msg, kind = "") {
  const t = el("toast");
  t.textContent = msg; t.className = `toast ${kind}`;
  setTimeout(() => t.classList.add("hidden"), 3600);
}

function renderMarkdown(md) {
  const lines = escapeHtml(md).split("\n");
  const out = []; let inList = false, inOrd = false, inCode = false;
  const closeLists = () => { if (inList) { out.push("</ul>"); inList = false; } if (inOrd) { out.push("</ol>"); inOrd = false; } };
  const inline = (t) => t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
  for (const line of lines) {
    if (line.trim().startsWith("```")) { closeLists(); out.push(inCode ? "</code></pre>" : "<pre><code>"); inCode = !inCode; continue; }
    if (inCode) { out.push(line); continue; }
    let m;
    if ((m = line.match(/^(#{1,3})\s+(.*)$/))) { closeLists(); const l = m[1].length; out.push(`<h${l}>${inline(m[2])}</h${l}>`); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) { if (inOrd) { out.push("</ol>"); inOrd = false; } if (!inList) { out.push("<ul>"); inList = true; } out.push(`<li>${inline(m[1])}</li>`); }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) { if (inList) { out.push("</ul>"); inList = false; } if (!inOrd) { out.push("<ol>"); inOrd = true; } out.push(`<li>${inline(m[1])}</li>`); }
    else if (/^\s*(---|\*\*\*)\s*$/.test(line)) { closeLists(); out.push("<hr/>"); }
    else if (line.trim() === "") { closeLists(); }
    else { closeLists(); out.push(`<p>${inline(line)}</p>`); }
  }
  closeLists(); if (inCode) out.push("</code></pre>");
  return out.join("\n");
}

function confClass(score) { return score >= 0.7 ? "ok" : score >= 0.45 ? "warn" : "err"; }
function statusBadge(s) {
  const cls = s === "completed" ? "ok" : s === "failed" ? "err" : "warn";
  const label = s === "completed_with_warnings" ? "con avisos" : s;
  return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

// Anillo de confianza (SVG)
function confidenceRing(score) {
  if (score == null) return "";
  const pct = Math.round(score * 100);
  const r = 34, c = 2 * Math.PI * r, dash = (c * pct) / 100;
  const col = score >= 0.7 ? "#2dd4a7" : score >= 0.45 ? "#f6b545" : "#f6685e";
  return `<svg class="ring" viewBox="0 0 86 86">
    <circle cx="43" cy="43" r="${r}" fill="none" stroke="#22304a" stroke-width="8"/>
    <circle cx="43" cy="43" r="${r}" fill="none" stroke="${col}" stroke-width="8" stroke-linecap="round"
      stroke-dasharray="${dash} ${c}" transform="rotate(-90 43 43)"/>
    <text x="43" y="40" text-anchor="middle" font-size="18">${pct}%</text>
    <text x="43" y="55" text-anchor="middle" font-size="8" class="ring-sub">CONFIANZA</text>
  </svg>`;
}

// Gráfico de barras horizontales
function barChart(container, items, kindFn) {
  if (!items.length) { container.innerHTML = '<div class="chart-empty">Sin datos todavía.</div>'; return; }
  const max = Math.max(...items.map((i) => i.value), 1);
  container.innerHTML = items.map((i) => {
    const w = Math.max(3, Math.round((i.value / max) * 100));
    const kind = kindFn ? kindFn(i) : "";
    return `<div class="bar-row"><span class="bar-label" title="${escapeHtml(i.label)}">${escapeHtml(i.label)}</span>
      <span class="bar-track"><span class="bar-fill ${kind}" style="--w:${w}%"></span></span>
      <span class="bar-val">${i.value}</span></div>`;
  }).join("");
}

function timelineChart(container, points) {
  const max = Math.max(...points.map((p) => p.count), 1);
  container.innerHTML = points.map((p) => {
    const h = Math.round((p.count / max) * 100);
    const d = p.date.slice(5);
    return `<div class="tl-bar" title="${p.date}: ${p.count}"><span class="tl-fill" style="--h:${h}%"></span><span class="tl-day">${d}</span></div>`;
  }).join("");
}

// --------------------------------------------------------------------------
// Navegación
// --------------------------------------------------------------------------
function buildNav() {
  el("nav").innerHTML = VIEWS.map((v, i) =>
    `<button class="nav-item ${i === 0 ? "active" : ""}" data-view="${v.id}">${ICONS[v.id]}<span>${v.label}</span></button>`
  ).join("");
  el("nav").querySelectorAll(".nav-item").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
}

function switchView(id) {
  const v = VIEWS.find((x) => x.id === id); if (!v) return;
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === id));
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("active", s.id === `view-${id}`));
  el("page-title").textContent = v.label;
  el("page-subtitle").textContent = v.sub;
  if (id === "dashboard") loadMetrics();
  if (id === "agents") loadAgentsView();
  if (id === "executions") loadExecutions();
  if (id === "reports") loadReports();
  if (id === "scheduler") loadScheduler();
  if (id === "pentest") loadPentest();
  if (id === "settings") loadSettings();
  if (id === "documents") loadDocuments();
}

// --------------------------------------------------------------------------
// Salud
// --------------------------------------------------------------------------
async function loadHealth() {
  const apiL = el("status-api"), olL = el("status-ollama");
  try { await api("/health"); apiL.className = "status-line up"; apiL.querySelector(".status-val").textContent = "OK"; }
  catch (_) { apiL.className = "status-line down"; apiL.querySelector(".status-val").textContent = "caída"; return; }
  try {
    const o = await api("/health/ollama");
    olL.className = `status-line ${o.status === "up" ? "up" : "down"}`;
    olL.querySelector(".status-val").textContent = o.status === "up" ? `${o.models_available} mod.` : "caído";
    olL.title = o.detail || `Modelo ${o.default_model}${o.default_model_available ? " (ok)" : " (no descargado)"}`;
  } catch (e) { olL.className = "status-line down"; olL.querySelector(".status-val").textContent = "error"; }
}

// --------------------------------------------------------------------------
// Dashboard
// --------------------------------------------------------------------------
async function loadMetrics() {
  let m;
  try { m = await api("/metrics/summary"); }
  catch (e) { el("kpi-row").innerHTML = `<div class="kpi"><div class="kpi-label">Error</div><div class="kpi-sub">${escapeHtml(e.message)}</div></div>`; return; }

  const avg = m.avg_confidence != null ? Math.round(m.avg_confidence * 100) + "%" : "—";
  el("kpi-row").innerHTML = `
    ${kpi("Ejecuciones", m.total_executions, "total registradas", true)}
    ${kpi("Tasa de éxito", m.success_rate + "%", `${m.completed + m.warnings} ok · ${m.failed} fallidas`)}
    ${kpi("Confianza media", avg, "de las ejecuciones")}
    ${kpi("Documentos", m.documents, `${m.chunks} chunks · ${m.embeddings} embeddings`)}`;

  barChart(el("chart-agents"), toItems(m.by_agent));
  barChart(el("chart-intents"), toItems(m.by_intent));
  barChart(el("chart-tools"), m.tool_usage.slice(0, 8).map((t) => ({ label: t.tool_name, value: t.count, errors: t.errors })),
    (i) => (i.errors > 0 ? "warn" : ""));
  barChart(el("chart-status"), toItems(m.by_status), (i) =>
    i.label === "completed" ? "ok" : i.label === "failed" ? "err" : "warn");
  timelineChart(el("chart-timeline"), m.timeline);

  loadRecent();
}

function kpi(label, value, sub, accent) {
  return `<div class="kpi ${accent ? "accent" : ""}"><div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div><div class="kpi-sub">${escapeHtml(sub)}</div></div>`;
}
function toItems(obj) {
  return Object.entries(obj || {}).map(([k, v]) => ({ label: k, value: v })).sort((a, b) => b.value - a.value).slice(0, 8);
}

async function loadRecent() {
  try {
    const ex = await api("/executions?limit=6");
    el("dashboard-recent").innerHTML = ex.length ? ex.map((e) =>
      `<div class="mini-row" data-exec="${e.id}"><strong>#${e.id}</strong>
        <span class="grow">${escapeHtml(e.agent_name)} · ${escapeHtml(e.intent)}</span>
        ${statusBadge(e.status)}
        <span class="badge">${e.confidence_score != null ? Math.round(e.confidence_score * 100) + "%" : "—"}</span></div>`
    ).join("") : '<div class="chart-empty">Aún no hay ejecuciones.</div>';
    el("dashboard-recent").querySelectorAll(".mini-row").forEach((r) =>
      r.addEventListener("click", () => { switchView("executions"); showExecutionDetail(r.dataset.exec); }));
  } catch (_) {}
}

// --------------------------------------------------------------------------
// Catálogos
// --------------------------------------------------------------------------
async function loadAgents() {
  try {
    AGENTS = await api("/agents");
    el("agent-select").innerHTML = AGENTS.map((a) =>
      `<option value="${escapeHtml(a.name)}">${escapeHtml(a.display_name)} — ${escapeHtml(a.category)}</option>`).join("");
    updateAgentHint();
    buildTeamChecklist("team-agents");
    buildTeamChecklist("sched-team-agents");
    if (el("sched-agent")) el("sched-agent").innerHTML = AGENTS.map((a) =>
      `<option value="${escapeHtml(a.name)}">${escapeHtml(a.display_name)} — ${escapeHtml(a.category)}</option>`).join("");
  } catch (_) {}
}

// Etiquetas legibles para las áreas (categorías) de agentes.
const AREA_LABELS = {
  programming: "💻 Programación", cybersecurity: "🛡️ Ciberseguridad", business: "📈 Negocio",
  psychology: "🧠 Psicología", compliance: "⚖️ Compliance", hr: "👥 RRHH",
  projects: "🗂️ Proyectos", finance: "💰 Finanzas", legal: "📜 Legal", sales: "🤝 Ventas",
  data: "📊 Datos", documents: "📄 Documentos", reporting: "📰 Informes",
  research: "🔎 Investigación", customer_support: "🎧 Soporte", security_testing: "🔐 Seguridad de prompts",
};
function areaLabel(cat) { return AREA_LABELS[cat] || cat; }

async function loadAgentsView() {
  if (!AGENTS.length) { try { AGENTS = await api("/agents"); } catch (_) {} }
  el("agents-count").textContent = `${AGENTS.length} agentes · ${new Set(AGENTS.map((a) => a.category)).size} áreas`;
  const byArea = {};
  AGENTS.forEach((a) => { (byArea[a.category] = byArea[a.category] || []).push(a); });
  el("agents-by-area").innerHTML = Object.keys(byArea).sort().map((cat) =>
    `<div class="area-block"><h4>${escapeHtml(areaLabel(cat))} · ${byArea[cat].length}</h4>
      <div class="agent-cards">${byArea[cat].map((a) =>
        `<div class="agent-card"><div class="agent-card-head"><strong>${escapeHtml(a.display_name)}</strong>
          <button class="btn ghost xs" data-use-agent="${escapeHtml(a.name)}">Usar</button></div>
          <p>${escapeHtml(a.description)}</p>
          <div class="agent-tools">${(a.allowed_tools || []).map((t) => `<span class="tool-chip">${escapeHtml(t)}</span>`).join("") || '<span class="muted">sin herramientas</span>'}</div>
          ${(a.data_access && a.data_access.length) ? `<div class="agent-access" title="Acceso de lectura de datos">🔌 ${a.data_access.map((d) => `<span class="access-chip">${escapeHtml(d)}</span>`).join("")}</div>` : ""}
        </div>`).join("")}</div></div>`).join("");
  el("agents-by-area").querySelectorAll("[data-use-agent]").forEach((b) =>
    b.addEventListener("click", () => useAgentInAssistant(b.dataset.useAgent)));

  if (!SQUADS.length) await loadSquads();
  el("squads-list").innerHTML = SQUADS.map((s) =>
    `<div class="squad-card"><div class="agent-card-head"><strong>${escapeHtml(s.display_name)}</strong>
      <button class="btn ghost xs" data-use-squad="${escapeHtml(s.name)}">Usar</button></div>
      <p>${escapeHtml(s.description)}</p>
      <div class="squad-chain">${s.members.map((m) => `<span class="chain-step">${escapeHtml(m)}</span>`).join('<span class="chain-arrow">→</span>')}</div>
    </div>`).join("") || '<div class="chart-empty">Sin equipos.</div>';
  el("squads-list").querySelectorAll("[data-use-squad]").forEach((b) =>
    b.addEventListener("click", () => useSquadInAssistant(b.dataset.useSquad)));
}

function useAgentInAssistant(name) {
  switchView("assistant");
  setMode("manual");
  el("agent-select").value = name; updateAgentHint();
  el("task-input").focus();
}
function useSquadInAssistant(name) {
  switchView("assistant");
  setMode("team");
  setTeamKind("squad");
  el("squad-select").value = name; updateSquadHint();
  el("task-input").focus();
}
function updateAgentHint() {
  const a = AGENTS.find((x) => x.name === el("agent-select").value);
  el("agent-description").textContent = a ? `${a.description} · Herramientas: ${a.allowed_tools.join(", ") || "ninguna"}` : "";
}

async function loadModels() {
  try {
    const models = await api("/models");
    const opts = '<option value="">(modelo por defecto)</option>' +
      models.map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`).join("");
    el("model-select").innerHTML = opts;
    if (el("sched-model")) el("sched-model").innerHTML = opts;
    if (el("pt-model")) el("pt-model").innerHTML = opts;
  } catch (_) { el("model-select").innerHTML = '<option value="">(Ollama no disponible)</option>'; }
}

async function loadSquads() {
  try {
    SQUADS = await api("/agents/squads");
    const sel = el("squad-select");
    if (sel) {
      sel.innerHTML = SQUADS.map((s) =>
        `<option value="${escapeHtml(s.name)}">${escapeHtml(s.display_name)} (${s.members.length})</option>`).join("");
      updateSquadHint();
    }
    if (el("sched-squad")) {
      el("sched-squad").innerHTML = SQUADS.map((s) =>
        `<option value="${escapeHtml(s.name)}">${escapeHtml(s.display_name)}</option>`).join("");
    }
  } catch (_) {}
}

function updateSquadHint() {
  const s = SQUADS.find((x) => x.name === el("squad-select").value);
  el("squad-description").textContent = s ? `${s.description} · Cadena: ${s.members.join(" → ")}` : "";
}

// Casillas de agentes para componer un equipo ad-hoc.
function buildTeamChecklist(containerId) {
  const c = el(containerId);
  if (!c) return;
  c.innerHTML = AGENTS.map((a) =>
    `<label class="chk-item"><input type="checkbox" value="${escapeHtml(a.name)}" />
      <span>${escapeHtml(a.display_name)}</span><span class="chk-cat">${escapeHtml(a.category)}</span></label>`).join("");
}

function checkedValues(containerId) {
  return [...el(containerId).querySelectorAll("input:checked")].map((i) => i.value);
}

async function loadConnectors() {
  try {
    CONNECTORS = await api("/connectors");
    const sel = el("sched-connector");
    if (sel) {
      sel.innerHTML = '<option value="">(ninguna)</option>' + CONNECTORS.map((c) =>
        `<option value="${escapeHtml(c.name)}"${c.enabled ? "" : " disabled"}>${escapeHtml(c.display_name)}${c.enabled ? "" : " (desactivado)"}</option>`).join("");
    }
  } catch (_) {}
}

async function loadTools() {
  try {
    const [tools, cats] = await Promise.all([api("/tools"), api("/tools/categories")]);
    const byName = Object.fromEntries(tools.map((t) => [t.name, t]));
    el("tools-list").innerHTML = Object.entries(cats.categories).map(([cat, names]) =>
      `<div class="tools-cat"><h4>${escapeHtml(cat)} · ${names.length}</h4><div class="tools-grid">${
        names.map((n) => { const t = byName[n] || {}; return `<div class="tool-card"><h5>${escapeHtml(n)}</h5>
          <p>${escapeHtml(t.description || "")}</p><span class="tool-chip">timeout ${t.timeout_seconds ?? "?"}s</span></div>`; }).join("")
      }</div></div>`).join("");
  } catch (e) { el("tools-list").innerHTML = `<div class="chart-empty">Error: ${escapeHtml(e.message)}</div>`; }
}

// --------------------------------------------------------------------------
// Asistente
// --------------------------------------------------------------------------
function currentMode() { return el("mode-seg").querySelector(".seg-btn.active").dataset.mode; }

function setMode(mode) {
  el("mode-seg").querySelectorAll(".seg-btn").forEach((x) => x.classList.toggle("active", x.dataset.mode === mode));
  applyMode();
}
function applyMode() {
  const mode = currentMode();
  el("agent-select-wrap").classList.toggle("hidden", mode !== "manual");
  el("squad-select-wrap").classList.toggle("hidden", mode !== "team");
  el("btn-execute").textContent = mode === "team" ? "Ejecutar equipo" : "Ejecutar tarea";
  el("btn-route").classList.toggle("hidden", mode === "team");
}
function teamKind() { return el("team-seg").querySelector(".seg-btn.active").dataset.team; }
function setTeamKind(kind) {
  el("team-seg").querySelectorAll(".seg-btn").forEach((x) => x.classList.toggle("active", x.dataset.team === kind));
  applyTeamKind();
}
function applyTeamKind() {
  const kind = teamKind();
  el("squad-predef-wrap").classList.toggle("hidden", kind !== "squad");
  el("squad-custom-wrap").classList.toggle("hidden", kind !== "custom");
}

async function previewRoute() {
  const task = el("task-input").value.trim();
  if (!task) return toast("Escribe una tarea primero.", "err");
  const p = el("route-preview"); p.classList.remove("hidden"); p.textContent = "Clasificando…";
  try {
    const r = await api("/agents/route", { method: "POST", body: JSON.stringify({ task }) });
    p.innerHTML = `Intención <strong>${escapeHtml(r.detected_intent)}</strong> · confianza ${Math.round(r.intent_confidence * 100)}% (${escapeHtml(r.classification_method)})<br/>
      Agente <strong>${escapeHtml(r.selected_agent)}</strong>${r.auxiliary_agents.length ? ` · aux.: ${r.auxiliary_agents.map(escapeHtml).join(", ")}` : ""}
      <br/><span class="muted">${escapeHtml(r.reason)}</span>`;
  } catch (e) { p.textContent = `Error: ${e.message}`; }
}

async function executeTask() {
  const task = el("task-input").value.trim();
  if (!task) return toast("Escribe una tarea primero.", "err");
  const mode = currentMode();
  const common = {
    task,
    model: el("model-select").value || null,
    use_documents: el("use-documents").checked,
    extra_context: el("context-input").value.trim() || null,
  };
  let path = "/agents/execute", body;
  if (mode === "team") {
    body = { ...common };
    if (teamKind() === "squad") {
      body.squad_name = el("squad-select").value;
    } else {
      const members = checkedValues("team-agents");
      if (members.length < 2) return toast("Selecciona al menos 2 agentes para el equipo.", "err");
      body.agent_names = members;
    }
    path = "/agents/squads/execute";
  } else {
    body = { ...common, agent_name: mode === "manual" ? el("agent-select").value : null };
  }

  el("result-empty").classList.add("hidden");
  el("result-content").classList.add("hidden");
  el("result-loading").classList.remove("hidden");
  el("btn-execute").disabled = true;
  try {
    const r = await api(path, { method: "POST", body: JSON.stringify(body) });
    renderResult(r);
  } catch (e) {
    el("result-content").classList.remove("hidden");
    ["result-meta", "result-output", "verification-list", "tools-used-list", "cow-list", "confidence-ring"].forEach((i) => el(i).innerHTML = "");
    const eb = el("result-error"); eb.classList.remove("hidden"); eb.textContent = `Error: ${e.message}`;
  } finally { el("result-loading").classList.add("hidden"); el("btn-execute").disabled = false; }
}

function renderCow(node, steps) {
  node.innerHTML = steps.map((s) => `<li class="risk-${escapeHtml(s.risk_level)}">
    <span class="cow-type">${escapeHtml(s.step_type)}</span><span class="cow-title">${escapeHtml(s.title)}</span>
    ${s.description ? `<div class="cow-desc">${escapeHtml(s.description)}</div>` : ""}
    ${s.tool_name ? `<div class="cow-desc">🔧 <code>${escapeHtml(s.tool_name)}</code></div>` : ""}
    ${s.evidence ? `<div class="cow-ev">${escapeHtml(s.evidence)}</div>` : ""}</li>`).join("");
}

function renderResult(r) {
  LAST_EXECUTION_ID = r.execution_id;
  el("result-content").classList.remove("hidden");
  const eb = el("result-error");
  if (r.status === "failed") { eb.classList.remove("hidden"); eb.textContent = r.error_message || "La ejecución falló."; }
  else eb.classList.add("hidden");

  el("confidence-ring").innerHTML = confidenceRing(r.confidence ? r.confidence.score : null);
  el("result-meta").innerHTML = [
    `<span class="badge accent">🤖 ${escapeHtml(r.agent_name)}</span>`,
    `<span class="badge">🎯 ${escapeHtml(r.detected_intent)}</span>`,
    `<span class="badge">${r.selected_by_router ? "Auto" : "Manual"}</span>`,
    `<span class="badge">🧠 ${escapeHtml(r.model_name)}</span>`,
    statusBadge(r.status),
    r.documents_used ? `<span class="badge">📄 ${r.documents_used} docs</span>` : "",
    `<span class="badge">#${r.execution_id}</span>`,
  ].join(" ");
  el("result-output").innerHTML = r.final_output ? renderMarkdown(r.final_output) : '<p class="muted">Sin salida.</p>';

  el("verification-list").innerHTML = (r.verification ? r.verification.checks : []).map((c) =>
    `<li class="${c.passed ? "ico-ok" : "ico-fail"}"><strong>${escapeHtml(c.name)}</strong>: ${escapeHtml(c.detail)}</li>`).join("") || "<li>No disponible.</li>";
  el("tools-used-list").innerHTML = (r.tool_results || []).map((t) =>
    `<li class="${t.status === "success" ? "ico-ok" : "ico-fail"}"><code>${escapeHtml(t.tool_name)}</code> · ${escapeHtml(t.status)} · ${t.duration_ms}ms${t.error_message ? " · " + escapeHtml(t.error_message) : ""}</li>`).join("") || "<li>No se usaron herramientas.</li>";
  renderCow(el("cow-list"), r.chain_of_work || []);
}

function exportExecution(format) {
  if (!LAST_EXECUTION_ID) return;
  window.open(`/executions/${LAST_EXECUTION_ID}/export?format=${format}`, "_blank");
}

// --------------------------------------------------------------------------
// Ejecuciones
// --------------------------------------------------------------------------
async function loadExecutions() {
  try {
    const ex = await api("/executions?limit=60");
    el("executions-table").querySelector("tbody").innerHTML = ex.map((e) =>
      `<tr><td>#${e.id}</td><td>${escapeHtml(e.agent_name)}</td><td>${escapeHtml(e.intent)}</td>
       <td>${escapeHtml(e.model_name)}</td><td>${statusBadge(e.status)}</td>
       <td>${e.confidence_score != null ? Math.round(e.confidence_score * 100) + "%" : "—"}</td>
       <td>${new Date(e.created_at).toLocaleString()}</td>
       <td class="sched-actions"><button class="btn ghost sm" data-exec="${e.id}">Ver</button>
         <button class="btn ghost sm" data-del-exec="${e.id}" title="Borrar">🗑</button></td></tr>`).join("");
    el("executions-table").querySelectorAll("button[data-exec]").forEach((b) =>
      b.addEventListener("click", () => showExecutionDetail(b.dataset.exec)));
    el("executions-table").querySelectorAll("button[data-del-exec]").forEach((b) =>
      b.addEventListener("click", () => deleteExecution(b.dataset.delExec)));
  } catch (_) {}
}

async function deleteExecution(id) {
  if (!confirm(`¿Borrar la ejecución #${id}?`)) return;
  try {
    const res = await fetch(`/executions/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    toast("Ejecución borrada.", "ok");
    el("execution-detail").classList.add("hidden");
    loadExecutions();
  } catch (e) { toast(e.message, "err"); }
}

async function clearFailedExecutions() {
  if (!confirm("¿Borrar TODAS las ejecuciones fallidas?")) return;
  try {
    const r = await api("/executions?status=failed", { method: "DELETE" });
    toast(`${r.deleted} ejecución(es) borrada(s).`, "ok");
    loadExecutions();
  } catch (e) { toast(e.message, "err"); }
}

// --------------------------------------------------------------------------
// Informes
// --------------------------------------------------------------------------
let REPORTS = [];
const PENTEST_AGENTS = ["web_pentester", "pentest_lead"];

async function loadReports() {
  try { REPORTS = await api("/executions?limit=200"); renderReports(); }
  catch (e) { el("reports-list").innerHTML = `<div class="muted">${escapeHtml(e.message)}</div>`; }
}

function renderReports() {
  const q = (el("reports-filter").value || "").toLowerCase();
  const items = REPORTS
    .filter((e) => e.status === "completed" || e.status === "completed_with_warnings")
    .filter((e) => !q || `${e.agent_name} ${e.intent} #${e.id}`.toLowerCase().includes(q));
  el("reports-count").textContent = `· ${items.length}`;
  if (!items.length) { el("reports-list").innerHTML = '<div class="chart-empty">No hay informes todavía.</div>'; return; }
  el("reports-list").innerHTML = items.map((e) => {
    const isPentest = PENTEST_AGENTS.includes(e.agent_name);
    const conf = e.confidence_score != null ? Math.round(e.confidence_score * 100) + "%" : "—";
    return `<div class="report-card ${isPentest ? "pentest" : ""}">
      <div class="report-head"><strong>${isPentest ? "🛡️ " : "📄 "}${escapeHtml(e.agent_name)}</strong>
        ${statusBadge(e.status)}<span class="badge">${conf}</span></div>
      <div class="doc-meta">#${e.id} · ${escapeHtml(e.intent || "—")} · ${new Date(e.created_at).toLocaleString()}</div>
      <div class="report-actions">
        <button class="btn ghost xs" data-rep-view="${e.id}">Ver</button>
        ${isPentest ? `<button class="btn ghost xs" data-rep-pdf="${e.id}">🛡 Informe</button>` : ""}
        <button class="btn ghost xs" data-rep-md="${e.id}">⬇ MD</button>
        <button class="btn ghost xs" data-rep-html="${e.id}">⬇ HTML</button>
        <button class="btn ghost xs" data-rep-del="${e.id}">🗑</button>
      </div></div>`;
  }).join("");
  const grid = el("reports-list");
  grid.querySelectorAll("[data-rep-view]").forEach((b) => b.addEventListener("click", () => { switchView("executions"); showExecutionDetail(b.dataset.repView); }));
  grid.querySelectorAll("[data-rep-pdf]").forEach((b) => b.addEventListener("click", () => window.open(`/pentest/report/${b.dataset.repPdf}`, "_blank")));
  grid.querySelectorAll("[data-rep-md]").forEach((b) => b.addEventListener("click", () => window.open(`/executions/${b.dataset.repMd}/export?format=markdown`, "_blank")));
  grid.querySelectorAll("[data-rep-html]").forEach((b) => b.addEventListener("click", () => window.open(`/executions/${b.dataset.repHtml}/export?format=html`, "_blank")));
  grid.querySelectorAll("[data-rep-del]").forEach((b) => b.addEventListener("click", () => deleteReport(b.dataset.repDel)));
}

async function deleteReport(id) {
  if (!confirm(`¿Borrar el informe #${id}?`)) return;
  try {
    const res = await fetch(`/executions/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    toast("Informe borrado.", "ok");
    REPORTS = REPORTS.filter((e) => String(e.id) !== String(id));
    renderReports();
  } catch (e) { toast(e.message, "err"); }
}

async function showExecutionDetail(id) {
  try {
    const [d, cow] = await Promise.all([api(`/executions/${id}`), api(`/executions/${id}/chain-of-work`)]);
    el("execution-detail").classList.remove("hidden");
    el("execution-detail").dataset.exec = id;
    el("execution-detail-title").innerHTML = `Ejecución #${d.id} · ${escapeHtml(d.agent_name)} ${statusBadge(d.status)}
      <span class="badge ${d.confidence_score != null ? confClass(d.confidence_score) : ""}">${d.confidence_score != null ? Math.round(d.confidence_score * 100) + "%" : "—"}</span>`;
    el("execution-detail-output").innerHTML = d.final_output ? renderMarkdown(d.final_output) : `<p class="muted">${escapeHtml(d.error_message || "Sin salida.")}</p>`;
    renderCow(el("execution-detail-cow"), cow.steps);
    el("execution-detail").scrollIntoView({ behavior: "smooth" });
  } catch (e) { toast(`Error: ${e.message}`, "err"); }
}

// --------------------------------------------------------------------------
// Documentos
// --------------------------------------------------------------------------
function searchMode() { return el("search-mode").querySelector(".seg-btn.active").dataset.smode; }

async function uploadDocument() {
  const input = el("file-input");
  if (!input.files.length) return toast("Selecciona un archivo.", "err");
  const fd = new FormData(); fd.append("file", input.files[0]);
  el("upload-status").textContent = "Subiendo e indexando…";
  try {
    const res = await fetch("/documents/upload", { method: "POST", body: fd });
    const b = await res.json();
    if (!res.ok) throw new Error(b.detail || `HTTP ${res.status}`);
    el("upload-status").textContent = `✓ ${b.message}`;
    el("dz-text").textContent = "Haz clic para elegir un archivo";
    input.value = ""; loadDocuments(); toast("Documento indexado.", "ok");
  } catch (e) { el("upload-status").textContent = `✗ ${e.message}`; toast(e.message, "err"); }
}

async function reindexEmbeddings() {
  el("btn-reindex").disabled = true; el("upload-status").textContent = "Reindexando embeddings…";
  try {
    const b = await api("/documents/reindex-embeddings", { method: "POST" });
    el("upload-status").textContent = `✓ ${b.message}`; toast("Embeddings regenerados.", "ok");
  } catch (e) { el("upload-status").textContent = `✗ ${e.message}`; toast(e.message, "err"); }
  finally { el("btn-reindex").disabled = false; }
}

async function loadDocuments() {
  try {
    const docs = await api("/documents");
    el("documents-list").innerHTML = docs.length ? docs.map((d) =>
      `<li><strong>${escapeHtml(d.filename)}</strong><div class="doc-meta">id ${d.id} · ${escapeHtml(d.content_type)} · ${new Date(d.uploaded_at).toLocaleString()}</div></li>`).join("")
      : '<li class="muted">No hay documentos.</li>';
  } catch (e) { el("documents-list").innerHTML = `<li class="muted">${escapeHtml(e.message)}</li>`; }
}

async function searchDocuments() {
  const query = el("search-input").value.trim();
  if (query.length < 2) return toast("Escribe al menos 2 caracteres.", "err");
  const list = el("search-results"); list.innerHTML = "<li>Buscando…</li>";
  try {
    const r = await api("/documents/search", { method: "POST", body: JSON.stringify({ query, top_k: 5, mode: searchMode() }) });
    list.innerHTML = r.hits.length ? r.hits.map((h) =>
      `<li><div class="hit-head"><strong>${escapeHtml(h.filename)}</strong>
        <span class="badge accent">${escapeHtml(h.method)} · ${h.score}</span></div>
        <div class="doc-meta">chunk ${h.chunk_index}</div><div class="snippet">${escapeHtml(h.snippet)}</div></li>`).join("")
      : '<li class="muted">Sin resultados.</li>';
  } catch (e) { list.innerHTML = `<li class="muted">${escapeHtml(e.message)}</li>`; }
}

// --------------------------------------------------------------------------
// Programador de tareas
// --------------------------------------------------------------------------
function schedBadge(status) {
  const map = { scheduled: "ok", paused: "warn", finished: "", error: "err" };
  return `<span class="badge ${map[status] ?? ""}">${escapeHtml(status)}</span>`;
}

function applySchedTarget() {
  const kind = el("sched-target-kind").value;
  el("sched-agent-wrap").classList.toggle("hidden", kind !== "agent");
  el("sched-squad-wrap").classList.toggle("hidden", kind !== "squad");
  el("sched-team-wrap").classList.toggle("hidden", kind !== "team");
}
function applySchedKind() {
  const kind = el("sched-kind").value;
  [["once", "sched-once-wrap"], ["interval", "sched-interval-wrap"], ["daily", "sched-daily-wrap"],
   ["weekly", "sched-weekly-wrap"], ["cron", "sched-cron-wrap"]].forEach(([k, id]) =>
    el(id).classList.toggle("hidden", kind !== k));
}
function applySchedConnector() {
  const c = el("sched-connector").value;
  el("sched-connector-params-wrap").classList.toggle("hidden", !c);
  const info = CONNECTORS.find((x) => x.name === c);
  el("sched-connector-hint").textContent = info
    ? `${info.description} · El objetivo debe ser un agente/equipo con acceso a este conector.`
    : "";
}

async function loadScheduler() {
  await loadSchedulerStatus();
  await loadScheduledTasks();
}

async function loadSchedulerStatus() {
  try {
    const s = await api("/scheduler/status");
    const next = s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—";
    const dot = s.running ? "up" : "down";
    el("scheduler-status").innerHTML =
      `<span class="status-dot ${dot}"></span> Programador ${s.running ? "activo" : (s.enabled ? "habilitado" : "desactivado")}
       · sondeo cada ${s.poll_seconds}s · ${s.active_tasks}/${s.total_tasks} activas · próxima: ${escapeHtml(next)}`;
  } catch (e) { el("scheduler-status").textContent = ""; }
}

async function loadScheduledTasks() {
  const tbody = el("sched-table").querySelector("tbody");
  try {
    const tasks = await api("/scheduler/tasks");
    if (!tasks.length) { tbody.innerHTML = '<tr><td colspan="7" class="muted">No hay tareas programadas.</td></tr>'; return; }
    tbody.innerHTML = tasks.map((t) => {
      const target = t.target_kind === "auto" ? "Auto"
        : t.target_kind === "team" ? `Equipo: ${escapeHtml(t.agent_names.join(", "))}`
        : `${t.target_kind}: ${escapeHtml(t.target_ref)}`;
      const next = t.next_run_at ? new Date(t.next_run_at).toLocaleString() : "—";
      const toggle = t.enabled
        ? `<button class="btn ghost xs" data-sched-pause="${t.id}">⏸</button>`
        : `<button class="btn ghost xs" data-sched-resume="${t.id}">▶</button>`;
      const conn = t.connector ? ` <span class="badge accent">🔌 ${escapeHtml(t.connector)}</span>` : "";
      return `<tr><td><strong>${escapeHtml(t.name)}</strong><div class="doc-meta">#${t.id}</div></td>
        <td>${target}</td><td>${escapeHtml(t.schedule_human)}${conn}</td>
        <td>${escapeHtml(next)}</td><td>${schedBadge(t.status)}${t.last_status ? ` <span class="badge">${escapeHtml(t.last_status)}</span>` : ""}</td>
        <td>${t.run_count}</td>
        <td class="sched-actions">${toggle}
          <button class="btn ghost xs" data-sched-run="${t.id}" title="Ejecutar ahora">▶▶</button>
          <button class="btn ghost xs" data-sched-view="${t.id}" title="Histórico">👁</button>
          <button class="btn ghost xs" data-sched-del="${t.id}" title="Borrar">🗑</button></td></tr>`;
    }).join("");
    bindSchedActions();
  } catch (e) { tbody.innerHTML = `<tr><td colspan="7" class="muted">${escapeHtml(e.message)}</td></tr>`; }
}

function bindSchedActions() {
  const q = (sel, fn) => el("sched-table").querySelectorAll(sel).forEach((b) => b.addEventListener("click", fn));
  q("[data-sched-pause]", (e) => schedAction(e.currentTarget.dataset.schedPause, "pause"));
  q("[data-sched-resume]", (e) => schedAction(e.currentTarget.dataset.schedResume, "resume"));
  q("[data-sched-run]", (e) => schedRunNow(e.currentTarget.dataset.schedRun));
  q("[data-sched-view]", (e) => showSchedDetail(e.currentTarget.dataset.schedView));
  q("[data-sched-del]", (e) => schedDelete(e.currentTarget.dataset.schedDel));
}

async function schedAction(id, action) {
  try { await api(`/scheduler/tasks/${id}/${action}`, { method: "POST" }); toast("Tarea actualizada.", "ok"); loadScheduler(); }
  catch (e) { toast(e.message, "err"); }
}
async function schedRunNow(id) {
  toast("Ejecutando…");
  try {
    const run = await api(`/scheduler/tasks/${id}/run-now`, { method: "POST" });
    toast(`Ejecutada: ${run.status}`, run.status === "completed" ? "ok" : "warn");
    loadScheduler();
    if (run.execution_id) { switchView("executions"); showExecutionDetail(run.execution_id); }
  } catch (e) { toast(e.message, "err"); }
}
async function schedDelete(id) {
  if (!confirm("¿Borrar esta tarea programada?")) return;
  try { await fetch(`/scheduler/tasks/${id}`, { method: "DELETE" }); toast("Tarea borrada.", "ok"); loadScheduler(); }
  catch (e) { toast(e.message, "err"); }
}

async function showSchedDetail(id) {
  try {
    const t = await api(`/scheduler/tasks/${id}`);
    const runs = (t.runs || []).map((r) =>
      `<li><span class="badge ${r.status === "completed" ? "ok" : r.status === "failed" || r.status === "error" ? "err" : "warn"}">${escapeHtml(r.status)}</span>
        ${new Date(r.started_at).toLocaleString()}${r.execution_id ? ` · <a href="#" data-exec-link="${r.execution_id}">ejecución #${r.execution_id}</a>` : ""}
        ${r.message ? `<div class="doc-meta">${escapeHtml(r.message)}</div>` : ""}</li>`).join("") || "<li class='muted'>Sin ejecuciones todavía.</li>";
    const d = el("sched-detail");
    d.classList.remove("hidden");
    d.innerHTML = `<h4>${escapeHtml(t.name)} · histórico</h4><div class="doc-meta">${escapeHtml(t.schedule_human)} · ${escapeHtml(t.timezone)}</div>
      <ul class="search-results">${runs}</ul>`;
    d.querySelectorAll("[data-exec-link]").forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault(); switchView("executions"); showExecutionDetail(a.dataset.execLink);
    }));
    d.scrollIntoView({ behavior: "smooth" });
  } catch (e) { toast(e.message, "err"); }
}

async function createScheduledTask() {
  const name = el("sched-name").value.trim();
  const task = el("sched-task").value.trim();
  if (!name || !task) return toast("Indica nombre y tarea.", "err");
  const targetKind = el("sched-target-kind").value;
  const kind = el("sched-kind").value;
  const payload = {
    name, task,
    extra_context: el("sched-context").value.trim() || null,
    model: el("sched-model").value || null,
    use_documents: el("sched-docs").checked,
    target_kind: targetKind,
    schedule_kind: kind,
    timezone: el("sched-tz").value.trim() || "UTC",
  };
  if (targetKind === "agent") payload.target_ref = el("sched-agent").value;
  else if (targetKind === "squad") payload.target_ref = el("sched-squad").value;
  else if (targetKind === "team") {
    payload.agent_names = checkedValues("sched-team-agents");
    if (payload.agent_names.length < 2) return toast("Selecciona al menos 2 agentes.", "err");
  }
  if (kind === "once") {
    if (!el("sched-runat").value) return toast("Indica fecha y hora.", "err");
    payload.run_at = new Date(el("sched-runat").value).toISOString();
  } else if (kind === "interval") payload.interval_minutes = parseInt(el("sched-interval").value, 10);
  else if (kind === "daily") payload.time_of_day = el("sched-daily-time").value;
  else if (kind === "weekly") { payload.day_of_week = parseInt(el("sched-weekday").value, 10); payload.time_of_day = el("sched-weekly-time").value; }
  else if (kind === "cron") payload.cron = el("sched-cron").value.trim();

  const connector = el("sched-connector").value;
  if (connector) {
    payload.connector = connector;
    const raw = el("sched-connector-params").value.trim();
    if (raw) {
      try { payload.connector_params = JSON.parse(raw); }
      catch (_) { return toast("Parámetros del conector: JSON inválido.", "err"); }
    }
  }

  el("btn-create-sched").disabled = true;
  try {
    await api("/scheduler/tasks", { method: "POST", body: JSON.stringify(payload) });
    el("sched-form-msg").textContent = "✓ Tarea programada.";
    el("sched-name").value = ""; el("sched-task").value = ""; el("sched-context").value = "";
    toast("Tarea programada.", "ok");
    loadScheduler();
  } catch (e) { el("sched-form-msg").textContent = `✗ ${e.message}`; toast(e.message, "err"); }
  finally { el("btn-create-sched").disabled = false; }
}

// --------------------------------------------------------------------------
// Pentest (Kali, autorizado)
// --------------------------------------------------------------------------
async function loadPentest() {
  // Agentes de ciberseguridad como analistas.
  if (!AGENTS.length) { try { AGENTS = await api("/agents"); } catch (_) {} }
  const cyber = AGENTS.filter((a) => a.category === "cybersecurity");
  el("pt-agent").innerHTML = cyber.map((a) =>
    `<option value="${escapeHtml(a.name)}"${a.name === "web_pentester" ? " selected" : ""}>${escapeHtml(a.display_name)}</option>`).join("");
  applyPtMode();
  try {
    const s = await api("/pentest/status");
    const avail = s.tools.filter((t) => t.available).map((t) => t.name);
    el("pt-wordlist").innerHTML = '<option value="">(por defecto)</option>' +
      (s.wordlists || []).map((w) => `<option value="${escapeHtml(w)}">${escapeHtml(w.split("/").pop())}</option>`).join("");
    renderToolsGrid(s.tools);
    const dot = s.enabled && s.scope_configured && s.mode_ok ? "up" : "down";
    let msg;
    if (!s.enabled) msg = "Pentest DESACTIVADO. Actívalo en Ajustes (o ENABLE_PENTEST_TOOLS).";
    else if (!s.scope_configured) msg = "Sin alcance autorizado: defínelo en Ajustes (alcance autorizado).";
    else msg = `Activo · modo ${s.execution_mode} · ${s.scope_count} en alcance · ${avail.length}/${s.tools.length} herramientas instaladas`;
    const diag = s.mode_check ? `<div class="muted" style="margin-top:4px">${s.mode_ok ? "✓" : "⚠"} ${escapeHtml(s.mode_check)}</div>` : "";
    el("pentest-status").innerHTML = `<span class="status-dot ${dot}"></span> ${escapeHtml(msg)}${diag}`;
  } catch (e) { el("pentest-status").textContent = ""; }
}

function applyPtMode() {
  const auto = el("pt-auto").checked;
  el("pt-profile-wrap").classList.toggle("hidden", auto);
  el("pt-aggressive-wrap").classList.toggle("hidden", !auto);
  if (auto && [...el("pt-agent").options].some((o) => o.value === "pentest_lead")) el("pt-agent").value = "pentest_lead";
}

function renderToolsGrid(tools) {
  const grid = el("pt-tools-grid");
  if (!grid || !tools) return;
  const inst = tools.filter((t) => t.available).length;
  el("pt-tools-count").textContent = `· ${inst}/${tools.length} instaladas`;
  grid.innerHTML = tools.map((t) =>
    `<span class="tool-pill ${t.available ? "ok" : "no"}" title="${escapeHtml(t.binary)}">${t.available ? "●" : "○"} ${escapeHtml(t.name)}</span>`).join("");
}

async function recheckTools() {
  el("btn-pt-recheck").disabled = true;
  try { const s = await api("/pentest/recheck", { method: "POST" }); renderToolsGrid(s.tools); toast("Herramientas comprobadas.", "ok"); }
  catch (e) { toast(e.message, "err"); }
  finally { el("btn-pt-recheck").disabled = false; }
}

let PT_INSTALL_TIMER = null;
async function installTools() {
  if (!confirm("Esto instalará/actualizará las herramientas de Kali (puede tardar varios minutos). ¿Continuar?")) return;
  el("btn-pt-install").disabled = true;
  el("pt-install-log").classList.remove("hidden");
  el("pt-install-log").textContent = "Iniciando…";
  try {
    await api("/pentest/tools/install", { method: "POST" });
    clearInterval(PT_INSTALL_TIMER);
    PT_INSTALL_TIMER = setInterval(pollInstall, 2500);
  } catch (e) { toast(e.message, "err"); el("btn-pt-install").disabled = false; }
}

async function pollInstall() {
  try {
    const s = await api("/pentest/tools/install/status");
    el("pt-install-log").textContent = s.log || "(sin salida todavía)";
    el("pt-install-log").scrollTop = el("pt-install-log").scrollHeight;
    if (!s.running) {
      clearInterval(PT_INSTALL_TIMER);
      el("btn-pt-install").disabled = false;
      toast(`Instalación finalizada (código ${s.returncode}).`, s.returncode === 0 ? "ok" : "warn");
      recheckTools();
    }
  } catch (_) {}
}

let PT_PROGRESS_TIMER = null;
async function runPentest() {
  const target = el("pt-target").value.trim();
  if (!target) return toast("Indica un objetivo.", "err");
  if (!el("pt-authorized").checked) return toast("Debes confirmar la autorización.", "err");
  const auto = el("pt-auto").checked;
  const options = el("pt-wordlist").value ? { wordlist: el("pt-wordlist").value } : {};
  const common = { target, authorized: true, agent_name: el("pt-agent").value, model: el("pt-model").value || null, email_to: el("pt-email").value.trim() || null, options };
  const path = auto ? "/pentest/start-auto" : "/pentest/start";
  const body = auto ? { ...common, aggressive: el("pt-aggressive").checked } : { ...common, profile: el("pt-profile").value };

  el("pt-empty").classList.add("hidden");
  el("pt-result").classList.add("hidden");
  el("pt-loading").classList.add("hidden");
  el("pt-progress").classList.remove("hidden");
  el("pt-prog-timeline").innerHTML = ""; el("pt-msg").textContent = "";
  el("btn-pentest-run").disabled = true;
  try {
    renderProgress(await api(path, { method: "POST", body: JSON.stringify(body) }));
    clearInterval(PT_PROGRESS_TIMER);
    PT_PROGRESS_TIMER = setInterval(pollPentestProgress, 1300);
  } catch (e) {
    el("pt-progress").classList.add("hidden");
    el("pt-msg").textContent = `Error: ${e.message}`; toast(e.message, "err");
    el("btn-pentest-run").disabled = false;
  }
}

async function pollPentestProgress() {
  try {
    const p = await api("/pentest/progress");
    renderProgress(p);
    if (!p.running) {
      clearInterval(PT_PROGRESS_TIMER);
      el("btn-pentest-run").disabled = false;
      el("pt-progress").classList.add("hidden");
      if (p.result) renderPentest(p.result);
      else if (p.error) { el("pt-msg").textContent = `Error: ${p.error}`; toast(p.error, "err"); }
    }
  } catch (_) {}
}

const STEP_KIND = { running: "run", success: "ok", error: "err", timeout: "warn", unavailable: "no" };
function renderProgress(p) {
  el("pt-prog-stage").textContent = p.stage || (p.running ? "Trabajando…" : p.status);
  el("pt-prog-pct").textContent = p.percent + "%";
  el("pt-prog-fill").style.setProperty("--p", p.percent + "%");
  const sev = Object.entries(p.findings_by_severity || {}).filter(([, n]) => n).map(([s, n]) => `${s}: ${n}`).join(" · ");
  el("pt-prog-sub").textContent = `${p.done}/${p.total} herramientas` + (sev ? ` · hallazgos: ${sev}` : "");
  const byPhase = {};
  (p.steps || []).forEach((s) => { (byPhase[s.phase] = byPhase[s.phase] || []).push(s); });
  el("pt-prog-timeline").innerHTML = Object.entries(byPhase).map(([phase, steps]) =>
    `<div class="tl-phase"><div class="tl-phase-name">${escapeHtml(phase)}</div>
      <div class="tl-steps">${steps.map((s) =>
        `<span class="tl-step ${STEP_KIND[s.status] || ""}" title="${escapeHtml(s.tool)} · ${escapeHtml(s.status)}${s.duration_ms ? ` · ${s.duration_ms}ms` : ""}">${escapeHtml(s.tool)}</span>`).join("")}</div></div>`).join("");
}

function renderPentest(r) {
  el("pt-result").classList.remove("hidden");
  const statusKind = r.status === "completed" ? "ok" : r.status === "denied" || r.status === "disabled" ? "warn" : "err";
  el("pt-meta").innerHTML = [
    `<span class="badge ${statusKind}">${escapeHtml(r.status)}</span>`,
    r.host ? `<span class="badge">🎯 ${escapeHtml(r.host)}</span>` : "",
    r.profile ? `<span class="badge">${escapeHtml(r.profile)}</span>` : "",
    r.emailed ? `<span class="badge ok">📧 enviado</span>` : (r.email_message ? `<span class="badge err">📧 ${escapeHtml(r.email_message)}</span>` : ""),
    `<span class="badge">${escapeHtml(r.message)}</span>`,
  ].join(" ");
  renderFindings(r);
  el("pt-tools").innerHTML = (r.tools || []).map((t) =>
    `<div class="pt-tool"><div class="pt-tool-head"><strong>${escapeHtml(t.tool_name)}</strong>
      ${t.phase ? `<span class="badge">${escapeHtml(t.phase)}</span>` : ""}
      <span class="badge ${t.status === "success" ? "ok" : t.status === "unavailable" ? "warn" : "err"}">${escapeHtml(t.status)}</span>
      <span class="muted">${t.duration_ms}ms</span></div>
      ${t.command ? `<div class="doc-meta">${escapeHtml(t.command)}</div>` : ""}
      <pre class="pt-output">${escapeHtml(t.output || t.summary || "(sin salida)")}</pre></div>`).join("")
    || '<div class="muted">No se ejecutaron herramientas.</div>';
  el("pt-report").innerHTML = r.execution && r.execution.final_output
    ? renderMarkdown(r.execution.final_output)
    : `<p class="muted">${escapeHtml(r.status === "completed" ? "Sin informe." : r.message)}</p>`;
  const reportBtn = el("btn-pt-report");
  if (r.execution && r.execution.execution_id) {
    LAST_EXECUTION_ID = r.execution.execution_id;
    reportBtn.classList.remove("hidden");
    reportBtn.onclick = () => window.open(`/pentest/report/${r.execution.execution_id}`, "_blank");
  } else reportBtn.classList.add("hidden");
}

const SEV_KIND = { critical: "err", high: "err", medium: "warn", low: "", info: "" };
function renderFindings(r) {
  const findings = r.findings || [];
  const box = el("pt-findings");
  if (!findings.length) { box.innerHTML = ""; return; }
  const counts = r.findings_by_severity || {};
  const chips = ["critical", "high", "medium", "low", "info"].filter((s) => counts[s])
    .map((s) => `<span class="badge ${SEV_KIND[s] || ""}">${s}: ${counts[s]}</span>`).join(" ");
  const rows = findings.slice(0, 25).map((f) =>
    `<li><span class="badge ${SEV_KIND[f.severity] || ""}">${escapeHtml(f.severity)}</span>
      ${escapeHtml(f.title)} ${f.cve ? `<span class="badge accent">${escapeHtml(f.cve)}</span>` : ""}
      <span class="muted">· ${escapeHtml(f.tool)}</span></li>`).join("");
  box.innerHTML = `<div class="pt-findings-box"><div class="pt-findings-head">
      <strong>🚩 Hallazgos priorizados</strong> ${chips}</div>
      <ol class="pt-findings-list">${rows}</ol></div>`;
}

// --------------------------------------------------------------------------
// Ajustes
// --------------------------------------------------------------------------
let SETTINGS_INFO = { host_os: "", wsl_available: false };

async function loadSettings() {
  try {
    const s = await api("/settings");
    SETTINGS_INFO = { host_os: s.host_os, wsl_available: s.wsl_available };
    const models = s.available_models && s.available_models.length ? s.available_models : [s.default_ollama_model];
    const opts = [...new Set([s.default_ollama_model, ...models])].filter(Boolean);
    el("set-model").innerHTML = opts.map((m) =>
      `<option value="${escapeHtml(m)}"${m === s.default_ollama_model ? " selected" : ""}>${escapeHtml(m)}</option>`).join("");
    el("set-pentest").checked = s.enable_pentest_tools;
    el("set-scope").value = s.pentest_scope_allowlist || "";
    el("set-mode").value = s.pentest_execution_mode;
    const distros = s.wsl_distros || [];
    if (s.pentest_wsl_distro && !distros.includes(s.pentest_wsl_distro)) distros.push(s.pentest_wsl_distro);
    el("set-distro").innerHTML = '<option value="">(distro por defecto)</option>' +
      distros.map((d) => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join("");
    el("set-distro").value = s.pentest_wsl_distro || "";
    el("set-wsl-user").value = s.pentest_wsl_user || "";
    el("set-wsl-pass").placeholder = s.pentest_wsl_password_set ? "(configurada · sin cambios)" : "(sin definir)";
    // Email
    el("set-smtp-host").value = s.smtp_host || "";
    el("set-smtp-port").value = s.smtp_port || 587;
    el("set-smtp-user").value = s.smtp_user || "";
    el("set-smtp-from").value = s.smtp_from || "";
    el("set-smtp-pass").placeholder = s.smtp_password_set ? "(configurada · sin cambios)" : "(sin definir)";
    el("set-smtp-tls").checked = s.smtp_use_tls;
    el("set-notify").value = s.notify_email || "";
    el("set-test-email").value = s.notify_email || "";
    el("set-company").value = s.company_name || "";
    el("set-report-footer").value = s.report_footer || "";
    el("set-logo").value = s.report_logo_url || "";
    el("settings-host").innerHTML = `<span class="status-dot ${s.wsl_available ? "up" : "down"}"></span> Sistema: <strong>${escapeHtml(s.host_os)}</strong> · WSL ${s.wsl_available ? "detectado" : "no detectado"} · ${s.available_models.length} modelo(s) · email ${s.email_configured ? "configurado" : "sin configurar"}`;
    applyWslHint();
  } catch (e) { el("settings-msg").textContent = e.message; }
}

function applyWslHint() {
  const mode = el("set-mode").value;
  const hint = el("set-wsl-hint");
  if (mode !== "wsl") { hint.textContent = ""; return; }
  if (SETTINGS_INFO.wsl_available) hint.textContent = "WSL detectado en el host. Las herramientas se ejecutarán dentro de la distro indicada.";
  else if (SETTINGS_INFO.host_os === "Windows") hint.innerHTML = "WSL no detectado: instala Kali con <code>scripts/install-kali-windows.ps1</code>.";
  else hint.textContent = "Aviso: el host no es Windows y no se detecta 'wsl'. El modo WSL solo aplica en Windows.";
}

async function saveSettings() {
  const body = {
    default_ollama_model: el("set-model").value,
    enable_pentest_tools: el("set-pentest").checked,
    pentest_scope_allowlist: el("set-scope").value.trim(),
    pentest_execution_mode: el("set-mode").value,
    pentest_wsl_distro: el("set-distro").value.trim(),
    pentest_wsl_user: el("set-wsl-user").value.trim(),
    smtp_host: el("set-smtp-host").value.trim(),
    smtp_port: parseInt(el("set-smtp-port").value, 10) || 587,
    smtp_user: el("set-smtp-user").value.trim(),
    smtp_from: el("set-smtp-from").value.trim(),
    smtp_use_tls: el("set-smtp-tls").checked,
    notify_email: el("set-notify").value.trim(),
    company_name: el("set-company").value.trim(),
    report_footer: el("set-report-footer").value.trim(),
    report_logo_url: el("set-logo").value.trim(),
  };
  // Las contraseñas solo se envían si se escriben (vacío = no cambiar).
  if (el("set-wsl-pass").value) body.pentest_wsl_password = el("set-wsl-pass").value;
  if (el("set-smtp-pass").value) body.smtp_password = el("set-smtp-pass").value;
  el("btn-save-settings").disabled = true;
  try {
    await api("/settings", { method: "PUT", body: JSON.stringify(body) });
    el("settings-msg").textContent = "✓ Ajustes guardados.";
    toast("Ajustes guardados.", "ok");
    el("set-wsl-pass").value = ""; el("set-smtp-pass").value = "";
    loadModels(); loadSettings();
  } catch (e) { el("settings-msg").textContent = `✗ ${e.message}`; toast(e.message, "err"); }
  finally { el("btn-save-settings").disabled = false; }
}

async function testEmail() {
  const to = el("set-test-email").value.trim();
  if (!to) return toast("Indica un email para la prueba.", "err");
  el("btn-test-email").disabled = true;
  try {
    const r = await api("/settings/test-email", { method: "POST", body: JSON.stringify({ to }) });
    toast(r.message, r.ok ? "ok" : "err");
  } catch (e) { toast(e.message, "err"); }
  finally { el("btn-test-email").disabled = false; }
}

// --------------------------------------------------------------------------
// Init
// --------------------------------------------------------------------------
function setupSeg(segId, onChange) {
  el(segId).querySelectorAll(".seg-btn").forEach((b) => b.addEventListener("click", () => {
    el(segId).querySelectorAll(".seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); if (onChange) onChange(b);
  }));
}

document.addEventListener("DOMContentLoaded", () => {
  buildNav();
  setupSeg("mode-seg", applyMode);
  setupSeg("team-seg", applyTeamKind);
  setupSeg("search-mode");
  applyMode(); applyTeamKind();

  el("agent-select").addEventListener("change", updateAgentHint);
  el("squad-select").addEventListener("change", updateSquadHint);
  el("btn-route").addEventListener("click", previewRoute);
  el("btn-execute").addEventListener("click", executeTask);

  // Programador
  el("sched-target-kind").addEventListener("change", applySchedTarget);
  el("sched-kind").addEventListener("change", applySchedKind);
  el("sched-connector").addEventListener("change", applySchedConnector);
  el("btn-create-sched").addEventListener("click", createScheduledTask);
  el("btn-refresh-sched").addEventListener("click", loadScheduler);
  applySchedTarget(); applySchedKind(); applySchedConnector();

  // Pentest
  el("btn-pentest-run").addEventListener("click", runPentest);
  el("pt-auto").addEventListener("change", applyPtMode);
  el("btn-pt-recheck").addEventListener("click", recheckTools);
  el("btn-pt-install").addEventListener("click", installTools);

  // Ajustes
  el("btn-save-settings").addEventListener("click", saveSettings);
  el("btn-test-email").addEventListener("click", testEmail);
  el("set-mode").addEventListener("change", applyWslHint);
  el("btn-export-md").addEventListener("click", () => exportExecution("markdown"));
  el("btn-export-html").addEventListener("click", () => exportExecution("html"));
  el("btn-refresh-executions").addEventListener("click", loadExecutions);
  el("btn-clear-failed").addEventListener("click", clearFailedExecutions);

  // Informes
  el("btn-reports-refresh").addEventListener("click", loadReports);
  el("btn-reports-clear").addEventListener("click", async () => { await clearFailedExecutions(); loadReports(); });
  el("reports-filter").addEventListener("input", renderReports);
  el("btn-detail-md").addEventListener("click", () => window.open(`/executions/${el("execution-detail").dataset.exec}/export?format=markdown`, "_blank"));
  el("btn-detail-html").addEventListener("click", () => window.open(`/executions/${el("execution-detail").dataset.exec}/export?format=html`, "_blank"));
  el("btn-upload").addEventListener("click", uploadDocument);
  el("btn-reindex").addEventListener("click", reindexEmbeddings);
  el("btn-refresh-documents").addEventListener("click", loadDocuments);
  el("btn-search").addEventListener("click", searchDocuments);
  el("search-input").addEventListener("keydown", (e) => { if (e.key === "Enter") searchDocuments(); });

  // Dropzone
  const dz = el("dropzone"), fi = el("file-input");
  fi.addEventListener("change", () => { if (fi.files.length) el("dz-text").textContent = fi.files[0].name; });
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => { e.preventDefault(); dz.classList.remove("drag"); if (e.dataTransfer.files.length) { fi.files = e.dataTransfer.files; el("dz-text").textContent = fi.files[0].name; } });

  document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.goto)));

  loadHealth(); loadMetrics(); loadAgents(); loadSquads(); loadConnectors(); loadModels(); loadTools();
  setInterval(loadHealth, 30000);
});
