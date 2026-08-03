// Game News Radar frontend.
//
// Reads data/game-news.json, produced by the live pipeline
// (scripts/update_game_news.py, see .github/workflows/update-game-news.yml)
// and pushed to the orphan `game-data` branch - NOT committed into master's
// history, so it never accumulates the way AI News's archive.json used to.
// Falls back to the same-branch relative path (the one-time historical seed
// baked into master) if the live branch isn't reachable yet, e.g. before its
// first successful run. Kept deliberately separate from assets/app.js so
// this page can iterate without risking the AI News page.

const REPO_SLUG = "ShaunaYong-PlayPark/ai-news-radar";
const LIVE_DATA_URL = `https://raw.githubusercontent.com/${REPO_SLUG}/game-data/data/game-news.json`;
const FALLBACK_DATA_URL = "./data/game-news.json";
const ST_RANK_URL = "./data/game-rank-index.json";
const LOCAL_PREVIEW_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
const REGION_LABELS = {
  ALL: "Hot",
  TH: "Thailand",
  PH: "Philippines",
  VN: "Vietnam",
  SG: "Singapore",
  MY: "Malaysia",
  ID: "Indonesia",
  CN: "China",
  TW: "Taiwan",
  GLOBAL: "Global",
  OTHERS: "Others",
  MISC: "Misc",
};
const RADAR_SECTION_LABELS = {
  industry_reports: "Industry reports",
  game_releases: "Game releases",
  game_announcements: "Game announcements",
  other: "Other",
};
const HOT_SECTION_ORDER = ["industry_reports", "game_announcements", "game_releases"];
const SOURCE_TIER_LABELS = {
  major_gaming_media: "Major gaming media",
  regional_gaming_media: "Regional gaming media",
  business_industry_media: "Business / industry media",
  aggregator: "Aggregators",
  mixed_portal: "Mixed portals",
};
const HOT_LIMIT = 200;
const DEFAULT_SOURCE_TIER = "aggregator";

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const state = {
  items: [],
  hotItems: [],
  clusters: [],
  byRegion: {},
  region: "ALL",
  radarSection: "",
  sourceTier: "",
  specificSource: "",
  query: "",
  dateFrom: null, // Date, UTC start-of-day
  dateTo: null,   // Date, UTC end-of-day
  stBonus: new Map(),         // url → float, pre-computed Sensor Tower rank bonus
  multiSourceBonus: new Map(), // url → float, +0.3 when 2+ distinct sources cover same game within 24h
  multiSourceSources: new Map(), // url → int, count of distinct sources for badge display
};

function itemEventTime(item) {
  const iso = item.published_at || item.last_seen_at || item.first_seen_at;
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDate(iso) {
  const d = itemEventTime({ published_at: iso });
  return d ? formatDDMMMYYYY(d) : "Undated";
}

function formatDDMMMYYYY(date) {
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const mmm = MONTH_ABBR[date.getUTCMonth()];
  return `${dd}-${mmm}-${date.getUTCFullYear()}`;
}

function escapeHtml(str) {
  return String(str || "").replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));
}

function sourceTierOf(item) {
  return item.source_tier || DEFAULT_SOURCE_TIER;
}

function sourceTierLabel(value) {
  return SOURCE_TIER_LABELS[value] || value || "Aggregators";
}

function clusterItems(cluster) {
  return Array.isArray(cluster.items) ? cluster.items : [];
}

function clusterMainItem(cluster) {
  return cluster.main_item || clusterItems(cluster)[0] || {};
}

function entryEventTime(entry) {
  return entry.kind === "cluster" ? itemEventTime(clusterMainItem(entry.data)) : itemEventTime(entry.data);
}

function entryMatchesRegion(entry, region) {
  if (region === "ALL") return true;
  if (entry.kind === "item") return entry.data.region === region;
  return clusterItems(entry.data).some((it) => it.region === region);
}

function entryMatchesRadarSection(entry, radarSection) {
  if (!radarSection) return true;
  return entryRadarSection(entry) === radarSection;
}

function entryRadarSection(entry) {
  return entry.kind === "cluster" ? entry.data.radar_section : entry.data.radar_section;
}

function entryMatchesSourceTier(entry, sourceTier) {
  if (!sourceTier) return true;
  if (entry.kind === "item") return sourceTierOf(entry.data) === sourceTier;
  return clusterItems(entry.data).some((it) => sourceTierOf(it) === sourceTier);
}

function entryMatchesSpecificSource(entry, siteId) {
  if (!siteId) return true;
  if (entry.kind === "item") return entry.data.site_id === siteId;
  return clusterItems(entry.data).some((it) => it.site_id === siteId);
}

