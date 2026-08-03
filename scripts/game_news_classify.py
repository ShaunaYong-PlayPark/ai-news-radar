#!/usr/bin/env python3
"""Shared quality-gate + classification rules for Game News items.

Used by both build_game_news.py (one-time historical seed processing) and
update_game_news.py (the live pipeline), so the two never drift apart.

Region rule (in priority order):
  1. Recurring daily filler (Wordle/Quordle/Connections/Strands/"hints and
     answers" style posts) -> Misc, regardless of language or source.
  2. Source-level override - single-country outlets (game_sources.py) and
     confirmed hyperfocused global gaming media (region_override="GLOBAL")
     are trusted over guessing from text.
  3. Explicit SEA country name/city in the title or source -> that country.
  4. Explicit Taiwan name/city -> Taiwan (checked before the China fallback,
     since Taiwan content is also Chinese-script and would otherwise be
     miscategorized as China by the generic CJK catch-all).
  5. Explicit China marker, or CJK script in the title -> China.
  6. Otherwise -> Others. "Others" is the generic/unclassified catch-all;
     "Global" (via region_override, above) is reserved for sources already
     confirmed as dedicated gaming media that just aren't region-tied -
     e.g. Riot Games, PC Gamer - so the two don't blend together.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Source boards that are not game news even though a title matched the
# keyword regex (e-commerce, app charts, design portfolios, generic forums).
JUNK_SOURCE_MARKERS = [
    "京东", "淘宝", "天猫", "拼多多", "苏宁",  # e-commerce bestseller lists
    "App Store",  # app ranking charts, not news
    "站酷",  # design-portfolio site
    "北大未名",  # general campus forum
]

ALIAS_NORMALIZATIONS = {
    "游戏驿站": "GameStop",
}

SEA_COUNTRY_PATTERNS: list[tuple[str, str, str]] = [
    ("TH", "Thailand", r"thailand|\bthai\b|泰国|曼谷"),
    ("PH", "Philippines", r"philippines|filipino|菲律宾|马尼拉"),
    ("VN", "Vietnam", r"vietnam|越南|河内"),
    ("SG", "Singapore", r"singapore|新加坡"),
    ("MY", "Malaysia", r"malaysia|马来西亚|吉隆坡"),
    ("ID", "Indonesia", r"indonesia|印尼|印度尼西亚|雅加达"),
]
TW_PATTERN = re.compile(r"taiwan|台湾|臺灣|台北|高雄|巴哈姆特", re.I)
CN_PATTERN = re.compile(r"中国大陆|中国(?!台湾|香港)|国产游戏|大陆(?!.*(台|港))")
CJK_PATTERN = re.compile(r"[一-鿿]")

# Daily word/puzzle-game "hints and answers" posts. Tech media republishes
# these every day for a handful of named puzzle brands - it's filler, not
# game industry news. Matched on brand name OR generic recap phrasing so a
# new puzzle brand still gets caught.
MISC_PATTERN = re.compile(
    r"\b(wordle|quordle|octordle|connections|strands|nyt mini|spelling bee|"
    r"heardle|waffle|crossword)\b|hints and answers|answers for (monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday)",
    re.I,
)

CONTENT_TYPE_PATTERNS: list[tuple[str, str]] = [
    ("launch", r"上线|发售|首发|公测|预约|首曝|launch|release[ds]?|out now|early access"),
    ("update", r"更新|补丁|改版|新赛季|dlc|hotfix|patch|update"),
    ("business", r"收购|投资|财报|营收|上市|裁员|acquisition|acquires|revenue|layoffs?|ipo|funding"),
    ("platform", r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch\b|app store|平台|主机|store"),
    ("esports", r"电竞|esports?|赛事|冠军|锦标赛|tournament|championship"),
]

# The seed matched a loose keyword regex against title+source combined,
# which lets a source/handle name merely containing "game" (e.g. a Twitter
# handle like "WoWGamerPVP") through even when the title has nothing to do
# with games. Re-check against the title alone as a quality gate.
TITLE_GAME_RE = re.compile(
    r"game|gaming|游戏|电竞|esport|手游|steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch\b",
    re.I,
)

BROAD_GAME_RE = re.compile(
    r"game|gaming|rpg|jrpg|gacha|steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch\b|"
    r"app store|google play|ios|android|mobile",
    re.I,
)

MARKET_NEWS_RE = re.compile(
    r"pre[- ]?registration|pre[- ]?order|soft launch|closed beta|open beta|early access|"
    r"release date|launch(?:es|ed|ing)?|out now|available now|coming to|"
    r"relaunch|re-release|rerelease|remake|remaster|reboot|port|mobile version|pc version|console version|"
    r"delay(?:ed|s)?|postpone(?:d|s|ment)?|cancel(?:led|s|ation)?|shutdown|shut down|server closure|delist(?:ed|ing)?|"
    r"publisher|publishing rights|developer|studio|acqui(?:re|res|red|sition)|funding|investment|layoffs?|revenue|"
    r"tournament|championship|qualifier|league|worlds|world championship|prize pool|sponsor(?:ship)?|"
    r"offline event|launch event|showcase|gamescom|tokyo game show|tgs|summer game fest",
    re.I,
)

UTILITY_GUIDE_RE = re.compile(
    r"\bhow to\b|where to find|walkthrough|guide|best build|builds?|tier list|codes?|cheats?|tips?|"
    r"ending(?:s)? explained|location guide|all .* locations|settings guide|unlock|counter .* in|"
    r"damage build|best .* heroes|best .* skins|pass math",
    re.I,
)

ROUTINE_LIVEOPS_RE = re.compile(
    r"\bdlc\b|expansion|new costume|costumes?|new skin|skins?|banner|season pass|battle pass|"
    r"new character|new weapon|new map|patch notes?|hotfix|balance (?:change|changes|patch)|"
    r"login event|event shop|daily rewards?|rerun event|collaboration cosmetics?|"
    r"limited[- ]time mission|limited[- ]time event",
    re.I,
)

PATCH_UPDATE_NOTE_RE = re.compile(
    r"patch(?:\s+v?[\d.]+)?\s+notes?|update notes?|hotfix|balance patch|bug fix(?:es)? patch|version update|"
    r"version\s+v?[\d.]+|maintenance update|minor content update|balance fixes|bug updates|bug fixes",
    re.I,
)

MAJOR_RELEASE_SIGNAL_RE = re.compile(
    r"full launch|global launch|official launch|new platform launch|early access launch|"
    r"relaunch|re-release|rerelease|standalone (?:paid )?release|shutdown|shut down|server closure|"
    r"delist(?:ed|ing)?|remake.{0,80}(?:launch|release)|remaster.{0,80}(?:launch|release)|"
    r"(?:launch(?:es|ed|ing)?|release[ds]?).{0,80}(?:remake|remaster)|"
    r"launch(?:es|ed|ing)? (?:on|for|to) (?:steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch|"
    r"app store|google play|ios|android|pc|mobile)",
    re.I,
)

PERIPHERAL_RE = re.compile(
    r"accessor(?:y|ies)|peripheral|keyboard|mouse|headset|monitor|gaming chair|controller review|controller|"
    r"gpu|graphics card|laptop|pc build|hardware deal",
    re.I,
)

PLATFORM_MARKET_RE = re.compile(
    r"nintendo|switch|playstation|\bps5\b|\bps4\b|xbox|steam|game pass|app store|google play|ios|android|"
    r"handheld|console|price|pricing|subscription|launch|release|delay|postpone",
    re.I,
)

NON_GAME_IP_RE = re.compile(
    r"anime|manga|movie|tv series|episode|season|voice actor|box office|figurine|figure|merch|cosplay|card game",
    re.I,
)

VIDEO_GAME_SIGNAL_RE = re.compile(
    r"video game|mobile game|console game|pc game|rpg|jrpg|gacha|steam|playstation|\bps5\b|\bps4\b|"
    r"xbox|nintendo|switch|app store|google play|ios|android",
    re.I,
)

ANIME_IP_RE = re.compile(
    r"one piece|naruto|dragon ball|bleach|jujutsu kaisen|demon slayer|attack on titan|solo leveling|"
    r"my hero academia|chainsaw man|spy x family|hunter x hunter",
    re.I,
)

TITLE_GAME_RE = re.compile(
    TITLE_GAME_RE.pattern.replace(r"playstation|", r"playstation|\bpsn\b|"),
    re.I,
)
BROAD_GAME_RE = re.compile(
    BROAD_GAME_RE.pattern.replace(r"playstation|", r"playstation|\bpsn\b|"),
    re.I,
)
MARKET_NEWS_RE = re.compile(
    MARKET_NEWS_RE.pattern.replace("reboot|port|", r"reboot|\bport\b|")
    + r"|sales|\bsells?\b|\bselling\b|\bsold\b|copies|downloads|grossing|wishlist(?:s|ed)?",
    re.I,
)
SOURCE_GAME_RE = re.compile(r"game|gaming|esport|rpg|playstation|xbox|nintendo|steam", re.I)
GAME_BUSINESS_RE = re.compile(
    r"game studio|game developer|developer|publisher|riot|sony interactive|nintendo|sega|square enix|"
    r"nexon|netease|tencent|hoyoverse|mihoyo|krafton|garena|ubisoft|electronic arts|\bea\b|"
    r"activision|blizzard|take[- ]two|rockstar|valve|epic games|unity|roblox|bandai namco|"
    r"capcom|konami|koei tecmo|ncsoft|smilegate|shift up|pearl abyss|kakao games|webzen|com2us|yostar",
    re.I,
)
FINANCE_ONLY_RE = re.compile(
    r"earnings|revenue|share buybacks?|eps|stock|quarterly results|\bq[1-4]\b|"
    r"lost \$|profit|operating loss|\$[0-9.]+ billion",
    re.I,
)
UTILITY_GUIDE_RE = re.compile(UTILITY_GUIDE_RE.pattern + r"|kode redeem|redeem code", re.I)
REVIEW_RE = re.compile(r"\breviews?\b|hands[- ]on|first impressions", re.I)
CELEBRITY_LIFESTYLE_RE = re.compile(
    r"hot girl|cosplay|cosplayer|bikini|gym|model|actor|actress|influencer|streamer|"
    r"nữ diễn viên|ca sĩ|mỹ nhân|khoe dáng|nhan sắc|game thủ trong bộ ảnh",
    re.I,
)
POST_RELEASE_DISCUSSION_RE = re.compile(
    r"weeks since .* released|months since .* released|years since .* released|since .* was released|"
    r"post[- ]release|debate|discussion|lore|explained|is .* real",
    re.I,
)
ACCESSORY_DLC_TIMING_RE = re.compile(
    r"(accessor(?:y|ies)|peripheral|controller|headset|keyboard|mouse|monitor|hardware|hori).{0,100}"
    r"(dlc|expansion|costume|skin|banner|launch)|"
    r"(dlc|expansion|costume|skin|banner).{0,100}"
    r"(accessor(?:y|ies)|peripheral|controller|headset|keyboard|mouse|monitor|hardware|hori)",
    re.I,
)
IDIOMATIC_GAME_RE = re.compile(r"\b(changed the game|game of chance|game changer|whole new game)\b", re.I)
FINANCE_ONLY_GAMESTOP_EBAY_RE = re.compile(r"gamestop.*ebay|ebay.*gamestop", re.I)
GAMESTOP_FINANCE_RE = re.compile(
    r"gamestop.*(?:stock|shares?|investors?|ceo|ryan cohen|pay package|profit|sales|lawsuit|"
    r"board|stake|holdings?|wallstreetbets|gme|股票|股价|投資|投资|投資者|投资者|收购|"
    r"首席执行官|薪酬|利润|銷售|销售|董事会|持股|股东)|"
    r"(?:stock|shares?|investors?|ceo|ryan cohen|profit|sales|股票|股价|投资|投資|收购).{0,80}gamestop",
    re.I,
)
FINANCE_SOURCE_RE = re.compile(
    r"finance\.yahoo|bloomberg|barrons|marketwatch|reuters|reut\.rs|wsj|ft\.com|businessinsider|news\.google",
    re.I,
)
LOOSE_AI_TOOL_RE = re.compile(
    r"\b(claude|gemini|anthropic|openai|ai tools?|antigravity|mcp|cli|agentic|chatbot)\b",
    re.I,
)
REAL_GAME_LIFECYCLE_RE = re.compile(
    r"mobile game|video game|pc game|console game|rpg|jrpg|mmorpg|gacha|"
    r"launch(?:es|ed|ing)?|release date|out now|available now|pre[- ]?registration|"
    r"soft launch|closed beta|open beta|early access|remake|remaster|relaunch|shutdown|"
    r"tournament|championship|qualifier",
    re.I,
)
GENERIC_EVENT_DLC_RE = re.compile(
    r"\ball .* events?\b|free trial events?|login event|event rewards?|event guide|"
    r"dlc launches early|dlc release date seemingly|expansive dlc|festival starts|new items",
    re.I,
)
AI_DEV_TOOL_GAME_NOISE_RE = re.compile(
    r"show hn:.*claude|claude.*(?:json|code|coding|generated?|desktop|mcp|game studios|atmospheric|shared memory)|"
    r"unreal engine.*(?:claude|gemini)|unreal editor.*(?:claude|gemini)|gemini.*(?:cli|gaming mode)",
    re.I,
)
POKOPIA_EVENT_DLC_NOISE_RE = re.compile(r"pokemon pokopia.*(?:events?|dlc|free trial)", re.I)

HOT_LIFECYCLE_RE = re.compile(
    r"launch(?:es|ed|ing)?|release date|\breleased\b|out now|available now|pre[- ]?registration|"
    r"pre[- ]?order|closed beta|open beta|beta test|soft launch|early access|remake|remaster|"
    r"relaunch|re-release|rerelease|port(?:ed|ing)?|delay(?:ed|s)?|postpone(?:d|s|ment)?|"
    r"cancel(?:led|s|ation)?|shutdown|shut down|server closure|delist(?:ed|ing)?",
    re.I,
)
HOT_BUSINESS_RE = re.compile(
    r"publisher|publishing rights|developer|studio|acqui(?:re|res|red|sition)|merger|funding|"
    r"investment|layoffs?|restructur(?:e|ing)|revenue|sales|\bsells?\b|\bselling\b|\bsold\b|copies|downloads|"
    r"grossing|profit|earnings",
    re.I,
)
HOT_ESPORTS_RE = re.compile(
    r"tournament|championship|qualifier|league|worlds|world championship|grand final|finals|"
    r"prize pool|esports?|e-sports?|playoffs",
    re.I,
)
HOT_PLATFORM_RE = re.compile(
    r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch\b|app store|google play|"
    r"game pass|epic games store|ios|android",
    re.I,
)
HOT_GAME_SIGNAL_RE = re.compile(
    r"game|gaming|video game|mobile game|pc game|console game|rpg|jrpg|gacha|mmorpg|"
    r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch\b|app store|google play|"
    r"ios|android|esports?",
    re.I,
)
HOT_CORE_GAME_SIGNAL_RE = re.compile(
    r"game|gaming|video game|mobile game|pc game|console game|rpg|jrpg|gacha|mmorpg|"
    r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|nintendo switch|switch 2|esports?",
    re.I,
)
HOT_CLOSED_TEST_RE = re.compile(r"closed network test|closed beta test|network test", re.I)
HOT_CLOSED_TEST_NO_DATE_RE = re.compile(
    r"(?:closed network test|closed beta test|network test).{0,100}"
    r"(?:full release date[^.]{0,30}(?:tba|not announced|unknown)|"
    r"(?:release date|full release)[^.]{0,70}(?:tba|not announced|has yet to be announced|not been announced)|"
    r"no (?:full )?release date)",
    re.I,
)
HOT_HARDWARE_PRODUCT_RE = re.compile(
    r"razer\s+(?:huntsman|keyboard|mouse|headset|controller)|hall effect|"
    r"(?:mechanical )?(?:keyboard|mouse|headset|controller)|gaming earbuds?|gaming monitor|"
    r"graphics card|gaming laptop|webcam|capture card|ar glasses|smart glasses|gaming glasses|"
    r"steamos|steam client|client beta|sd cards?|storage pricing|cpu tech|workstation tech|"
    r"amd.{0,40}(?:cpu|workstation|tech)",
    re.I,
)
HOT_CARD_GAME_RE = re.compile(r"\b(?:naruto|one piece|pokemon|pokémon|dragon ball).{0,50}\bcard game\b|\bcard game\b", re.I)
HOT_EDITORIAL_NOISE_RE = re.compile(
    r"\binterview\b|retrospective|looking back|in retrospect|associate game director|"
    r"showrunner|\btv series\b|\bmovie\b|\bfilm\b|\banime\b|\bseries\b|"
    r"\bpotential launch titles?\b|\b\d+\s+.*games?\s+that could\b|"
    r"external development|lessons? have developers? learned|secrets of|"
    r"how the developer|company-wide redundancy|selling video game merchandise|"
    r"hints? at (?:its )?lineup|\bdreams?\b|becoming independent|independent from",
    re.I,
)
HOT_CONSOLE_ONLY_RE = re.compile(
    r"\b(?:switch(?: 2)?|ps5|ps4|playstation|xbox|nintendo)\b",
    re.I,
)
HOT_MAJOR_IP_RE = re.compile(
    r"grand theft auto|\bgta\b|pokemon|pokémon|zelda|mario|elden ring|call of duty|"
    r"final fantasy|resident evil|monster hunter|assassin(?:'|’)s creed|stardew valley|"
    r"minecraft|fortnite|star wars|marvel",
    re.I,
)
HOT_DLC_MAJOR_RE = re.compile(r"\bdlc\b|expansion", re.I)
HOT_ACCESSORY_RE = re.compile(r"accessor(?:y|ies)|controller|headset|keyboard|mouse|monitor|chair", re.I)
DOWNLOAD_CODE_RE = re.compile(r"download code|code in the box", re.I)

RADAR_SECTION_LABELS = {
    "industry_reports": "Industry Reports",
    "game_releases": "Game Releases",
    "game_announcements": "Game Announcements",
    "other": "Other",
}
RADAR_WEAK_RE = re.compile(
    r"\bshould\b|\bcould\b|\bmay\b|rumou?red|reportedly|overdue|wishlist|opinion|"
    r"\bbest\b|ranked|listicle|guide|codes?|\breviews?\b",
    re.I,
)
RADAR_SPECULATION_RE = re.compile(
    r"\bpraying\b|\bprays?\b|overdue|\bshould\b|\bcould\b|\bmay\b|speculation|speculative|wishlist|\bwants?\b|\bhopes?\b|rumou?r",
    re.I,
)
RADAR_INDUSTRY_RE = re.compile(
    r"\bq[1-4]\b|earnings|revenue|\bceo\b|\bcfo\b|\blayoffs?\b|acquisition|acquires?|merger|"
    r"funding|investment|publisher|studio|developer|market report|sales|downloads|grossing|"
    r"user spending|\bmau\b|\bdau\b|app store|google play|steam business|policy|"
    r"nintendo|sony|microsoft|xbox|playstation|tencent|netease|krafton|nexon|hoyoverse|"
    r"mihoyo|riot|roblox|ubisoft|electronic arts|\bea\b|take[- ]two",
    re.I,
)
RADAR_STRONG_INDUSTRY_RE = re.compile(
    r"\bq[1-4]\b|earnings|revenue|\bceo\b|\bcfo\b|layoffs?|acquisition|acquires?|merger|"
    r"funding|investment|publisher|studio|developer|market report|sales|\bsells?\b|\bselling\b|\bsold\b|"
    r"copies|best[- ]selling|\$[0-9][0-9,.]*(?:k|m|b| thousand| million| billion)?|downloads|grossing|"
    r"user spending|\bmau\b|\bdau\b|steam business|policy",
    re.I,
)
RADAR_RELEASE_RE = re.compile(
    r"launch(?:es|ed|ing)?|(?:gets?|sets?|confirms?|announces?|reveals?|has|receives?) (?:a |an |the )?release date|"
    r"\breleased\b|out now|available now|coming to|"
    r"pre[- ]?registration|pre[- ]?order|beta|soft launch|early access|demo released|"
    r"\bport (?:announced|coming)|(?:coming|launch(?:es|ed|ing)?) to (?:steam|playstation|\bps5\b|\bps4\b|"
    r"xbox|nintendo|switch|app store|google play|ios|android|pc|mobile)|"
    r"remake .*release|remaster .*release|relaunch|re-release|rerelease|delay(?:ed|s)?|"
    r"postpone(?:d|s|ment)?|cancel(?:led|s|ation)?|shutdown|shut down|delist(?:ed|ing)?",
    re.I,
)
RADAR_RELEASED_RE = re.compile(
    r"out now|now available|available now|soft[- ]?launched|launched on|launched for|"
    r"launch(?:es|ed)? today|officially launches in (?:sea|southeast asia|singapore|vietnam|thailand|"
    r"philippines|indonesia|malaysia)|released on|released for|early access launched|is live",
    re.I,
)
RADAR_CURRENT_RELEASE_RE = re.compile(
    r"out now|now available|available now|soft[- ]?launched|launch(?:es|ed)? today|"
    r"early access launched|launched into early access|available in early access|"
    r"enters? early access(?: now| today)?|early access (?:is )?(?:live|available)|"
    r"early access[^.;]{0,20}(?:now|today|แล้ววันนี้)|"
    r"(?:เปิดให้เล่น|เปิดให้บริการ)[^.;]{0,30}early access|"
    r"beta (?:is )?live|opened now|"
    r"launch(?:es|ed)?\s+(?:on|for|to)\s+[^.;]{0,60}\bearly access\b|is live",
    re.I,
)
RADAR_STANDALONE_RELEASE_RE = re.compile(
    r"standalone (?:paid )?release|full launch|global launch|official launch",
    re.I,
)
RADAR_FUTURE_RELEASE_RE = re.compile(
    r"release date|launch window|launch(?:es|ed|ing)?\s+(?:on|for|in|this|next)|\bcoming (?:soon|to)|pre[- ]?registration|pre[- ]?order|beta|soft launch|early access|"
    r"\bport (?:announced|coming)|(?:coming|launch(?:es|ed|ing)?) to (?:steam|playstation|\bps5\b|\bps4\b|"
    r"xbox|nintendo|switch|app store|google play|ios|android|pc|mobile)|"
    r"remake .*release|remaster .*release|relaunch|re-release|rerelease|delay(?:ed|s)?|"
    r"postpone(?:d|s|ment)?|shutdown|shut down|delist(?:ed|ing)?",
    re.I,
)
RADAR_FUTURE_TIME_RE = re.compile(
    r"release date|launch window|preview|\bcoming (?:soon|to|in|this|next)|pre[- ]?registration|pre[- ]?order|soft launch date|"
    r"closed beta|network test|early access|"
    r"launch(?:es|ed|ing)?\s+(?:next|this|in\s+(?:20\d\d|q[1-4]|the|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)|"
    r"(?:on|for|in)\s+[^.;]{0,100}(?:next|this|month|20\d\d|q[1-4]|\d|"
    r"january|february|march|april|may|june|july|august|september|october|november|december))",
    re.I,
)
RADAR_PLATFORM_LAUNCH_RE = re.compile(
    r"launch(?:es|ed|ing)?\s+(?:on|for|to)\s+(?:steam|playstation|\bps5\b|\bps4\b|xbox|"
    r"nintendo|switch|app store|google play|ios|android|pc|mobile)",
    re.I,
)
RADAR_NOT_RELEASE_RE = re.compile(
    r"accessor(?:y|ies)|controller|headset|keyboard|mouse|monitor|chair|merch|figure|figurine|"
    r"steam machine|nitro rewards|game show|hardware|"
    r"weeks since .* released|months since .* released|years since .* released|since .* was released|"
    r"debate|discussion|opinion|lore|explained|is .* real|"
    r"\bdlc\b|expansion",
    re.I,
)
RADAR_ANNOUNCEMENT_RE = re.compile(
    r"announced?|reveal(?:ed|s)?|trailer|gameplay|showcase|new mode|new season|collaboration|"
    r"tournament|championship|qualifier|roadmap",
    re.I,
)
RADAR_ESPORTS_RE = re.compile(
    r"tournament|championship|qualifier|showdowns?|world championship|esports?|"
    r"schedule|standings|how to watch|teams|results?|grand final|playoffs?",
    re.I,
)
RADAR_PREORDER_RE = re.compile(r"pre[- ]?orders?", re.I)
RADAR_BUSINESS_STRATEGY_RE = re.compile(
    r"(?:sony|playstation|microsoft|xbox|nintendo|steam|valve).{0,100}"
    r"(?:physical games?|physical copies|digital sales|disc production|game pass|subscription|pricing|"
    r"platform policy|store policy|publishing policy|distribution|ownership)|"
    r"(?:physical games?|physical copies|disc production|digital sales).{0,100}"
    r"(?:sony|playstation|microsoft|xbox|nintendo|steam|valve)|"
    r"(?:ps6|steam machine|ram crisis).{0,100}(?:sony|playstation|valve|steam)|"
    r"(?:sony|playstation|valve|steam).{0,100}(?:ps6|steam machine|ram crisis)|"
    r"(?:playstation|xbox|nintendo|sony|microsoft).{0,100}(?:exclusive games?|"
    r"single-player games?.{0,30}(?:pc|console)|not coming to (?:pc|ps4|xbox)|"
    r"physical|digital|game pass)",
    re.I,
)
RADAR_NON_GAME_MOVIE_RE = re.compile(
    r"live[- ]action|\bmovie\b|\bfilm\b|\banime\b|\bseries\b|screenings?|theat(?:er|re)",
    re.I,
)
RADAR_CARD_GAME_RE = re.compile(
    r"\b(?:trading )?card game\b|\btcgs?\b|\btcg\b|"
    r"(?:pokemon|pokémon|naruto|one piece).{0,60}(?:card|trading card|booster|pack|set|การ์ด)",
    re.I,
)
RADAR_CONSUMER_NOISE_RE = re.compile(
    r"\b\d+\s+games?\s+for\s+\$|bundle|curator sale|trophy list|trophy leak|"
    r"leak(?:ed)?\s+(?:before|ahead of)\s+(?:the )?(?:game )?launch|"
    r"deal[s]?|discount|prime day|buying guide|best value|apology game|content moderation|"
    r"selling .*steam machine|impulse .*steam machine|incubator|grant|program|summit|conference|event|festival|"
    r"scammers?|without seeing any gameplay|fans? .*pre[- ]?order|\bbonus\b|new game digest",
    re.I,
)
RADAR_EDITORIAL_RE = re.compile(
    r"\binterview\b|retrospective|looking back|in retrospect|lessons? have developers? learned|"
    r"artist|\bimpressions?\b|\breview(?:s)?\b|showrunner|trophy|\bD&D\b|"
    r"fan[s’']? (?:think|theorize|react)|studio is a manor|show hn|"
    r"\d+ years after launch|out of the box|it's time to|get disgustingly|"
    r"gamers should continue fighting|please stop announcing|potential release date|"
    r"fans? discover|gamers react|dead in the water|how the developer|secrets of|"
    r"company-wide redundancy",
    re.I,
)
RADAR_NON_GAME_BETA_RE = re.compile(r"\bandroid\s+\d|\bios\s+\d|watchos\s+\d|q[1-4]\s+beta", re.I)
RADAR_EVENT_NOISE_RE = re.compile(
    r"games? done quick|schedule out now|event schedule|how to watch|standings|tournament schedule",
    re.I,
)
RADAR_ROUTINE_UPDATE_RE = re.compile(
    r"patch|patch notes?|map update|content update|huge map update|update added|new map|new character",
    re.I,
)
RADAR_GAME_CONTEXT_RE = re.compile(
    r"video game|mobile game|pc game|console game|game|gaming|rpg|jrpg|gacha|mmorpg|"
    r"genshin|valorant|call of duty|pokemon|pokémon|zelda|mario|elden ring|stardew|"
    r"early access|pre-registration",
    re.I,
)
RADAR_CLEAR_INDUSTRY_RE = re.compile(
    r"earnings|revenue|\blayoffs?\b|acquisition|acquires?|merger|funding|investment|market report|sales data|"
    r"user spending|\bmau\b|\bdau\b|platform policy|store policy|physical games?|physical copies|"
    r"disc production|game pass|subscription|pricing|distribution|ownership|publisher strategy|"
    r"studio closure|cancell?ation|newzoo|top-grossing|pre-orders? generate|sales milestone|"
    r"game engine|engine release|\bunity\s+\d|unreal engine|becoming independent|independent from",
    re.I,
)
RADAR_PLATFORM_CATALOG_NOISE_RE = re.compile(
    r"unreleased .{0,50}(?:nintendo switch online|game pass)|"
    r"(?:nintendo switch online|game pass).{0,50}unreleased",
    re.I,
)

REGION_ORDER = ["CN", "TW", "KR", "TH", "PH", "VN", "SG", "MY", "ID", "GLOBAL", "OTHERS", "MISC"]
REGION_LABELS = {
    "CN": "China",
    "TW": "Taiwan",
    "KR": "Korea",
    "TH": "Thailand",
    "PH": "Philippines",
    "VN": "Vietnam",
    "SG": "Singapore",
    "MY": "Malaysia",
    "ID": "Indonesia",
    "GLOBAL": "Global",
    "OTHERS": "Others",
    "MISC": "Misc",
}


def repair_mojibake(text: str) -> str:
    """Best-effort repair for UTF-8 text decoded as Latin-1, e.g. PokÃ©mon."""
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if repaired else text


def normalize_filter_text(text: str) -> str:
    repaired = repair_mojibake(str(text or ""))
    for alias, canonical in ALIAS_NORMALIZATIONS.items():
        repaired = repaired.replace(alias, canonical)
    decomposed = unicodedata.normalize("NFKD", repaired)
    ascii_folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_folded).strip()


def title_filter_text(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "")
    title_en = str(record.get("title_en") or "")
    normalized = normalize_filter_text(f"{title} {title_en}")
    return f"{normalized} {title} {title_en}".strip()


def is_junk(record: dict[str, Any]) -> bool:
    source = str(record.get("source") or "")
    if any(marker in source for marker in JUNK_SOURCE_MARKERS):
        return True
    title = title_filter_text(record)
    blob = f"{title} {source}"
    has_market_news = bool(MARKET_NEWS_RE.search(title))
    has_title_game_signal = bool(
        TITLE_GAME_RE.search(title) or BROAD_GAME_RE.search(title) or VIDEO_GAME_SIGNAL_RE.search(title)
    )
    has_source_game_signal = bool(SOURCE_GAME_RE.search(source))
    has_market_game_signal = has_market_news and (has_title_game_signal or bool(GAME_BUSINESS_RE.search(title)))
    has_generic_finance = bool(FINANCE_ONLY_RE.search(title)) and not has_market_game_signal

    if MISC_PATTERN.search(title):
        return True
    if IDIOMATIC_GAME_RE.search(title) and not REAL_GAME_LIFECYCLE_RE.search(title):
        return True
    if FINANCE_ONLY_GAMESTOP_EBAY_RE.search(title):
        return True
    if GAMESTOP_FINANCE_RE.search(title):
        return True
    if "gamestop" in title.lower() and FINANCE_SOURCE_RE.search(source):
        return True
    if PATCH_UPDATE_NOTE_RE.search(title):
        return True
    if AI_DEV_TOOL_GAME_NOISE_RE.search(title):
        return True
    if POKOPIA_EVENT_DLC_NOISE_RE.search(title):
        return True
    if LOOSE_AI_TOOL_RE.search(title) and not (
        REAL_GAME_LIFECYCLE_RE.search(title)
        or HOT_BUSINESS_RE.search(title)
        or RADAR_STRONG_INDUSTRY_RE.search(title)
    ):
        return True
    if GENERIC_EVENT_DLC_RE.search(title) and not (
        re.search(r"launch(?:es|ed|ing)? on|coming to|standalone|shutdown|server closure", title, re.I)
    ):
        return True
    if CELEBRITY_LIFESTYLE_RE.search(title):
        return True
    if POST_RELEASE_DISCUSSION_RE.search(title) and not has_market_game_signal:
        return True
    if ACCESSORY_DLC_TIMING_RE.search(title):
        return True
    if REVIEW_RE.search(title) and not has_market_news:
        return True
    if UTILITY_GUIDE_RE.search(title) and not has_market_news:
        return True
    if ROUTINE_LIVEOPS_RE.search(title) and not has_market_news:
        return True
    if PERIPHERAL_RE.search(title) and not (has_market_news and PLATFORM_MARKET_RE.search(blob)):
        return True
    if re.search(r"card game", title, re.I) and not (VIDEO_GAME_SIGNAL_RE.search(title) or has_market_news):
        return True
    if (NON_GAME_IP_RE.search(title) or ANIME_IP_RE.search(title)) and not (
        VIDEO_GAME_SIGNAL_RE.search(title) or has_market_news
    ):
        return True
    if record.get("source_dedicated"):
        # Dedicated feeds still carry finance, reviews, and community fluff.
        return has_generic_finance
    if not (has_title_game_signal or (has_market_news and has_source_game_signal and not has_generic_finance)):
        return True  # only matched via source/handle text, e.g. a "...Gamer..." username
    return False


def classify_region(record: dict[str, Any]) -> str:
    override = record.get("region_override")
    title = str(record.get("title") or "")
    blob = f"{title} {record.get('source', '')}"

    if MISC_PATTERN.search(title):
        return "MISC"
    if override:
        return override
    for code, _label, pattern in SEA_COUNTRY_PATTERNS:
        if re.search(pattern, blob, re.I):
            return code
    if TW_PATTERN.search(blob):
        return "TW"
    if CN_PATTERN.search(blob) or CJK_PATTERN.search(blob):
        return "CN"
    return "OTHERS"


def classify_content_type(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "")
    for content_type, pattern in CONTENT_TYPE_PATTERNS:
        if re.search(pattern, title, re.I):
            return content_type
    return "general"


def classify_radar_section(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "")
    title_en = str(record.get("title_en") or "")
    source = str(record.get("source") or record.get("site_name") or "")
    blob = f"{title} {title_en}"

    has_industry = bool(RADAR_INDUSTRY_RE.search(blob))
    has_strong_industry = bool(RADAR_STRONG_INDUSTRY_RE.search(blob))
    has_accessory_noise = bool(HOT_ACCESSORY_RE.search(blob))
    has_standalone_platform_dlc = bool(re.search(r"\bdlc\b|expansion", blob, re.I)) and bool(
        re.search(r"standalone", blob, re.I)
    ) and bool(re.search(r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch|app store|google play|pc", blob, re.I))
    not_release = (
        bool(RADAR_NOT_RELEASE_RE.search(blob))
        and not has_strong_industry
        and not (has_standalone_platform_dlc and not has_accessory_noise)
    )
    has_release = bool(RADAR_RELEASE_RE.search(blob)) and not not_release
    has_released = bool(RADAR_RELEASED_RE.search(blob))
    has_future_release = bool(RADAR_FUTURE_TIME_RE.search(blob))
    has_game_context = bool(RADAR_GAME_CONTEXT_RE.search(blob)) or bool(record.get("source_dedicated"))
    has_announcement = bool(RADAR_ANNOUNCEMENT_RE.search(blob))
    is_weak = bool(RADAR_WEAK_RE.search(blob))
    is_speculative = bool(RADAR_SPECULATION_RE.search(blob))
    has_esports = bool(RADAR_ESPORTS_RE.search(blob))
    engine_is_subject = bool(re.match(r"\s*(?:unity|unreal engine|epic)\b", blob, re.I))

    if is_speculative and not has_strong_industry:
        return "other"
    if is_weak and not has_industry and not has_strong_industry and not has_release:
        return "other"
    if PATCH_UPDATE_NOTE_RE.search(blob):
        return "other"
    if HOT_CLOSED_TEST_RE.search(blob) and (
        HOT_CLOSED_TEST_NO_DATE_RE.search(blob)
        or not re.search(
        r"full release|release date|launch(?:es|ed|ing)?|coming to|early access", blob, re.I
        )
    ):
        return "other"
    # Schedules, results, standings, teams, and viewing guides are not release
    # discovery even when they contain words such as "launch" or "out now".
    if has_esports and not (RADAR_CLEAR_INDUSTRY_RE.search(blob) or RADAR_BUSINESS_STRATEGY_RE.search(blob)):
        return "other"
    if RADAR_NON_GAME_MOVIE_RE.search(blob) and not re.search(
        r"video game|mobile game|pc game|console game|game launches?|game release|rpg|gacha",
        blob,
        re.I,
    ):
        return "other"
    if RADAR_CARD_GAME_RE.search(blob) or RADAR_CONSUMER_NOISE_RE.search(blob):
        return "other"
    if RADAR_PLATFORM_CATALOG_NOISE_RE.search(blob) and not re.search(
        r"sea|southeast asia|singapore|pc|mobile|ios|android", blob, re.I
    ):
        return "other"
    if (
        has_future_release
        and re.search(r"\b(?:switch(?: 2)?|ps5|ps4|playstation|xbox|nintendo)\b", blob, re.I)
        and not re.search(r"sea|southeast asia|singapore|pc|steam|mobile|ios|android", blob, re.I)
        and not HOT_MAJOR_IP_RE.search(blob)
    ):
        return "other"
    if RADAR_NON_GAME_BETA_RE.search(blob):
        return "other"
    if RADAR_EVENT_NOISE_RE.search(blob):
        return "other"
    if HOT_HARDWARE_PRODUCT_RE.search(blob):
        return "other"
    if RADAR_ROUTINE_UPDATE_RE.search(blob):
        return "other"
    if RADAR_EDITORIAL_RE.search(blob) and not RADAR_CLEAR_INDUSTRY_RE.search(blob) and not (
        re.search(r"gamesindustry\.biz|gameindustry|pocketgamer\.biz", source, re.I)
        and re.search(r"development|developer|publisher|studio|production|outsourc", blob, re.I)
    ):
        return "other"
    # Pre-orders describe an upcoming game. Do not let price/sales language
    # promote them into Industry Reports.
    if RADAR_BUSINESS_STRATEGY_RE.search(blob):
        return "industry_reports"
    if re.search(r"gamesindustry\.biz|gameindustry", source, re.I) and re.search(
        r"development|developer|publisher|studio|production|outsourc", blob, re.I
    ):
        return "industry_reports"
    # Engine/graphics mentions describe a game when the title has a concrete
    # lifecycle signal. Treat Unity/Unreal as industry subjects only when the
    # engine company or product is the headline subject.
    if RADAR_CLEAR_INDUSTRY_RE.search(blob) and not (
        re.search(r"engine|graphics|technology", blob, re.I)
        and has_future_release
        and has_game_context
        and not engine_is_subject
    ):
        return "industry_reports"
    if RADAR_PREORDER_RE.search(blob) and not has_accessory_noise and has_game_context:
        return "game_announcements"
    if (RADAR_CURRENT_RELEASE_RE.search(blob) or RADAR_STANDALONE_RELEASE_RE.search(blob)) and not has_accessory_noise and has_game_context:
        return "game_releases"
    if has_future_release and not has_accessory_noise and has_game_context:
        return "game_announcements"
    if has_released and not has_future_release and not has_accessory_noise and has_game_context:
        return "game_releases"
    if RADAR_PLATFORM_LAUNCH_RE.search(blob) and not has_future_release and not has_accessory_noise and has_game_context:
        return "game_releases"
    if has_esports:
        return "other"
    return "other"


def event_time_str(record: dict[str, Any]) -> str:
    return str(record.get("published_at") or record.get("last_seen_at") or record.get("first_seen_at") or "")


def normalize_title_for_dedup(title: str) -> str:
    return re.sub(r"[^\w一-鿿]+", "", title).lower()


def classify_and_tag(record: dict[str, Any]) -> dict[str, Any]:
    """Apply region + content_type tags to a copy of record. Does not dedupe/filter."""
    out = dict(record)
    region = classify_region(record)
    out["region"] = region
    out["region_label"] = REGION_LABELS[region]
    out["content_type"] = classify_content_type(record)
    out["radar_section"] = classify_radar_section(out)
    return out


def score_hot_news(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return deterministic hot-news score metadata, or None when not hot enough."""
    title = str(record.get("title") or "")
    title_en = str(record.get("title_en") or "")
    source = str(record.get("source") or record.get("site_name") or "")
    blob = f"{title} {title_en} {source}"
    title_blob = f"{title} {title_en}"

    if MISC_PATTERN.search(title_blob) or CELEBRITY_LIFESTYLE_RE.search(title_blob):
        return None
    if PATCH_UPDATE_NOTE_RE.search(title_blob):
        return None
    if HOT_HARDWARE_PRODUCT_RE.search(title_blob):
        return None
    if HOT_CARD_GAME_RE.search(title_blob) and not VIDEO_GAME_SIGNAL_RE.search(title_blob):
        return None
    if HOT_EDITORIAL_NOISE_RE.search(title_blob):
        return None
    if re.search(
        r"\brumou?r(?:ed|s)?\b|speculation|speculative|\bpotential\b|\bcould\b|\boverdue\b|"
        r"\bwishlist\b|\bpraying\b|\bhopes?\b|\bwants?\b",
        title_blob,
        re.I,
    ):
        return None
    if HOT_CLOSED_TEST_NO_DATE_RE.search(title_blob):
        return None
    section = str(record.get("radar_section") or classify_radar_section(record))
    if section == "other":
        return None
    has_accessory_noise = bool(HOT_ACCESSORY_RE.search(title_blob))
    has_standalone_platform_dlc = bool(HOT_DLC_MAJOR_RE.search(title_blob)) and bool(
        re.search(r"standalone", title_blob, re.I)
    ) and bool(re.search(r"steam|playstation|\bps5\b|\bps4\b|xbox|nintendo|switch|app store|google play|pc", title_blob, re.I))
    if RADAR_NOT_RELEASE_RE.search(title_blob) and (has_accessory_noise or not has_standalone_platform_dlc) and not (
        RADAR_STRONG_INDUSTRY_RE.search(title_blob) or HOT_BUSINESS_RE.search(title_blob)
    ):
        return None
    if HOT_CLOSED_TEST_RE.search(title_blob) and not re.search(
        r"full release|release date|launch(?:es|ed|ing)?|coming to|early access", title_blob, re.I
    ):
        return None
    if (
        HOT_CONSOLE_ONLY_RE.search(title_blob)
        and HOT_LIFECYCLE_RE.search(title_blob)
        and not re.search(r"sea|southeast asia|singapore|pc|steam|mobile|ios|android", title_blob, re.I)
        and not HOT_MAJOR_IP_RE.search(title_blob)
        and not RADAR_BUSINESS_STRATEGY_RE.search(title_blob)
    ):
        return None

    reasons: list[str] = []
    score = 0
    has_game_signal = bool(
        HOT_CORE_GAME_SIGNAL_RE.search(blob)
        or GAME_BUSINESS_RE.search(blob)
        or record.get("source_dedicated")
    )

    if HOT_LIFECYCLE_RE.search(title_blob):
        score += 45
        reasons.append("game_lifecycle")
    if HOT_BUSINESS_RE.search(title_blob) and (has_game_signal or GAME_BUSINESS_RE.search(blob)):
        score += 40
        reasons.append("business")
    if HOT_ESPORTS_RE.search(title_blob):
        if not re.search(r"rights|sponsor|revenue|viewership|publisher|platform|business", title_blob, re.I):
            return None
        score += 28
        reasons.append("esports")
    if HOT_PLATFORM_RE.search(title_blob) and has_game_signal:
        score += 24
        reasons.append("platform_store")
    if MARKET_NEWS_RE.search(title_blob):
        score += 12
        reasons.append("market_keyword")

    if record.get("content_type") in {"launch", "business", "platform", "esports"}:
        score += 8
    if record.get("region") not in {"MISC", "OTHERS", None}:
        score += 4
    if section == "industry_reports":
        score += 10
    elif section == "game_releases":
        score += 12
    elif section == "game_announcements":
        score += 5

    guide_or_review = bool(UTILITY_GUIDE_RE.search(title_blob) or REVIEW_RE.search(title_blob))
    routine_liveops = bool(ROUTINE_LIVEOPS_RE.search(title_blob))
    peripheral = bool(PERIPHERAL_RE.search(title_blob) or HOT_ACCESSORY_RE.search(title_blob))
    anime_without_game = bool((NON_GAME_IP_RE.search(title_blob) or ANIME_IP_RE.search(title_blob)) and not has_game_signal)
    dlc_without_major_signal = bool(HOT_DLC_MAJOR_RE.search(title_blob)) and not (
        HOT_BUSINESS_RE.search(title_blob) or HOT_PLATFORM_RE.search(title_blob)
    )

    if guide_or_review and not HOT_LIFECYCLE_RE.search(title_blob):
        score -= 60
        reasons.append("downrank_guide_or_review")
    if routine_liveops and not (HOT_LIFECYCLE_RE.search(title_blob) or HOT_BUSINESS_RE.search(title_blob)):
        score -= 45
        reasons.append("downrank_routine_liveops")
    if dlc_without_major_signal:
        score -= 35
        reasons.append("downrank_routine_dlc")
    if peripheral and not (HOT_PLATFORM_RE.search(title_blob) and HOT_LIFECYCLE_RE.search(title_blob)):
        score -= 50
        reasons.append("downrank_hardware")
    elif peripheral:
        score -= 45
        reasons.append("downrank_hardware")
    if DOWNLOAD_CODE_RE.search(title_blob):
        score -= 50
        reasons.append("downrank_download_code")
    if anime_without_game:
        score -= 50
        reasons.append("downrank_anime_no_game_signal")
    if not has_game_signal:
        score -= 40
        reasons.append("weak_game_signal")
    if section == "other" and not (
        HOT_BUSINESS_RE.search(title_blob) or RADAR_STRONG_INDUSTRY_RE.search(title_blob) or RADAR_RELEASE_RE.search(title_blob)
    ):
        reasons.append("downrank_other_section")
        return None

    if score < 35 or not any(
        reason in reasons for reason in ("game_lifecycle", "business", "esports", "platform_store")
    ):
        return None
    return {"hot_score": score, "hot_reasons": reasons}


def dedupe_by_title(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop same-title duplicates, keeping the first occurrence (call after sorting by recency)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    dropped = 0
    for item in items:
        key = normalize_title_for_dedup(str(item.get("title") or ""))
        if key and key in seen:
            dropped += 1
            continue
        if key:
            seen.add(key)
        out.append(item)
    return out, dropped
