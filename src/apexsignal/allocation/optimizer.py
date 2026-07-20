"""Correlation-aware, constrained allocation from ranked opportunities.

A transparent greedy allocator: size each opportunity by fractional Kelly on its conservative
probability, then clip to the per-market, total-deployment, per-driver, and correlated-cluster
caps (contracts on the same driver form a cluster — they are correlated). Integer contract
quantities. Portfolio risk (VaR / expected shortfall) is read from the simulation payoff paths,
so correlations are captured exactly. The allocator can return no positions.
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel

from apexsignal.allocation.constraints import RiskLimits, RiskTolerance
from apexsignal.allocation.kelly import full_kelly_fraction
from apexsignal.allocation.stress_tests import (
    expected_shortfall,
    portfolio_pnl_paths,
    value_at_risk,
)
from apexsignal.domain.markets import ContractType
from apexsignal.services.opportunity_service import Opportunity
from apexsignal.simulation.engine import SimulationResult
from apexsignal.simulation.payoff_matrix import build_payoff_matrix

NO_ALLOCATION = "No qualifying opportunity clears the risk, liquidity, and edge thresholds."


class AllocationPosition(BaseModel):
    market_id: str
    driver_id: str | None
    contract_type: ContractType
    cluster: str
    effective_price: float
    model_probability: float
    conservative_probability: float
    conservative_edge: float
    stake: float
    contracts: int
    max_loss: float
    expected_value: float
    rationale: str
    risk: str


class PortfolioRisk(BaseModel):
    total_stake: float
    cash_retained: float
    total_max_loss: float
    expected_portfolio_value: float
    var_95: float
    expected_shortfall_95: float
    largest_driver_exposure: float
    largest_cluster_exposure: float


class Allocation(BaseModel):
    bankroll: float
    tolerance: RiskTolerance
    positions: list[AllocationPosition]
    risk: PortfolioRisk
    message: str


def _cluster(opp: Opportunity) -> str:
    return opp.driver_id or "race"


def allocate(
    opportunities: list[Opportunity],
    result: SimulationResult,
    *,
    bankroll: float,
    tolerance: RiskTolerance,
    limits: RiskLimits | None = None,
    max_deployment_override: float | None = None,
) -> Allocation:
    limits = limits or RiskLimits()
    caps = limits.exposure
    kelly_frac = limits.kelly(tolerance)

    max_total = bankroll * (
        max_deployment_override
        if max_deployment_override is not None
        else caps.max_total_deployment
    )
    per_market_cap = bankroll * caps.max_per_market
    driver_cap = bankroll * caps.max_driver_exposure
    cluster_cap = bankroll * caps.max_correlated_cluster_exposure

    ranked = sorted(opportunities, key=lambda o: o.score, reverse=True)
    positions: list[AllocationPosition] = []
    total_stake = 0.0
    driver_used: dict[str, float] = {}
    cluster_used: dict[str, float] = {}

    for opp in ranked:
        full = full_kelly_fraction(opp.conservative_probability, opp.effective_ask)
        if full <= 0.0:
            continue
        cluster = _cluster(opp)
        driver_key = opp.driver_id or "race"

        target = full * kelly_frac * bankroll
        target = min(
            target,
            per_market_cap,
            max_total - total_stake,
            driver_cap - driver_used.get(driver_key, 0.0),
            cluster_cap - cluster_used.get(cluster, 0.0),
            opp.liquidity * opp.effective_ask,  # cannot exceed available depth
        )
        if target <= 0 or opp.effective_ask <= 0:
            continue
        contracts = math.floor(target / opp.effective_ask)
        if contracts <= 0:
            continue

        stake = contracts * opp.effective_ask
        positions.append(
            AllocationPosition(
                market_id=opp.market_id,
                driver_id=opp.driver_id,
                contract_type=opp.contract_type,
                cluster=cluster,
                effective_price=opp.effective_ask,
                model_probability=opp.model_probability,
                conservative_probability=opp.conservative_probability,
                conservative_edge=opp.conservative_edge,
                stake=stake,
                contracts=contracts,
                max_loss=stake,
                expected_value=contracts * (opp.model_probability - opp.effective_ask),
                rationale=opp.rationale,
                risk=opp.risk,
            )
        )
        total_stake += stake
        driver_used[driver_key] = driver_used.get(driver_key, 0.0) + stake
        cluster_used[cluster] = cluster_used.get(cluster, 0.0) + stake

    risk = _portfolio_risk(positions, result, bankroll, total_stake, driver_used, cluster_used)
    return Allocation(
        bankroll=bankroll,
        tolerance=tolerance,
        positions=positions,
        risk=risk,
        message=NO_ALLOCATION if not positions else f"{len(positions)} simulated position(s).",
    )


def _portfolio_risk(
    positions: list[AllocationPosition],
    result: SimulationResult,
    bankroll: float,
    total_stake: float,
    driver_used: dict[str, float],
    cluster_used: dict[str, float],
) -> PortfolioRisk:
    cash_retained = bankroll - total_stake
    if not positions:
        return PortfolioRisk(
            total_stake=0.0,
            cash_retained=bankroll,
            total_max_loss=0.0,
            expected_portfolio_value=bankroll,
            var_95=0.0,
            expected_shortfall_95=0.0,
            largest_driver_exposure=0.0,
            largest_cluster_exposure=0.0,
        )

    selections = [(p.contract_type, p.driver_id) for p in positions]
    payoff = build_payoff_matrix(result, selections)
    contracts = np.array([p.contracts for p in positions], dtype=np.float64)
    prices = np.array([p.effective_price for p in positions], dtype=np.float64)
    pnl = portfolio_pnl_paths(payoff, contracts, prices)

    expected_holdings = float(sum(p.contracts * p.model_probability for p in positions))
    return PortfolioRisk(
        total_stake=total_stake,
        cash_retained=cash_retained,
        total_max_loss=sum(p.max_loss for p in positions),
        expected_portfolio_value=cash_retained + expected_holdings,
        var_95=value_at_risk(pnl),
        expected_shortfall_95=expected_shortfall(pnl),
        largest_driver_exposure=max(driver_used.values(), default=0.0),
        largest_cluster_exposure=max(cluster_used.values(), default=0.0),
    )
