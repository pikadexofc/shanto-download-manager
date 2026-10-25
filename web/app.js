/**
 * Shanto Download Manager — Frontend Controller
 * WebSocket Telemetry & Dynamic Chunk Visualizer
 */

const API_BASE = window.location.origin;
const WS_URL = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws`;

let socket = null;
let tasksMap = new Map();
let currentCategory = "ALL";
let currentSearch = "";
let selectedTaskId = null;

// DOM Elements
const downloadsListEl = document.getElementById("downloads-list");
const emptyStateEl = document.getElementById("empty-state");
const hudTotalSpeedEl = document.getElementById("hud-total-speed");
const hudActiveThreadsEl = document.getElementById("hud-active-threads");
const segmentDrawerEl = document.getElementById("segment-drawer");
const drawerTitleEl = document.getElementById("drawer-title");
const drawerSummaryEl = document.getElementById("drawer-summary");
const drawerSegmentsEl = document.getElementById("drawer-segments");

// Badges
const badgeAll = document.getElementById("badge-all");
const badgeDownloading = document.getElementById("badge-downloading");
const badgeCompleted = document.getElementById("badge-completed");
const badgeCompressed = document.getElementById("badge-compressed");
const badgeVideo = document.getElementById("badge-video");
const badgeAudio = document.getElementById("badge-audio");
const badgeDocuments = document.getElementById("badge-documents");
const badgePrograms = document.getElementById("badge-programs");

// Connect WebSocket
function initWebSocket() {
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log("[SDM] Connected to Turbo WebSocket Telemetry");
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleSocketMessage(data);
    } catch (e) {
      console.error("[SDM] Failed to parse telemetry packet", e);
    }
  };

  socket.onclose = () => {
    console.warn("[SDM] Telemetry socket closed. Reconnecting in 2s...");
    setTimeout(initWebSocket, 2000);
  };
}

function handleSocketMessage(data) {
  if (data.event === "initial_state" && Array.isArray(data.tasks)) {
    tasksMap.clear();
    data.tasks.forEach((t) => tasksMap.set(t.task_id, t));
    renderTasks();
  } else if (data.event === "task_updated" && data.task) {
    tasksMap.set(data.task.task_id, data.task);
    updateTaskCard(data.task);
    updateHUD();
    if (selectedTaskId === data.task.task_id) {
      renderSegmentDrawer(data.task);
    }
  } else if (data.event === "task_deleted" && data.task_id) {
    tasksMap.delete(data.task_id);
    if (selectedTaskId === data.task_id) {
      closeDrawer();
    }
    renderTasks();
  }
}

function updateHUD() {
  let totalSpeed = 0;
  let activeThreads = 0;
  let cAll = tasksMap.size;
  let cDown = 0;
  let cComp = 0;
  let cCompressed = 0;
  let cVideo = 0;
  let cAudio = 0;
  let cDocs = 0;
  let cProg = 0;

  tasksMap.forEach((t) => {
    if (t.status === "DOWNLOADING") {
      totalSpeed += t.speed_bps || 0;
      activeThreads += (t.segments || []).filter((s) => s.status === "ACTIVE").length || 1;
      cDown++;
    } else if (t.status === "COMPLETED") {
      cComp++;
    }

    if (t.category === "Compressed") cCompressed++;
    if (t.category === "Video") cVideo++;
    if (t.category === "Audio") cAudio++;
    if (t.category === "Documents") cDocs++;
    if (t.category === "Programs") cProg++;
  });

  hudTotalSpeedEl.innerText = formatSpeed(totalSpeed);
  hudActiveThreadsEl.innerText = activeThreads;

  badgeAll.innerText = cAll;
  badgeDownloading.innerText = cDown;
  badgeCompleted.innerText = cComp;
  badgeCompressed.innerText = cCompressed;
  badgeVideo.innerText = cVideo;
  badgeAudio.innerText = cAudio;
  badgeDocuments.innerText = cDocs;
  badgePrograms.innerText = cProg;
}

function renderTasks() {
  const filtered = Array.from(tasksMap.values()).filter((t) => {
    if (currentCategory === "DOWNLOADING" && t.status !== "DOWNLOADING") return false;
    if (currentCategory === "COMPLETED" && t.status !== "COMPLETED") return false;
    if (currentCategory !== "ALL" && currentCategory !== "DOWNLOADING" && currentCategory !== "COMPLETED") {
      if (t.category !== currentCategory) return false;
    }
    if (currentSearch && !t.filename.toLowerCase().includes(currentSearch.toLowerCase())) {
      return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    emptyStateEl.style.display = "block";
    downloadsListEl.innerHTML = "";
    downloadsListEl.appendChild(emptyStateEl);
  } else {
    emptyStateEl.style.display = "none";
    downloadsListEl.innerHTML = "";
    filtered.forEach((task) => {
      const card = createTaskCard(task);
      downloadsListEl.appendChild(card);
    });
  }
  updateHUD();
}

function createTaskCard(task) {
  const card = document.createElement("div");
  card.className = "task-card";
  card.id = `card-${task.task_id}`;

  const icon = getCategoryIcon(task.category);

  card.innerHTML = `
    <div class="task-header">
      <div class="task-title-group">
        <span class="task-icon">${icon}</span>
        <div class="task-filename" title="${task.filename}">${task.filename}</div>
        <span class="task-category-pill">${task.category}</span>
      </div>
      <span class="task-status-badge status-${task.status}">${task.status}</span>
    </div>

    <div class="progress-bar-container" id="bar-${task.task_id}">
      ${renderSegmentsBar(task)}
    </div>

    <div class="task-meta">
      <div class="meta-stats">
        <span>${task.downloaded_formatted} / ${task.size_formatted}</span>
        <span>${task.progress}%</span>
        <span class="meta-speed">${task.speed_formatted}</span>
        <span>ETA: ${formatETA(task.eta_seconds)}</span>
      </div>
      <div class="task-actions">
        ${task.status === "DOWNLOADING" ? `<button class="btn btn-secondary btn-sm" onclick="pauseTask('${task.task_id}')">Pause</button>` : ""}
        ${task.status === "PAUSED" || task.status === "PENDING" || task.status === "ERROR" ? `<button class="btn btn-primary btn-sm" onclick="startTask('${task.task_id}')">Resume</button>` : ""}
        <button class="btn btn-secondary btn-sm" onclick="viewSegments('${task.task_id}')">Segments</button>
        <button class="btn btn-secondary btn-sm" onclick="deleteTask('${task.task_id}')">✕</button>
      </div>
    </div>
  `;

  return card;
}

function updateTaskCard(task) {
  let card = document.getElementById(`card-${task.task_id}`);
  if (!card) {
    renderTasks();
    return;
  }

  // Update status badge
  const badge = card.querySelector(".task-status-badge");
  if (badge) {
    badge.className = `task-status-badge status-${task.status}`;
    badge.innerText = task.status;
  }

  // Update progress bar
  const bar = document.getElementById(`bar-${task.task_id}`);
  if (bar) {
    bar.innerHTML = renderSegmentsBar(task);
  }

  // Update meta
  const meta = card.querySelector(".meta-stats");
  if (meta) {
    meta.innerHTML = `
      <span>${task.downloaded_formatted} / ${task.size_formatted}</span>
      <span>${task.progress}%</span>
      <span class="meta-speed">${task.speed_formatted}</span>
      <span>ETA: ${formatETA(task.eta_seconds)}</span>
    `;
  }
}

function renderSegmentsBar(task) {
  if (!task.segments || task.segments.length === 0) {
    return `<div class="progress-segment-fill segment-finished" style="width: ${task.progress}%"></div>`;
  }

  const total = task.total_size || 1;
  return task.segments.map((seg) => {
    const segTotal = Math.max(1, seg.end - seg.start + 1);
    const segDownloaded = Math.max(0, seg.current - seg.start);
    const segWidthPercent = (segTotal / total) * 100;
    const segProgress = Math.min(100, (segDownloaded / segTotal) * 100);

    let cls = "segment-pending";
    if (seg.status === "FINISHED") cls = "segment-finished";
    if (seg.status === "ACTIVE") cls = "segment-active";

    return `
      <div style="width: ${segWidthPercent}%; display: flex; height: 100%;">
        <div class="progress-segment-fill ${cls}" style="width: ${segProgress}%;"></div>
      </div>
    `;
  }).join("");
}

function renderSegmentDrawer(task) {
  drawerTitleEl.innerText = `Dynamic Segment Visualizer: ${task.filename}`;
  drawerSummaryEl.innerHTML = `
    <span><strong>Segments:</strong> ${task.segments ? task.segments.length : 1}</span> | 
    <span><strong>Speed:</strong> ${task.speed_formatted}</span> | 
    <span><strong>ETA:</strong> ${formatETA(task.eta_seconds)}</span>
  `;

  if (!task.segments || task.segments.length === 0) {
    drawerSegmentsEl.innerHTML = `<p style="color: var(--text-muted)">Single Stream Mode (Server does not advertise range chunks)</p>`;
    return;
  }

  drawerSegmentsEl.innerHTML = task.segments.map((s) => `
    <div class="segment-card ${s.status === 'ACTIVE' ? 'active' : ''} ${s.status === 'FINISHED' ? 'finished' : ''}">
      <div><strong>Thread #${s.id}</strong> [${s.status}]</div>
      <div>Range: ${formatBytes(s.start)} - ${formatBytes(s.end)}</div>
      <div>Progress: ${s.progress}% (${s.speed})</div>
    </div>
  `).join("");
}

function viewSegments(taskId) {
  selectedTaskId = taskId;
  const task = tasksMap.get(taskId);
  if (task) {
    renderSegmentDrawer(task);
    segmentDrawerEl.classList.add("open");
  }
}

function closeDrawer() {
  selectedTaskId = null;
  segmentDrawerEl.classList.remove("open");
}

// Actions
window.startTask = async (taskId) => {
  await fetch(`${API_BASE}/api/tasks/${taskId}/start`, { method: "POST" });
};

window.pauseTask = async (taskId) => {
  await fetch(`${API_BASE}/api/tasks/${taskId}/pause`, { method: "POST" });
};

window.deleteTask = async (taskId) => {
  if (confirm("Delete this download?")) {
    await fetch(`${API_BASE}/api/tasks/${taskId}?delete_file=false`, { method: "DELETE" });
  }
};

window.viewSegments = viewSegments;

// Categories Navigation
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentCategory = btn.dataset.category;
    renderTasks();
  });
});

// Search Filter
document.getElementById("search-input").addEventListener("input", (e) => {
  currentSearch = e.target.value;
  renderTasks();
});

// Speed Limit Buttons
document.querySelectorAll(".btn-speed").forEach((btn) => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll(".btn-speed").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const limit = parseInt(btn.dataset.limit, 10);
    await fetch(`${API_BASE}/api/settings/speed-limit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit_kbps: limit }),
    });
  });
});

