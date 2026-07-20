# Portfolio embedding (Phase 7 target)

How to embed the public ApexSignal F1 demo in a personal portfolio. Placeholders are filled
once the demo is actually deployed — nothing here claims a live URL yet.

## Hosted URL
`https://<your-deployment>/`  *(placeholder — not yet deployed)*

## Embed mode
The dashboard supports an embed view that hides navigation chrome:
```
https://<your-deployment>/?embed=true
```
```html
<iframe src="https://<your-deployment>/?embed=true"
        width="100%" height="820" style="border:0;border-radius:12px"
        title="ApexSignal F1 — F1 prediction-market research demo"
        loading="lazy"></iframe>
```

## Two-minute demo script
1. Open the historical race replay.
2. Step to a major incident (e.g., a safety car).
3. Watch the model probability update with attribution.
4. Show the related race-control / news event on the news timeline.
5. Compare model fair value vs. the market (or synthetic book).
6. Enter a sample research bankroll.
7. Show the correlation-aware simulated allocation (or the "No qualifying opportunity" result).
8. Open the calibration / model-performance page.

## Short project description (GitHub repo "About")
> Event-driven F1 prediction-market research platform: point-in-time telemetry + structured
> news → calibrated Monte Carlo pricing → market comparison → correlation-aware paper
> allocation.

## Resume bullet
Filled with **measured** values (2022-season evaluation, 5000-path Monte Carlo):
> Built an event-driven F1 prediction-market research engine across **22 races**, combining
> historical telemetry, structured upgrade/incident news (Bayesian shrinkage + telemetry
> confirmation), calibrated Elo/hazard models, and a **5000-path** vectorized Monte Carlo to
> price winner/podium/head-to-head/DNF contracts (calibrated winner-Brier **0.031** on a
> held-out test period); shipped a FastAPI + Streamlit dashboard comparing fair value with
> Kalshi/Polymarket/synthetic order books and generating fractional-Kelly, correlation-aware,
> risk-constrained **paper** allocations with VaR/expected-shortfall.

Keep the "paper/research" framing — this is not a live-trading system.

## Screenshots
Generated in Phase 7 via `scripts/generate_demo_assets.py`; stored under `dashboard/assets/`.
