# AI Balancer Roadmap

This roadmap frames AI Balancer as a multi-year ML research platform for Dota 2 balance intelligence.

## Phase 1 — Data Platform (1–2 months)

**Goal:** collect and preserve high-quality match data.

- Collect matches from OpenDota, STRATZ, and Steam APIs.
- Add replay parsing once the baseline API pipeline is stable.
- Store patch, rank, duration, heroes, items, talents, facets, neutral items, ability builds, gold, XP, damage, KDA, objectives, Roshan events, wards, smokes, and timelines.
- Split storage into raw, processed, and ML-feature layers.
- Version every dataset by patch.
- Build initial analytical queries for validation and exploration.

## Phase 2 — Analytical Core (1–2 months)

**Goal:** answer statistical balance questions reliably.

- Implement anomaly detection for heroes, items, talents, facets, and roles.
- Analyze hero, item, and facet synergies under patch, rank, and role filters.
- Measure patch impact with before/after comparisons and confidence intervals.
- Build a basic web interface with charts, filters, and drill-down views.

## Phase 3 — Representation Learning (2–3 months)

**Goal:** train a model that learns match structure.

- Convert matches into event sequences such as picks, bans, kills, item timings, Roshan, objectives, high-ground pushes, and win/loss outcomes.
- Train a Transformer Encoder to produce match embeddings.
- Use embeddings for similar-match search, strategy clustering, unusual-game detection, and meta-shift analysis.

## Phase 4 — Graph Model (2–3 months)

**Goal:** model complex interactions across game entities.

- Build a graph connecting heroes, abilities, talents, facets, items, neutral items, matches, patches, and roles.
- Train a graph neural network to discover hidden dependencies.
- Surface conditional balance patterns such as hero-facet-item-patch-rank interactions.

## Phase 5 — Balance Intelligence (3–6 months)

**Goal:** combine all model outputs into one decision-support system.

- Create a unified balance score with confidence and explanation metadata.
- Estimate the impact of proposed balance changes.
- Generate recommendations backed by statistical and model-derived evidence.
- Add an LLM assistant that explains existing signals without performing the underlying calculations.
- Expand the dashboard into a complete patch-review workspace.

## Target Capabilities

The long-term system should support questions like:

- Which heroes became outliers after a patch, and why?
- Which item timings changed the most across ranks?
- Which new counters appeared after a hero or item update?
- Which balance changes increase draft diversity with minimal disruption?
- Which proposed patch changes are likely to create second-order effects?