function entryMatchesDateRange(entry) {
  if (!state.dateFrom || !state.dateTo) return true;
  const t = entryEventTime(entry);
  return t && t >= state.dateFrom && t <= state.dateTo;
}

function hotEntryScore(entry) {
  if (entry.kind === "cluster") return Number(entry.data.cluster_score || 0);
  return Number(entry.data.hot_score || 0);
}

// High-signal title phrases — fires when content_type is unset or generic.
// Ordered by significance; first match wins, capped at 0.35.
const KEYWORD_BOOSTS = [
  // Major industry events
  [0.35, ["shuts down", "shut down", "shutting down", "bankruptcy", "bankrupt", "acquired by", "acquisition"]],
  [0.30, ["billion", "record breaking", "record-breaking", "all time high", "all-time high", "milestone"]],
  [0.25, ["lawsuit", "sued", "controversy", "major update", "big update", "world championship", "world cup"]],
  [0.20, ["launches", "launch date", "release date", "out now", "goes live", "early access", "new season",
           "server down", "maintenance", "ban wave", "partnership", "collaboration announced"]],
];

function keywordBoost(item) {
  const title = (item.title_en || item.title || "").toLowerCase();
  for (const [boost, phrases] of KEYWORD_BOOSTS) {
    for (const phrase of phrases) {
      if (title.includes(phrase)) return boost;
    }
  }
  return 0;
}

// Phase-1 signal score: pure client-side, no external API.
// Components: recency (decays to 0 at 7 days) + source tier + event type
// + keyword boost + Sensor Tower SEA revenue rank bonus (Phase 2).
// ── Sensor Tower rank bonus (Phase 2) ─────────────────────────────
// Loads data/game-rank-index.json (generated by scripts/build_game_rank_index.py
// from the Sensor Tower SEA6 export). Hot ranking uses backend scores.
// time — pre-computed once per item, not per-render.

