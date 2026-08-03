"use strict";

const DATA_URL = "./data/training/trend_review_training_round2.json";
const STORAGE_KEY = "trend_review_labels_v2";
const REASON_CHIPS = [
  "platform_policy",
  "distribution_model",
  "monetization",
  "publisher_strategy",
  "market_signal",
  "sea_relevance",
  "repeated_story",
  "credible_source",
  "too_consumer",
  "too_speculative",
  "stock_only",
  "junk",
  "wrong_category",
  "future_release",
  "not_future_release",
  "not_industry_trend",
  "not_sea_relevant",
  "not_sg_relevant",
  "minor_update",
  "esports_result",
  "esports_not_report",
  "ordinary_financials",
  "non_game_launch",
  "hardware_retail",
  "regional_ecosystem",
  "ip_expansion",
  "developer_profile",
  "low_market_relevance",
];

const state = {
  payload: null,
  items: [],
  labels: {},
  query: "",
  labelFilter: "all",
  bucketFilter: "all",
  laneFilter: "all",
};

const els = {
  totalCount: document.getElementById("totalCount"),
  labeledCount: document.getElementById("labeledCount"),
  visibleCount: document.getElementById("visibleCount"),
  progressPct: document.getElementById("progressPct"),
  reviewList: document.getElementById("reviewList"),
  searchInput: document.getElementById("searchInput"),
  labelFilter: document.getElementById("labelFilter"),
  bucketFilter: document.getElementById("bucketFilter"),
  laneFilter: document.getElementById("laneFilter"),
  exportButton: document.getElementById("exportButton"),
  clearVisibleButton: document.getElementById("clearVisibleButton"),
  fileInput: document.getElementById("fileInput"),
  loadNotice: document.getElementById("loadNotice"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeId(id) {
  return String(id || "").trim();
}

function loadLabels() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    state.labels = raw ? JSON.parse(raw) : {};
  } catch {
    state.labels = {};
  }
}

function saveLabels() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.labels));
}

function labelFor(articleId) {
  return state.labels[articleId] || { label: null, reasons: [], notes: "" };
}

function setLabel(articleId, label) {
  const current = labelFor(articleId);
  state.labels[articleId] = {
    ...current,
    label: current.label === label ? null : label,
    updated_at: new Date().toISOString(),
  };
  saveLabels();
  render();
}

function toggleReason(articleId, reason) {
  const current = labelFor(articleId);
  const reasons = new Set(current.reasons || []);
  if (reasons.has(reason)) {
    reasons.delete(reason);
  } else {
    reasons.add(reason);
  }
  state.labels[articleId] = {
    ...current,
    reasons: Array.from(reasons),
    updated_at: new Date().toISOString(),
  };
  saveLabels();
  renderStats(filteredItems().length);
}

function setNotes(articleId, notes) {
  const current = labelFor(articleId);
  state.labels[articleId] = {
    ...current,
    notes,
    updated_at: new Date().toISOString(),
  };
  saveLabels();
}

