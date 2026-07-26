"""Predict the 2026 Hungarian Grand Prix using today's real qualifying grid.

Trains driver/constructor Elo ratings on every completed real race (2022 through 2026
round 10), then prices win/podium/points for tomorrow's race with the EloGridModel,
blending current-season form with the actual qualifying classification pulled from
FastF1 (no hardcoded results — everything is real, downloaded data).

    .venv/bin/python scripts/predict_hungary_2026.py
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apexsignal.domain.contracts import DriverEntry, RaceResult  # noqa: E402
from apexsignal.ingestion.fastf1_adapter import FastF1Adapter  # noqa: E402
from apexsignal.models.prerace import EloGridModel, PreRaceConfig  # noqa: E402

SEASONS = [2022, 2023, 2024, 2025, 2026]
HUNGARY_ROUND = 11  # 2026 round 11; rounds 1-10 are completed
OUT = Path("artifacts/reports/hungary_2026_prediction.json")


def main() -> int:
    adapter = FastF1Adapter()  # default gitignored cache (.cache/fastf1)

    results: list[RaceResult] = []
    for season in SEASONS:
        last = HUNGARY_ROUND - 1 if season == 2026 else 24
        for rnd in range(1, last + 1):
            try:
                res = adapter.load_session_result(season, rnd, "R")
            except Exception:
                continue
            if res.entries and res.winner() is not None:
                results.append(res)
                print(f"loaded {season} round {rnd} ({len(res.entries)} drivers)", flush=True)
    results.sort(key=lambda r: r.date)
    print(f"TRAINED_ON {len(results)} races", flush=True)

    model = EloGridModel(PreRaceConfig(n_sims=20000, seed=42))
    for r in results:
        model.update(r)

    # Real qualifying classification for the 2026 Hungarian GP (today's session).
    quali = adapter.load_session_result(2026, HUNGARY_ROUND, "Q")
    grid_entries = []
    quali_order = sorted(
        [e for e in quali.entries if e.finish_position is not None],
        key=lambda e: e.finish_position,
    )
    for e in quali_order:
        grid_entries.append(
            DriverEntry(
                driver_id=e.driver_id,
                constructor_id=e.constructor_id,
                grid=e.finish_position,
            )
        )
    print("GRID " + ", ".join(f"P{e.grid} {e.driver_id}" for e in grid_entries), flush=True)

    card = RaceResult(
        meeting_id="2026-11",
        session_id="2026-11-R-forecast",
        date=datetime.now(UTC),
        entries=grid_entries,
    )
    pred = model.predict(card)
    ranked = sorted(pred.drivers.values(), key=lambda p: -p.win)
    grid_of = {e.driver_id: e.grid for e in grid_entries}
    team_of = {e.driver_id: e.constructor_id for e in grid_entries}

    report = {
        "race": "2026 Hungarian Grand Prix",
        "race_date": "2026-07-26",
        "generated_at": datetime.now(UTC).isoformat(),
        "trained_on_races": len(results),
        "method": (
            "EloGridModel: Elo driver+constructor form trained on all completed races "
            "2022-2026 r10, blended with the real qualifying grid (FastF1), "
            "20k Monte Carlo sims"
        ),
        "grid_source": "FastF1 2026 round 11 qualifying classification (real data)",
        "drivers": [
            {
                "driver": p.driver_id,
                "constructor": team_of.get(p.driver_id, ""),
                "grid": grid_of.get(p.driver_id),
                "win": round(p.win, 4),
                "podium": round(p.podium, 4),
                "points": round(p.points, 4),
            }
            for p in ranked
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    print("FORECAST")
    for d in report["drivers"]:
        print(
            f"  P{d['grid']:<3}{d['driver']:<5} win {d['win']:6.1%}  "
            f"podium {d['podium']:6.1%}  points {d['points']:6.1%}",
            flush=True,
        )
    print(f"WROTE {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