function stNormalize(s) {
  return String(s).toLowerCase()
    .replace(/[™®''™®:!?,.'`\-™®’]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function regexEscape(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildStIndex(rankData) {
  // Only the top 1000 by revenue rank carry meaningful signal weight;
  // entries below that have < $1.5M revenue across 12 years in SEA.
  const entries = (rankData.entries || []).slice(0, 1000).map((e) => ({
    rank:     e.rank,
    name:     e.name,
    key:      e.key,
    alt:      e.alt || null,
    // boundary=true → must match as a whole word (short Latin names like "Roblox", "MIR4")
    // boundary=false → substring match is safe (long/specific names like "Mobile Legends: Bang Bang")
    re:       e.boundary ? new RegExp("\\b" + regexEscape(e.key) + "\\b") : null,
    reAlt:    (e.boundary && e.alt) ? new RegExp("\\b" + regexEscape(e.alt) + "\\b") : null,
  }));
  // Sort longest key first so a longer match beats a shorter one if both
  // could fire (e.g. "call of duty mobile" wins over "call of duty").
  entries.sort((a, b) => b.key.length - a.key.length);
  return entries;
}

function stBonusForRank(rank) {
  if (rank <= 10)  return 0.5;
  if (rank <= 100) return 0.4;
  if (rank <= 500) return 0.25;
  return 0.15;
}

function stMatchEntry(normalizedTitle, entry) {
  if (entry.re) {
    return entry.re.test(normalizedTitle) || (entry.reAlt && entry.reAlt.test(normalizedTitle));
  }
  return normalizedTitle.includes(entry.key) || (entry.alt && normalizedTitle.includes(entry.alt));
}

function precomputeStBonuses(items, stEntries) {
  const bonuses = new Map();
  if (!stEntries.length) return bonuses;
  for (const item of items) {
    const title = stNormalize(item.title_en || item.title || "");
    if (!title) continue;
    for (const entry of stEntries) {
      if (stMatchEntry(title, entry)) {
        bonuses.set(item.url, stBonusForRank(entry.rank));
        break; // longest-first means first match is best
      }
    }
  }
  return bonuses;
}

// Multi-source bonus: when 2+ distinct outlets cover the same ranked game
// within 24h, each matching article gets +0.3. Requires stEntries to be built.
function computeMultiSourceBonus(items, stEntries) {
  const now = Date.now();
  const WINDOW_MS = 24 * 3_600_000;
  const byGame = new Map(); // game key → [{url, site}]

  for (const item of items) {
    const t = itemEventTime(item);
    if (!t || now - t.getTime() > WINDOW_MS) continue;
    const title = stNormalize(item.title_en || item.title || "");
    if (!title) continue;
    for (const entry of stEntries) {
      if (stMatchEntry(title, entry)) {
        if (!byGame.has(entry.key)) byGame.set(entry.key, []);
        byGame.get(entry.key).push({ url: item.url, site: item.site_id });
        break;
      }
    }
  }

  const bonus = new Map();
  const sourceCount = new Map();
  for (const [, articles] of byGame) {
    const sites = new Set(articles.map((a) => a.site));
    if (sites.size >= 2) {
      for (const a of articles) {
        bonus.set(a.url, 0.3);
        sourceCount.set(a.url, sites.size);
      }
    }
  }
  return { bonus, sourceCount };
}

// Templated "why it matters" — keyword-first, then content_type, then ST/multi-source fallback.
function hotReason(item) {
  const title = (item.title_en || item.title || "").toLowerCase();
  const section = item.radar_section || "other";
  const reasons = Array.isArray(item.hot_reasons) ? item.hot_reasons : [];

  if (section === "industry_reports") return "Industry Reports: company, market, platform, or financial signal.";
  if (section === "game_releases") return "Game Releases: launch, release timing, beta, availability, shutdown, or platform release signal.";
  if (section === "game_announcements") return "Game Announcements: factual reveal, trailer, esports, roadmap, or major game update signal.";
  if (reasons.includes("business")) return "Hot because backend scoring found a business or market signal.";
  if (reasons.includes("platform_store")) return "Hot because backend scoring found a platform or store move.";

  if (["shuts down", "shut down", "shutting down", "bankruptcy", "bankrupt"].some((k) => title.includes(k)))
    return "Service ending — player base may be available for acquisition; rival exits the SEA market.";
  if (["acquired by", "acquisition", "merger"].some((k) => title.includes(k)))
    return "Industry consolidation — M&A reshaping the competitive landscape for SEA publishers.";
  if (["billion", "record breaking", "record-breaking", "all time high", "all-time high"].some((k) => title.includes(k)))
    return "Revenue or engagement milestone — benchmark signal for a title's live-service health.";
  if (["world championship", "world cup"].some((k) => title.includes(k)))
    return "Major esports event — peak viewership window and sponsorship opportunity for SEA.";
  if (["lawsuit", "sued", "legal action"].some((k) => title.includes(k)))
    return "Legal action — regulatory or IP risk that could affect publishing and distribution.";
  if (["ban wave", "ban waves"].some((k) => title.includes(k)))
    return "Enforcement action — platform policy signal affecting active players.";
  if (["server down", "maintenance"].some((k) => title.includes(k)))
    return "Service disruption on a known SEA title — direct impact to active player count.";
  if (["partnership", "collaboration announced"].some((k) => title.includes(k)))
    return "Partnership or IP deal — cross-promotion opportunity for SEA publishers to evaluate.";

  const etype = item.content_type;
  if (etype === "launch")   return "New title entering the market — assess competitive impact and SEA player migration risk.";
  if (etype === "business") return "Corporate or financial event — potential partner move, competitor shift, or market restructuring.";
  if (etype === "esports")  return "Esports event — viewership and sponsorship signal relevant to the SEA gaming audience.";
  if (etype === "update")   return "Significant content update — retention signal and indicator of live-service momentum.";
  if (etype === "platform") return "Platform or store change — affects how games reach and monetise SEA players.";

  if (state.multiSourceBonus.has(item.url))
    return "Multiple outlets are covering this story simultaneously — broad industry attention signal.";
  if (state.stBonus.has(item.url))
    return "Covers a top SEA revenue title — industry attention on a proven high-earner.";

  return "High-signal source coverage of a game-industry development.";
}

// --- Date range quick-select math -------------------------------------
// Calendar quarters: Q1 Jan-Mar, Q2 Apr-Jun, Q3 Jul-Sep, Q4 Oct-Dec.
// "Current Quarter" = quarter-start through today (e.g. on 1-Jul, Current
// Quarter is just 1-Jul, since Q3 starts 1-Jul). "Last Quarter" = the full
// previous quarter, start through end.

function quarterStartUTC(year, quarterIndex) {
  return new Date(Date.UTC(year, quarterIndex * 3, 1));
}

function currentQuarterRange(now) {
  const q = Math.floor(now.getUTCMonth() / 3);
  return { from: quarterStartUTC(now.getUTCFullYear(), q), to: now };
}

function lastQuarterRange(now) {
  const q = Math.floor(now.getUTCMonth() / 3);
  let year = now.getUTCFullYear();
  let lastQ = q - 1;
  if (lastQ < 0) {
    lastQ = 3;
    year -= 1;
  }
  const from = quarterStartUTC(year, lastQ);
  const to = new Date(Date.UTC(year, lastQ * 3 + 3, 0)); // day 0 of next month = last day of this quarter
  return { from, to };
}

function daysAgoRange(now, days) {
  const from = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  return { from, to: now };
}

function startOfDayUTC(date) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function endOfDayUTC(date) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 23, 59, 59, 999));
}

