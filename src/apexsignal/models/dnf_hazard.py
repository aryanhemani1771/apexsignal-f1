"""DNF (retirement) hazard model.

Converts a per-race retirement probability (e.g. from constructor reliability) into a
per-lap hazard, with an elevated hazard on the opening lap (first-lap incidents). Kept as a
transparent survival baseline; a covariate-driven survival model arrives with real fitting.
"""

from __future__ import annotations

from pydantic import BaseModel


class DNFHazardConfig(BaseModel):
    first_lap_multiplier: float = 6.0  # opening-lap incidents are far more likely
    min_race_dnf: float = 0.02
    max_race_dnf: float = 0.6


class DNFHazardModel:
    def __init__(self, config: DNFHazardConfig | None = None) -> None:
        self.config = config or DNFHazardConfig()

    def per_lap_hazard(self, race_dnf_prob: float, laps_remaining: int) -> float:
        """Constant per-lap hazard consistent with ``race_dnf_prob`` over the remaining laps."""
        cfg = self.config
        q = min(max(race_dnf_prob, cfg.min_race_dnf), cfg.max_race_dnf)
        n = max(1, laps_remaining)
        # Survival: (1-h)^n = 1-q  ⇒  h = 1 - (1-q)^(1/n)
        return float(1.0 - (1.0 - q) ** (1.0 / n))

    def lap_hazard(
        self, race_dnf_prob: float, laps_remaining: int, *, is_first_racing_lap: bool = False
    ) -> float:
        base = self.per_lap_hazard(race_dnf_prob, laps_remaining)
        if is_first_racing_lap:
            return min(1.0, base * self.config.first_lap_multiplier)
        return base
