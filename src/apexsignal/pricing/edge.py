"""Edge and conservative-value calculations.

For a Yes contract bought at effective price ``a`` with model probability ``p`` and payout
normalised to 1, expected profit per contract is ``p - a``. The **conservative** probability
subtracts a Monte Carlo standard-error haircut so recommendations never rely on the raw point
estimate.
"""

from __future__ import annotations

import math


def monte_carlo_se(prob: float, n_paths: int) -> float:
    """Standard error of a Monte Carlo probability estimate."""
    p = min(max(prob, 0.0), 1.0)
    if n_paths <= 0:
        return 0.0
    return math.sqrt(p * (1.0 - p) / n_paths)


def conservative_probability(prob: float, n_paths: int, *, haircut_sd: float = 1.0) -> float:
    """Lower-bound probability = point estimate minus a standard-error haircut."""
    return max(0.0, prob - haircut_sd * monte_carlo_se(prob, n_paths))


def raw_edge(model_prob: float, effective_ask: float) -> float:
    return model_prob - effective_ask


def conservative_edge(conservative_prob: float, effective_ask: float) -> float:
    return conservative_prob - effective_ask


def expected_value(prob: float, effective_ask: float) -> float:
    """Expected profit per contract (payout normalised to 1)."""
    return prob - effective_ask
