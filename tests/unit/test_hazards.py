"""Hazard and component models: DNF, safety car, pit, overtake, tyres."""

from __future__ import annotations

from apexsignal.models.dnf_hazard import DNFHazardModel
from apexsignal.models.overtake import OvertakeModel
from apexsignal.models.pit_hazard import PitHazardModel
from apexsignal.models.safety_car_hazard import SafetyCarHazardModel
from apexsignal.models.tyres import TyreModel


def test_dnf_hazard_matches_survival() -> None:
    m = DNFHazardModel()
    q, n = 0.2, 10
    h = m.per_lap_hazard(q, n)
    # (1-h)^n should reproduce the race survival probability.
    assert abs((1 - h) ** n - (1 - q)) < 1e-9
    assert m.lap_hazard(q, n, is_first_racing_lap=True) > h


def test_safety_car_elevated_early() -> None:
    m = SafetyCarHazardModel()
    assert m.per_lap_prob(0) > m.per_lap_prob(20)
    assert m.per_lap_prob(20, circuit_multiplier=2.0) > m.per_lap_prob(20)


def test_pit_hazard_rises_past_target_and_late_race() -> None:
    m = PitHazardModel()
    fresh = m.per_lap_prob("medium", 5, laps_remaining=40)
    worn = m.per_lap_prob("medium", 30, laps_remaining=40)
    assert worn > fresh
    # No stop made and running out of laps ⇒ forced pit propensity.
    assert m.per_lap_prob("hard", 30, laps_remaining=1, mandatory_stop_pending=True) > 0
    assert m.per_lap_prob("hard", 30, laps_remaining=1, mandatory_stop_pending=False) == 0.0
    # Safety car raises the propensity.
    assert m.per_lap_prob("medium", 20, laps_remaining=30, under_safety_car=True) > m.per_lap_prob(
        "medium", 20, laps_remaining=30
    )


def test_overtake_monotone_in_pace() -> None:
    m = OvertakeModel()
    assert m.pass_probability(1.0) > m.pass_probability(0.0) > m.pass_probability(-1.0)
    assert m.pass_probability(0.5, circuit_ease=1.5) > m.pass_probability(0.5, circuit_ease=0.5)


def test_tyre_pace_and_fit() -> None:
    m = TyreModel()
    assert m.tyre_pace("soft", 10) > m.tyre_pace("soft", 0)
    before = m.deg_per_lap("medium")
    ages = list(range(1, 12))
    # Strong linear degradation of 0.1 s/lap should pull the slope up from the prior.
    lap_times = [90.0 + 0.1 * a for a in ages]
    m.fit_from_laps("medium", ages, lap_times)
    assert m.deg_per_lap("medium") > before
