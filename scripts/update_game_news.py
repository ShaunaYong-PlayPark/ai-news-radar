#!/usr/bin/env python3
"""Live, recurring Game News fetch pipeline.

Reuses the existing general-purpose scrapers from update_news.py (TopHub,
Iris, Buzzing, TechURLs, NewsNow, Zeli - all broad "what's trending" sources
that happen to carry real game content alongside everything else) for
China/global coverage, plus a config-driven generic RSS fetcher
(scripts/game_sources.py) for dedicated single-country SEA outlets.

Unlike update_news.py's main pipeline, nothing here is gated by AI relevance
scoring - the quality gate is the game-keyword + junk-source rules in
scripts/game_news_classify.py instead.

State model: maintains a rolling window (default ~110 days, enough to cover
"last quarter" plus buffer) across runs. On the very first run (no previous
output to load), bootstraps from the historical seed
(data/game-news-seed.json) so the live feed doesn't start empty. Output is
intended to be committed to a dedicated orphan branch (see
.github/workflows/update-game-news.yml), NOT accumulated into master's
history - that's the exact git-bloat mistake the AI News pipeline made.

Usage:
  python scripts/update_game_news.py --output data/game-news.json \
      [--previous PATH] [--seed data/game-news-seed.json] \
      [--retention-days 110]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402

from game_news_classify import (  # noqa: E402
    REGION_ORDER,
    classify_and_tag,
    dedupe_by_title,
    event_time_str,
    is_junk,
    score_hot_news,
)
from game_sources import DIRECT_RSS_SOURCES  # noqa: E402
from rsshub_sources import RSSHUB_BRIDGE_SOURCES  # noqa: E402
from update_news import (  # noqa: E402
    RawItem,
    fetch_buzzing,
    fetch_iris,
    fetch_newsnow,
    fetch_techurls,
    fetch_tophub,
    fetch_zeli,
    parse_date_any,
)

try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None

DEFAULT_RETENTION_DAYS = 110
DEFAULT_TRANSLATE_MAX_NEW = 800  # ~60s/run in testing; backfills the historical backlog in ~1-2 weeks
HOT_NEWS_LIMIT = 120
HOT_NEWS_RECENT_DAYS = 7
HOT_NEWS_WIDE_DAYS = 30
GAME_STORY_CLUSTER_LIMIT = 80
GAME_STORY_CLUSTER_RECENT_DAYS = 30
DIRECT_SOURCE_TYPES = {
    source["site_id"]: ("dedicated_game_media" if source.get("dedicated", False) else "tech_portal")
    for source in DIRECT_RSS_SOURCES
}
RSSHUB_SOURCE_TYPES = {source["site_id"]: "dedicated_game_media" for source in RSSHUB_BRIDGE_SOURCES}


def translate_to_en(session: requests.Session, text: str) -> str | None:
    """Free, keyless Google Translate web endpoint, auto-detecting source language.

    Same trick already used by translate_to_zh_cn() in update_news.py (no API
    key/billing needed) - just pointed at tl=en instead of tl=zh-CN, since
    game sources span Chinese, Thai, Vietnamese, and Indonesian. If the text
    is already English, Google returns it unchanged, which we treat as "no
    translation needed" rather than a failure.
    """
    s = (text or "").strip()
    if not s:
        return None
    try:
        r = session.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": s},
            timeout=12,
        )
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list) or not payload:
            return None
        segs = payload[0]
        if not isinstance(segs, list):
            return None
        translated = "".join(str(seg[0]) for seg in segs if isinstance(seg, list) and seg and seg[0])
        translated = translated.strip()
        if translated and translated != s:
            return translated
    except Exception:  # noqa: BLE001
        return None
    return None

# Broad "what's trending" scrapers - not game-specific, so every item goes
# through the same quality gate as everything else in game_news_classify.
GENERIC_TASKS = [
    ("tophub", "TopHub", fetch_tophub),
    ("iris", "Info Flow", fetch_iris),
    ("buzzing", "Buzzing", fetch_buzzing),
    ("techurls", "TechURLs", fetch_techurls),
    ("newsnow", "NewsNow", fetch_newsnow),
    ("zeli", "Zeli", fetch_zeli),
]
GENERIC_SOURCE_TYPES = {site_id: "aggregator" for site_id, _site_name, _fn in GENERIC_TASKS}

SOURCE_REPUTATION = {
    "rpg site": 1.0,
    "gamespot": 0.95,
    "gamespot asia": 0.95,
    "ign sea": 0.9,
    "ign southeast asia": 0.9,
    "gamesindustry.biz": 0.9,
    "pc gamer": 0.85,
    "gamesradar+": 0.8,
    "polygon": 0.8,
    "rpgfan": 0.8,
    "game rant": 0.7,
    "gamingonphone": 0.7,
    "pocketgamer.biz": 0.7,
}
SOURCE_TYPE_QUALITY = {"dedicated_game_media": 3, "business_industry_media": 3, "regional_game_media": 2.7, "mixed_portal": 2, "tech_portal": 2, "aggregator": 1}
SOURCE_TIER_LABELS = {
    "major_gaming_media": "Major gaming media",
    "regional_gaming_media": "Regional gaming media",
    "business_industry_media": "Business / industry media",
    "aggregator": "Aggregators",
    "mixed_portal": "Mixed portals",
}
MAJOR_GAMING_MEDIA_IDS = {
    "pcgamer",
    "gamerant",
    "gamesradar",
    "polygon",
    "shacknews",
    "siliconera",
    "pockettactics",
    "ign_sea",
    "rpgsite",
    "gamespot_asia",
    "gamingonphone",
    "esports_net",
    "dotesports",
}
BUSINESS_INDUSTRY_SOURCE_IDS = {
    "gamesindustry",
    "gamesindustry_biz",
    "pocketgamer_biz",
    "pocketgamerbiz",
    "mobilegamer_biz",
    "virtuos_games",
    "vnexpress_business",
    "bangkokpost_business",
}
BUSINESS_INDUSTRY_SOURCE_RE = re.compile(
    r"gamesindustry\.biz|pocketgamer\.biz|mobilegamer\.biz|gameindustry|virtuos|vnexpress business|bangkok post business",
    re.I,
)


def fetch_rss_source(session: requests.Session, source: dict[str, Any], now: datetime) -> list[RawItem]:
    """Generic single-feed RSS/Atom fetcher driven by game_sources.py config."""
    if feedparser is None:
        raise RuntimeError("feedparser is required for SEA RSS sources")

    resp = session.get(source["feed_url"], timeout=30, headers={"User-Agent": "ai-news-radar-game-bot/1.0"})
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    out: list[RawItem] = []
    for entry in parsed.entries:
        title = str(entry.get("title", "")).strip()
        url = str(entry.get("link", "")).strip()
        if not title or not url:
            continue
        published = (
            parse_date_any(entry.get("published"), now)
            or parse_date_any(entry.get("updated"), now)
            or parse_date_any(entry.get("pubDate"), now)
        )
        out.append(
            RawItem(
                site_id=source["site_id"],
                site_name=source["site_name"],
                source=source["site_name"],
                title=title,
                url=url,
                published_at=published,
                meta={
                    "region_override": source["region"],
                    "source_dedicated": source.get("dedicated", False),
                    "source_type": "dedicated_game_media" if source.get("dedicated", False) else "tech_portal",
                    "ingestion_path": "direct_feed",
                },
            )
        )
    return out


def rsshub_transform_url(base_url: str, source: dict[str, Any]) -> str:
    """Build a /rsshub/transform/html URL per RSSHub's own spec:
    https://github.com/DIYgod/RSSHub/blob/master/lib/routes/rsshub/transform/html.ts
    (path: /transform/html/:url/:routeParams - both segments URL-encoded,
    routeParams itself being a URL-encoded query string of CSS selectors).
    """
    params: dict[str, str] = {"item": source["item"], "itemTitle": source["item_title"], "itemLink": source["item_link"]}
    if source.get("item_pub_date"):
        params["itemPubDate"] = source["item_pub_date"]
    route_params = quote(urlencode(params), safe="")
    target = quote(source["target_url"], safe="")
    return f"{base_url.rstrip('/')}/rsshub/transform/html/{target}/{route_params}"


def fetch_rsshub_bridge_source(session: requests.Session, source: dict[str, Any], now: datetime) -> list[RawItem]:
    """Generic no-native-feed fetcher, bridged through a local RSSHub instance.

    Only called when RSSHUB_BRIDGE_ENABLED=1 - see scripts/rsshub_sources.py
    for why this is a separate, hand-curated registry rather than folded
    into game_sources.py's direct-feed list.
    """
    if feedparser is None:
        raise RuntimeError("feedparser is required for RSSHub bridge sources")

    base_url = os.environ.get("RSSHUB_BASE_URL", "http://localhost:1200")
    feed_url = rsshub_transform_url(base_url, source)
    resp = session.get(feed_url, timeout=30, headers={"User-Agent": "ai-news-radar-game-bot/1.0"})
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    out: list[RawItem] = []
    for entry in parsed.entries:
        title = str(entry.get("title", "")).strip()
        url = str(entry.get("link", "")).strip()
        if not title or not url:
            continue
        published = (
            parse_date_any(entry.get("published"), now)
            or parse_date_any(entry.get("updated"), now)
            or parse_date_any(entry.get("pubDate"), now)
        )
        out.append(
            RawItem(
                site_id=source["site_id"],
                site_name=source["site_name"],
                source=source["site_name"],
                title=title,
                url=url,
                published_at=published,
                meta={
                    "region_override": source.get("region_override"),
                    "source_type": "dedicated_game_media",
                    "ingestion_path": "rsshub_bridge",
                },
            )
        )
    return out


def parse_event_datetime(record: dict[str, Any]) -> datetime | None:
    ts_str = event_time_str(record)
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def hot_news_recency_bucket(record: dict[str, Any], now: datetime) -> int:
    ts = parse_event_datetime(record)
    if ts is None:
        return 0
    age_days = max(0.0, (now - ts).total_seconds() / 86_400)
    if age_days <= HOT_NEWS_RECENT_DAYS:
        return 2
    if age_days <= HOT_NEWS_WIDE_DAYS:
        return 1
    return 0


def hot_news_sort_key(record: dict[str, Any], now: datetime) -> tuple[int, int, float]:
    ts = parse_event_datetime(record)
    ts_value = ts.timestamp() if ts else 0.0
    return (hot_news_recency_bucket(record, now), int(record.get("hot_score") or 0), ts_value)


def infer_source_type(record: dict[str, Any]) -> str:
    existing = record.get("source_type")
    if existing:
        return str(existing)
    site_id = str(record.get("site_id") or "")
    if site_id in DIRECT_SOURCE_TYPES:
        return DIRECT_SOURCE_TYPES[site_id]
    if site_id in RSSHUB_SOURCE_TYPES:
        return RSSHUB_SOURCE_TYPES[site_id]
    if site_id in GENERIC_SOURCE_TYPES:
        return GENERIC_SOURCE_TYPES[site_id]
    if record.get("source_dedicated"):
        return "dedicated_game_media"
    if record.get("ingestion_path") == "direct_feed":
        return "tech_portal"
    return "aggregator"


def infer_source_tier(record: dict[str, Any]) -> str:
    existing = record.get("source_tier")
    if existing in SOURCE_TIER_LABELS:
        return str(existing)
    site_id = str(record.get("site_id") or "")
    source_name = str(record.get("source") or record.get("site_name") or "")
    if site_id in GENERIC_SOURCE_TYPES:
        return "aggregator"
    if site_id in BUSINESS_INDUSTRY_SOURCE_IDS or BUSINESS_INDUSTRY_SOURCE_RE.search(source_name):
        return "business_industry_media"
    if site_id in MAJOR_GAMING_MEDIA_IDS:
        return "major_gaming_media"
    source_type = infer_source_type(record)
    if source_type == "dedicated_game_media":
        region = str(record.get("region_override") or record.get("region") or "")
        return "regional_gaming_media" if region not in {"GLOBAL", "OTHERS", ""} else "major_gaming_media"
    if source_type == "aggregator":
        return "aggregator"
    return "mixed_portal"


def add_source_tier_fields(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    tier = infer_source_tier(out)
    out["source_tier"] = tier
    out["source_tier_label"] = SOURCE_TIER_LABELS[tier]
    return out


def normalize_story_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(text).lower())).strip()


def load_game_rank_entries(path: Path | None = None, limit: int = 1000) -> list[dict[str, Any]]:
    path = path or (REPO_ROOT / "data" / "game-rank-index.json")
    payload = load_json(path)
    if not payload:
        return []
    entries = []
    for entry in payload.get("entries", [])[:limit]:
        keys = [entry.get("key"), entry.get("alt"), entry.get("name")]
        normalized_keys = [normalize_story_text(str(key)) for key in keys if key]
        normalized_keys = [key for key in normalized_keys if len(key) >= 4]
        if not normalized_keys:
            continue
        entries.append({**entry, "normalized_keys": normalized_keys})
    entries.sort(key=lambda entry: max(len(key) for key in entry["normalized_keys"]), reverse=True)
    return entries


def match_known_game_name(title: str, rank_entries: list[dict[str, Any]]) -> str | None:
    normalized = normalize_story_text(title)
    if not normalized:
        return None
    for entry in rank_entries:
        for key in entry["normalized_keys"]:
            if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", normalized):
                return str(entry.get("name") or key)
    return None


def known_game_is_subject(title: str, game_name: str) -> bool:
    normalized_title = normalize_story_text(title)
    normalized_game = normalize_story_text(game_name)
    if not normalized_title or not normalized_game:
        return False
    if normalized_title.startswith(f"{normalized_game} "):
        return True
    subject_patterns = [
        rf"(?<!\w){re.escape(normalized_game)}(?!\w).{{0,80}}\b(?:launch|release|released|trailer|gameplay|"
        rf"showcase|announced|revealed|pre registration|pre order|beta|early access|shutdown|delisted|"
        rf"tournament|championship|qualifier)\b",
        rf"\b(?:launch|release|released|trailer|gameplay|showcase|announced|revealed|coming to|pre registration|"
        rf"pre order|beta|early access).{{0,80}}(?<!\w){re.escape(normalized_game)}(?!\w)",
    ]
    if any(re.search(pattern, normalized_title) for pattern in subject_patterns):
        return True
    broad_context = re.search(
        r"unreal engine|unreal editor|uefn|engine 6|claude|gemini|developer policy|subscription|"
        r"publishing games|app store|google play|steam business|earnings|revenue|layoffs?|acquisition|funding",
        normalized_title,
    )
    return not broad_context


def extract_quoted_game_name(title: str) -> str | None:
    quote_patterns = [
        r'"([^"]{3,80})"',
        r"'([^']{3,80})'",
        r"“([^”]{3,80})”",
        r"‘([^’]{3,80})’",
        r"《([^》]{3,80})》",
        r"「([^」]{3,80})」",
        r"『([^』]{3,80})』",
        r"【([^】]{3,80})】",
    ]
    for pattern in quote_patterns:
        match = re.search(pattern, title)
        if match:
            candidate = match.group(1).strip().strip(":-–—")
            if (
                len(candidate.split()) <= 6
                and re.search(r"[A-Z0-9]", candidate)
                and not re.search(r"\b(why|how|what|when|where|this|that|still|only|new|basically)\b", candidate, re.I)
                and not re.search(r"[,.!?;:]", candidate)
            ):
                return candidate
    return None


def extract_prefix_game_name(title: str) -> str | None:
    pattern = re.compile(
        r"^(.{3,80}?)(?:\s+(?:launch(?:es|ed|ing)?|gets?|sets?|confirms?|announces?|reveals?|opens?|"
        r"trailer|gameplay|showcase|is now available|available now|out now|coming to|pre[- ]?registration|"
        r"release date|closed beta|open beta|early access|delayed|postponed|shutdown|shut down|delisted))\b",
        re.I,
    )
    match = pattern.search(title)
    if not match:
        return None
    candidate = re.sub(r"^(new|the|a|an)\s+", "", match.group(1).strip().strip(":-–—"), flags=re.I)
    candidate = re.sub(r"\s+(officially|finally|reportedly)$", "", candidate, flags=re.I).strip()
    if len(candidate) < 3 or re.search(
        r"\b(report|rumou?r|subreddit|fans?|devs?|developers?|company|studio|publisher|market|industry|"
        r"revenue|earnings|layoffs?|esports world cup|world championship)\b",
        candidate,
        re.I,
    ):
        return None
    if re.fullmatch(
        r"(nintendo|sony|microsoft|xbox|playstation|tencent|netease|krafton|nexon|hoyoverse|riot|"
        r"roblox|ubisoft|electronic arts|ea|take[- ]two|epic games|valve|sega|capcom|konami)",
        candidate,
        re.I,
    ):
        return None
    if len(candidate.split()) > 8:
        return None
    return candidate


def extract_story_topic_key(item: dict[str, Any]) -> tuple[str, str] | None:
    title = normalize_story_text(str(item.get("title_en") or item.get("title") or ""))
    if "esports world cup" in title:
        return ("Esports World Cup", "esports world cup")
    if "world championship" in title and "esports" in title:
        return ("Esports World Championship", "esports world championship")
    if "xbox" in title and "revenue" in title:
        return ("Xbox revenue", "xbox revenue")
    if "xbox" in title and re.search(r"\blayoffs?\b|cut|closure|closing", title):
        return ("Xbox layoffs", "xbox layoffs")
    if "microsoft" in title and re.search(r"\bq[1-4]\b|earnings|revenue", title):
        return ("Microsoft earnings", "microsoft earnings")
    if "unreal engine" in title or "unreal editor" in title or "uefn" in title:
        return ("Unreal Engine", "unreal engine")
    if "roblox" in title and re.search(r"developer|subscription|publishing|kids|select accounts|policy", title):
        return ("Roblox platform policy", "roblox platform policy")
    if "epic games" in title and "lore" in title and "version control" in title:
        return ("Epic Games Lore version control", "epic games lore version control")
    if "pokemon" in title and "best selling" in title:
        return ("Pokemon sales", "pokemon sales")
    return None


def story_signature(title: str) -> str:
    normalized = normalize_story_text(title)
    tokens = [
        token for token in normalized.split()
        if token not in {"the", "a", "an", "to", "for", "of", "and", "on", "in", "with", "is", "now"}
    ]
    return " ".join(tokens[:10])


def detect_game_name(item: dict[str, Any], rank_entries: list[dict[str, Any]]) -> str | None:
    title = f"{item.get('title_en') or ''} {item.get('title') or ''}".strip()
    quoted = extract_quoted_game_name(title)
    if quoted:
        return quoted
    known = match_known_game_name(title, rank_entries)
    if known and known_game_is_subject(title, known):
        return known
    return extract_prefix_game_name(title)


def cluster_key_for_item(item: dict[str, Any], rank_entries: list[dict[str, Any]]) -> tuple[str, str, str | None]:
    section = str(item.get("radar_section") or "other")
    topic = extract_story_topic_key(item)
    if topic:
        _topic_name, topic_key = topic
        return ("story", topic_key, None)
    game_name = detect_game_name(item, rank_entries)
    if game_name:
        return ("game", normalize_story_text(game_name), game_name)
    return ("title", story_signature(str(item.get("title_en") or item.get("title") or "")), None)


def source_quality(item: dict[str, Any]) -> float:
    source_name = normalize_story_text(str(item.get("source") or item.get("site_name") or item.get("site_id") or ""))
    reputation = 0.0
    for name, score in SOURCE_REPUTATION.items():
        if normalize_story_text(name) in source_name:
            reputation = max(reputation, score)
    tier_quality = {
        "major_gaming_media": 3.4,
        "business_industry_media": 3.3,
        "regional_gaming_media": 3.0,
        "mixed_portal": 2.0,
        "aggregator": 1.0,
    }
    tier = str(item.get("source_tier") or infer_source_tier(item))
    source_type = SOURCE_TYPE_QUALITY.get(str(item.get("source_type") or "aggregator"), 1)
    return max(tier_quality.get(tier, 1.0), source_type) + reputation


def cluster_main_item_sort_key(item: dict[str, Any]) -> tuple[float, int, float]:
    ts = parse_event_datetime(item)
    return (source_quality(item), int(item.get("hot_score") or 0), ts.timestamp() if ts else 0.0)


def cluster_score(main_item: dict[str, Any], items: list[dict[str, Any]]) -> tuple[int, list[str]]:
    sources = {str(item.get("source") or item.get("site_name") or item.get("site_id") or "") for item in items}
    regions = {str(item.get("region") or "") for item in items if item.get("region")}
    section = str(main_item.get("radar_section") or "other")
    score = int(main_item.get("hot_score") or 0)
    reasons = [f"main_hot_score={score}"]
    if len(sources) > 1:
        boost = min(30, (len(sources) - 1) * 10)
        score += boost
        reasons.append(f"source_count_boost={boost}")
    if len(regions) > 1:
        score += 8
        reasons.append("multi_region_boost=8")
    if section in {"game_releases", "industry_reports"}:
        score += 10
        reasons.append(f"section_boost={section}")
    return score, reasons


def build_game_story_clusters(
    items: list[dict[str, Any]],
    rank_entries: list[dict[str, Any]] | None = None,
    limit: int = GAME_STORY_CLUSTER_LIMIT,
    now: datetime | None = None,
    recent_days: int = GAME_STORY_CLUSTER_RECENT_DAYS,
) -> list[dict[str, Any]]:
    rank_entries = rank_entries if rank_entries is not None else load_game_rank_entries()
    groups: dict[tuple[str, str, str, str | None], list[dict[str, Any]]] = {}
    singletons: list[dict[str, Any]] = []
    for item in items:
        section = str(item.get("radar_section") or "other")
        if section == "other" or int(item.get("hot_score") or 0) <= 0:
            continue
        key_type, key_value, game_name = cluster_key_for_item(item, rank_entries)
        if not key_value:
            continue
        key = (key_type, key_value, section, game_name)
        groups.setdefault(key, []).append(item)

    # Fallback near-duplicate merging for title-only singleton keys.
    merged_groups: list[tuple[tuple[str, str, str, str | None], list[dict[str, Any]]]] = []
    for key, group_items in groups.items():
        if key[0] != "title" or len(group_items) > 1:
            merged_groups.append((key, group_items))
            continue
        item = group_items[0]
        signature = key[1]
        merged = False
        for existing_key, existing_items in merged_groups:
            if existing_key[0] == "title" and existing_key[2] == key[2]:
                ratio = SequenceMatcher(None, signature, existing_key[1]).ratio()
                if ratio >= 0.86:
                    existing_items.append(item)
                    merged = True
                    break
        if not merged:
            singletons.append(item)
            merged_groups.append((key, group_items))

    clusters = []
    for index, (key, group_items) in enumerate(merged_groups, 1):
        if len(group_items) < 2:
            continue
        if now is not None:
            event_times = [parse_event_datetime(item) for item in group_items]
            event_times = [ts for ts in event_times if ts is not None]
            if not event_times or max(event_times) < now - timedelta(days=recent_days):
                continue
        main_item = max(group_items, key=cluster_main_item_sort_key)
        sources = sorted({
            str(item.get("source") or item.get("site_name") or item.get("site_id") or "")
            for item in group_items
            if item.get("source") or item.get("site_name") or item.get("site_id")
        })
        if len(sources) < 2:
            continue
        score, reasons = cluster_score(main_item, group_items)
        section = str(main_item.get("radar_section") or key[2])
        clusters.append(
            {
                "cluster_id": f"{section}:{key[0]}:{key[1]}",
                "game_name": key[3],
                "story_type": section,
                "radar_section": section,
                "main_item": main_item,
                "items": sorted(group_items, key=event_time_str, reverse=True),
                "source_count": len(sources),
                "sources": sources,
                "cluster_score": score,
                "cluster_reasons": reasons,
            }
        )
    clusters.sort(key=lambda cluster: (cluster["cluster_score"], event_time_str(cluster["main_item"])), reverse=True)
    return clusters[:limit]


def run_all_fetchers(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    raw_records: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    tasks: list[tuple[str, str, Any]] = list(GENERIC_TASKS)
    for source in DIRECT_RSS_SOURCES:
        tasks.append((source["site_id"], source["site_name"], source))

    rsshub_enabled = os.environ.get("RSSHUB_BRIDGE_ENABLED") == "1"
    if rsshub_enabled:
        for source in RSSHUB_BRIDGE_SOURCES:
            tasks.append((source["site_id"], source["site_name"], source))
    else:
        print("RSSHub bridge sources skipped (RSSHUB_BRIDGE_ENABLED != 1)", file=sys.stderr)

    for site_id, site_name, fn_or_config in tasks:
        start = time.perf_counter()
        error = None
        count = 0
        try:
            if isinstance(fn_or_config, dict) and "item" in fn_or_config:
                items = fetch_rsshub_bridge_source(session, fn_or_config, now)
            elif isinstance(fn_or_config, dict):
                items = fetch_rss_source(session, fn_or_config, now)
            else:
                items = fn_or_config(session, now)
            count = len(items)
            for item in items:
                raw_records.append(
                    {
                        "id": f"{item.site_id}::{item.url}",
                        "site_id": item.site_id,
                        "site_name": item.site_name,
                        "source": item.source,
                        "title": item.title,
                        "url": item.url,
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                        "region_override": item.meta.get("region_override"),
                        "source_dedicated": item.meta.get("source_dedicated", False),
                        "source_type": item.meta.get("source_type", "aggregator"),
                        "ingestion_path": item.meta.get("ingestion_path", "scraper"),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        statuses.append(
            {
                "site_id": site_id,
                "site_name": site_name,
                "ok": error is None,
                "item_count": count,
                "duration_ms": elapsed_ms,
                "error": error,
            }
        )

    return raw_records, statuses


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def merge_into_archive(
    archive: dict[str, dict[str, Any]], fresh_records: list[dict[str, Any]], now: datetime
) -> None:
    now_iso = now.isoformat()
    for record in fresh_records:
        item_id = record["id"]
        existing = archive.get(item_id)
        if existing is None:
            record = dict(record)
            record["first_seen_at"] = now_iso
            record["last_seen_at"] = now_iso
            archive[item_id] = record
        else:
            existing.update({k: v for k, v in record.items() if k != "first_seen_at"})
            existing["last_seen_at"] = now_iso


def prune_archive(archive: dict[str, dict[str, Any]], now: datetime, retention_days: int) -> None:
    keep_after = now - timedelta(days=retention_days)
    stale = []
    for item_id, record in archive.items():
        ts_str = record.get("last_seen_at") or record.get("published_at") or record.get("first_seen_at")
        try:
            ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            ts = now
        if ts < keep_after:
            stale.append(item_id)
    for item_id in stale:
        del archive[item_id]


def translate_new_titles(
    archive: dict[str, dict[str, Any]], max_new: int, max_workers: int = 12
) -> int:
    """Fill in title_en for surviving (non-junk) archive records missing it.

    The key's mere presence (even set to None) marks "translation attempted"
    so an already-English or untranslatable title isn't retried forever -
    each item only ever costs one translation call across its whole
    lifetime in the archive, regardless of how many runs it survives. Only
    translates records that pass is_junk (no point translating items that
    won't be shown), and parallelizes since a fresh deploy has a large
    one-time backlog to catch up on.
    """
    candidates = [
        record for record in archive.values()
        if "title_en" not in record and not is_junk(record)
    ]
    # Prioritize the most recent items first - dict iteration order is
    # insertion order (oldest-discovered first), which would otherwise
    # translate old, rarely-viewed items before the ones actually showing
    # at the top of the Hot tab.
    candidates.sort(key=event_time_str, reverse=True)
    candidates = candidates[:max_new]
    if not candidates:
        return 0

    def worker(record: dict[str, Any]) -> None:
        session = requests.Session()
        record["title_en"] = translate_to_en(session, str(record.get("title") or ""))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(worker, candidates))
    return len(candidates)


def bootstrap_archive_from_seed(seed_path: Path) -> dict[str, dict[str, Any]]:
    seed = load_json(seed_path)
    if not seed:
        return {}
    archive: dict[str, dict[str, Any]] = {}
    for record in seed.get("items", []):
        item_id = f"{record.get('site_id')}::{record.get('url')}"
        entry = dict(record)
        entry.setdefault("first_seen_at", record.get("first_seen_at") or record.get("last_seen_at"))
        entry.setdefault("last_seen_at", record.get("last_seen_at") or record.get("first_seen_at"))
        archive[item_id] = entry
    return archive


def build(
    output_path: Path,
    state_path: Path,
    previous_state_path: Path | None,
    seed_path: Path | None,
    retention_days: int,
    translate_max_new: int,
) -> None:
    now = datetime.now(timezone.utc)

    previous_state = load_json(previous_state_path) if previous_state_path else None
    if previous_state and previous_state.get("archive"):
        archive: dict[str, dict[str, Any]] = previous_state["archive"]
    elif seed_path:
        print(f"No previous state found, bootstrapping from {seed_path}", file=sys.stderr)
        archive = bootstrap_archive_from_seed(seed_path)
    else:
        archive = {}

    fresh_records, statuses = run_all_fetchers(now)
    merge_into_archive(archive, fresh_records, now)
    prune_archive(archive, now, retention_days)

    translated_count = translate_new_titles(archive, translate_max_new)
    print(f"Translated {translated_count} new title(s) to English", file=sys.stderr)

    for record in archive.values():
        record["source_type"] = infer_source_type(record)
        record.update(add_source_tier_fields(record))

    kept = [classify_and_tag(record) for record in archive.values() if not is_junk(record)]
    kept.sort(key=event_time_str, reverse=True)
    kept, duplicate_count = dedupe_by_title(kept)

    hot_candidates: list[dict[str, Any]] = []
    cluster_candidates: list[dict[str, Any]] = []
    for item in kept:
        hot_meta = score_hot_news(item)
        hot_item = dict(item)
        if hot_meta is not None:
            hot_item.update(hot_meta)
        else:
            hot_item["hot_score"] = 0
            hot_item["hot_reasons"] = []
        hot_item["hot_recency_bucket"] = hot_news_recency_bucket(hot_item, now)
        if hot_meta is not None:
            hot_candidates.append(hot_item)
        if hot_meta is not None and int(hot_item.get("hot_score") or 0) > 0:
            cluster_candidates.append(hot_item)
    hot_candidates.sort(key=lambda item: hot_news_sort_key(item, now), reverse=True)
    game_story_clusters = build_game_story_clusters(cluster_candidates, now=now)
    hot_news = hot_candidates[: min(HOT_NEWS_LIMIT, max(0, len(kept) - 1))]

    by_region = {code: 0 for code in REGION_ORDER}
    for item in kept:
        by_region[item["region"]] += 1

    ok_sources = sum(1 for s in statuses if s["ok"])
    payload = {
        "generated_at": now.isoformat(),
        "generated_note": (
            f"Live pipeline (scripts/update_game_news.py), rolling {retention_days}-day window. "
            "Full feed is recency-sorted; hot_news is deterministic market-news scoring."
        ),
        "retention_days": retention_days,
        "total_items_kept": len(kept),
        "total_hot_news": len(hot_news),
        "total_game_story_clusters": len(game_story_clusters),
        "dropped_as_duplicate": duplicate_count,
        "by_region": by_region,
        "source_health": {
            "ok_count": ok_sources,
            "total_count": len(statuses),
            "sources": statuses,
        },
        "game_story_clusters": game_story_clusters,
        "hot_news": hot_news,
        "items": kept,
    }

    # State (raw archive, pre quality-gate) is written separately from the
    # public payload above - game.html never needs to download it, only the
    # next run reads it back for state continuity across commits.
    state_payload = {
        "generated_at": now.isoformat(),
        "retention_days": retention_days,
        "archive": archive,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Archive size: {len(archive)} items, kept {len(kept)} after quality gate -> {output_path}")
    print(f"State written -> {state_path}")
    print(f"Source health: {ok_sources}/{len(statuses)} healthy")
    for status in statuses:
        flag = "OK" if status["ok"] else f"FAIL ({status['error']})"
        print(f"  {status['site_name']:<20} {status['item_count']:>5} items  {status['duration_ms']:>6}ms  {flag}")


def main() -> int:
    # Non-UTF-8 default consoles (e.g. Windows) can't print non-Latin source
    # names like 巴哈姆特GNN otherwise - a crash here happens after all files
    # are already written, but still fails the step (and the CI run) on a
    # log line, not real work. Linux GitHub Actions runners default to UTF-8
    # already; this only matters for local dev.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data" / "game-news.json",
                         help="Public payload game.html fetches")
    parser.add_argument("--state", type=Path, default=REPO_ROOT / "data" / "game-news-state.json",
                         help="Raw archive written for the next run to read back")
    parser.add_argument("--previous-state", type=Path, default=None,
                         help="Prior run's --state file, for state continuity across commits")
    parser.add_argument(
        "--seed", type=Path, default=REPO_ROOT / "data" / "game-news-seed.json",
        help="Bootstrap source used only when --previous-state is missing/empty",
    )
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--translate-max-new", type=int, default=DEFAULT_TRANSLATE_MAX_NEW,
                         help="Cap on new title translations per run, to avoid rate-limiting the free endpoint")
    args = parser.parse_args()
    build(args.output, args.state, args.previous_state, args.seed, args.retention_days, args.translate_max_new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