function applyDateRange(from, to) {
  state.dateFrom = startOfDayUTC(from);
  state.dateTo = endOfDayUTC(to);
  const readout = document.getElementById("gameDateRangeReadout");
  readout.textContent = `${formatDDMMMYYYY(state.dateFrom)} → ${formatDDMMMYYYY(state.dateTo)}`;
  readout.hidden = false;
}

function clearDateRange() {
  state.dateFrom = null;
  state.dateTo = null;
  const readout = document.getElementById("gameDateRangeReadout");
  readout.hidden = true;
  readout.textContent = "";
}

function handleDateRangePresetChange(value) {
  const now = new Date();
  const customField = document.getElementById("gameDateCustomField");
  const isCustom = value === "custom";
  customField.hidden = !isCustom;

  if (value === "all") {
    clearDateRange();
  } else if (value === "7d") {
    const r = daysAgoRange(now, 7);
    applyDateRange(r.from, r.to);
  } else if (value === "14d") {
    const r = daysAgoRange(now, 14);
    applyDateRange(r.from, r.to);
  } else if (value === "30d") {
    const r = daysAgoRange(now, 30);
    applyDateRange(r.from, r.to);
  } else if (value === "cq") {
    const r = currentQuarterRange(now);
    applyDateRange(r.from, r.to);
  } else if (value === "lq") {
    const r = lastQuarterRange(now);
    applyDateRange(r.from, r.to);
  } else if (isCustom) {
    const fromInput = document.getElementById("gameDateFrom");
    const toInput = document.getElementById("gameDateTo");
    if (!fromInput.value) fromInput.value = daysAgoRange(now, 30).from.toISOString().slice(0, 10);
    if (!toInput.value) toInput.value = now.toISOString().slice(0, 10);
    applyCustomDateInputs();
  }
  render();
}

function applyCustomDateInputs() {
  const fromInput = document.getElementById("gameDateFrom");
  const toInput = document.getElementById("gameDateTo");
  if (!fromInput.value || !toInput.value) return;
  applyDateRange(new Date(`${fromInput.value}T00:00:00Z`), new Date(`${toInput.value}T00:00:00Z`));
}

function itemParts(item) {
  const original = escapeHtml(item.title || "Untitled");
  const hasTranslation = item.title_en && item.title_en !== item.title;
  const mainTitle = hasTranslation ? escapeHtml(item.title_en) : original;
  const originalLine = hasTranslation
    ? `<span class="game-item-original">${original}</span>`
    : "";
  const source = escapeHtml(item.source || item.site_name || item.site_id || "");
  const date = formatDate(item.published_at || item.last_seen_at || item.first_seen_at);
  const regionLabel = escapeHtml(item.region_label || "Others");
  const url = escapeHtml(item.url || "#");
  const contentType = item.content_type && item.content_type !== "general"
    ? `<span class="game-item-type" data-type="${escapeHtml(item.content_type)}">${escapeHtml(item.content_type)}</span>`
    : "";
  const radarSection = item.radar_section
    ? `<span class="game-item-type" data-type="${escapeHtml(item.radar_section)}">${escapeHtml(RADAR_SECTION_LABELS[item.radar_section] || item.radar_section)}</span>`
    : "";
  const sourceTier = `<span class="game-source-tier">${escapeHtml(sourceTierLabel(sourceTierOf(item)))}</span>`;
  const hotScore = Number.isFinite(Number(item.hot_score))
    ? `<span class="game-score-badge">Score ${escapeHtml(item.hot_score)}</span>`
    : "";
  return { mainTitle, originalLine, source, date, regionLabel, url, contentType, radarSection, sourceTier, hotScore };
}

function renderItem(item) {
  const { mainTitle, originalLine, source, date, regionLabel, url, radarSection, sourceTier, hotScore } = itemParts(item);
  return `
    <a class="game-item-row" href="${url}" target="_blank" rel="noopener noreferrer">
      <span class="game-item-title">${mainTitle}</span>
      ${originalLine}
      <span class="game-item-meta">
        <span class="game-item-source">${source}</span>
        <span class="game-item-region">${regionLabel}</span>
        ${radarSection}
        ${sourceTier}
        ${hotScore}
        <span class="game-item-date">${date}</span>
      </span>
    </a>`;
}

