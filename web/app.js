const state = { view: "today", items: [], meta: {}, vaultAssets: [], identities: [], defaults: [], preview: null, selectedWorkflowId: "", workflowSteps: [], workflowQueue: { steps: [], telegram_mode: "queue_only" }, lastExecution: null };
const $ = (id) => document.getElementById(id);
const token = () => $("token").value.trim();
const routeFor = { today: "today", calendar: "calendar", workflows: "workflows", jobs: "jobs", accounts: "accounts", telegram: "telegram", vault: "vault/assets", content: "content" };
const titleFor = { today: "Hoy", calendar: "Calendario", workflows: "Workflows", jobs: "Ejecuciones", accounts: "Identidades", telegram: "Telegram", vault: "Vault", content: "Contenido" };
const labels = { identity_id: "Identidad", platform: "Plataforma", placement: "Destino", local_date: "Fecha", local_time: "Hora", state: "Estado", workflow_id: "Workflow", filename: "Archivo", username: "Cuenta", account_type: "Tipo", active: "Activo", created_at: "Creado", display_name: "Archivo", media_type: "Tipo", size_bytes: "Bytes", status: "Estado", path: "Ruta" };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function bootToken() {
  const params = new URLSearchParams(location.hash.slice(1));
  const supplied = params.get("token");
  const initialView = params.get("view");
  if (!supplied) return;
  $("token").value = supplied;
  history.replaceState(null, "", location.pathname);
  loadView(routeFor[initialView] ? initialView : state.view);
}

async function api(path, options = {}) {
  const headers = { Authorization: `Bearer ${token()}`, ...(options.headers || {}) };
  const response = await fetch(`/api/${path}`, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || payload.error || "Solicitud rechazada");
  return payload.data ?? payload.items ?? payload;
}

async function loadView(view = state.view) {
  state.view = view;
  $("view-title").textContent = titleFor[view] || view;
  document.querySelectorAll(".nav").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  try {
    const result = view === "workflows"
      ? await api("workflows")
      : await api(routeFor[view] || "today");
    state.meta = Array.isArray(result) ? {} : result;
    state.items = Array.isArray(result) ? result : (result.items || []);
    if (view === "workflows") {
      const [vault, identities] = await Promise.all([api("vault/assets"), api("identities")]);
      state.vaultAssets = vault.items || [];
      state.identities = identities || [];
      if (!state.items.some((item) => item.workflow_id === state.selectedWorkflowId)) state.selectedWorkflowId = state.items[0]?.workflow_id || "";
      state.workflowQueue = state.selectedWorkflowId ? await api("workflows/" + encodeURIComponent(state.selectedWorkflowId) + "/queue") : { steps: [], telegram_mode: "queue_only" };
    }
    if (view === "accounts") state.defaults = await api("publishing-defaults");
    render();
    $("status").textContent = `${state.items.length} registros cargados`;
  } catch (error) {
    state.items = [];
    state.meta = {};
    render();
    $("status").textContent = error.message;
  }
}

function render() {
  const needle = $("filter").value.toLowerCase();
  const items = state.items.filter((item) => JSON.stringify(item).toLowerCase().includes(needle));
  const pending = items.filter((item) => ["ready", "pending", "reserved"].includes(item.state)).length;
  const published = items.filter((item) => ["published_manual", "published"].includes(item.state)).length;
  $("metrics").innerHTML = `<div><b>${items.length}</b><span>Visibles</span></div><div><b>${pending}</b><span>Pendientes</span></div><div><b>${published}</b><span>Publicadas</span></div>`;
  if (state.view === "vault") return renderVault(items);
  if (state.view === "workflows") return renderWorkflows(items);
  if (state.view === "accounts") return renderIdentities(items);
  if (["today", "calendar", "telegram"].includes(state.view)) return renderTasks(items);
  if (!items.length) return renderEmpty();
  renderTable(items);
}

function workflowAction(item, index) {
  if (!item.workflow_job) return "";
  return "<button class=\"job-action\" data-action=\"queue-job\" data-item-index=\"" + index + "\">Agregar a workflow</button>";
}

function attachWorkflowButtons(items, container) {
  if (!container) return;
  container.querySelectorAll(".task").forEach((row, index) => {
    if (!items[index]?.workflow_job || row.querySelector("[data-action=queue-job]")) return;
    const button = document.createElement("button");
    button.className = "job-action";
    button.dataset.action = "queue-job";
    button.dataset.itemIndex = String(index);
    button.textContent = "Agregar a workflow";
    row.querySelector(".task-meta")?.appendChild(button);
  });
  container.querySelectorAll("tbody tr").forEach((row, index) => {
    if (!items[index]?.workflow_job || row.querySelector("[data-action=queue-job]")) return;
    const cell = row.insertCell(-1);
    const button = document.createElement("button");
    button.className = "job-action";
    button.dataset.action = "queue-job";
    button.dataset.itemIndex = String(index);
    button.textContent = "Agregar a workflow";
    cell.appendChild(button);
  });
  container.querySelectorAll("[data-action=queue-job]").forEach((button) => {
    button.addEventListener("click", () => queueJob(items[Number(button.dataset.itemIndex)]));
  });
}

