"""Plackett-Luce ranking simulation → contract probabilities.

Given per-driver strengths and DNF probabilities, we Monte-Carlo the finishing order using
the Gumbel-max trick (an exact Plackett-Luce sampler) with independent DNF draws, then read
off win/podium/points/DNF and pairwise head-to-head probabilities. Seeded for determinism.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel

PODIUM_CUTOFF = 3
POINTS_CUTOFF = 10


class RankingProbabilities(BaseModel):
    driver_ids: list[str]
    win: list[float]
    podium: list[float]
    points: list[float]
    dnf: list[float]
    # pairwise[i][j] = P(driver i finishes ahead of driver j)
    pairwise_ahead: list[list[float]]

    def as_dict(self) -> dict[str, dict[str, float]]:
        return {
            d: {
                "win": self.win[i],
                "podium": self.podium[i],
                "points": self.points[i],
                "dnf": self.dnf[i],
            }
            for i, d in enumerate(self.driver_ids)
        }

    def p_ahead(self, a: str, b: str) -> float:
        ia, ib = self.driver_ids.index(a), self.driver_ids.index(b)
        return self.pairwise_ahead[ia][ib]


def simulate(
    driver_ids: list[str],
    strengths: object,
    dnf_probs: object,
    *,
    n_sims: int = 4000,
    seed: int = 42,
) -> RankingProbabilities:
    """Simulate finishing orders and return contract probabilities.

    ``strengths`` are Plackett-Luce log-weights (theta); larger ⇒ stronger. ``dnf_probs`` are
    per-driver retirement probabilities in [0, 1].
    """
    theta = np.asarray(strengths, dtype=np.float64)
    dnf_p = np.clip(np.asarray(dnf_probs, dtype=np.float64), 0.0, 1.0)
    d = theta.shape[0]
    if d == 0:
        return RankingProbabilities(
            driver_ids=[], win=[], podium=[], points=[], dnf=[], pairwise_ahead=[]
        )

    rng = np.random.default_rng(seed)
    # Gumbel-max sampling of Plackett-Luce orderings.
    gumbel = -np.log(-np.log(rng.uniform(size=(n_sims, d))))
    scores = theta[None, :] + gumbel

    dnf_draw = rng.uniform(size=(n_sims, d)) < dnf_p[None, :]
    classified = ~dnf_draw
    # Retired cars sort to the back.
    eff = np.where(classified, scores, -np.inf)

    # positions: 0 = winner. argsort descending, then invert to get each driver's rank.
    order = np.argsort(-eff, axis=1, kind="stable")
    positions = np.empty((n_sims, d), dtype=np.int64)
    rows = np.arange(n_sims)[:, None]
    positions[rows, order] = np.arange(d)[None, :]

    win = np.mean(classified & (positions == 0), axis=0)
    podium = np.mean(classified & (positions < PODIUM_CUTOFF), axis=0)
    points = np.mean(classified & (positions < POINTS_CUTOFF), axis=0)
    dnf = np.mean(dnf_draw, axis=0)

    pairwise = _pairwise_ahead(positions, classified)

    return RankingProbabilities(
        driver_ids=list(driver_ids),
        win=[float(x) for x in win],
        podium=[float(x) for x in podium],
        points=[float(x) for x in points],
        dnf=[float(x) for x in dnf],
        pairwise_ahead=pairwise.tolist(),
    )


def _pairwise_ahead(
    positions: NDArray[np.int64], classified: NDArray[np.bool_]
) -> NDArray[np.float64]:
    """P(i ahead of j): i classified above j, or i classified while j retired."""
    d = positions.shape[1]
    ahead = np.zeros((d, d), dtype=np.float64)
    for i in range(d):
        pi = positions[:, i]
        ci = classified[:, i]
        for j in range(d):
            if i == j:
                continue
            pj = positions[:, j]
            cj = classified[:, j]
            i_beats_j = (ci & ~cj) | (ci & cj & (pi < pj))
            ahead[i, j] = float(np.mean(i_beats_j))
    return ahead
