"""Train on all-but-the-last-N real races, then predict the most recent N and compare.

Walk-forward and leak-free: each held-out race is predicted using only earlier races, then the
model is updated. Prints the model's win probabilities vs. the actual winner and a hit summary.

    uv run --extra data python scripts/predict_recent.py --season 2022 --season 2023 \
        --season 2024 --season 2025 --season 2026 --holdout 3
"""

from __future__ import annotations

import argparse

from apexsignal.domain.contracts import RaceResult
from apexsignal.ingestion.fastf1_adapter import FastF1Adapter, FastF1NotInstalledError
from apexsignal.models.prerace import EloGridModel, PreRaceConfig
from apexsignal.settings import load_settings


def _download(adapter: FastF1Adapter, seasons: list[int], rounds: int) -> list[RaceResult]:
    out: list[RaceResult] = []
    for season in seasons:
        for rnd in range(1, rounds + 1):
            try:
                res = adapter.load_session_result(season, rnd, "R")
            except Exception:  # skip rounds that don't exist / fail to load
                continue
            if res.entries and res.winner() is not None:
                out.append(res)
    out.sort(key=lambda r: r.date)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict the most recent races")
    parser.add_argument("--season", type=int, action="append", dest="seasons", required=True)
    parser.add_argument("--rounds", type=int, default=24)
    parser.add_argument("--holdout", type=int, default=3)
    args = parser.parse_args()

    settings = load_settings()
    try:
        adapter = FastF1Adapter(cache_dir=settings.fastf1_cache_dir)
    except FastF1NotInstalledError as exc:
        print(f"[error] {exc}")
        return 1

    print(f"Downloading seasons {args.seasons}...")
    results = _download(adapter, args.seasons, args.rounds)
    if len(results) <= args.holdout:
        print(f"[error] only {len(results)} races available.")
        return 1

    train, test = results[: -args.holdout], results[-args.holdout :]
    print(f"Trained on {len(train)} races; predicting the last {len(test)}.\n")

    model = EloGridModel(PreRaceConfig(n_sims=5000, seed=42))
    for r in train:
        model.update(r)

    hits_top1 = 0
    podium_hits = 0
    podium_total = 0
    for r in test:
        pred = model.predict(r)  # BEFORE seeing this race
        wins = sorted(pred.drivers.items(), key=lambda kv: -kv[1].win)
        actual_winner = r.winner()
        actual_podium = set(r.podium())
        top1 = wins[0][0]
        hits_top1 += int(top1 == actual_winner)
        model_podium = {d for d, _ in wins[:3]}
        podium_hits += len(model_podium & actual_podium)
        podium_total += 3

        print(f"{r.meeting_id}  ({r.date.date()})")
        print("  model top 5: " + ", ".join(f"{d} {p.win:.0%}" for d, p in wins[:5]))
        print(f"  ACTUAL: winner {actual_winner}, podium {r.podium()}")
        print(f"  model pick {top1} {'✓ CORRECT' if top1 == actual_winner else '✗'}\n")
        model.update(r)

    print(f"Winner hit rate: {hits_top1}/{len(test)}")
    print(f"Podium slots correctly in model top-3: {podium_hits}/{podium_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
