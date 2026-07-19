"""Baseline pre-race models the main model must beat.

* ``UniformModel`` — every driver equally likely (a sanity floor).
* ``GridModel`` — strength purely from starting grid position.

Both are stateless (``update`` is a no-op) and share the Plackett-Luce prediction helper with
the Elo models, so comparisons are apples-to-apples. A live current-position heuristic baseline
belongs to the in-race phase (Phase 3) and is not a pre-race predictor.
"""

from __future__ import annotations

from apexsignal.domain.contracts import RacePrediction, RaceResult
from apexsignal.models.prerace import PreRaceConfig, _median_grid, build_prediction


class UniformModel:
    name = "uniform"

    def __init__(self, config: PreRaceConfig | None = None) -> None:
        self.config = config or PreRaceConfig()

    def update(self, result: RaceResult) -> None:  # stateless
        return None

    def predict(self, result: RaceResult) -> RacePrediction:
        cfg = self.config
        driver_ids = [e.driver_id for e in result.entries]
        strengths = [0.0 for _ in driver_ids]
        dnf_probs = [cfg.baseline_dnf for _ in driver_ids]
        return build_prediction(
            result.meeting_id,
            result.session_id,
            driver_ids,
            strengths,
            dnf_probs,
            n_sims=cfg.n_sims,
            seed=cfg.seed,
        )


class GridModel:
    name = "grid"

    def __init__(self, config: PreRaceConfig | None = None) -> None:
        self.config = config or PreRaceConfig()

    def update(self, result: RaceResult) -> None:  # stateless
        return None

    def predict(self, result: RaceResult) -> RacePrediction:
        cfg = self.config
        driver_ids = [e.driver_id for e in result.entries]
        grids = [e.grid for e in result.entries]
        med = _median_grid(grids)
        strengths = [
            cfg.grid_weight * (med - e.grid) if e.grid is not None else 0.0 for e in result.entries
        ]
        dnf_probs = [cfg.baseline_dnf for _ in driver_ids]
        return build_prediction(
            result.meeting_id,
            result.session_id,
            driver_ids,
            strengths,
            dnf_probs,
            n_sims=cfg.n_sims,
            seed=cfg.seed,
        )
