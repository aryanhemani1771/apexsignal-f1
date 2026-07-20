"""Execution interfaces and shared types.

Only paper, synthetic, and Kalshi-demo execution exist. Real-money execution is never
implemented; the guard below re-exports ``LiveTradingDisabledError`` for callers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from apexsignal.domain.markets import OrderBook
from apexsignal.settings import LiveTradingDisabledError

__all__ = ["Executor", "Fill", "LiveTradingDisabledError", "Order", "Position", "Side"]


class Side(StrEnum):
    BUY_YES = "buy_yes"
    SELL_YES = "sell_yes"


class Order(BaseModel):
    market_id: str
    side: Side
    size: float
    limit_price: float | None = None  # probability [0,1]; None = marketable


class Fill(BaseModel):
    market_id: str
    side: Side
    size: float
    price: float
    fee: float
    timestamp: datetime


class Position(BaseModel):
    market_id: str
    quantity: float = 0.0  # net Yes contracts
    avg_price: float = 0.0


class Executor(Protocol):
    def submit(self, order: Order, book: OrderBook) -> Fill | None: ...

    def settle(self, market_id: str, outcome: int) -> float: ...
