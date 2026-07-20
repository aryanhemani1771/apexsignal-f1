"""Kalshi adapter — public market data (read-only) and demo-only execution.

Treats Kalshi's REST/WebSocket specs as the source of truth (their SDKs may lag). Public data
needs no credentials; demo execution needs demo API keys and runs against the demo environment
only. Real-money execution is never implemented — the production path raises
``LiveTradingDisabledError``. ``httpx`` is imported lazily (optional ``api`` extra), so this
module stays importable in CI. Prices are converted from Kalshi cents (0-100) to probabilities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apexsignal.domain.markets import (
    Exchange,
    Market,
    MarketEvent,
    OrderBook,
    PriceLevel,
)
from apexsignal.settings import LiveTradingDisabledError

DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"
PUBLIC_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiNotConfiguredError(RuntimeError):
    """Raised when httpx (the ``api`` extra) is unavailable."""


def _require_httpx() -> Any:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - only without the api extra
        raise KalshiNotConfiguredError(
            "httpx is not installed. Install the api extra: `uv sync --extra api`."
        ) from exc
    return httpx


def _cents_to_prob(cents: float) -> float:
    return max(0.0, min(1.0, cents / 100.0))


class KalshiPublicAdapter:
    """Read-only Kalshi market data. Never places orders."""

    exchange = Exchange.KALSHI

    def __init__(self, base_url: str = PUBLIC_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._httpx = _require_httpx()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def list_events(self, query: str | None = None) -> list[MarketEvent]:
        data = await self._get("/events", {"status": "open"})
        return [
            MarketEvent(
                event_id=e["event_ticker"],
                exchange=Exchange.KALSHI,
                title=e.get("title", e["event_ticker"]),
            )
            for e in data.get("events", [])
        ]

    async def list_markets(self, event_id: str | None = None) -> list[Market]:
        params = {"status": "open"}
        if event_id:
            params["event_ticker"] = event_id
        data = await self._get("/markets", params)
        return [self.parse_market(m) for m in data.get("markets", [])]

    async def get_orderbook(self, market_id: str) -> OrderBook:
        data = await self._get(f"/markets/{market_id}/orderbook")
        return self.parse_orderbook(market_id, data.get("orderbook", {}))

    @staticmethod
    def parse_market(m: dict[str, Any]) -> Market:
        return Market(
            market_id=m["ticker"],
            event_id=m.get("event_ticker", ""),
            exchange=Exchange.KALSHI,
            title=m.get("title", m["ticker"]),
            outcome_labels=["Yes", "No"],
            resolution_rules=m.get("rules_primary", ""),
            settlement_source=m.get("settlement_source"),
        )

    @staticmethod
    def parse_orderbook(market_id: str, ob: dict[str, Any]) -> OrderBook:
        # Kalshi gives yes/no price ladders in cents. Buying Yes = the ask side; we derive it
        # from the best No bids (ask_yes = 100 - bid_no).
        yes = ob.get("yes") or []
        no = ob.get("no") or []
        bids = [PriceLevel(price=_cents_to_prob(p), size=float(s)) for p, s in yes]
        asks = [PriceLevel(price=_cents_to_prob(100 - p), size=float(s)) for p, s in no]
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        return OrderBook(
            market_id=market_id,
            exchange=Exchange.KALSHI,
            timestamp=datetime.now(UTC),
            bids=bids,
            asks=asks,
        )


class KalshiDemoExecutor:
    """Demo-environment execution only. Real-money execution is never implemented."""

    def __init__(self, *, enable_live_trading: bool = False) -> None:
        if enable_live_trading:
            raise LiveTradingDisabledError(
                "Real-money Kalshi execution is not implemented. Use the demo environment."
            )
        self.base_url = DEMO_BASE_URL

    def place_order(self, *args: object, **kwargs: object) -> None:
        # Demo order placement requires signed requests against the demo API. Wiring is left to
        # the operator with demo credentials; production execution is intentionally absent.
        raise NotImplementedError(
            "Kalshi demo order placement requires demo credentials; see .env.example."
        )
