"""Risk limits and tolerance, loaded from ``configs/risk_limits.yaml``.

Conservative by default. Full Kelly is intentionally not offered; the largest fraction is 0.25.
All caps are fractions of the user-entered research bankroll.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "risk_limits.yaml"


class RiskTolerance(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class ExposureCaps(BaseModel):
    max_per_market: float = 0.02
    max_total_deployment: float = 0.10
    max_driver_exposure: float = 0.04
    max_constructor_exposure: float = 0.06
    max_correlated_cluster_exposure: float = 0.06


class Thresholds(BaseModel):
    min_conservative_edge: float = 0.03
    min_mapping_confidence: float = 0.95
    min_liquidity: float = 100.0
    max_estimated_slippage: float = 0.02


class RiskLimits(BaseModel):
    # Fractional Kelly only — no full Kelly.
    kelly_fraction: dict[str, float] = Field(
        default_factory=lambda: {"conservative": 0.10, "moderate": 0.20, "aggressive": 0.25}
    )
    exposure: ExposureCaps = Field(default_factory=ExposureCaps)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    risk_aversion: float = 5.0
    integer_contracts: bool = True
    allow_short: bool = False

    def kelly(self, tolerance: RiskTolerance) -> float:
        frac = self.kelly_fraction.get(tolerance.value, 0.10)
        return min(frac, 0.25)  # hard cap: never full Kelly


def load_risk_limits(path: str | Path | None = None) -> RiskLimits:
    p = Path(path) if path else _DEFAULT_CONFIG
    if not p.exists():
        return RiskLimits()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    kelly = data.get("kelly_fraction") or {}
    caps = data.get("exposure_caps") or {}
    thr = data.get("thresholds") or {}
    opt = data.get("optimizer") or {}
    return RiskLimits(
        kelly_fraction={
            k: float(v) for k, v in kelly.items() if k in ("conservative", "moderate", "aggressive")
        }
        or RiskLimits().kelly_fraction,
        exposure=ExposureCaps(
            **{k: float(v) for k, v in caps.items() if k in ExposureCaps.model_fields}
        ),
        thresholds=Thresholds(
            **{k: float(v) for k, v in thr.items() if k in Thresholds.model_fields}
        ),
        risk_aversion=float(opt.get("risk_aversion", 5.0)),
        integer_contracts=bool(opt.get("integer_contracts", True)),
        allow_short=bool(opt.get("allow_short", False)),
    )
