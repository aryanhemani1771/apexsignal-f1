"""Portfolio stress metrics from the simulation payoff paths.

Given the allocated positions and the Monte Carlo payoff matrix, compute the P&L distribution
across paths and read off Value at Risk and Expected Shortfall. Correlation is captured
naturally because every contract's payoff is evaluated on the same simulated paths.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def portfolio_pnl_paths(
    payoff_matrix: NDArray[np.float64],
    contracts: NDArray[np.float64],
    effective_prices: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Per-path portfolio P&L: sum over positions of contracts * (payoff - price)."""
    if payoff_matrix.size == 0:
        return np.zeros(0)
    per_contract_pnl = payoff_matrix - effective_prices[None, :]
    pnl: NDArray[np.float64] = (per_contract_pnl * contracts[None, :]).sum(axis=1)
    return pnl


def value_at_risk(pnl: NDArray[np.float64], *, alpha: float = 0.95) -> float:
    """Loss magnitude not exceeded with probability ``alpha`` (>= 0)."""
    if pnl.size == 0:
        return 0.0
    q = float(np.quantile(pnl, 1.0 - alpha))
    return max(0.0, -q)


def expected_shortfall(pnl: NDArray[np.float64], *, alpha: float = 0.95) -> float:
    """Mean loss in the worst ``1 - alpha`` tail (>= 0)."""
    if pnl.size == 0:
        return 0.0
    threshold = float(np.quantile(pnl, 1.0 - alpha))
    tail = pnl[pnl <= threshold]
    if tail.size == 0:
        return max(0.0, -threshold)
    return max(0.0, -float(tail.mean()))
