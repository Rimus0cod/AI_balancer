# AI Balancer Project Status

Last updated: 2026-08-21

## Working Rule

After every major or meaningful step, update this file with:

- what changed;
- which phase it belongs to;
- current project state;
- what is done;
- what needs work;
- next steps.

## Current Goal

Build a ranked-only Dota 2 balance analytics platform that can answer questions like:

- which heroes are statistically unusual by rank;
- which hero-item combinations perform above or below baseline;
- whether item timing correlates with winrate;
- how signals differ between rank brackets.

The near-term target is not deep ML yet. The current target is a reliable analytical foundation with clean ranked data and interpretable item timing reports.

## Current Data State

- Raw OpenDota payloads are preserved in `data/raw/`.
- Ranked processed data is stored under `data/processed/ranked/<rank-bucket>/`.
- Latest analyzer run saw `89,149` processed ranked matches.
- Earlier dataset quality check confirmed ranked-only filters were working:
  - `game_mode = 22`;
  - `lobby_type = 7`;
  - `duration >= 1200` seconds;
  - patch `60` in the current collected set.
- The collector tracks progress in `data/collector_state.json` and resumes safely.

## Phase Status

### Phase 1 - Data Platform

Status: mostly done, needs hardening.

Done:

- OpenDota match detail ingestion.
- Raw payload storage with provenance.
- Ranked-only filtering using OpenDota Explorer metadata.
- Resumable ranked collector by rank bucket.
- Daily request budget tracking.
- Processed match/player schemas.
- Purchase log extraction from `players[].purchase_log`.
- Rebuild script from raw to processed.
- Dataset summary script.

Needs work:

- More robust state reporting for exhausted buckets, especially Immortal.
- Better handling of transient OpenDota/CDN failures in long runs.
- Optional API-key validation and visible quota diagnostics.
- Constants caching should be treated as a formal data artifact.

### Phase 2 - Analytical Core

Status: started.

Done:

- Hero draft baseline model.
- Train/validation split.
- Rank bucket filtering.
- Basic item timing analyzer.
- Early/late/not-bought comparison for one hero-item pair.
- Confidence interval display for item timing groups.
- Filtering of trivial consumables and recipe components from reports.

Needs work:

- Current `hero x item x rank x timing` grouping is too sparse, even with ~89k matches.
- Add analysis modes with coarser grouping:
  - `hero-item`;
  - `hero-item-rank`;
  - `hero-item-timing`;
  - `item-rank-timing`.
- Add minimum sample warnings and automatic recommendations when a query is underpowered.
- Add CSV/JSON report output for later dashboard use.
- Add farm/control variables before interpreting item timing as an effect.

### Phase 3 - Representation Learning

Status: not started.

Planned:

- Convert match timelines into event sequences.
- Train sequence encoders only after analytical features are reliable.

### Phase 4 - Graph Model

Status: not started.

Planned:

- Build hero-item-rank-patch interaction graph after item timing reports are stable.

### Phase 5 - Balance Intelligence

Status: not started.

Planned:

- Combine statistical reports, model predictions, and explanation layer.

## Current Findings

- Draft-only baseline on ranked data is weak but expected:
  - validation accuracy around `0.540` from previous run;
  - Radiant baseline was around `0.533`, so draft-only model is only slightly above side prior.
- Item timing analysis is possible because OpenDota raw payloads contain `purchase_log`.
- Fine-grained slicing is too sparse:
  - `hero x item x rank x timing` produced almost no cells with `min-games >= 50`.
- Point queries show the real issue clearly:
  - Lina + Maelstrom has very small bought samples compared with a very large not-bought baseline.
  - Interpretation needs sample-size checks and confidence intervals.
- Current item report findings (after early-GPM rebuild):
  - `hero-item` grouping can produce candidate signals on ~89k matches.
  - `hero-item-rank` for a single hero is still usually thin and should not be interpreted as a stable rank-specific effect.
  - Rubick Blink Dagger: `egpm10=234.9 vs ebase=235.1` (bias low) with `+10.1pp` delta — cleanest current candidate; buyers were indistinguishable from baseline before purchase.
  - Pudge Blink Dagger: `276.1 vs 268.1` (bias low), `+8.3pp` — also relatively clean.
  - Lina Yasha / Yasha and Kaya / Aghanim's Scepter: early GPM uplift ~+20 (`408 vs 387`, bias medium). Pre-purchase advantage explains part of the delta, but the size of the uplift suggests genuine synergy may also contribute. Needs deeper control before claiming causality.
  - Final GPM was confirmed misleading as a bias indicator: farm-accelerating items raise buyers' final GPM as an outcome, not a cause.
  - Rubick Blink timing split (threshold minute 20): bought_early WR 71.9% (n=32, CI +-15.6pp), bought_late 54.7%, not_bought 49.7%. Early buyers had mildly higher pre-purchase GPM (260 vs 236); late buyers had lower-than-baseline GPM yet still won more, weakly supporting a real item effect beyond winning-state bias. Sample remains small.
  - Data sanity check passed: Anti-Mage shows zero Blink purchases because Blink is his innate ability.
  - Pudge Blink timing split (threshold minute 20): bought_early WR 62.5% (n=112) but early buyers had +23% pre-purchase GPM (289.5 vs 235.2); bought_late only +1.8pp. The aggregate "clean" signal is therefore dominated by winning-state bias once segmented by timing. Methodological lesson: farm bias must be checked per timing segment, not only in aggregate.
  - Rank-specific item cells (hero-item-rank) remain universally thin on ~89k matches; immortal cells show intriguing rows (e.g. Rubick Arcane Boots +30.9pp with negative GPM bias) but all below significance thresholds.

