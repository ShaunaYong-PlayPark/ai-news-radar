from scripts.game_news_classify import classify_and_tag, classify_radar_section, is_junk, score_hot_news


def rec(title: str, dedicated: bool = True, source: str = "Test Game Source", title_en: str | None = None) -> dict:
    return {
        "site_id": "test",
        "site_name": source,
        "source": source,
        "title": title,
        "title_en": title_en,
        "url": "https://example.com/story",
        "source_dedicated": dedicated,
    }


def test_drops_guides_codes_and_builds_even_from_dedicated_sources():
    assert is_junk(rec("Palworld 1.0 Best Fire Damage Builds: Two Meta Setups Explained"))
    assert is_junk(rec("Roblox Pass or Explode Codes July 2026"))
    assert is_junk(rec("Kode Redeem EA Sports FC Mobile 30 Juli 2026"))
    assert is_junk(rec("How to unlock MOMO in Xenoblade Chronicles 2"))


def test_keeps_launch_guide_when_release_state_is_present():
    assert not is_junk(rec("Digimon Up Launch Guide: Release Date, Rewards & More"))


def test_drops_routine_live_ops_but_keeps_lifecycle_news():
    assert is_junk(rec("Genshin Impact adds new character banner this week"))
    assert is_junk(rec("Elden Ring DLC gets new boss trailer"))
    assert not is_junk(rec("Classic RPG remake launches on mobile this October"))
    assert not is_junk(rec("Mobile RPG postpones SEA launch to 2027"))
    assert not is_junk(rec("Online RPG announces server closure in Singapore"))


def test_events_need_market_or_esports_signal():
    assert is_junk(rec("Mobile Legends summer login event gives free gems"))
    assert not is_junk(rec("EA SPORTS FC Pro Mobile announces Bangkok qualifier schedule"))
    assert not is_junk(rec("Riot announces Valorant Pacific tournament format"))
    assert hot("Jadwal Playoff MPL ID S17 13 Juni: Geek Fam Vs Bigetron by Vitality") is None


def test_anime_ip_needs_game_signal():
    assert is_junk(rec("One Piece creator reveals Shanks true goal"))
    assert is_junk(rec("Naruto The Card Game reveals first trailer"))
    assert not is_junk(rec("Jujutsu Kaisen mobile RPG opens pre-registration"))
    assert not is_junk(rec("Attack on Titan crossover launches in new mobile game"))


def test_peripherals_drop_unless_platform_market_news():
    assert is_junk(rec("Best gaming headset deals this week"))
    assert is_junk(rec("New GPU benchmark for PC builds"))
    assert not is_junk(rec("PlayStation handheld launches in SEA with new pricing"))


def test_mixed_sources_need_real_game_signal():
    assert is_junk(
        rec(
            "Vô địch SEA V.Cup, bóng chuyền nam Việt Nam giành vé tham dự AVC Cup 2027",
            dedicated=False,
            source="Kenh14 Sport & Esports",
        )
    )
    assert is_junk(rec("10 nữ diễn viên đẹp nhất Việt Nam: Minh Hằng - Chi Pu out top", dedicated=False, source="GameK"))
    assert not is_junk(rec("PUBG Mobile opens pre-registration in Vietnam", dedicated=False, source="GameK"))


def test_sea_mixed_business_sources_keep_gaming_company_signals():
    assert not is_junk(
        rec(
            "VNG invests in a new mobile game studio in Vietnam",
            dedicated=False,
            source="VnExpress Business",
        )
    )
    assert section(
        "VNG invests in a new mobile game studio in Vietnam",
        dedicated=False,
        source="VnExpress Business",
    ) == "industry_reports"
    assert not is_junk(
        rec(
            "Garena targets Thailand for gaming investment",
            dedicated=False,
            source="Bangkok Post Business",
        )
    )
    assert section(
        "Garena targets Thailand for gaming investment",
        dedicated=False,
        source="Bangkok Post Business",
    ) == "industry_reports"


def test_broad_platform_companies_still_need_gaming_context_in_mixed_sources():
    assert is_junk(
        rec(
            "Sony reports higher quarterly revenue",
            dedicated=False,
            source="VnExpress Business",
        )
    )
    assert not is_junk(
        rec(
            "Sony expands PlayStation gaming investment in Vietnam",
            dedicated=False,
            source="VnExpress Business",
        )
    )
    assert section(
        "Sony expands PlayStation gaming investment in Vietnam",
        dedicated=False,
        source="VnExpress Business",
    ) == "industry_reports"