function renderIdentities(items) {
  const rows = items.map((item) => {
    const settings = item.settings || {};
    const topicMode = settings.telegram_topic_mode || "identity_daily";
    return `<article class="identity-row" data-identity-id="${escapeHtml(item.identity_id)}"><div class="identity-title"><strong>${escapeHtml(item.display_name)}</strong><span>${escapeHtml(item.identity_id)} · ${escapeHtml(item.platform)}</span></div><div class="identity-fields"><input data-field="story_link_url" value="${escapeHtml(settings.story_link_url || "")}" placeholder="Enlace de Story"><input data-field="timezone" value="${escapeHtml(settings.timezone || "America/Argentina/Buenos_Aires")}" placeholder="Zona horaria"><input data-field="telegram_chat_id" value="${escapeHtml(settings.telegram_chat_id || "")}" placeholder="Chat ID Telegram"><select data-field="telegram_topic_mode"><option value="identity_daily" ${topicMode === "identity_daily" ? "selected" : ""}>Una cola por identidad</option><option value="identity_placement" ${topicMode === "identity_placement" ? "selected" : ""}>Separar por destino</option></select><button data-action="identity-save">Guardar</button></div></article>`;
  }).join("");
  const defaults = state.defaults.map((item) => `<tr><td>${escapeHtml(item.scope_kind)}</td><td>${escapeHtml(item.scope_id)}</td><td>${escapeHtml(item.setting_key)}</td><td>${escapeHtml(item.setting_value)}</td></tr>`).join("");
  $("result").innerHTML = `<section class="identity-form"><h2>Nueva identidad</h2><div class="identity-fields"><input id="identity-id" placeholder="ig:cuenta"><select id="identity-platform"><option value="instagram">Instagram</option><option value="facebook">Facebook</option></select><input id="identity-name" placeholder="Nombre visible"><button data-action="identity-create">Agregar</button></div></section><section class="identity-list">${rows || '<div class="empty">No hay identidades configuradas.</div>'}</section><section class="identity-form"><h2>Defaults de publicación</h2><div class="identity-fields"><select id="default-scope"><option value="global">Global</option><option value="platform">Plataforma</option></select><input id="default-scope-id" value="default" placeholder="default o instagram/facebook"><input id="default-key" value="timezone" placeholder="Clave"><input id="default-value" value="America/Argentina/Buenos_Aires" placeholder="Valor"><button data-action="default-save">Guardar default</button></div><table><thead><tr><th>Scope</th><th>ID</th><th>Clave</th><th>Valor</th></tr></thead><tbody>${defaults || '<tr><td colspan="4" class="empty">Sin defaults configurados.</td></tr>'}</tbody></table></section>`;
  document.querySelector('[data-action="identity-create"]').addEventListener("click", createIdentity);
  document.querySelectorAll('[data-action="identity-save"]').forEach((button) => button.addEventListener("click", () => saveIdentitySettings(button.closest(".identity-row"))));
  document.querySelector('[data-action="default-save"]').addEventListener("click", savePublishingDefault);
}

function renderTasks(items) {
  if (!items.length && state.view !== "telegram") return renderEmpty();
  const telegramControl = state.view === "telegram" ? `<section class="telegram-actions"><button data-action="telegram-deliver" ${items.length ? "" : "disabled"}>Enviar cola a Telegram</button></section>` : "";
  $("result").innerHTML = `${telegramControl}<div class="task-list">${items.map((item) => `<article class="task"><div class="task-main"><strong>${escapeHtml(item.local_date || "Sin fecha")} ${escapeHtml(item.local_time || "")}</strong><span>${escapeHtml(item.identity_id || item.username || "Identidad")}</span><span>${escapeHtml(item.placement || item.target || "Destino")}</span></div><div class="task-meta"><span class="state">${escapeHtml(item.state || "pendiente")}</span><span>${escapeHtml(item.delivery_path || item.filename || item.output_path || item.source_path || "Sin output")}</span>${isImageTask(item) && item.state !== "ready" ? `<button data-action="task-photo-forge" data-task-id="${escapeHtml(item.task_id)}">Producir foto</button>` : ""}${isVideoTask(item) && item.state !== "ready" ? `<button data-action="task-video-forge" data-task-id="${escapeHtml(item.task_id)}">Producir video</button>` : ""}${item.state === "published_manual" ? "" : `<button data-action="task-published" data-task-id="${escapeHtml(item.task_id)}">Publicado</button>`}</div></article>`).join("") || '<div class="empty">No hay outputs finales listos para Telegram.</div>'}</div>`;
  document.querySelectorAll('[data-action="task-published"]').forEach((button) => button.addEventListener("click", () => markTaskPublished(button.dataset.taskId)));
  document.querySelectorAll('[data-action="task-photo-forge"]').forEach((button) => button.addEventListener("click", () => produceTaskPhoto(button.dataset.taskId)));
  document.querySelectorAll('[data-action="task-video-forge"]').forEach((button) => button.addEventListener("click", () => produceTaskVideo(button.dataset.taskId)));
  attachWorkflowButtons(items, document.querySelector("#result"));
  const deliver = document.querySelector('[data-action="telegram-deliver"]');
  if (deliver) deliver.addEventListener("click", deliverTelegramQueue);
}

function isImageTask(item) {
  return /\.(jpg|jpeg|png|webp)$/i.test(item.source_path || "");
}

function isVideoTask(item) {
  return /\.(mp4|mov|mkv|avi)$/i.test(item.source_path || "");
}

