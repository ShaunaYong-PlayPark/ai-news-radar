# Trend Review Training Set

This folder contains a static review sample generated from `data/game-news.json`.

## How to Review

1. Open `review_trends.html` in a browser.
2. Label articles as `Include`, `Watch`, or `Exclude`.
3. Click `Export`.
4. Save the downloaded `trend_review_labels.json`.
5. Send `trend_review_labels.json` back to Codex/Alan for analysis.

If the browser blocks local JSON loading, click `Load JSON` in the toolbar and choose:

```text
data/training/trend_review_training_round2.json
```

No server, paid API, auth, or secrets are required.

## Label Intent

- `Include`: use in the final IBD report now.
- `Watch`: useful signal, future release, or regional item to monitor later, but not final report material now.
- `Exclude`: not useful for the final IBD scan.

Final report lanes:

- `Game Announcements` means `Future Game Releases` only.
- `Industry Trends` is a separate final report section.

Use `Future Game Releases` for concrete future release discovery: launch dates/windows, early access launches, platform launches/ports, remake/remaster/relaunch releases, shutdown/delist notices, or major preorder/wishlist milestones for known upcoming games.

Use `Industry Trends` for structural signals: platform policy, distribution model, monetization, publisher strategy, layoffs/cancellations with business consequence, market data with clear demand signal, and SEA ecosystem relevance.

Use reason chips to explain why a label was chosen. Notes are optional.
