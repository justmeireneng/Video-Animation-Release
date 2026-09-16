/*
 * Static desktop prototype only. State domains mirror the future Tauri + React
 * app boundary; no request in this file calls the current Python backend.
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
  age: false,
  pitch: true,
  styles: false,
  clone: false,
  referenceAudio: false,
  advanced: false,
  speed: { min: 0.85, max: 1.2, step: 0.01 },
};

const DEFAULT_NARRATION = "Dự án này bắt đầu bằng bối cảnh rõ ràng, sau đó dẫn người xem qua các ý chính theo từng cảnh có thể kiểm soát độc lập.";

const PROJECT_SEEDS = [
  { id: "atlantic-ocean", name: "Atlantic Ocean", initials: "AO", stage: "FINAL_REVIEW", sceneCount: 14, resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: true, updated: "Updated today" },
  { id: "urban-gardens", name: "Urban Gardens", initials: "UG", stage: "SCRIPT", sceneCount: 8, resolution: "1920 × 1080", aspect: "16:9", fps: 30, imported: true, updated: "Updated yesterday" },
  { id: "product-launch", name: "Product Launch 2026", initials: "PL", stage: "DRAFT", sceneCount: 0, resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: false, updated: "Created Sep 16" },
];

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
  workspaceState: { projects: PROJECT_SEEDS.map(project => ({ ...project })), activeProjectId: "atlantic-ocean" },
  projectState: { id: "atlantic-ocean", name: "Atlantic Ocean", initials: "AO", stage: "FINAL_REVIEW", resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: true },
  sceneState: { items: makeScenes(14), selectedId: "scene_01", sceneCount: 14, timelineZoom: 1 },
  scriptState: { bulkText: "SCENE 1\nNarration:\n\"Mỗi dự án bắt đầu bằng một bối cảnh rõ ràng và một mục tiêu cụ thể cho người xem.\"\n\nSCENE 2\nNarration:\n\"Từ đó, từng cảnh có thể phát triển ý chính theo một cấu trúc nhất quán.\"", mapped: 2, missing: 12 },
  voiceState: {
    provider: "omnivoice", language: "vi", locale: "default", mode: "voice_design", gender: "male", age: "young adult", pitch: "moderate", style: "documentary", speed: 1.1,
    profileId: "vn-documentary-male", previewText: DEFAULT_NARRATION, previewStatus: "READY", playing: false, subtitleSync: "SYNCED", advancedOpen: false,
    profiles: [
      { id: "vn-documentary-male", name: "Vietnamese Documentary Male", provider: "omnivoice", language: "vi", locale: "default", mode: "voice_design", gender: "male", pitch: "moderate", speed: 1.1 },
      { id: "vn-documentary-female", name: "Vietnamese Documentary Female", provider: "omnivoice", language: "vi", locale: "default", mode: "voice_design", gender: "female", pitch: "moderate", speed: 1.08 },
      { id: "en-explainer", name: "English Explainer", provider: "future", language: "en", locale: "en-US", mode: "voice_design", gender: "female", pitch: "moderate", speed: 1.0 },
    ],
    history: [
      { id: "a", name: "Male 1.08", language: "Vietnamese", gender: "Male", speed: 1.08, duration: "8.1s", created: "2 min ago" },
      { id: "b", name: "Male 1.12", language: "Vietnamese", gender: "Male", speed: 1.12, duration: "7.8s", created: "12 min ago" },
      { id: "c", name: "Female 1.08", language: "Vietnamese", gender: "Female", speed: 1.08, duration: "8.2s", created: "Today" },
      { id: "d", name: "Female 1.12", language: "Vietnamese", gender: "Female", speed: 1.12, duration: "7.9s", created: "Today" },
    ],
    comparisons: [
      { id: "A", gender: "Male", language: "Vietnamese", speed: 1.08, selected: true },
      { id: "B", gender: "Female", language: "Vietnamese", speed: 1.12, selected: false },
    ],
    pronunciation: [{ original: "Gulf Stream", pronunciation: "Gâlf Strim" }],
  },
  subtitleState: { language: "same", font: "Be Vietnam Pro", weight: "SemiBold", size: 55, position: "Bottom", offset: 102, highlight: true, safeZone: true },
  audioState: { narration: 100, source: 30, bgm: 12, sfx: 35, master: 100 },
  reviewState: { finalized: false },
  automationState: { status: "READY FOR REVIEW", progress: 100, step: 4 },
  renderState: { quality: "preview", status: "READY", progress: 0, activeStep: -1, requestScene: "scene_11", requestCategory: "Source" },
  uiState: { screen: "dashboard", inspector: "scene", projectMenuOpen: false },
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" }[char]));
const currentScene = () => state.sceneState.items.find(scene => scene.id === state.sceneState.selectedId) || state.sceneState.items[0];
const language = () => LANGUAGE_CATALOG.find(item => item.id === state.voiceState.language) || LANGUAGE_CATALOG[0];
const formatTime = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, "0")}`;
const keptScenes = () => state.sceneState.items.filter(scene => scene.decision !== "cut");
const cutScenes = () => state.sceneState.items.filter(scene => scene.decision === "cut");
const projectDuration = () => keptScenes().reduce((total, item) => total + item.duration, 0);
const activeProject = () => state.workspaceState.projects.find(project => project.id === state.workspaceState.activeProjectId) || state.workspaceState.projects[0];

function projectStageLabel(stage) {
  return ({ UPLOADED: "Uploaded", MAPPED: "Mapped", SCRIPT: "Script", READY: "Ready", PROCESSING: "Preparing", FINAL_REVIEW: "Final review", RENDERING: "Rendering", REVIEW: "Review", APPROVED: "Approved", NEEDS_CHANGES: "Needs changes", DONE: "Done", DRAFT: "Draft" })[stage] || stage;
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
    snapshot: { sceneState: structuredClone(state.sceneState), scriptState: structuredClone(state.scriptState), reviewState: structuredClone(state.reviewState), automationState: structuredClone(state.automationState) },
  });
}

function activateProject(id) {
  if (id === state.workspaceState.activeProjectId) { state.uiState.projectMenuOpen = false; renderProjectContext(); return; }
  syncActiveProject();
  const project = state.workspaceState.projects.find(item => item.id === id);
  if (!project) return;
  state.workspaceState.activeProjectId = project.id;
  state.projectState = { id: project.id, name: project.name, initials: project.initials, stage: project.stage, resolution: project.resolution, aspect: project.aspect, fps: project.fps, imported: project.imported };
  state.sceneState = project.snapshot ? structuredClone(project.snapshot.sceneState) : { items: makeScenes(project.sceneCount), selectedId: project.sceneCount ? "scene_01" : null, sceneCount: project.sceneCount, timelineZoom: 1 };
  state.scriptState = project.snapshot ? structuredClone(project.snapshot.scriptState) : { bulkText: "", mapped: 0, missing: project.sceneCount };
  state.reviewState = project.snapshot?.reviewState ? structuredClone(project.snapshot.reviewState) : { finalized: false };
  state.automationState = project.snapshot?.automationState ? structuredClone(project.snapshot.automationState) : { status: project.stage === "FINAL_REVIEW" ? "READY FOR REVIEW" : "IDLE", progress: project.stage === "FINAL_REVIEW" ? 100 : 0, step: project.stage === "FINAL_REVIEW" ? 4 : 0 };
  state.renderState.requestScene = state.sceneState.items[0]?.id || "";
  state.uiState.projectMenuOpen = false;
  state.uiState.screen = "dashboard";
  toast(`${project.name} is now the active project.`);
  savePulse();
  renderScreen();
}

function createProject() {
  syncActiveProject();
  const number = state.workspaceState.projects.length + 1;
  const project = { id: `untitled-project-${Date.now()}`, name: `Untitled Project ${number}`, initials: "NP", stage: "DRAFT", sceneCount: 0, resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: false, updated: "Created just now" };
  state.workspaceState.projects.unshift(project);
  state.workspaceState.activeProjectId = project.id;
  state.projectState = { id: project.id, name: project.name, initials: project.initials, stage: project.stage, resolution: project.resolution, aspect: project.aspect, fps: project.fps, imported: project.imported };
  state.sceneState = { items: [], selectedId: null, sceneCount: 0, timelineZoom: 1 };
  state.scriptState = { bulkText: "", mapped: 0, missing: 0 };
  state.reviewState = { finalized: false };
  state.automationState = { status: "IDLE", progress: 0, step: 0 };
  state.renderState.requestScene = "";
  state.uiState.projectMenuOpen = false;
  state.uiState.screen = "import";
  toast("New project created. Add a source when ready.");
  savePulse();
  renderScreen();
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
  const readyForReview = state.projectState.stage === "FINAL_REVIEW";
  const projectRows = state.workspaceState.projects.map(item => `<button class="workspace-project-row ${item.id === project.id ? "active" : ""}" data-action="select-project" data-project-id="${item.id}"><span class="project-avatar">${item.initials}</span><span><b>${escapeHtml(item.name)}</b><small>${item.sceneCount} scenes · ${escapeHtml(item.updated)}</small></span><span class="project-menu-status">${projectStageLabel(item.stage)}</span></button>`).join("");
  const nextUp = !state.sceneState.items.length ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Next up</p><h2 class="card-title">Add a source ZIP</h2></div><span class="status-tag pending">Not imported</span></div><p class="caption">This project has no scenes yet. Drop a Flow ZIP or folder and automatic preparation will start.</p><button class="button-secondary" data-nav="import">Import source</button></section>` : preparing ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Automatic preparation</p><h2 class="card-title">Preparing ${state.automationState.progress}%</h2></div><span class="status-tag review">Running</span></div><p class="caption">Source mapping, script mapping, narration setup, subtitle timing, and timeline preparation are running before your review.</p></section>` : state.reviewState.finalized ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Cut locked</p><h2 class="card-title">Ready to render</h2></div><span class="status-tag ready">${kept} scenes</span></div><p class="caption">The final cut is locked for rendering. You can reopen Final Review any time to change it.</p><button class="button-secondary" data-nav="render">Render preview</button></section>` : readyForReview ? `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Your decision</p><h2 class="card-title">Final cut review</h2></div><span class="status-tag review">${kept} keep · ${cut} cut</span></div><p class="caption">Choose what stays, what is cut, and make basic trim, crop, speed, audio, or transition adjustments before rendering.</p><button class="button-secondary" data-nav="scenes">Open Final Review</button></section>` : `<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Next up</p><h2 class="card-title">Run automatic preparation</h2></div><span class="status-tag pending">Ready</span></div><p class="caption">The source is present. Let the project prepare first, then review only the final cut.</p><button class="button-secondary" data-action="run-auto-prep">Start auto-prep</button></section>`;
  return `<section class="screen">${screenHeader("Project workspace", `Active project: ${project.name}. Keep multiple productions separate while using one compact workspace.`, `<button class="button-secondary" data-action="create-project">New project</button><button class="button" data-nav="render">Render preview</button>`)}
    <div class="grid four">${metric("ACTIVE PROJECT", escapeHtml(project.name), `${projectStageLabel(project.stage)} · ${project.updated}`, "blue")}${metric("SOURCE SCENES", state.sceneState.items.length, state.projectState.imported ? "ZIP mapped to project" : "Waiting for ZIP")}${metric("FINAL CUT", `${kept} kept`, `${cut} cut · user controlled`)}${metric("FINAL LENGTH", formatTime(projectDuration()), `${project.fps} fps · ${project.aspect}`, "amber")}</div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Production flow</p><h2 class="card-title">Automate preparation; review the final cut</h2></div><button class="button-quiet" data-nav="${state.sceneState.items.length ? "scenes" : "import"}">${state.sceneState.items.length ? "Open Final Review →" : "Import source →"}</button></div>
      <div class="workflow">${[["Source ZIP", state.projectState.imported ? "done" : "current", state.projectState.imported ? `${state.sceneState.items.length} scenes detected` : "Source needed"],["Auto-prep", state.automationState.progress === 100 ? "done" : preparing ? "current" : "", state.automationState.progress === 100 ? "Mapped" : preparing ? `${state.automationState.progress}%` : "Waiting"],["Final review", readyForReview ? "current" : state.reviewState.finalized ? "done" : "", readyForReview ? `${kept} keep · ${cut} cut` : state.reviewState.finalized ? "Locked for render" : "Waiting"],["Preview", state.renderState.status === "PREVIEW READY" ? "done" : "", state.renderState.status === "PREVIEW READY" ? "Ready" : "Optional"],["Export", state.projectState.stage === "APPROVED" ? "done" : "", state.projectState.stage === "APPROVED" ? "Approved" : "After review"]].map(([name, cls, small], index) => `<div class="workflow-step ${cls}"><span class="step-number">0${index + 1}</span><strong>${name}</strong><small>${small}</small></div>`).join("")}</div></section>
    <div class="grid two" style="margin-top:16px">${nextUp}<section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Workspace projects</p><h2 class="card-title">Switch without mixing assets</h2></div><button class="button-quiet" data-action="create-project">＋ New</button></div><p class="caption">Source, scene count, scripts, review state, and output settings belong to the selected project.</p><div class="workspace-project-list">${projectRows}</div></section></div>
  </section>`;
}

function renderImport() {
  const total = state.sceneState.items.length;
  const auto = state.automationState;
  const autoSteps = ["Detect & sort Scene_<number>", "Map script and source metadata", "Prepare OmniVoice and subtitles", "Build final review timeline"];
  return `<section class="screen">${screenHeader("Import Google Flow source", `Bring a ZIP or folder into ${activeProject().name}. Once the source is recognized, preparation runs automatically and stops at Final Review for your decisions.`, `<button class="button-secondary" data-action="run-auto-prep" ${auto.status === "RUNNING" ? "disabled" : ""}>${auto.status === "RUNNING" ? "Preparing…" : "Start auto-prep"}</button>`)}
    <div class="import-dropzone" id="dropzone"><div><div class="drop-icon">⇩</div><h2>DROP GOOGLE FLOW ZIP HERE</h2><p class="caption">The future app parses ZIP files locally. It will not upload the source to a cloud service.</p><div class="drop-actions"><button class="button" data-action="choose-zip">Choose ZIP & Run</button><button class="button-secondary" data-action="choose-folder">Choose Folder & Run</button></div></div></div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Dynamic scene count</p><h2 class="card-title">Simulate source sizes before building backend</h2></div></div><div class="simulator-row">${[5, 14, 24].map(count => `<button class="chip-button ${total === count ? "active" : ""}" data-action="simulate-scenes" data-count="${count}">Simulate ${count} Scenes</button>`).join("")}</div></section>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Last mock import</p><h2 class="card-title">Scene_<number> files sorted numerically</h2></div><span class="status-tag ${total ? "ready" : "pending"}">${total ? "Mapped" : "Waiting for source"}</span></div><div class="upload-report"><div class="report-cell"><b>${total}</b><span>Videos detected</span></div><div class="report-cell"><b>${total ? Math.max(0, total - 1) : 0}</b><span>Mapped</span></div><div class="report-cell"><b>${total ? 1 : 0}</b><span>Duplicates</span></div><div class="report-cell"><b>${total ? 1 : 0}</b><span>Missing</span></div><div class="report-cell"><b>0</b><span>Invalid</span></div></div></section>
    <section class="card card-pad auto-prep-card" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Automatic preparation</p><h2 class="card-title">${auto.status}</h2></div><span class="caption">${auto.progress}%</span></div><p class="caption">Automation prepares the project but does not decide the final cut. That stays with you in Final Review.</p><div class="progress-track"><i style="width:${auto.progress}%"></i></div><div class="auto-prep-list">${autoSteps.map((step, index) => `<div class="${index < auto.step ? "done" : index === auto.step && auto.status === "RUNNING" ? "active" : ""}"><span>${index < auto.step ? "✓" : index + 1}</span><b>${step}</b><small>${index < auto.step ? "Done" : index === auto.step && auto.status === "RUNNING" ? "Running…" : "Waiting"}</small></div>`).join("")}</div></section>
  </section>`;
}

function renderScript() {
  const previewRows = state.sceneState.items.slice(0, 7).map(scene => `<div class="validation-row"><span class="${scene.source === "Missing" ? "warning" : "check"}">${scene.source === "Missing" ? "▲" : "✓"}</span><b>Scene ${String(scene.number).padStart(2, "0")}</b><span class="muted">Video ${scene.source === "Missing" ? "missing" : "ready"} · Script ${scene.narration ? "ready" : "missing"}</span></div>`).join("");
  return `<section class="screen">${screenHeader("Script mapping", "Paste one script for all scenes, then refine narration individually from the Scene Inspector. The parser handles SCENE <number> blocks.", `<button class="button" data-action="parse-script">Map narration to scenes</button>`)}
    <div class="script-layout"><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Bulk paste</p><h2 class="card-title">Narration by scene</h2></div><span class="caption">${state.scriptState.mapped} mapped</span></div><label class="field-label">Paste format <small>SCENE 1 → Narration: → “text”</small></label><textarea id="bulk-script" class="textarea-input">${escapeHtml(state.scriptState.bulkText)}</textarea><div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px"><span class="caption">Unmatched blocks remain in draft; nothing is rendered.</span><button class="button" data-action="parse-script">Parse & map</button></div></section>
      <aside class="card card-pad"><div class="card-head"><div><p class="eyebrow">Validation</p><h2 class="card-title">Source + script health</h2></div><span class="status-tag pending">${state.scriptState.missing} missing</span></div>${previewRows}<button class="button-quiet" data-nav="scenes" style="margin-top:9px">Open all ${state.sceneState.items.length} scenes →</button></aside></div>
  </section>`;
}

function renderScenes() {
  const kept = keptScenes().length;
  const cut = cutScenes().length;
  if (!state.sceneState.items.length) return `<section class="screen">${screenHeader("Final Review", "Import a source first. Automatic preparation will build the review timeline before you make cut decisions.", `<button class="button" data-nav="import">Import source</button>`)}<div class="empty-state"><div><h2>No review timeline yet</h2><p>Once a Flow ZIP is prepared, each scene appears here with Keep/Cut and basic edit controls.</p></div></div></section>`;
  return `<section class="screen">${screenHeader("Final Review", "This is your only required decision point after automatic preparation. Select a scene, choose Keep or Cut, then adjust trim, speed, crop, transition, or source audio in the inspector.", `<button class="button-secondary" data-action="keep-all-scenes">Keep all</button><button class="button" data-action="finalize-review">Finalize ${kept} kept · ${cut} cut</button>`)}
    <section class="card card-pad review-summary"><div><p class="eyebrow">Cut decision</p><h2 class="card-title">${kept} kept · ${cut} cut · ${formatTime(projectDuration())} final duration</h2><p class="caption">Cut scenes stay available for reversal but are excluded from preview and final render.</p></div><button class="button-quiet" data-action="toggle-cut-filter">${state.reviewState.showCutsOnly ? "Show all scenes" : "Show cuts only"}</button></section>
    <div class="scene-grid">${state.sceneState.items.filter(scene => !state.reviewState.showCutsOnly || scene.decision === "cut").map(sceneCard).join("")}</div>
  </section>`;
}

function optionList(items, selected) { return items.map(item => `<option value="${item.id || item}" ${String(item.id || item) === String(selected) ? "selected" : ""}>${item.label || item}</option>`).join(""); }
function selectedClass(actual, expected) { return actual === expected ? "active" : ""; }
function capabilityHint(supported, label = "Future provider capability") { return supported ? "" : `<span class="support-hint">${label}</span>`; }

function renderVoice() {
  const voice = state.voiceState;
  const lang = language();
  const localeOptions = lang.locales.map(locale => ({ id: locale, label: locale === "default" ? "Default" : locale }));
  const profileOptions = voice.profiles.map(profile => ({ id: profile.id, label: profile.name }));
  const isLanguageReady = VOICE_CAPABILITIES.supportedLanguages.includes(voice.language);
  const waves = Array.from({ length: 44 }, (_, index) => `<i class="wave" style="height:${18 + ((index * 23) % 70)}px;animation-delay:-${(index % 9) / 10}s"></i>`).join("");
  const history = voice.history.map(item => `<div class="history-row"><div class="history-title"><b>${item.name}</b><span>${item.language} · ${item.gender} · ${item.speed.toFixed(2)}x · ${item.duration} · ${item.created}</span></div><button data-action="play-history" data-history="${item.id}">Play</button><button data-action="select-history" data-history="${item.id}">Select</button><button data-action="delete-history" data-history="${item.id}">Delete</button></div>`).join("");
  const comparisons = voice.comparisons.map(item => `<div class="compare-slot"><span class="compare-key">${item.id}</span><div><b>${item.gender} narrator</b><span>${item.language} · ${item.speed.toFixed(2)}x</span></div><div><button data-action="play-compare" data-id="${item.id}">Play ${item.id}</button> <button data-action="select-compare" data-id="${item.id}">${item.selected ? "Selected" : `Select ${item.id}`}</button></div></div>`).join("");
  return `<section class="screen">${screenHeader("Voice", "A dedicated preview-first voice workspace. OmniVoice is the only active engine; future-language and provider controls are visibly marked as prototype or unavailable.", `<button class="button-secondary" data-action="save-voice-profile">Save Profile</button><button class="button" data-action="generate-preview">Generate Preview</button>`)}
    <div class="voice-layout"><section class="voice-config"><article class="card card-pad"><p class="eyebrow">Voice engine</p><div class="voice-engine"><div class="voice-engine-icon">◖</div><div><b>OmniVoice</b><span>Active production engine · Edge TTS runtime</span></div><span class="availability">● ACTIVE</span></div>
      <div class="form-stack" style="margin-top:15px"><div><label class="control-label">Language <em>${isLanguageReady ? "Supported now" : "Future provider mock"}</em></label><div class="select-with-hint"><select class="select-input" data-setting="voice-language">${optionList(LANGUAGE_CATALOG, voice.language)}</select>${capabilityHint(isLanguageReady, "prototype")}</div></div>
        <div><label class="control-label">Accent / Locale <em>${voice.language === "vi" ? "Default active" : "Mock options"}</em></label><select class="select-input" data-setting="voice-locale">${optionList(localeOptions, voice.locale)}</select></div>
        <div><label class="control-label">Voice Profile</label><select class="select-input" data-setting="voice-profile">${optionList(profileOptions, voice.profileId)}</select><div style="display:flex;gap:4px;margin-top:7px"><button class="button-quiet" data-action="duplicate-profile">Duplicate</button><button class="button-quiet" data-action="rename-profile">Rename</button><button class="button-quiet" data-action="delete-profile">Delete</button></div></div>
      </div></article>
      <article class="card card-pad"><p class="eyebrow">Voice direction</p><div class="form-stack"><div><label class="control-label">Mode <em>Clone is engine-gated</em></label><div class="segmented"><button class="${selectedClass(voice.mode, "auto")}" data-action="voice-mode" data-mode="auto">Auto</button><button class="${selectedClass(voice.mode, "voice_design")}" data-action="voice-mode" data-mode="voice_design">Voice Design</button><button class="unsupported" disabled title="OmniVoice does not support clone yet">Voice Clone</button></div></div>
        <div class="${voice.mode === "voice_design" ? "" : "disabled-layer"}"><label class="control-label">Gender</label><div class="option-pills"><button class="chip-button ${selectedClass(voice.gender, "male")}" data-action="voice-gender" data-value="male">Male</button><button class="chip-button ${selectedClass(voice.gender, "female")}" data-action="voice-gender" data-value="female">Female</button></div></div>
        <div class="${VOICE_CAPABILITIES.age ? "" : "disabled-layer"}"><label class="control-label">Age <em>${VOICE_CAPABILITIES.age ? "Supported" : "Not supported by OmniVoice"}</em></label><div class="option-pills">${["young adult", "middle-aged", "older adult"].map(value => `<button class="chip-button ${selectedClass(voice.age, value)} ${VOICE_CAPABILITIES.age ? "" : "unsupported"}" ${VOICE_CAPABILITIES.age ? `data-action="voice-age" data-value="${value}"` : "disabled"}>${value}</button>`).join("")}</div></div>
        <div><label class="control-label">Pitch</label><div class="option-pills">${["low", "moderate", "high"].map(value => `<button class="chip-button ${selectedClass(voice.pitch, value)}" data-action="voice-pitch" data-value="${value}">${value}</button>`).join("")}</div></div>
        <div class="${VOICE_CAPABILITIES.styles ? "" : "disabled-layer"}"><label class="control-label">Tone / Style <em>${VOICE_CAPABILITIES.styles ? "Supported" : "Future provider capability"}</em></label><div class="option-pills">${["neutral", "warm", "calm", "energetic", "documentary", "friendly", "serious", "educational"].map(value => `<button class="chip-button ${selectedClass(voice.style, value)} ${VOICE_CAPABILITIES.styles ? "" : "unsupported"}" ${VOICE_CAPABILITIES.styles ? `data-action="voice-style" data-value="${value}"` : "disabled"}>${value}</button>`).join("")}</div></div>
        <div class="speed-control"><div class="speed-title"><div><p class="eyebrow">Voice speed</p><b>Rate without pitch shift</b></div><div class="stepper"><button data-action="speed-step" data-direction="-1">−</button><span class="speed-readout">${voice.speed.toFixed(2)}x</span><button data-action="speed-step" data-direction="1">+</button></div></div><input type="range" min="0.85" max="1.20" step="0.01" value="${voice.speed}" data-setting="voice-speed" /><div class="preset-chips">${[[.95,"Slow"],[1,"Normal"],[1.08,"Natural+"],[1.1,"Default"],[1.12,"Fast"],[1.15,"Fast+"]].map(([speed, label]) => `<button class="preset-chip ${Number(speed) === voice.speed ? "active" : ""}" data-action="speed-preset" data-speed="${speed}">${speed.toFixed(2)} ${label}</button>`).join("")}</div></div>
      </div></article>
      <details class="disclosure" ${voice.advancedOpen ? "open" : ""}><summary data-action="toggle-advanced">ADVANCED VOICE CONTROLS <span>⌄</span></summary><div class="advanced-inner disabled-layer"><div class="disabled-notice">These controls are designed for future engines. OmniVoice does not advertise them, so they are disabled.</div>${["Energy", "Expressiveness", "Stability", "Pause Strength", "Sentence Gap", "Emotion Strength"].map(label => `<div><label class="control-label">${label}<em>Unavailable</em></label><input type="range" disabled value="50" /></div>`).join("")}</div></details>
    </section>
    <section><article class="voice-preview-stage"><div class="preview-stage-head"><div><p class="eyebrow">Preview first</p><h2>Shape narration before rendering</h2></div><span class="preview-state">${voice.previewStatus}</span></div><textarea class="preview-copy" data-setting="preview-text">${escapeHtml(voice.previewText)}</textarea><div class="waveform ${voice.playing ? "playing" : ""}" id="waveform">${waves}</div><div class="preview-controls"><div class="preview-buttons"><button class="button" data-action="generate-preview">Generate Preview</button><button class="button-secondary" data-action="play-preview">${voice.playing ? "Stop" : "Play"}</button></div><span class="audio-detail">Mock WAV · ${voice.speed.toFixed(2)}x · ${voice.gender === "male" ? "Nam Minh" : "Hoài My"}</span></div><div class="voice-status-grid"><div class="voice-status"><span>Voice Engine</span><b>OmniVoice</b></div><div class="voice-status"><span>Selected Profile</span><b>${escapeHtml((voice.profiles.find(profile => profile.id === voice.profileId) || {}).name || "Custom")}</b></div><div class="voice-status"><span>Subtitle Sync</span><b class="${voice.subtitleSync === "SYNCED" ? "check" : "warning"}">${voice.subtitleSync}</b></div></div>${voice.subtitleSync !== "SYNCED" ? `<button class="button-secondary" style="position:relative;z-index:1;margin-top:11px" data-action="update-timing">Update Timing</button>` : ""}</article>
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
  return `<section class="screen">${screenHeader("Audio mix", "Narration stays dominant. Per-scene source-audio controls are available in the inspector; this screen controls project-wide mix targets.", `<button class="button" data-action="save-audio">Save Mix</button>`)}
    <div class="grid two"><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Project mix</p><h2 class="card-title">Level hierarchy</h2></div><span class="status-tag ready">Balanced</span></div>${rows.map(([label, id, note]) => `<div class="audio-level"><div><b>${label}</b><div class="tiny subtle">${note}</div></div><input type="range" min="0" max="100" value="${state.audioState[id]}" data-setting="audio-${id}" /><output>${state.audioState[id]}%</output></div>`).join("")}</section><section class="card card-pad"><p class="eyebrow">Source Audio defaults</p><h2 class="card-title">Flow ambience under narration</h2><div class="form-stack" style="margin-top:17px"><div class="form-row"><div><label class="field-label">Default mode</label><select class="select-input"><option>Background</option><option>Mute</option><option>Full</option></select></div><div><label class="field-label">Default volume</label><select class="select-input"><option>30%</option><option>15%</option><option>50%</option></select></div></div><div class="toggle-row"><span>Duck under narration</span><button class="switch on"></button></div><p class="caption">Priority: Narration → Important SFX → Source ambience → BGM. Nothing here changes source media until a future backend is connected.</p></div></section></div></section>`;
}

function renderRender() {
  const steps = ["Preparing scenes", "Generating narration", "Syncing subtitles", "Mixing source audio", "Rendering Remotion", "FFmpeg mastering"];
  const render = state.renderState;
  const kept = keptScenes().length;
  const cut = cutScenes().length;
  return `<section class="screen">${screenHeader("Render & final review", `${kept} kept scenes will be included; ${cut} cut scenes are excluded. Choose a low-cost preview first, then approve export after you inspect the player.`, `<button class="button-quiet" data-nav="scenes">Adjust Final Review</button><button class="button-secondary" data-action="start-render" data-quality="preview">Render Preview</button><button class="button" data-action="start-render" data-quality="final">Render Final</button>`)}
    <div class="render-layout"><section class="card card-pad"><p class="eyebrow">Final player</p><div class="video-player" data-project-title="${escapeHtml(activeProject().name)}"><span class="player-play">▶</span></div><div style="display:flex;justify-content:space-between;margin-top:12px"><span class="caption">${kept} scenes · ${formatTime(projectDuration())} · ${activeProject().aspect} · ${activeProject().fps}fps · H.264</span><div><button class="button-secondary" data-action="approve-export">Approve & Export</button><button class="button-quiet" data-action="request-changes">Request Changes</button></div></div></section><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Render progress</p><h2 class="card-title">${render.status}</h2></div><span class="caption">${render.progress}%</span></div><div class="progress-track"><i style="width:${render.progress}%"></i></div><div class="progress-steps">${steps.map((step, index) => `<div class="progress-step ${index < render.activeStep ? "done" : index === render.activeStep ? "active" : ""}"><span class="progress-dot">${index < render.activeStep ? "✓" : index + 1}</span><div><b>${step}</b><span>${index < render.activeStep ? "Done" : index === render.activeStep ? "Working…" : "Waiting"}</span></div><span class="tiny subtle">${index === 1 ? "Voice" : index === 4 ? "Remotion" : index === 5 ? "FFmpeg" : ""}</span></div>`).join("")}</div></section></div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Request changes</p><h2 class="card-title">Send a precise revision back through the project</h2></div></div><div class="form-row three"><div><label class="field-label">Scene</label><select class="select-input" data-setting="request-scene">${optionList(state.sceneState.items.map(scene => ({ id: scene.id, label: `Scene ${String(scene.number).padStart(2, "0")} · ${scene.title}` })), render.requestScene)}</select></div><div><label class="field-label">Change type</label><select class="select-input" data-setting="request-category">${optionList(["Source", "Trim", "Speed", "Crop", "Audio", "Transition", "Subtitle", "Voice Timing", "Voice Override"], render.requestCategory)}</select></div><div><label class="field-label">Action</label><button class="button-secondary" style="width:100%" data-action="apply-changes">Apply Changes</button></div></div><textarea id="change-comment" class="textarea-input compact-textarea" style="margin-top:10px" placeholder="Describe the correction for this scene…"></textarea></section>
  </section>`;
}

function renderSettings() {
  const project = activeProject();
  const statuses = ["DRAFT", "UPLOADED", "MAPPED", "SCRIPT", "PROCESSING", "FINAL_REVIEW", "READY", "RENDERING", "REVIEW", "APPROVED", "NEEDS_CHANGES", "DONE"];
  return `<section class="screen">${screenHeader("Settings", "Workspace defaults remain separate from the active project. Provider integrations, filesystem paths, and rendering jobs are intentionally not wired here.")}
    <div class="grid two"><section class="card card-pad"><p class="eyebrow">Active project</p><h2 class="card-title">${escapeHtml(project.name)}</h2><div class="form-stack" style="margin-top:16px"><div><label class="field-label">Project status</label><select class="select-input" data-setting="project-stage">${optionList(statuses, state.projectState.stage)}</select></div><div class="form-row"><div><label class="field-label">Format</label><output class="readout">${project.resolution}</output></div><div><label class="field-label">Frame rate</label><output class="readout">${project.fps} fps</output></div></div><p class="caption">Changing this status affects only ${escapeHtml(project.name)}. Future global preferences stay outside each project record.</p></div></section><section class="card card-pad"><p class="eyebrow">Prototype boundary</p><h2 class="card-title">No backend connection</h2><p class="caption">All imports, scripts, previews, voice settings, renders, and exports in this prototype are in-memory UI interactions. OmniVoice is shown as the active engine only; VoiceStudio is intentionally absent.</p></section></div></section>`;
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
  inspector.innerHTML = `<div class="inspector-head"><h2>Scene Inspector</h2><button class="button-quiet" data-action="close-inspector">×</button></div><div class="inspector-section"><div class="inspector-scene-preview">${String(scene.number).padStart(2, "0")}</div><div class="inspector-title-row"><b>Scene ${String(scene.number).padStart(2, "0")}</b><span class="status-tag ${scene.status}">${scene.status}</span></div><p class="caption">${escapeHtml(scene.title)} · ${scene.source} · Version ${scene.sourceVersion}</p><div style="display:flex;gap:5px"><button class="button-secondary" data-action="approve-scene">Approve source</button><button class="button-quiet" data-action="reject-scene">Flag source</button><button class="button-quiet" data-action="replace-source">Replace</button></div></div>
    <div class="inspector-section"><h3>Final cut</h3><p class="caption">Your decision controls inclusion in preview and final render.</p><div class="cut-actions"><button class="button-secondary ${scene.decision === "keep" ? "selected-keep" : ""}" data-action="set-scene-decision" data-decision="keep">✓ Keep</button><button class="button-quiet ${scene.decision === "cut" ? "selected-cut" : ""}" data-action="set-scene-decision" data-decision="cut">✕ Cut</button></div></div>
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
function setVoiceSpeed(value) { state.voiceState.speed = Math.min(1.2, Math.max(.85, +Number(value).toFixed(2))); state.voiceState.subtitleSync = "NEEDS UPDATE"; savePulse("Voice changed"); renderScreen(); }

function parseScript() {
  const text = $("#bulk-script")?.value || state.scriptState.bulkText;
  state.scriptState.bulkText = text;
  const matches = [...text.matchAll(/SCENE\s*(\d+)[\s\S]*?Narration\s*:\s*["“]?([\s\S]*?)(?=\n\s*SCENE\s*\d+|$)/gi)];
  let mapped = 0;
  matches.forEach(match => {
    const scene = state.sceneState.items.find(item => item.number === Number(match[1]));
    const narration = match[2].trim().replace(/[”"]+$/, "").trim();
    if (scene && narration) { scene.narration = narration; mapped += 1; }
  });
  state.scriptState.mapped = state.sceneState.items.filter(scene => scene.narration).length;
  state.scriptState.missing = state.sceneState.items.length - state.scriptState.mapped;
  toast(`${mapped} script block${mapped === 1 ? "" : "s"} mapped to dynamic scenes.`);
  savePulse(); renderScreen();
}

function runAutoPrep() {
  if (state.automationState.status === "RUNNING") return;
  if (!state.sceneState.items.length) {
    state.sceneState.items = makeScenes(5);
    state.sceneState.sceneCount = 5;
    state.sceneState.selectedId = "scene_01";
    state.scriptState = { bulkText: "", mapped: 0, missing: 5 };
  }
  state.projectState.imported = true;
  state.projectState.stage = "PROCESSING";
  state.reviewState = { finalized: false, showCutsOnly: false };
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
        scene.narration = scene.narration || `Narration placeholder for Scene ${scene.number}.`;
      });
      state.scriptState.mapped = state.sceneState.items.length;
      state.scriptState.missing = 0;
      state.voiceState.subtitleSync = "SYNCED";
      state.automationState = { status: "READY FOR REVIEW", progress: 100, step: 4 };
      state.projectState.stage = "FINAL_REVIEW";
      state.uiState.screen = "scenes";
      toast("Automatic preparation complete. Make the final cut decisions.");
      savePulse("Ready for Final Review");
    }
    renderScreen();
  }, 300);
}
function mockImport() { runAutoPrep(); }
function simulateScenes(count) { state.sceneState.items = makeScenes(count); state.sceneState.sceneCount = count; state.sceneState.selectedId = state.sceneState.items[0]?.id || null; state.scriptState.mapped = Math.min(2, count); state.scriptState.missing = Math.max(0, count - state.scriptState.mapped); state.projectState.imported = count > 0; state.projectState.stage = count ? "MAPPED" : "DRAFT"; state.reviewState = { finalized: false, showCutsOnly: false }; state.automationState = { status: "IDLE", progress: 0, step: 0 }; toast(`Prototype now renders ${count} scenes.`); savePulse(); renderScreen(); }
function generatePreview() { state.voiceState.previewStatus = "GENERATING…"; state.voiceState.playing = false; renderScreen(); setTimeout(() => { state.voiceState.previewStatus = "READY"; state.voiceState.history.unshift({ id: `take-${Date.now()}`, name: `${state.voiceState.gender === "male" ? "Male" : "Female"} ${state.voiceState.speed.toFixed(2)}`, language: language().label, gender: state.voiceState.gender === "male" ? "Male" : "Female", speed: state.voiceState.speed, duration: "8.0s", created: "Just now" }); toast("Preview generated (mock). No video render started."); savePulse(); renderScreen(); }, 760); }
function togglePlay() { state.voiceState.playing = !state.voiceState.playing; toast(state.voiceState.playing ? "Playing mock preview…" : "Preview stopped."); renderScreen(); }
function saveProfile() { const voice = state.voiceState; const id = `profile-${Date.now()}`; voice.profiles.unshift({ id, name: `Custom ${language().label} ${voice.gender === "male" ? "Male" : "Female"}`, provider: voice.provider, language: voice.language, locale: voice.locale, mode: voice.mode, gender: voice.gender, pitch: voice.pitch, speed: voice.speed }); voice.profileId = id; toast("Voice profile saved to prototype state."); savePulse(); renderScreen(); }
function useProfile(id) { const profile = state.voiceState.profiles.find(item => item.id === id); if (!profile) return; Object.assign(state.voiceState, { profileId: id, language: profile.language, locale: profile.locale, mode: profile.mode, gender: profile.gender, pitch: profile.pitch, speed: profile.speed, subtitleSync: "NEEDS UPDATE" }); toast(`${profile.name} applied.`); renderScreen(); }
function startRender(quality) { const render = state.renderState; render.quality = quality; render.status = `RENDERING ${quality.toUpperCase()}`; render.progress = 0; render.activeStep = 0; renderScreen(); const interval = setInterval(() => { render.progress = Math.min(100, render.progress + 9); render.activeStep = Math.min(5, Math.floor(render.progress / 17)); renderScreen(); if (render.progress >= 100) { clearInterval(interval); render.status = quality === "final" ? "FINAL READY FOR REVIEW" : "PREVIEW READY"; render.activeStep = 6; toast(`${quality === "final" ? "Final" : "Preview"} render complete (mock).`); renderScreen(); } }, 280); }

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
    case "mock-import": case "choose-zip": case "choose-folder": mockImport(); break;
    case "parse-script": parseScript(); break;
    case "approve-scene": currentScene().status = "approved"; toast("Scene approved."); savePulse(); renderScreen(); break;
    case "reject-scene": currentScene().status = "rejected"; toast("Scene marked for replacement.", "warning"); savePulse(); renderScreen(); break;
    case "approve-all": state.sceneState.items.forEach(scene => { if (scene.status === "pending") scene.status = "approved"; }); toast("Visible pending scenes approved."); renderScreen(); break;
    case "set-scene-decision": currentScene().decision = target.dataset.decision; state.reviewState.finalized = false; state.projectState.stage = "FINAL_REVIEW"; toast(`Scene ${String(currentScene().number).padStart(2, "0")} marked ${target.dataset.decision}.`); savePulse("Cut decision saved"); renderScreen(); break;
    case "keep-all-scenes": state.sceneState.items.forEach(scene => { scene.decision = "keep"; }); state.reviewState.finalized = false; state.projectState.stage = "FINAL_REVIEW"; toast("All scenes marked keep."); savePulse("Cut decisions saved"); renderScreen(); break;
    case "toggle-cut-filter": state.reviewState.showCutsOnly = !state.reviewState.showCutsOnly; renderScreen(); break;
    case "finalize-review": if (!keptScenes().length) { toast("Keep at least one scene before finalizing.", "warning"); break; } state.reviewState.finalized = true; state.projectState.stage = "READY"; state.uiState.screen = "render"; toast(`${keptScenes().length} kept scenes locked for render.`); savePulse("Final cut ready"); renderScreen(); break;
    case "replace-source": currentScene().source = "Google Flow"; currentScene().sourceVersion += 1; currentScene().status = "pending"; toast("Source replacement queued (mock).", "warning"); renderScreen(); break;
    case "toggle-hold": currentScene().edit.holdLastFrame = !currentScene().edit.holdLastFrame; renderInspector(); break;
    case "toggle-duck": currentScene().sourceAudio.duck = !currentScene().sourceAudio.duck; renderInspector(); break;
    case "toggle-voice-override": currentScene().voiceOverride = currentScene().voiceOverride ? null : { language: state.voiceState.language, speed: state.voiceState.speed }; renderInspector(); break;
    case "voice-mode": state.voiceState.mode = target.dataset.mode; renderScreen(); break;
    case "voice-gender": state.voiceState.gender = target.dataset.value; renderScreen(); break;
    case "voice-pitch": state.voiceState.pitch = target.dataset.value; renderScreen(); break;
    case "speed-step": setVoiceSpeed(state.voiceState.speed + Number(target.dataset.direction) * .01); break;
    case "speed-preset": setVoiceSpeed(Number(target.dataset.speed)); break;
    case "generate-preview": generatePreview(); break;
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
    case "save-subtitles": case "save-audio": toast("Preset saved to prototype state."); savePulse(); break;
    case "start-render": startRender(target.dataset.quality); break;
    case "approve-export": state.projectState.stage = "APPROVED"; toast("Project approved for export (mock)."); savePulse(); break;
    case "request-changes": $("#change-comment")?.focus(); break;
    case "apply-changes": state.projectState.stage = "NEEDS_CHANGES"; toast("Change request applied to project state.", "warning"); savePulse(); break;
    case "timeline-zoom-in": state.sceneState.timelineZoom = Math.min(1.6, state.sceneState.timelineZoom + .1); renderTimeline(); break;
    case "timeline-zoom-out": state.sceneState.timelineZoom = Math.max(.6, state.sceneState.timelineZoom - .1); renderTimeline(); break;
    default: break;
  }
});

document.addEventListener("change", event => {
  const target = event.target;
  const setting = target.dataset.setting;
  if (setting === "voice-language") { state.voiceState.language = target.value; state.voiceState.locale = language().locales[0]; state.voiceState.subtitleSync = "NEEDS UPDATE"; renderScreen(); }
  if (setting === "voice-locale") { state.voiceState.locale = target.value; renderScreen(); }
  if (setting === "voice-profile") useProfile(target.value);
  if (setting === "voice-speed") setVoiceSpeed(target.value);
  if (setting === "preview-text") { state.voiceState.previewText = target.value; }
  if (setting === "subtitle-language") { state.subtitleState.language = target.value; }
  if (setting === "subtitle-size") { state.subtitleState.size = Number(target.value); }
  if (setting?.startsWith("audio-")) { const key = setting.replace("audio-", ""); state.audioState[key] = Number(target.value); renderScreen(); }
  if (setting === "request-scene") state.renderState.requestScene = target.value;
  if (setting === "request-category") state.renderState.requestCategory = target.value;
  if (setting === "project-stage") { state.projectState.stage = target.value; savePulse("Project status updated"); renderScreen(); }
  if (target.dataset.sceneSetting) { const key = target.dataset.sceneSetting; currentScene().edit[key] = key === "speed" || key === "trimStart" ? Number(target.value) : target.value; renderInspector(); renderTimeline(); }
  if (target.dataset.audioSetting) { const key = target.dataset.audioSetting; currentScene().sourceAudio[key] = ["volume", "fadeIn", "fadeOut"].includes(key) ? Number(target.value) : target.value; renderInspector(); }
});

document.addEventListener("dragover", event => { if (event.target.closest("#dropzone")) { event.preventDefault(); $("#dropzone")?.classList.add("dragging"); } });
document.addEventListener("dragleave", event => { if (event.target.closest("#dropzone")) $("#dropzone")?.classList.remove("dragging"); });
document.addEventListener("drop", event => { if (event.target.closest("#dropzone")) { event.preventDefault(); $("#dropzone")?.classList.remove("dragging"); mockImport(); } });

renderScreen();
