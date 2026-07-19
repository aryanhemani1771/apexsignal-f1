# ROADMAP — ApexSignal F1

This is the **single source of truth for build progress and handoff**. Any agent
(Claude Code, Codex, Fable) resuming work should read this first, then
`DECISIONS.md`, then `AGENTS.md`. Update the checklists and "Current status" as you go.

Legend: `[x]` done & verified · `[~]` partial / stubbed with a real interface · `[ ]` not started

---

## Current status

- **Phase:** 2 (Baseline probabilities) — **COMPLETE** (real evaluation on the 2022 season).
- **Last agent:** Claude Code (Opus 4.8), 2026-07-19.
- **Next action:** start **Phase 3** — race simulation: tyre-degradation, pit-hazard, DNF
  survival, overtake, and safety-car models; a vectorized Monte Carlo race-continuation
  simulator (~5k paths in a few seconds, seeded); the contract payoff matrix; and a scenario
  engine. The Plackett-Luce simulator and calibration/metrics from Phase 2 carry forward.
- **Deferred (non-blocking):** DuckDB/Parquet repository backends; LightGBM GBM baseline
  (pure-NumPy `grid`/`elo`/`elo_grid` + `uniform` cover the ≥4-baseline bar — see D-009);
  live current-position baseline (belongs to in-race, Phase 3); evaluation currently spans one
  season (7 test races → noisy metrics) — widen to multiple seasons; dashboard not run in CI.

### Verification status (be honest — do not claim unverified work)
| Capability | Verified how | Status |
|---|---|---|
| `uv sync --dev` installs | local | ✅ verified (Python 3.12.13, uv.lock committed) |
| `ruff` / `mypy(strict)` / `pytest` / `bandit` green | local `make ci` | ✅ verified — 42 tests pass + 1 gated skip, 0 lint/type/security issues |
| `scripts/bootstrap.py` runs | local | ✅ verified |
| Deterministic replay of the synthetic fixture | unit tests | ✅ verified |
| **Real FastF1 download + replay** (2023 Bahrain GP) | `RUN_FASTF1_TESTS=1` integration test + manual `download_history.py`/`replay_race.py` | ✅ verified — 1347 events, 0 quality errors, replayed podium **VER/PER/ALO** matches reality |
| **Real model evaluation** (2022 season) | `scripts/train_models.py` walk-forward | ✅ verified — 22 races; best winner Brier `elo_grid` 0.0312 (calibrated); report committed |
| Docker image builds | CI `deploy.yml` / `ci.yml` docker-build job | **NOT verified locally** — no Docker on the authoring machine |
| Dashboard (replay + model perf) renders | needs `--extra dashboard` (Streamlit) | **compiles + lints; not run-verified** (Streamlit not in CI env) |

---

## Phase 0 — Repository & research
**Deliverable:** *Repository boots and tests pass.*

- [x] Initialize repository + `.gitignore`
- [x] Package/directory structure under `src/apexsignal`
- [x] `pyproject.toml` (uv, ruff, mypy, pytest, coverage, bandit) with phased optional-dep groups
- [x] Tooling config: `.pre-commit-config.yaml`, `Makefile`
- [x] Container config: `Dockerfile`, `docker-compose.yml` (build not locally verified)
- [x] CI: `ci.yml`, `security.yml`, `refresh_demo_data.yml`, `deploy.yml`
- [x] Docs scaffold: README, CLAUDE, AGENTS, DECISIONS, ROADMAP, CHANGELOG, MODEL_CARD, RISK_DISCLOSURE, DATA_DICTIONARY, THIRD_PARTY_NOTICES, REFERENCES
- [x] `configs/*.yaml` (base, development, portfolio_demo, risk_limits, news_sources, event_impact_priors)
- [x] `.env.example` + startup settings validation (`settings.py`)
- [x] Structured logging (`logging.py`) with secret redaction
- [x] Foundational domain models with real tests: `provenance.py`, `events.py`
- [x] Minimal deterministic fixture bundle under `data/fixtures/`
- [x] `make ci` green locally (lint + type + test + security)  ← **Phase 0 exit gate ✅**
- [~] Inspect referenced repos' licenses and record in `REFERENCES.md` / `THIRD_PARTY_NOTICES.md` (initial pass done; deepen when code is actually borrowed in later phases)

## Phase 1 — Historical F1 data & replay
**Deliverable:** *A complete race can be replayed locally without external credentials.*

