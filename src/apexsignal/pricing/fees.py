"""Fees and effective execution prices.

Effective price is what you actually pay/receive after fees and estimated slippage. Buying a
Yes contract costs ``best_ask + fee + slippage``; selling receives ``best_bid - fee - slippage``.
Kalshi's true fee is price-dependent — this flat baseline is a conservative placeholder and is
documented as such.
"""

from __future__ import annotations

from pydantic import BaseModel


class FeeConfig(BaseModel):
    taker_fee: float = 0.01  # per contract, in probability units
    default_slippage: float = 0.005


def effective_ask(best_ask: float, *, fee: float, slippage: float) -> float:
    """Cost to buy one Yes contract, after fees and slippage."""
    return min(1.0, best_ask + fee + slippage)


def effective_bid(best_bid: float, *, fee: float, slippage: float) -> float:
    """Proceeds from selling one Yes contract, after fees and slippage."""
    return max(0.0, best_bid - fee - slippage)