def test_sea_business_sources_are_registered_without_duplicates():
    from scripts.game_sources import DIRECT_RSS_SOURCES

    ids = [source["site_id"] for source in DIRECT_RSS_SOURCES]
    assert ids.count("gamingonphone") == 1
    assert ids.count("gamek_vn") == 1
    assert ids.count("vnexpress_business") == 1
    assert ids.count("bangkokpost_business") == 1
    assert next(source for source in DIRECT_RSS_SOURCES if source["site_id"] == "vnexpress_business")["dedicated"] is False
    assert next(source for source in DIRECT_RSS_SOURCES if source["site_id"] == "bangkokpost_business")["dedicated"] is False


def test_reviews_drop_unless_they_are_release_news():
    assert is_junk(rec("Review: Granblue Fantasy Relink Endless Ragnarok DLC"))
    assert not is_junk(rec("Dragon Quest remake launches on Switch after new reviews go live"))


def test_dedicated_sources_still_drop_non_game_fluff():
    assert is_junk(rec("Microsoft spent $4.5 billion on share buybacks during Q4"))
    assert is_junk(rec("Facebook Q2 earnings results beat revenue expectations"))
    assert is_junk(rec('Hóa "nàng thơ", MC Linh Nắng gây mê anh em game thủ trong bộ ảnh mới'))
    assert not is_junk(rec("Hound13 Dragon Sword Awakening sells 200,000 copies after launch"))
    assert not is_junk(rec("NetEase studio layoffs hit mobile RPG team"))


def hot(title: str, dedicated: bool = True, source: str = "Test Game Source") -> dict | None:
    return score_hot_news(classify_and_tag(rec(title, dedicated=dedicated, source=source)))


def test_hot_news_keeps_market_important_lifecycle_and_business_news():
    launch = hot("Jujutsu Kaisen mobile RPG opens pre-registration in Southeast Asia")
    business = hot("NetEase studio layoffs hit mobile RPG developer team")
    platform = hot("Indie RPG launches on Steam and Nintendo Switch next month")
    esports = hot("Valorant Pacific championship qualifier schedule announced for Bangkok")

    assert launch and "game_lifecycle" in launch["hot_reasons"]
    assert business and "business" in business["hot_reasons"]
    assert platform and "platform_store" in platform["hot_reasons"]
    assert esports is None


def test_hot_news_excludes_guides_reviews_codes_and_routine_liveops():
    assert hot("Roblox Pass or Explode Codes July 2026") is None
    assert hot("Best builds for Palworld fire damage in the new patch") is None
    assert hot("Review: Granblue Fantasy Relink Endless Ragnarok DLC") is None
    assert hot("Genshin Impact adds new skin banner and login event") is None
    assert hot("Elden Ring DLC gets new boss trailer") is None
    assert hot("Xbox studio apocalypse: Every studio closure rumored and confirmed") is None


def test_hot_news_dlc_needs_major_launch_business_or_platform_signal():
    assert hot("Fantasy RPG DLC launches as standalone release on Steam") is not None
    assert hot("Fantasy RPG DLC adds two costumes and a new map") is None


def test_hot_news_anime_ip_needs_video_game_signal():
    assert hot("One Piece anime announces new movie trailer") is None
    assert hot("One Piece mobile game announces soft launch date") is not None


def test_hot_news_excludes_hardware_unless_platform_market_story():
    assert hot("Best gaming headset deals this week") is None
    assert hot("PlayStation handheld launches in SEA with new pricing") is not None
    assert hot('Designer discusses the fun of killing five or six soldiers') is None


def test_hot_news_excludes_patch_speculation_editorial_card_tv_and_other_sections():
    assert hot("VALORANT Reveals Patch 13.02 Notes: Phoenix Ult Nerf, New Retake Maps, AROS Delays, and More") is None
    assert hot("5 PlayStation Games That Could Be Potential Launch Titles for PS6") is None
    assert hot("Cyberpunk 2077 interview and retrospective with its associate game director") is None
    assert hot("Naruto Card Game Officially Launches with all Naruto anime series") is None
    assert hot("Wonder Man showrunner reveals why the series was shockingly canceled") is None
    assert hot("A quiet opinion piece about the future of games") is None


