/*
 * Local desktop UI.  When opened through `python app.py serve-studio`, its
 * project/source/script actions are backed by the loopback Python service.
 * The in-memory fallback below only keeps this design file viewable by itself.
 */
const NAVIGATION = [
  ["dashboard", "▦", "Dashboard"], ["import", "⇩", "Import"], ["script", "≡", "Script"],
  ["scenes", "✂", "Final Review"], ["voice", "◖", "Voice"], ["subtitles", "▤", "Subtitles"],
  ["audio", "♫", "Audio"], ["render", "▶", "Render"], ["settings", "⚙", "Settings"],
];

const LANGUAGE_CATALOG = [
  { id: "vi", label: "Vietnamese", locales: ["default", "vi-North", "vi-South", "vi-Central"] },
  { id: "en", label: "English", locales: ["en-US", "en-GB", "en-AU"] },
  { id: "ja", label: "Japanese", locales: ["ja-JP"] },
  { id: "ko", label: "Korean", locales: ["ko-KR"] },
  { id: "zh", label: "Chinese", locales: ["zh-CN", "zh-TW"] },
  { id: "es", label: "Spanish", locales: ["es-ES", "es-MX"] },
  { id: "fr", label: "French", locales: ["fr-FR", "fr-CA"] },
  { id: "de", label: "German", locales: ["de-DE"] },
  { id: "th", label: "Thai", locales: ["th-TH"] },
  { id: "id", label: "Indonesian", locales: ["id-ID"] },
];

const VOICE_CAPABILITIES = {
  activeProvider: "omnivoice",
  providerName: "OmniVoice",
  supportedLanguages: ["vi"],
  modes: ["auto", "voice_design"],
  gender: true,
  age: true,
  pitch: true,
  styles: false,
  clone: false,
  referenceAudio: false,
  advanced: false,
  speed: { min: 0.85, max: 1.2, step: 0.01 },
};

const DEFAULT_NARRATION = "Dự án này bắt đầu bằng bối cảnh rõ ràng, sau đó dẫn người xem qua các ý chính theo từng cảnh có thể kiểm soát độc lập.";

function makeScenes(count) {
  const subjects = ["Opening context", "Core idea", "Key evidence", "Detail", "Change over time", "Human perspective", "Practical impact", "System view", "Next question", "Closing thought"];
  return Array.from({ length: count }, (_, index) => ({
    id: `scene_${String(index + 1).padStart(2, "0")}`,
    number: index + 1,
    title: subjects[index] || `Scene ${index + 1}`,
    narration: index === 0 ? DEFAULT_NARRATION : "",
    source: index % 6 === 5 ? "Missing" : "Google Flow",
    sourceVersion: index % 3 === 0 ? 2 : 1,
    duration: +(5.4 + ((index * 11) % 31) / 10).toFixed(1),
    status: index < 8 ? "approved" : index === 10 ? "rejected" : "pending",
    sourceAudio: { mode: "background", volume: 30, duck: true, fadeIn: .15, fadeOut: .2 },
    edit: { trimStart: 0, trimEnd: null, speed: 1, crop: "cover", position: "center", holdLastFrame: true, transition: index === 0 ? "none" : "soft slide" },
    decision: "keep",
    voiceOverride: null,
  }));
}

const state = {
  workspaceState: { projects: [], activeProjectId: null },
  projectState: { id: "", name: "No project", initials: "NP", stage: "DRAFT", resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: false },
  sceneState: { items: [], selectedId: null, sceneCount: 0, timelineZoom: 1 },
  scriptState: { bulkText: "", mapped: 0, missing: 0, approved: false },
  voiceState: {
    provider: "omnivoice", language: "vi", locale: "default", mode: "voice_design", gender: "male", age: "young adult", pitch: "moderate", style: "documentary", speed: 1.1,
    profileId: null, previewText: DEFAULT_NARRATION, previewStatus: "NOT GENERATED", previewUrl: null, playing: false, subtitleSync: "PENDING", advancedOpen: false,
    profiles: [], history: [], comparisons: [], pronunciation: [],
  },
  voiceRuntime: { available: false, ready_for_generation: false, status: "checking", detail: "Checking local OmniVoice runtime…" },
  subtitleState: { language: "same", font: "Be Vietnam Pro", weight: "SemiBold", size: 55, position: "Bottom", offset: 102, highlight: true, safeZone: true },
  audioState: { narration: 100, source: 30, sourceMode: "background", sourceDuck: true, bgm: 12, sfx: 35, master: 100 },
  workflowState: { scriptApproved: false, voiceApproved: false, previewReady: false, previewApproved: false, finalReady: false },
  reviewState: { finalized: false, dirty: false },
  automationState: { status: "SOURCE READY", progress: 100, step: 1 },
  importReport: null,
  renderState: { quality: "preview", status: "READY", progress: 0, activeStep: -1, requestScene: "scene_11", requestCategory: "Source", videoUrl: null, error: null, voiceSteps: 4 },
  uiState: { screen: "dashboard", inspector: "scene", projectMenuOpen: false },
};

const DEFAULT_VOICE_STATE = structuredClone(state.voiceState);
const DEFAULT_SUBTITLE_STATE = structuredClone(state.subtitleState);
const DEFAULT_AUDIO_STATE = structuredClone(state.audioState);
const DEFAULT_RENDER_STATE = structuredClone(state.renderState);

const STUDIO_API = "/api";
let backendOnline = false;
let renderPollTimer = null;
let projectWriteQueue = Promise.resolve();
let projectWriteError = null;

async function apiRequest(path, options = {}) {
  const headers = { ...(options.body instanceof Blob ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) };
  const response = await fetch(`${STUDIO_API}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Local request failed (${response.status})`);
  return payload;
}

function initials(value) {
  return String(value || "Untitled").split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join("").toUpperCase() || "NP";
}

function projectSummaryForUi(item) {
  return {
    id: item.id, name: item.name, initials: initials(item.name), stage: item.status || "DRAFT",
    sceneCount: item.scene_count || 0, resolution: "1080 × 1920", aspect: "9:16", fps: 30,
    imported: Boolean(item.imported), updated: item.updated_at ? "Updated locally" : "Local project",
  };
}

function applyBackendProject(detail) {
  const manifest = detail.project || {};
  const remotion = detail.remotion || {};
  const voice = manifest.voice || {};
  const summary = projectSummaryForUi({ id: manifest.id, name: manifest.name, status: manifest.status || detail.workflow?.status, scene_count: detail.scenes?.length, imported: manifest.source?.imported });
  const existing = state.workspaceState.projects.find(item => item.id === summary.id);
  if (existing) Object.assign(existing, summary); else state.workspaceState.projects.unshift(summary);
  state.workspaceState.activeProjectId = summary.id;
  state.projectState = { id: summary.id, name: summary.name, initials: summary.initials, stage: summary.stage, resolution: `${remotion.width || 1080} × ${remotion.height || 1920}`, aspect: "9:16", fps: remotion.fps || 30, imported: summary.imported };
  state.importReport = detail.last_import_report || null;
  state.sceneState = {
    items: (detail.scenes || []).map(item => {
      const video = item.video || {};
      const current = (video.versions || []).find(version => version.version === video.active_version) || {};
      const audio = current.source_audio || video.source_audio || {};
      const timing = current.timing || {};
      return {
        id: item.id, number: item.number, title: `Scene ${String(item.number).padStart(2, "0")}`,
        narration: item.narration || "", source: current.source_provider ? "Google Flow" : "Missing", sourceFilename: current.source_filename || "",
        sourceVersion: current.version || 0, duration: +(current.probe?.duration || Math.max(1, item.duration_in_frames / (remotion.fps || 30))).toFixed(1),
        status: current.status || video.status || "missing", sourceAudio: { mode: audio.mode || "mute", volume: Math.round((audio.volume || 0) * 100), duck: Boolean(audio.duck_under_narration), fadeIn: audio.fade_in || 0, fadeOut: audio.fade_out || 0 },
        edit: { trimStart: current.trim?.start || 0, trimEnd: current.trim?.end || null, speed: timing.playback_rate || 1, crop: current.crop?.mode || "cover", position: "center", holdLastFrame: Boolean(timing.hold_last_frame), transition: item.transition || "none" },
        decision: manifest.render?.scene_decisions?.[item.id] || "keep", voiceOverride: null,
      };
    }),
    selectedId: detail.scenes?.[0]?.id || null, sceneCount: detail.scenes?.length || 0, timelineZoom: 1,
  };
  const projectAudio = manifest.audio || {};
  const firstSourceAudio = state.sceneState.items[0]?.sourceAudio || {};
  state.audioState = {
    ...structuredClone(DEFAULT_AUDIO_STATE),
    narration: Math.round(Number(projectAudio.narration_volume ?? 1) * 100),
    source: Math.round(Number(projectAudio.source_volume ?? (firstSourceAudio.volume ?? 30) / 100) * 100),
    sourceMode: projectAudio.source_mode || firstSourceAudio.mode || "mute",
    sourceDuck: projectAudio.source_duck ?? firstSourceAudio.duck ?? true,
    bgm: Math.round(Number(projectAudio.bgm_volume ?? 0.12) * 100),
  };
  state.scriptState = { bulkText: detail.script_text || "", mapped: state.sceneState.items.filter(scene => scene.narration).length, missing: state.sceneState.items.filter(scene => !scene.narration).length, approved: Boolean(manifest.script?.approved) };
  state.voiceState = { ...structuredClone(DEFAULT_VOICE_STATE), provider: voice.provider || "omnivoice", language: voice.language || "vi", locale: voice.locale || "default", mode: voice.mode || "voice_design", gender: voice.design?.gender || "male", age: voice.design?.age || "young adult", pitch: voice.design?.pitch || "moderate", speed: voice.speed || 1.1, previewStatus: voice.preview_file ? "GENERATED" : "NOT GENERATED", previewUrl: voice.preview_file ? `${STUDIO_API}/projects/${encodeURIComponent(summary.id)}/voice/preview?t=${encodeURIComponent(manifest.updated_at || "")}` : null };
  state.workflowState = { scriptApproved: Boolean(manifest.script?.approved), voiceApproved: Boolean(voice.approved), previewReady: Boolean(manifest.render?.preview_ready), previewApproved: Boolean(manifest.render?.preview_approved), finalReady: Boolean(manifest.render?.final_ready) };
  state.reviewState = { finalized: Boolean(manifest.render?.final_ready), dirty: Boolean(manifest.render?.review_dirty), showCutsOnly: false };
  state.automationState = { status: summary.imported ? "SOURCE READY" : "IDLE", progress: summary.imported ? 100 : 0, step: summary.imported ? 1 : 0 };
  state.renderState = { ...structuredClone(DEFAULT_RENDER_STATE), requestScene: state.sceneState.selectedId || "",
    voiceSteps: Number(manifest.render?.voice_steps || 4),
    status: manifest.render?.final_ready ? "FINAL READY" : manifest.render?.preview_ready ? "PREVIEW READY" : "READY",
    videoUrl: manifest.render?.final_ready ? `${STUDIO_API}/projects/${encodeURIComponent(summary.id)}/render/final?t=${Date.now()}` : manifest.render?.preview_ready ? `${STUDIO_API}/projects/${encodeURIComponent(summary.id)}/render/preview?t=${Date.now()}` : null,
    progress: manifest.render?.final_ready || manifest.render?.preview_ready ? 100 : 0 };
}

async function loadBackendProject(projectId) {
  const detail = await apiRequest(`/projects/${encodeURIComponent(projectId)}`);
  applyBackendProject(detail);
  const renderStatus = await apiRequest(`/projects/${encodeURIComponent(projectId)}/render/status`).catch(() => null);
  if (renderStatus) applyRenderStatus(renderStatus);
  if (renderStatus?.status === "running") { watchRenderStatus(); renderScreen(); }
  state.uiState.projectMenuOpen = false;
  renderScreen();
  return detail;
}

