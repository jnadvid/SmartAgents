/* OCS Agentic Enterprise Platform - frontend (vanilla JS, sin dependencias) */
"use strict";

const API_BASE = ""; // mismo origen: FastAPI sirve frontend y API

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

async function api(path, options = {}) {
  const response = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) { /* respuesta sin JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

function el(id) { return document.getElementById(id); }

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

/** Conversor Markdown -> HTML mínimo (titulares, listas, negrita, código). */
function renderMarkdown(md) {
  const lines = escapeHtml(md).split("\n");
  const html = [];
  let inList = false, inOrdered = false, inCode = false;

  const closeLists = () => {
    if (inList) { html.push("</ul>"); inList = false; }
    if (inOrdered) { html.push("</ol>"); inOrdered = false; }
  };

  for (const rawLine of lines) {
    const line = rawLine;
    if (line.trim().startsWith("```")) {
      closeLists();
      html.push(inCode ? "</code></pre>" : "<pre><code>");
      inCode = !inCode;
      continue;
    }
    if (inCode) { html.push(line); continue; }

    const inline = (text) => text
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

    let match;
    if ((match = line.match(/^(#{1,3})\s+(.*)$/))) {
      closeLists();
      const level = match[1].length;
      html.push(`<h${level}>${inline(match[2])}</h${level}>`);
    } else if ((match = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (inOrdered) { html.push("</ol>"); inOrdered = false; }
      if (!inList) { html.push("<ul>"); inList = true; }
      html.push(`<li>${inline(match[1])}</li>`);
    } else if ((match = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      if (inList) { html.push("</ul>"); inList = false; }
      if (!inOrdered) { html.push("<ol>"); inOrdered = true; }
      html.push(`<li>${inline(match[1])}</li>`);
    } else if (/^\s*(---|\*\*\*)\s*$/.test(line)) {
      closeLists();
      html.push("<hr/>");
    } else if (line.trim() === "") {
      closeLists();
    } else {
      closeLists();
      html.push(`<p>${inline(line)}</p>`);
    }
  }
  closeLists();
  if (inCode) html.push("</code></pre>");
  return html.join("\n");
}

function confidenceBadge(score) {
  if (score == null) return "";
  const pct = Math.round(score * 100);
  const cls = score >= 0.7 ? "ok" : score >= 0.45 ? "warn" : "err";
  return `<span class="badge ${cls}">Confianza: ${pct}%</span>`;
}

function statusBadge(status) {
  const cls = status === "completed" ? "ok" : status === "failed" ? "err" : "warn";
  return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
}

// ---------------------------------------------------------------------------
// Estado de salud y catálogos
// ---------------------------------------------------------------------------

let AGENTS = [];

async function loadHealth() {
  const apiPill = el("status-api");
  const ollamaPill = el("status-ollama");
  try {
    await api("/health");
    apiPill.classList.add("up");
    apiPill.querySelector("span").textContent = "OK";
  } catch (_) {
    apiPill.classList.add("down");
    apiPill.querySelector("span").textContent = "caída";
    return;
  }
  try {
    const ollama = await api("/health/ollama");
    ollamaPill.classList.remove("up", "down");
    ollamaPill.classList.add(ollama.status === "up" ? "up" : "down");
    ollamaPill.querySelector("span").textContent =
      ollama.status === "up" ? `OK (${ollama.models_available} modelos)` : "caído";
    ollamaPill.title = ollama.detail || `Modelo por defecto: ${ollama.default_model}` +
      (ollama.default_model_available ? " (disponible)" : " (NO descargado)");
  } catch (err) {
    ollamaPill.classList.add("down");
    ollamaPill.querySelector("span").textContent = "error";
    ollamaPill.title = String(err.message || err);
  }
}

async function loadAgents() {
  try {
    AGENTS = await api("/agents");
    const select = el("agent-select");
    select.innerHTML = AGENTS.map(
      (agent) => `<option value="${escapeHtml(agent.name)}">${escapeHtml(agent.display_name)} (${escapeHtml(agent.category)})</option>`
    ).join("");
    updateAgentDescription();
  } catch (err) {
    console.error("No se pudieron cargar los agentes:", err);
  }
}

function updateAgentDescription() {
  const name = el("agent-select").value;
  const agent = AGENTS.find((a) => a.name === name);
  el("agent-description").textContent = agent
    ? `${agent.description} Herramientas: ${agent.allowed_tools.join(", ") || "ninguna"}.`
    : "";
}

async function loadModels() {
  const select = el("model-select");
  try {
    const models = await api("/models");
    select.innerHTML = '<option value="">(modelo por defecto)</option>' + models.map(
      (model) => `<option value="${escapeHtml(model.name)}">${escapeHtml(model.name)}</option>`
    ).join("");
  } catch (err) {
    select.innerHTML = `<option value="">(Ollama no disponible)</option>`;
  }
}

async function loadTools() {
  try {
    const tools = await api("/tools");
    el("tools-list").innerHTML = tools.map((tool) => `
      <div class="tool-card">
        <h3>${escapeHtml(tool.name)}</h3>
        <p><span class="badge accent">${escapeHtml(tool.category)}</span>
           <span class="badge">timeout ${tool.timeout_seconds}s</span></p>
        <p>${escapeHtml(tool.description)}</p>
      </div>`).join("");
  } catch (err) {
    el("tools-list").innerHTML = `<p class="hint">Error cargando herramientas: ${escapeHtml(err.message)}</p>`;
  }
}

// ---------------------------------------------------------------------------
// Ejecución de tareas
// ---------------------------------------------------------------------------

function currentMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

async function previewRoute() {
  const task = el("task-input").value.trim();
  const preview = el("route-preview");
  if (!task) { alert("Escribe una tarea primero."); return; }
  preview.classList.remove("hidden");
  preview.textContent = "Clasificando...";
  try {
    const route = await api("/agents/route", { method: "POST", body: JSON.stringify({ task }) });
    preview.innerHTML =
      `Intención: <strong>${escapeHtml(route.detected_intent)}</strong> ` +
      `(confianza ${Math.round(route.intent_confidence * 100)}%, método ${escapeHtml(route.classification_method)})<br/>` +
      `Agente: <strong>${escapeHtml(route.selected_agent)}</strong>` +
      (route.auxiliary_agents.length ? ` · Auxiliares propuestos: ${route.auxiliary_agents.map(escapeHtml).join(", ")}` : "") +
      `<br/><span class="hint">${escapeHtml(route.reason)}</span>`;
  } catch (err) {
    preview.textContent = `Error: ${err.message}`;
  }
}

async function executeTask() {
  const task = el("task-input").value.trim();
  if (!task) { alert("Escribe una tarea primero."); return; }

  const body = {
    task,
    agent_name: currentMode() === "manual" ? el("agent-select").value : null,
    model: el("model-select").value || null,
    use_documents: el("use-documents").checked,
    extra_context: el("context-input").value.trim() || null,
  };

  el("result-empty").classList.add("hidden");
  el("result-content").classList.add("hidden");
  el("result-loading").classList.remove("hidden");
  el("btn-execute").disabled = true;

  try {
    const result = await api("/agents/execute", { method: "POST", body: JSON.stringify(body) });
    renderResult(result);
  } catch (err) {
    el("result-content").classList.remove("hidden");
    el("result-meta").innerHTML = "";
    el("result-output").innerHTML = "";
    el("verification-list").innerHTML = "";
    el("tools-used-list").innerHTML = "";
    el("cow-list").innerHTML = "";
    const errorBox = el("result-error");
    errorBox.classList.remove("hidden");
    errorBox.textContent = `Error: ${err.message}`;
  } finally {
    el("result-loading").classList.add("hidden");
    el("btn-execute").disabled = false;
  }
}

function renderCow(listElement, steps) {
  listElement.innerHTML = steps.map((step) => `
    <li class="risk-${escapeHtml(step.risk_level)}">
      <span class="cow-type">${escapeHtml(step.step_type)}</span><br/>
      <span class="cow-title">${escapeHtml(step.title)}</span>
      ${step.description ? `<div class="cow-desc">${escapeHtml(step.description)}</div>` : ""}
      ${step.tool_name ? `<div class="cow-desc">Herramienta: <code>${escapeHtml(step.tool_name)}</code></div>` : ""}
      ${step.evidence ? `<div class="cow-evidence">${escapeHtml(step.evidence)}</div>` : ""}
    </li>`).join("");
}

function renderResult(result) {
  el("result-content").classList.remove("hidden");

  const errorBox = el("result-error");
  if (result.status === "failed") {
    errorBox.classList.remove("hidden");
    errorBox.textContent = result.error_message || "La ejecución falló.";
  } else {
    errorBox.classList.add("hidden");
  }

  el("result-meta").innerHTML = [
    `<span class="badge accent">Agente: ${escapeHtml(result.agent_name)}</span>`,
    `<span class="badge">Intención: ${escapeHtml(result.detected_intent)}</span>`,
    `<span class="badge">${result.selected_by_router ? "Auto (router)" : "Manual"}</span>`,
    `<span class="badge">Modelo: ${escapeHtml(result.model_name)}</span>`,
    statusBadge(result.status),
    confidenceBadge(result.confidence ? result.confidence.score : null),
    result.documents_used ? `<span class="badge">Docs usados: ${result.documents_used}</span>` : "",
    `<span class="badge">Ejecución #${result.execution_id}</span>`,
  ].join(" ");

  el("result-output").innerHTML = result.final_output
    ? renderMarkdown(result.final_output)
    : '<p class="hint">Sin salida.</p>';

  el("verification-list").innerHTML = (result.verification ? result.verification.checks : [])
    .map((check) => `<li class="${check.passed ? "check-ok" : "check-fail"}">
        <strong>${escapeHtml(check.name)}</strong>: ${escapeHtml(check.detail)}</li>`)
    .join("") || "<li>No disponible.</li>";

  el("tools-used-list").innerHTML = (result.tool_results || [])
    .map((tool) => `<li class="${tool.status === "success" ? "check-ok" : "check-fail"}">
        <code>${escapeHtml(tool.tool_name)}</code> (${escapeHtml(tool.status)}, ${tool.duration_ms} ms)
        ${tool.error_message ? `— ${escapeHtml(tool.error_message)}` : ""}</li>`)
    .join("") || "<li>No se usaron herramientas.</li>";

  renderCow(el("cow-list"), result.chain_of_work || []);
  loadExecutions(); // refresca el histórico en segundo plano
}

// ---------------------------------------------------------------------------
// Ejecuciones anteriores
// ---------------------------------------------------------------------------

async function loadExecutions() {
  try {
    const executions = await api("/executions?limit=50");
    const tbody = el("executions-table").querySelector("tbody");
    tbody.innerHTML = executions.map((execution) => `
      <tr>
        <td>${execution.id}</td>
        <td>${escapeHtml(execution.agent_name)}</td>
        <td>${escapeHtml(execution.intent)}</td>
        <td>${escapeHtml(execution.model_name)}</td>
        <td>${statusBadge(execution.status)}</td>
        <td>${execution.confidence_score != null ? Math.round(execution.confidence_score * 100) + "%" : "—"}</td>
        <td>${new Date(execution.created_at).toLocaleString()}</td>
        <td><button class="btn secondary small" data-execution="${execution.id}">Ver</button></td>
      </tr>`).join("");
    tbody.querySelectorAll("button[data-execution]").forEach((button) => {
      button.addEventListener("click", () => showExecutionDetail(button.dataset.execution));
    });
  } catch (err) {
    console.error("No se pudieron cargar las ejecuciones:", err);
  }
}

async function showExecutionDetail(executionId) {
  try {
    const [detail, cow] = await Promise.all([
      api(`/executions/${executionId}`),
      api(`/executions/${executionId}/chain-of-work`),
    ]);
    el("execution-detail").classList.remove("hidden");
    el("execution-detail-title").innerHTML =
      `Ejecución #${detail.id} — ${escapeHtml(detail.agent_name)} ${statusBadge(detail.status)} ${confidenceBadge(detail.confidence_score)}`;
    el("execution-detail-output").innerHTML = detail.final_output
      ? renderMarkdown(detail.final_output)
      : `<p class="hint">${escapeHtml(detail.error_message || "Sin salida.")}</p>`;
    renderCow(el("execution-detail-cow"), cow.steps);
    el("execution-detail").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert(`Error cargando la ejecución: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Documentos
// ---------------------------------------------------------------------------

async function uploadDocument() {
  const input = el("file-input");
  const status = el("upload-status");
  if (!input.files.length) { alert("Selecciona un archivo primero."); return; }
  const formData = new FormData();
  formData.append("file", input.files[0]);
  status.textContent = "Subiendo e indexando...";
  try {
    const response = await fetch(`${API_BASE}/documents/upload`, { method: "POST", body: formData });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    status.textContent = `OK: ${body.message}`;
    input.value = "";
    loadDocuments();
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  }
}

async function loadDocuments() {
  try {
    const documents = await api("/documents");
    el("documents-list").innerHTML = documents.length
      ? documents.map((doc) => `
          <li>
            <strong>${escapeHtml(doc.filename)}</strong>
            <div class="doc-meta">id=${doc.id} · ${escapeHtml(doc.content_type)} ·
              ${new Date(doc.uploaded_at).toLocaleString()}</div>
          </li>`).join("")
      : '<li class="hint">No hay documentos subidos.</li>';
  } catch (err) {
    el("documents-list").innerHTML = `<li class="hint">Error: ${escapeHtml(err.message)}</li>`;
  }
}

async function searchDocuments() {
  const query = el("search-input").value.trim();
  const list = el("search-results");
  if (query.length < 2) { alert("Escribe al menos 2 caracteres."); return; }
  list.innerHTML = "<li>Buscando...</li>";
  try {
    const result = await api("/documents/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 5 }),
    });
    list.innerHTML = result.hits.length
      ? result.hits.map((hit) => `
          <li>
            <strong>${escapeHtml(hit.filename)}</strong>
            <span class="doc-meta">(chunk ${hit.chunk_index}, score ${hit.score})</span>
            <div class="snippet">${escapeHtml(hit.snippet)}</div>
          </li>`).join("")
      : '<li class="hint">Sin resultados.</li>';
  } catch (err) {
    list.innerHTML = `<li class="hint">Error: ${escapeHtml(err.message)}</li>`;
  }
}

// ---------------------------------------------------------------------------
// Navegación e inicialización
// ---------------------------------------------------------------------------

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      el(`panel-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

function setupModeToggle() {
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      el("agent-select-wrap").classList.toggle("hidden", currentMode() !== "manual");
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupModeToggle();
  el("agent-select").addEventListener("change", updateAgentDescription);
  el("btn-route").addEventListener("click", previewRoute);
  el("btn-execute").addEventListener("click", executeTask);
  el("btn-refresh-executions").addEventListener("click", loadExecutions);
  el("btn-upload").addEventListener("click", uploadDocument);
  el("btn-refresh-documents").addEventListener("click", loadDocuments);
  el("btn-search").addEventListener("click", searchDocuments);
  el("search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchDocuments();
  });

  loadHealth();
  loadAgents();
  loadModels();
  loadTools();
  loadExecutions();
  loadDocuments();
  setInterval(loadHealth, 30000);
});
