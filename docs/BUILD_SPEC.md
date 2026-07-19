# BUILD SPEC (condensed) — ApexSignal F1

Faithful condensation of the master autonomous build specification this project derives
from. `ROADMAP.md` is the live tracker; this file is the durable statement of intent so any
agent (incl. Codex) shares the same target. Where this and `ROADMAP.md` differ on status,
`ROADMAP.md` wins.

## Mission
News-aware, event-driven F1 prediction-market **pricing + paper-trading research**
platform. Download & normalize historical F1 data; reconstruct point-in-time race state
without leakage; estimate calibrated contract probabilities; update them as laps, weather,
pits, race-control, penalties, incidents, and news arrive; compare to Kalshi/Polymarket
(read-only) prices; rank opportunities after fees/slippage/uncertainty/liquidity/
correlation; produce a conservative **simulated** allocation from a user bankroll; and
present it in a polished, embeddable dashboard with replay, calibration, and provenance.

## Supported contracts
Driver win · podium · points · A-ahead-of-B · retires (DNF) · both constructor cars finish ·
safety car (race / next N laps) · pit before lap N · gains ≥ K positions · fastest lap ·
constructor points comparison. Only display contracts that map to a real market with high
confidence.

## Non-negotiables
- `ENABLE_LIVE_TRADING=false`, `EXECUTION_MODE=paper` by default; no real-money execution;
  guarded path raises `LiveTradingDisabledError`. Polymarket read-only. No geo/platform
  evasion, VPN/proxy, account automation, or CAPTCHA solving.
- Allocations labeled "Model-ranked simulated allocation"; never "guaranteed/safe/lock/
  risk-free". Engine may return "No qualifying opportunity."
- No fabricated results — `Not yet evaluated` until measured. README/ROADMAP separate
  implemented / experimental / planned / validated.
- No data leakage — `event_time`, `published_at`, `first_seen_at`, `ingested_at`,
  `effective_at`; backtests use `first_seen_at`; leakage tests required.
- Original branding; inspect licenses before reuse; `THIRD_PARTY_NOTICES.md`.

## Build modes
`fixture` (deterministic bundled data; CI/tests/demo) · `replay` (event-by-event historical)
· `live` (read-only latest) · `paper` (simulated fills/P&L; optional `kalshi_demo` exec).

## Model stack (progressive — no giant NN first)
Baselines (grid, position, Elo, GBM) → driver/constructor ratings → pairwise/ranking →
latent live-pace state-space (Kalman→particle) → tyre/pit/DNF/safety-car/overtake hazards →
vectorized Monte Carlo (~5k paths/few seconds, seeded) → payoff matrix + scenarios →
calibration (isotonic/Platt/beta on validation) with uncertainty bounds.

## News intelligence
Separate **fundamental** race info (can move fair value) from **public sentiment** (explains
market moves). Strict `ExtractedF1Event` schema; deterministic extractor + optional cached
LLM; source scoring; dedup/clustering; contradiction & supersession; structured event →
model-parameter mapping via Bayesian shrinkage (priors in
`configs/event_impact_priors.yaml`, labeled as priors); "news proposes, telemetry confirms."

## Markets & pricing
Unified `MarketDataAdapter`; Kalshi public+WS+demo; Polymarket read-only (+optional geo
check); synthetic adapter always works. Rule-aware mapping with confidence threshold and
manual-review gate — never rank/allocate to an ambiguous mapping. Fair vs. market vs.
conservative probabilities; conservative EV = `probability_lower_bound − effective_ask`.

## Allocation & risk
Fractional Kelly (0.10/0.20/0.25; no full Kelly) on conservative probability; constraints
in `configs/risk_limits.yaml` (per-market/total/driver/constructor/cluster caps, min edge,
min mapping confidence, liquidity, slippage); correlation from the simulated payoff
covariance; constrained optimizer (cvxpy or transparent greedy + local improvement); stress
tests; explicit "No qualifying opportunity."

## Dashboard (9 pages)
Executive overview · live race state · contract pricing · opportunity scanner · simulated
allocation · news intelligence · race replay · model performance · architecture/methodology.
Dark trading-terminal theme, responsive, `?embed=true`, no copyrighted branding.

## Acceptance (see ROADMAP for status)
≥1 full race bundled for offline replay; ≥20 races processable; deterministic replay;
data-quality reports; ≥4 baselines; calibrated held-out probabilities; ≥6 news event
classes end-to-end; Kalshi/Polymarket/synthetic adapters per rules; user-entered bankroll →
constrained simulated allocation or none; all dashboard pages load in fixture mode;
model-performance page shows real metrics; Docker build + CI green; one-command setup;
complete `.env.example`; no secrets committed; meaningful test coverage; graceful API
degradation.

## Phases
0 repo/research · 1 data+replay · 2 baselines+calibration · 3 simulation · 4 news ·
5 markets · 6 allocation/risk · 7 portfolio deploy. Build the smallest end-to-end slice per
step; test; document; commit.
