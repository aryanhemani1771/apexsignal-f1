"""Walk-forward evaluation on a synthetic season with known driver strengths."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from apexsignal.backtesting.baselines import UniformModel
from apexsignal.backtesting.evaluation import evaluate_model
from apexsignal.domain.contracts import DriverEntry, RaceResult
from apexsignal.models.prerace import EloModel, PreRaceConfig

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def make_season(
    n_races: int, strengths: dict[str, float], *, dnf_rate: float = 0.06, seed: int = 0
) -> list[RaceResult]:
    rng = np.random.default_rng(seed)
    drivers = list(strengths)
    theta = np.array([strengths[d] for d in drivers], dtype=float)
    out: list[RaceResult] = []
    for r in range(n_races):
        gq = -np.log(-np.log(rng.uniform(size=len(drivers))))
        grid_order = np.argsort(-(theta + gq))
        grid_pos = {drivers[i]: pos + 1 for pos, i in enumerate(grid_order)}

        gr = -np.log(-np.log(rng.uniform(size=len(drivers))))
        race_order = np.argsort(-(theta + gr))
        dnf_mask = rng.uniform(size=len(drivers)) < dnf_rate
        classified = [drivers[i] for i in race_order if not dnf_mask[i]]
        finish_pos = {d: i + 1 for i, d in enumerate(classified)}

        entries = [
            DriverEntry(
                driver_id=d,
                constructor_id=f"t_{d}",
                grid=grid_pos[d],
                finish_position=None if dnf_mask[i] else finish_pos[d],
                dnf=bool(dnf_mask[i]),
                classified=not bool(dnf_mask[i]),
            )
            for i, d in enumerate(drivers)
        ]
        out.append(
            RaceResult(
                meeting_id=f"m{r}",
                session_id=f"m{r}-R",
                date=T0 + timedelta(days=r),
                entries=entries,
            )
        )
    return out


STRENGTHS = {f"D{i}": (10 - i) * 0.6 for i in range(10)}
CFG = PreRaceConfig(n_sims=800, seed=11)


def test_elo_beats_uniform_on_winner_brier() -> None:
    season = make_season(45, STRENGTHS, seed=1)
    elo = evaluate_model(season, lambda: EloModel(CFG))
    uni = evaluate_model(season, lambda: UniformModel(CFG))
    assert elo.contracts["win"].raw.brier < uni.contracts["win"].raw.brier
    assert elo.contracts["podium"].raw.brier < uni.contracts["podium"].raw.brier


def test_evaluation_reports_all_contracts() -> None:
    season = make_season(30, STRENGTHS, seed=2)
    ev = evaluate_model(season, lambda: EloModel(CFG))
    assert set(ev.contracts) == {"win", "podium", "points", "dnf"}
    for ce in ev.contracts.values():
        assert ce.raw.n > 0
        assert ce.calibration_method in {"identity", "platt", "isotonic"}


def test_calibration_does_not_worsen_validation_choice() -> None:
    season = make_season(40, STRENGTHS, seed=3)
    ev = evaluate_model(season, lambda: EloModel(CFG))
    # The chosen calibrator is the argmin of validation log loss (by construction).
    win = ev.contracts["win"]
    if win.validation_log_loss:
        assert win.validation_log_loss[win.calibration_method] == min(
            win.validation_log_loss.values()
        )