function renderVault(items) {
  const rows = items.map((item) => `<tr><td>${escapeHtml(item.id)}</td><td>${escapeHtml(item.media_type)}</td><td>${escapeHtml(item.display_name)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.path)}</td></tr>`).join("");
  $("result").innerHTML = `<section class="vault-actions"><label>Archivo local<input id="vault-file" type="file" multiple accept="video/*,image/*"></label><button data-action="vault-upload">Importar al Vault</button><button data-action="vault-family">Nueva familia</button><button data-action="vault-collection">Nueva coleccion</button></section><div class="vault-summary">${state.meta.total || 0} assets registrados</div><table><thead><tr><th>ID</th><th>Tipo</th><th>Archivo</th><th>Estado</th><th>Ruta</th></tr></thead><tbody>${rows || '<tr><td colspan="5" class="empty">El Vault todavia no tiene assets.</td></tr>'}</tbody></table>`;
  document.querySelector('[data-action="vault-upload"]').addEventListener("click", uploadVaultFiles);
  document.querySelector('[data-action="vault-family"]').addEventListener("click", () => createVaultGroup("families", "Nombre de familia"));
  document.querySelector('[data-action="vault-collection"]').addEventListener("click", () => createVaultGroup("collections", "Nombre de coleccion"));
}

const MANUAL_MODULES = {
  forge: { label: "Forge", subtypes: { normal: "Normal", trials: "Trials" } },
  logistica: { label: "Logística", subtypes: { por_tandas: "Por tandas", por_cuentas: "Por cuentas" } },
  telegram: { label: "Telegram", subtypes: { send: "Enviar" } },
};

function blankStep(moduleType = "", subtype = "") {
  return {
    id: `paso_${Date.now()}_${state.workflowSteps.length + 1}`,
    module_type: moduleType,
    subtype,
    fields: { video_paths: [], account_names: [], fx_enabled: {}, overrides: null, metadata_assignments: [], caption_modes: {}, schedule_config: {}, fillup: false, express: false, reset_topics: false },
    profile_id: "",
    input_binding: {},
  };
}

function selectOptions(options, selected = "") {
  return `<option value=""></option>${Object.entries(options).map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("")}`;
}

function manualAssetOptions(selectedPaths) {
  const selected = new Set(selectedPaths || []);
  return state.vaultAssets.map((asset) => {
    const path = asset.path || asset.display_name || asset.id;
    return `<option value="${escapeHtml(asset.id)}" data-path="${escapeHtml(path)}" ${selected.has(path) || selected.has(String(asset.id)) ? "selected" : ""}>${escapeHtml(asset.display_name)} · ${escapeHtml(asset.media_type)}</option>`;
  }).join("");
}

function textField(name, label, value = "", type = "text", placeholder = "") {
  return `<label>${label}<input data-step-field="${name}" type="${type}" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}"></label>`;
}

function jsonField(name, label, value, placeholder) {
  const text = value && Object.keys(value).length ? JSON.stringify(value, null, 2) : "";
  return `<label>${label}<textarea data-step-field="${name}" placeholder="${escapeHtml(placeholder)}">${escapeHtml(text)}</textarea></label>`;
}

function renderForgeFields(step) {
  const fields = step.fields || {};
  const fx = ["crop", "mirror", "zoom", "rotate", "color", "noise", "speed", "trim"].map((key) => `<label class="workflow-check"><input type="checkbox" data-step-fx="${key}" ${fields.fx_enabled?.[key] ? "checked" : ""}>${key}</label>`).join("");
  return `<div class="workflow-step-grid"><label>Videos<select data-step-assets multiple size="5">${manualAssetOptions(fields.video_paths)}</select></label>${textField("tanda_name", "Nombre de tanda", fields.tanda_name)}${textField("copies", "Copias por vídeo", fields.copies || "", "number", "1")}${textField("days", "Días a distribuir", fields.days || "", "text", "MAX")}<label>Tipo Forge<select data-step-field="trial_mode"><option value=""></option><option value="Normal" ${step.subtype === "normal" ? "selected" : ""}>Normal</option><option value="Trials" ${step.subtype === "trials" ? "selected" : ""}>Trials</option></select></label><label>Efectos<select data-step-field="effects">${selectOptions({ Default: "Default", Light: "Light", Medio: "Medio", Alto: "Alto", Custom: "Custom" }, fields.effects)}</select></label><label>Fuerza<select data-step-field="strength">${selectOptions({ Default: "Default", Light: "Light", Medio: "Medio", Alto: "Alto", Custom: "Custom" }, fields.strength)}</select></label>${textField("forge_strength", "Intensidad general", fields.forge_strength || "", "number", "0.5")}${jsonField("overrides", "Rangos Custom", fields.overrides, "{\"zoom\":[1.00,1.05]}")}<label>Micro-ediciones por copia<div class="workflow-checks">${fx}</div></label>${jsonField("metadata_assignments", "Asignaciones de metadata", fields.metadata_assignments, "[]")}</div>`;
}

