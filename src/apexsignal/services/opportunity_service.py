"""Opportunity scanning: compare model prices to market books and rank the edges.

For each market we map it to an internal contract (skipping anything below the mapping-confidence
gate — never ranking an ambiguous mapping), compute the effective ask after fees/slippage, and
compare it to the conservative (uncertainty-adjusted) model probability. Opportunities are ranked
by a composite score, not raw edge. The scan may return *no qualifying opportunity*.
"""

from __future__ import annotations

from pydantic import BaseModel

from apexsignal.domain.markets import ContractType, Exchange, MarketDataAdapter
from apexsignal.pricing.edge import conservative_probability, expected_value
from apexsignal.pricing.fees import FeeConfig, effective_ask
from apexsignal.pricing.market_mapper import MappedContract, MarketMapper
from apexsignal.simulation.payoff_matrix import ContractPrices

NO_OPPORTUNITY = (
    "No market currently clears the project's uncertainty, liquidity, and risk thresholds."
)


class Opportunity(BaseModel):
    market_id: str
    exchange: Exchange
    driver_id: str | None
    contract_type: ContractType
    model_probability: float
    conservative_probability: float
    market_bid: float | None
    market_ask: float
    effective_ask: float
    spread: float | None
    fees: float
    slippage: float
    raw_edge: float
    conservative_edge: float
    expected_value: float
    liquidity: float
    mapping_confidence: float
    score: float
    rationale: str
    risk: str


class OpportunityScan(BaseModel):
    n_markets: int
    n_reviewed_out: int
    opportunities: list[Opportunity]
    message: str


def _model_prob(prices: ContractPrices, mapped: MappedContract) -> float | None:
    ct = mapped.contract_type
    if ct is ContractType.SAFETY_CAR:
        return prices.safety_car
    if mapped.driver_id is None or mapped.driver_id not in prices.drivers:
        return None
    dp = prices.drivers[mapped.driver_id]
    table = {
        ContractType.WIN: dp.win,
        ContractType.PODIUM: dp.podium,
        ContractType.POINTS: dp.points,
        ContractType.DNF: dp.dnf,
        ContractType.FASTEST_LAP: dp.fastest_lap,
        ContractType.POSITIONS_GAINED: dp.gains_positions,
        ContractType.PIT_BEFORE_LAP: dp.pit_before_lap,
    }
    return table.get(ct) if ct is not None else None


async def scan_opportunities(
    adapter: MarketDataAdapter,
    prices: ContractPrices,
    *,
    mapper: MarketMapper | None = None,
    fee_config: FeeConfig | None = None,
    min_conservative_edge: float = 0.03,
    min_mapping_confidence: float = 0.95,
    min_liquidity: float = 100.0,
    haircut_sd: float = 1.0,
) -> OpportunityScan:
    mapper = mapper or MarketMapper(min_confidence=min_mapping_confidence)
    fees = fee_config or FeeConfig()
    markets = await adapter.list_markets()

    opportunities: list[Opportunity] = []
    reviewed_out = 0
    for market in markets:
        mapped = mapper.map(market)
        if mapped.needs_review or mapped.confidence < min_mapping_confidence:
            reviewed_out += 1
            continue
        model_p = _model_prob(prices, mapped)
        if model_p is None or mapped.contract_type is None:
            reviewed_out += 1
            continue

        book = await adapter.get_orderbook(market.market_id)
        if book.best_ask is None:
            continue
        eff_ask = effective_ask(book.best_ask, fee=fees.taker_fee, slippage=fees.default_slippage)
        cons_p = conservative_probability(model_p, prices.n_paths, haircut_sd=haircut_sd)
        cons_edge = cons_p - eff_ask
        liquidity = book.ask_liquidity()

        if cons_edge < min_conservative_edge or liquidity < min_liquidity:
            continue

        liq_weight = min(1.0, liquidity / (min_liquidity * 2.0))
        score = cons_edge * mapped.confidence * liq_weight
        opportunities.append(
            Opportunity(
                market_id=market.market_id,
                exchange=market.exchange,
                driver_id=mapped.driver_id,
                contract_type=mapped.contract_type,
                model_probability=model_p,
                conservative_probability=cons_p,
                market_bid=book.best_bid,
                market_ask=book.best_ask,
                effective_ask=eff_ask,
                spread=book.spread,
                fees=fees.taker_fee,
                slippage=fees.default_slippage,
                raw_edge=model_p - eff_ask,
                conservative_edge=cons_edge,
                expected_value=expected_value(model_p, eff_ask),
                liquidity=liquidity,
                mapping_confidence=mapped.confidence,
                score=score,
                rationale=(
                    f"Model {model_p:.1%} vs effective ask {eff_ask:.1%} → "
                    f"conservative edge {cons_edge:.1%}"
                ),
                risk="Monte Carlo + mapping uncertainty; edge shrinks after fees and slippage.",
            )
        )

    opportunities.sort(key=lambda o: o.score, reverse=True)
    return OpportunityScan(
        n_markets=len(markets),
        n_reviewed_out=reviewed_out,
        opportunities=opportunities,
        message=NO_OPPORTUNITY if not opportunities else f"{len(opportunities)} opportunity(ies).",
    )
