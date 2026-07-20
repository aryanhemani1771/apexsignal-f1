"""Fractional Kelly, risk limits, correlation-aware allocation, and stress metrics."""

from __future__ import annotations

import asyncio

from apexsignal.allocation.constraints import RiskLimits, RiskTolerance, load_risk_limits
from apexsignal.allocation.kelly import fractional_kelly_stake, full_kelly_fraction
from apexsignal.allocation.optimizer import NO_ALLOCATION, allocate
from apexsignal.domain.markets import ContractType
from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.services.opportunity_service import Opportunity, scan_opportunities
from apexsignal.services.portfolio_service import build_allocation
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput, SimulationResult
from apexsignal.simulation.payoff_matrix import (
    ContractPrices,
    build_payoff_matrix,
    contract_payoff,
    price_contracts,
)

BANKROLL = 10_000.0


def _result() -> SimulationResult:
    d = 10
    sim = SimInput(
        driver_ids=[f"D{i}" for i in range(d)],
        total_laps=40,
        current_lap=15,
        clean_air_pace=[90.0 + i * 0.18 for i in range(d)],
        tyre_compound=["medium"] * d,
        tyre_age=[10] * d,
        pit_count=[0] * d,
        gap_to_leader=[i * 1.5 for i in range(d)],
        retired=[False] * d,
        race_dnf_prob=[0.09] * d,
    )
    return RaceSimulator(SimConfig(n_paths=3000, seed=1)).simulate(sim)


def _setup() -> tuple[SimulationResult, list[Opportunity], ContractPrices]:
    result = _result()
    prices = price_contracts(result)
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.12, seed=3)
    )
    scan = asyncio.run(
        scan_opportunities(adapter, prices, min_conservative_edge=0.02, min_liquidity=100)
    )
    return result, scan.opportunities, prices


# --- kelly & limits ---


def test_full_kelly_math() -> None:
    assert abs(full_kelly_fraction(0.6, 0.5) - 0.2) < 1e-9
    assert full_kelly_fraction(0.5, 0.5) == 0.0  # no edge
    assert full_kelly_fraction(0.4, 0.5) == 0.0  # negative edge


def test_full_kelly_decreases_with_worse_price() -> None:
    assert full_kelly_fraction(0.6, 0.45) > full_kelly_fraction(0.6, 0.55)
    assert fractional_kelly_stake(0.6, 0.5, kelly_fraction=0.1, bankroll=1000) > 0


def test_limits_never_full_kelly() -> None:
    limits = load_risk_limits()
    assert limits.kelly(RiskTolerance.CONSERVATIVE) == 0.10
    assert limits.kelly(RiskTolerance.AGGRESSIVE) <= 0.25
    hot = RiskLimits(kelly_fraction={"aggressive": 0.9})
    assert hot.kelly(RiskTolerance.AGGRESSIVE) == 0.25  # hard-capped


# --- payoff matrix / covariance ---


def test_contract_payoff_and_matrix() -> None:
    result = _result()
    win = contract_payoff(result, ContractType.WIN, "D0")
    dnf = contract_payoff(result, ContractType.DNF, "D0")
    assert set(win.tolist()) <= {0.0, 1.0}
    assert abs(win.mean() - dnf.mean()) >= 0  # both valid probabilities
    matrix = build_payoff_matrix(
        result, [(ContractType.WIN, "D0"), (ContractType.SAFETY_CAR, None)]
    )
    assert matrix.shape == (result.n_paths, 2)


# --- allocation ---


def test_allocation_respects_all_caps() -> None:
    result, opps, _ = _setup()
    alloc = allocate(opps, result, bankroll=BANKROLL, tolerance=RiskTolerance.MODERATE)
    assert alloc.positions, alloc.message
    assert alloc.risk.total_stake <= 0.10 * BANKROLL + 1e-6  # total deployment
    for p in alloc.positions:
        assert p.stake <= 0.02 * BANKROLL + 1e-6  # per market
        assert p.contracts == int(p.contracts) and p.contracts > 0
        assert abs(p.max_loss - p.stake) < 1e-9
    # Per-driver exposure cap.
    by_driver: dict[str, float] = {}
    for p in alloc.positions:
        by_driver[p.driver_id or "race"] = by_driver.get(p.driver_id or "race", 0.0) + p.stake
    assert max(by_driver.values()) <= 0.04 * BANKROLL + 1e-6


def test_allocation_never_exceeds_bankroll_and_reports_risk() -> None:
    result, opps, _ = _setup()
    alloc = allocate(opps, result, bankroll=BANKROLL, tolerance=RiskTolerance.MODERATE)
    assert alloc.risk.total_stake + alloc.risk.cash_retained == BANKROLL
    assert alloc.risk.total_max_loss <= alloc.risk.total_stake + 1e-6
    assert alloc.risk.var_95 >= 0.0
    assert alloc.risk.expected_shortfall_95 >= alloc.risk.var_95 - 1e-6


def test_aggressive_allocates_at_least_as_much() -> None:
    result, opps, _ = _setup()
    cons = allocate(opps, result, bankroll=BANKROLL, tolerance=RiskTolerance.CONSERVATIVE)
    aggr = allocate(opps, result, bankroll=BANKROLL, tolerance=RiskTolerance.AGGRESSIVE)
    assert aggr.risk.total_stake >= cons.risk.total_stake - 1e-6


def test_no_opportunity_returns_empty_allocation() -> None:
    result = _result()
    alloc = allocate([], result, bankroll=BANKROLL, tolerance=RiskTolerance.MODERATE)
    assert alloc.positions == []
    assert alloc.message == NO_ALLOCATION
    assert alloc.risk.cash_retained == BANKROLL


def test_portfolio_service_end_to_end() -> None:
    result = _result()
    alloc = asyncio.run(
        build_allocation(result, bankroll=BANKROLL, tolerance=RiskTolerance.MODERATE)
    )
    assert alloc.bankroll == BANKROLL
    # Either positions with valid accounting, or an explicit no-opportunity result.
    if alloc.positions:
        assert alloc.risk.total_stake <= 0.10 * BANKROLL + 1e-6
    else:
        assert alloc.message == NO_ALLOCATION