async function hydrateLocalWorkspace() {
  try {
    const payload = await apiRequest("/projects");
    const health = await apiRequest("/health").catch(() => null);
    backendOnline = true;
    state.voiceRuntime = health?.voice?.providers?.[0]?.health || state.voiceRuntime;
    state.workspaceState.projects = payload.projects.map(projectSummaryForUi);
    if (state.workspaceState.projects.length) await loadBackendProject(state.workspaceState.projects[0].id);
    else {
      state.workspaceState.activeProjectId = null;
      state.projectState = { id: "", name: "No project", initials: "NP", stage: "DRAFT", resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: false };
      state.sceneState = { items: [], selectedId: null, sceneCount: 0, timelineZoom: 1 };
      renderScreen();
    }
  } catch (_) {
    backendOnline = false;
  }
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" }[char]));
const currentScene = () => state.sceneState.items.find(scene => scene.id === state.sceneState.selectedId) || state.sceneState.items[0];
const language = () => LANGUAGE_CATALOG.find(item => item.id === state.voiceState.language) || LANGUAGE_CATALOG[0];
const formatTime = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, "0")}`;
const keptScenes = () => state.sceneState.items.filter(scene => scene.decision !== "cut");
const cutScenes = () => state.sceneState.items.filter(scene => scene.decision === "cut");
const projectDuration = () => keptScenes().reduce((total, item) => total + item.duration, 0);
const activeProject = () => state.workspaceState.projects.find(project => project.id === state.workspaceState.activeProjectId) || state.workspaceState.projects[0] || { id: "", name: "No project", initials: "NP", stage: "DRAFT", sceneCount: 0, imported: false, updated: "Create a local project" };

function projectStageLabel(stage) {
  return ({ UPLOADED: "Uploaded", MAPPED: "Mapped", SCRIPT: "Script", SCRIPT_MAPPING: "Script mapping", VOICE_SETUP: "Voice setup", READY_TO_RENDER: "Ready to render", PROCESSING: "Preparing source", POST_RENDER_REVIEW: "Post-render review", FINAL_REVIEW: "Final review", RENDERING: "Rendering", REVIEW: "Review", APPROVED: "Approved", NEEDS_CHANGES: "Needs changes", DONE: "Done", DRAFT: "Draft" })[stage] || stage;
}

function syncActiveProject() {
  const project = activeProject();
  if (!project) return;
  Object.assign(project, {
    name: state.projectState.name,
    initials: state.projectState.initials,
    stage: state.projectState.stage,
    resolution: state.projectState.resolution,
    aspect: state.projectState.aspect,
    fps: state.projectState.fps,
    imported: state.projectState.imported,
    sceneCount: state.sceneState.items.length,
    updated: "Updated just now",
    snapshot: { sceneState: structuredClone(state.sceneState), scriptState: structuredClone(state.scriptState), voiceState: structuredClone(state.voiceState), subtitleState: structuredClone(state.subtitleState), audioState: structuredClone(state.audioState), renderState: structuredClone(state.renderState), workflowState: structuredClone(state.workflowState), reviewState: structuredClone(state.reviewState), automationState: structuredClone(state.automationState) },
  });
}

function activateProject(id) {
  if (backendOnline) {
    loadBackendProject(id).catch(error => toast(error.message, "warning"));
    return;
  }
  if (id === state.workspaceState.activeProjectId) { state.uiState.projectMenuOpen = false; renderProjectContext(); return; }
  syncActiveProject();
  const project = state.workspaceState.projects.find(item => item.id === id);
  if (!project) return;
  state.workspaceState.activeProjectId = project.id;
  state.projectState = { id: project.id, name: project.name, initials: project.initials, stage: project.stage, resolution: project.resolution, aspect: project.aspect, fps: project.fps, imported: project.imported };
  state.sceneState = project.snapshot ? structuredClone(project.snapshot.sceneState) : { items: makeScenes(project.sceneCount), selectedId: project.sceneCount ? "scene_01" : null, sceneCount: project.sceneCount, timelineZoom: 1 };
  state.scriptState = project.snapshot ? structuredClone(project.snapshot.scriptState) : { bulkText: "", mapped: 0, missing: project.sceneCount, approved: project.stage === "VOICE_SETUP" || project.stage === "READY_TO_RENDER" || project.stage === "POST_RENDER_REVIEW" };
  state.voiceState = project.snapshot?.voiceState ? structuredClone(project.snapshot.voiceState) : structuredClone(DEFAULT_VOICE_STATE);
  state.subtitleState = project.snapshot?.subtitleState ? structuredClone(project.snapshot.subtitleState) : structuredClone(DEFAULT_SUBTITLE_STATE);
  state.audioState = project.snapshot?.audioState ? structuredClone(project.snapshot.audioState) : structuredClone(DEFAULT_AUDIO_STATE);
  state.renderState = project.snapshot?.renderState ? structuredClone(project.snapshot.renderState) : structuredClone(DEFAULT_RENDER_STATE);
  state.workflowState = project.snapshot?.workflowState ? structuredClone(project.snapshot.workflowState) : { scriptApproved: ["VOICE_SETUP", "READY_TO_RENDER", "POST_RENDER_REVIEW", "APPROVED"].includes(project.stage), voiceApproved: ["READY_TO_RENDER", "POST_RENDER_REVIEW", "APPROVED"].includes(project.stage), previewReady: ["POST_RENDER_REVIEW", "APPROVED"].includes(project.stage) };
  state.reviewState = project.snapshot?.reviewState ? structuredClone(project.snapshot.reviewState) : { finalized: false, dirty: false };
  state.automationState = project.snapshot?.automationState ? structuredClone(project.snapshot.automationState) : { status: project.imported ? "SOURCE READY" : "IDLE", progress: project.imported ? 100 : 0, step: project.imported ? 1 : 0 };
  state.renderState.requestScene = state.sceneState.items[0]?.id || "";
  state.uiState.projectMenuOpen = false;
  state.uiState.screen = "dashboard";
  toast(`${project.name} is now the active project.`);
  savePulse();
  renderScreen();
}

function createProject() {
  if (backendOnline) {
    const name = window.prompt("Project name", "Untitled Project");
    if (!name?.trim()) return;
    apiRequest("/projects", { method: "POST", body: JSON.stringify({ name: name.trim() }) })
      .then(detail => { applyBackendProject(detail); state.uiState.screen = "import"; toast("Local project created."); renderScreen(); })
      .catch(error => toast(error.message, "warning"));
    return;
  }
  toast("Start the local studio server before creating a project.", "warning");
}

function renderProjectContext() {
  const project = activeProject();
  if (!project) return;
  $("#project-avatar").textContent = project.initials;
  $("#project-name").textContent = project.name;
  $("#project-meta").textContent = `${project.sceneCount} scenes · ${projectStageLabel(project.stage)}`;
  $("#active-project-crumb").textContent = project.name;
  const menu = $("#project-menu");
  menu.hidden = !state.uiState.projectMenuOpen;
  menu.innerHTML = `<div class="project-menu-head"><span>Workspace projects</span><span>${state.workspaceState.projects.length}</span></div><button class="button-secondary project-menu-new" data-action="create-project">＋ New project</button><div class="project-menu-list">${state.workspaceState.projects.map(item => `<button class="project-menu-item ${item.id === project.id ? "active" : ""}" role="menuitem" data-action="select-project" data-project-id="${item.id}"><span class="project-avatar">${item.initials}</span><span><b>${escapeHtml(item.name)}</b><small>${item.sceneCount} scenes · ${escapeHtml(item.updated)}</small></span><span class="project-menu-status">${projectStageLabel(item.stage)}</span></button>`).join("")}</div>`;
  $(".project-switcher").setAttribute("aria-expanded", String(state.uiState.projectMenuOpen));
}

function savePulse(message = "All changes saved") {
  syncActiveProject();
  const node = $("#save-state");
  node.textContent = "● Saving…";
  setTimeout(() => { node.textContent = `● ${message}`; }, 280);
}

function toast(message, kind = "success") {
  const item = document.createElement("div");
  item.className = `toast ${kind}`;
  item.textContent = message;
  $("#toast-region").append(item);
  setTimeout(() => item.remove(), 3200);
}

function renderNavigation() {
  $("#sidebar-nav").innerHTML = NAVIGATION.map(([id, icon, label]) => `
    <button class="nav-button ${state.uiState.screen === id ? "active" : ""}" type="button" data-nav="${id}">
      <span class="nav-icon">${icon}</span>${label}
    </button>`).join("");
}

function screenHeader(title, description, actions = "") {
  return `<div class="screen-header"><div><h1>${title}</h1><p>${description}</p></div><div class="screen-actions">${actions}</div></div>`;
}

function metric(label, value, meta, tone = "") {
  return `<article class="card metric-card ${tone}"><span class="metric-label">${label}</span><div class="metric-value">${value}</div><div class="metric-meta">${meta}</div></article>`;
}

function sceneCard(scene) {
  const hasScript = Boolean(scene.narration);
  return `<article class="scene-card ${scene.id === state.sceneState.selectedId ? "selected" : ""} ${scene.decision === "cut" ? "cut" : ""}" data-action="select-scene" data-scene-id="${scene.id}">
    <div class="scene-thumb"><span class="scene-index">${String(scene.number).padStart(2, "0")}</span><span class="scene-decision ${scene.decision}">${scene.decision === "cut" ? "CUT" : "KEEP"}</span><span class="play-dot">▶</span></div>
    <div class="scene-card-body"><div class="scene-card-title"><b>${escapeHtml(scene.title)}</b><span class="status-tag ${scene.status}">${scene.status}</span></div>
      <p class="scene-card-copy">${hasScript ? escapeHtml(scene.narration) : "Narration needed — add script for this scene."}</p>
      <div class="scene-meta"><span>${scene.source}${scene.sourceVersion ? ` · v${scene.sourceVersion}` : ""}</span><span>${scene.duration}s</span></div>
    </div></article>`;
}

function renderDashboard() {
  const project = activeProject();
  const kept = keptScenes().length;
  const cut = cutScenes().length;
  const preparing = state.automationState.status === "RUNNING";
  const scriptReady = state.workflowState.scriptApproved;
  const voiceReady = state.workflowState.voiceApproved;
  const previewReady = state.workflowState.previewReady;
  const projectRows = state.workspaceState.projects.map(item => `<button class="workspace-project-row ${item.id === project.id ? "active" : ""}" data-action="select-project" data-project-id="${item.id}"><span class="project-avatar">${item.initials}</span><span><b>${escapeHtml(item.name)}</b><small>${item.sceneCount} scenes · ${escapeHtml(item.updated)}</small></span><span class="project-menu-status">${projectStageLabel(item.stage)}</span></button>`).join("");
  const nextUp = !state.sceneState.items.length ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Next up</p><h2 class="card-title">Add a source ZIP</h2></div><span class="status-tag pending">Not imported</span></div><p class="caption">Drop a Flow ZIP or folder. The app scans and orders scenes, then waits for your script.</p><button class="button-secondary" data-nav="import">Import source</button></section>` : preparing ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Source preparation</p><h2 class="card-title">Preparing ${state.automationState.progress}%</h2></div><span class="status-tag review">Running</span></div><p class="caption">Only source detection and scene ordering are running. Narration remains under your control.</p></section>` : !scriptReady ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Your approval</p><h2 class="card-title">Review script mapping</h2></div><span class="status-tag pending">${state.scriptState.mapped} / ${state.sceneState.items.length} mapped</span></div><p class="caption">Paste the scene-by-scene script, inspect the proposed mapping, then approve it before any preview render can start.</p><button class="button-secondary" data-nav="script">Open Script Mapping</button></section>` : !voiceReady ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Manual voice</p><h2 class="card-title">Tune narration</h2></div><span class="status-tag pending">Approval needed</span></div><p class="caption">Adjust OmniVoice and preview the narration yourself before enabling video rendering.</p><button class="button-secondary" data-nav="voice">Open Voice</button></section>` : !previewReady ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Preview render</p><h2 class="card-title">Create review video</h2></div><span class="status-tag pending">Ready</span></div><p class="caption">The source, approved script, and manual voice settings are ready for a low-cost preview render.</p><button class="button-secondary" data-nav="render">Render preview</button></section>` : `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Final decision</p><h2 class="card-title">Watch and approve export</h2></div><span class="status-tag review">${kept} keep · ${cut} cut</span></div><p class="caption">After preview, keep or cut scenes and make basic edits. Export only when you are satisfied.</p><button class="button-secondary" data-nav="scenes">Open Final Review</button></section>`;
  return `<section class="screen">${screenHeader("Project workspace", `Active project: ${project.name}. Source intake is automatic; script, voice, and final output stay under your approval.`, `<button class="button-secondary" data-action="create-project">New project</button><button class="button" data-nav="${!scriptReady ? "script" : !voiceReady ? "voice" : !previewReady ? "render" : "scenes"}">Open next step</button>`)}
    <div class="grid four">${metric("ACTIVE PROJECT", escapeHtml(project.name), `${projectStageLabel(project.stage)} · ${project.updated}`, "blue")}${metric("SOURCE SCENES", state.sceneState.items.length, state.projectState.imported ? "ZIP mapped to project" : "Waiting for ZIP")}${metric("SCRIPT MAP", `${state.scriptState.mapped} / ${state.sceneState.items.length}`, scriptReady ? "Approved" : "Needs your approval")}${metric("FINAL CUT", `${kept} kept`, `${cut} cut · ${formatTime(projectDuration())}`, "amber")}</div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Production flow</p><h2 class="card-title">Automatic intake, manual approvals before and after render</h2></div><button class="button-quiet" data-nav="${!scriptReady ? "script" : !voiceReady ? "voice" : !previewReady ? "render" : "scenes"}">Open next step →</button></div>
      <div class="workflow workflow-six">${[["Source ZIP", state.projectState.imported ? "done" : "current", state.projectState.imported ? `${state.sceneState.items.length} scenes detected` : "Source needed"],["Script map", scriptReady ? "done" : state.projectState.stage === "SCRIPT_MAPPING" ? "current" : "", scriptReady ? "Approved" : `${state.scriptState.mapped} / ${state.sceneState.items.length}`],["Voice", voiceReady ? "done" : state.projectState.stage === "VOICE_SETUP" ? "current" : "", voiceReady ? "Approved" : "Manual tuning"],["Preview", previewReady ? "done" : state.projectState.stage === "RENDERING" ? "current" : "", previewReady ? "Ready" : "Waiting"],["Final review", state.projectState.stage === "POST_RENDER_REVIEW" ? "current" : state.projectState.stage === "APPROVED" ? "done" : "", previewReady ? `${kept} keep · ${cut} cut` : "After preview"],["Export", state.projectState.stage === "APPROVED" ? "done" : "", state.projectState.stage === "APPROVED" ? "Approved" : "Your decision"]].map(([name, cls, small], index) => `<div class="workflow-step ${cls}"><span class="step-number">0${index + 1}</span><strong>${name}</strong><small>${small}</small></div>`).join("")}</div></section>
    <div class="grid two" style="margin-top:16px">${nextUp}<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Workspace projects</p><h2 class="card-title">Switch without mixing assets</h2></div><button class="button-quiet" data-action="create-project">＋ New</button></div><p class="caption">Source, scene count, scripts, review state, and output settings belong to the selected project.</p><div class="workspace-project-list">${projectRows}</div></section></div>
  </section>`;
}

