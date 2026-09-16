/*
 * Static desktop prototype only. State domains mirror the future Tauri + React
 * app boundary; no request in this file calls the current Python backend.
 */
const NAVIGATION = [
  ["dashboard", "▦", "Dashboard"], ["import", "⇩", "Import"], ["script", "≡", "Script"],
  ["scenes", "▧", "Scenes"], ["voice", "◖", "Voice"], ["subtitles", "▤", "Subtitles"],
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

const DEFAULT_NARRATION = "Đại Tây Dương không chỉ là một khoảng nước nằm giữa các lục địa. Nó là một hệ thống khổng lồ kết nối khí hậu, địa chất, thương mại và lịch sử của cả thế giới.";

function makeScenes(count) {
  const subjects = ["Atlantic overview", "Geographic position", "Ocean scale", "Mid-Atlantic Ridge", "Plate movement", "Gulf Stream", "Climate impact", "Sea routes", "Global trade", "Subsea cables", "Ecosystems", "Human pressure", "Connected system", "Closing thought"];
  return Array.from({ length: count }, (_, index) => ({
    id: `scene_${String(index + 1).padStart(2, "0")}`,
    number: index + 1,
    title: subjects[index] || `Ocean story ${index + 1}`,
    narration: index === 0 ? DEFAULT_NARRATION : "",
    source: index % 6 === 5 ? "Missing" : "Google Flow",
    sourceVersion: index % 3 === 0 ? 2 : 1,
    duration: +(5.4 + ((index * 11) % 31) / 10).toFixed(1),
    status: index < 8 ? "approved" : index === 10 ? "rejected" : "pending",
    sourceAudio: { mode: "background", volume: 30, duck: true, fadeIn: .15, fadeOut: .2 },
    edit: { trimStart: 0, trimEnd: null, speed: 1, crop: "cover", position: "center", holdLastFrame: true, transition: index === 0 ? "none" : "soft slide" },
    voiceOverride: null,
  }));
}

const state = {
  projectState: { name: "Atlantic Ocean", stage: "REVIEW", resolution: "1080 × 1920", aspect: "9:16", fps: 30, imported: true },
  sceneState: { items: makeScenes(14), selectedId: "scene_01", sceneCount: 14, timelineZoom: 1 },
  scriptState: { bulkText: "SCENE 1\nNarration:\n\"Đại Tây Dương không chỉ là một khoảng nước nằm giữa các lục địa. Nó là một hệ thống khổng lồ kết nối khí hậu, địa chất, thương mại và lịch sử của cả thế giới.\"\n\nSCENE 2\nNarration:\n\"Nó nằm giữa châu Mỹ ở phía tây, và châu Âu cùng châu Phi ở phía đông.\"", mapped: 2, missing: 12 },
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
  renderState: { quality: "preview", status: "READY", progress: 0, activeStep: -1, requestScene: "scene_11", requestCategory: "Source" },
  uiState: { screen: "dashboard", inspector: "scene" },
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" }[char]));
const currentScene = () => state.sceneState.items.find(scene => scene.id === state.sceneState.selectedId) || state.sceneState.items[0];
const language = () => LANGUAGE_CATALOG.find(item => item.id === state.voiceState.language) || LANGUAGE_CATALOG[0];
const formatTime = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, "0")}`;
const projectDuration = () => state.sceneState.items.reduce((total, item) => total + item.duration, 0);

function savePulse(message = "All changes saved") {
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
  return `<article class="scene-card ${scene.id === state.sceneState.selectedId ? "selected" : ""}" data-action="select-scene" data-scene-id="${scene.id}">
    <div class="scene-thumb"><span class="scene-index">${String(scene.number).padStart(2, "0")}</span><span class="play-dot">▶</span></div>
    <div class="scene-card-body"><div class="scene-card-title"><b>${escapeHtml(scene.title)}</b><span class="status-tag ${scene.status}">${scene.status}</span></div>
      <p class="scene-card-copy">${hasScript ? escapeHtml(scene.narration) : "Narration needed — add script for this scene."}</p>
      <div class="scene-meta"><span>${scene.source}${scene.sourceVersion ? ` · v${scene.sourceVersion}` : ""}</span><span>${scene.duration}s</span></div>
    </div></article>`;
}

function renderDashboard() {
  const completed = state.sceneState.items.filter(scene => scene.status === "approved").length;
  return `<section class="screen">${screenHeader("Good morning, Nhieu Loc", "Your Atlantic project is ready for a focused review. Start from the next item below or jump directly into any workspace.", `<button class="button" data-nav="render">Render preview</button>`)}
    <div class="grid four">${metric("PROJECT STATUS", "Review", "● 8 scenes approved", "blue")}${metric("SCENES", state.sceneState.items.length, `${completed} approved · ${state.sceneState.items.length - completed} pending`)}${metric("NARRATION", "Ready", "OmniVoice · Vietnamese")}${metric("FINAL LENGTH", formatTime(projectDuration()), "30 fps · 9:16", "amber")}</div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Production flow</p><h2 class="card-title">Simple steps, detailed controls only when needed</h2></div><button class="button-quiet" data-nav="scenes">Open scene review →</button></div>
      <div class="workflow">${[["Import", "done", "ZIP mapped"],["Script", "done", "2 / 14 mapped"],["Scenes", "current", "8 approved"],["Voice", "", "Preview ready"],["Render", "", "Not started"]].map(([name, cls, small], index) => `<div class="workflow-step ${cls}"><span class="step-number">0${index + 1}</span><strong>${name}</strong><small>${small}</small></div>`).join("")}</div></section>
    <div class="grid two" style="margin-top:16px"><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Next up</p><h2 class="card-title">Review scene 11 source</h2></div><span class="status-tag pending">Needs review</span></div><p class="caption">The uploaded Flow source needs a replacement or approval before final export.</p><button class="button-secondary" data-action="select-scene" data-scene-id="scene_11" data-nav="scenes">Review scene 11</button></section>
      <section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Narration</p><h2 class="card-title">Voice timing is synced</h2></div><span class="status-tag ready">Ready</span></div><p class="caption">OmniVoice narration is using Vietnamese Documentary Male at 1.10x. A new speed will flag subtitle timing for update.</p><button class="button-secondary" data-nav="voice">Open Voice studio</button></section></div>
  </section>`;
}

function renderImport() {
  const total = state.sceneState.items.length;
  return `<section class="screen">${screenHeader("Import Google Flow source", "Bring in a Google Flow ZIP or a folder. This prototype detects Scene_<number>, sorts numerically, and reports source health.", `<button class="button-secondary" data-action="mock-import">Run import mock</button>`)}
    <div class="import-dropzone" id="dropzone"><div><div class="drop-icon">⇩</div><h2>DROP GOOGLE FLOW ZIP HERE</h2><p class="caption">ZIP is parsed locally in the future app. No cloud upload is implied.</p><div class="drop-actions"><button class="button" data-action="choose-zip">Choose ZIP</button><button class="button-secondary" data-action="choose-folder">Choose Folder</button></div></div></div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Dynamic scene count</p><h2 class="card-title">Simulate source sizes before building backend</h2></div></div><div class="simulator-row"><button class="chip-button" data-action="simulate-scenes" data-count="5">Simulate 5 Scenes</button><button class="chip-button active" data-action="simulate-scenes" data-count="14">Simulate 14 Scenes</button><button class="chip-button" data-action="simulate-scenes" data-count="24">Simulate 24 Scenes</button></div></section>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Last mock import</p><h2 class="card-title">Scene_<number> files sorted numerically</h2></div><span class="status-tag ready">Mapped</span></div><div class="upload-report"><div class="report-cell"><b>${total}</b><span>Videos detected</span></div><div class="report-cell"><b>${Math.max(0, total - 1)}</b><span>Mapped</span></div><div class="report-cell"><b>1</b><span>Duplicates</span></div><div class="report-cell"><b>1</b><span>Missing</span></div><div class="report-cell"><b>0</b><span>Invalid</span></div></div></section>
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
  return `<section class="screen">${screenHeader("Review scenes", `${state.sceneState.items.length} scene cards are rendered from dynamic state. Select one to expose focused source, video, audio, and voice controls in the inspector.`, `<button class="button-secondary" data-action="approve-all">Approve visible</button><button class="button" data-nav="voice">Continue to Voice</button>`)}
    <div class="scene-grid">${state.sceneState.items.map(sceneCard).join("")}</div>
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
  return `<section class="screen">${screenHeader("Render & final review", "Choose a low-cost preview first. Final export remains a separate decision after you review the vertical player.", `<button class="button-secondary" data-action="start-render" data-quality="preview">Render Preview</button><button class="button" data-action="start-render" data-quality="final">Render Final</button>`)}
    <div class="render-layout"><section class="card card-pad"><p class="eyebrow">Final player</p><div class="video-player"><span class="player-play">▶</span></div><div style="display:flex;justify-content:space-between;margin-top:12px"><span class="caption">9:16 · 1080 × 1920 · 30fps · H.264</span><div><button class="button-secondary" data-action="approve-export">Approve & Export</button><button class="button-quiet" data-action="request-changes">Request Changes</button></div></div></section><section class="card card-pad"><div class="card-head"><div><p class="eyebrow">Render progress</p><h2 class="card-title">${render.status}</h2></div><span class="caption">${render.progress}%</span></div><div class="progress-track"><i style="width:${render.progress}%"></i></div><div class="progress-steps">${steps.map((step, index) => `<div class="progress-step ${index < render.activeStep ? "done" : index === render.activeStep ? "active" : ""}"><span class="progress-dot">${index < render.activeStep ? "✓" : index + 1}</span><div><b>${step}</b><span>${index < render.activeStep ? "Done" : index === render.activeStep ? "Working…" : "Waiting"}</span></div><span class="tiny subtle">${index === 1 ? "Voice" : index === 4 ? "Remotion" : index === 5 ? "FFmpeg" : ""}</span></div>`).join("")}</div></section></div>
    <section class="card card-pad" style="margin-top:16px"><div class="card-head"><div><p class="eyebrow">Request changes</p><h2 class="card-title">Send a precise revision back through the project</h2></div></div><div class="form-row three"><div><label class="field-label">Scene</label><select class="select-input" data-setting="request-scene">${optionList(state.sceneState.items.map(scene => ({ id: scene.id, label: `Scene ${String(scene.number).padStart(2, "0")} · ${scene.title}` })), render.requestScene)}</select></div><div><label class="field-label">Change type</label><select class="select-input" data-setting="request-category">${optionList(["Source", "Trim", "Speed", "Crop", "Audio", "Transition", "Subtitle", "Voice Timing", "Voice Override"], render.requestCategory)}</select></div><div><label class="field-label">Action</label><button class="button-secondary" style="width:100%" data-action="apply-changes">Apply Changes</button></div></div><textarea id="change-comment" class="textarea-input compact-textarea" style="margin-top:10px" placeholder="Describe the correction for this scene…"></textarea></section>
  </section>`;
}

function renderSettings() {
  return `<section class="screen">${screenHeader("Settings", "Prototype workspace settings. Provider integrations, filesystem paths, and rendering jobs are intentionally not wired here.")}
    <div class="grid two"><section class="card card-pad"><p class="eyebrow">Project</p><div class="form-stack"><div><label class="field-label">Project status</label><select class="select-input"><option>UPLOADED</option><option>MAPPED</option><option>READY</option><option>RENDERING</option><option>REVIEW</option><option>APPROVED</option><option>NEEDS_CHANGES</option><option>DONE</option></select></div><p class="caption">The future desktop app maps this state to the existing project workflow instead of replacing it.</p></div></section><section class="card card-pad"><p class="eyebrow">Prototype boundary</p><h2 class="card-title">No backend connection</h2><p class="caption">All imports, scripts, previews, voice settings, renders, and exports in this prototype are in-memory UI interactions. OmniVoice is shown as the active engine only; VoiceStudio is intentionally absent.</p></section></div></section>`;
}

function renderScreen() {
  const root = $("#screen-root");
  const screens = { dashboard: renderDashboard, import: renderImport, script: renderScript, scenes: renderScenes, voice: renderVoice, subtitles: renderSubtitles, audio: renderAudio, render: renderRender, settings: renderSettings };
  root.innerHTML = (screens[state.uiState.screen] || renderDashboard)();
  const title = NAVIGATION.find(item => item[0] === state.uiState.screen)?.[2] || "Dashboard";
  $("#screen-title").textContent = title;
  renderNavigation();
  renderInspector();
  renderTimeline();
}

function renderInspector() {
  const scene = currentScene();
  const inspector = $("#inspector");
  if (!scene || state.uiState.screen === "voice") {
    inspector.innerHTML = `<div class="inspector-head"><h2>Inspector</h2><span class="caption">Project</span></div><div class="inspector-empty"><div><p class="eyebrow">Progressive disclosure</p><b>${state.uiState.screen === "voice" ? "Voice has its own full workspace" : "Select a scene"}</b><p>${state.uiState.screen === "voice" ? "Per-scene voice override will appear here when a future provider supports it." : "Scene-level source, trim, crop, speed, audio, transitions, and optional voice overrides live here."}</p></div></div>`;
    return;
  }
  inspector.innerHTML = `<div class="inspector-head"><h2>Scene Inspector</h2><button class="button-quiet" data-action="close-inspector">×</button></div><div class="inspector-section"><div class="inspector-scene-preview">${String(scene.number).padStart(2, "0")}</div><div class="inspector-title-row"><b>Scene ${String(scene.number).padStart(2, "0")}</b><span class="status-tag ${scene.status}">${scene.status}</span></div><p class="caption">${escapeHtml(scene.title)} · ${scene.source} · Version ${scene.sourceVersion}</p><div style="display:flex;gap:5px"><button class="button-secondary" data-action="approve-scene">Approve</button><button class="button-quiet" data-action="reject-scene">Reject</button><button class="button-quiet" data-action="replace-source">Replace</button></div></div>
    <div class="inspector-section"><h3>Video edit</h3><label class="field-label">Trim start <small>${scene.edit.trimStart.toFixed(1)}s</small></label><input type="range" min="0" max="${Math.max(1, scene.duration - .5)}" step=".1" value="${scene.edit.trimStart}" data-scene-setting="trimStart" /><label class="field-label" style="margin-top:10px">Playback speed <small>${scene.edit.speed.toFixed(2)}x</small></label><select class="select-input" data-scene-setting="speed">${optionList([.5,.75,1,1.1,1.25,1.5,2], scene.edit.speed)}</select><div class="form-row" style="margin-top:10px"><div><label class="field-label">Crop</label><select class="select-input" data-scene-setting="crop">${optionList(["cover", "contain", "custom"], scene.edit.crop)}</select></div><div><label class="field-label">Position</label><select class="select-input" data-scene-setting="position">${optionList(["center", "top", "bottom", "left", "right"], scene.edit.position)}</select></div></div><label class="field-label" style="margin-top:10px">Transition</label><select class="select-input" data-scene-setting="transition">${optionList(["none", "crossfade", "soft slide", "wipe reveal", "paper"], scene.edit.transition)}</select><div class="toggle-row"><span>Hold last frame</span><button class="switch ${scene.edit.holdLastFrame ? "on" : ""}" data-action="toggle-hold"></button></div></div>
    <div class="inspector-section"><h3>Source audio</h3><label class="field-label">Mode</label><select class="select-input" data-audio-setting="mode">${optionList(["mute", "background", "full"], scene.sourceAudio.mode)}</select><label class="field-label" style="margin-top:10px">Volume <small>${scene.sourceAudio.volume}%</small></label><input type="range" min="0" max="100" value="${scene.sourceAudio.volume}" data-audio-setting="volume" /><div class="toggle-row"><span>Duck under narration</span><button class="switch ${scene.sourceAudio.duck ? "on" : ""}" data-action="toggle-duck"></button></div><div class="form-row"><div><label class="field-label">Fade In</label><input class="number-input" type="number" step=".05" value="${scene.sourceAudio.fadeIn}" data-audio-setting="fadeIn" /></div><div><label class="field-label">Fade Out</label><input class="number-input" type="number" step=".05" value="${scene.sourceAudio.fadeOut}" data-audio-setting="fadeOut" /></div></div></div>
    <div class="inspector-section"><h3>Voice override</h3><div class="toggle-row"><span>Use project default</span><button class="switch ${scene.voiceOverride ? "" : "on"}" data-action="toggle-voice-override"></button></div>${scene.voiceOverride ? `<div class="form-stack"><select class="select-input"><option>Vietnamese</option><option>English</option></select><select class="select-input"><option>Vietnamese Documentary Male</option><option>Vietnamese Documentary Female</option></select><select class="select-input"><option>1.10x</option><option>1.12x</option></select></div>` : `<p class="caption">Overrides are intentionally collapsed until needed.</p>`}</div>`;
}

function renderTimeline() {
  $("#timeline-summary").textContent = `${state.sceneState.items.length} scenes · ${formatTime(projectDuration())}`;
  $("#timeline-zoom").textContent = `${Math.round(state.sceneState.timelineZoom * 100)}%`;
  $("#timeline").innerHTML = state.sceneState.items.map(scene => `<button class="timeline-scene ${scene.status} ${scene.id === state.sceneState.selectedId ? "selected" : ""}" type="button" data-action="select-scene" data-scene-id="${scene.id}" style="min-width:${Math.max(45, scene.duration * 9 * state.sceneState.timelineZoom)}px"><span>${String(scene.number).padStart(2, "0")}</span><i class="timeline-status"></i><span>${scene.duration}s</span></button>`).join("");
}

function setScreen(screen) { state.uiState.screen = screen; renderScreen(); }
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

function mockImport() { toast(`Mock import complete: ${state.sceneState.items.length} scenes detected and numerically sorted.`); savePulse("Import mock saved"); }
function simulateScenes(count) { state.sceneState.items = makeScenes(count); state.sceneState.sceneCount = count; state.sceneState.selectedId = state.sceneState.items[0].id; state.scriptState.mapped = Math.min(2, count); state.scriptState.missing = Math.max(0, count - state.scriptState.mapped); toast(`Prototype now renders ${count} scenes.`); savePulse(); renderScreen(); }
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
    case "select-scene": selectScene(target.dataset.sceneId); break;
    case "simulate-scenes": simulateScenes(Number(target.dataset.count)); break;
    case "mock-import": case "choose-zip": case "choose-folder": mockImport(); break;
    case "parse-script": parseScript(); break;
    case "approve-scene": currentScene().status = "approved"; toast("Scene approved."); savePulse(); renderScreen(); break;
    case "reject-scene": currentScene().status = "rejected"; toast("Scene marked for replacement.", "warning"); savePulse(); renderScreen(); break;
    case "approve-all": state.sceneState.items.forEach(scene => { if (scene.status === "pending") scene.status = "approved"; }); toast("Visible pending scenes approved."); renderScreen(); break;
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
    case "open-project-menu": toast("Project switcher is a desktop-shell mock."); break;
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
  if (target.dataset.sceneSetting) { const key = target.dataset.sceneSetting; currentScene().edit[key] = key === "speed" || key === "trimStart" ? Number(target.value) : target.value; renderInspector(); renderTimeline(); }
  if (target.dataset.audioSetting) { const key = target.dataset.audioSetting; currentScene().sourceAudio[key] = ["volume", "fadeIn", "fadeOut"].includes(key) ? Number(target.value) : target.value; renderInspector(); }
});

document.addEventListener("dragover", event => { if (event.target.closest("#dropzone")) { event.preventDefault(); $("#dropzone")?.classList.add("dragging"); } });
document.addEventListener("dragleave", event => { if (event.target.closest("#dropzone")) $("#dropzone")?.classList.remove("dragging"); });
document.addEventListener("drop", event => { if (event.target.closest("#dropzone")) { event.preventDefault(); $("#dropzone")?.classList.remove("dragging"); mockImport(); } });

renderScreen();
