"""Leakage guard for walk-forward evaluation.

Each race must be predicted using only information from strictly earlier races: the harness
must call ``predict`` before ``update`` for every race, in order.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apexsignal.backtesting.evaluation import collect_walk_forward
from apexsignal.domain.contracts import (
    DriverContractProbs,
    DriverEntry,
    RacePrediction,
    RaceResult,
)

pytestmark = pytest.mark.leakage

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _race(round_no: int) -> RaceResult:
    entries = [
        DriverEntry(driver_id="A", constructor_id="t", grid=1, finish_position=1),
        DriverEntry(driver_id="B", constructor_id="t", grid=2, finish_position=2),
    ]
    return RaceResult(
        meeting_id=f"m{round_no}",
        session_id=f"m{round_no}-R",
        date=T0 + timedelta(days=round_no),
        entries=entries,
    )


class RecordingModel:
    name = "recording"

    def __init__(self) -> None:
        self.updates_seen = 0
        self.updates_at_predict: list[int] = []

    def predict(self, result: RaceResult) -> RacePrediction:
        self.updates_at_predict.append(self.updates_seen)
        return RacePrediction(
            meeting_id=result.meeting_id,
            session_id=result.session_id,
            drivers={d: DriverContractProbs(driver_id=d) for d in result.drivers()},
        )

    def update(self, result: RaceResult) -> None:
        self.updates_seen += 1


def test_predict_precedes_update_for_every_race() -> None:
    season = [_race(i) for i in range(6)]
    model = RecordingModel()
    collect_walk_forward(season, model)
    # At race k, exactly k prior updates have happened — never a future one.
    assert model.updates_at_predict == list(range(6))
