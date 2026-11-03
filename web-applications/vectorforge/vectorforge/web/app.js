// Vectorforge web app: upload, progress, compare viewer, refine panel, download.

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const DEFAULTS = {
  "processing.max_colors": 0,
  "processing.palette": "",
  "processing.image_type": "auto",
  "processing.detail": "medium",
  "processing.background.remove": false,
  "processing.parameterized_shapes.enabled": true,
  "processing.corner_threshold": 50,
  "processing.fit_tolerance": 0,
  "output.shape_stacking": "cutouts",
};
const OUT_DEFAULTS = {
  "output.file_format": "svg",
  "output.draw_style": "fill_shapes",
  "output.group_by": "none",
  "output.gap_filler.enabled": true,
  "output.dxf.compatibility_level": "lines_and_arcs",
  "output.size.width": "",
  "output.size.unit": "none",
};
const STAGES = {
  queued: "Waiting for a worker",
  decoding: "Reading the image",
  palette: "Picking colors",
  segmenting: "Separating regions",
  tracing: "Fitting shapes and curves",
  done: "Done",
};

const state = {
  token: null,
  file: null,
  srcUrl: null,
  imgW: 0,
  imgH: 0,
  opts: { ...DEFAULTS },
  out: { ...OUT_DEFAULTS },
  palette: [],
  history: [],
  future: [],
  view: "compare",
  zoom: 1,
  tx: 0,
  ty: 0,
  split: 0.5,
  es: null,
  pending: null,
};

// ---------------------------------------------------------------- utilities
function toast(msg, isError = false, ms = 4200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.hidden = false;
  clearTimeout(toast._h);
  toast._h = setTimeout(() => (t.hidden = true), ms);
}

function setBusy(label, frac) {
  const b = $("#busy");
  if (label == null) { b.hidden = true; return; }
  b.hidden = false;
  $("#busyLabel").textContent = label;
  $("#meterFill").style.width = `${Math.round((frac || 0) * 100)}%`;
}

function errorText(payload, fallback) {
  const e = payload && (payload.error || payload);
  return (e && e.message) || fallback;
}

// ---------------------------------------------------------------- upload
function acceptFile(file) {
  if (!file) return;
  if (!/^image\//.test(file.type) && !/\.(png|jpe?g|gif|bmp|webp|tiff?)$/i.test(file.name)) {
    toast("That file isn't an image. Choose a PNG, JPG, GIF, BMP, WebP or TIFF file.", true);
    return;
  }
  if (file.size > 30 * 1024 * 1024) {
    toast("That image is larger than 30 MB. Shrink it and try again.", true);
    return;
  }
  state.file = file;
  if (state.srcUrl) URL.revokeObjectURL(state.srcUrl);
  state.srcUrl = URL.createObjectURL(file);
  startJob({ file, name: file.name });
}

function startJob({ file, url, name }) {
  resetSession();
  showViewer(name || "image");
  const fd = new FormData();
  if (file) fd.append("image", file, file.name);
  if (url) fd.append("image.url", url);
  fd.append("options", JSON.stringify(state.opts));
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/jobs");
  xhr.upload.onprogress = (e) => e.lengthComputable && setBusy("Uploading", (e.loaded / e.total) * 0.3);
  xhr.onerror = () => failToEmpty("The upload failed. Check your connection and try again.");
  xhr.onload = () => {
    let body = {};
    try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
    if (xhr.status >= 300) return failToEmpty(errorText(body, `Upload failed (HTTP ${xhr.status}).`));
    state.token = body.token;
    if (!file) state.srcUrl = `/api/jobs/${body.token}/source`;
    loadSource().then(() => listen());
  };
  setBusy("Uploading", 0);
  xhr.send(fd);
}

function loadSource() {
  return new Promise((resolve) => {
    const img = $("#srcImg");
    img.onload = () => {
      state.imgW = img.naturalWidth;
      state.imgH = img.naturalHeight;
      $("#fileMeta").textContent = `${state.imgW} × ${state.imgH} px`;
      fit();
      resolve();
    };
    img.onerror = () => resolve(); // e.g. TIFF the browser can't show; vector still loads
    img.src = state.srcUrl;
  });
}

