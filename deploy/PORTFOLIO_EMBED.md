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
Fill only with **measured** values after Phase 7 evaluation (brackets are placeholders):
> Built an event-driven F1 prediction-market engine across [N] races, combining live
> telemetry, structured upgrade/incident news, calibrated hazard models, and [P]-path Monte
> Carlo simulation to price winner/podium/H2H/DNF contracts; deployed a dashboard comparing
> fair value with Kalshi/Polymarket order books and generating risk-constrained paper
> allocations.

## Screenshots
Generated in Phase 7 via `scripts/generate_demo_assets.py`; stored under `dashboard/assets/`.
