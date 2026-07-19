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

**First measured evaluation** — walk-forward over the **2022 season (22 races)**, 5000
simulation paths, calibrated on validation only, scored on the final **7 test races**.
Best model by winner Brier is `elo_grid` (Elo form + starting grid). Full report:
`artifacts/reports/evaluation_latest.json`. Regenerate with
`uv run --extra data python scripts/train_models.py --season 2022`.

| Metric (calibrated, test set) | `grid` | `elo` | `elo_grid` |
|---|---|---|---|
| Winner — Brier | 0.0385 | 0.0472 | **0.0312** |
| Winner — log loss | 0.143 | 0.141 | 0.293 |
| Podium — Brier | 0.0797 | 0.1004 | **0.0788** |
| Podium — log loss | 0.261 | 0.985 | **0.423** |
| DNF — ECE | 0.052 | 0.125 | 0.125 |

> **Caveat (honest):** the test set is only 7 races, so these numbers are noisy — treat them
> as a working baseline, not a settled result. Longer horizons (more seasons) come next; the
> harness records whatever is actually measured. `elo`'s edge over `grid` is expected to grow
> with more training races.

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
