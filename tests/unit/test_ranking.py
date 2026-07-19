"""Plackett-Luce ranking simulation."""

from __future__ import annotations

from apexsignal.models import ranking

DRIVERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]


def test_probabilities_in_range_and_sums() -> None:
    strengths = [1.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dnf = [0.0] * len(DRIVERS)
    r = ranking.simulate(DRIVERS, strengths, dnf, n_sims=3000, seed=7)
    assert all(0.0 <= p <= 1.0 for p in r.win)
    # No DNFs ⇒ exactly one winner, three podium spots, ten points spots per sim.
    assert abs(sum(r.win) - 1.0) < 1e-9
    assert abs(sum(r.podium) - 3.0) < 1e-9
    assert abs(sum(r.points) - 10.0) < 1e-9


def test_stronger_driver_wins_more() -> None:
    strengths = [2.0] + [0.0] * (len(DRIVERS) - 1)
    dnf = [0.0] * len(DRIVERS)
    r = ranking.simulate(DRIVERS, strengths, dnf, n_sims=3000, seed=1)
    probs = r.as_dict()
    assert probs["A"]["win"] == max(p["win"] for p in probs.values())
    assert probs["A"]["podium"] >= probs["A"]["win"] >= 0.0


def test_pairwise_complementary_without_dnf() -> None:
    strengths = [1.0, 0.3, -0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dnf = [0.0] * len(DRIVERS)
    r = ranking.simulate(DRIVERS, strengths, dnf, n_sims=2000, seed=5)
    assert abs(r.p_ahead("A", "B") + r.p_ahead("B", "A") - 1.0) < 1e-9
    assert r.p_ahead("A", "B") > 0.5  # stronger driver usually ahead


def test_deterministic_with_seed() -> None:
    strengths = [1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    dnf = [0.1] * len(DRIVERS)
    a = ranking.simulate(DRIVERS, strengths, dnf, n_sims=1000, seed=42)
    b = ranking.simulate(DRIVERS, strengths, dnf, n_sims=1000, seed=42)
    assert a.win == b.win
    assert a.dnf == b.dnf


def test_higher_dnf_prob_shows_up() -> None:
    strengths = [0.0] * len(DRIVERS)
    dnf = [0.5] + [0.05] * (len(DRIVERS) - 1)
    r = ranking.simulate(DRIVERS, strengths, dnf, n_sims=3000, seed=9)
    assert r.dnf[0] > 0.4
    assert r.dnf[1] < 0.15
