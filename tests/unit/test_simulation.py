"""Monte Carlo race-continuation simulator and contract payoff matrix."""

from __future__ import annotations

import numpy as np

from apexsignal.models.dnf_hazard import DNFHazardConfig, DNFHazardModel
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import price_contracts

D = 12


def _sim_input(**overrides: object) -> SimInput:
    base: dict[str, object] = {
        "driver_ids": [f"D{i}" for i in range(D)],
        "total_laps": 40,
        "current_lap": 15,
        "clean_air_pace": [90.0 + i * 0.2 for i in range(D)],  # D0 fastest
        "tyre_compound": ["medium"] * D,
        "tyre_age": [8] * D,
        "pit_count": [0] * D,
        "gap_to_leader": [i * 1.5 for i in range(D)],
        "retired": [False] * D,
        "race_dnf_prob": [0.05] * D,
    }
    base.update(overrides)
    return SimInput(**base)  # type: ignore[arg-type]


def test_simulation_is_deterministic() -> None:
    sim = _sim_input()
    a = RaceSimulator(SimConfig(n_paths=1000, seed=7)).simulate(sim)
    b = RaceSimulator(SimConfig(n_paths=1000, seed=7)).simulate(sim)
    assert a.final_positions == b.final_positions
    assert a.safety_car_occurred == b.safety_car_occurred


def test_final_positions_are_permutations() -> None:
    result = RaceSimulator(SimConfig(n_paths=500, seed=1)).simulate(_sim_input())
    pos = result.positions_array()
    expected = set(range(1, D + 1))
    for row in pos:
        assert set(row.tolist()) == expected


def test_faster_driver_wins_more() -> None:
    result = RaceSimulator(SimConfig(n_paths=2000, seed=3)).simulate(_sim_input())
    prices = price_contracts(result)
    wins = prices.win_probs()
    assert wins["D0"] == max(wins.values())
    assert wins["D0"] > wins["D11"]


def test_retired_driver_never_classified() -> None:
    sim = _sim_input(retired=[i == 5 for i in range(D)])
    result = RaceSimulator(SimConfig(n_paths=500, seed=2)).simulate(sim)
    classified = result.classified_array()
    assert not classified[:, 5].any()
    prices = price_contracts(result)
    assert prices.drivers["D5"].win == 0.0
    assert prices.drivers["D5"].dnf == 1.0


def test_payoff_probabilities_valid() -> None:
    result = RaceSimulator(SimConfig(n_paths=2000, seed=4)).simulate(_sim_input())
    prices = price_contracts(result, gains_threshold=3, pit_before_lap=30)
    win_sum = sum(p.win for p in prices.drivers.values())
    assert abs(win_sum - 1.0) < 0.05  # ~one winner per path (tiny DNF chance)
    for p in prices.drivers.values():
        for v in (p.win, p.podium, p.points, p.dnf, p.fastest_lap, p.gains_positions):
            assert 0.0 <= v <= 1.0
        assert p.podium >= p.win - 1e-9
        assert p.pit_before_lap is not None
    assert 0.0 <= prices.safety_car <= 1.0


def test_pairwise_complementary_for_running_pair() -> None:
    # Truly zero DNF (floor disabled) ⇒ both cars always classified ⇒ p(A>B)+p(B>A)=1.
    sim = _sim_input(race_dnf_prob=[0.0] * D)
    no_dnf = DNFHazardModel(DNFHazardConfig(min_race_dnf=0.0))
    result = RaceSimulator(SimConfig(n_paths=1500, seed=6), dnf_model=no_dnf).simulate(sim)
    prices = price_contracts(result)
    assert abs(prices.p_ahead("D0", "D5") + prices.p_ahead("D5", "D0") - 1.0) < 1e-9
    assert np.isclose(prices.p_ahead("D0", "D0"), 0.0)
