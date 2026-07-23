"""Predict the next F1 race from current-season form.

Trains the driver/constructor ratings on every available real race (2022-present), then
produces a pre-race win/podium/points forecast for the current grid, based on form (no grid
position, since the upcoming race hasn't qualified yet). Saves a JSON the dashboard reads, so
the "Next race" prediction is available offline without any live data.

    uv run --extra data python scripts/predict_next.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from apexsignal.domain.contracts import DriverEntry, RaceResult
from apexsignal.ingestion.fastf1_adapter import FastF1Adapter, FastF1NotInstalledError
from apexsignal.models.prerace import EloModel, PreRaceConfig
from apexsignal.settings import load_settings

SEASONS = [2022, 2023, 2024, 2025, 2026]
NEXT_RACE = "2026 Hungarian Grand Prix"
NEXT_DATE = "2026-07-26"
OUT = Path("artifacts/reports/next_race_prediction.json")


def _download(adapter: FastF1Adapter) -> list[RaceResult]:
    out: list[RaceResult] = []
    for season in SEASONS:
        for rnd in range(1, 25):
            try:
                res = adapter.load_session_result(season, rnd, "R")
            except Exception:
                continue
            if res.entries and res.winner() is not None:
                out.append(res)
    out.sort(key=lambda r: r.date)
    return out


def main() -> int:
    settings = load_settings()
    try:
        adapter = FastF1Adapter(cache_dir=settings.fastf1_cache_dir)
    except FastF1NotInstalledError as exc:
        print(f"[error] {exc}")
        return 1

    print(f"Training on real races {SEASONS}...")
    results = _download(adapter)
    print(f"Trained on {len(results)} real races. Predicting {NEXT_RACE}.")

    model = EloModel(PreRaceConfig(n_sims=8000, seed=42))
    for r in results:
        model.update(r)

    # Current grid = the most recent race's entry list; predict from form (grid unknown).
    latest = results[-1]
    constructor = {e.driver_id: e.constructor_id for e in latest.entries}
    card = RaceResult(
        meeting_id="next",
        session_id="next-R",
        date=datetime.now(UTC),
        entries=[
            DriverEntry(driver_id=e.driver_id, constructor_id=e.constructor_id)
            for e in latest.entries
        ],
    )
    pred = model.predict(card)
    ranked = sorted(pred.drivers.values(), key=lambda p: -p.win)

    report = {
        "race": NEXT_RACE,
        "date": NEXT_DATE,
        "generated_at": datetime.now(UTC).isoformat(),
        "trained_on_races": len(results),
        "method": "form-based (Elo ratings + Plackett-Luce); pre-qualifying, no grid",
        "drivers": [
            {
                "driver": p.driver_id,
                "constructor": constructor.get(p.driver_id) or "",
                "win": round(p.win, 4),
                "podium": round(p.podium, 4),
                "points": round(p.points, 4),
            }
            for p in ranked
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    print(f"\nTop picks for {NEXT_RACE}:")
    for d in report["drivers"][:5]:
        print(f"  {d['driver']:<5} win {d['win']:.0%}  podium {d['podium']:.0%}")
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
