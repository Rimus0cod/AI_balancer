# AI Balancer

AI Balancer is a long-term ML research project for understanding Dota 2 balance and supporting patch-design decisions. The goal is not to replace game designers, but to build a decision-support system that detects meta shifts, explains balance signals, and estimates the downstream effects of potential changes.

## Vision

Create a platform that learns how Dota 2 matches evolve across patches, ranks, drafts, item builds, facets, objectives, and timelines. The system should eventually answer counterfactual balance questions such as:

- What happens if Axe loses 1 base armor?
- Which heroes lose the most win rate if BKB costs 200 more gold?
- Which changes maximize meta diversity while minimizing overall balance disruption?

## Architecture

```text
                     Data Sources
      ┌──────────────────────────────────────────┐
      │ OpenDota │ STRATZ │ Steam API │ Replay   │
      └──────────────────────────────────────────┘
                          │
                          ▼
                Data Collection Layer
                          │
                          ▼
                 Data Warehouse / Lake
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
 Feature Engineering              Match Timeline
          │                               │
          └───────────────┬───────────────┘
                          ▼
               Representation Learning
            (Transformer / GNN Encoder)
                          │
                Match-level embeddings
                          │
      ┌───────────────────┼───────────────────┐
      ▼                   ▼                   ▼
 Anomaly Model      Synergy Model      Meta Prediction
      │                   │                   │
      └───────────────┬───┴───────────────────┘
                      ▼
             Balance Intelligence Core
                      │
          ┌───────────┴────────────┐
          ▼                        ▼
    Dashboard                LLM Assistant
```

## Core Principles

- Store raw data first, then derive processed datasets and ML-ready features.
- Treat matches as timelines of game events, not only as final scoreboard rows.
- Learn reusable representations of matches, heroes, items, talents, facets, patches, and roles.
- Combine statistical analysis, representation learning, graph modeling, and explainable summaries.
- Use an LLM only as an interface and narrative layer; numeric conclusions must come from the analytics and ML core.

## Roadmap

See [`docs/roadmap.md`](docs/roadmap.md) for the phased research and engineering plan.

Current implementation status, phase notes, known gaps, and next steps are tracked in [`docs/project-status.md`](docs/project-status.md). Update that file after every major project step.

To begin Phase 1 implementation, use the dedicated [`Phase 1 system prompt`](docs/system-prompt-phase-1.md) for the first data-platform vertical slice.

## Current Phase 1 Slice

The repository currently contains a minimal OpenDota ingestion flow:

- fetch one or more matches from OpenDota;
- store the raw API payload with provenance metadata;
- transform raw match/player fields into typed Pydantic schemas;
- store validated processed match summaries separately from raw data.

Run it from the repository root:

```bash
python cli.py 1234567890
```

Rebuild processed datasets from preserved raw data after changing quality gates:

```bash
python rebuild_processed.py --clear --include-filtered
```

Collect ranked All Pick matches only:

```bash
python collect_recent.py --count 50 --lookback 500 --delay 1.5 --skip-existing
```

For long-running ranked collection by rank bracket, use the resumable collector:

```bash
python collect_ranked.py --target-per-bucket 10000 --buckets archon,legend,crusader,ancient,guardian,herald,divine,immortal --daily-budget 30000 --delay 1.0
```

Speed options for the detail collector (needed only for purchase-log data):

```bash
# Parallel fetchers with a shared requests-per-minute ceiling:
python collect_ranked.py --workers 6 --rpm 120 --buckets all --daily-budget 30000
```

For draft-model data you do NOT need match details at all. The bulk collector pulls thousands of matches per explorer request (~1000x cheaper):

```bash
python collect_bulk_drafts.py --target-per-bucket 200000 --rows-per-request 50000 --summary-only
python collect_bulk_drafts.py --target-per-bucket 200000 --rows-per-request 50000
```

Bulk drafts are stored as JSONL per bucket in `data/bulk/drafts_<bucket>.jsonl` and trained directly:

```bash
python train_hero_model.py --bulk-dir data/bulk --processed-only --epochs 10
```

The collector stores progress in `data/collector_state.json`, writes matches into `data/processed/ranked/<rank-bucket>/`, and resumes safely after rate limits, restarts, or machine shutdowns. To inspect current progress without making API calls:

```bash
python collect_ranked.py --summary-only
```

Recommended `.env` settings when using an OpenDota API key:

