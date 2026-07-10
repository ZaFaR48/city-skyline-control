const api = "/api/v1";
let presets = [];
let zones = [];
let slots = [];
let selectedPreset = null;
let draftPoints = [];
let polygonClosed = false;
let cameraStatus = null;
let runtimeStatus = null;
let activeSessions = [];
let alprStatus = null;
let alprObservations = [];
let alprReview = [];

const $ = (id) => document.getElementById(id);

function logMessage(message) {
  $("messages").textContent = `${new Date().toLocaleTimeString()} ${message}\n${$("messages").textContent}`.slice(0, 5000);
}

async function request(path, options = {}) {
  const response = await fetch(`${api}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch (_) {
      // Keep status text.
    }
    throw new Error(Array.isArray(detail) ? JSON.stringify(detail) : detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function snapshotUrl(path) {
  if (!path) return "";
  return `/snapshots/${path.split(/[\\/]/).pop()}`;
}

async function loadHealth() {
  const data = await request("");
  $("status").textContent = `${data.status} ${data.version}`;
}

async function loadCameraStatus() {
  cameraStatus = await request("/camera/status");
  renderCameraStatus();
}

async function loadRuntimeStatus() {
  runtimeStatus = await request("/runtime/status");
  renderRuntimeStatus();
}

async function loadActiveSessions() {
  activeSessions = await request("/parking/sessions/active");
  renderActiveSessions();
}

async function loadAlprStatus() {
  alprStatus = await request("/alpr/status");
  alprObservations = await request("/alpr/observations");
  alprReview = await request("/alpr/review");
  renderAlpr();
}

function renderCameraStatus(extra = "") {
  if (!cameraStatus) return;
  const indicator = $("cameraIndicator");
  indicator.textContent = cameraStatus.connected ? "Connected" : cameraStatus.configured ? "Offline" : "Not configured";
  indicator.className = `status small ${cameraStatus.connected ? "ok" : "bad"}`;
  const resolution =
    cameraStatus.frame_width && cameraStatus.frame_height
      ? `${cameraStatus.frame_width} x ${cameraStatus.frame_height}`
      : "unknown";
  $("cameraDetails").innerHTML = `
    <div><strong>Name</strong><span>${cameraStatus.camera_name || "Unnamed camera"}</span></div>
    <div><strong>Vendor</strong><span>${cameraStatus.camera_vendor}</span></div>
    <div><strong>Local IP</strong><span>${cameraStatus.camera_local_ip || "not set"}</span></div>
    <div><strong>RTSP</strong><span>${cameraStatus.rtsp_url_redacted || "not configured"}</span></div>
    <div><strong>Resolution</strong><span>${resolution}</span></div>
    <div><strong>FPS</strong><span>${cameraStatus.measured_fps ?? "unknown"}</span></div>
    <div><strong>Last frame</strong><span>${cameraStatus.last_frame_at || "never"}</span></div>
    <div><strong>Failures</strong><span>${cameraStatus.failure_count}</span></div>
    <div><strong>PTZ dry-run</strong><span>${cameraStatus.ptz_dry_run ? "true" : "false"}</span></div>
    <div><strong>Error</strong><span>${cameraStatus.last_error || "none"}</span></div>
    ${extra ? `<div><strong>Result</strong><span>${extra}</span></div>` : ""}
  `;
}

function formatDateTime(value) {
  if (!value) return "unknown";
  return new Date(value).toLocaleString("en-GB", { hour12: false });
}

function durationText(startValue, endValue = null) {
  if (!startValue) return "unknown";
  const start = new Date(startValue).getTime();
  const end = endValue ? new Date(endValue).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function paymentLabel(value) {
  if (value === "not_integrated" || value === "unknown") return "not configured";
  return value;
}

function renderRuntimeStatus() {
  if (!runtimeStatus) return;
  const running = runtimeStatus.worker_process === "running" || runtimeStatus.api_embedded_worker_running;
  $("runtimeIndicator").textContent = running ? "Running" : "Stopped";
  $("runtimeIndicator").className = `status small ${running ? "ok" : "bad"}`;
  const hours = runtimeStatus.working_hours || {};
  $("runtimeSummary").innerHTML = `
    <div class="metric"><strong>Working hours</strong><span>${hours.is_working_hours ? "active" : "inactive"}</span></div>
    <div class="metric"><strong>Local time</strong><span>${formatDateTime(hours.local_time)}</span></div>
    <div class="metric"><strong>Active sessions</strong><span>${runtimeStatus.active_sessions_count}</span></div>
    <div class="metric"><strong>Free / billable</strong><span>${runtimeStatus.active_free_sessions} / ${runtimeStatus.active_billable_sessions}</span></div>
    <div class="metric"><strong>Payment</strong><span>${runtimeStatus.payment_integration_status}</span></div>
    <div class="metric"><strong>Pending review</strong><span>${runtimeStatus.pending_violation_candidates}</span></div>
    <div class="metric"><strong>PTZ dry-run</strong><span>${runtimeStatus.ptz_dry_run ? "true" : "false"}</span></div>
    <div class="metric"><strong>Heartbeat</strong><span>${formatDateTime(runtimeStatus.last_worker_heartbeat)}</span></div>
  `;
  $("paymentNotice").textContent =
    runtimeStatus.payment_integration_status === "not_integrated"
      ? "Payment integration not configured"
      : "";
}

function renderActiveSessions() {
  const body = $("activeVehiclesTable");
  body.innerHTML = "";
  if (!activeSessions.length) {
    body.innerHTML = `<tr><td colspan="7" class="muted">No active vehicles.</td></tr>`;
    return;
  }
  activeSessions.forEach((session) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${session.plate_text}</td>
      <td>${session.slot_code}</td>
      <td>${formatDateTime(session.first_seen_at_local || session.first_seen_at)}</td>
      <td>${durationText(session.first_seen_at)}</td>
      <td>${session.session_status}</td>
      <td>${Number(session.amount_tjs || 0).toFixed(2)} TJS</td>
      <td>${paymentLabel(session.payment_status)}</td>
    `;
    body.appendChild(row);
  });
}

