# ROADMAP — ApexSignal F1

This is the **single source of truth for build progress and handoff**. Any agent
(Claude Code, Codex, Fable) resuming work should read this first, then
`DECISIONS.md`, then `AGENTS.md`. Update the checklists and "Current status" as you go.

Legend: `[x]` done & verified · `[~]` partial / stubbed with a real interface · `[ ]` not started

---

## Current status

- **Phase:** 6 (Allocation & risk) — **COMPLETE** (bankroll → simulated allocation verified).
- **Last agent:** Claude Code (Opus 4.8), 2026-07-19.
- **Next action:** start **Phase 7** — portfolio deployment: single-container deploy + public
  demo mode + health checks + graceful API fallbacks; screenshots + portfolio copy; finalize
  MODEL_CARD / RISK_DISCLOSURE; run the full demo and record **actual measured** metrics; fill
  the resume-bullet brackets. Mostly packaging/docs — the nine analytical pages exist.
- **Deferred (non-blocking):** DuckDB/Parquet backends; LightGBM GBM baseline (D-009); widen
  Phase 2 evaluation; explicit `DriverRetired` events (D-011); latent-pace particle filter;
  hosted-LLM extractor (D-012); real FIA/RSS/GDELT news adapters; Kalshi WebSocket + demo order
  signing (D-013); constructor-exposure cap needs a driver→constructor lineup map (driver +
  cluster caps enforced); full event-driven backtester (`run_backtest.py` still a stub — walk-
  forward eval covers Phase 2); richer bundled demo race; Docker + dashboard not run in CI.

### Verification status (be honest — do not claim unverified work)
| Capability | Verified how | Status |
|---|---|---|
| `uv sync --dev` installs | local | ✅ verified (Python 3.12.13, uv.lock committed) |
| `ruff` / `mypy(strict)` / `pytest` / `bandit` green | local `make ci` | ✅ verified — 42 tests pass + 1 gated skip, 0 lint/type/security issues |
| `scripts/bootstrap.py` runs | local | ✅ verified |
| Deterministic replay of the synthetic fixture | unit tests | ✅ verified |
| **Real FastF1 download + replay** (2023 Bahrain GP) | `RUN_FASTF1_TESTS=1` integration test + manual `download_history.py`/`replay_race.py` | ✅ verified — 1347 events, 0 quality errors, replayed podium **VER/PER/ALO** matches reality |
| **Real model evaluation** (2022 season) | `scripts/train_models.py` walk-forward | ✅ verified — 22 races; best winner Brier `elo_grid` 0.0312 (calibrated); report committed |
| **Real mid-race pricing** (2023 Bahrain, lap 30) | `scripts/price_race.py` + gated integration test | ✅ verified — VER 0.66 win / PER 0.20 / LEC 0.09; DNF ≈ input; VER led & won |
| Monte Carlo speed | local timing | ✅ 5000 paths × 37 laps in ~0.23s (well under the "few seconds" bar) |
| **News moves a prior + telemetry confirms** | `scripts/refresh_news.py` + unit tests | ✅ verified — confirmed upgrade: BO4 win 0.26→0.33; telemetry obs confirms/reverses the pace prior |
| **Model-vs-market opportunity scan** | `scripts/refresh_markets.py` + unit tests | ✅ verified — 41 synthetic markets → 9 ranked opportunities after fees/slippage/mapping gate; "no opportunity" path works |
| Safety guards (no live trading, Polymarket read-only, mapping gate) | unit tests | ✅ verified — `LiveTradingDisabledError` on live Kalshi; title-only markets forced to manual review |
| **Bankroll → simulated allocation** | `services/portfolio_service.py` + unit tests | ✅ verified — $10k → 8 positions, exactly 10% deployed, all caps respected, integer contracts, VaR95 $237 / ES95 $280 from payoff paths; "no qualifying opportunity" path works |
| Docker image builds | CI `deploy.yml` / `ci.yml` docker-build job | **NOT verified locally** — no Docker on the authoring machine |
| Dashboard (replay + pricing + model perf) renders | needs `--extra dashboard` (Streamlit) | **compiles + lints; not run-verified** (Streamlit not in CI env) |

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