function renderLogisticaFields(step) {
  const fields = step.fields || {};
  const accounts = Array.isArray(fields.account_names) ? fields.account_names.join(", ") : (fields.account_names || "");
  return `<div class="workflow-step-grid"><div class="workflow-inline-note">Modo: <strong>${escapeHtml(MANUAL_MODULES.logistica.subtypes[step.subtype])}</strong></div>${textField("tanda_name", "Tanda principal", fields.tanda_name)}${textField("tanda_name_2", "2da tanda (opcional)", fields.tanda_name_2)}${textField("category_dest", "Categoría destino", fields.category_dest)}${textField("daily_quota", "Videos/día por cuenta", fields.daily_quota || "", "number", "1")}${textField("days", "Días o MAX", fields.days || "", "text", "MAX")}${step.subtype === "por_cuentas" ? textField("account_names", "Cuentas", accounts, "text", "cuenta1, cuenta2") : ""}<label class="workflow-check"><input type="checkbox" data-step-field="fillup" ${fields.fillup ? "checked" : ""}>Habilitar Fill-up</label>${jsonField("caption_modes", "Modo de captions por tanda", fields.caption_modes, "{\"SPAM\":\"general\"}")}</div>`;
}

function renderTelegramFields(step) {
  const fields = step.fields || {};
  const accounts = Array.isArray(fields.account_names) ? fields.account_names.join(", ") : (fields.account_names || "");
  return `<div class="workflow-step-grid">${textField("account_names", "Cuentas", accounts, "text", "cuenta1, cuenta2")}${textField("date", "Fecha inicio", fields.date || "", "date") }<label class="workflow-check"><input type="checkbox" data-step-field="express" ${fields.express ? "checked" : ""}>Envío express</label><label class="workflow-check"><input type="checkbox" data-step-field="reset_topics" ${fields.reset_topics ? "checked" : ""}>Borrar topics existentes y recrear</label>${jsonField("schedule_config", "Horarios", fields.schedule_config, "{\"cuenta1\":[\"09:00\"]}")}</div>`;
}

function renderManualStep(step, index) {
  const module = MANUAL_MODULES[step.module_type];
  const subtypeOptions = module ? selectOptions(module.subtypes, step.subtype) : "<option value=\"\"></option>";
  let fields = "<div class=\"workflow-empty-choice\"><strong>Elegí el módulo de este paso</strong><span>No se carga ningún perfil ni configuración automáticamente.</span></div>";
  if (step.module_type === "forge" && step.subtype) fields = renderForgeFields(step);
  if (step.module_type === "logistica" && step.subtype) fields = renderLogisticaFields(step);
  if (step.module_type === "telegram" && step.subtype) fields = renderTelegramFields(step);
  return `<article class="workflow-step" data-step-index="${index}"><div class="workflow-step-head"><strong>Paso ${index + 1}</strong><button data-action="workflow-remove-step" data-step-index="${index}">Quitar</button></div><div class="workflow-step-selectors"><label>Módulo<select data-step-field="module_type">${selectOptions(Object.fromEntries(Object.entries(MANUAL_MODULES).map(([key, value]) => [key, value.label])), step.module_type)}</select></label><label>Tipo<select data-step-field="subtype" ${module ? "" : "disabled"}>${subtypeOptions}</select></label><label>Perfil opcional<select data-profile-select data-step-index="${index}" ${module && step.subtype ? "" : "disabled"}><option value="">Sin perfil</option></select></label><button data-action="profile-load" data-step-index="${index}">Cargar perfil</button><button data-action="profile-save" data-step-index="${index}">Guardar como perfil</button><button data-action="profile-clear" data-step-index="${index}">Limpiar formulario</button></div>${index ? `<label class="workflow-check"><input type="checkbox" data-step-previous ${step.input_binding?.kind === "previous_output" ? "checked" : ""}>Usar output del paso anterior como input</label>` : ""}${fields}</article>`;
}

