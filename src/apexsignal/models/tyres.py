"""Tyre-degradation model.

A compound's lap-time contribution is modelled as ``grip_offset + deg_per_lap * age`` seconds
relative to a neutral reference. Priors are sensible defaults; ``fit_from_laps`` refines the
per-compound degradation slope by robust regression when enough clean laps are available
(pit-in/out, safety-car, and outlier laps must be excluded by the caller).
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel


class CompoundParams(BaseModel):
    grip_offset: float  # seconds vs. reference at age 0 (negative = faster)
    deg_per_lap: float  # seconds added per lap of age


# Defaults: softs start quickest but degrade fastest; wets/inters are far off dry pace.
DEFAULT_PRIORS: dict[str, CompoundParams] = {
    "soft": CompoundParams(grip_offset=-0.35, deg_per_lap=0.06),
    "medium": CompoundParams(grip_offset=0.0, deg_per_lap=0.045),
    "hard": CompoundParams(grip_offset=0.35, deg_per_lap=0.03),
    "intermediate": CompoundParams(grip_offset=2.5, deg_per_lap=0.05),
    "wet": CompoundParams(grip_offset=5.0, deg_per_lap=0.05),
}
_UNKNOWN = CompoundParams(grip_offset=0.0, deg_per_lap=0.045)


class TyreModel:
    def __init__(self, priors: dict[str, CompoundParams] | None = None) -> None:
        self.params = dict(priors or DEFAULT_PRIORS)

    def _get(self, compound: str | None) -> CompoundParams:
        if compound is None:
            return _UNKNOWN
        return self.params.get(compound.lower(), _UNKNOWN)

    def compound_params(self, compound: str | None) -> CompoundParams:
        """Public accessor for a compound's (grip_offset, deg_per_lap)."""
        return self._get(compound)

    def tyre_pace(self, compound: str | None, age: float) -> float:
        p = self._get(compound)
        return p.grip_offset + p.deg_per_lap * age

    def deg_per_lap(self, compound: str | None) -> float:
        return self._get(compound).deg_per_lap

    def fit_from_laps(
        self, compound: str, ages: object, lap_times: object, *, min_laps: int = 6
    ) -> None:
        """Refine a compound's degradation slope by robust (Theil-Sen-style) regression."""
        a = np.asarray(ages, dtype=np.float64)
        t = np.asarray(lap_times, dtype=np.float64)
        if a.size < min_laps or np.ptp(a) < 1.0:
            return
        # Median of pairwise slopes → robust to outliers, no heavy deps.
        slopes = []
        for i in range(a.size):
            for j in range(i + 1, a.size):
                if a[j] != a[i]:
                    slopes.append((t[j] - t[i]) / (a[j] - a[i]))
        if not slopes:
            return
        slope = float(np.median(slopes))
        key = compound.lower()
        prev = self.params.get(key, _UNKNOWN)
        # Keep degradation non-negative and blend with the prior for stability.
        blended = max(0.0, 0.5 * prev.deg_per_lap + 0.5 * slope)
        self.params[key] = CompoundParams(grip_offset=prev.grip_offset, deg_per_lap=blended)