function renderImport() {
  const total = state.sceneState.items.length;
  const auto = state.automationState;
  const report = state.importReport;
  const rows = (report?.scene_map || []).map(row => {
    const scene = state.sceneState.items.find(item => item.number === row.scene_number);
    const status = scene?.status || row.status;
    const sourceUrl = `${STUDIO_API}/projects/${encodeURIComponent(state.projectState.id)}/scenes/${encodeURIComponent(scene?.id || "")}/source`;
    return `<div class="validation-row"><span class="${status === "invalid" ? "warning" : "check"}">${status === "invalid" ? "▲" : "✓"}</span><div><b>Scene ${String(row.scene_number).padStart(2, "0")}</b><span class="muted">${escapeHtml(row.source_filename || "Unknown file")} · ${escapeHtml(status)}</span>${row.error ? `<small class="warning">${escapeHtml(row.error)}</small>` : ""}${backendOnline && scene?.sourceVersion && status !== "invalid" ? `<video class="source-review-video" controls preload="metadata" src="${sourceUrl}"></video><small class="muted">Original source clip · no render</small>` : ""}${backendOnline && scene?.sourceVersion && status === "pending_review" ? `<div style="margin-top:6px"><button class="button-secondary" data-action="review-import-source" data-scene-id="${escapeHtml(scene.id)}" data-status="approved">Approve this source</button> <button class="button-quiet" data-action="review-import-source" data-scene-id="${escapeHtml(scene.id)}" data-status="rejected">Flag</button></div>` : ""}</div></div>`;
  }).join("");
  return `<section class="screen">${screenHeader("Import Google Flow source", `Import a ZIP or folder into ${escapeHtml(activeProject().name)}. Check the video-to-scene order here, then map your narration in the next step.`, `<button class="button-secondary" data-action="run-auto-prep" ${auto.status === "RUNNING" ? "disabled" : ""}>${auto.status === "RUNNING" ? "Importing…" : "Choose source ZIP"}</button>`)}
    <div class="import-dropzone" id="dropzone"><div><div class="drop-icon">⇩</div><h2>DROP GOOGLE FLOW ZIP HERE</h2><p class="caption">ZIP stays on this computer. Numbered filenames map directly; generic Flow filenames follow ZIP order and require your review.</p><div class="drop-actions"><button class="button" data-action="choose-zip" ${auto.status === "RUNNING" ? "disabled" : ""}>Choose ZIP</button><button class="button-secondary" data-action="choose-folder" ${auto.status === "RUNNING" ? "disabled" : ""}>Choose Folder</button></div></div></div>
    <section class="card card-pad auto-prep-card" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Local import</p><h2 class="card-title">${escapeHtml(auto.status)}</h2></div><span class="caption">${auto.progress}%</span></div><p class="caption">${auto.status === "RUNNING" ? "Uploading locally, then validating video metadata. Larger ZIPs may take a moment after upload reaches 100%." : "No video render starts during import."}</p><div class="progress-track"><i style="width:${auto.progress}%"></i></div></section>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">${report ? "Last import" : "Scene mapping"}</p><h2 class="card-title">${report?.mapping_requires_review ? "Review inferred ZIP order" : "Source files by scene"}</h2></div><span class="status-tag ${report?.valid_files ? "review" : "pending"}">${report?.valid_files ? "Ready for your review" : "Waiting for source"}</span></div><div class="upload-report"><div class="report-cell"><b>${report?.files_found ?? 0}</b><span>Videos found</span></div><div class="report-cell"><b>${report?.valid_files ?? 0}</b><span>Valid</span></div><div class="report-cell"><b>${report?.scene_map?.length ?? 0}</b><span>Mapped</span></div><div class="report-cell"><b>${report?.missing_scenes?.length ?? 0}</b><span>Missing</span></div><div class="report-cell"><b>${report?.invalid_files?.length ?? 0}</b><span>Invalid</span></div></div>${report?.warnings?.length ? `<p class="caption" style="margin-top:12px">${report.warnings.map(escapeHtml).join(" · ")}</p>` : ""}<div style="margin-top:12px">${rows || `<p class="caption">No videos mapped yet. Choose a ZIP to begin.</p>`}</div>${report?.valid_files ? `<button class="button" data-nav="script" style="margin-top:14px">Review mapping & add narration →</button>` : ""}</section>
  </section>`;
}

function renderScript() {
  if (!state.sceneState.items.length) return `<section class="screen">${screenHeader("Script Mapping", "Import a source ZIP first. Scene slots are created from the detected source files.", `<button class="button" data-nav="import">Import source</button>`)}<div class="empty-state"><div><h2>No scene slots yet</h2><p>Once the ZIP has been scanned, paste a script with SCENE blocks and review the proposed mapping here.</p></div></div></section>`;
  const allMapped = state.scriptState.mapped === state.sceneState.items.length;
  const selected = currentScene();
  const selectedNumber = String(selected.number).padStart(2, "0");
  const previewRows = state.sceneState.items.map(scene => `<div class="validation-row script-map-row ${scene.id === selected.id ? "selected" : ""}" data-action="select-script-scene" data-scene-id="${escapeHtml(scene.id)}"><span class="${scene.narration ? "check" : "warning"}">${scene.narration ? "✓" : "▲"}</span><div><b>Scene ${String(scene.number).padStart(2, "0")}</b><span class="muted">${escapeHtml(scene.sourceFilename || "Source missing")} · Script ${scene.narration ? "mapped" : "missing"}</span>${scene.narration ? `<small class="muted">${escapeHtml(scene.narration.length > 96 ? `${scene.narration.slice(0, 96)}…` : scene.narration)}</small>` : ""}</div><span class="script-row-action">Edit</span></div>`).join("");
  return `<section class="screen">${screenHeader("Script Mapping", "Select one scene, enter only that scene's narration, then save it. Each scene keeps an independent script.", `<button class="button" data-action="approve-script-mapping" ${allMapped && !state.scriptState.approved ? "" : "disabled"}>${state.scriptState.approved ? "Mapping approved" : "Approve mapping"}</button>`)}
    <div class="script-layout"><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Selected scene only</p><h2 class="card-title">Scene ${selectedNumber} narration</h2></div><span class="status-tag ${selected.narration ? "ready" : "pending"}">${selected.narration ? "Mapped" : "Missing"}</span></div><p class="caption scene-edit-notice">Changes here apply only to Scene ${selectedNumber}. Select another scene from the list or timeline to edit it separately.</p><label class="field-label" for="scene-script">Narration for Scene ${selectedNumber}</label><textarea id="scene-script" class="textarea-input scene-script-input" placeholder="Enter narration for Scene ${selectedNumber}…">${escapeHtml(selected.narration)}</textarea><div class="scene-script-actions"><span class="caption">Saving resets script approval so you can review the updated mapping.</span><button class="button" data-action="save-scene-script">Save Scene ${selectedNumber}</button></div><details class="bulk-script-panel"><summary>Optional: import a full multi-scene script</summary><p class="caption">Use explicit SCENE blocks. This is separate from the selected-scene editor above.</p><label class="field-label">Bulk format <small>SCENE 1 → Narration: → “text”</small></label><textarea id="bulk-script" class="textarea-input compact-textarea">${escapeHtml(state.scriptState.bulkText)}</textarea><div class="scene-script-actions"><span class="caption">Only scene numbers present in the text are updated.</span><button class="button-secondary" data-action="parse-script">Import scene blocks</button></div></details></section>
      <aside class="card card-pad"><div class="card-head"><div><p class="eyebrow">Mapping review</p><h2 class="card-title">Choose a scene to edit</h2></div><span class="status-tag ${state.scriptState.approved ? "ready" : allMapped ? "review" : "pending"}">${state.scriptState.approved ? "Approved" : allMapped ? "Ready to approve" : `${state.scriptState.missing} missing`}</span></div>${previewRows}<button class="button-secondary" data-action="approve-script-mapping" ${allMapped && !state.scriptState.approved ? "" : "disabled"} style="margin-top:12px;width:100%">${state.scriptState.approved ? "Mapping approved" : "Approve & continue to Voice"}</button></aside></div>
  </section>`;
}

function renderScenes() {
  const kept = keptScenes().length;
  const cut = cutScenes().length;
  if (!state.sceneState.items.length) return `<section class="screen">${screenHeader("Final Review", "Import a source and approve its script and voice first. Final review becomes available after a preview render.", `<button class="button" data-nav="import">Import source</button>`)}<div class="empty-state"><div><h2>No review timeline yet</h2><p>Once a preview video exists, each scene appears here with Keep/Cut and basic edit controls.</p></div></div></section>`;
  if (!state.workflowState.previewReady) return `<section class="screen">${screenHeader("Final Review", "Final review is deliberately after preview rendering. First approve the script, tune the voice, and create a review video.", `<button class="button" data-nav="${!state.workflowState.scriptApproved ? "script" : !state.workflowState.voiceApproved ? "voice" : "render"}">Open next step</button>`)}<div class="empty-state"><div><h2>Preview video not ready</h2><p>You will choose Keep/Cut and make basic video edits only after you can watch the generated preview.</p></div></div></section>`;
  return `<section class="screen">${screenHeader("Final Review", "Watch the generated preview, then choose Keep or Cut and adjust trim, speed, crop, transition, or source audio. Re-render a preview after edits; approve it before final rendering.", `<button class="button-secondary" data-action="keep-all-scenes">Keep all</button><button class="button-secondary" data-action="rerender-preview">${state.reviewState.dirty ? "Render updated preview" : "Render another preview"}</button><button class="button" data-action="approve-export" ${state.reviewState.dirty || state.workflowState.previewApproved ? "disabled" : ""}>${state.workflowState.previewApproved ? "Preview approved" : "Approve preview"}</button>`)}
    <section class="card card-pad" style="margin-bottom:16px"><p class="eyebrow">Rendered preview</p><video controls preload="metadata" style="display:block;max-height:480px;max-width:100%;margin:12px auto" src="${state.renderState.videoUrl || `${STUDIO_API}/projects/${encodeURIComponent(state.projectState.id)}/render/preview?t=${Date.now()}`}"></video></section>
    <section class="card card-pad review-summary"><div><p class="eyebrow">Post-render decision</p><h2 class="card-title">${kept} kept · ${cut} cut · ${formatTime(projectDuration())} final duration</h2><p class="caption">${state.reviewState.dirty ? "Edits are pending a new preview render." : "Cut scenes stay available for reversal and are excluded from any new render."}</p></div><button class="button-quiet" data-action="toggle-cut-filter">${state.reviewState.showCutsOnly ? "Show all scenes" : "Show cuts only"}</button></section>
    <div class="scene-grid">${state.sceneState.items.filter(scene => !state.reviewState.showCutsOnly || scene.decision === "cut").map(sceneCard).join("")}</div>
  </section>`;
}

