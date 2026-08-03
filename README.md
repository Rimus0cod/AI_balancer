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