def test_section_boundaries_for_bundles_leaks_sales_and_future_releases():
    assert section("Get more than 100 games for just $10 in a new bundle supporting laid-off game devs") == "other"
    assert hot("Get more than 100 games for just $10 in a new bundle supporting laid-off game devs") is None
    assert section("Trophy list leak before game launch") == "other"
    assert hot("Trophy list leak before game launch") is None
    assert section("PDGX 2026 launches official Steam curator sale") == "other"
    assert hot("PDGX 2026 launches official Steam curator sale") is None
    assert section("Call of Duty: Modern Warfare 4 release date, trailer, and platforms") == "game_announcements"
    assert section("Ragnarok: The New World has been soft-launched in SEA") == "game_releases"
    assert section("Game X is out now on Steam") == "game_releases"
    assert section("Game Y launches today on iOS and Android") == "game_releases"
    assert section("Every Gears Of War: E-Day Versus Mode For Online Multiplayer That Will Appear at Launch") == "other"
    assert section("KRAFTON Launches First Global Brand Campaign in Japan") == "other"
    assert section("Android 17 QPR2 Beta 1 appears with a strange bug") == "other"
    assert section("Summer Games Done Quick returns this July, schedule out now") == "other"
    assert hot("Summer Games Done Quick returns this July, schedule out now") is None
    assert section("Unity 7 to launch in Q1 2027; new game engine continues Unity 6") == "industry_reports"
    assert section("Newzoo: GTA 6 pre-orders generate estimated $260m globally") == "industry_reports"
    assert section("PlayStation exclusives are not coming to PC anymore") == "industry_reports"


def test_section_rules_reject_consumer_leaks_sales_and_entertainment_noise():
    assert section("Get more than 100 games for just $10 in a new bundle supporting laid-off game devs") == "other"
    assert section("Trophy list leak before game launch") == "other"
    assert section("PDGX 2026 launches official Steam curator sale") == "other"
    assert section("Wonder Man showrunner reveals why the series was shockingly canceled") == "other"
    assert hot("Get more than 100 games for just $10 in a new bundle supporting laid-off game devs") is None
    assert hot("Trophy list leak before game launch") is None
    assert hot("PDGX 2026 launches official Steam curator sale") is None
    assert hot("Wonder Man showrunner reveals why the series was shockingly canceled") is None


def test_future_release_announcement_does_not_become_release():
    title = "Call of Duty: Modern Warfare 4 release date, trailer, and platforms"
    assert section(title) == "game_announcements"
    assert section(title) != "game_releases"
    assert hot("Guardian Maiden release date speculation, platforms, and story") is None


def test_game_announcements_require_concrete_release_signals():
    assert section(
        "Ubisoft Thinks Remakes Are More Valuable Than New Games, Which Clearly Hints at Its Lineup for the Coming Years"
    ) == "other"
    assert section(
        "Shigeru Miyamoto dreams of Nintendo consoles becoming a rite of passage for everyone coming of age"
    ) == "other"
    assert section("Two Unreleased Virtual Boy Games Are Coming To Nintendo Switch Online") == "other"
    assert section("Popular Xbox Exclusive From 2025 Officially Coming to PS5 in August") == "other"
    assert hot(
        "Ubisoft Thinks Remakes Are More Valuable Than New Games, Which Clearly Hints at Its Lineup for the Coming Years"
    ) is None
    assert hot(
        "Shigeru Miyamoto dreams of Nintendo consoles becoming a rite of passage for everyone coming of age"
    ) is None
    assert hot("Two Unreleased Virtual Boy Games Are Coming To Nintendo Switch Online") is None
    assert hot("Popular Xbox Exclusive From 2025 Officially Coming to PS5 in August") is None


def test_independence_interview_is_not_a_release_announcement():
    title = (
        "Spyro studio CEO says there was no pushback to becoming independent from Activision Blizzard, "
        "but the process and planning the game at the same time was complex"
    )
    assert section(title) == "industry_reports"
    assert hot(title) is None


def test_gamesindustry_development_interview_stays_low_priority():
    title = "What lessons have developers learned from external development?"
    assert section(title, source="GamesIndustry.biz") == "industry_reports"
    assert hot(title, source="GamesIndustry.biz") is None


def test_closed_network_test_without_confirmed_date_is_not_hot():
    assert hot("The Duskbloods gets a closed network test this summer; full release date TBA") is None
    assert hot("The Duskbloods gets a closed network test this summer; no release date announced") is None


def test_named_hardware_products_are_never_hot():
    for title in (
        "Razer Huntsman launches with Hall effect switches",
        "Razer launches a new gaming keyboard",
        "New Hall effect gaming mouse launches this week",
        "Gaming headset launches with spatial audio",
        "New controller launches for PC gamers",
    ):
        assert hot(title) is None