function optionList(items, selected) { return items.map(item => `<option value="${item.id || item}" ${String(item.id || item) === String(selected) ? "selected" : ""}>${item.label || item}</option>`).join(""); }
function selectedClass(actual, expected) { return actual === expected ? "active" : ""; }
function capabilityHint(supported, label = "Future provider capability") { return supported ? "" : `<span class="support-hint">${label}</span>`; }

function renderVoice() {
  const voice = state.voiceState;
  const runtime = state.voiceRuntime || {};
  const runtimeLabel = runtime.ready_for_generation
    ? runtime.status === "ready_low_memory" ? "● LOW-MEM READY" : "● READY"
    : runtime.available ? "● MEMORY FULL" : "● NOT READY";
  const lang = language();
  const localeOptions = lang.locales.map(locale => ({ id: locale, label: locale === "default" ? "Default" : locale }));
  const profileOptions = voice.profiles.map(profile => ({ id: profile.id, label: profile.name }));
  if (!profileOptions.length) profileOptions.push({ id: "native-design", label: "Native voice design" });
  const isLanguageReady = VOICE_CAPABILITIES.supportedLanguages.includes(voice.language);
  const canApproveVoice = state.workflowState.scriptApproved;
  const waves = Array.from({ length: 44 }, (_, index) => `<i class="wave" style="height:${18 + ((index * 23) % 70)}px;animation-delay:-${(index % 9) / 10}s"></i>`).join("");
  const history = voice.history.map(item => `<div class="history-row"><div class="history-title"><b>${item.name}</b><span>${item.language} · ${item.gender} · ${item.speed.toFixed(2)}x · ${item.duration} · ${item.created}</span></div><button data-action="play-history" data-history="${item.id}">Play</button><button data-action="select-history" data-history="${item.id}">Select</button><button data-action="delete-history" data-history="${item.id}">Delete</button></div>`).join("");
  const comparisons = voice.comparisons.map(item => `<div class="compare-slot"><span class="compare-key">${item.id}</span><div><b>${item.gender} narrator</b><span>${item.language} · ${item.speed.toFixed(2)}x</span></div><div><button data-action="play-compare" data-id="${item.id}">Play ${item.id}</button> <button data-action="select-compare" data-id="${item.id}">${item.selected ? "Selected" : `Select ${item.id}`}</button></div></div>`).join("");
  return `<section class="screen">${screenHeader("Voice", "Tune voice settings manually and listen to a preview. OmniVoice is the only active engine; this stage must be approved before video rendering.", `<button class="button-secondary" data-action="save-voice-profile">Save Profile</button><button class="button-secondary" data-action="generate-preview" ${voice.previewStatus === "GENERATING" ? "disabled" : ""}>${voice.previewStatus === "GENERATING" ? "Generating…" : "Generate Preview"}</button><button class="button" data-action="approve-voice" ${canApproveVoice && voice.previewUrl ? "" : "disabled"}>${state.workflowState.voiceApproved ? "Voice approved" : "Approve voice & continue"}</button>`)}
    <div class="voice-layout"><section class="voice-config"><article class="card card-pad"><p class="eyebrow">Voice engine</p><div class="voice-engine"><div class="voice-engine-icon">◖</div><div><b>OmniVoice</b><span>Local model · CPU inference</span></div><span class="availability">${runtimeLabel}</span></div>${runtime.detail ? `<p class="caption" style="margin-top:10px">${escapeHtml(runtime.detail)}</p>` : ""}
      <div class="form-stack" style="margin-top:15px"><div><label class="control-label">Language <em>${isLanguageReady ? "Supported now" : "Future provider mock"}</em></label><div class="select-with-hint"><select class="select-input" data-setting="voice-language">${optionList(LANGUAGE_CATALOG, voice.language)}</select>${capabilityHint(isLanguageReady, "prototype")}</div></div>
        <div><label class="control-label">Accent / Locale <em>${voice.language === "vi" ? "Default active" : "Mock options"}</em></label><select class="select-input" data-setting="voice-locale">${optionList(localeOptions, voice.locale)}</select></div>
        <div><label class="control-label">Voice Profile</label><select class="select-input" data-setting="voice-profile">${optionList(profileOptions, voice.profileId)}</select><div style="display:flex;gap:4px;margin-top:7px"><button class="button-quiet" data-action="duplicate-profile">Duplicate</button><button class="button-quiet" data-action="rename-profile">Rename</button><button class="button-quiet" data-action="delete-profile">Delete</button></div></div>
      </div></article>
      <article class="card card-pad"><p class="eyebrow">Voice direction</p><div class="form-stack"><div><label class="control-label">Mode <em>Clone is engine-gated</em></label><div class="segmented"><button class="${selectedClass(voice.mode, "auto")}" data-action="voice-mode" data-mode="auto">Auto</button><button class="${selectedClass(voice.mode, "voice_design")}" data-action="voice-mode" data-mode="voice_design">Voice Design</button><button class="unsupported" disabled title="OmniVoice does not support clone yet">Voice Clone</button></div></div>
        <div class="${voice.mode === "voice_design" ? "" : "disabled-layer"}"><label class="control-label">Gender</label><div class="option-pills"><button class="chip-button ${selectedClass(voice.gender, "male")}" data-action="voice-gender" data-value="male">Male</button><button class="chip-button ${selectedClass(voice.gender, "female")}" data-action="voice-gender" data-value="female">Female</button></div></div>
        <div class="${VOICE_CAPABILITIES.age ? "" : "disabled-layer"}"><label class="control-label">Age <em>${VOICE_CAPABILITIES.age ? "Native voice design" : "Not supported by OmniVoice"}</em></label><div class="option-pills">${["young adult", "middle-aged", "older adult"].map(value => `<button class="chip-button ${selectedClass(voice.age, value)} ${VOICE_CAPABILITIES.age ? "" : "unsupported"}" ${VOICE_CAPABILITIES.age ? `data-action="voice-age" data-value="${value}"` : "disabled"}>${value}</button>`).join("")}</div></div>
        <div><label class="control-label">Pitch</label><div class="option-pills">${["low", "moderate", "high"].map(value => `<button class="chip-button ${selectedClass(voice.pitch, value)}" data-action="voice-pitch" data-value="${value}">${value}</button>`).join("")}</div></div>
        <div class="${VOICE_CAPABILITIES.styles ? "" : "disabled-layer"}"><label class="control-label">Tone / Style <em>${VOICE_CAPABILITIES.styles ? "Supported" : "Future provider capability"}</em></label><div class="option-pills">${["neutral", "warm", "calm", "energetic", "documentary", "friendly", "serious", "educational"].map(value => `<button class="chip-button ${selectedClass(voice.style, value)} ${VOICE_CAPABILITIES.styles ? "" : "unsupported"}" ${VOICE_CAPABILITIES.styles ? `data-action="voice-style" data-value="${value}"` : "disabled"}>${value}</button>`).join("")}</div></div>
        <div class="speed-control"><div class="speed-title"><div><p class="eyebrow">Voice speed</p><b>Rate without pitch shift</b></div><div class="stepper"><button data-action="speed-step" data-direction="-1">−</button><span class="speed-readout">${voice.speed.toFixed(2)}x</span><button data-action="speed-step" data-direction="1">+</button></div></div><input type="range" min="0.85" max="1.20" step="0.01" value="${voice.speed}" data-setting="voice-speed" /><div class="preset-chips">${[[.95,"Slow"],[1,"Normal"],[1.08,"Natural+"],[1.1,"Default"],[1.12,"Fast"],[1.15,"Fast+"]].map(([speed, label]) => `<button class="preset-chip ${Number(speed) === voice.speed ? "active" : ""}" data-action="speed-preset" data-speed="${speed}">${speed.toFixed(2)} ${label}</button>`).join("")}</div></div>
      </div></article>
      <details class="disclosure" ${voice.advancedOpen ? "open" : ""}><summary data-action="toggle-advanced">ADVANCED VOICE CONTROLS <span>⌄</span></summary><div class="advanced-inner disabled-layer"><div class="disabled-notice">These controls are designed for future engines. OmniVoice does not advertise them, so they are disabled.</div>${["Energy", "Expressiveness", "Stability", "Pause Strength", "Sentence Gap", "Emotion Strength"].map(label => `<div><label class="control-label">${label}<em>Unavailable</em></label><input type="range" disabled value="50" /></div>`).join("")}</div></details>
    </section>
    <section><article class="voice-preview-stage"><div class="preview-stage-head"><div><p class="eyebrow">Preview first</p><h2>Shape narration before rendering</h2></div><span class="preview-state">${voice.previewStatus}</span></div><textarea class="preview-copy" data-setting="preview-text">${escapeHtml(voice.previewText)}</textarea><div class="waveform ${voice.playing ? "playing" : ""}" id="waveform">${waves}</div>${voice.previewUrl ? `<audio id="active-voice-preview" class="voice-audio-player" controls preload="metadata" src="${voice.previewUrl}"></audio>` : ""}<div class="preview-controls"><div class="preview-buttons"><button class="button" data-action="generate-preview" ${voice.previewStatus === "GENERATING" ? "disabled" : ""}>${voice.previewStatus === "GENERATING" ? "Generating…" : "Quick Preview"}</button><button class="button-secondary" data-action="generate-full-preview" ${voice.previewStatus === "GENERATING" ? "disabled" : ""}>Full sentence</button><button class="button-secondary" data-action="play-preview" ${voice.previewUrl ? "" : "disabled"}>${voice.playing ? "Stop" : "Play"}</button></div><span class="audio-detail">Quick uses the first phrase · Real local OmniVoice · ${voice.speed.toFixed(2)}x</span></div><div class="voice-status-grid"><div class="voice-status"><span>Voice Engine</span><b>OmniVoice</b></div><div class="voice-status"><span>Selected Profile</span><b>Native design</b></div><div class="voice-status"><span>Subtitle Sync</span><b class="${voice.subtitleSync === "SYNCED" ? "check" : "warning"}">${voice.subtitleSync}</b></div></div>${voice.subtitleSync !== "SYNCED" ? `<button class="button-secondary" style="position:relative;z-index:1;margin-top:11px" data-action="update-timing">Update Timing</button>` : ""}</article>
      <div class="voice-lower"><article class="card card-pad"><div class="card-head"><div><p class="eyebrow">Preview history</p><h2 class="card-title">A/B-ready takes</h2></div><span class="caption">${voice.history.length} takes</span></div>${history}</article><article class="card card-pad"><div class="card-head"><div><p class="eyebrow">Compare</p><h2 class="card-title">A / B voice slots</h2></div><button class="button-quiet" data-action="add-compare">+ Add slot</button></div><div class="compare-slots">${comparisons}</div></article></div>
      <article class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Pronunciation Dictionary</p><h2 class="card-title">Names, acronyms, and multilingual corrections</h2></div><span class="caption">Stored by project in future</span></div><div class="dictionary-row"><input id="pronounce-original" class="text-input" placeholder="Original · Gulf Stream" /><input id="pronounce-as" class="text-input" placeholder="Pronounce as" /><button class="button-secondary" data-action="add-pronunciation">Add Rule</button></div><div class="dictionary-list">${voice.pronunciation.map(item => `<div class="dictionary-item"><span><b>${escapeHtml(item.original)}</b> → ${escapeHtml(item.pronunciation)}</span><button class="button-quiet" data-action="delete-pronunciation" data-word="${escapeHtml(item.original)}">Delete</button></div>`).join("")}</div></article>
    </section></div></section>`;
}

