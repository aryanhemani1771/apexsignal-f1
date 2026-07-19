"""Safety-car hazard model.

Per-lap probability that a safety car (or virtual safety car) is deployed. A transparent
baseline: a circuit-agnostic base rate, elevated in the opening laps and scaled by a
per-circuit multiplier when one is supplied. Historical fitting refines the base rate later.
"""

from __future__ import annotations

from pydantic import BaseModel


class SafetyCarConfig(BaseModel):
    base_per_lap: float = 0.018  # ~1-in-55 laps baseline
    early_race_laps: int = 3
    early_multiplier: float = 2.5
    max_per_lap: float = 0.25


class SafetyCarHazardModel:
    def __init__(self, config: SafetyCarConfig | None = None) -> None:
        self.config = config or SafetyCarConfig()

    def per_lap_prob(self, laps_into_race: int, *, circuit_multiplier: float = 1.0) -> float:
        cfg = self.config
        p = cfg.base_per_lap * max(0.0, circuit_multiplier)
        if laps_into_race < cfg.early_race_laps:
            p *= cfg.early_multiplier
        return min(cfg.max_per_lap, p)
