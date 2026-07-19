"""Latent clean-air pace estimation."""

from __future__ import annotations

from apexsignal.models.latent_pace import (
    LapRecord,
    LatentPaceFilter,
    estimate_clean_air_pace,
    fuel_effect,
)
from apexsignal.models.latent_pace import LatentPaceConfig as Cfg
from apexsignal.models.tyres import TyreModel

TYRES = TyreModel()
TOTAL = 57
CFG = Cfg()


def _synthetic_laps(base: float, compound: str, start_lap: int, n: int) -> list[LapRecord]:
    laps = []
    for k in range(n):
        lap = start_lap + k
        age = k + 1
        lt = base + TYRES.tyre_pace(compound, age) + fuel_effect(lap, TOTAL, CFG.fuel_gain_per_lap)
        laps.append(LapRecord(lap=lap, lap_time=lt, compound=compound, tyre_age=age))
    return laps


def test_estimate_recovers_base_pace() -> None:
    laps = _synthetic_laps(89.5, "medium", start_lap=10, n=12)
    est = estimate_clean_air_pace(laps, TYRES, TOTAL)
    assert abs(est - 89.5) < 0.1


def test_estimate_rejects_pit_outlier() -> None:
    laps = _synthetic_laps(89.5, "medium", start_lap=10, n=12)
    laps.append(LapRecord(lap=22, lap_time=115.0, compound="medium", tyre_age=13))  # pit lap
    est = estimate_clean_air_pace(laps, TYRES, TOTAL)
    assert abs(est - 89.5) < 0.3


def test_kalman_filter_converges() -> None:
    filt = LatentPaceFilter(TYRES, TOTAL)
    mean = 0.0
    for r in _synthetic_laps(90.0, "hard", start_lap=5, n=15):
        mean = filt.update(r)
    assert abs(mean - 90.0) < 0.3


def test_empty_returns_fallback() -> None:
    assert estimate_clean_air_pace([], TYRES, TOTAL, fallback=91.0) == 91.0
