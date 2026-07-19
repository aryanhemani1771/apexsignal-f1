"""Latent live-pace estimation.

Observed lap time is decomposed into a latent, fuel- and tyre-neutral "clean-air" pace plus
tyre degradation, fuel burn, and noise. Two estimators are provided:

* :func:`estimate_clean_air_pace` — a robust one-shot estimate from a driver's recent laps;
* :class:`LatentPaceFilter` — a 1-D Kalman filter (latent pace as a random walk) for streaming
  updates, the deterministic baseline the build spec calls for before a particle filter.

The simulator reconstructs a lap time as ``clean_air_pace + tyre_pace(compound, age) +
fuel_effect(lap) + noise`` — the inverse of what is removed here.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from apexsignal.models.tyres import TyreModel


class LatentPaceConfig(BaseModel):
    fuel_gain_per_lap: float = 0.055  # sec/lap the car gains as fuel burns off
    outlier_mad_z: float = 3.0  # reject laps beyond this many MADs
    process_var: float = 0.02  # Kalman random-walk variance on latent pace
    obs_var: float = 0.35  # Kalman observation (lap-to-lap) variance


class LapRecord(BaseModel):
    lap: int
    lap_time: float
    compound: str | None = None
    tyre_age: int = 0


def fuel_effect(lap: int, total_laps: int, gain_per_lap: float) -> float:
    """Seconds a lap is slowed by remaining fuel load (heavier early ⇒ slower)."""
    return gain_per_lap * max(0, total_laps - lap)


def _fresh_equivalents(
    laps: list[LapRecord], tyre_model: TyreModel, total_laps: int, cfg: LatentPaceConfig
) -> np.ndarray:
    vals = []
    for r in laps:
        if r.lap_time <= 0:
            continue
        neutral = (
            r.lap_time
            - tyre_model.tyre_pace(r.compound, r.tyre_age)
            - fuel_effect(r.lap, total_laps, cfg.fuel_gain_per_lap)
        )
        vals.append(neutral)
    return np.asarray(vals, dtype=np.float64)


def estimate_clean_air_pace(
    laps: list[LapRecord],
    tyre_model: TyreModel,
    total_laps: int,
    *,
    config: LatentPaceConfig | None = None,
    fallback: float = 90.0,
) -> float:
    """Robust fuel- and tyre-neutral pace from a driver's laps (outliers rejected by MAD)."""
    cfg = config or LatentPaceConfig()
    x = _fresh_equivalents(laps, tyre_model, total_laps, cfg)
    if x.size == 0:
        return fallback
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) or 1e-6
    keep = x[np.abs(x - med) <= cfg.outlier_mad_z * 1.4826 * mad]
    return float(np.median(keep)) if keep.size else med


class LatentPaceFilter:
    """1-D Kalman filter: latent clean-air pace as a random walk."""

    def __init__(
        self, tyre_model: TyreModel, total_laps: int, config: LatentPaceConfig | None = None
    ) -> None:
        self.tyre_model = tyre_model
        self.total_laps = total_laps
        self.cfg = config or LatentPaceConfig()
        self.mean: float | None = None
        self.var: float = 1.0

    def update(self, record: LapRecord) -> float:
        """Fold in one lap; returns the posterior mean clean-air pace."""
        obs = (
            record.lap_time
            - self.tyre_model.tyre_pace(record.compound, record.tyre_age)
            - fuel_effect(record.lap, self.total_laps, self.cfg.fuel_gain_per_lap)
        )
        if self.mean is None:
            self.mean = obs
            self.var = self.cfg.obs_var
            return self.mean
        # Predict (random walk) then correct.
        pred_var = self.var + self.cfg.process_var
        gain = pred_var / (pred_var + self.cfg.obs_var)
        self.mean = self.mean + gain * (obs - self.mean)
        self.var = (1.0 - gain) * pred_var
        return self.mean
