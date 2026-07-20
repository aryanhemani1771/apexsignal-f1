"""Market domain: exchange events, markets, order books, and the unified adapter interface.

All prices are normalised to probability units in [0, 1] (Kalshi cents / Polymarket decimals are
converted on ingest). A binary Yes contract costs ``best_ask`` to buy and returns 1 on Yes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class Exchange(StrEnum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    SYNTHETIC = "synthetic"


class ContractType(StrEnum):
    WIN = "win"
    PODIUM = "podium"
    POINTS = "points"
    DNF = "dnf"
    HEAD_TO_HEAD = "head_to_head"
    SAFETY_CAR = "safety_car"
    PIT_BEFORE_LAP = "pit_before_lap"
    POSITIONS_GAINED = "positions_gained"
    FASTEST_LAP = "fastest_lap"
    CONSTRUCTOR_POINTS = "constructor_points"


class MarketEvent(BaseModel):
    event_id: str
    exchange: Exchange
    title: str
    meeting_id: str | None = None


class Market(BaseModel):
    market_id: str
    event_id: str
    exchange: Exchange
    title: str
    outcome_labels: list[str] = Field(default_factory=list)
    resolution_rules: str = ""
    settlement_source: str | None = None
    expiration: datetime | None = None
    # Structured fields (populated by well-formed exchanges or the mapper).
    driver_id: str | None = None
    constructor_id: str | None = None
    contract_type: ContractType | None = None
    threshold: float | None = None
    raw: dict[str, str] = Field(default_factory=dict)


class PriceLevel(BaseModel):
    price: float  # probability [0, 1]
    size: float  # contracts available


class OrderBook(BaseModel):
    market_id: str
    exchange: Exchange
    timestamp: datetime
    bids: list[PriceLevel] = Field(default_factory=list)  # buy-Yes interest, high→low
    asks: list[PriceLevel] = Field(default_factory=list)  # sell-Yes interest, low→high

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    def ask_liquidity(self) -> float:
        return sum(level.size for level in self.asks)


class MarketDataAdapter(Protocol):
    """Unified read-only market-data interface (all implementations are read-only)."""

    async def list_events(self, query: str | None = None) -> list[MarketEvent]: ...

    async def list_markets(self, event_id: str | None = None) -> list[Market]: ...

    async def get_orderbook(self, market_id: str) -> OrderBook: ...