function renderAlpr() {
  if (!alprStatus) return;
  $("alprIndicator").textContent = alprStatus.ready ? "Ready" : "Not ready";
  $("alprIndicator").className = `status small ${alprStatus.ready ? "ok" : "bad"}`;
  const latest = alprObservations[0] || {};
  $("alprSummary").innerHTML = `
    <div class="metric"><strong>Vehicle model</strong><span>${alprStatus.vehicle_model?.ready ? "ready" : "not ready"}</span></div>
    <div class="metric"><strong>OCR model</strong><span>${alprStatus.ocr_model?.ready ? "ready" : "not ready"}</span></div>
    <div class="metric"><strong>Current preset</strong><span>${alprStatus.current_preset || "not configured"}</span></div>
    <div class="metric"><strong>Latest plate</strong><span>${latest.plate_display || "none"}</span></div>
    <div class="metric"><strong>Vehicle confidence</strong><span>${latest.vehicle_confidence ?? "n/a"}</span></div>
    <div class="metric"><strong>OCR confidence</strong><span>${latest.plate_confidence ?? "n/a"}</span></div>
    <div class="metric"><strong>Slot</strong><span>${latest.slot_code || "n/a"}</span></div>
    <div class="metric"><strong>Processing ms</strong><span>${latest.processing_time_ms ? Number(latest.processing_time_ms).toFixed(1) : "n/a"}</span></div>
    <div class="metric"><strong>Accepted</strong><span>${alprStatus.metrics.accepted_observations}</span></div>
    <div class="metric"><strong>Needs review</strong><span>${alprStatus.metrics.needs_review_observations}</span></div>
    <div class="metric"><strong>Rejected</strong><span>${alprStatus.metrics.rejected_candidates}</span></div>
    <div class="metric"><strong>Warnings</strong><span>${(alprStatus.warnings || []).length}</span></div>
  `;
  renderAlprList("alprObservations", alprObservations.slice(0, 5), false);
  renderAlprList("alprReviewQueue", alprReview.slice(0, 5), true);
}

function renderAlprList(id, rows, review) {
  const list = $(id);
  list.innerHTML = "";
  if (!rows.length) {
    list.innerHTML = `<p class="muted">No ALPR results.</p>`;
    return;
  }
  rows.forEach((item) => {
    const row = document.createElement("div");
    row.className = "item";
    row.innerHTML = `<div class="item-title"><span>${item.plate_display}</span><span>${item.status}</span></div>
      <span class="tag">${item.slot_code}</span>
      <span class="tag">${item.plate_format}</span>
      <p class="muted">${Number(item.plate_confidence || 0).toFixed(2)} OCR · ${Number(item.processing_time_ms || 0).toFixed(1)} ms</p>
      ${review ? `<div class="mini-actions">
        <button data-action="confirm">Confirm</button>
        <button data-action="correct">Correct</button>
        <button data-action="reject">Reject</button>
      </div>` : ""}`;
    if (review) {
      row.querySelector('[data-action="confirm"]').onclick = () => reviewAlpr(item.observation_id, "confirm");
      row.querySelector('[data-action="correct"]').onclick = () => {
        const corrected = prompt("Correct plate", item.plate_canonical);
        if (corrected) reviewAlpr(item.observation_id, "correct", corrected);
      };
      row.querySelector('[data-action="reject"]').onclick = () => reviewAlpr(item.observation_id, "reject");
    }
    list.appendChild(row);
  });
}