function renderSubtitles() {
  const subtitle = state.subtitleState;
  return `<section class="screen">${screenHeader("Subtitles", "Typography and language are separated from narration so future multilingual projects can translate or replace caption tracks.", `<button class="button" data-action="save-subtitles">Save subtitle preset</button>`)}
    <div class="grid two"><section class="card card-pad"><p class="eyebrow">Caption settings</p><div class="form-stack"><div class="form-row"><div><label class="field-label">Narration language</label><select class="select-input"><option>Vietnamese</option><option>English</option><option>Japanese</option></select></div><div><label class="field-label">Subtitle language</label><select class="select-input" data-setting="subtitle-language"><option value="same">Same as Narration</option><option value="vi">Vietnamese</option><option value="en">English</option><option value="ja">Japanese</option></select></div></div><div class="form-row three"><div><label class="field-label">Font</label><select class="select-input"><option>${subtitle.font}</option><option>Noto Sans</option></select></div><div><label class="field-label">Weight</label><select class="select-input"><option>${subtitle.weight}</option><option>Bold</option></select></div><div><label class="field-label">Position</label><select class="select-input"><option>${subtitle.position}</option><option>Center</option></select></div></div><div><label class="field-label">Size <small>${subtitle.size}px</small></label><input type="range" min="36" max="82" value="${subtitle.size}" data-setting="subtitle-size" /></div><div class="toggle-row"><span>Highlight phrase + keywords</span><button class="switch ${subtitle.highlight ? "on" : ""}" data-action="toggle-subtitle-highlight"></button></div><div class="toggle-row"><span>Safe zone guides</span><button class="switch ${subtitle.safeZone ? "on" : ""}" data-action="toggle-safe-zone"></button></div></div></section><section class="subtitle-preview"><span>Đại Tây Dương không chỉ là một khoảng nước.</span></section></div></section>`;
}

function renderAudio() {
  const rows = [["Narration", "narration", "Priority 1"], ["Flow Source", "source", "Priority 3"], ["BGM", "bgm", "Priority 4"], ["Important SFX", "sfx", "Priority 2"], ["Master", "master", "Output"]];
  return `<section class="screen">${screenHeader("Audio mix", "Narration stays dominant. Per-scene source-audio controls are available in the inspector; this screen controls project-wide mix targets.", `<button class="button" data-action="save-audio">Save source audio</button>`)}
    <div class="grid two"><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Project mix</p><h2 class="card-title">Level hierarchy</h2></div><span class="status-tag ready">Balanced</span></div>${rows.map(([label, id, note]) => `<div class="audio-level"><div><b>${label}</b><div class="tiny subtle">${note}</div></div><input type="range" min="0" max="100" value="${state.audioState[id]}" data-setting="audio-${id}" /><output>${state.audioState[id]}%</output></div>`).join("")}</section><section class="card card-pad"><p class="eyebrow">Source Audio defaults</p><h2 class="card-title">Flow ambience under narration</h2><div class="form-stack" style="margin-top:17px"><div class="form-row"><div><label class="field-label">Default mode</label><select class="select-input" data-setting="audio-source-mode">${optionList(["background", "mute", "full"], state.audioState.sourceMode)}</select></div><div><label class="field-label">Default volume</label><select class="select-input" data-setting="audio-source-volume">${optionList([15, 30, 50].map(value => ({id: value, label: `${value}%`})), state.audioState.source)}</select></div></div><div class="toggle-row"><span>Duck under narration</span><button class="switch ${state.audioState.sourceDuck ? "on" : ""}" data-action="toggle-project-source-duck"></button></div><p class="caption">This policy is saved to every current scene and becomes the default for the next render.</p></div></section></div></section>`;
}

function renderRender() {
  const steps = ["Preparing scenes", "Generating narration", "Syncing subtitles", "Mixing source audio", "Rendering Remotion", "FFmpeg mastering"];
  const render = state.renderState;
  const kept = keptScenes().length;
  const cut = cutScenes().length;
  const canRender = state.workflowState.scriptApproved && state.workflowState.voiceApproved;
  const hasPreview = state.workflowState.previewReady;
  const isRendering = renderPollTimer !== null;
  const canRenderFinal = canRender && state.workflowState.previewApproved && !state.reviewState.dirty && !isRendering;
  const playableUrl = render.videoUrl || (state.workflowState.finalReady ? `${STUDIO_API}/projects/${encodeURIComponent(state.projectState.id)}/render/final?t=${Date.now()}` : hasPreview ? `${STUDIO_API}/projects/${encodeURIComponent(state.projectState.id)}/render/preview?t=${Date.now()}` : null);
  return `<section class="screen">${screenHeader("Render", canRender ? "Create a preview with local OmniVoice narration. Watch and approve it before rendering the final video." : "Rendering is locked until you approve scene-by-scene script mapping and manual voice settings.", `<button class="button-quiet" data-nav="${hasPreview ? "scenes" : !state.workflowState.scriptApproved ? "script" : "voice"}">${hasPreview ? "Open Final Review" : !state.workflowState.scriptApproved ? "Review Script" : "Review Voice"}</button><button class="button-secondary" data-action="start-render" data-quality="preview" ${canRender && !isRendering ? "" : "disabled"}>Render Preview</button><button class="button" data-action="start-render" data-quality="final" ${canRenderFinal ? "" : "disabled"}>Render Final</button>`)}
    <div class="render-layout"><section class="card card-pad"><p class="eyebrow">Review player</p>${playableUrl ? `<video controls preload="metadata" style="display:block;max-height:480px;max-width:100%;margin:12px auto" src="${playableUrl}"></video>` : `<div class="video-player" data-project-title="${escapeHtml(activeProject().name)}"><span class="player-play">▶</span></div>`}<div style="display:flex;justify-content:space-between;margin-top:12px"><span class="caption">${kept} scenes · ${formatTime(projectDuration())} · ${activeProject().aspect} · ${activeProject().fps}fps · H.264</span><div><button class="button-secondary" data-nav="scenes" ${hasPreview ? "" : "disabled"}>Basic edits</button>${state.workflowState.finalReady ? `<a class="button-secondary" href="${STUDIO_API}/projects/${encodeURIComponent(state.projectState.id)}/render/final" download="${escapeHtml(state.projectState.id)}-final.mp4">Download final MP4</a>` : `<button class="button-quiet" data-action="approve-export" ${hasPreview && !state.reviewState.dirty && !state.workflowState.previewApproved ? "" : "disabled"}>${state.workflowState.previewApproved ? "Preview approved" : "Approve preview"}</button>`}</div></div></section><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Render progress</p><h2 class="card-title">${escapeHtml(render.status)}</h2></div><span class="caption">${render.progress}%</span></div><label class="field-label" style="margin:12px 0 6px">OmniVoice quality for next preview</label><select class="select-input" data-setting="render-voice-steps" ${isRendering ? "disabled" : ""}><option value="4" ${render.voiceSteps === 4 ? "selected" : ""}>Fast · 4 steps</option><option value="8" ${render.voiceSteps === 8 ? "selected" : ""}>Balanced · 8 steps</option><option value="16" ${render.voiceSteps === 16 ? "selected" : ""}>Detailed · 16 steps</option></select><p class="caption" style="margin:6px 0 12px">Final render reuses the narration you approved in the preview.</p><div class="progress-track"><i style="width:${render.progress}%"></i></div>${render.error ? `<p class="warning" style="margin-top:12px">${escapeHtml(render.error)}</p>` : ""}<div class="progress-steps">${steps.map((step, index) => `<div class="progress-step ${index < render.activeStep ? "done" : index === render.activeStep ? "active" : ""}"><span class="progress-dot">${index < render.activeStep ? "✓" : index + 1}</span><div><b>${step}</b><span>${index < render.activeStep ? "Done" : index === render.activeStep ? "Working…" : "Waiting"}</span></div><span class="tiny subtle">${index === 1 ? "Voice" : index === 4 ? "Remotion" : index === 5 ? "FFmpeg" : ""}</span></div>`).join("")}</div></section></div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Request changes</p><h2 class="card-title">Send a precise revision back through the project</h2></div></div><div class="form-row three"><div><label class="field-label">Scene</label><select class="select-input" data-setting="request-scene">${optionList(state.sceneState.items.map(scene => ({ id: scene.id, label: `Scene ${String(scene.number).padStart(2, "0")} · ${scene.title}` })), render.requestScene)}</select></div><div><label class="field-label">Change type</label><select class="select-input" data-setting="request-category">${optionList(["Source", "Trim", "Speed", "Crop", "Audio", "Transition", "Subtitle", "Voice Timing", "Voice Override"], render.requestCategory)}</select></div><div><label class="field-label">Action</label><button class="button-secondary" style="width:100%" data-action="apply-changes">Apply Changes</button></div></div><textarea id="change-comment" class="textarea-input compact-textarea" style="margin-top:10px" placeholder="Describe the correction for this scene…"></textarea></section>
  </section>`;
}

function renderSettings() {
  const project = activeProject();
  const statuses = ["DRAFT", "UPLOADED", "MAPPED", "SCRIPT_MAPPING", "VOICE_SETUP", "READY_TO_RENDER", "PROCESSING", "RENDERING", "POST_RENDER_REVIEW", "APPROVED", "NEEDS_CHANGES", "DONE"];
  return `<section class="screen">${screenHeader("Settings", "Workspace defaults remain separate from the active project. Local files and provider runtime state are scoped to this machine.")}
    <div class="grid two"><section class="card card-pad"><p class="eyebrow">Active project</p><h2 class="card-title">${escapeHtml(project.name)}</h2><div class="form-stack" style="margin-top:16px"><div><label class="field-label">Project status</label><select class="select-input" data-setting="project-stage">${optionList(statuses, state.projectState.stage)}</select></div><div class="form-row"><div><label class="field-label">Format</label><output class="readout">${project.resolution}</output></div><div><label class="field-label">Frame rate</label><output class="readout">${project.fps} fps</output></div></div><p class="caption">Changing this status affects only ${escapeHtml(project.name)}. Future global preferences stay outside each project record.</p></div></section><section class="card card-pad"><p class="eyebrow">Local runtime</p><h2 class="card-title">${backendOnline ? "Backend connected" : "Backend offline"}</h2><p class="caption">Flow ZIP import, project state, and OmniVoice previews use the local Python service. VoiceStudio is intentionally absent.</p></section></div></section>`;
}

function renderScreen() {
  const root = $("#screen-root");
  const screens = { dashboard: renderDashboard, import: renderImport, script: renderScript, scenes: renderScenes, voice: renderVoice, subtitles: renderSubtitles, audio: renderAudio, render: renderRender, settings: renderSettings };
  root.innerHTML = (screens[state.uiState.screen] || renderDashboard)();
  const title = NAVIGATION.find(item => item[0] === state.uiState.screen)?.[2] || "Dashboard";
  $("#screen-title").textContent = title;
  renderProjectContext();
  renderNavigation();
  renderInspector();
  renderTimeline();
}

