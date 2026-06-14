/* OCS Agentic Enterprise Platform - frontend Fase 3 (vanilla JS, offline) */
"use strict";

const API = "";
let AGENTS = [];
let SQUADS = [];
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
};

const VIEWS = [
  { id: "dashboard", label: "Dashboard", sub: "Visión general de la plataforma" },
  { id: "assistant", label: "Asistente", sub: "Lanza una tarea a un agente o equipo" },
  { id: "agents", label: "Agentes", sub: "Catálogo por áreas y equipos" },
  { id: "executions", label: "Ejecuciones", sub: "Histórico y trazabilidad" },
  { id: "scheduler", label: "Programador", sub: "Tareas puntuales y periódicas" },
  { id: "documents", label: "Documentos", sub: "RAG local: subida y búsqueda" },
  { id: "tools", label: "Herramientas", sub: "Catálogo de herramientas locales" },
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
  if (id === "scheduler") loadScheduler();
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
       <td><button class="btn ghost sm" data-exec="${e.id}">Ver</button></td></tr>`).join("");
    el("executions-table").querySelectorAll("button[data-exec]").forEach((b) =>
      b.addEventListener("click", () => showExecutionDetail(b.dataset.exec)));
  } catch (_) {}
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
      return `<tr><td><strong>${escapeHtml(t.name)}</strong><div class="doc-meta">#${t.id}</div></td>
        <td>${target}</td><td>${escapeHtml(t.schedule_human)}</td>
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
  el("btn-create-sched").addEventListener("click", createScheduledTask);
  el("btn-refresh-sched").addEventListener("click", loadScheduler);
  applySchedTarget(); applySchedKind();
  el("btn-export-md").addEventListener("click", () => exportExecution("markdown"));
  el("btn-export-html").addEventListener("click", () => exportExecution("html"));
  el("btn-refresh-executions").addEventListener("click", loadExecutions);
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

  loadHealth(); loadMetrics(); loadAgents(); loadSquads(); loadModels(); loadTools();
  setInterval(loadHealth, 30000);
});
