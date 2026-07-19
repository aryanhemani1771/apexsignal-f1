"""Pit-stop hazard model.

Per-lap probability a driver pits, driven by how far their current tyre age is past a
compound-dependent target stint length, whether a mandatory second compound is still needed,
and how many laps remain. A logistic ramp around the target keeps it smooth. Safety cars raise
the propensity to pit (cheap stop) — the simulator passes that context in.
"""

from __future__ import annotations

from pydantic import BaseModel

# Rough target stint length (laps) before a stop becomes likely, by compound.
TARGET_STINT = {"soft": 16, "medium": 24, "hard": 32, "intermediate": 20, "wet": 18}
_DEFAULT_TARGET = 24


class PitHazardConfig(BaseModel):
    steepness: float = 0.25  # logistic slope around the target stint length
    base_max: float = 0.6  # cap on per-lap pit prob from tyre wear alone
    safety_car_bonus: float = 0.35  # added propensity under safety car
    min_laps_left_to_pit: int = 2  # do not model a stop in the last couple of laps


class PitHazardModel:
    def __init__(self, config: PitHazardConfig | None = None) -> None:
        self.config = config or PitHazardConfig()

    def per_lap_prob(
        self,
        compound: str | None,
        tyre_age: int,
        laps_remaining: int,
        *,
        pit_stops_made: int = 0,
        under_safety_car: bool = False,
        mandatory_stop_pending: bool = False,
    ) -> float:
        cfg = self.config
        if laps_remaining <= cfg.min_laps_left_to_pit:
            # Only pit this late if a mandatory stop is still outstanding.
            return 0.5 if mandatory_stop_pending else 0.0

        target = TARGET_STINT.get((compound or "").lower(), _DEFAULT_TARGET)
        # Logistic in (age - target): near/after target ⇒ higher pit probability.
        x = cfg.steepness * (tyre_age - target)
        wear_prob = cfg.base_max / (1.0 + pow(2.718281828, -x))

        prob = wear_prob
        if under_safety_car:
            prob = min(1.0, prob + cfg.safety_car_bonus)
        if mandatory_stop_pending and laps_remaining < target:
            # Running out of race with no stop made yet — force the issue.
            prob = max(prob, 0.4)
        return float(min(1.0, prob))
