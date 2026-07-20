# MODEL CARD — ApexSignal F1

> Living document. Fields marked **`Not yet evaluated`** must stay that way until a real
> evaluation run produces the number. Never hand-fill a metric.

## Overview
A stack of models that turn point-in-time F1 race state + structured news into calibrated
probabilities for prediction-market contracts (winner, podium, points, head-to-head, DNF,
safety car, pit-before-lap, positions gained, fastest lap, constructor comparisons).

## Intended use
Research and **paper-trading** only. Comparing model fair value to public market prices and
producing **simulated**, risk-constrained allocations. **Not** financial advice; **not**
for live-money trading.

## Model components (see ROADMAP for build status)
- Baselines: grid heuristic, current-position heuristic, driver/constructor Elo, GBM pre-race.
- Time-varying driver/constructor ratings (decay + partial pooling).
- Pairwise "A beats B" → coherent ranking → contract probabilities.
- Latent live-pace state-space model (Kalman → particle filter).
- Hazard models: tyre degradation, pit, DNF (survival), safety car, overtake.
- Monte Carlo race simulator → contract payoff matrix.
- Calibration layer (isotonic / Platt / beta), selected on validation only.

## Data
FastF1 / OpenF1 (timing, telemetry, tyres, weather, race control); FIA documents and
permitted news metadata/excerpts. Point-in-time discipline via `first_seen_at`.

## Evaluation
- Splits: **time-based only** (never random row splits within a race).
- Metrics: Brier, log loss, ECE, calibration slope/intercept, reliability diagrams,
  plus breakdowns by laps-remaining / circuit type / weather / contract type.
- Baseline comparison + ablations (no-news / sentiment / structured-event / telemetry-only / full).

**Measured evaluation** — walk-forward over **2022–2026 (102 real races, ~31 held-out test
races)**, 5000 simulation paths, calibrated on validation only. Full report:
`artifacts/reports/evaluation_latest.json`. Regenerate with
`uv run --extra data python scripts/train_models.py --season 2022 --season 2023 --season 2024 --season 2025 --season 2026`.

| Metric (calibrated, test set) | `grid` | `elo_grid` |
|---|---|---|
| Winner — Brier | **0.0284** | 0.0290 |
| Winner — log loss | **0.092** | 0.093 |
| Winner — ECE (calibration) | 0.019 | 0.022 |
| Podium — Brier | **0.0595** | 0.0607 |
| Podium — log loss | 0.316 | **0.276** |
| Points — Brier | **0.165** | 0.191 |
| DNF — Brier | 0.249 | **0.237** |
| DNF — ECE | 0.114 | 0.089 |

Naive baseline for reference: `uniform` winner Brier 0.078 (≈ the ~0.05 win base rate after
calibration drift). Both models roughly **halve** the winner Brier and are **well calibrated**
(ECE ≈ 0.02).

> **Honest reading:** on a large sample, **starting grid position does most of the predictive
> work** — `grid` and `elo_grid` are statistically tied on winner/podium, and Elo *form* adds
> only modest value (it helps points/DNF). This matches F1 reality (pole/front-row wins most
> races). **DNF prediction is weak** (Brier ≈ 0.24, near the event's own variance) — retirements
> are close to random at this feature depth. A single-race sanity check (2023 Bahrain, VER
> favoured mid-race) and a most-recent-3-race spot check (`predict_recent.py`: 1/3 winners, 5/9
> podium slots) are illustrative, not statistically strong. This is a **calibrated baseline that
> beats naive models**, not a proven edge over the market.

## Uncertainty
Every probability is returned with a lower/upper bound plus `model_version`,
`calibration_version`, `data_snapshot_id`. Allocation uses the **conservative**
(lower-bound-adjusted) probability, never the raw point estimate.

## Limitations & risks
Small-sample event classes; regime changes (regulations, upgrades); market illiquidity;
news extraction errors; simulation simplifications (collisions modeled probabilistically).
See `RISK_DISCLOSURE.md`.

## Ethical / safety
No live-money execution. No evasion of platform/geo controls. No fabricated performance.
