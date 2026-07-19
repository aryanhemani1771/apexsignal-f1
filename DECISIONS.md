# DECISIONS — ApexSignal F1

Architecture Decision Log. Newest first. Each entry: context → decision → rationale → status.
The autonomous build makes sensible technical calls here rather than blocking on the user.

---

## 2026-07-19 — Phase 0 foundation

### D-001 Repository lives as a standalone sibling repo
- **Context:** authored from within an unrelated resume-tooling directory.
- **Decision:** create a clean, standalone `apexsignal-f1` repo (its own git history), not nested in any existing project.
- **Rationale:** spec requires an original, self-contained project; avoids polluting unrelated tooling.
- **Status:** done.

### D-002 uv + phased optional-dependency groups
- **Decision:** `uv` for env/deps; core deps kept minimal; heavy stacks (`data`, `models`, `api`, `dashboard`, `sim`) are optional-dependency extras pulled in per phase.
- **Rationale:** keeps Phase 0 / CI fast and installable; avoids compiling LightGBM/PyMC before they're used. Matches "simplest architecture that satisfies acceptance criteria."
- **Status:** done.

### D-003 Python 3.12 via uv even though system Python is 3.10
- **Decision:** target 3.12; `uv` fetches its own interpreter.
- **Rationale:** spec pins 3.12; decouples from the machine's anaconda 3.10.
- **Status:** done (uv installed this session).

### D-004 Docker configs written but not locally verified
- **Context:** no Docker daemon on the authoring machine.
- **Decision:** ship `Dockerfile` + `docker-compose.yml`; rely on CI's docker-build job as the verification of record; mark clearly in `ROADMAP.md`.
- **Rationale:** anti-fabrication rule — do not claim a build succeeds when it was never run.
- **Status:** written, unverified locally.

### D-005 Event sourcing with a plain append-only log (no Kafka)
- **Decision:** immutable domain events in an append-only store backed by DuckDB/Parquet; `asyncio.Queue` for in-process distribution; add Redis only when separate live processes need it (Phase 5+).
- **Rationale:** spec explicitly says not to add Kafka for sophistication; portfolio-scale simplicity.
- **Status:** interface planned; store lands in Phase 1.

### D-006 Safety defaults are hard-coded, not just documented
- **Decision:** `ENABLE_LIVE_TRADING=false`, `EXECUTION_MODE=paper` enforced in `settings.py` validation; real-money execution path raises `LiveTradingDisabledError` and is never implemented on the default branch. No geo-restriction bypass, ever. Polymarket read-only.
- **Rationale:** non-negotiable safety/integrity section of the spec.
- **Status:** settings guard implemented Phase 0; execution guards in Phase 5.

### D-007 Provenance timestamps are first-class on every observation
- **Decision:** every event carries `event_time`, `first_seen_at`, `ingested_at` (+ `published_at`, `effective_at` where applicable); backtests use `first_seen_at` for availability. Leakage tests enforce it.
- **Rationale:** no-data-leakage requirement; defensible point-in-time reconstruction.
- **Status:** base models + leakage test implemented Phase 0.

### D-009 Pure-NumPy model stack for Phase 2; GBM deferred
- **Decision:** implement the Phase 2 baselines and calibration in pure NumPy (Elo ratings,
  Plackett-Luce simulation, isotonic/Platt calibration, Brier/log-loss/ECE) so the whole model
  stack is exercised in CI without the heavy `models` extra. The ≥4-baseline bar is met by
  `uniform`, `grid`, `elo`, `elo_grid`. A LightGBM GBM pre-race model is deferred to a guarded
  module (like the FastF1 adapter) when tabular training data warrants it.
- **Rationale:** fast, deterministic, offline-testable; avoids compiling LightGBM for a
  baseline that grid+Elo already cover. Simplest thing that satisfies the acceptance criteria.
- **Status:** done (Phase 2). GBM: not started.

### D-010 Tests import from `src/` via pytest `pythonpath`
- **Context:** the hatchling editable install for the `src/` layout proved flaky across repeated
  `uv sync` runs with different extras (the package intermittently failed to import).
- **Decision:** set `[tool.pytest.ini_options] pythonpath = ["src"]` so tests import the package
  directly from source, independent of the editable install. CI does a single clean sync anyway.
- **Rationale:** robust, standard for src-layout, decouples the test gate from install flakiness.
- **Status:** done.

### D-011 Simulator is cumulative-time + hazards; retirement inferred for live pricing
- **Decision:** the Monte Carlo engine advances positions by cumulative race time (fastest car
  advances) with a dirty-air penalty for track-position stickiness, and draws pits/DNF/safety
  cars from the hazard models. Two subtleties resolved: (a) the per-lap DNF hazard is calibrated
  **once** to the remaining stint (recomputing it against a shrinking `laps_remaining` each lap
  oversums retirements); (b) `pricing_service` orders drivers from the reducer's tracked
  `position` and treats a driver whose last lap is well behind the leader as retired — the
  FastF1 adapter doesn't emit explicit retirement events yet, and naive cumulative-time sums
  rank a car with fewer completed laps as "ahead".
- **Rationale:** transparent, fast (5k paths in ~0.23s), and correct on real data — verified on
  Bahrain 2023 (VER favourite mid-race, DNF ≈ input). Simplest approach meeting the deliverable.
- **Status:** done (Phase 3). Future: have the adapter emit `DriverRetired`; add a particle filter.

### D-008 Deterministic-first, LLM-optional
- **Decision:** the default news event extractor is rule-based and deterministic; a hosted LLM extractor is an optional, cached, schema-validated alternative. Explainability contributions are computed numerically; an LLM may only phrase verified numbers.
- **Rationale:** reproducibility, anti-fabrication, offline CI.
- **Status:** interfaces in Phase 4.
