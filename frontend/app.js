"use strict";

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
// Typographic status marks (colored by state in CSS) — deliberately not emoji.
const ICON = { pass: "✓", fail: "✕", warn: "!", unreadable: "!" };
const EXPECTED_FIELDS = [
  "brand_name", "class_type", "alcohol_content",
  "net_contents", "producer", "country_of_origin",
];

function show(el, on = true) { el.hidden = !on; }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---------- tabs ----------
function activateTab(which) {
  const single = which === "single";
  $("tab-single").classList.toggle("is-active", single);
  $("tab-batch").classList.toggle("is-active", !single);
  $("tab-single").setAttribute("aria-selected", String(single));
  $("tab-batch").setAttribute("aria-selected", String(!single));
  show($("panel-single"), single);
  show($("panel-batch"), !single);
}
$("tab-single").addEventListener("click", () => activateTab("single"));
$("tab-batch").addEventListener("click", () => activateTab("batch"));

// ---------- mode toggle ----------
let mode = "rules";
document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    mode = radio.value;
    document.querySelectorAll(".mode-option").forEach((opt) =>
      opt.classList.toggle("is-active", opt.contains(radio)));
    const compare = mode === "compare";
    show($("expected-step"), compare);
    $("upload-num").textContent = compare ? "3" : "2";
  });
});

// ---------- single upload ----------
let singleFile = null;
const dz = $("dropzone");
const fileInput = $("file-single");

function setSingleFile(file) {
  singleFile = file || null;
  const preview = $("preview");
  if (singleFile) {
    preview.src = URL.createObjectURL(singleFile);
    show(preview, true);
    show($("dropzone-empty"), false);
  } else {
    show(preview, false);
    show($("dropzone-empty"), true);
  }
  $("verify-btn").disabled = !singleFile;
}

dz.addEventListener("click", () => fileInput.click());
dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
fileInput.addEventListener("change", () => setSingleFile(fileInput.files[0]));
wireDrop(dz, (files) => { if (files[0]) setSingleFile(files[0]); });

$("verify-btn").addEventListener("click", runSingle);