def test_strict_release_hot_rules_for_esports_hardware_console_and_tests():
    assert section("Esports World Cup schedule, results, standings, teams and how to watch") == "other"
    assert hot("Esports World Cup schedule, results, standings, teams and how to watch") is None
    assert section("Razer launches a new gaming keyboard") == "other"
    assert hot("Razer launches a new gaming keyboard") is None
    assert hot("Indie RPG launches on Nintendo Switch only") is None
    assert section("GTA VI pre-orders are live for PS5 and Xbox") == "game_announcements"
    assert hot("GTA VI pre-orders are live for PS5 and Xbox") is not None
    assert hot("The Duskbloods gets a closed network test this summer; full release date TBA") is None
    assert section("The Duskbloods gets a closed network test this summer; full release date TBA") == "other"
    assert section("The Duskbloods gets a closed network test this summer, but a release date for the full game has yet to be announced") == "other"
    assert section("Patch Notes v1.2: balance fixes and bug updates") == "other"
    assert section("Nintendo live-action movie release date announced") == "other"


def test_platform_business_strategy_stays_in_industry_reports():
    assert section("Sony will stop making physical copies of PlayStation games in 2028") == "industry_reports"
    assert section("Microsoft changes Xbox Game Pass pricing and subscription policy") == "industry_reports"
    assert section("Nintendo outlines its Switch software distribution strategy") == "industry_reports"
    assert section("Sony hesitates to announce PS6 release date or price due to RAM crisis") == "industry_reports"


def section(
    title: str,
    dedicated: bool = True,
    source: str = "Test Game Source",
    title_en: str | None = None,
) -> str:
    return classify_radar_section(
        classify_and_tag(rec(title, dedicated=dedicated, source=source, title_en=title_en))
    )


def test_radar_section_industry_reports():
    assert section("Microsoft reports Q4 Xbox revenue down 13% YoY") == "industry_reports"
    assert section("Xbox Game Studios CEO steps down as layoffs loom") == "industry_reports"
    assert section("Nintendo celebrates Mario Day with a new wallpaper") == "other"


def test_radar_section_game_releases():
    assert section("Indie RPG launches on Steam next month") == "game_announcements"
    assert section("Jujutsu Kaisen mobile RPG opens pre-registration") == "game_announcements"
    assert section("Prelude Dark Pain is now available for PC via Steam Early Access") == "game_releases"


def test_early_access_current_vs_future_release_state():
    assert section("New dungeon crawler RPG Dverghold launches for PC via Early Access") == "game_releases"
    assert section("Delverium is available now in Early Access") == "game_releases"
    assert section("SUDDEN ATTACK ZERO POINT เปิดให้เล่นช่วง EARLY ACCESS แล้ววันนี้") == "game_releases"
    assert section("Subnautica 2 trailer drops ahead of its Early Access release") == "game_announcements"
    assert section("Game X will launch into Early Access on October 21") == "game_announcements"


def test_engine_descriptor_does_not_override_game_lifecycle_section():
    assert section(
        "Trải nghiệm tu tiên dưới nền đồ họa Unreal Engine 5 trong 9 Yin Sutra: Immortal",
        title_en="9 Yin Sutra: Immortal preview showcases Unreal Engine 5 graphics",
    ) == "game_announcements"
    assert section("Unity 7 to launch in Q1 2027") == "industry_reports"
    assert section("Epic changes Unreal Engine pricing for game developers") == "industry_reports"


def test_radar_section_speculative_port_story_is_other():
    assert section("Pokemon historic release overdue for Switch port") == "other"
    assert section("The Steam Frame subreddit is currently losing its collective mind praying for a release date") == "other"


def test_radar_section_noisy_release_contexts_are_other_and_not_hot():
    post_release_debate = "It's been weeks since The Odyssey was released but this debate is still raging on: Is Athena real?"
    accessory_dlc_timing = (
        "What perfect timing, Hori's adorable Switch 2 Ditto accessories launch just one day after "
        "Pokopia's first DLC expansion"
    )

    assert section(post_release_debate) == "other"
    assert section(accessory_dlc_timing) == "other"
    assert hot(post_release_debate) is None
    assert hot(accessory_dlc_timing) is None


def test_full_feed_drops_noisy_post_release_and_accessory_dlc_contexts():
    assert is_junk(rec("It's been weeks since The Odyssey was released but this debate is still raging on: Is Athena real?"))
    assert is_junk(
        rec(
            "What perfect timing, Hori's adorable Switch 2 Ditto accessories launch just one day after "
            "Pokopia's first DLC expansion"
        )
    )