```bash
OPENDOTA_API_KEY=your_key_here
OPENDOTA_DAILY_REQUEST_BUDGET=30000
```

OpenDota listing metadata is used to filter before downloading match details. The current quality gates keep only `lobby_type=7`, `game_mode=22`, and `duration >= 1200` seconds in `data/processed/ranked/`. Raw API payloads are still preserved in `data/raw/`.

Processed player rows also include normalized `purchase_log` entries (`time`, `item_name`) so item timing analysis can be derived without parsing replays.

Local outputs are written to `data/raw/`, `data/processed/ranked/`, and optionally `data/processed/filtered/`. These directories are intended for local examples only and should not be used as a production data lake.

Train the first baseline model from locally processed matches:

```bash
python train_hero_model.py
```

Train a rank-bracket-specific model when enough data exists:

```bash
python train_hero_model.py --rank-bucket legend
python train_hero_model.py --min-rank-tier 70
```

The baseline model is a simple hero-draft logistic model. It uses Radiant heroes as positive draft features, Dire heroes as negative draft features, and predicts `radiant_win`. The ranked model artifact is written to `models/hero_draft_baseline_ranked.json` by default. Training reports both train and validation metrics, because train-only accuracy is not a reliable quality signal on small datasets.

Summarize the local dataset and inspect the trained model:

```bash
python summarize_dataset.py
python inspect_hero_model.py
```

Interpret early metrics cautiously. For example, validation accuracy around `0.75-0.80` on fewer than a few hundred matches is only a smoke-test signal that the pipeline is learning something; it is not yet a reliable balance model.

Analyze item timings from processed ranked data:

```bash
python rebuild_processed.py
python analyze_item_timings.py --group hero-item --top 30 --min-games 50
```

This reports hero/item/rank/timing buckets relative to that hero's winrate in the same rank bucket.

Point query for one hero and one item — early vs late vs not-bought with 95% confidence intervals:

```bash
python analyze_item_timings.py --hero-id 25 --item blink --minute 12 --rank legend --compare
python analyze_item_timings.py --hero-id 25 --item maelstrom --minute 18 --compare
```

Filtered discovery across all matches (consumables and recipe components are excluded by default; `--include-noise` brings them back):

```bash
python analyze_item_timings.py --hero-id 25 --min-games 50 --top 50
python analyze_item_timings.py --item black_king_bar --group hero-item --min-games 50 --top 50
python analyze_item_timings.py --group hero-item-rank --min-games 100 --top 50
python analyze_item_timings.py --group hero-item-rank-timing --min-games 30 --top 50
python analyze_item_timings.py --group hero-item --min-games 50 --status signal --top 50
python analyze_item_timings.py --group hero-item --min-games 50 --output reports/item_timings.csv --format csv
```

Read the deltas with care: the `±Xpp` is the 95% CI half-width of the cell itself. If the delta is smaller than the error bars of either group, it is noise, not a balance signal.

Farm context uses `egpm10` / `ebase` — average gold earned per minute **by minute 10** (from OpenDota `gold_t`), i.e. before most core purchases. Final GPM is intentionally not used for bias checks: farm-accelerating items legitimately raise buyers' final GPM, so it measures the item's effect as much as pre-existing advantage. The `bias` column (`low`, `medium`, `high`, `negative`) flags whether buyers were already farming better *before* buying. Hero and item display names are fetched once from OpenDota `/constants/heroes` and `/constants/items` and cached under `data/constants/`.

Generate per-hero item recommendation reports (CSV data + readable Markdown):

```bash
python generate_item_report.py --min-games 50 --top-per-hero 5
python generate_item_report.py --min-games 50 --signal-only
```

Outputs `reports/item_recommendations.csv` and `reports/item_recommendations.md`. By default both statistically separated signals and unclear rows are included (unclear is marked); pass `--signal-only` for strict reports.

Run the validation tests:

```bash
python -m pytest
```

## Current Limitations

- OpenDota is the only implemented source client.
- Replay parsing, STRATZ, Steam API enrichment, and ML feature generation are roadmap items.
- The processed schema intentionally captures only the first stable match/player summary fields.
- The first training model only learns draft-level hero signals and does not use items, timings, ranks, patches, lanes, or objectives yet.
- Patch, rank, role, lane, item, ability, objective, and timeline fields may be missing or source-specific and must be treated as partial until expanded schemas and data-quality reports are added.