- [x] FastF1 adapter (`ingestion/fastf1_adapter.py`) — laps, positions, tyres, pit stops, weather, track status, race control; caching on; t0-anchored absolute times. *(telemetry/sector events deferred to when a model needs them)*
- [x] Normalize one complete race → domain events with stable IDs (meeting/session/driver/constructor). *(persisted as JSONL; DuckDB/Parquet repository backends deferred — see Current status)*
- [x] Append-only event store (`storage/event_store.py`) — immutable domain events + JSONL load/save
- [x] Deterministic race-state reducer (`domain/race_state.py`): `apply_event(state, event) -> state`
- [x] Deterministic replay (same event log ⇒ identical state + snapshot id) — unit-tested, order-independent
- [x] Data-quality checks + report (`ingestion/normalization.py`) — 8 check classes
- [~] Basic replay page in the dashboard (`dashboard/app.py`) — written, compiles, lints; not run in CI (no Streamlit env)
- [x] `scripts/download_history.py` (real FastF1), `scripts/replay_race.py` (offline replay) — both verified

## Phase 2 — Baseline probabilities
**Deliverable:** *Evaluated, calibrated historical probabilities.*

- [x] Baselines: grid + uniform + driver/constructor Elo (+ Elo×grid). GBM deferred (D-009); live current-position baseline is an in-race (Phase 3) predictor
- [x] Time-varying driver/constructor ratings (`models/driver_ratings.py`) — decay + partial pooling; pace ratings exclude DNFs
- [x] Pairwise "A ahead of B" + Plackett-Luce ranking → contract probs (`models/ranking.py`)
- [x] Winner / podium / points / H2H (pairwise) / DNF probabilities (`models/prerace.py`)
- [x] Time-based walk-forward splits, calibrate on validation only (`backtesting/evaluation.py`) + leakage test
- [x] Calibration (isotonic / Platt / identity) chosen by validation log loss (`models/calibration.py`)
- [x] Metrics: Brier, log loss, ECE, calibration slope/intercept, reliability bins (`backtesting/metrics.py`)
- [x] Model-performance dashboard view (real metrics from the report, else "Not yet evaluated")
- [x] Real evaluation run (`scripts/train_models.py`) → `artifacts/reports/evaluation_latest.json`

## Phase 3 — Race simulation
**Deliverable:** *Prices multiple contracts from simulated race continuations.*

- [ ] Tyre-degradation model · pit hazard · DNF survival · overtake · safety-car hazard
- [ ] Latent live-pace state-space model (Kalman baseline → particle filter)
- [ ] Vectorized Monte Carlo simulator (~5k paths in a few seconds, seeded in tests)
- [ ] Contract payoff matrix + scenario engine

## Phase 4 — News intelligence
**Deliverable:** *A structured news event visibly moves a model prior and is later confirmed/rejected by telemetry.*

- [ ] FIA + fixture adapters; event ontology; strict `ExtractedF1Event` schema
- [ ] Deterministic rule-based extractor (+ optional cached LLM extractor)
- [ ] Source scoring · dedup/clustering · contradiction & supersession
- [ ] Structured event → model-parameter mapping (Bayesian shrinkage, priors in `configs/event_impact_priors.yaml`)
- [ ] Telemetry confirmation ("news proposes, telemetry confirms")
- [ ] News dashboard page + event-study notebook

## Phase 5 — Prediction-market integration
**Deliverable:** *Model prices compared with real public market data or synthetic replay books.*

- [ ] Unified `MarketDataAdapter`; Kalshi public + WebSocket + demo execution (`LiveTradingDisabledError` guard)
- [ ] Polymarket read-only (+ optional geo-availability check, graceful disable)
- [ ] Synthetic market adapter (always works offline)
- [ ] Rule-aware contract mapping with confidence threshold + manual-review gate
- [ ] Opportunity dashboard page

## Phase 6 — Allocation & risk
**Deliverable:** *A user-entered research amount → transparent simulated allocation OR a no-opportunity result.*

- [ ] Effective price after fees/slippage · conservative EV (lower-bound based)
- [ ] Fractional Kelly (0.10/0.20/0.25; no full Kelly)
- [ ] Risk constraints from `configs/risk_limits.yaml`
- [ ] Payoff-covariance from simulation → correlation-aware constrained allocator
- [ ] Stress tests · allocation dashboard page · "No qualifying opportunity" path

## Phase 7 — Portfolio deployment
**Deliverable:** *A recruiter opens the hosted dashboard and understands it in two minutes.*

- [ ] Single-container deploy · public demo mode · health checks · graceful API fallbacks
- [ ] Screenshots · portfolio copy · finalize MODEL_CARD + RISK_DISCLOSURE
- [ ] Run full demo · record **actual measured** metrics · fill resume bullet brackets

---

## Handoff protocol (for the next agent / Codex)
1. Read `ROADMAP.md` (this file) → `DECISIONS.md` → `AGENTS.md`.
2. Pick the first unchecked box in the lowest incomplete phase.
3. Implement the **smallest end-to-end slice**, add its acceptance test, run `make check`.
4. Update this file's checkboxes + "Current status" + `CHANGELOG.md`; commit logically.
5. Never mark a box `[x]` unless it is actually verified. Use `[~]` for interface-complete stubs.
