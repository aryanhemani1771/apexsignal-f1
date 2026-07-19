"""Walk-forward evaluation of pre-race models on real historical races.

Downloads race classifications via FastF1 (cached; no credentials), evaluates each model
chronologically with validation-only calibration, writes a JSON report to
``artifacts/reports/``, and prints a summary. All metrics are measured here — nothing is
hard-coded.

    uv run --extra data python scripts/train_models.py --season 2022 --rounds 22
    uv run --extra data python scripts/train_models.py --season 2022 --season 2023
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from apexsignal.backtesting.baselines import GridModel, UniformModel
from apexsignal.backtesting.evaluation import ModelEvaluation, evaluate_model
from apexsignal.domain.contracts import RaceResult
from apexsignal.ingestion.fastf1_adapter import FastF1Adapter, FastF1NotInstalledError
from apexsignal.models.prerace import EloGridModel, EloModel, PreRaceConfig
from apexsignal.settings import load_settings

MODEL_FACTORIES = {
    "uniform": lambda cfg: UniformModel(cfg),
    "grid": lambda cfg: GridModel(cfg),
    "elo": lambda cfg: EloModel(cfg),
    "elo_grid": lambda cfg: EloGridModel(cfg),
}


def download_results(adapter: FastF1Adapter, seasons: list[int], rounds: int) -> list[RaceResult]:
    results: list[RaceResult] = []
    for season in seasons:
        for rnd in range(1, rounds + 1):
            try:
                res = adapter.load_session_result(season, rnd, "R")
            except Exception as exc:  # skip missing/failed rounds, keep going
                print(f"  skip {season} R{rnd}: {type(exc).__name__}")
                continue
            if res.entries:
                results.append(res)
                print(f"  loaded {season} R{rnd}: {len(res.entries)} entries")
    results.sort(key=lambda r: r.date)
    return results


def summarize(evaluations: dict[str, ModelEvaluation]) -> None:
    print("\n=== Winner-contract Brier / log-loss (test set, raw → calibrated) ===")
    print(f"{'model':<10} {'brier_raw':>10} {'brier_cal':>10} {'logloss_cal':>12} {'calib':>10}")
    for name, ev in evaluations.items():
        win = ev.contracts.get("win")
        if win is None:
            continue
        print(
            f"{name:<10} {win.raw.brier:>10.4f} {win.calibrated.brier:>10.4f} "
            f"{win.calibrated.log_loss:>12.4f} {win.calibration_method:>10}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward model evaluation")
    parser.add_argument("--season", type=int, action="append", dest="seasons", required=True)
    parser.add_argument("--rounds", type=int, default=22, help="rounds per season to try")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    settings = load_settings()
    try:
        adapter = FastF1Adapter(cache_dir=settings.fastf1_cache_dir)
    except FastF1NotInstalledError as exc:
        print(f"[error] {exc}")
        return 1

    print(f"Downloading results for seasons {args.seasons} (up to {args.rounds} rounds each)...")
    results = download_results(adapter, args.seasons, args.rounds)
    if len(results) < 6:
        print(f"[error] only {len(results)} races available; need at least 6 to evaluate.")
        return 1
    print(f"\nEvaluating on {len(results)} races.")

    cfg = PreRaceConfig(n_sims=settings.simulation_paths, seed=settings.random_seed)
    evaluations = {
        name: evaluate_model(results, lambda factory=factory: factory(cfg))
        for name, factory in MODEL_FACTORIES.items()
    }
    summarize(evaluations)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "seasons": args.seasons,
        "n_races": len(results),
        "simulation_paths": cfg.n_sims,
        "models": {name: ev.model_dump() for name, ev in evaluations.items()},
    }
    out = Path(args.out or "artifacts/reports/evaluation_latest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