function listen() {
  if (state.es) state.es.close();
  const es = new EventSource(`/api/jobs/${state.token}/events`);
  state.es = es;
  es.addEventListener("progress", (e) => {
    const d = JSON.parse(e.data);
    setBusy(STAGES[d.stage] || "Working", 0.3 + d.progress * 0.7);
  });
  es.addEventListener("done", (e) => {
    es.close();
    onResult(JSON.parse(e.data));
  });
  es.addEventListener("error", (e) => {
    es.close();
    if (e.data) {
      const d = JSON.parse(e.data);
      setBusy(null);
      toast(errorText(d, "Vectorizing failed."), true);
    } else if (!state.palette.length) {
      setTimeout(pollOnce, 600); // connection dropped: fall back to polling
    }
  });
}

async function pollOnce() {
  const r = await fetch(`/api/jobs/${state.token}`);
  const d = await r.json();
  if (d.status === "done") onResult(d);
  else if (d.status === "error") { setBusy(null); toast(errorText(d, "Vectorizing failed."), true); }
  else { setBusy(STAGES[d.stage] || "Working", 0.3 + d.progress * 0.7); setTimeout(pollOnce, 500); }
}

async function onResult(summary) {
  setBusy("Drawing the result", 0.98);
  const r = await fetch(`/api/jobs/${state.token}/result?output.file_format=svg&output.draw_style=fill_shapes&output.gap_filler.enabled=true`);
  if (!r.ok) {
    setBusy(null);
    let b = {};
    try { b = await r.json(); } catch { /* ignore */ }
    return toast(errorText(b, "Could not load the result."), true);
  }
  const svgText = await r.text();
  const layer = $("#vecLayer");
  layer.innerHTML = svgText.replace(/^<\?xml[^>]*>\s*/, "");
  const svg = layer.querySelector("svg");
  if (svg) svg.setAttribute("preserveAspectRatio", "none");
  if (!state.imgW) { state.imgW = summary.width; state.imgH = summary.height; fit(); }
  state.palette = summary.palette || [];
  renderPalette();
  renderStats(summary.stats, svgText.length);
  updateDownload();
  setBusy(null);
  applyTransform();
}

function failToEmpty(msg) {
  setBusy(null);
  toast(msg, true, 6000);
  showEmpty();
}

// ---------------------------------------------------------------- re-processing
function commit(patch, { record = true } = {}) {
  if (record) { state.history.push({ ...state.opts }); state.future = []; }
  Object.assign(state.opts, patch);
  syncControls();
  clearTimeout(state.pending);
  state.pending = setTimeout(reprocess, 280);
}

