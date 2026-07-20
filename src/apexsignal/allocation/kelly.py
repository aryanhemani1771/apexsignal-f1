"""Fractional Kelly sizing.

For a Yes contract bought at effective price ``a`` with (conservative) win probability ``p``
and payout normalised to 1, the full-Kelly fraction of bankroll is ``(p - a) / (1 - a)`` when
``p > a``, else 0. Only a fraction of full Kelly is ever used (0.10 / 0.20 / 0.25).
"""

from __future__ import annotations


def full_kelly_fraction(prob: float, effective_price: float) -> float:
    """Full-Kelly bankroll fraction for a favourable Yes bet, else 0."""
    if prob <= effective_price or effective_price >= 1.0:
        return 0.0
    return (prob - effective_price) / (1.0 - effective_price)


def fractional_kelly_stake(
    prob: float, effective_price: float, *, kelly_fraction: float, bankroll: float
) -> float:
    """Recommended stake (currency) at a fraction of full Kelly. Never negative."""
    full = full_kelly_fraction(prob, effective_price)
    return max(0.0, full * min(kelly_fraction, 0.25) * bankroll)
