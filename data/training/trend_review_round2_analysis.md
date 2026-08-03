# Trend Review Round 2 Analysis

Source: `data/training/trend_review_labels_shauna_round2.json`
Training sample: `data/training/trend_review_training_round2.json`

## Label Summary

Shauna labelled 180 records:

- Include: 8
- Watch: 9
- Exclude: 163

This is a strict assisted-review set. Only 17 of 180 records were useful enough
to include or watch.

## System Bucket Comparison

| Suggested bucket | Include | Watch | Exclude | Acceptance |
| --- | ---: | ---: | ---: | ---: |
| `include_candidate` | 0 | 3 | 5 | 37.5% |
| `watch_candidate` | 5 | 6 | 91 | 10.8% |
| `exclude_candidate` | 3 | 0 | 67 | 4.3% |

The system produced 96 false positives: 96 records suggested as include/watch
that Shauna excluded. There were 3 false negatives: records suggested as
exclude that Shauna included.

False positives were concentrated in:

- Generic future-release headlines: Switch, PlayStation, Xbox, remake, port,
  trailer, and release-date stories without SEA/SG, PC/mobile, major-IP, or
  industry value.
- Consumer and retail material: price hikes, Prime Day deals, hardware sales,
  Steam Deck coverage, and buying advice.
- Non-report material: esports personalities, fan discourse, profiles, movie
  and event stories, guides, and speculative rumors.
- Broad market lists: top-grossing/download rankings without a specific demand
  or business implication.

Representative false positives include generic Switch launches, Gears of War
platform availability, Ocarina of Time fan speculation, Steam Deck price
coverage, Xbox buying advice, esports-player profiles, and film/event stories.

False negatives:

1. `Unity 7 to launch in Q1 2027`: an engine/platform ecosystem signal.
2. `181K mobile games launched in six months`: aggregate market-demand/supply
   data, not a single game release.
3. `Pokémon Champions launches on iOS and Android`: a concrete mobile game
   release.

## Common Exclude Reasons

| Reason | Count |
| --- | ---: |
| `too_consumer` | 94 |
| `not_sg_relevant` | 77 |
| `non_game_launch` | 66 |
| `wrong_category` | 65 |
| `hardware_retail` | 20 |
| `not_sea_relevant` | 16 |
| `esports_not_report` | 14 |
| `not_future_release` | 13 |
| `too_speculative` | 8 |
| `ordinary_financials` | 7 |
| `low_market_relevance` | 6 |

The reason chips are multi-select, so counts exceed the 163 excluded records.

## Rules That Must Change

1. Game Announcements must mean future game releases only. Generic trailers,
   showcases, esports schedules/results/standings/teams/how-to-watch, and
   already-released games do not qualify.
2. Pre-orders are future-release signals and must not be promoted to Industry
   Reports merely because a title contains prices, sales, or platform names.
3. Closed network tests without a full release date are watch-level signals;
   they must not earn a high hot-release score.
4. Switch-only, PlayStation-only, Xbox-only, and Nintendo-only releases should
   be excluded or downranked unless they have SEA/SG relevance, Steam/PC or
   mobile relevance, major-IP significance, or a separate industry signal.
5. Hardware, keyboards, accessories, peripherals, and retail deals are not
   Game Releases.
6. PlayStation, Xbox, Nintendo, and similar platform distribution, ownership,
   pricing, subscription, and physical/digital strategy stories belong in
   Industry Reports, separately from Game Announcements and Game Releases.
7. Aggregate market data and engine/platform releases should be eligible for
   Industry Trends when they describe a structural gaming-market signal.

These changes remain deterministic and assisted-review only. They do not
auto-publish trend reports.