## Next Engineering Steps

1. Add stronger underpowered-query guidance for `--compare` output.
2. Add a per-hero item recommendation report using `hero-item` and `hero-item-rank` groups.
3. Add stronger farm context later:
   - XPM and final net worth deltas in printed report;
   - then minute-level net worth when timeline data is available.

## Next Product Questions

- Which first report matters most?
  - per-hero item recommendations;
  - per-item rank impact;
  - early-vs-late timing thresholds;
  - patch-level change detection.
- Should Immortal be collected via a different method/source if OpenDota public data is sparse?
- Should we prioritize STRATZ for richer rank and timeline data?

## Change Log

### 2026-08-22 - Collection Speedup: Bulk Drafts + Parallel Details

Phase: Phase 1 - Data Platform.

Changed:

- Added `collect_bulk_drafts.py`: draft-model data (heroes + result + rank tier) via explorer JOIN of `public_matches` and `public_player_matches`. One request returns up to `rows-per-request/10` matches; output is JSONL per bucket in `data/bulk/drafts_<bucket>.jsonl`; resumable via the shared collector state (`bulk:<bucket>` keys with explicit counts).
- Added `fetch_draft_page()` to the OpenDota client.
- Added `load_bulk_matches()` to the training module; compact JSONL rows are converted to Match objects so the existing feature extraction/training pipeline works unchanged.
- `train_hero_model.py`: new `--bulk-dir` (merge bulk JSONL) and `--processed-only` flags.
- `collect_ranked.py`: added `--workers N --rpm X` parallel mode with a thread-safe RatePacer ceiling; sequential mode unchanged.
- Tests for rows grouping, validation drops, JSONL roundtrip, and feature extraction on bulk data.

Reason:

- One-request-per-match was the collection bottleneck. Draft modeling does not need purchase logs, so bulk SQL is ~1000x more data per request. Purchase-log details remain per-match but can now be fetched in parallel under an explicit rpm ceiling.

Expected throughput:

- Bulk drafts: millions of matches/day within a 30k request budget (50k rows ≈ 5k matches per request).
- Detail collector in parallel mode: bounded by chosen rpm instead of fixed delay.

Next:

- Collect 100k+ bulk drafts per bucket and retrain the draft model at scale.
- Validate that bulk-trained model metrics match processed-data expectations.

### 2026-08-22 - Per-Hero Item Recommendation Report

Phase: Phase 2 - Analytical Core.

Changed:

- Added `generate_item_report.py`: aggregates hero-item rows for all heroes, applies min-games and signal/unclear filters, and writes:
  - `reports/item_recommendations.csv` (full enriched data);
  - `reports/item_recommendations.md` (readable per-hero sections with delta, CI context, pre-purchase GPM, bias, status).
- Heroes are ordered by their best available delta; items within a hero likewise.
- Added tests for hero grouping/order and Markdown rendering.

Reason:

- Item timing analysis produced its first screened candidates; they need a consumable artifact rather than console-only output.

Next:

- Fill the report with more data (collection continues).
- Consider adding ability-build analytics as the next domain.

### 2026-08-22 - Timing-Segmented Bias Finding

Phase: Phase 2 - Analytical Core.

Changed:

- Documented Pudge Blink case: aggregate low-bias signal decomposes into a high-bias early segment (+23% pre-purchase GPM among buyers before minute 20).
- Established analysis rule: check farm bias per timing segment; aggregate bias can mask segment-level confounding.

Reason:

- Aggregate bias screening alone can produce false-clean signals (Simpson-style reversal).

Next:

- Add per-segment bias display to `--compare` output (bias label next to bought_early/bought_late rows).
- Decide next domain: recommendation report, ability builds, or more data collection.

### 2026-08-22 - Early-GPM Findings and Bias Filter

Phase: Phase 2 - Analytical Core.

Changed:

- Rebuilt processed data with `early_gpm`; signal reports now carry pre-purchase farm context.
- Added `--bias low|medium|high|negative|unknown|all` filter to `analyze_item_timings.py`.
- Updated Current Findings with data-driven verdicts:
  - Rubick/Pudge Blink = clean candidates (bias low);
  - Lina Yasha/Aghanim = medium bias; partial confounding, plausible synergy, unresolved.
- README updated.

Reason:

- The final-GPM dispute was resolved by early GPM: buyers' pre-purchase state is measurable, so bias can be screened instead of guessed.

Next:

- Produce a "clean candidates" report (`--status signal --bias low`) across all heroes.
- Consider XPM-based second control and minute-level net worth later.

### 2026-08-22 - Pre-Purchase Farm Context (early GPM)

Phase: Phase 2 - Analytical Core.

Changed:

- Added `Player.early_gpm` to processed schema: gold earned per minute by minute 10, derived from raw `gold_t[10]`.
- Item reports now show `egpm10` / `ebase` (pre-purchase farm) instead of final GPM for bias checks.
- `farm_bias` classification now uses early GPM.
- Final GPM and final net worth remain in CSV/JSON exports as secondary context.
- Updated tests: fixture includes `gold_t`; new test verifies early GPM extraction and aggregation.

Reason:

- User correctly pointed out that final GPM is an outcome of farm-accelerating items, not just a confounder. Items like Yasha or Maelstrom legitimately raise buyers' final GPM, so it cannot separate "item made the hero rich" from "rich hero bought the item". GPM by minute 10 measures the state before most core item purchases.

Interpretation rule going forward:

- High early-GPM uplift among buyers = likely winning-state bias; treat the winrate delta skeptically.
- Early GPM near baseline + large winrate delta = cleaner candidate signal worth deeper study.
- Neither proves causality; both are screening heuristics.

Next:

- Rebuild processed data (`python rebuild_processed.py`) so existing matches gain `early_gpm`.
- Re-run signal reports with the new context.
- Later add XPM-based control and minute-level net worth.

### 2026-08-21 - Farm Bias Classification

Phase: Phase 2 - Analytical Core.

Changed:

- Added `farm_bias` classification to item reports:
  - `low`;
  - `medium`;
  - `high`;
  - `negative`;
  - `unknown`.
- Printed `bias` in console reports.
- Added `farm_bias` to CSV/JSON exports.
- Updated tests and README.

Reason:

- Strong item winrate deltas can be caused by players already farming well enough to buy expensive items, not by the item itself.

Next:

- Use farm bias to prioritize cleaner signals and later replace final GPM with minute-level net worth controls.

### 2026-08-21 - Farm Context in Item Reports

Phase: Phase 2 - Analytical Core.

Changed:

- Added average GPM and average final net worth to item timing aggregates.
- Added baseline average GPM and baseline final net worth for hero/rank baseline.
- Added GPM and final net worth to early/late/not-bought compare output.
- Added farm-context fields to CSV/JSON exports.

Reason:

- Item winrate deltas are heavily confounded by whether a hero was already farming/winning well enough to buy the item.

Next:

- Use GPM/net-worth deltas to flag likely winning-state bias.
- Later replace final net worth with minute-level net worth from timelines/replays.

### 2026-08-21 - Item Timing Status and Export

Phase: Phase 2 - Analytical Core.

Changed:

- Added signal classification to item timing rows:
  - `signal`;
  - `unclear`;
  - `thin`.
- Added confidence-aware sorting.
- Added `--output` and `--format csv|json` report export.
- Added status counts and a warning when no statistically separated signal is found.
- Updated tests and README examples.

Reason:

- Raw winrate deltas alone were too easy to overinterpret, especially with small sample sizes.

Next:

- Add farm context and clearer underpowered warnings in exact early/late/not-bought comparisons.

### 2026-08-21 - Item Noise Filter and Status Filtering

Phase: Phase 2 - Analytical Core.

Changed:

- Expanded item noise filtering to remove additional low-level components and early-game utility items:
  - `quelling_blade`;
  - `gauntlets`;
  - `ring_of_protection`;
  - `blades_of_attack`;
  - `gloves`;
  - `wind_lace`;
  - `splintmail`;
  - other small components.
- Added `--status signal|unclear|thin|all` to `analyze_item_timings.py`.
- Updated README examples.

Reason:

- General reports still contained component-level noise that looked like balance insight but was mostly build-path artifact.

Next:

- Run signal-only reports and then add farm context to reduce winning-state bias.

### 2026-08-21 - Item Timing Analyzer Grouping Modes

Phase: Phase 2 - Analytical Core.

Changed:

- Added `--group` to `analyze_item_timings.py`.
- Supported grouping levels:
  - `hero-item`;
  - `hero-item-rank`;
  - `hero-item-timing`;
  - `hero-item-rank-timing`.
- Changed default discovery grouping to `hero-item` to avoid sparse `hero x item x rank x timing` cells.
- Kept exact early/late/not-bought comparisons behind `--compare`.
- Updated tests and README examples.

Reason:

- With ~89k processed matches, deep four-dimensional item timing cells were too sparse to produce stable reports.

Next:

- Add underpowered-query warnings and CSV/JSON export.

### 2026-08-21 - Project Status File Added

Phase: project management / all phases.

Changed:

- Added this living status file.
- Established rule that major steps must update project goals, phase status, completed work, known gaps, and next steps.

Reason:

- The project has moved from scaffolding into a multi-phase data/analytics workflow and needs a persistent source of truth.

Next:

- Update item timing analyzer grouping modes and record the change here.