function renderInspector() {
  const scene = currentScene();
  const overrideLanguages = VOICE_CAPABILITIES.supportedLanguages.map(id => LANGUAGE_CATALOG.find(item => item.id === id)).filter(Boolean);
  const inspector = $("#inspector");
  if (!scene || state.uiState.screen === "voice") {
    inspector.innerHTML = `<div class="inspector-head"><h2>Inspector</h2><span class="caption">Project</span></div><div class="inspector-empty"><div><p class="eyebrow">Progressive disclosure</p><b>${state.uiState.screen === "voice" ? "Voice has its own full workspace" : "Select a scene"}</b><p>${state.uiState.screen === "voice" ? "Per-scene voice override will appear here when a future provider supports it." : "Scene-level source, trim, crop, speed, audio, transitions, and optional voice overrides live here."}</p></div></div>`;
    return;
  }
  const finalCutControls = state.workflowState.previewReady ? `<div class="inspector-section"><h3>Final cut</h3><p class="caption">Your decision controls inclusion in the next preview and final render.</p><div class="cut-actions"><button class="button-secondary ${scene.decision === "keep" ? "selected-keep" : ""}" data-action="set-scene-decision" data-decision="keep">✓ Keep</button><button class="button-quiet ${scene.decision === "cut" ? "selected-cut" : ""}" data-action="set-scene-decision" data-decision="cut">✕ Cut</button></div></div>` : `<div class="inspector-section"><h3>Final cut</h3><p class="caption">Keep/Cut decisions unlock after a preview render, so script mapping and voice approval stay focused first.</p></div>`;
  inspector.innerHTML = `<div class="inspector-head"><h2>Scene Inspector</h2><button class="button-quiet" data-action="close-inspector">×</button></div><div class="inspector-section"><div class="inspector-scene-preview">${String(scene.number).padStart(2, "0")}</div><div class="inspector-title-row"><b>Scene ${String(scene.number).padStart(2, "0")}</b><span class="status-tag ${scene.status}">${scene.status}</span></div><p class="caption">${escapeHtml(scene.title)} · ${scene.source} · Version ${scene.sourceVersion}</p><div style="display:flex;gap:5px"><button class="button-secondary" data-action="approve-scene">Approve source</button><button class="button-quiet" data-action="reject-scene">Flag source</button><button class="button-quiet" data-action="replace-source">Replace</button></div></div>
    ${finalCutControls}
    <div class="inspector-section"><h3>Video edit</h3><label class="field-label">Trim start <small>${scene.edit.trimStart.toFixed(1)}s</small></label><input type="range" min="0" max="${Math.max(1, scene.duration - .5)}" step=".1" value="${scene.edit.trimStart}" data-scene-setting="trimStart" /><label class="field-label" style="margin-top:10px">Playback speed <small>${scene.edit.speed.toFixed(2)}x</small></label><select class="select-input" data-scene-setting="speed">${optionList([.5,.75,1,1.1,1.25,1.5,2], scene.edit.speed)}</select><div class="form-row" style="margin-top:10px"><div><label class="field-label">Crop</label><select class="select-input" data-scene-setting="crop">${optionList(["cover", "contain", "custom"], scene.edit.crop)}</select></div><div><label class="field-label">Position</label><select class="select-input" data-scene-setting="position">${optionList(["center", "top", "bottom", "left", "right"], scene.edit.position)}</select></div></div><label class="field-label" style="margin-top:10px">Transition</label><select class="select-input" data-scene-setting="transition">${optionList(["none", "crossfade", "soft slide", "wipe reveal", "paper"], scene.edit.transition)}</select><div class="toggle-row"><span>Hold last frame</span><button class="switch ${scene.edit.holdLastFrame ? "on" : ""}" data-action="toggle-hold"></button></div></div>
    <div class="inspector-section"><h3>Source audio</h3><label class="field-label">Mode</label><select class="select-input" data-audio-setting="mode">${optionList(["mute", "background", "full"], scene.sourceAudio.mode)}</select><label class="field-label" style="margin-top:10px">Volume <small>${scene.sourceAudio.volume}%</small></label><input type="range" min="0" max="100" value="${scene.sourceAudio.volume}" data-audio-setting="volume" /><div class="toggle-row"><span>Duck under narration</span><button class="switch ${scene.sourceAudio.duck ? "on" : ""}" data-action="toggle-duck"></button></div><div class="form-row"><div><label class="field-label">Fade In</label><input class="number-input" type="number" step=".05" value="${scene.sourceAudio.fadeIn}" data-audio-setting="fadeIn" /></div><div><label class="field-label">Fade Out</label><input class="number-input" type="number" step=".05" value="${scene.sourceAudio.fadeOut}" data-audio-setting="fadeOut" /></div></div></div>
    <div class="inspector-section"><h3>Voice override</h3><div class="toggle-row"><span>Use project default</span><button class="switch ${scene.voiceOverride ? "" : "on"}" data-action="toggle-voice-override"></button></div>${scene.voiceOverride ? `<div class="form-stack"><select class="select-input">${optionList(overrideLanguages, state.voiceState.language)}</select><select class="select-input"><option>Vietnamese Documentary Male</option><option>Vietnamese Documentary Female</option></select><select class="select-input"><option>1.10x</option><option>1.12x</option></select></div>` : `<p class="caption">Overrides are intentionally collapsed until needed.</p>`}</div>`;
}

function renderTimeline() {
  $("#timeline-summary").textContent = `${keptScenes().length} kept · ${cutScenes().length} cut · ${formatTime(projectDuration())}`;
  $("#timeline-zoom").textContent = `${Math.round(state.sceneState.timelineZoom * 100)}%`;
  $("#timeline").innerHTML = state.sceneState.items.map(scene => `<button class="timeline-scene ${scene.status} ${scene.decision === "cut" ? "cut" : ""} ${scene.id === state.sceneState.selectedId ? "selected" : ""}" type="button" data-action="select-scene" data-scene-id="${scene.id}" style="min-width:${Math.max(45, scene.duration * 9 * state.sceneState.timelineZoom)}px"><span>${String(scene.number).padStart(2, "0")}</span><i class="timeline-status"></i><span>${scene.decision === "cut" ? "CUT" : `${scene.duration}s`}</span></button>`).join("");
}

