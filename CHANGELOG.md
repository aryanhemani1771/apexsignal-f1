# Changelog

All notable changes to ApexSignal F1. Format loosely follows Keep a Changelog.
Also serves as the agent development log (one entry per phase / work session).

## [Unreleased]

### Phase 7 — Portfolio deployment — 2026-07-19
**Objective:** a recruiter opens the dashboard/API and understands the system in two minutes.

Added:
- `api/main.py` — FastAPI service: `/health`, `/version`, `/disclaimer`, `/races/demo/state`,
  `/model-performance`, `/opportunities`, `POST /allocations` (read-only; simulated allocations;
  health reports safe mode + data availability). `fastapi`/`httpx` added to the dev group so the
  API is CI-tested via `TestClient`.
- Dashboard "Architecture" view (graphviz pipeline diagram + methodology) — 9 views total.
- Docker health checks (dashboard `/_stcore/health`, API `/health`).
- README "Actual measured results"; `deploy/PORTFOLIO_EMBED.md` portfolio copy + resume bullet
  filled with measured values; MODEL_CARD real metrics; RISK_DISCLOSURE final.
- API tests (health/version/state/opportunities/allocations/validation).

Verified:
- `make ci` green — 131 tests pass + 2 gated skips; ruff/mypy(strict)/bandit clean.
- **Full offline demo runs end-to-end**: bootstrap → replay (AX7 P1) → news timeline → 41
  markets/9 opportunities → API health `ok` (live_trading False) → 7-position simulated
  allocation. All 9 dashboard views and the API operate credential-free in fixture mode.

Deferred (documented): dashboard screenshots (need a browser); local Docker build verification;
multi-season evaluation.

### Phase 6 — Allocation & risk — 2026-07-19
**Objective:** a user-entered research amount → transparent simulated allocation, or a no-opportunity result.

Added:
- `allocation/constraints.py` — `RiskTolerance` + `RiskLimits` from `configs/risk_limits.yaml`
  (kelly fractions hard-capped at 0.25; exposure caps; thresholds).
- `allocation/kelly.py` — full-Kelly fraction + fractional-Kelly stake (no full Kelly).
- `simulation/payoff_matrix.py` — per-path `contract_payoff` + `build_payoff_matrix` (covariance
  substrate; every contract evaluated on the same paths).
- `allocation/optimizer.py` — correlation-aware greedy allocator: fractional Kelly on the
  conservative probability, clipped to per-market/total/driver/cluster caps, integer contracts;
  returns positions or `NO_ALLOCATION`.
- `allocation/stress_tests.py` — portfolio P&L paths → VaR(95%) + expected shortfall.
- `services/portfolio_service.py` — bankroll → allocation (price → scan → allocate).
- Dashboard "Simulated allocation" view (bankroll / tolerance / max-deployment inputs).
- Tests: Kelly math, limits (never full Kelly), payoff matrix, cap enforcement, bankroll safety,
  aggressive ≥ conservative, no-opportunity path, end-to-end service.

Verified:
- `make ci` green — 125 tests pass + 2 gated skips; ruff/mypy(strict)/bandit clean.
- **$10k / moderate**: 8 simulated positions, exactly 10% deployed, every cap respected, integer
  contracts, VaR95 $237 / ES95 $280 computed from the payoff paths. Kelly sizing scales with
  edge (low-edge markets get tiny stakes). Labeled "model-ranked simulated allocation" only.

### Phase 5 — Prediction-market integration — 2026-07-19
**Objective:** compare model prices to real public market data or synthetic replay books.

Added:
- `domain/markets.py` — unified read-only `MarketDataAdapter` Protocol + Market/OrderBook/
  MarketEvent/ContractType (prices normalised to probabilities).
- `ingestion/synthetic_market.py` — always-offline adapter; books from model prices, seeded to
  misprice so there are edges to find.
- `ingestion/kalshi_adapter.py` — public REST (read-only, lazy httpx, cents→prob parse) +
  `KalshiDemoExecutor` guarded by `LiveTradingDisabledError`.
- `ingestion/polymarket_adapter.py` — read-only + geo-availability check, graceful disable; no
  trading methods.
- `pricing/market_mapper.py` — rule-aware mapping with a confidence gate (never maps on title
  alone); `pricing/fees.py`, `pricing/edge.py` (effective price, conservative probability/edge).
- `services/opportunity_service.py` — scan model vs. market, rank by composite score, skip
  below-gate mappings, explicit "no qualifying opportunity".
- `execution/base.py` + `paper.py` + `synthetic.py` + `kalshi_demo.py` — paper accounting
  (fills cross the spread) and demo/live guards.
