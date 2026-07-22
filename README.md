# ApexSignal F1

**ApexSignal F1 is an event-driven Formula 1 prediction-market research platform that
combines historical telemetry, live race state, structured technical and incident news,
calibrated Monte Carlo simulation, public exchange prices, and correlation-aware paper
allocation.**

> Given all information available at this exact moment, what is the calibrated
> probability of each F1 contract settling *Yes*, how does that compare with the market,
> why does the model disagree, and what **simulated** allocation would satisfy a
> conservative risk policy?

It is a research and **paper-trading** platform — not a live-money trading bot, and not a
one-shot winner predictor. Allocations are always labeled *Model-ranked simulated
allocation*; the engine is allowed to answer *"No qualifying opportunity."*

> ℹ️ *A personal research/learning project, built with AI assistance, to explore end-to-end
> quantitative-research workflows — point-in-time data engineering, calibrated probabilistic
> modeling, market microstructure, and risk. Research and paper-trading only; no real money.*

---

## Status

**All 7 phases implemented.** See [`ROADMAP.md`](ROADMAP.md) for exactly what is implemented,
experimental, and deferred. This project follows a strict **no-fabricated-results** policy: any
metric shown as `Not yet evaluated` has genuinely not been measured yet; the numbers below were
measured by the code.

| Capability | State |
|---|---|
| Repository, tooling, CI, docs | ✅ Implemented (Phase 0) |
| Historical data + deterministic replay | ✅ verified on real 2023 Bahrain GP (Phase 1) |
| Baseline + calibrated probabilities | ✅ real 2022-season evaluation (Phase 2) |
| Monte Carlo simulation & contract pricing | ✅ mid-race pricing verified (Phase 3) |
| Structured news intelligence | ✅ moves a prior + telemetry confirms (Phase 4) |
| Kalshi / Polymarket / synthetic integration | ✅ read-only + safety guards (Phase 5) |
| Allocation & risk | ✅ fractional Kelly + VaR/ES (Phase 6) |
| FastAPI + dashboard + deploy | ✅ 9 views, health checks (Phase 7) |

### Actual measured results
*(reproduce with the commands noted; nothing here is hard-coded)*

- **Replay** — 2023 Bahrain GP: 1347 events, 0 data-quality errors, replayed podium **VER / PER /
  ALO** (matches reality). `download_history.py` + `replay_race.py`.
- **Baseline evaluation** — walk-forward on **2022–2026 (102 real races, ~31 held-out test
  races)**: calibrated winner-contract Brier **0.028** (`grid`) / **0.029** (`elo_grid`), roughly
  half the naive baseline (0.078) and well-calibrated (ECE ≈ 0.02). Honest finding: **starting
  grid does most of the work**; Elo form adds modest value; DNF prediction is weak. `train_models.py`.
- **Recent-race spot check** — trained on 2022–2026, predicting the 3 most recent races:
  **1/3 winners, 5/9 podium slots** (small sample, illustrative). `predict_recent.py`.
- **In-race pricing** — 2023 Bahrain at lap 30: **VER 0.66 / PER 0.20 / LEC 0.09** win; per-driver
  DNF ≈ the input rate. Monte Carlo runs **5000 paths × 37 laps in ~0.23s**. `price_race.py`.
- **News → model** — a confirmed aero upgrade moves a driver's win probability **0.26 → 0.33**;
  telemetry then confirms/reverses the pace prior. `refresh_news.py`.
- **Model vs. market** — 41 synthetic markets → **9 ranked opportunities** after fees, slippage,
  and the mapping gate. `refresh_markets.py`.
- **Allocation** — $10k / moderate → 8 positions, exactly 10% deployed, all caps respected,
  **VaR95 ~$237 / ES95 ~$280** from the payoff paths. Dashboard "Simulated allocation".

> These are baseline models on a modest evaluation window — a working research system, not a
> settled result. See `MODEL_CARD.md` for the honest caveats.

## Why this project exists
To demonstrate the full research-to-production workflow of a junior quantitative
researcher: point-in-time data engineering, calibrated probabilistic modeling, survival
and hazard models, Monte Carlo simulation, market microstructure and fair-value
comparison, and risk-constrained allocation — end to end, with honest evaluation.

## Quickstart (fixture mode — no credentials)
```bash
git clone <this-repo> apexsignal-f1 && cd apexsignal-f1
make setup      # uv sync --dev  (uv installs Python 3.12 itself)
make check      # ruff + mypy + pytest
```
The fixture demo requires **zero** credentials. Live/authenticated adapters are optional
and are unlocked via `.env` (copy from `.env.example`).

## Docker
```bash
docker compose up --build      # dashboard on :8501  (add --profile api for the API on :8000)
```
> The Docker build is verified in CI, not on the authoring machine — see `ROADMAP.md`.

## Operating modes
`APP_MODE = fixture | replay | live | paper` — fixture (bundled deterministic data, used
by CI and the public demo), replay (event-by-event historical replay), live (read-only
latest data, no order placement), paper (simulated fills & P&L; Kalshi *demo* execution
optional via `EXECUTION_MODE=kalshi_demo`).

## Safety, data & licensing
- Default: `ENABLE_LIVE_TRADING=false`, `EXECUTION_MODE=paper`. No real-money execution
  exists on this branch. Polymarket is read-only. No evasion of platform/geographic controls.
- FastF1 / OpenF1 supply F1 data; only permitted news excerpts + metadata are retained.
  See [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md),
  [`REFERENCES.md`](REFERENCES.md).
- Model scope & limits: [`MODEL_CARD.md`](MODEL_CARD.md). Risk framing: [`RISK_DISCLOSURE.md`](RISK_DISCLOSURE.md).

## Testing
```bash
make test        # full suite         make cov     # with coverage
make lint        # ruff               make type    # mypy (strict)
make security    # bandit             make audit   # pip-audit
```

## Roadmap
Seven phases, each with a concrete deliverable — see [`ROADMAP.md`](ROADMAP.md).

## Disclaimer
ApexSignal F1 is an independent research project and is not affiliated with Formula 1,
the FIA, any constructor, Kalshi, Polymarket, or Akuna Capital. Nothing here is financial
advice. All allocations are simulated for research purposes only.