function renderWorkflows(items) {
  const workflowOptions = items.map((item) => `<option value="${escapeHtml(item.workflow_id)}" ${item.workflow_id === state.selectedWorkflowId ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
  const stepRows = state.workflowSteps.map(renderManualStep).join("");
  const listing = items.length ? `<table><thead><tr><th>Workflow</th><th>Creado</th><th>Activo</th><th></th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.created_at)}</td><td>${escapeHtml(item.active)}</td><td><button data-action="workflow-clone" data-workflow-id="${escapeHtml(item.workflow_id)}" data-workflow-name="${escapeHtml(item.name)}">Duplicar</button></td></tr>`).join("")}</tbody></table>` : '<div class="empty"><strong>Todavía no hay workflows</strong><span>Crea el primero desde pasos manuales.</span></div>';
  const emptySteps = '<div class="workflow-empty-choice"><strong>No hay pasos configurados</strong><span>Agregá Forge, Logística o Telegram y completá cada formulario manualmente.</span></div>';
  $("result").innerHTML = `<section class="workflow-setup"><header><div><p class="eyebrow">WORKFLOW MANUAL</p><h2>Pasos configurables</h2><span>Cada paso empieza vacío. Los perfiles solo se cargan si vos los elegís.</span></div></header><div class="workflow-grid"><label>Nombre<input id="workflow-name" placeholder="Ej. Forge → Logística → Telegram"></label></div><div class="workflow-step-list">${stepRows || emptySteps}</div><button data-action="workflow-add-step">Agregar paso</button><button data-action="workflow-create-and-continue">Guardar workflow</button></section><section class="workflow-list"><h2>Workflows guardados</h2>${listing}</section>`;
  $("result").insertAdjacentHTML("beforeend", renderWorkflowQueue(state.workflowQueue));
  document.querySelector('[data-action="workflow-add-step"]').addEventListener("click", () => { syncWorkflowSteps(); state.workflowSteps.push(blankStep()); renderWorkflows(items); });
  document.querySelector('[data-action="workflow-create-and-continue"]').addEventListener("click", createWorkflow);
  document.querySelectorAll('[data-action="workflow-remove-step"]').forEach((button) => button.addEventListener("click", () => { syncWorkflowSteps(); state.workflowSteps.splice(Number(button.dataset.stepIndex), 1); renderWorkflows(items); }));
  document.querySelectorAll('[data-step-field="module_type"]').forEach((select) => select.addEventListener("change", () => { syncWorkflowSteps(); const step = state.workflowSteps[Number(select.closest(".workflow-step").dataset.stepIndex)]; step.module_type = select.value; step.subtype = ""; step.fields = blankStep().fields; step.profile_id = ""; renderWorkflows(items); }));
  document.querySelectorAll('[data-step-field="subtype"]').forEach((select) => select.addEventListener("change", () => { syncWorkflowSteps(); const step = state.workflowSteps[Number(select.closest(".workflow-step").dataset.stepIndex)]; step.subtype = select.value; step.fields = blankStep().fields; step.fields.trial_mode = step.subtype === "trials" ? "Trials" : step.subtype === "normal" ? "Normal" : ""; step.profile_id = ""; renderWorkflows(items); }));
  document.querySelectorAll('[data-action="profile-load"]').forEach((button) => button.addEventListener("click", () => loadStepProfile(Number(button.dataset.stepIndex))));
  document.querySelectorAll('[data-action="profile-save"]').forEach((button) => button.addEventListener("click", () => saveStepProfile(Number(button.dataset.stepIndex))));
  document.querySelectorAll('[data-action="profile-clear"]').forEach((button) => button.addEventListener("click", () => { syncWorkflowSteps(); const step = state.workflowSteps[Number(button.dataset.stepIndex)]; step.fields = blankStep().fields; step.fields.trial_mode = step.subtype === "trials" ? "Trials" : step.subtype === "normal" ? "Normal" : ""; step.profile_id = ""; renderWorkflows(items); }));
  document.querySelectorAll('[data-action="queue-remove"]').forEach((button) => button.addEventListener("click", () => removeQueueStep(button.dataset.stepId)));
  document.querySelectorAll('[data-action="queue-up"], [data-action="queue-down"]').forEach((button) => button.addEventListener("click", () => moveQueueStep(button.dataset.stepId, button.dataset.direction)));
  document.querySelector('[data-action="queue-mode"]')?.addEventListener("change", saveTelegramMode);
  document.querySelector('[data-action="queue-execute"]')?.addEventListener("click", executeWorkflow);
  document.querySelectorAll('[data-action="workflow-clone"]').forEach((button) => button.addEventListener("click", () => cloneWorkflow(button.dataset.workflowId, button.dataset.workflowName)));
  state.workflowSteps.forEach((step, index) => { if (step.module_type && step.subtype) loadProfilesForStep(index); });
}

function readJsonField(row, name, fallback) {
  const raw = row.querySelector(`[data-step-field="${name}"]`)?.value.trim();
  if (!raw) return fallback;
  try { return JSON.parse(raw); } catch (_error) { throw new Error(`${name} debe contener JSON válido.`); }
}

function splitValues(value) {
  return String(value || "").split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
}

function readManualStep(row) {
  const value = (name) => row.querySelector(`[data-step-field="${name}"]`)?.value.trim() || "";
  const moduleType = value("module_type");
  const subtype = value("subtype");
  if (!moduleType || !subtype) return { module_type: moduleType, subtype, fields: {}, input_binding: row.querySelector("[data-step-previous]")?.checked ? { kind: "previous_output" } : {} };
  const fields = { module_type: moduleType, subtype };
  if (moduleType === "forge") {
    fields.video_paths = [...row.querySelectorAll("[data-step-assets] option:checked")].map((option) => option.dataset.path || option.value);
    Object.assign(fields, { tanda_name: value("tanda_name"), copies: Number(value("copies")), days: value("days"), trial_mode: value("trial_mode"), effects: value("effects"), strength: value("strength"), forge_strength: Number(value("forge_strength")), overrides: readJsonField(row, "overrides", null), metadata_assignments: readJsonField(row, "metadata_assignments", []) });
    fields.fx_enabled = Object.fromEntries([...row.querySelectorAll("[data-step-fx]")].map((input) => [input.dataset.stepFx, input.checked]));
  } else if (moduleType === "logistica") {
    Object.assign(fields, { mode: subtype, tanda_name: value("tanda_name"), tanda_name_2: value("tanda_name_2"), category_dest: value("category_dest"), daily_quota: Number(value("daily_quota")), days: value("days"), fillup: Boolean(row.querySelector('[data-step-field="fillup"]')?.checked), account_names: splitValues(value("account_names")), caption_modes: readJsonField(row, "caption_modes", {}) });
  } else {
    Object.assign(fields, { account_names: splitValues(value("account_names")), date: value("date"), express: Boolean(row.querySelector('[data-step-field="express"]')?.checked), reset_topics: Boolean(row.querySelector('[data-step-field="reset_topics"]')?.checked), schedule_config: readJsonField(row, "schedule_config", {}) });
  }
  return { module_type: moduleType, subtype, fields, input_binding: row.querySelector("[data-step-previous]")?.checked ? { kind: "previous_output" } : {} };
}

function syncWorkflowSteps() {
  document.querySelectorAll(".workflow-step").forEach((row) => { state.workflowSteps[Number(row.dataset.stepIndex)] = { ...state.workflowSteps[Number(row.dataset.stepIndex)], ...readManualStep(row) }; });
}

