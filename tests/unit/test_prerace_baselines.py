"""Pre-race models and baselines."""

from __future__ import annotations

from datetime import UTC, datetime

from apexsignal.backtesting.baselines import GridModel, UniformModel
from apexsignal.domain.contracts import DriverEntry, RaceResult
from apexsignal.models.prerace import EloModel, PreRaceConfig

T0 = datetime(2024, 1, 1, tzinfo=UTC)
FIELD = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]


def _card(grid_order: list[str]) -> RaceResult:
    entries = [
        DriverEntry(driver_id=d, constructor_id=f"t_{d.lower()}", grid=i, finish_position=i)
        for i, d in enumerate(grid_order, start=1)
    ]
    return RaceResult(meeting_id="m", session_id="m-R", date=T0, entries=entries)


CFG = PreRaceConfig(n_sims=1500, seed=3)


def test_uniform_model_is_flat() -> None:
    pred = UniformModel(CFG).predict(_card(FIELD))
    wins = [p.win for p in pred.drivers.values()]
    assert max(wins) - min(wins) < 0.05  # roughly equal


def test_grid_model_favours_pole() -> None:
    pred = GridModel(CFG).predict(_card(FIELD))
    pole = pred.drivers["A"].win  # grid position 1
    back = pred.drivers["L"].win  # grid position 12
    assert pole > back
    assert pred.drivers["A"].win == max(p.win for p in pred.drivers.values())


def test_win_probabilities_sum_to_about_one() -> None:
    pred = GridModel(CFG).predict(_card(FIELD))
    total = sum(p.win for p in pred.drivers.values())
    assert 0.9 < total <= 1.0


def test_elo_model_predicts_and_updates() -> None:
    model = EloModel(CFG)
    card = _card(FIELD)
    pred = model.predict(card)
    assert set(pred.drivers) == set(FIELD)
    assert all(0.0 <= p.win <= 1.0 for p in pred.drivers.values())
    model.update(card)
    assert model.ratings.races_seen == 1