def test_full_feed_drops_patch_notes_unless_major_release_signal():
    assert is_junk(rec("Patch Notes v1.2: balance fixes and bug updates"))
    assert is_junk(rec("Genshin Impact version update patch notes released"))
    assert is_junk(rec("Mobile RPG hotfix fixes login issue"))
    assert not is_junk(rec("Classic RPG remake launches on Steam"))
    assert not is_junk(rec("Online RPG announces server shutdown"))
    assert not is_junk(rec("Fantasy RPG DLC launches as standalone release on Steam"))


def test_full_feed_drops_generic_event_dlc_finance_and_loose_ai_tool_noise():
    assert is_junk(rec("GameStop CEO Ryan Cohen wants to buy eBay so badly that he's taken his $35 billion pay deal off the table"))
    assert is_junk(
        rec(
            "California just changed the game for GovTech as Anthropic makes Claude available to every state agency",
            dedicated=False,
            source="@sanjaykalra",
        )
    )
    assert is_junk(rec("Show HN: I used Claude to write a tactics JSON file for a football game", dedicated=False, source="Hacker News"))
    assert is_junk(rec("All Pokemon Pokopia events"))
    assert is_junk(rec("Pokemon Pokopia Feebas and Milotic Event Announced"))
    assert is_junk(rec("Pokemon Pokopia Free Trial Events Coming to Manila This April 2026"))
    assert is_junk(rec("Pokemon Pokopia's Bubbly Basin DLC launches early August, just in time for summer"))
    assert is_junk(rec("GameStop commits to moving ahead with its eBay acquisition offer"))
    assert is_junk(rec("GameStop会成为下一个伯克希尔·哈撒韦吗？", source="finance.yahoo.com"))
    assert is_junk(rec("Roblox vs GameStop: which gaming stock is the better buy?", source="finance.yahoo.com"))
    assert is_junk(rec("Epic says Unreal Engine 6 will add integrations with Claude and Gemini"))
    assert is_junk(rec("Donchitos / Claude-Code-Game-Studios", dedicated=False, source="GitHub Trending"))
    assert not is_junk(rec("GameStop partners with Uber Eats to deliver physical game discs", source="UDN Game"))


def test_full_feed_drops_chinese_gamestop_ebay_finance_aliases():
    assert is_junk(rec("游戏驿站想吞下电商巨头，eBay 为什么对溢价收购毫无兴趣？"))
    assert is_junk(rec("游戏驿站提出近560亿美元收购eBay"))
    assert is_junk(rec("游戏驿站 CEO“卖袜子”筹集 560 亿美元收购 eBay，账户被 eBay 永久停用"))
    assert not is_junk(rec("GameStop partners with Uber Eats to deliver physical game discs", source="UDN Game"))


def test_full_feed_junk_checks_normalized_original_and_title_en_text():
    assert is_junk(rec("Pokémon Pokopia Free Trial Events Coming to Manila This April 2026"))
    assert is_junk(rec("PokÃ©mon Pokopia Free Trial Events Coming to Manila This April 2026"))
    assert is_junk(rec("GameStop股价小幅上涨，公司重申将继续推进收购eBay的计划（GME）", source="finance.yahoo.com"))
    assert is_junk(rec("GameStop 股票的倒计时是否已经开始？", source="finance.yahoo.com"))
    assert is_junk(
        rec(
            "任天堂宣布新消息",
            source="Pocket Tactics",
            title_en="Pokemon Pokopia Free Trial Events Coming to Manila This April 2026",
        )
    )


def test_full_feed_keeps_real_release_announcement_esports_and_business_news():
    assert not is_junk(rec("Classic RPG remake launches on Steam next month"))
    assert not is_junk(rec("Mobile RPG release date announced for Southeast Asia"))
    assert not is_junk(rec("Online RPG shutdown announced as publisher exits market"))
    assert not is_junk(rec("Valorant Pacific tournament qualifier schedule announced for Bangkok"))
    assert not is_junk(rec("NetEase studio layoffs hit mobile RPG developer team"))


def test_radar_section_game_announcements():
    assert section("New tactical RPG trailer revealed at showcase") == "other"
    assert section("Valorant Pacific tournament qualifier schedule announced") == "other"
    assert section("New tactical RPG launches on Steam next month after showcase") == "game_announcements"
    assert (
        section("EA SPORTS FC Pro Mobile set for Bangkok and Seoul showdowns as road to World Championship in October begins")
        == "other"
    )


def test_radar_section_added_by_classify_and_tag():
    tagged = classify_and_tag(rec("Action RPG launches on Steam"))
    assert tagged["radar_section"] == "game_releases"