async function reviewAlpr(id, action, corrected = null) {
  const suffix = corrected ? `?corrected_plate=${encodeURIComponent(corrected)}` : "";
  await request(`/alpr/review/${id}/${action}${suffix}`, { method: "POST" });
  await loadAlprStatus();
}

async function loadPresets() {
  presets = await request("/ptz/presets");
  renderPresets();
  renderPatrol();
}

async function loadZones() {
  const suffix = selectedPreset ? `?preset_id=${encodeURIComponent(selectedPreset.id)}` : "";
  zones = await request(`/zones${suffix}`);
  renderZones();
  redrawCanvas();
}

async function loadSlots() {
  const suffix = selectedPreset ? `?preset_id=${encodeURIComponent(selectedPreset.id)}` : "";
  slots = await request(`/slots${suffix}`);
  renderSlots();
  redrawCanvas();
}

function renderPresets() {
  const list = $("presetList");
  list.innerHTML = "";
  presets.forEach((preset) => {
    const item = document.createElement("div");
    item.className = `item ${selectedPreset?.id === preset.id ? "selected" : ""}`;
    item.innerHTML = `<div class="item-title"><span>${preset.name}</span><span>${preset.sort_order}</span></div>
      <span class="tag ${preset.preset_type}">${preset.preset_type}</span>
      <span class="tag">${preset.dwell_time_ms} ms dwell</span>
      <div class="mini-actions">
        <button data-action="select">Select</button>
        <button data-action="edit">Edit</button>
      </div>`;
    item.querySelector('[data-action="select"]').onclick = () => selectPreset(preset.id);
    item.querySelector('[data-action="edit"]').onclick = () => editPreset(preset.id);
    list.appendChild(item);
  });
}

async function selectPreset(id) {
  selectedPreset = presets.find((preset) => preset.id === id);
  $("selectedPresetTitle").textContent = selectedPreset.name;
  $("selectedPresetMeta").textContent = `${selectedPreset.preset_type} · ${selectedPreset.camera_id}`;
  $("snapshotImage").src = snapshotUrl(selectedPreset.reference_snapshot_path);
  $("snapshotEmpty").style.display = selectedPreset.reference_snapshot_path ? "none" : "grid";
  draftPoints = [];
  polygonClosed = false;
  renderPresets();
  await Promise.all([loadZones(), loadSlots()]);
}

function showCapturedSnapshot(snapshot) {
  $("snapshotImage").src = `${snapshot.snapshot_url}?t=${Date.now()}`;
  $("snapshotEmpty").style.display = "none";
  logMessage(`Snapshot captured: ${snapshot.frame_width}x${snapshot.frame_height}`);
}

function renderZones() {
  const list = $("zoneList");
  list.innerHTML = "";
  zones.forEach((zone) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `<div class="item-title"><span>${zone.code}</span><span>${zone.polygon_points.length} pts</span></div>
      <span class="tag ${zone.zone_type}">${zone.zone_type}</span>
      <p class="muted">${zone.name}</p>
      <p class="muted">${(zone.warnings || []).join(" ")}</p>
      <div class="mini-actions">
        <button data-action="edit">Edit</button>
        <button data-action="delete">Delete</button>
      </div>`;
    item.querySelector('[data-action="edit"]').onclick = () => editZone(zone.id);
    item.querySelector('[data-action="delete"]').onclick = () => deleteZone(zone.id);
    list.appendChild(item);
  });
}

function renderSlots() {
  const list = $("slotList");
  list.innerHTML = "";
  slots.forEach((slot) => {
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `<div class="item-title"><span>${slot.slot_code}</span><span>${slot.polygon_points.length} pts</span></div>
      <span class="tag ${slot.slot_type}">${slot.slot_type}</span>
      <span class="tag">${slot.occupancy_status}</span>
      <div class="mini-actions">
        <button data-action="edit">Edit</button>
        <button data-action="delete">Delete</button>
      </div>`;
    item.querySelector('[data-action="edit"]').onclick = () => editSlot(slot.id);
    item.querySelector('[data-action="delete"]').onclick = () => deleteSlot(slot.id);
    list.appendChild(item);
  });
}

