"""Paper execution and accounting.

Simulates marketable fills against an order book (crossing the spread, not the midpoint),
charges a flat fee, and tracks cash, positions, and realised P&L. Settlement pays 1 per Yes
contract on a Yes outcome, 0 otherwise.
"""

from __future__ import annotations

from datetime import UTC, datetime

from apexsignal.domain.markets import OrderBook
from apexsignal.execution.base import Fill, Order, Position, Side
from apexsignal.pricing.fees import FeeConfig


class PaperExecutor:
    def __init__(self, starting_cash: float = 1000.0, fee_config: FeeConfig | None = None) -> None:
        self.cash = starting_cash
        self.fees = fee_config or FeeConfig()
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self.realized_pnl = 0.0

    def submit(self, order: Order, book: OrderBook) -> Fill | None:
        price = book.best_ask if order.side is Side.BUY_YES else book.best_bid
        if price is None:
            return None
        if order.limit_price is not None:
            if order.side is Side.BUY_YES and price > order.limit_price:
                return None
            if order.side is Side.SELL_YES and price < order.limit_price:
                return None

        fee = self.fees.taker_fee * order.size
        fill = Fill(
            market_id=order.market_id,
            side=order.side,
            size=order.size,
            price=price,
            fee=fee,
            timestamp=datetime.now(UTC),
        )
        self._apply(fill)
        self.fills.append(fill)
        return fill

    def _apply(self, fill: Fill) -> None:
        pos = self.positions.get(fill.market_id, Position(market_id=fill.market_id))
        signed = fill.size if fill.side is Side.BUY_YES else -fill.size
        if fill.side is Side.BUY_YES:
            new_qty = pos.quantity + fill.size
            # Weighted-average entry across adds.
            pos.avg_price = (
                (pos.avg_price * pos.quantity + fill.price * fill.size) / new_qty
                if new_qty
                else 0.0
            )
            pos.quantity = new_qty
            self.cash -= fill.price * fill.size + fill.fee
        else:
            self.realized_pnl += (fill.price - pos.avg_price) * fill.size
            pos.quantity += signed
            self.cash += fill.price * fill.size - fill.fee
        self.positions[fill.market_id] = pos

    def settle(self, market_id: str, outcome: int) -> float:
        pos = self.positions.pop(market_id, None)
        if pos is None or pos.quantity == 0:
            return 0.0
        pnl = (outcome - pos.avg_price) * pos.quantity
        self.realized_pnl += pnl
        self.cash += outcome * pos.quantity
        return pnl

    def portfolio_value(self, marks: dict[str, float]) -> float:
        holdings = sum(p.quantity * marks.get(m, p.avg_price) for m, p in self.positions.items())
        return self.cash + holdings
