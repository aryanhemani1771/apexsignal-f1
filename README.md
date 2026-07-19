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

---

## Status

🚧 **Early build — Phase 0 of 7.** See [`ROADMAP.md`](ROADMAP.md) for exactly what is
implemented, experimental, planned, and validated. This project follows a strict
**no-fabricated-results** policy: any metric shown as `Not yet evaluated` has genuinely
not been measured yet.

| Category | State |
|---|---|
| Repository, tooling, CI, docs | Implemented (Phase 0) |
| Historical data + deterministic replay | Planned (Phase 1) |
| Baseline + calibrated probabilities | Planned (Phase 2) |
| Monte Carlo simulation & contract pricing | Planned (Phase 3) |
| Structured news intelligence | Planned (Phase 4) |
| Kalshi / Polymarket integration | Planned (Phase 5) |
| Allocation & risk | Planned (Phase 6) |
| Hosted portfolio demo | Planned (Phase 7) |

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