function renderPatrol() {
  const list = $("patrolList");
  list.innerHTML = "";
  presets
    .slice()
    .sort((a, b) => a.sort_order - b.sort_order || a.priority - b.priority)
    .forEach((preset, index) => {
      const row = document.createElement("div");
      row.className = "item";
      row.innerHTML = `<div class="item-title"><span>${index}. ${preset.name}</span><span>${preset.preset_type}</span></div>
        <span class="tag">${preset.settle_time_ms} ms settle</span>
        <span class="tag">${preset.dwell_time_ms} ms dwell</span>
        <div class="mini-actions">
          <button data-action="up">Up</button>
          <button data-action="down">Down</button>
        </div>`;
      row.querySelector('[data-action="up"]').onclick = () => movePreset(preset.id, -1);
      row.querySelector('[data-action="down"]').onclick = () => movePreset(preset.id, 1);
      list.appendChild(row);
    });
}

function resizeCanvas() {
  const canvas = $("polygonCanvas");
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width));
  canvas.height = Math.max(1, Math.floor(rect.height));
  redrawCanvas();
}

function drawPolygon(ctx, points, color, label, closed = true) {
  if (!points.length) return;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = point.x * ctx.canvas.width;
    const y = point.y * ctx.canvas.height;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  if (closed) ctx.closePath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = `${color}33`;
  if (closed) ctx.fill();
  const first = points[0];
  ctx.fillStyle = color;
  ctx.fillText(label, first.x * ctx.canvas.width + 6, first.y * ctx.canvas.height + 16);
}

function redrawCanvas() {
  const canvas = $("polygonCanvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.font = "13px system-ui";
  zones.forEach((zone) => drawPolygon(ctx, zone.polygon_points, colorForType(zone.zone_type), zone.code));
  slots.forEach((slot) => drawPolygon(ctx, slot.polygon_points, "#e3b341", slot.slot_code));
  drawPolygon(ctx, draftPoints, "#ffffff", "draft", polygonClosed);
  draftPoints.forEach((point) => {
    ctx.beginPath();
    ctx.arc(point.x * canvas.width, point.y * canvas.height, 4, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
  });
}

function colorForType(type) {
  return {
    paid_parking: "#2f9e8f",
    no_parking: "#d35d5d",
    disabled_only: "#e3b341",
    service: "#5877d8",
    entrance: "#41b883",
    exit: "#d69e2e",
    lane: "#9aa8b8",
    ignore: "#777777",
  }[type] || "#ffffff";
}

async function savePolygon() {
  if (!selectedPreset) throw new Error("Select a preset first.");
  if (!polygonClosed || draftPoints.length < 3) throw new Error("Close a polygon with at least 3 points.");
  const label = $("polygonLabel").value.trim();
  if (!label) throw new Error("Polygon label or slot code is required.");

  if ($("drawMode").value === "zone") {
    await request("/zones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preset_id: selectedPreset.id,
        code: label,
        name: label,
        zone_type: $("zoneType").value,
        polygon_points: draftPoints,
      }),
    });
    await loadZones();
  } else {
    if (!zones.length) throw new Error("Create a logical zone before saving parking slots.");
    await request("/slots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zone_id: zones[0].id,
        preset_id: selectedPreset.id,
        slot_code: label,
        display_name: label,
        polygon_points: draftPoints,
        slot_type: $("zoneType").value === "disabled_only" ? "disabled" : "normal",
      }),
    });
    await loadSlots();
  }
  draftPoints = [];
  polygonClosed = false;
  $("polygonLabel").value = "";
  redrawCanvas();
}

async function deleteZone(id) {
  if (!confirm("Delete this polygon zone?")) return;
  await request(`/zones/${id}`, { method: "DELETE" });
  await loadZones();
}