- `scripts/refresh_markets.py` + dashboard "Opportunity scanner" view.
- Tests: order-book math, fees/edge, synthetic adapter, mapping gate, opportunity ranking +
  no-opportunity, paper accounting, Kalshi cents→prob parsing, live-trading guard.

Verified:
- `make ci` green — 116 tests pass + 2 gated skips; ruff/mypy(strict)/bandit clean.
- **Model-vs-market scan** (`refresh_markets.py`): 41 synthetic markets → 9 ranked opportunities
  after fees/slippage and the mapping gate; top edge D6-points 16.7% (conservative). Safety
  guards verified: live Kalshi execution raises; title-only markets forced to manual review.

### Phase 4 — News intelligence — 2026-07-19
**Objective:** a structured news event visibly moves a model prior and is later confirmed/rejected by telemetry.

Added:
- `intelligence/event_ontology.py` (34 event classes, fundamental vs. context) and
  `domain/news.py` (NewsDocument + strict `ExtractedF1Event` schema with provenance).
- `intelligence/event_extractor.py` — deterministic rule-based extractor (14 event classes,
  entity resolution, prior-backed effect sizes, strict "unknown" handling); `EventExtractor`
  Protocol for an optional hosted-LLM extractor.
- `intelligence/entity_resolution.py`, `source_scoring.py` (from `configs/news_sources.yaml`),
  `deduplication.py`, `contradiction.py` (contradictions + supersession), `impact_priors.py`.
- `intelligence/event_impact.py` — Bayesian shrinkage event→parameter mapping (confidence,
  confirmation scaling, time decay); `telemetry_confirmation.py` (news proposes, telemetry
  confirms — normal-normal update); `sentiment.py` (public track, kept separate).
- `services/news_service.py` — point-in-time pipeline (availability filter before supersession)
  + `apply_impacts_to_sim_input`; `scripts/refresh_news.py`; dashboard "News intelligence" view.
- Synthetic news fixtures (`data/fixtures/news/`, invented drivers) + loaders.
- Tests: extraction, entity/source scoring, impact mapping, telemetry, sentiment, and a
  full-pipeline test proving a confirmed upgrade moves BO4's win probability.

Verified:
- `make ci` green — 105 tests pass + 2 gated skips; ruff/mypy(strict)/bandit clean.
- **Deliverable demonstrated** (`refresh_news.py`): confirmed aero upgrade moves BO4 win
  0.26→0.33; a superseded rumour drops out; telemetry observation confirms (posterior −0.087)
  or reverses (+0.035) the proposed pace prior. Sentiment shown on a separate track.

### Phase 3 — Race simulation & in-race pricing — 2026-07-19
**Objective:** price multiple contracts from simulated race continuations.

Added:
- Component models: `models/tyres.py` (degradation + robust fit), `models/dnf_hazard.py`
  (survival), `models/safety_car_hazard.py`, `models/pit_hazard.py`, `models/overtake.py`,
  and `models/latent_pace.py` (robust clean-air pace + a 1-D Kalman filter baseline).
- `simulation/engine.py` — vectorized Monte Carlo race-continuation simulator (lap-by-lap:
  pace + tyre deg + fuel + dirty air + noise; pit/DNF/safety-car draws; gap compression under
  SC). 5000 paths × ~37 laps in ~0.23s, seeded and deterministic.
- `simulation/payoff_matrix.py` — win/podium/points/DNF/fastest-lap/positions-gained/
  pit-before-lap/pairwise-H2H + race-level safety-car probabilities.
- `simulation/scenarios.py` — perturb pace/penalty/DNF/safety-car and compare contract deltas.
- `services/pricing_service.py` — race state + lap history → contract prices; `scripts/price_race.py`;
  a dashboard "Contract pricing" view.
- Tests: hazards, latent pace, simulator (determinism/validity/monotonicity), payoff,
  scenarios, pricing service, and a gated real-pricing integration test.

Verified:
- `make ci` green — 89 tests pass + 2 gated skips; ruff/mypy(strict)/bandit clean.
- **Real mid-race pricing on Bahrain 2023 (lap 30)**: VER 0.66 win / PER 0.20 / LEC 0.09,
  per-driver DNF ≈ the input rate — VER led and won. Matches reality; nothing hard-coded.

### Phase 2 — Baseline probabilities — 2026-07-19
**Objective:** produce evaluated, calibrated historical contract probabilities.

Added:
- `models/_numeric.py` — NumPy helpers (sigmoid/logit, IRLS logistic fit, PAVA isotonic).
- `models/driver_ratings.py` — time-varying driver/constructor Elo (decay + partial pooling)
  and a Beta-smoothed constructor DNF reliability estimate; pace ratings exclude retirements.