async function loadProfilesForStep(index) {
  const step = state.workflowSteps[index];
  const select = document.querySelector(`[data-profile-select][data-step-index="${index}"]`);
  if (!step || !select) return;
  try {
    const profiles = await api(`workflow-profiles?module_type=${encodeURIComponent(step.module_type)}&subtype=${encodeURIComponent(step.subtype)}`);
    select.innerHTML = '<option value="">Sin perfil</option>' + profiles.map((profile) => `<option value="${escapeHtml(profile.profile_id)}" ${profile.profile_id === step.profile_id ? "selected" : ""}>${escapeHtml(profile.name)}</option>`).join("");
  } catch (error) { $("status").textContent = error.message; }
}

async function loadStepProfile(index) {
  try {
    syncWorkflowSteps();
    const step = state.workflowSteps[index];
    const select = document.querySelector(`[data-profile-select][data-step-index="${index}"]`);
    if (!step?.module_type || !step.subtype || !select?.value) throw new Error("Elegí un perfil compatible para cargarlo.");
    const profiles = await api(`workflow-profiles?module_type=${encodeURIComponent(step.module_type)}&subtype=${encodeURIComponent(step.subtype)}`);
    const profile = profiles.find((item) => item.profile_id === select.value);
    if (!profile) throw new Error("No encontré ese perfil.");
    step.fields = { ...step.fields, ...profile.recipe };
    step.profile_id = profile.profile_id;
    renderWorkflows(state.items);
    $("status").textContent = `Perfil cargado: ${profile.name}. Revisalo antes de guardar el paso.`;
  } catch (error) { $("status").textContent = error.message; }
}

async function saveStepProfile(index) {
  try {
    syncWorkflowSteps();
    const step = state.workflowSteps[index];
    if (!step?.module_type || !step.subtype) throw new Error("Elegí módulo y tipo antes de guardar un perfil.");
    const name = window.prompt("Nombre del perfil");
    if (!name || !name.trim()) return;
    await api("workflow-profiles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ module_type: step.module_type, subtype: step.subtype, name: name.trim(), recipe: step.fields }) });
    $("status").textContent = "Perfil guardado. No se agregó ningún job.";
    await loadProfilesForStep(index);
  } catch (error) { $("status").textContent = error.message; }
}

function renderWorkflowQueue(queue) {
  const steps = queue?.steps || [];
  const rows = steps.map((step, index) => (
    '<article class="workflow-queue-step"><div><strong>' +
    (index + 1) + '. ' + escapeHtml(step.job_type) +
    '</strong><span>Salida: ' + escapeHtml(step.output_contract) +
    '</span><small>Entrada: ' +
    escapeHtml(step.input_binding?.step_id || step.input_binding?.kind || 'configuración propia') +
    '</small></div><div class="workflow-queue-actions">' +
    '<button data-action="queue-up" data-step-id="' + escapeHtml(step.step_id) + '" data-direction="up" ' +
    (index === 0 ? 'disabled' : '') + '>↑</button>' +
    '<button data-action="queue-down" data-step-id="' + escapeHtml(step.step_id) + '" data-direction="down" ' +
    (index === steps.length - 1 ? 'disabled' : '') + '>↓</button>' +
    '<button data-action="queue-remove" data-step-id="' + escapeHtml(step.step_id) + '">Quitar</button>' +
    '</div></article>'
  )).join('');
  return '<section class="workflow-queue"><header><div><p class="eyebrow">COLA DE JOBS</p>' +
    '<h2>Pasos encadenados</h2><span>' +
    (steps.length ? 'Cada job usa el output compatible del paso anterior cuando corresponde.' : 'Agrega jobs desde Ejecuciones, Hoy o Telegram.') +
    '</span></div></header><label class="workflow-queue-mode">Telegram<select data-action="queue-mode">' +
    '<option value="queue_only" ' + ((queue?.telegram_mode || 'queue_only') === 'queue_only' ? 'selected' : '') + '>Dejar en cola Telegram</option>' +
    '<option value="send_on_run" ' + (queue?.telegram_mode === 'send_on_run' ? 'selected' : '') + '>Enviar automáticamente</option>' +
    '</select></label><div class="workflow-queue-list">' +
    (rows || '<div class="empty">Todavía no hay jobs en este workflow.</div>') +
    '</div><button data-action="queue-execute" ' + (steps.length ? '' : 'disabled') + '>Ejecutar workflow</button></section>';
}

async function queueJob(item) {
  if (!state.selectedWorkflowId) {
    $('status').textContent = 'Selecciona un workflow en Workflows antes de agregar jobs.';
    return;
  }
  try {
    const job = JSON.parse(JSON.stringify(item.workflow_job));
    const previous = state.workflowQueue?.steps?.at(-1);
    if (!job.input_binding && previous && (job.input_contract === 'Any' || previous.output_contract === job.input_contract)) {
      job.input_binding = { kind: 'previous_output', step_id: previous.step_id };
    }
    await api('workflows/' + encodeURIComponent(state.selectedWorkflowId) + '/queue/steps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(job),
    });
    state.workflowQueue = await api('workflows/' + encodeURIComponent(state.selectedWorkflowId) + '/queue');
    $('status').textContent = 'Job agregado al workflow.';
  } catch (error) {
    $('status').textContent = error.message;
  }
}