function renderFeaturedItem(item) {
  const { mainTitle, originalLine, source, date, regionLabel, url, radarSection, sourceTier, hotScore } = itemParts(item);
  const why = escapeHtml(hotReason(item));
  const multiCount = state.multiSourceSources.get(item.url);
  const multiSourceBadge = multiCount
    ? `<span class="game-source-count">${multiCount} sources</span>`
    : "";
  return `
    <a class="game-item-featured" href="${url}" target="_blank" rel="noopener noreferrer">
      <span class="game-item-title">${mainTitle}</span>
      ${originalLine}
      <div class="game-key-why">${why}</div>
      <span class="game-item-meta">
        <span class="game-item-source">${source}</span>
        <span class="game-item-region">${regionLabel}</span>
        ${radarSection}
        ${sourceTier}
        ${multiSourceBadge}
        ${hotScore}
        <span class="game-item-date">${date}</span>
      </span>
    </a>`;
}

function renderClusterCard(cluster) {
  const main = clusterMainItem(cluster);
  const { mainTitle, originalLine, source, date, regionLabel, url, radarSection } = itemParts(main);
  const gameName = cluster.game_name
    ? `<span class="game-cluster-game">${escapeHtml(cluster.game_name)}</span>`
    : "";
  const sources = (cluster.sources || []).map(escapeHtml).join(", ");
  const sourceCount = Number(cluster.source_count || clusterItems(cluster).length || 0);
  const score = Number(cluster.cluster_score || 0);
  const mainSource = escapeHtml(source || main.site_name || main.site_id || "Unknown source");
  return `
    <a class="game-item-featured game-cluster-card" href="${url}" target="_blank" rel="noopener noreferrer">
      <span class="game-item-title">${mainTitle}</span>
      ${originalLine}
      <div class="game-cluster-summary">
        ${gameName}
        ${radarSection}
        <span class="game-source-count">${sourceCount} sources</span>
        <span class="game-score-badge">Cluster ${escapeHtml(score)}</span>
      </div>
      <span class="game-item-meta">
        <span class="game-item-source">Main: ${mainSource}</span>
        <span class="game-item-region">${regionLabel}</span>
        <span class="game-item-date">${date}</span>
      </span>
      <div class="game-cluster-sources">${sources}</div>
    </a>`;
}

function renderEntry(entry) {
  return entry.kind === "cluster" ? renderClusterCard(entry.data) : renderItem(entry.data);
}

function renderFeaturedEntry(entry) {
  return entry.kind === "cluster" ? renderClusterCard(entry.data) : renderFeaturedItem(entry.data);
}

function renderHotSection(section, entries) {
  if (!entries.length) return "";
  const label = RADAR_SECTION_LABELS[section] || section;
  const clusters = entries.filter((entry) => entry.kind === "cluster")
    .sort((a, b) => hotEntryScore(b) - hotEntryScore(a));
  const items = entries.filter((entry) => entry.kind === "item")
    .sort((a, b) => {
      const scoreDiff = hotEntryScore(b) - hotEntryScore(a);
      if (scoreDiff) return scoreDiff;
      const aTime = entryEventTime(a);
      const bTime = entryEventTime(b);
      return (bTime ? bTime.getTime() : 0) - (aTime ? aTime.getTime() : 0);
    });
  const html = [...clusters, ...items].map(renderFeaturedEntry).join("");
  return `
    <section class="game-hot-section" data-section="${escapeHtml(section)}">
      <div class="game-hot-section-head">
        <h3>${escapeHtml(label)}</h3>
        <span>${entries.length.toLocaleString()} stories</span>
      </div>
      ${html}
    </section>`;
}

function renderHotSections(entries) {
  return HOT_SECTION_ORDER
    .map((section) => renderHotSection(section, entries.filter((entry) => entryRadarSection(entry) === section)))
    .filter(Boolean)
    .join("");
}

// Multi-word search: every space-separated term must appear somewhere in the
// haystack, but terms don't need to be contiguous - "gaming sdk" should match
// a title like "Gaming Chat SDK by CometChat".
function matchesQuery(item, query) {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const hay = `${item.title || ""} ${item.title_en || ""} ${item.source || ""}`.toLowerCase();
  return terms.every((term) => hay.includes(term));
}