function setScreen(screen) { state.uiState.screen = screen; state.uiState.projectMenuOpen = false; renderScreen(); }
function selectScene(id) { if (state.sceneState.items.some(scene => scene.id === id)) { state.sceneState.selectedId = id; savePulse(); renderScreen(); } }
function markVoiceChanged(message = "Voice changed") {
  state.voiceState.subtitleSync = "NEEDS UPDATE";
  state.voiceState.previewStatus = "NOT GENERATED";
  state.voiceState.previewUrl = null;
  if (state.workflowState.scriptApproved) { state.workflowState.voiceApproved = false; state.workflowState.previewReady = false; state.projectState.stage = "VOICE_SETUP"; }
  if (backendOnline) {
    const voice = state.voiceState;
    apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/voice`, { method: "POST", body: JSON.stringify({ mode: voice.mode, language: voice.language, gender: voice.gender, age: voice.age, pitch: voice.pitch, speed: voice.speed }) })
      .then(() => savePulse(`${message} saved locally`))
      .catch(error => toast(error.message, "warning"));
  } else savePulse(message);
  renderScreen();
}
function setVoiceSpeed(value) { state.voiceState.speed = Math.min(1.2, Math.max(.85, +Number(value).toFixed(2))); markVoiceChanged(); }
function markReviewDirty() { if (state.workflowState.previewReady) { state.reviewState.dirty = true; state.reviewState.finalized = false; state.projectState.stage = "POST_RENDER_REVIEW"; } }

function parseScript() {
  const text = $("#bulk-script")?.value || state.scriptState.bulkText;
  if (backendOnline) {
    apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/script`, { method: "POST", body: JSON.stringify({ text }) })
      .then(() => loadBackendProject(state.projectState.id))
      .then(() => { state.uiState.screen = "script"; toast("Script mapped to the real project. Review the mapping before approval."); renderScreen(); })
      .catch(error => toast(error.message, "warning"));
    return;
  }
  state.scriptState.bulkText = text;
  const matches = [...text.matchAll(/SCENE\s*(\d+)[\s\S]*?Narration\s*:\s*["“]?([\s\S]*?)(?=\n\s*SCENE\s*\d+|$)/gi)];
  let mapped = 0;
  state.sceneState.items.forEach(scene => scene.narration = "");
  matches.forEach(match => {
    const scene = state.sceneState.items.find(item => item.number === Number(match[1]));
    const narration = match[2].trim().replace(/[”"]+$/, "").trim();
    if (scene && narration) { scene.narration = narration; mapped += 1; }
  });
  state.scriptState.mapped = state.sceneState.items.filter(scene => scene.narration).length;
  state.scriptState.missing = state.sceneState.items.length - state.scriptState.mapped;
  state.scriptState.approved = false;
  state.workflowState.scriptApproved = false;
  state.workflowState.voiceApproved = false;
  state.workflowState.previewReady = false;
  state.projectState.stage = "SCRIPT_MAPPING";
  toast(`${mapped} script block${mapped === 1 ? "" : "s"} mapped to dynamic scenes.`);
  savePulse(); renderScreen();
}

async function saveSceneScript() {
  const scene = currentScene();
  const narration = $("#scene-script")?.value.trim() || "";
  if (!scene || !narration) { toast("Enter narration for the selected scene first.", "warning"); return; }
  const selectedId = scene.id;
  if (backendOnline) {
    try {
      await apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/scenes/${encodeURIComponent(selectedId)}/script`, { method: "POST", body: JSON.stringify({ narration }) });
      await loadBackendProject(state.projectState.id);
      state.sceneState.selectedId = selectedId;
      state.uiState.screen = "script";
      renderScreen();
      toast(`Scene ${String(scene.number).padStart(2, "0")} saved. Other scenes were not changed.`, "success");
    } catch (error) { toast(error.message, "warning"); }
    return;
  }
  scene.narration = narration;
  state.scriptState.mapped = state.sceneState.items.filter(item => item.narration).length;
  state.scriptState.missing = state.sceneState.items.length - state.scriptState.mapped;
  state.scriptState.approved = false;
  state.workflowState.scriptApproved = false;
  state.workflowState.voiceApproved = false;
  state.workflowState.previewReady = false;
  state.projectState.stage = "SCRIPT_MAPPING";
  toast(`Scene ${String(scene.number).padStart(2, "0")} saved. Other scenes were not changed.`, "success");
  savePulse(); renderScreen();
}

function approveScriptMapping() {
  if (backendOnline) {
    apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/script/approve`, { method: "POST", body: "{}" })
      .then(() => loadBackendProject(state.projectState.id))
      .then(() => { state.uiState.screen = "voice"; toast("Script mapping approved."); renderScreen(); })
      .catch(error => toast(error.message, "warning"));
    return;
  }
  if (state.scriptState.mapped !== state.sceneState.items.length) { toast("Map every scene before approval.", "warning"); return; }
  state.scriptState.approved = true;
  state.workflowState.scriptApproved = true;
  state.workflowState.voiceApproved = false;
  state.workflowState.previewReady = false;
  state.projectState.stage = "VOICE_SETUP";
  state.uiState.screen = "voice";
  toast("Script mapping approved. Tune and approve the voice next.");
  savePulse("Script mapping approved");
  renderScreen();
}

function approveVoice() {
  if (backendOnline) {
    if (!state.voiceState.previewUrl) { toast("Generate and listen to an OmniVoice preview first.", "warning"); return; }
    apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/voice/approve`, { method: "POST", body: "{}" })
      .then(() => loadBackendProject(state.projectState.id))
      .then(() => { state.uiState.screen = "render"; toast("OmniVoice preview approved. Full narration is now the next gate.", "success"); renderScreen(); })
      .catch(error => toast(error.message, "warning"));
    return;
  }
  if (!state.workflowState.scriptApproved) { toast("Approve the script mapping first.", "warning"); return; }
  state.workflowState.voiceApproved = true;
  state.workflowState.previewReady = false;
  state.projectState.stage = "READY_TO_RENDER";
  state.uiState.screen = "render";
  toast("Voice approved. A preview render is now available.");
  savePulse("Voice approved");
  renderScreen();
}

function runAutoPrep() {
  if (state.automationState.status === "RUNNING") return;
  if (backendOnline) { $("#source-zip-input")?.click(); return; }
  if (!state.sceneState.items.length) {
    state.sceneState.items = makeScenes(5);
    state.sceneState.sceneCount = 5;
    state.sceneState.selectedId = "scene_01";
    state.scriptState = { bulkText: "", mapped: 0, missing: 5, approved: false };
  }
  state.projectState.imported = true;
  state.projectState.stage = "PROCESSING";
  state.workflowState = { scriptApproved: false, voiceApproved: false, previewReady: false };
  state.reviewState = { finalized: false, dirty: false, showCutsOnly: false };
  state.automationState = { status: "RUNNING", progress: 0, step: 0 };
  renderScreen();
  const interval = setInterval(() => {
    state.automationState.progress = Math.min(100, state.automationState.progress + 25);
    state.automationState.step = Math.min(4, Math.floor(state.automationState.progress / 25));
    if (state.automationState.progress >= 100) {
      clearInterval(interval);
      state.sceneState.items.forEach(scene => {
        scene.source = scene.source === "Missing" ? "Google Flow" : scene.source;
        scene.status = "ready";
        scene.decision = "keep";
        scene.narration = "";
      });
      state.scriptState = { bulkText: "", mapped: 0, missing: state.sceneState.items.length, approved: false };
      state.automationState = { status: "SOURCE READY", progress: 100, step: 4 };
      state.projectState.stage = "SCRIPT_MAPPING";
      state.uiState.screen = "script";
      toast("Source ready. Paste and review the script mapping.");
      savePulse("Source ready for script mapping");
    }
    renderScreen();
  }, 300);
}
function importZipFile(file) {
  if (!file || !backendOnline) return;
  if (state.automationState.status === "RUNNING") return;
  if (!file.name.toLowerCase().endsWith(".zip")) { toast("Choose a ZIP file exported from Flow.", "warning"); return; }
  const projectId = state.projectState.id;
  state.automationState = { status: "RUNNING", progress: 0, step: 0 };
  state.uiState.screen = "import";
  renderScreen();
  const request = new XMLHttpRequest();
  request.open("POST", `${STUDIO_API}/projects/${encodeURIComponent(projectId)}/import-zip`);
  request.setRequestHeader("X-File-Name", encodeURIComponent(file.name));
  request.setRequestHeader("Content-Type", "application/zip");
  request.upload.onprogress = event => {
    if (event.lengthComputable && state.projectState.id === projectId) {
      state.automationState.progress = Math.min(90, Math.round(event.loaded / event.total * 90));
      renderScreen();
    }
  };
  request.upload.onload = () => {
    if (state.projectState.id === projectId) { state.automationState.progress = 95; renderScreen(); }
  };
  request.onload = async () => {
    let payload = {};
    try { payload = JSON.parse(request.responseText); } catch (_) { /* Show HTTP status below. */ }
    if (request.status < 200 || request.status >= 300) {
      state.automationState = { status: "ERROR", progress: 0, step: 0 };
      toast(payload.error || `Import failed (HTTP ${request.status})`, "warning"); renderScreen(); return;
    }
    try {
      await loadBackendProject(projectId);
      state.uiState.screen = "import";
      toast(`${payload.valid_files} video(s) mapped. Review the scene order, then add narration.`);
      renderScreen();
    } catch (error) { state.automationState = { status: "ERROR", progress: 0, step: 0 }; toast(error.message, "warning"); renderScreen(); }
  };
  request.onerror = () => { state.automationState = { status: "ERROR", progress: 0, step: 0 }; toast("Connection to the local studio server was lost during ZIP import.", "warning"); renderScreen(); };
  request.send(file);
}
function chooseFolderPath() {
  if (!backendOnline) { runAutoPrep(); return; }
  const path = window.prompt("Full local path to the Flow source folder");
  if (!path?.trim()) return;
  state.automationState = { status: "RUNNING", progress: 95, step: 2 }; renderScreen();
  apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/import-path`, { method: "POST", body: JSON.stringify({ path: path.trim() }) })
    .then(() => loadBackendProject(state.projectState.id))
    .then(() => { state.uiState.screen = "import"; toast("Folder mapped. Review video order before adding narration."); renderScreen(); })
    .catch(error => { state.automationState = { status: "ERROR", progress: 0, step: 0 }; toast(error.message, "warning"); renderScreen(); });
}
function mockImport() { if (backendOnline) { $("#source-zip-input")?.click(); return; } toast("Start the local studio server before importing a source.", "warning"); }
function simulateScenes(count) { toast("Use a real Flow ZIP or folder for this project.", "warning"); }
async function generatePreview(previewScope = "quick") {
  const voice = state.voiceState;
  voice.previewText = $("[data-setting='preview-text']")?.value.trim() || voice.previewText.trim();
  if (!voice.previewText) { toast("Enter a short preview sentence first.", "warning"); return; }
  if (!backendOnline) { toast("Start the local studio server before generating OmniVoice.", "warning"); return; }
  voice.previewStatus = "GENERATING"; voice.previewUrl = null; voice.playing = false; renderScreen();
  try {
    const result = await apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/voice/preview`, {
      method: "POST", body: JSON.stringify({ text: voice.previewText, preview_scope: previewScope, mode: voice.mode, language: voice.language, gender: voice.gender, age: voice.age, pitch: voice.pitch, speed: voice.speed }),
    });
    voice.previewStatus = "GENERATED";
    voice.previewUrl = `${result.audio_url}?t=${Date.now()}`;
    voice.history.unshift({ id: result.preview_id, name: `OmniVoice ${voice.gender}`, language: "Vietnamese", gender: voice.gender, speed: voice.speed, duration: `${Number(result.duration || 0).toFixed(1)}s`, created: "just now", url: voice.previewUrl });
    toast(result.cache_hit ? "Loaded the matching OmniVoice preview from cache." : `${result.preview_scope === "quick" ? "Quick" : "Full"} OmniVoice preview generated locally.`, "success");
  } catch (error) {
    voice.previewStatus = "FAILED";
    toast(error.message, "warning");
  }
  renderScreen();
}
function togglePlay() {
  const player = $("#active-voice-preview");
  if (!player) { toast("Generate an OmniVoice preview first.", "warning"); return; }
  if (player.paused) { player.play().then(() => { state.voiceState.playing = true; }).catch(error => toast(error.message, "warning")); }
  else { player.pause(); state.voiceState.playing = false; }
}
function saveProfile() { const voice = state.voiceState; const id = `profile-${Date.now()}`; voice.profiles.unshift({ id, name: `Custom ${language().label} ${voice.gender === "male" ? "Male" : "Female"}`, provider: voice.provider, language: voice.language, locale: voice.locale, mode: voice.mode, gender: voice.gender, pitch: voice.pitch, speed: voice.speed }); voice.profileId = id; toast("Voice profile saved to prototype state."); savePulse(); renderScreen(); }
function useProfile(id) { const profile = state.voiceState.profiles.find(item => item.id === id); if (!profile) return; Object.assign(state.voiceState, { profileId: id, language: profile.language, locale: profile.locale, mode: profile.mode, gender: profile.gender, pitch: profile.pitch, speed: profile.speed, subtitleSync: "NEEDS UPDATE" }); toast(`${profile.name} applied.`); markVoiceChanged("Voice profile changed"); }
function applyRenderStatus(job) {
  const render = state.renderState;
  render.quality = job.quality || render.quality;
  render.status = job.status === "running" ? (job.detail || "RENDERING") : job.status === "failed" ? "FAILED" : job.status === "complete" ? `${render.quality.toUpperCase()} READY` : "READY";
  render.progress = Number(job.progress || 0);
  render.activeStep = Number.isInteger(job.step) ? job.step : -1;
  render.error = job.error || null;
  if (job.video_url) render.videoUrl = `${job.video_url}?t=${Date.now()}`;
}

function watchRenderStatus() {
  if (renderPollTimer) clearInterval(renderPollTimer);
  const projectId = state.projectState.id;
  renderPollTimer = setInterval(async () => {
    try {
      const job = await apiRequest(`/projects/${encodeURIComponent(projectId)}/render/status`);
      if (state.projectState.id !== projectId) { clearInterval(renderPollTimer); renderPollTimer = null; return; }
      if (job.status === "running") { applyRenderStatus(job); if (state.uiState.screen === "render") renderScreen(); return; }
      clearInterval(renderPollTimer); renderPollTimer = null;
      if (job.status === "complete") {
        await loadBackendProject(projectId);
        state.reviewState.dirty = false;
        toast(`${job.quality === "final" ? "Final" : "Preview"} video is ready. Watch it before approving.`, "success");
      } else if (job.status === "failed") {
        applyRenderStatus(job);
        toast(job.error || "Render failed. Check the local runtime.", "warning");
      }
      renderScreen();
    } catch (error) { clearInterval(renderPollTimer); renderPollTimer = null; toast(error.message, "warning"); }
  }, 1500);
}

async function startRender(quality) {
  if (!backendOnline) { toast("Start the local studio server before rendering a real video.", "warning"); return; }
  if (!state.workflowState.scriptApproved || !state.workflowState.voiceApproved) { toast("Approve script mapping and voice before rendering.", "warning"); return; }
  if (quality === "final" && !state.workflowState.previewApproved) { toast("Render, watch, and approve a preview before final rendering.", "warning"); return; }
  if (!keptScenes().length) { toast("Keep at least one scene before rendering.", "warning"); return; }
  if (renderPollTimer) { toast("A render is already running.", "warning"); return; }
  try {
    await projectWriteQueue;
    if (projectWriteError) throw projectWriteError;
    const job = await apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/render`, {
      method: "POST", body: JSON.stringify({ quality, voice_steps: state.renderState.voiceSteps }),
    });
    applyRenderStatus(job);
    toast(quality === "preview" ? "Generating OmniVoice narration, then rendering preview." : "Rendering final video locally.");
    watchRenderStatus();
    renderScreen();
  } catch (error) { toast(error.message, "warning"); }
}

async function approveRenderedPreview() {
  if (!backendOnline) { toast("This approval requires the local studio server.", "warning"); return; }
  if (!state.workflowState.previewReady || state.reviewState.dirty) { toast("Watch an up-to-date preview before approving it.", "warning"); return; }
  try {
    await apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/render/approve-preview`, { method: "POST", body: "{}" });
    await loadBackendProject(state.projectState.id);
    toast("Preview approved. You can now render the final video.", "success");
    renderScreen();
  } catch (error) { toast(error.message, "warning"); }
}

async function saveSceneDecisions(decisions) {
  if (!backendOnline) { toast("Start the local studio server before saving Keep/Cut decisions.", "warning"); return; }
  const projectId = state.projectState.id;
  const selectedId = state.sceneState.selectedId;
  try {
    await apiRequest(`/projects/${encodeURIComponent(projectId)}/render/decisions`, {
      method: "POST", body: JSON.stringify({ decisions }),
    });
    await loadBackendProject(projectId);
    state.sceneState.selectedId = selectedId;
    toast("Keep/Cut saved. Render an updated preview before final approval.", "success");
    renderScreen();
  } catch (error) { toast(error.message, "warning"); }
}

function setBackendVideoStatus(status, sceneId = currentScene()?.id) {
  const scene = state.sceneState.items.find(item => item.id === sceneId);
  if (!backendOnline || !scene?.sourceVersion) return false;
  apiRequest(`/projects/${encodeURIComponent(state.projectState.id)}/scenes/${encodeURIComponent(scene.id)}/video`, { method: "POST", body: JSON.stringify({ version: scene.sourceVersion, status }) })
    .then(() => loadBackendProject(state.projectState.id))
    .then(() => { state.sceneState.selectedId = scene.id; renderScreen(); toast(status === "approved" ? "Source version approved." : "Source version flagged for replacement.", status === "approved" ? "success" : "warning"); })
    .catch(error => toast(error.message, "warning"));
  return true;
}

function persistSceneEdit(action, extra = {}) {
  const scene = currentScene();
  if (!backendOnline || !scene?.sourceVersion) return;
  const projectId = state.projectState.id;
  const sceneId = scene.id;
  const version = scene.sourceVersion;
  const operation = projectWriteQueue.then(() => apiRequest(`/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/video/edit`, { method: "POST", body: JSON.stringify({ version, action, ...extra }) }));
  projectWriteQueue = operation.then(result => { projectWriteError = null; return result; }).catch(error => { projectWriteError = error; toast(error.message, "warning"); });
  return operation;
}

function saveProjectAudio() {
  if (!backendOnline) { toast("Start the local studio server before saving audio.", "warning"); return; }
  const projectId = state.projectState.id;
  const payload = { source_mode: state.audioState.sourceMode, source_volume: state.audioState.source / 100, source_duck: state.audioState.sourceDuck };
  state.sceneState.items.forEach(scene => { scene.sourceAudio.mode = payload.source_mode; scene.sourceAudio.volume = state.audioState.source; scene.sourceAudio.duck = payload.source_duck; });
  markReviewDirty();
  const operation = projectWriteQueue.then(() => apiRequest(`/projects/${encodeURIComponent(projectId)}/audio`, { method: "POST", body: JSON.stringify(payload) }));
  projectWriteQueue = operation.then(result => { projectWriteError = null; toast("Source audio saved for every scene.", "success"); return result; }).catch(error => { projectWriteError = error; toast(error.message, "warning"); });
  return operation;
}

function cropCoordinates(position) {
  return ({ center: [0.5, 0.5], top: [0.5, 0], bottom: [0.5, 1], left: [0, 0.5], right: [1, 0.5] })[position] || [0.5, 0.5];
}

document.addEventListener("click", event => {
  const target = event.target.closest("[data-action], [data-nav]");
  if (!target || target.disabled) return;
  const action = target.dataset.action;
  const nav = target.dataset.nav;
  if (nav) { if (target.dataset.sceneId) selectScene(target.dataset.sceneId); setScreen(nav); return; }
  switch (action) {
    case "open-project-menu": state.uiState.projectMenuOpen = !state.uiState.projectMenuOpen; renderProjectContext(); break;
    case "select-project": activateProject(target.dataset.projectId); break;
    case "create-project": createProject(); break;
    case "select-scene": selectScene(target.dataset.sceneId); break;
    case "simulate-scenes": simulateScenes(Number(target.dataset.count)); break;
    case "run-auto-prep": runAutoPrep(); break;
    case "mock-import": case "choose-zip": mockImport(); break;
    case "choose-folder": chooseFolderPath(); break;
    case "parse-script": parseScript(); break;
    case "select-script-scene": selectScene(target.dataset.sceneId); break;
    case "save-scene-script": saveSceneScript(); break;
    case "approve-script-mapping": approveScriptMapping(); break;
    case "approve-voice": approveVoice(); break;
    case "approve-scene": if (!setBackendVideoStatus("approved")) { currentScene().status = "approved"; toast("Scene approved."); savePulse(); renderScreen(); } break;
    case "reject-scene": if (!setBackendVideoStatus("rejected")) { currentScene().status = "rejected"; toast("Scene marked for replacement.", "warning"); savePulse(); renderScreen(); } break;
    case "review-import-source": setBackendVideoStatus(target.dataset.status, target.dataset.sceneId); break;
    case "approve-all": state.sceneState.items.forEach(scene => { if (scene.status === "pending") scene.status = "approved"; }); toast("Visible pending scenes approved."); renderScreen(); break;
    case "set-scene-decision": if (!state.workflowState.previewReady) { toast("Watch a preview before deciding Keep or Cut.", "warning"); break; } saveSceneDecisions({ [currentScene().id]: target.dataset.decision }); break;
    case "keep-all-scenes": if (!state.workflowState.previewReady) { toast("Watch a preview before deciding Keep or Cut.", "warning"); break; } saveSceneDecisions(Object.fromEntries(state.sceneState.items.map(scene => [scene.id, "keep"]))); break;
    case "toggle-cut-filter": state.reviewState.showCutsOnly = !state.reviewState.showCutsOnly; renderScreen(); break;
    case "finalize-review": if (!keptScenes().length) { toast("Keep at least one scene before finalizing.", "warning"); break; } state.uiState.screen = "render"; toast(`${keptScenes().length} kept scenes ready for a new preview.`); renderScreen(); break;
    case "replace-source": if (backendOnline) { state.uiState.screen = "import"; toast("Import a replacement ZIP or folder; existing versions remain available."); renderScreen(); } else { currentScene().source = "Google Flow"; currentScene().sourceVersion += 1; currentScene().status = "pending"; toast("Source replacement queued (mock).", "warning"); renderScreen(); } break;
    case "toggle-hold": currentScene().edit.holdLastFrame = !currentScene().edit.holdLastFrame; persistSceneEdit("hold_last_frame", { enabled: currentScene().edit.holdLastFrame }); markReviewDirty(); savePulse("Video edit changed"); renderInspector(); break;
    case "toggle-duck": currentScene().sourceAudio.duck = !currentScene().sourceAudio.duck; persistSceneEdit("source_audio", { mode: currentScene().sourceAudio.mode, volume: currentScene().sourceAudio.volume / 100, duck: currentScene().sourceAudio.duck, fade_in: currentScene().sourceAudio.fadeIn, fade_out: currentScene().sourceAudio.fadeOut }); markReviewDirty(); savePulse("Source audio changed"); renderInspector(); break;
    case "toggle-project-source-duck": state.audioState.sourceDuck = !state.audioState.sourceDuck; saveProjectAudio(); renderScreen(); break;
    case "toggle-voice-override": currentScene().voiceOverride = currentScene().voiceOverride ? null : { language: state.voiceState.language, speed: state.voiceState.speed }; renderInspector(); break;
    case "voice-mode": state.voiceState.mode = target.dataset.mode; markVoiceChanged(); break;
    case "voice-gender": state.voiceState.gender = target.dataset.value; markVoiceChanged(); break;
    case "voice-age": state.voiceState.age = target.dataset.value; markVoiceChanged(); break;
    case "voice-pitch": state.voiceState.pitch = target.dataset.value; markVoiceChanged(); break;
    case "speed-step": setVoiceSpeed(state.voiceState.speed + Number(target.dataset.direction) * .01); break;
    case "speed-preset": setVoiceSpeed(Number(target.dataset.speed)); break;
    case "generate-preview": generatePreview("quick"); break;
    case "generate-full-preview": generatePreview("full"); break;
    case "play-preview": case "play-history": case "play-compare": togglePlay(); break;
    case "select-history": { const item = state.voiceState.history.find(row => row.id === target.dataset.history); if (item) { state.voiceState.gender = item.gender.toLowerCase(); setVoiceSpeed(item.speed); toast(`${item.name} selected.`); } break; }
    case "delete-history": state.voiceState.history = state.voiceState.history.filter(row => row.id !== target.dataset.history); toast("Preview removed from local mock history."); renderScreen(); break;
    case "select-compare": state.voiceState.comparisons.forEach(item => item.selected = item.id === target.dataset.id); toast(`Comparison ${target.dataset.id} selected.`); renderScreen(); break;
    case "add-compare": { const id = String.fromCharCode(65 + state.voiceState.comparisons.length); state.voiceState.comparisons.push({ id, gender: "Custom", language: language().label, speed: state.voiceState.speed, selected: false }); renderScreen(); break; }
    case "save-voice-profile": saveProfile(); break;
    case "duplicate-profile": { const profile = state.voiceState.profiles.find(row => row.id === state.voiceState.profileId); if (profile) { const copy = { ...profile, id: `${profile.id}-copy-${Date.now()}`, name: `${profile.name} Copy` }; state.voiceState.profiles.unshift(copy); state.voiceState.profileId = copy.id; toast("Profile duplicated."); renderScreen(); } break; }
    case "rename-profile": { const profile = state.voiceState.profiles.find(row => row.id === state.voiceState.profileId); if (profile) { profile.name = `${profile.name.replace(/ Copy$/, "")} · Edited`; toast("Profile renamed in prototype."); renderScreen(); } break; }
    case "delete-profile": { if (state.voiceState.profiles.length > 1) { state.voiceState.profiles = state.voiceState.profiles.filter(row => row.id !== state.voiceState.profileId); state.voiceState.profileId = state.voiceState.profiles[0].id; toast("Profile deleted.", "warning"); renderScreen(); } break; }
    case "toggle-advanced": state.voiceState.advancedOpen = !state.voiceState.advancedOpen; break;
    case "add-pronunciation": { const original = $("#pronounce-original")?.value.trim(); const pronunciation = $("#pronounce-as")?.value.trim(); if (!original || !pronunciation) { toast("Add both original and pronunciation first.", "warning"); break; } state.voiceState.pronunciation.push({ original, pronunciation }); toast("Pronunciation rule added."); renderScreen(); break; }
    case "delete-pronunciation": state.voiceState.pronunciation = state.voiceState.pronunciation.filter(row => row.original !== target.dataset.word); renderScreen(); break;
    case "update-timing": state.voiceState.subtitleSync = "SYNCED"; toast("Subtitle timing updated (mock)."); renderScreen(); break;
    case "toggle-subtitle-highlight": state.subtitleState.highlight = !state.subtitleState.highlight; renderScreen(); break;
    case "toggle-safe-zone": state.subtitleState.safeZone = !state.subtitleState.safeZone; renderScreen(); break;
    case "save-subtitles": toast("Subtitle preset saved to prototype state."); savePulse(); break;
    case "save-audio": saveProjectAudio(); break;
    case "start-render": startRender(target.dataset.quality); break;
    case "rerender-preview": startRender("preview"); break;
    case "approve-export": approveRenderedPreview(); break;
    case "request-changes": $("#change-comment")?.focus(); break;
    case "apply-changes": if (!state.workflowState.previewReady) { toast("Create a preview before applying review changes.", "warning"); break; } markReviewDirty(); state.uiState.screen = "scenes"; toast("Change request recorded. Adjust the scene and render an updated preview.", "warning"); savePulse("Review change requested"); renderScreen(); break;
    case "timeline-zoom-in": state.sceneState.timelineZoom = Math.min(1.6, state.sceneState.timelineZoom + .1); renderTimeline(); break;
    case "timeline-zoom-out": state.sceneState.timelineZoom = Math.max(.6, state.sceneState.timelineZoom - .1); renderTimeline(); break;
    default: break;
  }
});

document.addEventListener("change", event => {
  const target = event.target;
  const setting = target.dataset.setting;
  if (setting === "voice-language") { state.voiceState.language = target.value; state.voiceState.locale = language().locales[0]; markVoiceChanged(); }
  if (setting === "voice-locale") { state.voiceState.locale = target.value; markVoiceChanged(); }
  if (setting === "voice-profile") useProfile(target.value);
  if (setting === "voice-speed") setVoiceSpeed(target.value);
  if (setting === "preview-text") { state.voiceState.previewText = target.value; }
  if (setting === "subtitle-language") { state.subtitleState.language = target.value; }
  if (setting === "subtitle-size") { state.subtitleState.size = Number(target.value); }
  if (setting === "audio-source-mode") { state.audioState.sourceMode = target.value; saveProjectAudio(); renderScreen(); }
  else if (setting === "audio-source-volume") { state.audioState.source = Number(target.value); saveProjectAudio(); renderScreen(); }
  else if (setting?.startsWith("audio-")) { const key = setting.replace("audio-", ""); state.audioState[key] = Number(target.value); if (key === "source") saveProjectAudio(); renderScreen(); }
  if (setting === "request-scene") state.renderState.requestScene = target.value;
  if (setting === "render-voice-steps") state.renderState.voiceSteps = Number(target.value);
  if (setting === "request-category") state.renderState.requestCategory = target.value;
  if (setting === "project-stage") { state.projectState.stage = target.value; savePulse("Project status updated"); renderScreen(); }
  if (target.dataset.sceneSetting) {
    const key = target.dataset.sceneSetting;
    const scene = currentScene();
    scene.edit[key] = key === "speed" || key === "trimStart" ? Number(target.value) : target.value;
    if (key === "speed") persistSceneEdit("speed", { speed: scene.edit.speed });
    if (key === "trimStart") persistSceneEdit("trim", { start: scene.edit.trimStart, end: scene.edit.trimEnd || scene.duration });
    if (key === "crop" || key === "position") { const [x, y] = cropCoordinates(scene.edit.position); persistSceneEdit("crop", { mode: scene.edit.crop === "custom" ? "cover" : scene.edit.crop, x, y }); }
    if (key === "transition") persistSceneEdit("transition", { transition: scene.edit.transition.replaceAll(" ", "_") });
    markReviewDirty(); savePulse("Video edit changed"); renderInspector(); renderTimeline();
  }
  if (target.dataset.audioSetting) {
    const key = target.dataset.audioSetting;
    const scene = currentScene();
    scene.sourceAudio[key] = ["volume", "fadeIn", "fadeOut"].includes(key) ? Number(target.value) : target.value;
    persistSceneEdit("source_audio", { mode: scene.sourceAudio.mode, volume: scene.sourceAudio.volume / 100, duck: scene.sourceAudio.duck, fade_in: scene.sourceAudio.fadeIn, fade_out: scene.sourceAudio.fadeOut });
    markReviewDirty(); savePulse("Source audio changed"); renderInspector();
  }
});

document.addEventListener("dragover", event => { if (event.target.closest("#dropzone")) { event.preventDefault(); $("#dropzone")?.classList.add("dragging"); } });
document.addEventListener("dragleave", event => { if (event.target.closest("#dropzone")) $("#dropzone")?.classList.remove("dragging"); });
document.addEventListener("drop", event => { if (event.target.closest("#dropzone")) { event.preventDefault(); $("#dropzone")?.classList.remove("dragging"); const file = event.dataTransfer?.files?.[0]; if (backendOnline && file) importZipFile(file); else mockImport(); } });
$("#source-zip-input")?.addEventListener("change", event => { importZipFile(event.target.files?.[0]); event.target.value = ""; });

renderScreen();
hydrateLocalWorkspace();
