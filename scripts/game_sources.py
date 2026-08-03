#!/usr/bin/env python3
"""Configurable source registry for the live Game News pipeline.

This is the ONE place to edit when adding or removing a plain RSS/Atom game
source - no new fetcher code needed. Each entry is fetched by the single
generic `fetch_rss_source()` function in update_game_news.py. Despite the
name, this now covers more than SEA: single-country outlets (SEA + Taiwan),
mixed general-news portals filtered by keyword, and confirmed hyperfocused
global gaming media (region="GLOBAL") - anything that's a plain RSS/Atom
feed belongs here; sites with no native feed go through the RSSHub bridge
in scripts/rsshub_sources.py instead.

Sources that need bespoke scraping (TopHub, Iris, etc.) are NOT config-driven
here - they're imported directly from scripts/update_news.py and wired in
update_game_news.py, since they aren't plain RSS feeds.

To add a source: append an entry below with a unique site_id.
To remove a source: delete its entry (or comment it out).

Fields:
  site_id   - short stable id, used in output data and dedup keys
  site_name - display name
  feed_url  - RSS/Atom feed URL, fetched directly (verified working via curl,
              no login/cookies/JS challenge as of the date noted)
  region    - authoritative region for every item from this source: a
              country code for single-country outlets (trust the source over
              keyword guessing), or "GLOBAL" for confirmed dedicated gaming
              media that isn't region-tied (kept separate from "Others",
              which is the generic/unclassified catch-all - see
              game_news_classify.py)
  dedicated - True if the ENTIRE site is game news (e.g. GamingPH.com), so
              the generic "does the title mention a game keyword" quality
              gate should be skipped - it exists to filter noise out of
              broad aggregators, and would otherwise wrongly drop real
              articles like "GTA 6 PSN Prices Revealed" just because the
              title doesn't literally say "game". False for mixed-topic
              portals like Pokde.Net, where that gate still earns its keep.
  language  - source language, informational only today
  verified  - date this feed URL was last confirmed to return valid XML
"""
from __future__ import annotations

from typing import Any

