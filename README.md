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
