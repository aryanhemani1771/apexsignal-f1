"""Polymarket adapter — read-only, always.

Polymarket's docs list the United States as blocked. This adapter keeps to public/read-only
data, supports an optional geographic-availability check, and disables itself gracefully when
access is restricted. It never implements authenticated trading and never attempts to bypass any
geographic or platform control.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from apexsignal.domain.markets import (
    Exchange,
    Market,
    MarketEvent,
    OrderBook,
    PriceLevel,
)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"


class PolymarketRestrictedError(RuntimeError):
    """Raised when Polymarket is unavailable in the current jurisdiction."""


class PolymarketNotConfiguredError(RuntimeError):
    """Raised when httpx (the ``api`` extra) is unavailable."""


def _require_httpx() -> Any:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - only without the api extra
        raise PolymarketNotConfiguredError(
            "httpx is not installed. Install the api extra: `uv sync --extra api`."
        ) from exc
    return httpx


class PolymarketReadOnlyAdapter:
    """Read-only Polymarket market data. No trading methods exist on this class."""

    exchange = Exchange.POLYMARKET

    def __init__(self, *, base_url: str = GAMMA_BASE_URL, assume_available: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self._httpx = _require_httpx()
        self.available = assume_available

    async def check_availability(self) -> bool:
        """Best-effort geo/availability probe; on failure, disable gracefully."""
        try:
            async with self._httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/markets", params={"limit": 1})
            self.available = resp.status_code < 400
        except Exception:  # pragma: no cover - network dependent
            self.available = False
        return self.available

    def _ensure_available(self) -> None:
        if not self.available:
            raise PolymarketRestrictedError(
                "Polymarket is unavailable in this jurisdiction; adapter disabled (read-only, "
                "no bypass)."
            )

    async def list_events(self, query: str | None = None) -> list[MarketEvent]:
        self._ensure_available()
        data = await self._get("/events", {"limit": 50})
        return [
            MarketEvent(
                event_id=str(e.get("id", "")),
                exchange=Exchange.POLYMARKET,
                title=e.get("title", ""),
            )
            for e in _as_list(data)
        ]

    async def list_markets(self, event_id: str | None = None) -> list[Market]:
        self._ensure_available()
        params: dict[str, Any] = {"limit": 50}
        if event_id:
            params["event_id"] = event_id
        data = await self._get("/markets", params)
        return [self.parse_market(m) for m in _as_list(data)]

    async def get_orderbook(self, market_id: str) -> OrderBook:
        self._ensure_available()
        data = await self._get("/book", {"token_id": market_id}, base=CLOB_BASE_URL)
        return self.parse_orderbook(market_id, data)

    async def _get(self, path: str, params: dict[str, Any], *, base: str | None = None) -> Any:
        async with self._httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{(base or self.base_url).rstrip('/')}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def parse_market(m: dict[str, Any]) -> Market:
        return Market(
            market_id=str(m.get("id", m.get("conditionId", ""))),
            event_id=str(m.get("eventId", "")),
            exchange=Exchange.POLYMARKET,
            title=m.get("question", m.get("title", "")),
            outcome_labels=m.get("outcomes", ["Yes", "No"]),
            resolution_rules=m.get("description", ""),
        )

    @staticmethod
    def parse_orderbook(market_id: str, ob: dict[str, Any]) -> OrderBook:
        def _levels(rows: Any) -> list[PriceLevel]:
            out = []
            for r in rows or []:
                out.append(PriceLevel(price=float(r["price"]), size=float(r["size"])))
            return out

        bids = _levels(ob.get("bids"))
        asks = _levels(ob.get("asks"))
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        return OrderBook(
            market_id=market_id,
            exchange=Exchange.POLYMARKET,
            timestamp=datetime.now(UTC),
            bids=bids,
            asks=asks,
        )


def _as_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "markets", "events"):
            if isinstance(data.get(key), list):
                return cast(list[dict[str, Any]], data[key])
    return []