function matchesEntryQuery(entry, query) {
  if (!query) return true;
  if (entry.kind === "item") return matchesQuery(entry.data, query);
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const main = clusterMainItem(entry.data);
  const hay = [
    main.title,
    main.title_en,
    main.source,
    entry.data.game_name,
    entry.data.story_type,
    entry.data.radar_section,
    ...(entry.data.sources || []),
  ].join(" ").toLowerCase();
  return terms.every((term) => hay.includes(term));
}

function currentList() {
  const usingHotView = state.region === "ALL";
  const clusteredUrls = new Set();
  state.clusters.forEach((cluster) => {
    clusterItems(cluster).forEach((it) => {
      if (it.url) clusteredUrls.add(it.url);
    });
  });
  const hotStandalone = state.hotItems
    .filter((it) => !clusteredUrls.has(it.url))
    .map((it) => ({ kind: "item", data: it }));
  let list = usingHotView && state.clusters.length
    ? [
        ...state.clusters.map((cluster) => ({ kind: "cluster", data: cluster })),
        ...hotStandalone,
      ]
    : state.items.map((it) => ({ kind: "item", data: it }));

  if (state.region === "ALL") {
    list = list.filter((entry) => (
      entry.kind === "cluster"
        ? clusterItems(entry.data).some((it) => it.region !== "MISC")
        : entry.data.region !== "MISC"
    ));
    list = list.filter((entry) => HOT_SECTION_ORDER.includes(entryRadarSection(entry)));
  } else {
    list = list.filter((entry) => entryMatchesRegion(entry, state.region));
  }

  if (state.radarSection) {
    list = list.filter((entry) => entryMatchesRadarSection(entry, state.radarSection));
  }

  if (state.sourceTier) {
    list = list.filter((entry) => entryMatchesSourceTier(entry, state.sourceTier));
  }

  if (state.specificSource) {
    list = list.filter((entry) => entryMatchesSpecificSource(entry, state.specificSource));
  }

  list = list.filter(entryMatchesDateRange);

  if (state.query) {
    list = list.filter((entry) => matchesEntryQuery(entry, state.query));
  }

  const noOtherFilters = !state.sourceTier && !state.specificSource
    && !state.radarSection && !state.dateFrom && !state.query;
  if (noOtherFilters) {
    if (usingHotView) {
      list = list.slice(0, HOT_LIMIT);
    } else {
      list = list
        .sort((a, b) => {
          const aTime = entryEventTime(a);
          const bTime = entryEventTime(b);
          return (bTime ? bTime.getTime() : 0) - (aTime ? aTime.getTime() : 0);
        })
        .slice(0, HOT_LIMIT)
    }
  }

  return list;
}

const KEY_SIGNALS_COUNT = 10;

function currentFullFeedList() {
  let list = state.items.map((it) => ({ kind: "item", data: it }));

  if (state.region === "ALL") {
    list = list.filter((entry) => entry.data.region !== "MISC");
  } else {
    list = list.filter((entry) => entryMatchesRegion(entry, state.region));
  }

  if (state.radarSection) {
    list = list.filter((entry) => entryMatchesRadarSection(entry, state.radarSection));
  }
  if (state.sourceTier) {
    list = list.filter((entry) => entryMatchesSourceTier(entry, state.sourceTier));
  }
  if (state.specificSource) {
    list = list.filter((entry) => entryMatchesSpecificSource(entry, state.specificSource));
  }

  list = list.filter(entryMatchesDateRange);

  if (state.query) {
    list = list.filter((entry) => matchesEntryQuery(entry, state.query));
  }

  return list
    .sort((a, b) => {
      const aTime = entryEventTime(a);
      const bTime = entryEventTime(b);
      return (bTime ? bTime.getTime() : 0) - (aTime ? aTime.getTime() : 0);
    })
    .slice(0, HOT_LIMIT);
}