async function removeQueueStep(stepId) {
  try {
    state.workflowQueue = await api('workflows/' + encodeURIComponent(state.selectedWorkflowId) + '/queue/remove', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ step_id: stepId }),
    });
    renderWorkflows(state.items);
  } catch (error) { $('status').textContent = error.message; }
}

async function moveQueueStep(stepId, direction) {
  const steps = [...(state.workflowQueue?.steps || [])];
  const index = steps.findIndex((step) => step.step_id === stepId);
  const target = direction === 'up' ? index - 1 : index + 1;
  if (index < 0 || target < 0 || target >= steps.length) return;
  [steps[index], steps[target]] = [steps[target], steps[index]];
  try {
    state.workflowQueue = await api('workflows/' + encodeURIComponent(state.selectedWorkflowId) + '/queue/reorder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step_ids: steps.map((step) => step.step_id) }),
    });
    renderWorkflows(state.items);
  } catch (error) { $('status').textContent = error.message; }
}

async function saveTelegramMode(event) {
  try {
    state.workflowQueue = await api('workflows/' + encodeURIComponent(state.selectedWorkflowId) + '/queue/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telegram_mode: event.target.value }),
    });
    $('status').textContent = 'Modo de Telegram guardado.';
  } catch (error) { $('status').textContent = error.message; }
}

async function executeWorkflow() {
  try {
    const result = await api('workflows/' + encodeURIComponent(state.selectedWorkflowId) + '/queue/execute', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    state.lastExecution = result;
    $('status').textContent = 'Workflow ' + result.state + '. Ejecución ' + result.execution_id + '.';
  } catch (error) { $('status').textContent = error.message; }
}

const QUEUE_JOB_TYPE = 'workflow.queue';

function parseWorkflowRules(text) {
  const grouped = { instagram: [], facebook: [] };
  for (const raw of text.split("\n")) {
    if (!raw.trim()) continue;
    const [target, times, everyDays] = raw.split("|").map((part) => part.trim());
    if (!target || !times || !everyDays || !(target.startsWith("instagram_") || target.startsWith("facebook_"))) throw new Error("Regla invalida. Usa destino | HH:MM,HH:MM | cada N dias.");
    const slots = times.split(",").map((value) => value.trim()).filter(Boolean);
    const platform = target.startsWith("instagram_") ? "instagram" : "facebook";
    grouped[platform].push({ target, times: slots, count: slots.length, every_days: Number(everyDays) });
  }
  return grouped;
}

function selectedWorkflowIdentities() {
  const identities = [...document.querySelectorAll("[data-workflow-identity]:checked")].map((input) => ({ identity_id: input.dataset.workflowIdentity, platform: input.dataset.platform }));
  if (!identities.length) throw new Error("Selecciona al menos una identidad.");
  return identities;
}

async function createWorkflow() {
  try {
    syncWorkflowSteps();
    const name = $("workflow-name").value.trim();
    if (!name) throw new Error("Ingresa un nombre de workflow.");
    if (!state.workflowSteps.length) throw new Error("Agrega al menos un paso.");
    if (state.workflowSteps.some((step) => !step.module_type || !step.subtype)) throw new Error("Elegí módulo y tipo para cada paso.");
    const workflow = await api("workflows/manual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, steps: state.workflowSteps }) });
    state.selectedWorkflowId = workflow.workflow_id;
    state.workflowSteps = [];
    $("status").textContent = "Workflow guardado con sus pasos manuales.";
    await loadView("workflows");
  } catch (error) { $("status").textContent = error.message; }
}

async function cloneWorkflow(workflowId, workflowName) {
  const name = window.prompt("Nombre de la copia", `${workflowName} copia`);
  if (!name || !name.trim()) return;
  try {
    await api(`workflows/${encodeURIComponent(workflowId)}/clone`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name.trim() }) });
    $("status").textContent = "Workflow duplicado.";
    await loadView("workflows");
  } catch (error) { $("status").textContent = error.message; }
}

async function createIdentity() {
  try {
    const identity_id = $("identity-id").value.trim();
    const platform = $("identity-platform").value;
    const display_name = $("identity-name").value.trim();
    await api("identities", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identity_id, platform, display_name }) });
    $("status").textContent = "Identidad guardada.";
    await loadView("accounts");
  } catch (error) { $("status").textContent = error.message; }
}