async function runSingle() {
  const statusEl = $("single-status");
  const resultEl = $("single-result");
  show(resultEl, false);
  statusEl.className = "status";
  statusEl.textContent = "Checking the label…";
  show(statusEl, true);
  $("verify-btn").disabled = true;

  const form = new FormData();
  form.append("image", singleFile);
  form.append("mode", mode);
  if (mode === "compare") {
    for (const f of EXPECTED_FIELDS) {
      const v = $(`exp-${f}`).value.trim();
      if (v) form.append(f, v);
    }
  }

  try {
    const res = await fetch("/api/verify", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    const verdict = await res.json();
    show(statusEl, false);
    renderVerdict(resultEl, verdict);
    show(resultEl, true);
  } catch (err) {
    statusEl.className = "status error";
    statusEl.textContent = "Something went wrong: " + err.message;
  } finally {
    $("verify-btn").disabled = false;
  }
}

// ---------- batch upload ----------
let batchFiles = [];
const dzBatch = $("dropzone-batch");
const fileBatch = $("file-batch");

function setBatchFiles(list) {
  batchFiles = Array.from(list || []);
  $("batch-count-text").textContent = batchFiles.length
    ? `${batchFiles.length} photo${batchFiles.length === 1 ? "" : "s"} ready — click "Check all labels"`
    : "Click to choose photos, or drag them here";
  $("verify-batch-btn").disabled = batchFiles.length === 0;
}

dzBatch.addEventListener("click", () => fileBatch.click());
dzBatch.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") fileBatch.click(); });
fileBatch.addEventListener("change", () => setBatchFiles(fileBatch.files));
wireDrop(dzBatch, setBatchFiles);

// optional application manifest
const fileManifest = $("file-manifest");
fileManifest.addEventListener("change", () => {
  const f = fileManifest.files[0];
  $("manifest-name").textContent = f ? f.name : "No CSV chosen";
});

$("verify-batch-btn").addEventListener("click", runBatch);

async function runBatch() {
  const statusEl = $("batch-status");
  show($("batch-result"), false);
  show($("batch-summary"), false);
  statusEl.className = "status";
  statusEl.textContent = `Checking ${batchFiles.length} labels… this can take a moment.`;
  show(statusEl, true);
  $("verify-batch-btn").disabled = true;

  const form = new FormData();
  batchFiles.forEach((f) => form.append("images", f));
  form.append("mode", "rules");
  if (fileManifest.files[0]) form.append("manifest", fileManifest.files[0]);

  try {
    const res = await fetch("/api/verify-batch", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    const data = await res.json();
    show(statusEl, false);
    renderBatch(data);
  } catch (err) {
    statusEl.className = "status error";
    statusEl.textContent = "Something went wrong: " + err.message;
  } finally {
    $("verify-batch-btn").disabled = false;
  }
}

// ---------- rendering ----------
function renderVerdict(container, v) {
  let html = "";
  const bannerText = {
    pass: "PASS — label looks compliant",
    fail: "NEEDS REVIEW — issues found",
    unreadable: "Couldn't read this image",
  }[v.overall];
  html += `<div class="verdict-banner ${v.overall}">${bannerText}` +
    (v.elapsed_ms ? `<span class="elapsed">checked in ${(v.elapsed_ms / 1000).toFixed(1)}s</span>` : "") +
    `</div>`;

  if (v.overall === "unreadable") {
    html += `<div class="check warn"><span class="icon">!</span><div>` +
      `<div class="field-name">Please resubmit a clearer photo</div>` +
      `<div class="reason">${esc(v.error || "The label text could not be read.")}</div></div></div>`;
    container.innerHTML = html;
    return;
  }

  if (v.quality_note) {
    html += `<div class="quality-note"><b>Image quality:</b> ${esc(v.quality_note)}</div>`;
  }
  if (v.crosscheck_note) {
    html += `<div class="crosscheck-note"><b>Independent check:</b> ${esc(v.crosscheck_note)}</div>`;
  }

  for (const c of v.checks) {
    html += `<div class="check ${c.status}"><span class="icon">${ICON[c.status]}</span><div>` +
      `<div class="field-name">${esc(c.label)}</div>` +
      `<div class="reason">${esc(c.reason)}</div>`;
    if (c.expected != null || c.found != null) {
      html += `<div class="detail">`;
      if (c.expected != null) html += `Application: <b>${esc(c.expected)}</b>. `;
      if (c.found != null) html += `Label: <b>${esc(c.found)}</b>.`;
      html += `</div>`;
    }
    html += `</div></div>`;
  }
  container.innerHTML = html;
}

let batchRows = [];
const RESULT_LABEL = { pass: "Pass", fail: "Review", unreadable: "Unreadable" };
const modeLabel = (m) => (m === "compare" ? "vs application" : "completeness");

function renderBatch(data) {
  $("batch-summary").innerHTML =
    pill("pass", "Passed", data.passed) +
    pill("fail", "Need review", data.failed) +
    pill("unreadable", "Unreadable", data.unreadable);
  show($("batch-summary"), true);

  batchRows = data.results.map((r) => ({
    filename: r.filename,
    overall: r.verdict.overall,
    mode: r.verdict.mode,
    // Actionable items: failures plus prominence/quality warnings.
    issues: (r.verdict.checks || [])
      .filter((c) => c.status === "fail" || c.status === "warn")
      .map((c) => `${c.label}${c.status === "warn" ? " (check)" : ""}`),
  }));
  renderBatchTable("overall");
  show($("batch-toolbar"), true);
  show($("batch-result"), true);
}

function renderBatchTable(sortKey) {
  const rank = { fail: 0, unreadable: 1, pass: 2 };
  const rows = [...batchRows].sort((a, b) => {
    if (sortKey === "filename") return a.filename.localeCompare(b.filename);
    return rank[a.overall] - rank[b.overall];
  });
  let html = `<table class="batch-table"><thead><tr>` +
    `<th data-sort="filename">File</th><th data-sort="overall">Result</th>` +
    `<th>Checked as</th><th>Issues</th>` +
    `</tr></thead><tbody>`;
  for (const r of rows) {
    html += `<tr><td>${esc(r.filename)}</td>` +
      `<td><span class="pill ${r.overall}">${RESULT_LABEL[r.overall]}</span></td>` +
      `<td>${modeLabel(r.mode)}</td>` +
      `<td>${r.issues.length ? esc(r.issues.join(", ")) : "—"}</td></tr>`;
  }
  html += `</tbody></table>`;
  $("batch-result").innerHTML = html;
  $("batch-result").querySelectorAll("th[data-sort]").forEach((th) =>
    th.addEventListener("click", () => renderBatchTable(th.dataset.sort)));
}

function pill(cls, label, n) {
  return `<div class="summary-pill ${cls}"><span class="big">${n}</span>${label}</div>`;
}

// ---------- export ----------
function csvCell(v) {
  const s = String(v == null ? "" : v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

$("download-csv").addEventListener("click", () => {
  const lines = [["filename", "result", "checked_as", "issues"].join(",")];
  for (const r of batchRows) {
    lines.push([r.filename, RESULT_LABEL[r.overall], modeLabel(r.mode), r.issues.join("; ")]
      .map(csvCell).join(","));
  }
  const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "label-check-results.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

$("print-results").addEventListener("click", () => window.print());

// ---------- drag & drop ----------
function wireDrop(zone, onFiles) {
  ["dragenter", "dragover"].forEach((ev) =>
    zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
  zone.addEventListener("drop", (e) => {
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) onFiles(files);
  });
}

// ---------- backend note ----------
fetch("/api/health").then((r) => r.json()).then((h) => {
  $("backend-note").textContent = h.extraction_backend === "tesseract"
    ? "Local OCR mode. " : "";
}).catch(() => {});
