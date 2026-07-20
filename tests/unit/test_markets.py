"""Market domain, synthetic adapter, mapping, fees/edge, opportunities, execution."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from apexsignal.domain.markets import Exchange, Market, OrderBook, PriceLevel
from apexsignal.execution.base import Order, Side
from apexsignal.execution.paper import PaperExecutor
from apexsignal.ingestion.kalshi_adapter import KalshiDemoExecutor, KalshiPublicAdapter
from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.pricing.edge import conservative_probability, monte_carlo_se, raw_edge
from apexsignal.pricing.fees import FeeConfig, effective_ask
from apexsignal.pricing.market_mapper import MarketMapper
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.settings import LiveTradingDisabledError
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import ContractPrices, price_contracts

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _prices() -> ContractPrices:
    d = 8
    sim = SimInput(
        driver_ids=[f"D{i}" for i in range(d)],
        total_laps=30,
        current_lap=10,
        clean_air_pace=[90.0 + i * 0.2 for i in range(d)],
        tyre_compound=["medium"] * d,
        tyre_age=[8] * d,
        pit_count=[0] * d,
        gap_to_leader=[i * 1.5 for i in range(d)],
        retired=[False] * d,
        race_dnf_prob=[0.08] * d,
    )
    return price_contracts(RaceSimulator(SimConfig(n_paths=1500, seed=1)).simulate(sim))


def _book(bid: float, ask: float) -> OrderBook:
    return OrderBook(
        market_id="m",
        exchange=Exchange.SYNTHETIC,
        timestamp=T0,
        bids=[PriceLevel(price=bid, size=100)],
        asks=[PriceLevel(price=ask, size=100)],
    )


# --- order book / fees / edge ---


def test_orderbook_derived_prices() -> None:
    b = _book(0.40, 0.44)
    assert b.best_bid == 0.40
    assert b.best_ask == 0.44
    assert abs(b.mid - 0.42) < 1e-9
    assert abs(b.spread - 0.04) < 1e-9


def test_fees_and_edge_math() -> None:
    assert abs(effective_ask(0.50, fee=0.01, slippage=0.005) - 0.515) < 1e-9
    assert raw_edge(0.60, 0.515) == 0.60 - 0.515
    se = monte_carlo_se(0.5, 2500)
    assert abs(se - 0.01) < 1e-9
    assert conservative_probability(0.5, 2500, haircut_sd=1.0) < 0.5


# --- synthetic adapter ---


def test_synthetic_adapter_builds_markets_and_books() -> None:
    adapter = SyntheticMarketAdapter(_prices(), meeting_id="demo")
    markets = asyncio.run(adapter.list_markets())
    assert len(markets) == 8 * 4 + 1  # 4 driver contracts + safety car
    book = asyncio.run(adapter.get_orderbook(markets[0].market_id))
    assert book.best_ask is not None and book.best_bid is not None
    assert book.best_ask > book.best_bid  # positive spread


# --- mapping (safety gate) ---


def test_structured_market_maps_with_high_confidence() -> None:
    adapter = SyntheticMarketAdapter(_prices())
    market = asyncio.run(adapter.list_markets())[0]
    mapped = MarketMapper().map(market)
    assert mapped.confidence >= 0.95
    assert not mapped.needs_review


def test_title_only_market_needs_review() -> None:
    ambiguous = Market(
        market_id="x",
        event_id="e",
        exchange=Exchange.KALSHI,
        title="Verstappen to win",  # no resolution rules, no structured fields
    )
    mapped = MarketMapper().map(ambiguous)
    assert mapped.needs_review is True  # never map on title alone


# --- opportunities ---


def test_scan_finds_and_ranks_opportunities() -> None:
    prices = _prices()
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.15, seed=3)
    )
    scan = asyncio.run(
        scan_opportunities(adapter, prices, min_conservative_edge=0.02, min_liquidity=100)
    )
    assert scan.opportunities, scan.message
    scores = [o.score for o in scan.opportunities]
    assert scores == sorted(scores, reverse=True)  # ranked
    top = scan.opportunities[0]
    assert top.conservative_edge >= 0.02
    assert top.effective_ask > top.market_ask  # fees/slippage raise the cost


def test_scan_can_return_no_opportunity() -> None:
    prices = _prices()
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.15, seed=3)
    )
    scan = asyncio.run(scan_opportunities(adapter, prices, min_conservative_edge=0.9))
    assert scan.opportunities == []
    assert "No market" in scan.message


# --- execution + safety guards ---


def test_paper_executor_accounting() -> None:
    ex = PaperExecutor(starting_cash=1000.0, fee_config=FeeConfig(taker_fee=0.0))
    fill = ex.submit(Order(market_id="m", side=Side.BUY_YES, size=100), _book(0.40, 0.44))
    assert fill is not None and fill.price == 0.44
    assert abs(ex.cash - (1000.0 - 44.0)) < 1e-9
    # Settles Yes: 100 contracts pay 1 each.
    pnl = ex.settle("m", outcome=1)
    assert abs(pnl - (1.0 - 0.44) * 100) < 1e-9


def test_paper_limit_rejects_when_not_marketable() -> None:
    ex = PaperExecutor()
    fill = ex.submit(
        Order(market_id="m", side=Side.BUY_YES, size=10, limit_price=0.30), _book(0.40, 0.44)
    )
    assert fill is None  # ask 0.44 > limit 0.30


def test_kalshi_demo_executor_blocks_live_trading() -> None:
    KalshiDemoExecutor(enable_live_trading=False)  # ok
    try:
        KalshiDemoExecutor(enable_live_trading=True)
    except LiveTradingDisabledError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected LiveTradingDisabledError")


def test_kalshi_orderbook_parsing_cents_to_prob() -> None:
    ob = {"yes": [[40, 100], [39, 50]], "no": [[54, 100]]}
    book = KalshiPublicAdapter.parse_orderbook("TICKER", ob)
    assert book.best_bid == 0.40  # 40c
    assert book.best_ask == 0.46  # 100 - 54c