DIRECT_RSS_SOURCES: list[dict[str, Any]] = [
    {
        "site_id": "gamingph",
        "site_name": "GamingPH.com",
        "feed_url": "https://gamingph.com/feed/",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-07",
    },
    {
        "site_id": "gamingpinas",
        "site_name": "Gaming Pinas",
        "feed_url": "https://gamingpinas.com/feed/",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-07",
    },
    {
        "site_id": "pokde",
        "site_name": "Pokde.Net",
        "feed_url": "https://pokde.net/feed",
        "region": "MY",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-07",
    },
    {
        "site_id": "gamingdose",
        "site_name": "GamingDose",
        "feed_url": "https://www.gamingdose.com/feed/",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-07",
    },
    {
        "site_id": "gamestation_id",
        "site_name": "GameStation.co.id",
        "feed_url": "https://gamestation.co.id/feed/",
        "region": "ID",
        "dedicated": True,
        "language": "id",
        "verified": "2026-07-07",
    },
    {
        "site_id": "gamebrott",
        "site_name": "Gamebrott.com",
        "feed_url": "https://gamebrott.com/feed/",
        "region": "ID",
        "dedicated": True,
        "language": "id",
        "verified": "2026-07-07",
    },
    {
        "site_id": "gamelade",
        "site_name": "Gamelade",
        "feed_url": "https://gamelade.vn/feed/",
        "region": "VN",
        "dedicated": True,
        "language": "vi",
        "verified": "2026-07-07",
    },
    # General-interest news sites, added as dedicated=False (2026-07-08):
    # each covers gaming rarely, but the existing TITLE_GAME_RE keyword gate
    # already filters a mixed feed down to just the game-relevant items (the
    # same mechanism proven on Pokde.Net above) - no new code needed, just
    # accept a low, high-precision trickle rather than rejecting the source
    # outright. Genuinely fills SG/MY, the thinnest regions.
    {
        "site_id": "mothership_sg",
        "site_name": "Mothership.sg",
        "feed_url": "https://mothership.sg/feed/",
        "region": "SG",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "siakapkeli",
        "site_name": "Siakap Keli",
        "feed_url": "https://siakapkeli.my/feed/",
        "region": "MY",
        "dedicated": False,
        "language": "ms",
        "verified": "2026-07-08",
    },
    {
        "site_id": "medcom",
        "site_name": "Medcom.id",
        "feed_url": "https://www.medcom.id/feed",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    {
        "site_id": "genmuda",
        "site_name": "Genmuda.com",
        "feed_url": "https://www.genmuda.com/feed/",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    {
        "site_id": "kaorinusantara",
        "site_name": "Kaori Nusantara",
        "feed_url": "https://www.kaorinusantara.or.id/feed",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    # More general-news portals, added same day, same dedicated=False
    # treatment, verified against live feeds first:
    # inet_detik 6/100, kontan_lifestyle 11/300, mediaindonesia 1/100 passed
    # the keyword gate with genuine hits; liputan6 and straitstimes showed
    # 0/50 and 0/10 in their current window (no ongoing cost to keeping them
    # wired in - see game_news_classify.py's is_junk for why a dry spell
    # isn't a problem). hardwarezone_sg 1/10 - Singapore's biggest tech/
    # gadget forum, same tier as Lowyat.
    {
        "site_id": "inet_detik",
        "site_name": "detikInet",
        "feed_url": "https://inet.detik.com/rss/",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    {
        "site_id": "kontan_lifestyle",
        "site_name": "Kontan Lifestyle",
        "feed_url": "https://lifestyle.kontan.co.id/rss/",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    {
        "site_id": "mediaindonesia",
        "site_name": "Media Indonesia",
        "feed_url": "https://mediaindonesia.com/feed/",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    {
        "site_id": "liputan6",
        "site_name": "Liputan6.com",
        "feed_url": "https://feed.liputan6.com/rss/news",
        "region": "ID",
        "dedicated": False,
        "language": "id",
        "verified": "2026-07-08",
    },
    {
        "site_id": "straitstimes",
        "site_name": "The Straits Times",
        "feed_url": "https://www.straitstimes.com/rss.xml",
        "region": "SG",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "hardwarezone_sg",
        "site_name": "HardwareZone.com.sg",
        "feed_url": "https://www.hardwarezone.com.sg/feed/",
        "region": "SG",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-08",
    },
    # Taiwan -巴哈姆特GNN, Taiwan's largest dedicated gaming news portal.
    # Also the reason TW is a first-class region now: it was being silently
    # miscategorized as China by the generic CJK fallback before this.
    {
        "site_id": "gnn_tw",
        "site_name": "巴哈姆特 GNN",
        "feed_url": "https://gnn.gamer.com.tw/rss_utf8.xml",
        "region": "TW",
        "dedicated": True,
        "language": "zh-tw",
        "verified": "2026-07-08",
    },
    # Confirmed hyperfocused global gaming media - region="GLOBAL" (not
    # "Others"), since these are already known-dedicated gaming journalism,
    # just not tied to one country. GameSpot, PocketGamer, and ClutchPoints
    # were checked the same day but dropped: GameSpot and PocketGamer are
    # Cloudflare-blocked (403), ClutchPoints is rate-limited (429).
    {
        "site_id": "pcgamer",
        "site_name": "PC Gamer",
        "feed_url": "https://www.pcgamer.com/rss/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "gamerant",
        "site_name": "Game Rant",
        "feed_url": "https://gamerant.com/feed/gaming/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamesradar",
        "site_name": "GamesRadar+",
        "feed_url": "https://www.gamesradar.com/feeds.xml",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "polygon",
        "site_name": "Polygon",
        "feed_url": "https://www.polygon.com/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "shacknews",
        "site_name": "Shacknews",
        "feed_url": "https://www.shacknews.com/feed/rss",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "siliconera",
        "site_name": "Siliconera",
        "feed_url": "https://www.siliconera.com/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-08",
    },
    {
        "site_id": "pockettactics",
        "site_name": "Pocket Tactics",
        "feed_url": "https://www.pockettactics.com/mainrss.xml",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-08",
    },
    # ── Round 2 additions (2026-07-09) — 11 candidates researched, 8 verified ──
    # Failures: GamerBraves (403 Cloudflare), Gadget Pilipinas (403 Cloudflare),
    # VALO2ASIA (404 — no RSS feed exists). All 8 below returned 200 via curl.

    # Singapore — Geek Culture fills the dedicated-SG gap. Not a pure game
    # outlet, but the /games/ category feed isolates gaming content cleanly.
    {
        "site_id": "geekculture_sg",
        "site_name": "Geek Culture",
        "feed_url": "https://geekculture.co/games/feed/",
        "region": "SG",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Thailand — GameMonday is a dedicated mobile/MMO outlet (ROV, Free Fire,
    # mobile anime RPG). Blognone covers platform policy, studio business, and
    # app store regulation — strong for "business" content type.
    {
        "site_id": "gamemonday",
        "site_name": "GameMonday",
        "feed_url": "https://www.gamemonday.com/feed/",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-09",
    },
    {
        "site_id": "blognone",
        "site_name": "Blognone",
        "feed_url": "https://www.blognone.com/atom.xml",
        "region": "TH",
        "dedicated": False,
        "language": "th",
        "verified": "2026-07-09",
    },
    # Vietnam — Kenh14 is a major Vietnamese media network; the /sport.rss
    # category covers esports (VCS LoL, Arena of Valor, MLBB) alongside
    # traditional sport. dedicated=False so TITLE_GAME_RE keyword gate filters
    # the non-game sport items.
    {
        "site_id": "kenh14",
        "site_name": "Kenh14 Sport & Esports",
        "feed_url": "https://kenh14.vn/rss/sport.rss",
        "region": "VN",
        "dedicated": False,
        "language": "vi",
        "verified": "2026-07-09",
    },
    # Malaysia — Lowyat.NET gaming category. Malaysia's largest consumer tech
    # portal; gaming subsection covers platform news, console/PC launches,
    # regional market activities. GamerBraves (the dedicated MY outlet) was
    # 403 Cloudflare-blocked during verification.
    {
        "site_id": "lowyat",
        "site_name": "Lowyat.NET Gaming",
        "feed_url": "https://www.lowyat.net/category/gaming/feed/",
        "region": "MY",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Philippines — Ungeek covers tech + gaming + geek culture; editorial team
    # with strong mobile and local event coverage.
    {
        "site_id": "ungeek",
        "site_name": "Ungeek",
        "feed_url": "https://www.ungeek.ph/feed/",
        "region": "PH",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Malaysia — Kakuchopurei is the dedicated SEA gaming outlet missing from
    # round 1. Original regional coverage: fighting games, mobile esports,
    # anime adaptations, local indie developers. Returned 200 via curl.
    {
        "site_id": "kakuchopurei",
        "site_name": "Kakuchopurei",
        "feed_url": "https://www.kakuchopurei.com/feed/",
        "region": "MY",
        "dedicated": False,  # games + anime/pop culture mix; keyword gate earns its keep
        "language": "en",
        "verified": "2026-07-09",
    },
    # Philippines — YugaTech is the largest PH consumer tech site. Gaming desk
    # covers developer layoffs, domestic digital policies, hardware launches,
    # and major game updates. Category feed isolates gaming content.
    {
        "site_id": "yugatech",
        "site_name": "YugaTech Gaming",
        "feed_url": "https://www.yugatech.com/category/gaming/feed/",
        "region": "PH",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Vietnam — GenK is a major VN tech portal (VCCorp). The /rss/apps-games.rss
    # category feed targets gaming/app content only, avoiding general tech noise.
    # Note: VCCorp properties occasionally activate CDN bot-blocking (intermittent
    # 403s); this and gamek_vn below may fail on some pipeline runs — fail-open.
    {
        "site_id": "genk_vn",
        "site_name": "GenK Apps & Games",
        "feed_url": "https://genk.vn/rss/apps-games.rss",
        "region": "VN",
        "dedicated": False,
        "language": "vi",
        "verified": "2026-07-09",
    },
    {
        "site_id": "gamek_vn",
        "site_name": "GameK Esport",
        "feed_url": "https://gamek.vn/esport.rss",
        "region": "VN",
        "dedicated": True,
        "language": "vi",
        "verified": "2026-07-09",
    },
    # ── Round 3 additions (2026-07-09) — Codex deep research ──────────────
    # This pass actually parsed feed XML and checked item recency (≥3 items
    # in the last 7 days), catching two false approvals from rounds 1-2:
    # AFK Gaming (HTML not XML) and TouchArcade (dormant since Apr 2025).
    # All 11 below returned 200 + valid XML content-type in live checks.

    # Singapore — IGN SEA edition. Dedicated regional staff, covers SEA
    # game launches and local pricing. Not SG-only but fills the gap.
    {
        "site_id": "ign_sea",
        "site_name": "IGN Southeast Asia",
        "feed_url": "https://sea.ign.com/feed.xml",
        "region": "GLOBAL",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Thailand — three more dedicated TH outlets. Thisisgame and COMPGAMER
    # are fully dedicated gaming sites. 4Gamers has cosplay/anime spillover
    # so dedicated=False to keep the keyword gate active.
    {
        "site_id": "thisisgame_th",
        "site_name": "Thisisgame Thailand",
        "feed_url": "https://thisisgamethailand.com/feed/",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-09",
    },
    {
        "site_id": "compgamer_th",
        "site_name": "COMPGAMER",
        "feed_url": "https://compgamer.com/feed/",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-09",
    },
    {
        "site_id": "fourgamers_th",
        "site_name": "4Gamers Thailand",
        "feed_url": "https://www.4gamers.co.th/rss/latest-news",
        "region": "TH",
        "dedicated": False,
        "language": "th",
        "verified": "2026-07-09",
    },
    # Vietnam — two additional dedicated VN gaming sites. GameHub had 25
    # recent items in the parsed check; XemGame had 10. Both fully dedicated.
    {
        "site_id": "gamehub_vn",
        "site_name": "GameHub",
        "feed_url": "https://gamehub.vn/portal/index.rss",
        "region": "VN",
        "dedicated": True,
        "language": "vi",
        "verified": "2026-07-09",
    },
    {
        "site_id": "xemgame_vn",
        "site_name": "XemGame",
        "feed_url": "https://www.xemgame.com/feed",
        "region": "VN",
        "dedicated": True,
        "language": "vi",
        "verified": "2026-07-09",
    },
    # Malaysia — Gamer Matters is a dedicated MY gaming outlet with good
    # platform/update/business signal. The Magic Rain covers games + esports
    # + anime so dedicated=False for the keyword gate.
    {
        "site_id": "gamermatters",
        "site_name": "Gamer Matters",
        "feed_url": "https://gamermatters.com/feed/",
        "region": "MY",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-09",
    },
    {
        "site_id": "themagicrain",
        "site_name": "The Magic Rain",
        "feed_url": "https://themagicrain.com/feed/",
        "region": "MY",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Philippines — Reimaru Files: game-heavy PH source, mobile/esports/launch.
    {
        "site_id": "reimarufiles",
        "site_name": "The Reimaru Files",
        "feed_url": "https://www.reimarufiles.com/feed/",
        "region": "PH",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Global mobile business — both are distinct from the blocked consumer
    # sites. MobileGamer.biz covers studio shutdowns, revenue, layoffs.
    # PocketGamer.biz is the trade/B2B edition (NOT the blocked .com).
    {
        "site_id": "mobilegamer_biz",
        "site_name": "MobileGamer.biz",
        "feed_url": "https://mobilegamer.biz/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-09",
    },
    {
        "site_id": "pocketgamer_biz",
        "site_name": "PocketGamer.biz",
        "feed_url": "https://www.pocketgamer.biz/rss/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-09",
    },
    # ── Round 4 additions (2026-07-09) — Qwen research ──────────────────
    # All verified 200 + valid XML. Qwen's "blocked" flags for Blognone and
    # HardwareZone were wrong — both return 200 with correct URLs.
    # gamek.vn/trang-chu.rss (main feed) skipped — content covered by the
    # esport.rss + mobile-social.rss combo with less duplication.

    # Vietnam — GameK mobile category. SEA is predominantly mobile so this
    # feed gives a dedicated mobile-first signal from the same trusted source.
    {
        "site_id": "gamek_vn_mobile",
        "site_name": "GameK Mobile",
        "feed_url": "https://gamek.vn/mobile-social.rss",
        "region": "VN",
        "dedicated": False,
        "language": "vi",
        "verified": "2026-07-09",
    },
    # Global B2B / business — GamesIndustry.biz is the trade press of record.
    # Covers acquisitions, studio closures, earnings, market reports. Articles
    # reference the studio/publisher not always specific game titles, so
    # dedicated=True skips the game-title keyword gate.
    {
        "site_id": "gamesindustry_biz",
        "site_name": "GamesIndustry.biz",
        "feed_url": "https://www.gamesindustry.biz/feed",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Global esports — Esports.net and Dot Esports both cover Valorant, LoL,
    # CS2, and mobile titles with SEA tournament coverage.
    {
        "site_id": "esports_net",
        "site_name": "Esports.net",
        "feed_url": "https://www.esports.net/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-09",
    },
    {
        "site_id": "dotesports",
        "site_name": "Dot Esports",
        "feed_url": "https://dotesports.com/feed",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-09",
    },
    # Global RPG-focused media. Good fit for IBD because it catches RPG launch,
    # platform, mobile, and publisher announcements that broad game feeds miss.
    {
        "site_id": "rpgsite",
        "site_name": "RPG Site",
        "feed_url": "https://www.rpgsite.net/feed",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamingonphone",
        "site_name": "GamingonPhone",
        "feed_url": "https://gamingonphone.com/category/news/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "comicbook_gaming",
        "site_name": "ComicBook Gaming",
        "feed_url": "https://comicbook.com/category/gaming/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "lapakgaming_my",
        "site_name": "Lapakgaming Malaysia Blog",
        "feed_url": "https://www.lapakgaming.com/blog/en-my/feed/",
        "region": "MY",
        "dedicated": False,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "player_one",
        "site_name": "Player.One",
        "feed_url": "https://www.player.one/rss",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "nerdschalk_gaming",
        "site_name": "Nerdschalk Gaming",
        "feed_url": "https://nerdschalk.com/category/gaming/feed/",
        "region": "GLOBAL",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    # High-priority gaming media RSS sources from Alan audit (2026-07-30).
    {
        "site_id": "gamespot_asia",
        "site_name": "GameSpot Asia",
        "feed_url": "https://www.gamespot.com/feeds/news/",
        "region": "SG",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamek_home",
        "site_name": "GameK",
        "feed_url": "https://gamek.vn/home.rss",
        "region": "VN",
        "dedicated": False,
        "language": "vi",
        "verified": "2026-07-30",
    },
    {
        "site_id": "fourgamers_tw",
        "site_name": "4Gamers Taiwan",
        "feed_url": "https://www.4gamers.com.tw/rss/latest-news",
        "region": "TW",
        "dedicated": True,
        "language": "zh-tw",
        "verified": "2026-07-30",
    },
    {
        "site_id": "techhub_th",
        "site_name": "TechHub Gaming",
        "feed_url": "https://www.techhub.in.th/feed/",
        "region": "TH",
        "dedicated": False,
        "language": "th",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamehub_vn_forum",
        "site_name": "GameHub Forum",
        "feed_url": "https://gamehub.vn/forum/-/index.rss",
        "region": "VN",
        "dedicated": True,
        "language": "vi",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gametoc",
        "site_name": "GameToc",
        "feed_url": "https://cdn.gametoc.co.kr/rss/gn_rss_allArticle.xml",
        "region": "KR",
        "dedicated": True,
        "language": "ko",
        "verified": "2026-07-30",
    },
    {
        "site_id": "vietgame",
        "site_name": "VietGame",
        "feed_url": "https://vietgame.asia/feed/",
        "region": "VN",
        "dedicated": True,
        "language": "vi",
        "verified": "2026-07-30",
    },
    {
        "site_id": "game_ded",
        "site_name": "Game-Ded",
        "feed_url": "https://www.game-ded.com/feed",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-30",
    },
    {
        "site_id": "pinoygamer",
        "site_name": "PinoyGamer",
        "feed_url": "https://pinoygamer.ph/news/index.rss?order=post_date",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamevu",
        "site_name": "GameVu",
        "feed_url": "https://cdn.gamevu.co.kr/rss/gn_rss_allArticle.xml",
        "region": "KR",
        "dedicated": True,
        "language": "ko",
        "verified": "2026-07-30",
    },
    {
        "site_id": "game_chosun",
        "site_name": "Game Chosun",
        "feed_url": "https://www.gamechosun.co.kr/rss/",
        "region": "KR",
        "dedicated": True,
        "language": "ko",
        "verified": "2026-07-30",
    },
    {
        "site_id": "khgames",
        "site_name": "KHGames",
        "feed_url": "https://cdn.khgames.co.kr/rss/gn_rss_allArticle.xml",
        "region": "KR",
        "dedicated": True,
        "language": "ko",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamersantai",
        "site_name": "GamerSantai",
        "feed_url": "https://gamersantai.com/feed/",
        "region": "MY",
        "dedicated": True,
        "language": "ms",
        "verified": "2026-07-30",
    },
    {
        "site_id": "udn_game",
        "site_name": "UDN Game",
        "feed_url": "https://game.udn.com/game/rssfeed/",
        "region": "TW",
        "dedicated": True,
        "language": "zh-tw",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamelook",
        "site_name": "GameLook",
        "feed_url": "http://www.gamelook.com.cn/feed/",
        "region": "CN",
        "dedicated": True,
        "language": "zh-cn",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gamerculture_th",
        "site_name": "GamerCulture",
        "feed_url": "https://gamerculture.co/feed/",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-30",
    },
    {
        "site_id": "jomgaming",
        "site_name": "JomGaming",
        "feed_url": "https://jomgaming.my/feed/",
        "region": "MY",
        "dedicated": True,
        "language": "ms",
        "verified": "2026-07-30",
    },
    {
        "site_id": "vcgamers",
        "site_name": "VCGamers",
        "feed_url": "https://www.vcgamers.com/news/feed/",
        "region": "ID",
        "dedicated": True,
        "language": "id",
        "verified": "2026-07-30",
    },
    {
        "site_id": "yuga_gaming",
        "site_name": "YUGA Gaming",
        "feed_url": "https://gaming.yugatech.com/feed/",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "divine_shop_games",
        "site_name": "Divine Shop Games",
        "feed_url": "https://divineshop.vn/tin-tuc/feed/",
        "region": "VN",
        "dedicated": False,
        "language": "vi",
        "verified": "2026-07-30",
    },
    {
        "site_id": "game_ops",
        "site_name": "Game Ops",
        "feed_url": "https://feeds.feedburner.com/gameops",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "gcores",
        "site_name": "GCores",
        "feed_url": "https://www.gcores.com/rss",
        "region": "CN",
        "dedicated": True,
        "language": "zh-cn",
        "verified": "2026-07-30",
    },
    {
        "site_id": "liputan6_tekno_game",
        "site_name": "Liputan6 Tekno Game",
        "feed_url": "https://feed.liputan6.com/rss/tekno/game",
        "region": "ID",
        "dedicated": True,
        "language": "id",
        "verified": "2026-07-30",
    },
    {
        "site_id": "one_more_game_ph",
        "site_name": "One More Game PH",
        "feed_url": "https://onemoregame.ph/feed/",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "pcbang",
        "site_name": "PCBang",
        "feed_url": "https://cdn.ilovepcbang.com/rss/gn_rss_allArticle.xml",
        "region": "KR",
        "dedicated": True,
        "language": "ko",
        "verified": "2026-07-30",
    },
    {
        "site_id": "thaigamers",
        "site_name": "ThaiGamers",
        "feed_url": "https://thai-gamers.com/feed/",
        "region": "TH",
        "dedicated": True,
        "language": "th",
        "verified": "2026-07-30",
    },
    {
        "site_id": "the_game_ph",
        "site_name": "The GAME Ph",
        "feed_url": "https://thegame.ph/feed/",
        "region": "PH",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "virtuos_games",
        "site_name": "Virtuos Games",
        "feed_url": "https://www.virtuosgames.com/feed/",
        "region": "SG",
        "dedicated": True,
        "language": "en",
        "verified": "2026-07-30",
    },
    {
        "site_id": "youyanshe",
        "site_name": "YouYanShe",
        "feed_url": "https://www.yystv.cn/rss/feed",
        "region": "CN",
        "dedicated": True,
        "language": "zh-cn",
        "verified": "2026-07-30",
    },
    # Note: TouchArcade removed — feed verified 200 but dormant since
    # 2025-04-18 (Codex research confirmed latest item date). Not useful
    # for a live 24h radar.
    # Note: AFK Gaming removed — feed returns text/html not RSS XML despite
    # HTTP 200. Codex research caught this; our initial curl missed it.
]

# Singapore status as of 2026-07-09: Geek Culture (/games/ category feed)
# added as the closest functional dedicated-games outlet for SG. Still no
# unblocked pure-gaming outlet found — SCOGA (rsshub_sources.py), Mothership,
# Straits Times, HardwareZone, and Geek Culture remain the SG signal pool.
