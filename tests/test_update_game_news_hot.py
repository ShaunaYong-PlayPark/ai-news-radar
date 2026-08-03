import json
from datetime import datetime, timedelta, timezone

from scripts import update_game_news


def cluster_item(
    title: str,
    source: str,
    site_id: str,
    source_type: str = "dedicated_game_media",
    hot_score: int = 50,
    section: str = "game_announcements",
    published_at: str = "2026-07-30T00:00:00+00:00",
) -> dict:
    return {
        "site_id": site_id,
        "site_name": source,
        "source": source,
        "title": title,
        "url": f"https://example.com/{site_id}/{abs(hash(title))}",
        "published_at": published_at,
        "region": "GLOBAL",
        "radar_section": section,
        "source_type": source_type,
        "hot_score": hot_score,
    }


def test_hot_news_sort_prioritizes_recent_bucket_over_stale_high_score():
    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    recent = {
        "title": "Mobile RPG opens pre-registration",
        "published_at": (now - timedelta(days=1)).isoformat(),
        "hot_score": 40,
    }
    stale = {
        "title": "Older studio acquisition story",
        "published_at": (now - timedelta(days=60)).isoformat(),
        "hot_score": 120,
    }

    ranked = sorted([stale, recent], key=lambda item: update_game_news.hot_news_sort_key(item, now), reverse=True)

    assert ranked[0] is recent
    assert update_game_news.hot_news_recency_bucket(recent, now) > update_game_news.hot_news_recency_bucket(stale, now)


