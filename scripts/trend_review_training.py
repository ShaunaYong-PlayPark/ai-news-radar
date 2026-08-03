#!/usr/bin/env python3
"""Build trend-review training samples from data/game-news.json.

Round 2 is intentionally assisted-review scoring, not auto-publish logic.
It separates Future Game Releases from Industry Trends and keeps noisy
categories visible for reviewer calibration.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

REASON_CHIPS = [
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
]

SEA_RE = re.compile(
    r"sea|southeast asia|thailand|thai|philippines|filipino|vietnam|singapore|malaysia|indonesia|"
    r"bangkok|manila|jakarta|kuala lumpur|hanoi|ph\b|my\b|sg\b",
    re.I,
)
SG_RE = re.compile(r"singapore|\bsg\b", re.I)
SOURCE_CREDIBLE = {"major_gaming_media", "business_industry_media", "regional_gaming_media"}

PATCH_MINOR_RE = re.compile(
    r"patch notes?|update notes?|hotfix|balance patch|bug fix(?:es)? patch|version update|"
    r"maintenance update|minor content update|new skin|new costume|banner|login event|season pass",
    re.I,
)
ESPORTS_RESULT_RE = re.compile(
    r"esports world cup|championship|tournament|qualifier|\bschedules?\b|standings|teams|how to watch|"
    r"defeat(?:s|ed)?|wins?|results?|grand final|playoffs?|vòng chung kết|vô địch",
    re.I,
)
ORDINARY_FINANCIALS_RE = re.compile(
    r"\bq[1-4]\b|quarterly|earnings|eps|revenue up|revenue down|results miss|shares?|stock|"
    r"price target|investors?|y/y|yoy|write-down",
    re.I,
)
STOCK_ONLY_RE = re.compile(r"\bstock\b|shares?|nasdaq|nyse|price target|investors?", re.I)
NON_GAME_LAUNCH_RE = re.compile(
    r"(?:launch(?:es|ed|ing)?|announces?|opens?|unveils?).{0,80}"
    r"(?:fund|grant|program|sale|curator sale|event|festival|server|cohort|rebate|initiative|mod voice|voice mod)",
    re.I,
)
CONSUMER_MARKET_NOISE_RE = re.compile(
    r"prime day|best .* deals?|price drop|price drops|price hike|price increase|price increases|"
    r"should you buy|where to buy|how to buy|cheapest|discount|sale|all-time low|"
    r"perfect for|rip-off|what smart people|top 10|top games|so far|fan[s’']? rejoice",
    re.I,
)
HARDWARE_RETAIL_RE = re.compile(
    r"hardware|steam machine|steam frame|game boy camera|console price|xbox prices?|playstation prices?|selling .* for|"
    r"retail|accessor(?:y|ies)|controller|headset|gpu|handheld",
    re.I,
)
CONSUMER_PROFILE_RE = re.compile(
    r"show hn:|how to|guide|review|hands-on|fans?|logo|anniversary|miyamoto|developer spent|profile|"
    r"interview|behind the scenes|history|lore|trailer|cosplay|anime adaptation|movie|episode",
    re.I,
)
SPECULATIVE_RE = re.compile(r"rumou?r|reportedly|could|may|should|hopes?|wants?|speculat|report reveals", re.I)
IP_EXPANSION_RE = re.compile(r"anime adaptation|movie|tv series|film|merch|transmedia", re.I)
REGIONAL_ECOSYSTEM_RE = re.compile(
    r"developer program|game developers|indie studios?|local studios?|incubator|grant|fund|rebate|"
    r"ecosystem|pgdx|hatch|gamescom asia|regional",
    re.I,
)
FUTURE_CONSUMER_NOISE_RE = re.compile(
    r"show hn:|scammers?|discount(?:ed)?|bonus|homepage|fans?.{0,80}pre[- ]?order|without seeing any gameplay|"
    r"performance on .*switch|not good enough|free gta games",
    re.I,
)

FUTURE_RELEASE_RE = re.compile(
    r"release date|launch window|launch(?:es|ed|ing)? (?:on|for|to|in|this|next)|"
    r"\bcoming (?:to|this|next|in (?:20\d\d|q[1-4]|january|february|march|april|may|june|july|august|september|october|november|december))|"
    r"early access|pre[- ]?order|available on|now available on|is now available|"
    r"remake|remaster|relaunch|re-release|rerelease|"
    r"\bport(?:ed|ing)?\b.{0,50}(?:steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch|app store|google play|ios|android|pc|console|mobile)|"
    r"shutdown|shut down|server closure|"
    r"delist(?:ed|ing)?|wishlist|pre[- ]?registration",
    re.I,
)
FUTURE_PLATFORM_RE = re.compile(
    r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch|app store|google play|ios|android|pc|console|mobile",
    re.I,
)
FUTURE_GAME_CONTEXT_RE = re.compile(
    r"game|rpg|jrpg|mmorpg|gacha|survivor|soulslike|dungeon crawler|fighting souls|resident evil|"
    r"free fire|titanfall|stupid never dies|exstetra|god of war|marvel",
    re.I,
)

PLATFORM_POLICY_RE = re.compile(
    r"app store changes?|android developers?|age-assurance|ownership|physical games?|digital formats?|"
    r"distribution|platform policy|store policy|console prices?|xbox prices?|subscription|game pass",
    re.I,
)
DISTRIBUTION_MODEL_RE = re.compile(r"physical|digital|ownership|subscription|game pass|app store|google play|store changes?", re.I)
MONETIZATION_RE = re.compile(r"price|pricing|iap|ad spend|pre-orders? generate|user spending|subscription|monetization", re.I)
PUBLISHER_STRATEGY_RE = re.compile(
    r"publisher strategy|cancels?|cancellations?|layoffs?|portfolio|studio closure|leadership impacted|"
    r"acquisition|merger|investment|funding|co-published|publishing rights|new studio",
    re.I,
)
MARKET_DATA_RE = re.compile(
    r"pre-orders? generate|\bpre-orders?\b.{0,40}(?:million|\$|estimated)|wishlists?|\bmarket data\b|"
    r"\bdownloads\b|\bgrossing\b|sales milestone|records? \$|"
    r"\b\d+[,.]?\d*k?\s+(?:mobile )?games?\s+(?:launched|released)|"
    r"game releases?\s+(?:surge|jump|rise|grew)|mobile games?\s+(?:launched|released)",
    re.I,
)
ENGINE_STRATEGY_RE = re.compile(
    r"\b(?:unity|unreal|godot)\s+\d|game engine|engine update|engine release|"
    r"developer tools?\s+(?:for|used by)\s+games?",
    re.I,
)


def text_for(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "title_en", "source", "radar_section", "source_tier", "region", "region_label")
    )


def event_timestamp(item: dict[str, Any]) -> float:
    value = item.get("published_at") or item.get("last_seen_at") or item.get("first_seen_at") or ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def has_future_release_signal(text: str) -> bool:
    # Engine/platform tooling is an industry signal, not a game release.
    if ENGINE_STRATEGY_RE.search(text):
        return False
    # Aggregate release-volume reporting is market data, not one upcoming title.
    if re.search(r"\b\d+[,.]?\d*k?\s+(?:mobile )?games?\s+(?:launched|released)|game releases?\s+(?:surge|jump|rise|grew)", text, re.I):
        return False
    if not FUTURE_RELEASE_RE.search(text):
        return False
    if re.search(r"shutdown|shut down|server closure|delist", text, re.I):
        return True
    if re.search(r"wishlist|pre[- ]?order", text, re.I):
        return bool(FUTURE_GAME_CONTEXT_RE.search(text) or FUTURE_PLATFORM_RE.search(text))
    return bool(FUTURE_GAME_CONTEXT_RE.search(text) or FUTURE_PLATFORM_RE.search(text))


def has_industry_trend_signal(text: str) -> bool:
    return bool(
        PLATFORM_POLICY_RE.search(text)
        or DISTRIBUTION_MODEL_RE.search(text)
        or MONETIZATION_RE.search(text)
        or PUBLISHER_STRATEGY_RE.search(text)
        or ENGINE_STRATEGY_RE.search(text)
        or (MARKET_DATA_RE.search(text) and FUTURE_GAME_CONTEXT_RE.search(text))
        or (SEA_RE.search(text) and REGIONAL_ECOSYSTEM_RE.search(text))
    )


def score_review_item(item: dict[str, Any]) -> dict[str, Any]:
    text = text_for(item)
    reasons: list[str] = []
    score = 0

    future_signal = has_future_release_signal(text)
    industry_signal = has_industry_trend_signal(text)
    hard_reject = False

    if item.get("source_tier") in SOURCE_CREDIBLE:
        score += 8
        reasons.append("credible_source")
    if SEA_RE.search(text):
        score += 10
        reasons.append("sea_relevance")
    if SG_RE.search(text):
        score += 4
        reasons.append("sg_relevance")

    if PATCH_MINOR_RE.search(text):
        score -= 55
        reasons.append("minor_update")
        hard_reject = True
    if ESPORTS_RESULT_RE.search(text):
        score -= 45
        reasons.append("esports_result")
        if not re.search(r"business|rights|sponsor|market|publisher|platform", text, re.I):
            reasons.append("esports_not_report")
            hard_reject = True
    if NON_GAME_LAUNCH_RE.search(text):
        score -= 40
        reasons.append("non_game_launch")
        if not (future_signal and re.search(r"launch(?:es|ed|ing)?\s+(?:on|for|to|in)|release|early access|pre[- ]?registration", text, re.I)):
            hard_reject = True
    if HARDWARE_RETAIL_RE.search(text) and not (PLATFORM_POLICY_RE.search(text) or DISTRIBUTION_MODEL_RE.search(text)):
        score -= 35
        reasons.append("hardware_retail")
        hard_reject = True
    if ORDINARY_FINANCIALS_RE.search(text) and not (
        PLATFORM_POLICY_RE.search(text) or PUBLISHER_STRATEGY_RE.search(text) or MARKET_DATA_RE.search(text)
        or ENGINE_STRATEGY_RE.search(text)
    ):
        score -= 35
        reasons.append("ordinary_financials")
        hard_reject = True
    if STOCK_ONLY_RE.search(text) and not has_industry_trend_signal(text):
        score -= 25
        reasons.append("stock_only")
    if CONSUMER_MARKET_NOISE_RE.search(text) and not (
        PLATFORM_POLICY_RE.search(text) or DISTRIBUTION_MODEL_RE.search(text) or PUBLISHER_STRATEGY_RE.search(text)
    ):
        score -= 45
        reasons.append("too_consumer")
        hard_reject = True
    if re.search(r"top\s+\d+|top 10|so far", text, re.I) and MARKET_DATA_RE.search(text):
        score -= 35
        reasons.append("low_market_relevance")
        hard_reject = True
    if CONSUMER_PROFILE_RE.search(text) and not (future_signal or industry_signal):
        score -= 30
        reasons.append("too_consumer")
        hard_reject = True
    if SPECULATIVE_RE.search(text):
        score -= 10
        reasons.append("too_speculative")
    if FUTURE_CONSUMER_NOISE_RE.search(text):
        score -= 45
        reasons.append("too_consumer")
        hard_reject = True
    if IP_EXPANSION_RE.search(text):
        score += 10
        reasons.append("ip_expansion")
    if REGIONAL_ECOSYSTEM_RE.search(text):
        score += 12
        reasons.append("regional_ecosystem")

    if future_signal and not hard_reject:
        review_lane = "future_release"
        score += 70
        reasons.append("future_release")
        if MARKET_DATA_RE.search(text):
            score += 18
            reasons.append("market_signal")
    elif industry_signal and not hard_reject:
        review_lane = "industry_trend"
        score += 65
        if PLATFORM_POLICY_RE.search(text):
            score += 18
            reasons.append("platform_policy")
        if DISTRIBUTION_MODEL_RE.search(text):
            score += 14
            reasons.append("distribution_model")
        if MONETIZATION_RE.search(text):
            score += 10
            reasons.append("monetization")
        if PUBLISHER_STRATEGY_RE.search(text):
            score += 12
            reasons.append("publisher_strategy")
        if ENGINE_STRATEGY_RE.search(text):
            score += 18
            reasons.append("publisher_strategy")
        if MARKET_DATA_RE.search(text):
            score += 14
            reasons.append("market_signal")
    else:
        review_lane = "reject_candidate"
        if not future_signal:
            reasons.append("not_future_release")
        if not industry_signal:
            reasons.append("not_industry_trend")
        if not SEA_RE.search(text):
            reasons.append("not_sea_relevant")
        if not SG_RE.search(text):
            reasons.append("not_sg_relevant")

    if review_lane == "reject_candidate":
        suggested = "exclude_candidate" if score < 35 else "watch_candidate"
    elif score >= 95:
        suggested = "include_candidate"
    elif score >= 60:
        suggested = "watch_candidate"
    else:
        suggested = "exclude_candidate"

    deduped_reasons = list(dict.fromkeys(reasons))
    return {
        "review_lane": review_lane,
        "suggested_trend_bucket": suggested,
        "system_reason": ", ".join(deduped_reasons),
        "system_score": int(score),
    }


def review_record(item: dict[str, Any], cluster_keys: set[str] | None = None) -> dict[str, Any]:
    scored = score_review_item(item)
    article_id = item.get("id") or item.get("url")
    if cluster_keys and (item.get("id") in cluster_keys or item.get("url") in cluster_keys):
        scored["system_score"] += 8
        scored["system_reason"] = f"{scored['system_reason']}, repeated_story"
    return {
        "article_id": article_id,
        "title": item.get("title"),
        "title_en": item.get("title_en"),
        "source": item.get("source") or item.get("site_name"),
        "url": item.get("url"),
        "published_at": item.get("published_at"),
        "radar_section": item.get("radar_section"),
        "source_tier": item.get("source_tier"),
        **scored,
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def round1_false_positive_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = load_json(path)
    ids = set()
    for row in payload.get("labels", []):
        if row.get("label") == "exclude" and row.get("suggested_trend_bucket") in {"include_candidate", "watch_candidate"}:
            article_id = row.get("article_id")
            if article_id:
                ids.add(str(article_id))
    return ids


def cluster_keys(game_payload: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for cluster in game_payload.get("game_story_clusters", []):
        for item in cluster.get("items", []) or []:
            if item.get("id"):
                keys.add(str(item["id"]))
            if item.get("url"):
                keys.add(str(item["url"]))
    return keys


def select_round2_items(
    game_payload: dict[str, Any],
    labels_path: Path,
    target_count: int = 180,
) -> list[dict[str, Any]]:
    false_positive_ids = round1_false_positive_ids(labels_path)
    clusters = cluster_keys(game_payload)
    records = [review_record(item, clusters) for item in game_payload.get("items", []) if item.get("id") or item.get("url")]
    by_id = {str(row["article_id"]): row for row in records}

    categories: list[tuple[str, int, Any]] = [
        ("future_release", 35, lambda row: row["review_lane"] == "future_release"),
        ("watch_market", 25, lambda row: row["review_lane"] in {"future_release", "industry_trend"} and "market_signal" in row["system_reason"]),
        ("industry_trend", 35, lambda row: row["review_lane"] == "industry_trend"),
        ("esports", 20, lambda row: "esports_result" in row["system_reason"]),
        ("ordinary_financials", 18, lambda row: "ordinary_financials" in row["system_reason"]),
        ("non_game_launch", 18, lambda row: "non_game_launch" in row["system_reason"]),
        ("hardware_retail", 14, lambda row: "hardware_retail" in row["system_reason"]),
        ("regional_ecosystem", 20, lambda row: "regional_ecosystem" in row["system_reason"]),
        ("ip_expansion", 10, lambda row: "ip_expansion" in row["system_reason"]),
        ("round1_false_positive", 25, lambda row: str(row["article_id"]) in false_positive_ids),
    ]

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_rows(candidates: list[dict[str, Any]], limit: int) -> None:
        added = 0
        for row in candidates:
            article_id = str(row["article_id"])
            if article_id in seen:
                continue
            selected.append(row)
            seen.add(article_id)
            added += 1
            if added >= limit:
                break

    for _name, limit, predicate in categories:
        candidates = [row for row in records if predicate(row)]
        candidates.sort(key=lambda row: (abs(int(row["system_score"]) - 70), -event_timestamp(row)), reverse=False)
        add_rows(candidates, limit)

    if len(selected) < target_count:
        remaining = [row for row in records if str(row["article_id"]) not in seen]
        remaining.sort(key=lambda row: (abs(int(row["system_score"]) - 55), -event_timestamp(row)))
        for row in remaining:
            selected.append(row)
            seen.add(str(row["article_id"]))
            if len(selected) >= target_count:
                break

    return selected[:target_count]


def build_round2_payload(game_payload: dict[str, Any], labels_path: Path, target_count: int) -> dict[str, Any]:
    items = select_round2_items(game_payload, labels_path, target_count)
    lane_counts = Counter(item["review_lane"] for item in items)
    bucket_counts = Counter(item["suggested_trend_bucket"] for item in items)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": "data/game-news.json",
        "source_generated_at": game_payload.get("generated_at"),
        "round1_labels_file": str(labels_path).replace("\\", "/"),
        "label_schema": {
            "labels": ["include", "watch", "exclude"],
            "reason_chips": REASON_CHIPS,
        },
        "sampling": {
            "target_count": target_count,
            "actual_count": len(items),
            "notes": (
                "Round 2 focuses on borderline assisted-review cases: future releases, market signals, "
                "industry trends, esports, ordinary financials, non-game launches, hardware retail, "
                "regional ecosystem, IP expansion, and Round 1 false-positive patterns."
            ),
            "review_lane_counts": dict(lane_counts),
            "suggested_bucket_counts": dict(bucket_counts),
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO_ROOT / "data" / "game-news.json")
    parser.add_argument(
        "--round1-labels",
        type=Path,
        default=REPO_ROOT / "data" / "training" / "trend_review_labels_shauna_round1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "training" / "trend_review_training_round2.json",
    )
    parser.add_argument("--target-count", type=int, default=180)
    args = parser.parse_args()

    game_payload = load_json(args.input)
    payload = build_round2_payload(game_payload, args.round1_labels, args.target_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['items'])} items -> {args.output}")
    print(f"Review lanes: {payload['sampling']['review_lane_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
