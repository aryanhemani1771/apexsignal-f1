"""Overtake probability model.

Pairwise probability that a following car completes a pass on the car ahead over one lap,
as a logistic function of the pace advantage (seconds/lap), scaled by how hard the circuit is
to overtake at. The Monte Carlo engine also captures track position through a dirty-air
penalty; this model is used for scenario analysis, explainability, and the "positions gained"
family of contracts.
"""

from __future__ import annotations

from pydantic import BaseModel

# 1.0 = neutral; >1 easier to pass (e.g. long DRS straights), <1 harder (street circuits).
DEFAULT_OVERTAKE_EASE = 1.0


class OvertakeConfig(BaseModel):
    pace_sensitivity: float = 1.6  # logistic slope per second/lap of advantage
    base_pass_logit: float = -1.4  # baseline difficulty when pace is equal
    max_prob: float = 0.95


class OvertakeModel:
    def __init__(self, config: OvertakeConfig | None = None) -> None:
        self.config = config or OvertakeConfig()

    def pass_probability(
        self, pace_advantage_s: float, *, circuit_ease: float = DEFAULT_OVERTAKE_EASE
    ) -> float:
        """P(following car passes over one lap). ``pace_advantage_s`` > 0 favours the pass."""
        cfg = self.config
        logit = cfg.base_pass_logit + cfg.pace_sensitivity * pace_advantage_s
        prob = 1.0 / (1.0 + pow(2.718281828, -logit))
        prob *= max(0.0, circuit_ease)
        return float(min(cfg.max_prob, max(0.0, prob)))