function render() {
  const body = document.getElementById("gamePanelBody");
  const keyPanel = document.getElementById("gameKeySignalsPanel");
  const keyBody = document.getElementById("gameKeySignalsBody");
  const list = currentList();
  const fullFeedList = currentFullFeedList();
  const title = document.getElementById("gamePanelTitle");
  const eyebrow = document.getElementById("gamePanelEyebrow");

  if (state.region === "ALL") {
    const hotHtml = renderHotSections(list);
    keyPanel.hidden = !hotHtml;
    keyBody.innerHTML = hotHtml;
    body.innerHTML = fullFeedList.length
      ? `<div class="game-item-list">${fullFeedList.map(renderEntry).join("")}</div>`
      : `<div class="empty-state">No full-feed articles match this view yet.</div>`;
    title.textContent = "Full Feed";
    eyebrow.textContent = "FULL FEED";
    if (!hotHtml && !fullFeedList.length) {
      body.innerHTML = `<div class="empty-state">No game news matches this view yet.</div>`;
    }
    return;
  }

  if (!list.length) {
    keyPanel.hidden = true;
    body.innerHTML = `<div class="empty-state">No game news matches this view yet.</div>`;
    title.textContent = `${REGION_LABELS[state.region]} Full Feed`;
    eyebrow.textContent = `${REGION_LABELS[state.region].toUpperCase()} FEED`;
    return;
  }

  const regionLabel = state.region === "ALL" ? "" : `${REGION_LABELS[state.region]} `;
  keyPanel.hidden = true;
  keyBody.innerHTML = "";
  body.innerHTML = `<div class="game-item-list">${list.map(renderEntry).join("")}</div>`;
  title.textContent = `${regionLabel}Full Feed`;
  eyebrow.textContent = `${regionLabel.toUpperCase().trim()} FEED`;
}

function updateTabCounts() {
  const miscCount = state.byRegion.MISC || 0;
  const total = state.items.length;
  document.querySelectorAll("#gameTabs .section-tab").forEach((btn) => {
    const region = btn.dataset.region;
    const count = region === "ALL" ? total - miscCount : (state.byRegion[region] || 0);
    const strong = btn.querySelector("strong");
    if (strong) strong.textContent = count.toLocaleString();
  });
}

function setRegion(region) {
  state.region = region;
  document.querySelectorAll("#gameTabs .section-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.region === region);
  });
  const select = document.getElementById("gameRegionSelect");
  if (select) select.value = region;
  render();
}

