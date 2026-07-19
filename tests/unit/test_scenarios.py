"""Scenario engine."""

from __future__ import annotations

from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.scenarios import Scenario, compare_scenario

D = 10


def _sim_input() -> SimInput:
    return SimInput(
        driver_ids=[f"D{i}" for i in range(D)],
        total_laps=40,
        current_lap=15,
        clean_air_pace=[90.0 + i * 0.2 for i in range(D)],
        tyre_compound=["medium"] * D,
        tyre_age=[8] * D,
        pit_count=[0] * D,
        gap_to_leader=[i * 1.5 for i in range(D)],
        retired=[False] * D,
        race_dnf_prob=[0.05] * D,
    )


def test_pace_penalty_reduces_leader_win() -> None:
    simulator = RaceSimulator(SimConfig(n_paths=1500, seed=5))
    scenario = Scenario(name="D0 loses 1s/lap", driver_pace_delta_s={"D0": 1.0})
    cmp = compare_scenario(simulator, _sim_input(), scenario)
    assert cmp.win_delta["D0"] < 0  # slower leader wins less


def test_elevated_safety_car_raises_probability() -> None:
    simulator = RaceSimulator(SimConfig(n_paths=1500, seed=5))
    scenario = Scenario(name="chaos", sc_multiplier=3.0)
    cmp = compare_scenario(simulator, _sim_input(), scenario)
    assert cmp.safety_car_delta > 0


def test_penalty_seconds_demotes_driver() -> None:
    simulator = RaceSimulator(SimConfig(n_paths=1500, seed=8))
    scenario = Scenario(name="5s penalty D0", driver_penalty_s={"D0": 30.0})
    cmp = compare_scenario(simulator, _sim_input(), scenario)
    assert cmp.win_delta["D0"] < 0
