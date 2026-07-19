"""Pre-race models: turn ratings (and grid) into calibrated-shaped contract probabilities.

Every model exposes the same walk-forward interface:

* ``update(result)`` — learn from a completed race (stateless models no-op);
* ``predict(result)`` — read only the pre-race fields (driver, constructor, grid) of the
  entries and return a :class:`RacePrediction`. It must never read finishing positions.

The Elo models delegate the finishing-order distribution to the Plackett-Luce simulator.
Blend weights (grid vs. form) are fixed, documented priors — not tuned on the test set.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from apexsignal.domain.contracts import (
    DriverContractProbs,
    RacePrediction,
    RaceResult,
)
from apexsignal.models import ranking
from apexsignal.models.driver_ratings import DEFAULT_RATING, DriverRatings, RatingConfig


class PreRaceConfig(BaseModel):
    rating_to_theta: float = 90.0  # Elo points per Plackett-Luce theta unit
    grid_weight: float = 0.35  # theta per grid position of advantage (documented prior)
    baseline_dnf: float = 0.12  # per-driver DNF prior when no reliability estimate exists
    n_sims: int = 4000
    seed: int = 42


def build_prediction(
    meeting_id: str,
    session_id: str,
    driver_ids: list[str],
    strengths: list[float],
    dnf_probs: list[float],
    *,
    n_sims: int,
    seed: int,
) -> RacePrediction:
    """Run the ranking simulation and package a :class:`RacePrediction`."""
    result = ranking.simulate(driver_ids, strengths, dnf_probs, n_sims=n_sims, seed=seed)
    probs = result.as_dict()
    drivers = {
        d: DriverContractProbs(
            driver_id=d,
            win=probs[d]["win"],
            podium=probs[d]["podium"],
            points=probs[d]["points"],
            dnf=probs[d]["dnf"],
        )
        for d in driver_ids
    }
    return RacePrediction(meeting_id=meeting_id, session_id=session_id, drivers=drivers)


def _median_grid(grids: list[int | None]) -> float:
    known = [g for g in grids if g is not None]
    return float(np.median(known)) if known else 0.0


class EloModel:
    """Main model: Plackett-Luce over Elo strengths with constructor reliability for DNF."""

    name = "elo"

    def __init__(
        self, config: PreRaceConfig | None = None, rating_config: RatingConfig | None = None
    ) -> None:
        self.config = config or PreRaceConfig()
        self.ratings = DriverRatings(rating_config)
        self._use_grid = False

    def update(self, result: RaceResult) -> None:
        self.ratings.update(result)

    def predict(self, result: RaceResult) -> RacePrediction:
        cfg = self.config
        driver_ids = [e.driver_id for e in result.entries]
        grids = [e.grid for e in result.entries]
        med = _median_grid(grids)

        strengths: list[float] = []
        dnf_probs: list[float] = []
        for e in result.entries:
            rating = self.ratings.strength(e.driver_id, e.constructor_id)
            theta = (rating - DEFAULT_RATING) / cfg.rating_to_theta
            if self._use_grid and e.grid is not None:
                theta += cfg.grid_weight * (med - e.grid)
            strengths.append(theta)
            rate = self.ratings.dnf_rate(e.constructor_id)
            dnf_probs.append(rate if self.ratings.races_seen > 0 else cfg.baseline_dnf)

        return build_prediction(
            result.meeting_id,
            result.session_id,
            driver_ids,
            strengths,
            dnf_probs,
            n_sims=cfg.n_sims,
            seed=cfg.seed,
        )


class EloGridModel(EloModel):
    """Elo strengths blended with starting-grid position."""

    name = "elo_grid"

    def __init__(
        self, config: PreRaceConfig | None = None, rating_config: RatingConfig | None = None
    ) -> None:
        super().__init__(config, rating_config)
        self._use_grid = True