async function saveIdentitySettings(row) {
  try {
    const settings = Object.fromEntries([...row.querySelectorAll("[data-field]")].map((field) => [field.dataset.field, field.value.trim()]));
    await api(`identities/${encodeURIComponent(row.dataset.identityId)}/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ settings }) });
    $("status").textContent = "Configuración de identidad guardada.";
    await loadView("accounts");
  } catch (error) { $("status").textContent = error.message; }
}

async function savePublishingDefault() {
  try {
    const scope_kind = $("default-scope").value;
    const scope_id = $("default-scope-id").value.trim();
    const setting_key = $("default-key").value.trim();
    const setting_value = $("default-value").value.trim();
    await api("publishing-defaults", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope_kind, scope_id, setting_key, setting_value }) });
    $("status").textContent = "Default guardado.";
    await loadView("accounts");
  } catch (error) { $("status").textContent = error.message; }
}

async function previewWorkflow() {
  try {
    const candidates = [...document.querySelectorAll(".workflow-block")].flatMap((row) => {
      const block = state.workflowBlocks[Number(row.dataset.blockIndex)];
      return [...row.querySelector("[data-block-assets]").selectedOptions].map((option) => ({ source_id: `vault-${option.value}-${block.id}`, source_path: option.dataset.path, media_class: option.dataset.type, production_block_id: block.id }));
    });
    if (!candidates.length) throw new Error("Selecciona fuentes del Vault.");
    state.preview = await api("previews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workflow_id: $("workflow-select").value, identities: selectedWorkflowIdentities(), candidates, start_date: $("workflow-start").value, days: Number($("workflow-days").value), timezone: $("workflow-timezone").value, mode: "strict" }) });
    renderWorkflows(state.items);
  } catch (error) { $("status").textContent = error.message; }
}

async function confirmWorkflowPreview() {
  try {
    const result = await api("previews/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preview: state.preview }) });
    const videos = state.preview.tasks.filter((task) => isVideoTask(task)).map((task) => task.demand_id);
    const images = state.preview.tasks.filter((task) => isImageTask(task)).map((task) => task.demand_id);
    if (videos.length) await api("tasks/video-forge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_ids: videos }) });
    if (images.length) await api("tasks/photo-forge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_ids: images }) });
    $("status").textContent = `${result.created} tareas confirmadas y producidas. Ya estan listas para la cola manual de Telegram.`;
    state.preview = null;
    await loadView("calendar");
  } catch (error) { $("status").textContent = error.message; }
}

function renderTable(items) {
  const keys = [...new Set(items.flatMap((item) => Object.keys(item)))].filter((key) => key !== "payload").slice(0, 9);
  $("result").innerHTML = `<table><thead><tr>${keys.map((key) => `<th>${escapeHtml(labels[key] || key)}</th>`).join("")}</tr></thead><tbody>${items.map((item) => `<tr>${keys.map((key) => `<td>${escapeHtml(typeof item[key] === "object" ? JSON.stringify(item[key]) : item[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  attachWorkflowButtons(items, document.querySelector("#result"));
}

function renderEmpty() {
  const messages = { today: ["No hay publicaciones para hoy", "Crea un workflow y confirma su preview para llenar la cola."], calendar: ["Calendario sin tareas", "Las publicaciones confirmadas apareceran ordenadas por dia e identidad."], workflows: ["Todavia no hay workflows", "Crea recetas y plantillas para reutilizarlas con otras tandas o cuentas."], jobs: ["No hay ejecuciones", "Los jobs de Forge y Photo Forge apareceran aqui."], accounts: ["No hay identidades cargadas", "Agrega o importa cuentas desde Legacy."], telegram: ["Cola Telegram vacia", "Las tareas confirmadas se agruparan aqui antes de publicar manualmente."], content: ["No hay contenido registrado", "Los renders y outputs de Forge apareceran aqui."] };
  const [title, detail] = messages[state.view] || ["Sin registros", ""];
  $("result").innerHTML = `<div class="empty"><strong>${title}</strong><span>${detail}</span></div>`;
}

async function uploadVaultFiles() {
  const files = [...$("vault-file").files];
  if (!files.length) { $("status").textContent = "Selecciona al menos un archivo."; return; }
  try {
    for (const file of files) {
      const response = await fetch("/api/vault/upload", { method: "POST", headers: { Authorization: `Bearer ${token()}`, "X-Filename": encodeURIComponent(file.name), "Content-Type": file.type || "application/octet-stream" }, body: file });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || payload.error || "No se pudo importar el archivo");
    }
    $("status").textContent = `${files.length} archivos importados al Vault.`;
    await loadView("vault");
  } catch (error) { $("status").textContent = error.message; }
}

async function createVaultGroup(kind, promptText) {
  const name = window.prompt(promptText);
  if (!name || !name.trim()) return;
  try {
    await api(`vault/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name.trim() }) });
    $("status").textContent = "Guardado correctamente.";
  } catch (error) { $("status").textContent = error.message; }
}

async function markTaskPublished(taskId) {
  try {
    await api(`tasks/${encodeURIComponent(taskId)}/published`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    $("status").textContent = "Tarea marcada como publicada.";
    await refresh();
  } catch (error) { $("status").textContent = error.message; }
}

async function produceTaskPhoto(taskId) {
  try {
    const result = await api("tasks/photo-forge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_ids: [taskId] }) });
    if (!result.ready) throw new Error("Photo Forge no completo el output final.");
    $("status").textContent = "Photo Forge finalizado.";
    await refresh();
  } catch (error) { $("status").textContent = error.message; }
}

async function produceTaskVideo(taskId) {
  try {
    const result = await api("tasks/video-forge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_ids: [taskId] }) });
    if (!result.ready) throw new Error("Forge no completo el output final.");
    $("status").textContent = "Forge de video finalizado.";
    await refresh();
  } catch (error) { $("status").textContent = error.message; }
}

async function deliverTelegramQueue() {
  try {
    const result = await api("telegram/deliver", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    $("status").textContent = `${result.sent} tareas enviadas a Telegram.`;
    await loadView("telegram");
  } catch (error) { $("status").textContent = error.message; }
}

function refresh() { return loadView(state.view); }
document.querySelectorAll(".nav").forEach((button) => button.addEventListener("click", () => loadView(button.dataset.view)));
$("filter").addEventListener("input", render);
document.querySelector('[data-action="connect"]').addEventListener("click", refresh);
document.querySelector('[data-action="refresh"]').addEventListener("click", refresh);
window.loadView = loadView;
bootToken();
