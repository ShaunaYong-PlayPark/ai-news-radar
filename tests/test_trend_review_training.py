from scripts.trend_review_training import score_review_item


def rec(title: str, source_tier: str = "major_gaming_media", radar_section: str = "industry_reports") -> dict:
    return {
        "id": "test::item",
        "title": title,
        "title_en": None,
        "source": "Test Source",
        "source_tier": source_tier,
        "radar_section": radar_section,
    }


def test_future_release_requires_concrete_release_signal():
    result = score_review_item(
        rec(
            "Action RPG Stupid Never Dies launches on October 21 for PlayStation 5 and PC",
            radar_section="game_releases",
        )
    )

    assert result["review_lane"] == "future_release"
    assert "future_release" in result["system_reason"]
    assert result["suggested_trend_bucket"] in {"include_candidate", "watch_candidate"}


def test_industry_trend_detects_platform_policy():
    result = score_review_item(rec("Google Brings Its Age-Assurance Tech To Android Developers Worldwide"))

    assert result["review_lane"] == "industry_trend"
    assert "platform_policy" in result["system_reason"]


def test_non_game_launch_is_reject_candidate():
    result = score_review_item(
        rec(
            "PGDX 2026 Launches Official Steam Curator Sale",
            source_tier="regional_gaming_media",
            radar_section="game_releases",
        )
    )

    assert result["review_lane"] == "reject_candidate"
    assert "non_game_launch" in result["system_reason"]


def test_esports_schedule_result_is_not_future_release():
    result = score_review_item(
        rec(
            "Overwatch Midseason Championship at Esports World Cup 2026: Schedule, results, standings, teams, how to watch",
            radar_section="game_announcements",
        )
    )

    assert result["review_lane"] == "reject_candidate"
    assert "esports_result" in result["system_reason"]
    assert "esports_not_report" in result["system_reason"]


def test_ordinary_financials_do_not_become_industry_trend_by_default():
    result = score_review_item(rec("Roblox Q2 2026 earnings results miss revenue on smaller than expected EPS losses"))

    assert result["review_lane"] == "reject_candidate"
    assert "ordinary_financials" in result["system_reason"]


def test_scheduled_games_cancellation_is_publisher_strategy_not_esports():
    result = score_review_item(rec('Hasbro records $56m write-down and cancels "several games" scheduled for 2028 and beyond'))

    assert "publisher_strategy" in result["system_reason"]
    assert "esports_result" not in result["system_reason"]


def test_hardware_app_platform_availability_is_not_future_release():
    result = score_review_item(rec("The Game Boy Camera experience is now available on Android", radar_section="game_releases"))

    assert result["review_lane"] == "reject_candidate"
    assert "hardware_retail" in result["system_reason"]


def test_wishlist_market_signal_can_be_future_release_watch():
    result = score_review_item(
        rec(
            "Resident Evil Veronica hits a million wishlists on PS5 and PC just under a week after its announcement",
            source_tier="aggregator",
            radar_section="other",
        )
    )

    assert result["review_lane"] == "future_release"
    assert "market_signal" in result["system_reason"]


def test_engine_release_is_an_industry_trend():
    result = score_review_item(rec("Unity 7 to launch in Q1 2027; new engine is a direct continuation of Unity 6"))
    assert result["review_lane"] == "industry_trend"
    assert result["suggested_trend_bucket"] in {"include_candidate", "watch_candidate"}
    assert "publisher_strategy" in result["system_reason"]


def test_game_volume_data_is_an_industry_trend():
    result = score_review_item(
        rec("AI and vibe coding fuel a surge in game releases: 181K mobile games launched in six months")
    )
    assert result["review_lane"] == "industry_trend"
    assert "market_signal" in result["system_reason"]


def test_concrete_mobile_game_launch_is_not_a_non_game_launch():
    result = score_review_item(rec("Pokémon Champions launches on iOS and Android"))
    assert result["review_lane"] == "future_release"


def test_consumer_deals_and_rankings_are_rejected():
    for title in (
        "The 4th of July sales include great prices on RTX gaming laptops",
        "2026's top 10 grossing mobile games so far",
        "Should you buy a Nintendo Switch 2 before the price hikes?",
    ):
        assert score_review_item(rec(title))["review_lane"] == "reject_candidate"