def test_build_payload_includes_hot_news_without_changing_full_items(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    seed_path = tmp_path / "seed.json"
    output_path = tmp_path / "game-news.json"
    state_path = tmp_path / "game-news-state.json"
    seed_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "site_id": "test_site",
                        "site_name": "Test Game Source",
                        "source": "Test Game Source",
                        "title": "Mobile RPG opens pre-registration in Southeast Asia",
                        "url": "https://example.com/pre-registration",
                        "published_at": now.isoformat(),
                        "region_override": "PH",
                        "source_dedicated": True,
                        "source_type": "dedicated_game_media",
                    },
                    {
                        "site_id": "test_site",
                        "site_name": "Test Game Source",
                        "source": "Test Game Source",
                        "title": "General mobile game industry roundup",
                        "url": "https://example.com/roundup",
                        "published_at": now.isoformat(),
                        "region_override": "PH",
                        "source_dedicated": True,
                        "source_type": "dedicated_game_media",
                    },
                    {
                        "site_id": "preview_site",
                        "site_name": "Test Game Source",
                        "source": "Test Game Source",
                        "title": "Trải nghiệm tu tiên dưới nền đồ họa Unreal Engine 5 trong 9 Yin Sutra: Immortal",
                        "title_en": "9 Yin Sutra: Immortal preview showcases Unreal Engine 5 graphics",
                        "url": "https://example.com/9-yin-sutra",
                        "published_at": now.isoformat(),
                        "region_override": "GLOBAL",
                        "source_dedicated": True,
                        "source_type": "dedicated_game_media",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(update_game_news, "run_all_fetchers", lambda now_arg: ([], []))
    monkeypatch.setattr(update_game_news, "translate_new_titles", lambda archive, max_new: 0)

    update_game_news.build(output_path, state_path, None, seed_path, 110, 0)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "hot_news" in payload
    assert "game_story_clusters" in payload
    assert payload["total_hot_news"] == len(payload["hot_news"]) == 1
    assert payload["total_items_kept"] == len(payload["items"]) == 3
    assert payload["hot_news"][0]["hot_score"] > 0
    assert payload["hot_news"][0]["hot_recency_bucket"] == 2
    assert payload["items"][0]["source_tier"] == "regional_gaming_media"
    assert payload["items"][0]["source_tier_label"] == "Regional gaming media"
    assert len(payload["items"]) == 3
    assert all("9 Yin Sutra" not in item["title"] for item in payload["hot_news"])
    assert all(
        "9 Yin Sutra" not in item.get("title", "")
        for cluster in payload["game_story_clusters"]
        for item in cluster["items"]
    )


def test_same_known_game_across_three_titles_becomes_one_cluster():
    rank_entries = [{"name": "PUBG MOBILE", "normalized_keys": ["pubg mobile"]}]
    items = [
        cluster_item("PUBG MOBILE tournament qualifier announced for Bangkok", "IGN Southeast Asia", "ign_sea"),
        cluster_item("PUBG MOBILE championship qualifier schedule revealed", "GameSpot Asia", "gamespot_asia"),
        cluster_item("PUBG MOBILE esports roadmap announced for SEA", "Game Rant", "gamerant"),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=rank_entries)

    assert len(clusters) == 1
    assert clusters[0]["game_name"] == "PUBG MOBILE"
    assert clusters[0]["source_count"] == 3
    assert len(clusters[0]["items"]) == 3


def test_zero_score_items_are_not_hot_story_cluster_candidates():
    rank_entries = [{"name": "9 Yin Sutra: Immortal", "normalized_keys": ["9 yin sutra immortal"]}]
    item = cluster_item(
        "9 Yin Sutra: Immortal preview showcases Unreal Engine 5 graphics",
        "Test Game Source",
        "test",
        hot_score=0,
        section="game_announcements",
    )

    assert update_game_news.build_game_story_clusters([item], rank_entries=rank_entries) == []


def test_strong_positive_score_industry_items_can_still_cluster():
    rank_entries = [{"name": "Roblox", "normalized_keys": ["roblox"]}]
    items = [
        cluster_item("Roblox platform policy changes publishing rules", "GamesIndustry.biz", "gamesindustry_biz", section="industry_reports", hot_score=70),
        cluster_item("Roblox developer publishing policy adds a new requirement", "The Verge", "theverge", source_type="mixed_portal", section="industry_reports", hot_score=60),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=rank_entries)

    assert len(clusters) == 1


def test_cluster_main_item_prefers_reputable_source_over_weaker_aggregator():
    rank_entries = [{"name": "PUBG MOBILE", "normalized_keys": ["pubg mobile"]}]
    items = [
        cluster_item("PUBG MOBILE championship qualifier announced", "Random Aggregator", "buzzing", "aggregator", 90),
        cluster_item("PUBG MOBILE championship qualifier detailed", "RPG Site", "rpgsite", "dedicated_game_media", 50),
    ]

    cluster = update_game_news.build_game_story_clusters(items, rank_entries=rank_entries)[0]

    assert cluster["main_item"]["source"] == "RPG Site"


def test_source_count_boosts_cluster_score():
    main = cluster_item("PUBG MOBILE qualifier announced", "RPG Site", "rpgsite", hot_score=50)
    second = cluster_item("PUBG MOBILE qualifier revealed", "GameSpot Asia", "gamespot_asia", hot_score=40)
    third = cluster_item("PUBG MOBILE qualifier schedule posted", "IGN Southeast Asia", "ign_sea", hot_score=30)

    two_source_score, _ = update_game_news.cluster_score(main, [main, second])
    three_source_score, _ = update_game_news.cluster_score(main, [main, second, third])

    assert three_source_score > two_source_score


def test_unrelated_pokemon_opinion_does_not_merge_as_release_cluster():
    rank_entries = [{"name": "Pokemon TCG Pocket", "normalized_keys": ["pokemon tcg pocket", "pokemon"]}]
    items = [
        cluster_item("Pokemon TCG Pocket launches new expansion on mobile", "GameSpot Asia", "gamespot_asia", section="game_releases"),
        cluster_item(
            "Pokemon historic release overdue for Switch port",
            "Random Aggregator",
            "buzzing",
            source_type="aggregator",
            hot_score=80,
            section="other",
        ),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=rank_entries)

    assert clusters == []


def test_source_tier_mapping_uses_shauna_labels():
    assert update_game_news.infer_source_tier({"site_id": "tophub"}) == "aggregator"
    assert update_game_news.infer_source_tier({"site_id": "pcgamer", "source_type": "dedicated_game_media"}) == "major_gaming_media"
    assert update_game_news.infer_source_tier(
        {
            "site_id": "gamingph",
            "source_type": "dedicated_game_media",
            "region_override": "PH",
        }
    ) == "regional_gaming_media"
    assert update_game_news.infer_source_tier(
        {
            "site_id": "gamesindustry_biz",
            "source": "GamesIndustry.biz",
            "source_type": "dedicated_game_media",
        }
    ) == "business_industry_media"
    assert update_game_news.add_source_tier_fields({"site_id": "pokde", "source_type": "tech_portal"})[
        "source_tier_label"
    ] == "Mixed portals"


def test_quoted_and_prefix_game_names_cluster_without_rank_entry():
    items = [
        cluster_item('"Crystal of Atlan" launches on Steam', "RPG Site", "rpgsite", section="game_releases"),
        cluster_item("Crystal of Atlan release date announced for PC", "GameSpot Asia", "gamespot_asia", section="game_releases"),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=[])

    assert len(clusters) == 1
    assert clusters[0]["game_name"] == "Crystal of Atlan"
    assert clusters[0]["source_count"] == 2


def test_unreal_engine_story_does_not_cluster_under_fortnite():
    rank_entries = [{"name": "Fortnite", "normalized_keys": ["fortnite"]}]
    items = [
        cluster_item(
            "Epic says Unreal Engine 6 will unify UE5 and Unreal Editor for Fortnite with Claude integrations",
            "Techmeme",
            "techmeme",
            source_type="aggregator",
            section="game_releases",
        ),
        cluster_item(
            "Unreal Engine 6 preview adds Gemini tools and Unreal Editor for Fortnite support",
            "TechRadar",
            "techradar",
            source_type="mixed_portal",
            section="game_releases",
        ),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=rank_entries)

    assert len(clusters) == 1
    assert clusters[0]["game_name"] is None
    assert "unreal engine" in clusters[0]["cluster_id"]


def test_broad_company_platform_story_does_not_cluster_under_game_name():
    rank_entries = [{"name": "Roblox", "normalized_keys": ["roblox"]}]
    items = [
        cluster_item(
            "Roblox says developers need Roblox Plus subscription to publish games for Kids accounts",
            "Techmeme",
            "techmeme",
            source_type="aggregator",
            section="industry_reports",
        ),
        cluster_item(
            "Roblox developer publishing policy adds new monthly subscription requirement",
            "The Verge",
            "theverge",
            source_type="mixed_portal",
            section="industry_reports",
        ),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=rank_entries)

    assert len(clusters) == 1
    assert clusters[0]["game_name"] is None
    assert "roblox platform policy" in clusters[0]["cluster_id"]


def test_quoted_game_name_beats_loose_known_game_match():
    rank_entries = [{"name": "Roblox", "normalized_keys": ["roblox"]}]
    item = cluster_item('"Crystal of Atlan" launches Roblox crossover beta', "RPG Site", "rpgsite")

    assert update_game_news.detect_game_name(item, rank_entries) == "Crystal of Atlan"


def test_stale_seed_cluster_is_excluded_by_recency_guard():
    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    old_date = (now - timedelta(days=90)).isoformat()
    items = [
        cluster_item("GameStop makes $55.5bn takeover offer for eBay", "BBC", "bbc", section="industry_reports", published_at=old_date),
        cluster_item("GameStop takeover offer for eBay rejected", "hackernews", "hackernews", section="industry_reports", published_at=old_date),
    ]

    clusters = update_game_news.build_game_story_clusters(items, rank_entries=[], now=now)

    assert clusters == []