async function reprocess() {
  if (!state.token) return;
  setBusy("Re-processing", 0.3);
  const r = await fetch(`/api/jobs/${state.token}/reprocess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.opts),
  });
  if (!r.ok) {
    let b = {};
    try { b = await r.json(); } catch { /* ignore */ }
    setBusy(null);
    return toast(errorText(b, "Could not apply that change."), true);
  }
  listen();
}

function undo() {
  if (!state.history.length) return;
  state.future.push({ ...state.opts });
  state.opts = state.history.pop();
  commit({}, { record: false });
}
function redo() {
  if (!state.future.length) return;
  state.history.push({ ...state.opts });
  state.opts = state.future.pop();
  commit({}, { record: false });
}

// ---------------------------------------------------------------- palette
function paletteString(edits) {
  return state.palette
    .map((p, i) => {
      const e = edits[i] || {};
      const color = "color" in e ? e.color : p.color;
      return `${p.source} -> ${color === null ? "none" : color};`;
    })
    .join(" ");
}

function renderPalette() {
  const ul = $("#swatches");
  ul.innerHTML = "";
  state.palette.forEach((p, i) => {
    const li = document.createElement("li");
    li.className = "swatch" + (p.color === null ? " off" : "");
    const shown = p.color || p.source;
    const pct = (p.coverage * 100).toFixed(p.coverage < 0.01 ? 2 : 1);
    li.innerHTML = `
      <label style="background:${shown}" title="Change color"><input type="color" value="${shown}" aria-label="Change color ${shown}"></label>
      <span class="hex"><span>${shown}</span><small>${pct}%</small></span>
      <button type="button" aria-label="${p.color === null ? "Show" : "Make transparent"} ${shown}" title="${p.color === null ? "Show color" : "Make transparent"}">
        ${p.color === null
          ? '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 3l18 18M10.6 6.2A10 10 0 0 1 12 6c5 0 9 6 9 6a17 17 0 0 1-3.2 3.7M6.3 7.8A17 17 0 0 0 3 12s4 6 9 6a9 9 0 0 0 3.4-.7"/></svg>'
          : '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12s4-6 9-6 9 6 9 6-4 6-9 6-9-6-9-6z"/><circle cx="12" cy="12" r="2.6"/></svg>'}
      </button>`;
    li.querySelector("input").addEventListener("change", (e) => {
      commit({ "processing.palette": paletteString({ [i]: { color: e.target.value } }) });
    });
    li.querySelector("button").addEventListener("click", () => {
      commit({ "processing.palette": paletteString({ [i]: { color: p.color === null ? p.source : null } }) });
    });
    ul.appendChild(li);
  });
}

function renderStats(st, bytes) {
  if (!st) return;
  const prims = Object.values(st.primitives || {}).reduce((a, b) => a + b, 0);
  const kb = bytes / 1024;
  $("#stats").textContent =
    `${st.shapes} shapes, ${st.nodes} curve segments, ${prims} fitted whole shapes, ` +
    `${st.colors} colors. Processed as ${st.image_type === "art" ? "artwork" : "a photo"} in ` +
    `${st.timings_s.total.toFixed(1)} s. Preview SVG ${kb < 1024 ? kb.toFixed(0) + " KB" : (kb / 1024).toFixed(1) + " MB"}.`;
}

// ---------------------------------------------------------------- controls
function syncControls() {
  const o = state.opts;
  const n = o["processing.max_colors"];
  $("#colorCount").value = n;
  $("#colorCountOut").textContent = n ? String(n) : "Auto";
  $$(".seg[data-opt]").forEach((seg) => {
    const v = o[seg.dataset.opt];
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.val === v));
  });
  $$("input[type=checkbox][data-opt]").forEach((c) => (c.checked = !!o[c.dataset.opt]));
  $("#corner").value = o["processing.corner_threshold"];
  $("#cornerOut").textContent = `${o["processing.corner_threshold"]}°`;
  $("#tol").value = o["processing.fit_tolerance"];
  $("#tolOut").textContent = o["processing.fit_tolerance"] ? `${(+o["processing.fit_tolerance"]).toFixed(2)} px` : "Auto";
  $("#undoBtn").disabled = !state.history.length;
  $("#redoBtn").disabled = !state.future.length;
  // output controls
  const out = state.out;
  $$(".seg[data-out]").forEach((seg) => {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.val === out[seg.dataset.out]));
  });
  $$("input[type=checkbox][data-out]").forEach((c) => {
    const on = c.dataset.on;
    c.checked = on ? out[c.dataset.out] === on : !!out[c.dataset.out];
  });
  $$("select[data-out], input[type=number][data-out]").forEach((el) => (el.value = out[el.dataset.out]));
  $$("#formats button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.fmt === out["output.file_format"])));
  $("#dxfField").hidden = out["output.file_format"] !== "dxf";
  updateDownload();
}

function updateDownload() {
  const a = $("#downloadBtn");
  const fmt = state.out["output.file_format"];
  a.textContent = `Download ${fmt.toUpperCase()}`;
  if (!state.token) { a.setAttribute("aria-disabled", "true"); return; }
  const q = new URLSearchParams({ download: "1" });
  for (const [k, v] of Object.entries(state.out)) if (v !== "" && v != null) q.set(k, v);
  a.href = `/api/jobs/${state.token}/result?${q}`;
  a.removeAttribute("aria-disabled");
}

function bindControls() {
  $("#colorCount").addEventListener("input", (e) => ($("#colorCountOut").textContent = +e.target.value ? e.target.value : "Auto"));
  $("#colorCount").addEventListener("change", (e) => commit({ "processing.max_colors": +e.target.value, "processing.palette": "" }));
  $$(".seg[data-opt]").forEach((seg) =>
    seg.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || state.opts[seg.dataset.opt] === b.dataset.val) return;
      const patch = { [seg.dataset.opt]: b.dataset.val };
      if (seg.dataset.opt !== "output.shape_stacking") patch["processing.palette"] = "";
      commit(patch);
    }));
  $$("input[type=checkbox][data-opt]").forEach((c) => c.addEventListener("change", () => commit({ [c.dataset.opt]: c.checked })));
  $("#corner").addEventListener("input", (e) => ($("#cornerOut").textContent = `${e.target.value}°`));
  $("#corner").addEventListener("change", (e) => commit({ "processing.corner_threshold": +e.target.value }));
  $("#tol").addEventListener("input", (e) => ($("#tolOut").textContent = +e.target.value ? `${(+e.target.value).toFixed(2)} px` : "Auto"));
  $("#tol").addEventListener("change", (e) => commit({ "processing.fit_tolerance": +e.target.value }));
  $("#undoBtn").addEventListener("click", undo);
  $("#redoBtn").addEventListener("click", redo);
  $("#resetBtn").addEventListener("click", () => commit({ ...DEFAULTS }));

  $$(".seg[data-out]").forEach((seg) =>
    seg.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (b) { state.out[seg.dataset.out] = b.dataset.val; syncControls(); }
    }));
  $$("input[type=checkbox][data-out]").forEach((c) =>
    c.addEventListener("change", () => {
      state.out[c.dataset.out] = c.dataset.on ? (c.checked ? c.dataset.on : c.dataset.off) : c.checked;
      syncControls();
    }));
  $$("select[data-out], input[type=number][data-out]").forEach((el) =>
    el.addEventListener("change", () => { state.out[el.dataset.out] = el.value; syncControls(); }));
  $("#formats").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) { state.out["output.file_format"] = b.dataset.fmt; syncControls(); }
  });
  $("#downloadBtn").addEventListener("click", (e) => {
    if (!state.token) e.preventDefault();
    else toast(`Preparing your ${state.out["output.file_format"].toUpperCase()} file`, false, 2000);
  });
}

// ---------------------------------------------------------------- viewer
function setView(v) {
  state.view = v;
  $("#viewer").dataset.view = v;
  $$(".view-tools [data-view]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === v)));
  $("#split").hidden = v !== "compare";
  applyTransform();
}

function fit() {
  const vw = $("#viewer").clientWidth, vh = $("#viewer").clientHeight;
  if (!state.imgW || !vw) return;
  const pad = Math.min(48, vw * 0.05);
  const tools = $("#viewTools").offsetHeight + 24;
  state.zoom = Math.min((vw - pad * 2) / state.imgW, (vh - pad - tools) / state.imgH, 8);
  state.tx = (vw - state.imgW * state.zoom) / 2;
  state.ty = Math.max(pad / 2, (vh - tools - state.imgH * state.zoom) / 2);
  applyTransform();
}

function zoomAt(f, cx, cy) {
  const z = Math.min(64, Math.max(0.05, state.zoom * f));
  const k = z / state.zoom;
  state.tx = cx - (cx - state.tx) * k;
  state.ty = cy - (cy - state.ty) * k;
  state.zoom = z;
  applyTransform();
}

function applyTransform() {
  const st = $("#stage");
  const w = state.imgW * state.zoom, h = state.imgH * state.zoom;
  st.style.width = `${w}px`;
  st.style.height = `${h}px`;
  st.style.transform = `translate(${state.tx}px, ${state.ty}px)`;
  st.classList.toggle("pixelated", state.zoom >= 3);
  $("#zoomVal").textContent = `${Math.round(state.zoom * 100)}%`;
  const viewer = $("#viewer");
  const sx = state.split * viewer.clientWidth;
  $("#split").style.left = `${sx}px`;
  const layer = $("#vecLayer");
  layer.style.clipPath = state.view === "compare" ? `inset(0 0 0 ${Math.max(0, sx - state.tx)}px)` : "none";
}

function bindViewer() {
  const viewer = $("#viewer");
  $$(".view-tools [data-view]").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  $("#zoomIn").addEventListener("click", () => zoomAt(1.25, viewer.clientWidth / 2, viewer.clientHeight / 2));
  $("#zoomOut").addEventListener("click", () => zoomAt(0.8, viewer.clientWidth / 2, viewer.clientHeight / 2));
  $("#zoomFit").addEventListener("click", fit);
  viewer.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = viewer.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0018)), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  let drag = null;
  viewer.addEventListener("pointerdown", (e) => {
    const onHandle = e.target.closest("#splitHandle") || e.target.closest("#split");
    drag = { x: e.clientX, y: e.clientY, tx: state.tx, ty: state.ty, split: onHandle };
    viewer.setPointerCapture(e.pointerId);
    if (!onHandle) viewer.classList.add("panning");
  });
  viewer.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (drag.split) {
      const r = viewer.getBoundingClientRect();
      state.split = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    } else {
      state.tx = drag.tx + (e.clientX - drag.x);
      state.ty = drag.ty + (e.clientY - drag.y);
    }
    applyTransform();
  });
  const end = () => { drag = null; viewer.classList.remove("panning"); };
  viewer.addEventListener("pointerup", end);
  viewer.addEventListener("pointercancel", end);
  $("#splitHandle").addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") state.split = Math.max(0, state.split - 0.05);
    else if (e.key === "ArrowRight") state.split = Math.min(1, state.split + 0.05);
    else return;
    e.preventDefault();
    applyTransform();
  });
  window.addEventListener("resize", () => state.imgW && fit());
}

// ---------------------------------------------------------------- screens
function showViewer(name) {
  $("#workspace").dataset.state = "viewer";
  $("#drop").hidden = true;
  $("#viewer").hidden = false;
  $("#viewTools").hidden = false;
  $("#panel").hidden = false;
  $("#newBtn").hidden = false;
  $("#fileName").textContent = name;
  $("#fileMeta").textContent = "";
  setView("compare");
  syncControls();
}

function showEmpty() {
  $("#workspace").dataset.state = "empty";
  $("#drop").hidden = false;
  $("#viewer").hidden = true;
  $("#viewTools").hidden = true;
  $("#panel").hidden = true;
  $("#newBtn").hidden = true;
}

function resetSession() {
  if (state.es) state.es.close();
  state.token = null;
  state.palette = [];
  state.history = [];
  state.future = [];
  state.opts = { ...DEFAULTS };
  state.imgW = state.imgH = 0;
  state.split = 0.5;
  $("#vecLayer").innerHTML = "";
  $("#srcImg").removeAttribute("src");
  $("#swatches").innerHTML = "";
  $("#stats").textContent = "";
}

function bindDrop() {
  const drop = $("#drop");
  const mat = $("#mat");
  ["dragenter", "dragover"].forEach((t) => mat.addEventListener(t, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  }));
  ["dragleave", "drop"].forEach((t) => mat.addEventListener(t, (e) => {
    e.preventDefault();
    if (t === "dragleave" && mat.contains(e.relatedTarget)) return;
    drop.classList.remove("over");
  }));
  mat.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) acceptFile(f);
  });
  $("#fileInput").addEventListener("change", (e) => {
    acceptFile(e.target.files[0]);
    e.target.value = "";
  });
  $("#urlForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const url = $("#urlInput").value.trim();
    if (!/^https?:\/\//i.test(url)) return toast("Enter a full image URL starting with http:// or https://", true);
    state.file = null;
    startJob({ url, name: url.split("/").pop().split("?")[0] || "image" });
  });
  document.addEventListener("paste", (e) => {
    if (e.target.closest && e.target.closest("input")) return;
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
    if (item) {
      const f = item.getAsFile();
      acceptFile(new File([f], f.name && f.name !== "image.png" ? f.name : "pasted-image.png", { type: f.type }));
    }
  });
  $("#newBtn").addEventListener("click", () => { resetSession(); showEmpty(); });
}

bindDrop();
bindViewer();
bindControls();
syncControls();
