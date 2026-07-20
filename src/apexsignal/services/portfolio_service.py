"""Bankroll → simulated allocation.

Prices the simulated race, scans the market (synthetic by default) for opportunities through the
mapping gate, then runs the correlation-aware allocator under the risk limits. Returns a
transparent simulated allocation or the explicit no-opportunity result.
"""

from __future__ import annotations

from apexsignal.allocation.constraints import RiskLimits, RiskTolerance, load_risk_limits
from apexsignal.allocation.optimizer import Allocation, allocate
from apexsignal.domain.markets import MarketDataAdapter
from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.simulation.engine import SimulationResult
from apexsignal.simulation.payoff_matrix import price_contracts


async def build_allocation(
    result: SimulationResult,
    *,
    bankroll: float,
    tolerance: RiskTolerance = RiskTolerance.CONSERVATIVE,
    adapter: MarketDataAdapter | None = None,
    limits: RiskLimits | None = None,
    max_deployment_override: float | None = None,
    synthetic_mispricing_seed: int = 7,
) -> Allocation:
    limits = limits or load_risk_limits()
    prices = price_contracts(result)
    if adapter is None:
        adapter = SyntheticMarketAdapter(
            prices,
            config=SyntheticMarketConfig(mispricing_sd=0.08, seed=synthetic_mispricing_seed),
        )

    scan = await scan_opportunities(
        adapter,
        prices,
        min_conservative_edge=limits.thresholds.min_conservative_edge,
        min_mapping_confidence=limits.thresholds.min_mapping_confidence,
        min_liquidity=limits.thresholds.min_liquidity,
    )
    return allocate(
        scan.opportunities,
        result,
        bankroll=bankroll,
        tolerance=tolerance,
        limits=limits,
        max_deployment_override=max_deployment_override,
    )
