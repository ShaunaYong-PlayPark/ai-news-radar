# Trend Review Round 1 Analysis

Generated from:

- `data/training/trend_review_labels_shauna_round1.json`
- `data/training/trend_review_training.json`

Scope: analyze Shauna's labels and recommend practical rule changes. No model is built in this round.

## Summary

Shauna labeled all 200 review records.

| Label | Count | Share |
| --- | ---: | ---: |
| Exclude | 171 | 85.5% |
| Watch | 20 | 10.0% |
| Include | 9 | 4.5% |

Reason chip counts:

| Reason | Count |
| --- | ---: |
| junk | 171 |
| market_signal | 26 |
| too_consumer | 10 |
| wrong_category | 7 |
| repeated_story | 6 |
| sea_relevance | 4 |
| too_speculative | 2 |
| platform_policy | 2 |
| credible_source | 1 |
| publisher_strategy | 1 |

Important interpretation: `exclude + junk` is overloaded. It includes true junk, wrong product category, consumer-only items, irrelevant geography, ordinary earnings, esports results, and stories the current chips could not describe well enough.

## System Comparison

| System bucket | Shauna exclude | Shauna watch | Shauna include | Accepted rate |
| --- | ---: | ---: | ---: | ---: |
| include_candidate | 59 | 14 | 7 | 26.3% |
| watch_candidate | 65 | 3 | 2 | 7.1% |
| exclude_candidate | 47 | 3 | 0 | 6.0% |

By score band:

| System score | Exclude | Watch | Include | Accepted rate |
| --- | ---: | ---: | ---: | ---: |
| 150+ | 22 | 7 | 3 | 31.3% |
| 100-149 | 37 | 7 | 4 | 22.9% |
| 50-99 | 65 | 3 | 2 | 7.1% |
| <0 | 47 | 3 | 0 | 6.0% |

The current score is too optimistic. High score mostly means "has business/release/platform keywords from a decent source"; Shauna is applying a stricter trend standard.

## False Positives

Definition: system suggested `include_candidate` or `watch_candidate`, Shauna labeled `exclude`.

Total false positives: 124.

Common patterns:

- Ordinary earnings/revenue reports without strategic consequence.
- Grants, funds, and studio ecosystem stories outside SEA or core tracked markets.
- Esports schedules/results and how-to-watch posts.
- Consumer commentary, fan reaction, logo/history/profile pieces, and reviews.
- Hardware/retail availability without distribution-policy impact.
- Game Announcements that are not future release discovery.

Representative examples:

- `Ex-PlayStation Boss Reveals Reason Behind Japan Studio's Shutdown`
- `Supercell launches equity-free grants program for Africa-based game studios`
- `Overwatch Midseason Championship at Esports World Cup 2026: Schedule, results, standings, teams, how to watch`
- `Nintendo's Shigeru Miyamoto thinks it's "rude"...`
- `Roblox (RBLX) Q2 2026 earnings results miss revenue on smaller than expected EPS losses`
- `PGDX 2026 Launches Official Steam Curator Sale`

## False Negatives

Definition: system suggested `exclude_candidate`, Shauna labeled `include` or `watch`.

Total false negatives: 3.

| Shauna label | System score | Title | Reason |
| --- | ---: | --- | --- |
| watch | -20 | `1047 Games' spiritual successor to Titanfall will reportedly be called Empulse` | market_signal |
| watch | -20 | `Resident Evil Veronica hits a million wishlists on PS5 and PC...` | market_signal |
| watch | -30 | `Free Fire Daybreak Is The Anime Adaptation Of The Namesake Mobile Game...` | market_signal |

These are not strong includes, but they reveal that Shauna may still want watch-level coverage for market demand signals, franchise signal, and IP expansion when the story is tied to a real game or mobile game.

## Missing Reason Chips

Add these chips before the next review round:

- `not_future_release`: for announcements, esports, or commentary that are not future release discovery.
- `esports_result`: for match results, standings, schedules, and how-to-watch posts.
- `regional_ecosystem`: for local developer programs, events, incubators, grants, and SEA ecosystem stories.
- `ordinary_financials`: for earnings/revenue/stock stories without strategic implication.
- `hardware_retail`: for device/accessory/retail price stories.
- `ip_expansion`: for anime, film, merchandise, and transmedia extensions tied to a game IP.
- `developer_profile`: for interviews, studio retrospectives, creator profiles, and behind-the-scenes pieces.
- `low_market_relevance`: for credible but geographically or commercially irrelevant industry stories.

Keep `junk`, but do not rely on it as the only exclusion reason.

## Recommended Rule Changes

### Future Game Releases

In the final report, treat Game Announcements as Future Game Releases only. This should be separate from Industry Trends.

Promote to Future Game Releases when the title has a concrete future release signal:

- new game launch date/window
- early access launch
- platform launch or port launch
- remake/remaster release
- relaunch
- shutdown/delist notice
- substantial wishlist/preorder milestone for a known upcoming game

Downrank or exclude from Future Game Releases:

- esports schedules, standings, results, teams, and how-to-watch posts
- game events, festivals, sales, curator sales, and local expo program announcements
- content updates, patches, seasons, cosmetics, DLC without standalone paid release
- fan reaction, review, guide, profile, logo/history, and commentary pieces
- "launches" where the subject is a fund, grant, sale, server, event, or program rather than a game/product release

Practical implementation:

- Rename the final-facing `game_announcements` concept to future release discovery in downstream trend logic.
- Add a negative subject filter around launch verbs: `fund`, `grant`, `sale`, `curator`, `server`, `event`, `program`, `festival`, `tournament`.
- Keep `Game Releases` when release terms attach to a game title or platform target, not to a business program.
- Keep watch-level demand signals such as major wishlist/preorder milestones, but do not auto-include them.

### Industry Trends

Industry Trends should be a separate lane from Future Game Releases.

Promote to Industry Trends when the story indicates structural or market movement:

- platform policy or distribution model changes
- ownership/physical-vs-digital distribution changes
- console/app-store pricing changes with market impact
- publisher strategy, cancellations, portfolio changes, or layoffs with clear business consequence
- market data with clear demand signal, such as GTA 6 preorder estimates or major wishlist milestones
- SEA ecosystem relevance, especially PH/SEA developer programs or launch infrastructure

Downrank or exclude from Industry Trends:

- routine quarterly earnings unless they include strategic context
- stock-only stories, EPS misses, share price, investor framing
- grants/funds/incubators outside target regions unless they affect major publishers or platforms
- esports results and schedules
- consumer hardware retail listings without policy/distribution impact
- generic studio profiles, creator quotes, anniversary/logo stories, and fan discourse

Practical implementation:

- Split `industry_reports` scoring into at least two branches:
  - `industry_trend`: platform policy, distribution, monetization, publisher strategy, market signal, SEA ecosystem.
  - `industry_noise`: ordinary financials, stock-only, grants outside scope, profiles, esports, hardware retail.
- Require at least one high-intent trend term for auto-include; source quality alone should not lift an item.
- Treat `market_signal` as watch by default unless repeated by multiple sources or tied to a major platform/publisher.

## Next Changes To Make

1. Add the missing reason chips to `assets/review_trends.js`.
2. Add rule-level negative filters for esports results/schedules and non-game launch subjects.
3. Split trend scoring into Future Game Releases and Industry Trends instead of letting `industry_reports` dominate.
4. Lower weight from source tier and raw business keywords.
5. Add explicit watch rules for preorder/wishlist/franchise demand signals.
6. Run a second 200-item review after these rules change.
