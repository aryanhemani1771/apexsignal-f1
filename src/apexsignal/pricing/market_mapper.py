"""Rule-aware market → internal-contract mapping.

Mapping is a safety component: never map on fuzzy title similarity alone. We parse structured
fields, outcome labels, and resolution rules, and produce a confidence score. Markets below the
configured confidence require manual review and are never ranked or allocated to.
"""

from __future__ import annotations

from pydantic import BaseModel

from apexsignal.domain.markets import ContractType, Market
from apexsignal.intelligence.entity_resolution import EntityResolver

DEFAULT_MIN_CONFIDENCE = 0.95

_CONTRACT_KEYWORDS: list[tuple[ContractType, tuple[str, ...]]] = [
    (ContractType.SAFETY_CAR, ("safety car",)),
    (ContractType.FASTEST_LAP, ("fastest lap",)),
    (ContractType.PIT_BEFORE_LAP, ("pit before", "pits before")),
    (ContractType.POSITIONS_GAINED, ("positions gained", "gain positions", "places gained")),
    (ContractType.HEAD_TO_HEAD, ("ahead of", "beat ", "finish ahead")),
    (ContractType.PODIUM, ("podium", "top 3", "top three")),
    (ContractType.POINTS, ("points", "top 10", "top ten")),
    (ContractType.DNF, ("dnf", "retire", "does not finish", "fail to finish")),
    (ContractType.WIN, ("to win", "wins the", "race winner", " win")),
]
_RACE_LEVEL = {ContractType.SAFETY_CAR}


class MappedContract(BaseModel):
    market_id: str
    driver_id: str | None
    contract_type: ContractType | None
    threshold: float | None
    confidence: float
    needs_review: bool
    reasons: list[str]


class MarketMapper:
    def __init__(
        self,
        resolver: EntityResolver | None = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self.resolver = resolver or EntityResolver()
        self.min_confidence = min_confidence

    def _detect_contract(self, market: Market) -> ContractType | None:
        if market.contract_type is not None:
            return market.contract_type
        text = f"{market.title} {market.resolution_rules}".lower()
        for ct, keywords in _CONTRACT_KEYWORDS:
            if any(k in text for k in keywords):
                return ct
        return None

    def map(self, market: Market) -> MappedContract:
        reasons: list[str] = []
        confidence = 0.5

        contract = self._detect_contract(market)
        if contract is not None:
            confidence += 0.25
            if market.contract_type is not None:
                reasons.append("structured contract_type")
        else:
            reasons.append("contract type not identified")

        driver = market.driver_id
        if driver is None:
            found = self.resolver.resolve_drivers(f"{market.title} {market.resolution_rules}")
            driver = found[0] if len(found) == 1 else None
            if len(found) > 1:
                confidence -= 0.2
                reasons.append("multiple drivers mentioned — ambiguous")

        if driver is not None or contract in _RACE_LEVEL:
            confidence += 0.2
        else:
            reasons.append("no single driver resolved")

        rules = market.resolution_rules.strip().lower()
        if rules and ("settle" in rules or "resolve" in rules or market.settlement_source):
            confidence += 0.15
        else:
            confidence -= 0.3
            reasons.append("resolution rules missing/weak — cannot map on title alone")

        labels = {label.strip().lower() for label in market.outcome_labels}
        if labels and labels != {"yes", "no"}:
            confidence -= 0.3
            reasons.append("non-binary outcome labels")

        confidence = max(0.0, min(1.0, confidence))
        needs_review = confidence < self.min_confidence or contract is None
        return MappedContract(
            market_id=market.market_id,
            driver_id=driver,
            contract_type=contract,
            threshold=market.threshold,
            confidence=confidence,
            needs_review=needs_review,
            reasons=reasons,
        )