function populateSpecificSourceOptions() {
  const select = document.getElementById("gameSpecificSourceSelect");
  const sources = new Map();
  state.items.forEach((it) => {
    if (it.site_id && !sources.has(it.site_id)) {
      sources.set(it.site_id, it.site_name || it.source || it.site_id);
    }
  });
  const sorted = [...sources.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  select.innerHTML = `<option value="">All sites</option>` +
    sorted.map(([siteId, name]) => `<option value="${escapeHtml(siteId)}">${escapeHtml(name)}</option>`).join("");
}

function wireControls() {
  document.getElementById("gameTabs").addEventListener("click", (evt) => {
    const btn = evt.target.closest(".section-tab");
    if (!btn) return;
    setRegion(btn.dataset.region);
  });

  document.getElementById("gameRegionSelect").addEventListener("change", (evt) => {
    setRegion(evt.target.value);
  });

  document.getElementById("gameRadarSectionSelect").addEventListener("change", (evt) => {
    state.radarSection = evt.target.value;
    render();
  });

  document.getElementById("gameSourceTierSelect").addEventListener("change", (evt) => {
    state.sourceTier = evt.target.value;
    render();
  });

  document.getElementById("gameSpecificSourceSelect").addEventListener("change", (evt) => {
    state.specificSource = evt.target.value;
    render();
  });

  document.getElementById("gameDateRangePreset").addEventListener("change", (evt) => {
    handleDateRangePresetChange(evt.target.value);
  });

  document.getElementById("gameDateFrom").addEventListener("change", applyAndRenderCustomDates);
  document.getElementById("gameDateTo").addEventListener("change", applyAndRenderCustomDates);

  document.getElementById("gameSearch").addEventListener("input", (evt) => {
    state.query = evt.target.value.trim();
    render();
  });
}

function applyAndRenderCustomDates() {
  applyCustomDateInputs();
  render();
}

async function fetchJson(url) {
  const res = await fetch(`${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function isLocalPreview() {
  return LOCAL_PREVIEW_HOSTS.has(window.location.hostname);
}

async function fetchGameNewsData() {
  const localPreview = isLocalPreview();
  const primaryUrl = isLocalPreview() ? FALLBACK_DATA_URL : LIVE_DATA_URL;
  const fallbackUrl = isLocalPreview() ? LIVE_DATA_URL : FALLBACK_DATA_URL;
  try {
    const data = await fetchJson(primaryUrl);
    return { data, live: primaryUrl === LIVE_DATA_URL, localPreview, usedFallback: false, primaryErr: null };
  } catch (primaryErr) {
    try {
      const data = await fetchJson(fallbackUrl);
      return { data, live: fallbackUrl === LIVE_DATA_URL, localPreview, usedFallback: true, primaryErr };
    } catch (fallbackErr) {
      throw { primaryErr, fallbackErr };
    }
  }
}

function renderSourceHealth(sourceHealth) {
  const el = document.getElementById("gameSourceHealthTable");
  if (!el) return;
  if (!sourceHealth || !Array.isArray(sourceHealth.sources) || !sourceHealth.sources.length) {
    el.innerHTML = `<div class="empty-state">No live source-health data yet (showing historical backfill).</div>`;
    return;
  }
  const rows = [...sourceHealth.sources].sort((a, b) => (b.ok - a.ok) || b.item_count - a.item_count);
  el.innerHTML = [
    `<div class="source-table-row source-table-head"><span>Source</span><span>Items</span><span>Duration</span><span>Status</span></div>`,
    ...rows.map((s) => `
      <div class="source-table-row">
        <span>${escapeHtml(s.site_name || s.site_id)}</span>
        <span>${(s.item_count || 0).toLocaleString()}</span>
        <span>${s.duration_ms ? `${s.duration_ms}ms` : "-"}</span>
        <span class="${s.ok ? "ok" : "bad"}">${s.ok ? "Healthy" : "Failed"}</span>
      </div>`),
  ].join("");
}

async function init() {
  wireControls();
  let data;
  let live = true;
  let localPreview = false;
  let usedFallback = false;
  try {
    ({ data, live, localPreview, usedFallback } = await fetchGameNewsData());
  } catch (err) {
    document.getElementById("gamePanelBody").innerHTML =
      `<div class="empty-state">Could not load game news data (primary: ${escapeHtml(err.primaryErr?.message)}; fallback: ${escapeHtml(err.fallbackErr?.message)}).</div>`;
    document.getElementById("gameStatusPill").textContent = "Load failed";
    return;
  }

  state.items = data.items || [];
  state.hotItems = data.hot_news || [];
  state.clusters = data.game_story_clusters || [];
  state.byRegion = data.by_region || {};

  const sourceCount = new Set(state.items.map((it) => it.site_id)).size;
  const countryRegionCount = Object.keys(REGION_LABELS).filter(
    (code) => !["ALL", "GLOBAL", "OTHERS", "MISC"].includes(code)
  ).length;
  document.getElementById("gameStatCount").textContent = state.items.length.toLocaleString();
  document.getElementById("gameStatSources").textContent = String(sourceCount);
  document.getElementById("gameStatRegions").textContent = String(countryRegionCount);
  document.getElementById("gameUpdatedLabel").textContent = data.generated_at
    ? formatDDMMMYYYY(new Date(data.generated_at))
    : "Unknown";

  const pill = document.getElementById("gameStatusPill");
  const health = data.source_health;
  const advancedSummary = document.getElementById("gameAdvancedSummary");
  if (localPreview && !live) {
    pill.textContent = "Local preview data";
    pill.classList.remove("warn");
    advancedSummary.textContent = health
      ? `Local preview data · ${health.ok_count}/${health.total_count} sources healthy`
      : "Local preview data";
  } else if (live && health) {
    pill.textContent = `${health.ok_count}/${health.total_count} sources healthy`;
    pill.classList.toggle("warn", health.ok_count < health.total_count);
    advancedSummary.textContent = `Live · ${health.ok_count}/${health.total_count} sources healthy`;
  } else if (live) {
    pill.textContent = "Live";
    pill.classList.remove("warn");
    advancedSummary.textContent = "Live";
  } else {
    pill.textContent = usedFallback ? "Fallback data (live branch unreachable)" : "Fallback data";
    pill.classList.add("warn");
    advancedSummary.textContent = usedFallback ? "Fallback data, live branch unreachable" : "Fallback data";
  }
  renderSourceHealth(health);
  populateSpecificSourceOptions();

  updateTabCounts();
  render();

  // Load Sensor Tower rank index in the background — non-blocking.
  // First render uses Phase 1 scores only; re-renders with ST bonus once loaded.
  // Fails silently if the file is missing (e.g. fresh clone without the data/).
  false && fetchJson(ST_RANK_URL)
    .then((rankData) => {
      const stEntries = buildStIndex(rankData);
      state.stBonus = precomputeStBonuses(state.items, stEntries);
      const { bonus: msBonus, sourceCount: msSources } = computeMultiSourceBonus(state.items, stEntries);
      state.multiSourceBonus = msBonus;
      state.multiSourceSources = msSources;
      if (state.stBonus.size > 0 || state.multiSourceBonus.size > 0) render();
    })
    .catch(() => { /* no ST index — Phase 1 scores remain in effect */ });
}

document.addEventListener("DOMContentLoaded", init);