function articleText(item) {
  return [
    item.title,
    item.title_en,
    item.source,
    item.radar_section,
    item.source_tier,
    item.review_lane,
    item.suggested_trend_bucket,
    item.system_reason,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function filteredItems() {
  const terms = state.query.toLowerCase().split(/\s+/).filter(Boolean);
  return state.items.filter((item) => {
    const articleId = normalizeId(item.article_id);
    const label = labelFor(articleId).label;
    if (state.labelFilter === "unlabeled" && label) return false;
    if (["include", "watch", "exclude"].includes(state.labelFilter) && label !== state.labelFilter) return false;
    if (state.bucketFilter !== "all" && item.suggested_trend_bucket !== state.bucketFilter) return false;
    if (state.laneFilter !== "all" && item.review_lane !== state.laneFilter) return false;
    if (terms.length && !terms.every((term) => articleText(item).includes(term))) return false;
    return true;
  });
}

function bucketLabel(bucket) {
  return String(bucket || "unbucketed").replaceAll("_", " ");
}

function labelButtons(item, current) {
  const articleId = escapeHtml(item.article_id);
  return ["include", "watch", "exclude"]
    .map((label) => {
      const active = current.label === label ? " active" : "";
      return `<button class="label-button ${label}${active}" type="button" data-action="label" data-id="${articleId}" data-label="${label}">${label}</button>`;
    })
    .join("");
}

function reasonChips(item, current) {
  const reasons = new Set(current.reasons || []);
  const articleId = escapeHtml(item.article_id);
  return REASON_CHIPS.map((reason) => {
    const active = reasons.has(reason) ? " active" : "";
    return `<button class="chip${active}" type="button" data-action="reason" data-id="${articleId}" data-reason="${reason}">${reason}</button>`;
  }).join("");
}

function renderItem(item) {
  const articleId = normalizeId(item.article_id);
  const current = labelFor(articleId);
  const titleEn = item.title_en ? `<p class="title-en">${escapeHtml(item.title_en)}</p>` : "";
  const url = item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">open source</a>` : "no url";
  return `
    <article class="card" data-article-id="${escapeHtml(articleId)}">
      <div class="card-head">
        <div>
          <h2 class="title">${escapeHtml(item.title)}</h2>
          ${titleEn}
        </div>
        <div class="score">${Number(item.system_score || 0)}</div>
      </div>
      <div class="meta">
        <span class="pill">${escapeHtml(item.source)}</span>
        <span class="pill">${escapeHtml(item.published_at || "undated")}</span>
        <span class="pill">${escapeHtml(item.radar_section || "unknown")}</span>
        <span class="pill">${escapeHtml(item.source_tier || "unknown tier")}</span>
        <span class="pill">${url}</span>
      </div>
      <div class="system">
        <span class="pill">${escapeHtml(bucketLabel(item.review_lane || "unlaned"))}</span>
        <span class="pill">${escapeHtml(bucketLabel(item.suggested_trend_bucket))}</span>
        <span class="pill">${escapeHtml(item.system_reason || "no system reason")}</span>
      </div>
      <div class="actions">${labelButtons(item, current)}</div>
      <div class="chips">${reasonChips(item, current)}</div>
      <textarea data-action="notes" data-id="${escapeHtml(articleId)}" placeholder="Optional notes">${escapeHtml(current.notes || "")}</textarea>
    </article>
  `;
}

function renderStats(visibleCount) {
  const total = state.items.length;
  const labeled = state.items.filter((item) => labelFor(normalizeId(item.article_id)).label).length;
  els.totalCount.textContent = String(total);
  els.labeledCount.textContent = String(labeled);
  els.visibleCount.textContent = String(visibleCount);
  els.progressPct.textContent = total ? `${Math.round((labeled / total) * 100)}%` : "0%";
}

function render() {
  const visible = filteredItems();
  renderStats(visible.length);
  if (!visible.length) {
    els.reviewList.innerHTML = '<div class="empty">No items match the current filters.</div>';
    return;
  }
  els.reviewList.innerHTML = visible.map(renderItem).join("");
}

function normalizePayload(payload) {
  if (Array.isArray(payload)) {
    return { items: payload };
  }
  return payload && Array.isArray(payload.items) ? payload : { items: [] };
}

function setPayload(payload) {
  state.payload = normalizePayload(payload);
  state.items = state.payload.items.filter((item) => normalizeId(item.article_id));
  els.loadNotice.classList.remove("visible");
  render();
}

async function loadTrainingData() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    setPayload(await response.json());
  } catch {
    els.loadNotice.classList.add("visible");
    render();
  }
}

function exportLabels() {
  const labeledItems = state.items
    .map((item) => {
      const articleId = normalizeId(item.article_id);
      const label = labelFor(articleId);
      return {
        article_id: articleId,
        label: label.label,
        reasons: label.reasons || [],
        notes: label.notes || "",
        title: item.title,
        source: item.source,
        review_lane: item.review_lane,
        suggested_trend_bucket: item.suggested_trend_bucket,
        system_score: item.system_score,
        updated_at: label.updated_at || null,
      };
    })
    .filter((entry) => entry.label || entry.reasons.length || entry.notes);

  const payload = {
    exported_at: new Date().toISOString(),
    source_file: state.payload?.source_file || DATA_URL.replace("./", ""),
    source_generated_at: state.payload?.generated_at || null,
    total_training_items: state.items.length,
    total_label_records: labeledItems.length,
    labels: labeledItems,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "trend_review_labels.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function clearVisibleLabels() {
  for (const item of filteredItems()) {
    delete state.labels[normalizeId(item.article_id)];
  }
  saveLabels();
  render();
}

function bindEvents() {
  els.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    render();
  });
  els.labelFilter.addEventListener("change", (event) => {
    state.labelFilter = event.target.value;
    render();
  });
  els.bucketFilter.addEventListener("change", (event) => {
    state.bucketFilter = event.target.value;
    render();
  });
  els.laneFilter.addEventListener("change", (event) => {
    state.laneFilter = event.target.value;
    render();
  });
  els.exportButton.addEventListener("click", exportLabels);
  els.clearVisibleButton.addEventListener("click", clearVisibleLabels);
  els.fileInput.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setPayload(JSON.parse(await file.text()));
  });
  els.reviewList.addEventListener("click", (event) => {
    const target = event.target.closest("button");
    if (!target) return;
    const articleId = target.dataset.id;
    if (target.dataset.action === "label") {
      setLabel(articleId, target.dataset.label);
    }
    if (target.dataset.action === "reason") {
      toggleReason(articleId, target.dataset.reason);
      target.classList.toggle("active");
    }
  });
  els.reviewList.addEventListener("input", (event) => {
    if (event.target.dataset.action === "notes") {
      setNotes(event.target.dataset.id, event.target.value);
      renderStats(filteredItems().length);
    }
  });
}

loadLabels();
bindEvents();
loadTrainingData();