- [x] Tyre degradation (`models/tyres.py`) · pit hazard · DNF survival · overtake · safety-car hazard — parametric baselines, tested
- [~] Latent live-pace state-space model — Kalman baseline shipped (`models/latent_pace.py`); particle filter deferred
- [x] Vectorized Monte Carlo simulator (`simulation/engine.py`) — 5000 paths × 37 laps in ~0.23s, seeded/deterministic in tests
- [x] Contract payoff matrix (`simulation/payoff_matrix.py`) + scenario engine (`simulation/scenarios.py`)
- [x] Pricing service (`services/pricing_service.py`) state→prices + `scripts/price_race.py` + dashboard pricing view

## Phase 4 — News intelligence
**Deliverable:** *A structured news event visibly moves a model prior and is later confirmed/rejected by telemetry.*

- [x] Fixture news adapter + event ontology (`intelligence/event_ontology.py`) + strict `ExtractedF1Event` schema (`domain/news.py`). Real FIA/RSS/GDELT adapters deferred.
- [x] Deterministic rule-based extractor (`intelligence/event_extractor.py`) — 14 event classes, entity resolution, prior-backed effect sizes; LLM extractor Protocol in place, optional (D-012)
- [x] Source scoring (`intelligence/source_scoring.py`) · dedup (`deduplication.py`) · contradiction & supersession (`contradiction.py`)
- [x] Structured event → model-parameter mapping with Bayesian shrinkage + confidence/decay (`intelligence/event_impact.py`); priors from `configs/event_impact_priors.yaml`
- [x] Telemetry confirmation (`intelligence/telemetry_confirmation.py`) — normal-normal update, confirmed/reduced/reversed
- [x] `services/news_service.py` pipeline (point-in-time correct) + `scripts/refresh_news.py` + dashboard "News intelligence" view. Event-study notebook deferred to Phase 7.

## Phase 5 — Prediction-market integration
**Deliverable:** *Model prices compared with real public market data or synthetic replay books.*

- [x] Unified `MarketDataAdapter` (`domain/markets.py`); Kalshi public REST (`ingestion/kalshi_adapter.py`) + demo executor guarded by `LiveTradingDisabledError`. WebSocket streaming + demo order signing deferred (need demo creds).
- [x] Polymarket read-only (`ingestion/polymarket_adapter.py`) + geo-availability check, graceful disable; no trading methods exist on the class
- [x] Synthetic market adapter (`ingestion/synthetic_market.py`) — always works offline; books derived from model prices, seeded to misprice
- [x] Rule-aware contract mapping (`pricing/market_mapper.py`) with confidence score + manual-review gate; never maps on title alone
- [x] Fees/edge (`pricing/fees.py`, `pricing/edge.py`) + opportunity scanner (`services/opportunity_service.py`, conservative edge, "no opportunity" path) + paper/synthetic/kalshi-demo executors + `scripts/refresh_markets.py` + dashboard "Opportunity scanner" view

## Phase 6 — Allocation & risk
**Deliverable:** *A user-entered research amount → transparent simulated allocation OR a no-opportunity result.*

- [x] Effective price after fees/slippage (Phase 5) · conservative EV, lower-bound based (`pricing/edge.py`)
- [x] Fractional Kelly (`allocation/kelly.py`) — 0.10/0.20/0.25, hard-capped; full Kelly never offered
- [x] Risk constraints from `configs/risk_limits.yaml` (`allocation/constraints.py`)
- [x] Payoff matrix + covariance from simulation (`simulation/payoff_matrix.py`) → correlation-aware greedy allocator with local caps (`allocation/optimizer.py`)
- [x] Stress tests VaR/ES (`allocation/stress_tests.py`) · allocation dashboard page · explicit "No qualifying opportunity" · `services/portfolio_service.py` (bankroll→allocation)
- [~] Constructor-exposure cap deferred (needs a driver→constructor lineup map); per-driver + correlated-cluster caps enforced. Full event-driven backtester (`run_backtest.py`) still a stub.

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