- `models/ranking.py` — Gumbel-max Plackett-Luce simulator → win/podium/points/DNF + pairwise
  head-to-head probabilities (seeded, deterministic).
- `models/prerace.py` + `backtesting/baselines.py` — `elo`, `elo_grid`, `grid`, `uniform`
  models over a shared prediction path.
- `models/calibration.py` — isotonic + Platt + identity, chosen by validation log loss.
- `backtesting/metrics.py` — Brier, log loss, ECE, calibration slope/intercept, reliability bins.
- `backtesting/evaluation.py` — walk-forward, time-based evaluation with validation-only
  calibration; `domain/contracts.py` (RaceResult / RacePrediction / outcome extractors).
- `ingestion/fastf1_adapter.py` — `load_session_result` → `RaceResult`.
- `services/evaluation_report.py` + dashboard "Model performance" view.
- Real `scripts/train_models.py`; report at `artifacts/reports/evaluation_latest.json`.
- Tests: metrics, calibration, ranking, ratings, prerace/baselines, evaluation, evaluation
  report, and a walk-forward leakage guard.

Verified:
- `make ci` green — 70 tests pass + 1 gated skip; ruff/mypy(strict)/bandit clean.
- **Real walk-forward evaluation on the 2022 season (22 races)**: best winner Brier
  `elo_grid` = 0.0312 (calibrated, 7 test races). Metrics are measured, not hard-coded; small
  test set flagged as noisy in `MODEL_CARD.md`.

Changed:
- Tests import from `src/` via pytest `pythonpath` (D-010), decoupling the gate from a flaky
  editable install.

### Phase 1 — Historical F1 data & replay — 2026-07-19
**Objective:** a complete race can be replayed locally without external credentials.

Added:
- `domain/race_state.py` — `RaceState`/`DriverState` + deterministic reducer
  (`apply_event`) and `replay`/`replay_states`; replay is order-independent and produces a
  stable snapshot id.
- `storage/event_store.py` — append-only event store with JSONL load/save, deterministic
  iteration order.
- `ingestion/fixtures_adapter.py` — load bundled fixture bundles offline.
- `ingestion/fastf1_adapter.py` — real FastF1 → domain events (laps, positions, tyres, pit
  stops, weather, track status, race control); t0-anchored absolute timestamps; lazy import
  so the module stays importable without the `data` extra.
- `ingestion/normalization.py` — `run_quality_checks` with 8 integrity checks + report.
- `services/race_service.py` — replay/standings/timing-tower helpers shared by CLI + dashboard.
- `dashboard/app.py` + `dashboard/theme.py` — interactive replay page (fixture mode).
- Real `scripts/download_history.py` and `scripts/replay_race.py`.
- Tests: reducer determinism, event-store round-trip, 8 quality checks, race-service views,
  and a network-gated FastF1 integration test (skipped unless `RUN_FASTF1_TESTS=1`).

Verified:
- `make ci` green — 42 tests pass + 1 gated skip; ruff/mypy(strict)/bandit clean.
- **Real end-to-end on the 2023 Bahrain GP**: 1347 events, 0 data-quality errors, replayed
  podium **VER / PER / ALO** — matches the actual race result.

### Phase 0 — Repository & research — 2026-07-19
**Objective:** repository boots and tests pass; documentation and tooling scaffold
that lets any agent (incl. Codex) resume the build phase-by-phase.

Added:
- Standalone `apexsignal-f1` repo, package structure under `src/apexsignal/`.
- `pyproject.toml` with `uv`, ruff, mypy (strict), pytest, coverage, bandit; phased
  optional-dependency groups (`data`/`models`/`api`/`dashboard`/`sim`).
- Tooling: `Makefile`, `.pre-commit-config.yaml`, `.gitignore`, `.env.example`.
- Containers: `Dockerfile`, `docker-compose.yml` (build not verified locally — no Docker on authoring machine).
- CI: `ci.yml`, `security.yml`, `refresh_demo_data.yml`, `deploy.yml`.
- Docs: README, AGENTS, CLAUDE, ROADMAP, DECISIONS, MODEL_CARD, RISK_DISCLOSURE,
  DATA_DICTIONARY, THIRD_PARTY_NOTICES, REFERENCES, `docs/BUILD_SPEC.md`.
- Configs: `base`, `development`, `portfolio_demo`, `risk_limits`, `news_sources`, `event_impact_priors`.
- Core code: `settings.py` (env validation + safety guards), `logging.py` (structlog + secret redaction),
  domain models `provenance.py` and `events.py`.
- Tests: settings validation, domain-event invariants, and a point-in-time leakage guard.
- Deterministic fixture bundle under `data/fixtures/`.

Notes:
- No fabricated metrics anywhere. No model results claimed yet.