async function editZone(id) {
  const zone = zones.find((item) => item.id === id);
  if (!zone) return;
  const code = prompt("Zone code", zone.code);
  if (!code) return;
  const name = prompt("Zone label", zone.name);
  if (!name) return;
  const zoneType = prompt("Zone type", zone.zone_type) || zone.zone_type;
  await request(`/zones/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, name, zone_type: zoneType }),
  });
  await loadZones();
}

async function deleteSlot(id) {
  if (!confirm("Delete this parking slot?")) return;
  await request(`/slots/${id}`, { method: "DELETE" });
  await loadSlots();
}

async function editSlot(id) {
  const slot = slots.find((item) => item.id === id);
  if (!slot) return;
  const slotCode = prompt("Slot code", slot.slot_code);
  if (!slotCode) return;
  const displayName = prompt("Display name", slot.display_name) || slotCode;
  await request(`/slots/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_code: slotCode, display_name: displayName }),
  });
  await loadSlots();
}

async function editPreset(id) {
  const preset = presets.find((item) => item.id === id);
  if (!preset) return;
  const name = prompt("Preset name", preset.name);
  if (!name) return;
  const settle = Number(prompt("Settle time ms", preset.settle_time_ms));
  const dwell = Number(prompt("Dwell time ms", preset.dwell_time_ms));
  const revisit = Number(prompt("Revisit interval seconds", preset.revisit_interval_seconds));
  await request(`/ptz/presets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      settle_time_ms: Number.isFinite(settle) ? settle : preset.settle_time_ms,
      dwell_time_ms: Number.isFinite(dwell) ? dwell : preset.dwell_time_ms,
      revisit_interval_seconds: Number.isFinite(revisit) ? revisit : preset.revisit_interval_seconds,
    }),
  });
  await loadPresets();
  if (selectedPreset?.id === id) await selectPreset(id);
}

async function movePreset(id, direction) {
  const ordered = presets.slice().sort((a, b) => a.sort_order - b.sort_order || a.priority - b.priority);
  const index = ordered.findIndex((preset) => preset.id === id);
  const swapIndex = index + direction;
  if (index < 0 || swapIndex < 0 || swapIndex >= ordered.length) return;
  const current = ordered[index];
  const other = ordered[swapIndex];
  await Promise.all([
    request(`/ptz/presets/${current.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sort_order: other.sort_order }),
    }),
    request(`/ptz/presets/${other.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sort_order: current.sort_order }),
    }),
  ]);
  await loadPresets();
}

async function savePatrol() {
  const steps = presets
    .slice()
    .sort((a, b) => a.sort_order - b.sort_order || a.priority - b.priority)
    .map((preset, index) => ({
      preset_id: preset.id,
      order: index,
      enabled: preset.enabled,
      settle_time_ms: preset.settle_time_ms,
      dwell_time_ms: preset.dwell_time_ms,
      capture_burst_count: 3,
      revisit_interval_seconds: preset.revisit_interval_seconds,
      priority: preset.priority,
    }));
  const home = presets.find((preset) => preset.preset_type === "home");
  await request("/patrol", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Default Patrol", home_preset_id: home?.id || null, steps }),
  });
  const simulation = await request("/patrol/simulate", { method: "POST" });
  $("patrolSummary").textContent =
    `Cycle: ${simulation.estimated_complete_cycle_seconds}s · ` +
    `Max detection delay: ${simulation.estimated_maximum_detection_delay_seconds}s\n` +
    simulation.warnings.join("\n");
}

function bindEvents() {
  $("refreshPresets").onclick = () => loadPresets().catch((error) => logMessage(error.message));
  $("refreshZones").onclick = () => loadZones().catch((error) => logMessage(error.message));
  $("refreshSlots").onclick = () => loadSlots().catch((error) => logMessage(error.message));
  $("refreshRuntime").onclick = () => Promise.all([loadRuntimeStatus(), loadActiveSessions()]).catch((error) => logMessage(error.message));
  $("refreshSessions").onclick = () => loadActiveSessions().catch((error) => logMessage(error.message));
  $("refreshAlpr").onclick = () => loadAlprStatus().catch((error) => logMessage(error.message));
  $("processLatestSnapshot").onclick = async () => {
    const result = await request("/alpr/process-latest-snapshot", { method: "POST" });
    logMessage(`ALPR processed latest snapshot: ${result.observations.length} observations`);
    await loadAlprStatus();
  };
  $("alprTestImage").onchange = async (event) => {
    const file = event.currentTarget.files[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    const result = await request("/alpr/test-snapshot", { method: "POST", body });
    logMessage(`ALPR test image: ${result.observations.length} observations`);
    await loadAlprStatus();
  };
  $("startRuntime").onclick = async () => {
    const result = await request("/runtime/start", { method: "POST" });
    logMessage(result.message);
    await loadRuntimeStatus();
  };
  $("stopRuntime").onclick = async () => {
    const result = await request("/runtime/stop", { method: "POST" });
    logMessage(result.message);
    await loadRuntimeStatus();
  };
  $("testCamera").onclick = async () => {
    try {
      cameraStatus = await request("/camera/test", { method: "POST" });
      renderCameraStatus(cameraStatus.decoded_frame ? "decoded frame received" : "no frame decoded");
    } catch (error) {
      logMessage(error.message);
      await loadCameraStatus();
    }
  };
  $("reconnectCamera").onclick = async () => {
    try {
      cameraStatus = await request("/camera/reconnect", { method: "POST" });
      renderCameraStatus(cameraStatus.decoded_frame ? "reconnected" : "reconnect failed");
    } catch (error) {
      logMessage(error.message);
      await loadCameraStatus();
    }
  };
  $("captureCameraSnapshot").onclick = async () => {
    try {
      if (selectedPreset) {
        await request(`/ptz/presets/${selectedPreset.id}/snapshot?source=capture`, { method: "POST" });
        await loadPresets();
        await selectPreset(selectedPreset.id);
        logMessage("Preset reference snapshot captured.");
      } else {
        const snapshot = await request("/camera/snapshot", { method: "POST" });
        showCapturedSnapshot(snapshot);
      }
      await loadCameraStatus();
    } catch (error) {
      logMessage(error.message);
      await loadCameraStatus();
    }
  };
  $("savePatrol").onclick = () => savePatrol().catch((error) => logMessage(error.message));
  $("closePolygon").onclick = () => {
    polygonClosed = true;
    redrawCanvas();
  };
  $("undoPoint").onclick = () => {
    draftPoints.pop();
    polygonClosed = false;
    redrawCanvas();
  };
  $("clearPolygon").onclick = () => {
    draftPoints = [];
    polygonClosed = false;
    redrawCanvas();
  };
  $("savePolygon").onclick = () => savePolygon().catch((error) => logMessage(error.message));
  $("polygonCanvas").onclick = (event) => {
    if (polygonClosed) return;
    const rect = event.currentTarget.getBoundingClientRect();
    draftPoints.push({
      x: Number(((event.clientX - rect.left) / rect.width).toFixed(5)),
      y: Number(((event.clientY - rect.top) / rect.height).toFixed(5)),
    });
    redrawCanvas();
  };
  $("presetForm").onsubmit = async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await request("/ptz/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(form.entries())),
    }).catch((error) => logMessage(error.message));
    event.currentTarget.reset();
    await loadPresets();
  };
  $("setHome").onclick = async () => {
    if (!selectedPreset) return;
    await request(`/ptz/presets/${selectedPreset.id}/set-home`, { method: "POST" });
    await loadPresets();
  };
  $("gotoPreset").onclick = async () => {
    if (!selectedPreset) return;
    const result = await request(`/ptz/presets/${selectedPreset.id}/goto`, { method: "POST" });
    logMessage(result.message);
  };
  $("deletePreset").onclick = async () => {
    if (!selectedPreset || !confirm("Delete this preset and its polygons?")) return;
    await request(`/ptz/presets/${selectedPreset.id}`, { method: "DELETE" });
    selectedPreset = null;
    await loadPresets();
  };
  $("snapshotForm").onsubmit = async (event) => {
    event.preventDefault();
    if (!selectedPreset) return logMessage("Select a preset first.");
    const file = $("snapshotFile").files[0];
    if (!file) return logMessage("Choose a JPEG or PNG first.");
    const body = new FormData();
    body.append("file", file);
    await request(`/ptz/presets/${selectedPreset.id}/snapshot?source=upload`, { method: "POST", body });
    await loadPresets();
    await selectPreset(selectedPreset.id);
  };
  $("captureSnapshot").onclick = async () => {
    if (!selectedPreset) return logMessage("Select a preset first.");
    try {
      await request(`/ptz/presets/${selectedPreset.id}/snapshot?source=capture`, { method: "POST" });
      await loadPresets();
      await selectPreset(selectedPreset.id);
    } catch (error) {
      logMessage(error.message);
    }
  };
  $("snapshotImage").onload = resizeCanvas;
  window.onresize = resizeCanvas;
}

bindEvents();
loadHealth()
  .then(loadCameraStatus)
  .then(loadRuntimeStatus)
  .then(loadActiveSessions)
  .then(loadAlprStatus)
  .then(loadPresets)
  .then(resizeCanvas)
  .catch((error) => logMessage(error.message));
