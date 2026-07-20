"""Synthetic market adapter — builds order books from model prices.

Always works offline (no credentials, no network). Given the simulator's contract prices, it
creates well-formed markets whose mid-price is the model probability perturbed by a seeded
"mispricing" — so the opportunity engine has genuine (but synthetic) edges to find. Markets
carry structured fields and resolution text, so the contract mapper maps them with high
confidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel

from apexsignal.domain.markets import (
    ContractType,
    Exchange,
    Market,
    MarketEvent,
    OrderBook,
    PriceLevel,
)
from apexsignal.simulation.payoff_matrix import ContractPrices

_DRIVER_CONTRACTS = (ContractType.WIN, ContractType.PODIUM, ContractType.POINTS, ContractType.DNF)


class SyntheticMarketConfig(BaseModel):
    spread: float = 0.03
    liquidity: float = 250.0
    mispricing_sd: float = 0.05  # how far the synthetic market strays from the model
    depth_levels: int = 3
    seed: int = 42


class SyntheticMarketAdapter:
    """Read-only adapter serving synthetic books derived from model prices."""

    exchange = Exchange.SYNTHETIC

    def __init__(
        self,
        prices: ContractPrices,
        *,
        meeting_id: str = "demo",
        config: SyntheticMarketConfig | None = None,
    ) -> None:
        self.prices = prices
        self.meeting_id = meeting_id
        self.config = config or SyntheticMarketConfig()
        self._event_id = f"{meeting_id}-race"
        self._markets: dict[str, Market] = {}
        self._mids: dict[str, float] = {}
        self._build()

    def _build(self) -> None:
        rng = np.random.default_rng(self.config.seed)
        for did, dp in self.prices.drivers.items():
            model = {
                ContractType.WIN: dp.win,
                ContractType.PODIUM: dp.podium,
                ContractType.POINTS: dp.points,
                ContractType.DNF: dp.dnf,
            }
            for ct in _DRIVER_CONTRACTS:
                self._add_market(f"{did}_{ct.value}", ct, model[ct], driver_id=did, rng=rng)
        # Race-level safety-car market.
        self._add_market(
            "race_safety_car", ContractType.SAFETY_CAR, self.prices.safety_car, rng=rng
        )

    def _add_market(
        self,
        market_id: str,
        contract_type: ContractType,
        model_prob: float,
        *,
        rng: np.random.Generator,
        driver_id: str | None = None,
    ) -> None:
        mid = float(np.clip(model_prob + rng.normal(0.0, self.config.mispricing_sd), 0.01, 0.99))
        who = driver_id or "the race"
        self._markets[market_id] = Market(
            market_id=market_id,
            event_id=self._event_id,
            exchange=Exchange.SYNTHETIC,
            title=f"{who} {contract_type.value.replace('_', ' ')}",
            outcome_labels=["Yes", "No"],
            resolution_rules=(
                f"Resolves YES if {who} achieves {contract_type.value} in the race; "
                "settled from official classification."
            ),
            settlement_source="official_classification",
            driver_id=driver_id,
            contract_type=contract_type,
        )
        self._mids[market_id] = mid

    async def list_events(self, query: str | None = None) -> list[MarketEvent]:
        return [
            MarketEvent(
                event_id=self._event_id,
                exchange=Exchange.SYNTHETIC,
                title=f"{self.meeting_id} race markets",
                meeting_id=self.meeting_id,
            )
        ]

    async def list_markets(self, event_id: str | None = None) -> list[Market]:
        return list(self._markets.values())

    async def get_orderbook(self, market_id: str) -> OrderBook:
        mid = self._mids[market_id]
        cfg = self.config
        half = cfg.spread / 2.0
        bids = [
            PriceLevel(price=round(max(0.0, mid - half - i * 0.01), 4), size=cfg.liquidity)
            for i in range(cfg.depth_levels)
        ]
        asks = [
            PriceLevel(price=round(min(1.0, mid + half + i * 0.01), 4), size=cfg.liquidity)
            for i in range(cfg.depth_levels)
        ]
        return OrderBook(
            market_id=market_id,
            exchange=Exchange.SYNTHETIC,
            timestamp=datetime.now(UTC),
            bids=bids,
            asks=asks,
        )