// Modal Controls
const modal = document.getElementById("add-modal");
document.getElementById("btn-add-modal").addEventListener("click", () => {
  modal.classList.add("open");
  document.getElementById("modal-url").focus();
});
document.getElementById("btn-close-modal").addEventListener("click", () => modal.classList.remove("open"));
document.getElementById("btn-cancel-modal").addEventListener("click", () => modal.classList.remove("open"));
document.getElementById("btn-close-drawer").addEventListener("click", closeDrawer);

// Sniff Media
document.getElementById("btn-sniff-media").addEventListener("click", async () => {
  const url = document.getElementById("modal-url").value.trim();
  if (!url) return;

  const btn = document.getElementById("btn-sniff-media");
  btn.innerText = "Sniffing...";
  try {
    const res = await fetch(`${API_BASE}/api/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (data.status === "ok" && data.info) {
      document.getElementById("preview-title").innerText = data.info.title;
      document.getElementById("preview-meta").innerText = `Uploader: ${data.info.uploader} | Formats: ${data.info.formats.length} streams available`;
      if (data.info.thumbnail) {
        document.getElementById("preview-img").src = data.info.thumbnail;
      }
      document.getElementById("media-preview").style.display = "flex";
    }
  } catch (e) {
    alert("Media sniffing failed: " + e.message);
  } finally {
    btn.innerText = "Sniff Media Formats";
  }
});

// Start Download from Modal
document.getElementById("btn-start-download").addEventListener("click", async () => {
  const url = document.getElementById("modal-url").value.trim();
  if (!url) return;

  const filename = document.getElementById("modal-filename").value.trim() || null;
  const category = document.getElementById("modal-category").value || null;
  const speed = parseInt(document.getElementById("modal-speed").value, 10) || 0;

  await fetch(`${API_BASE}/api/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      filename,
      category,
      speed_limit_kbps: speed,
      auto_start: true,
    }),
  });

  modal.classList.remove("open");
  document.getElementById("modal-url").value = "";
  document.getElementById("modal-filename").value = "";
  document.getElementById("media-preview").style.display = "none";
});

// Global Pause/Resume All
document.getElementById("btn-pause-all").addEventListener("click", () => {
  tasksMap.forEach((t) => {
    if (t.status === "DOWNLOADING") pauseTask(t.task_id);
  });
});

document.getElementById("btn-resume-all").addEventListener("click", () => {
  tasksMap.forEach((t) => {
    if (t.status === "PAUSED" || t.status === "PENDING") startTask(t.task_id);
  });
});

// Helpers
function formatSpeed(bps) {
  if (!bps || bps <= 0) return "0.00 B/s";
  const units = ["B/s", "KB/s", "MB/s", "GB/s"];
  let i = 0, v = bps;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(2)} ${units[i]}`;
}

function formatBytes(b) {
  if (!b || b <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = b;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}

function formatETA(sec) {
  if (!sec || sec <= 0 || !isFinite(sec)) return "--";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }
  return `${m}m ${s}s`;
}

function getCategoryIcon(cat) {
  switch (cat) {
    case "Compressed": return "📦";
    case "Video": return "🎬";
    case "Audio": return "🎵";
    case "Documents": return "📄";
    case "Programs": return "💻";
    default: return "⚡";
  }
}

// Start
initWebSocket();
