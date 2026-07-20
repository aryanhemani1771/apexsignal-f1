"""Load expert impact priors from ``configs/event_impact_priors.yaml``.

These are labelled **priors**, not facts: they seed a Bayesian shrinkage step and are meant to
be overridden by historical event studies. Unconfirmed events get scaled-down impact, widened
uncertainty, and faster time decay via the ``defaults`` block.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "event_impact_priors.yaml"

# Prior fields map 1:1 onto ExtractedF1Event effect-size fields.
PRIOR_FIELDS = (
    "grid_position_delta",
    "pace_delta_seconds_per_lap",
    "pace_uncertainty_delta",
    "dnf_log_odds_delta",
    "wet_performance_delta",
)


class PriorMeanSd(BaseModel):
    mean: float
    sd: float


class ImpactDefaults(BaseModel):
    unconfirmed_impact_scale: float = 0.4
    unconfirmed_uncertainty_scale: float = 1.8
    half_life_confirmed_hours: float = 168.0
    half_life_unconfirmed_hours: float = 24.0


class ImpactPriors(BaseModel):
    version: int = 0
    defaults: ImpactDefaults = Field(default_factory=ImpactDefaults)
    priors: dict[str, dict[str, PriorMeanSd]] = Field(default_factory=dict)

    def for_event(self, event_type: str) -> dict[str, PriorMeanSd]:
        return self.priors.get(event_type, {})


def load_impact_priors(path: str | Path | None = None) -> ImpactPriors:
    p = Path(path) if path else _DEFAULT_CONFIG
    if not p.exists():
        return ImpactPriors()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    defaults_raw = data.get("defaults") or {}
    decay = defaults_raw.get("time_decay_half_life_hours") or {}
    defaults = ImpactDefaults(
        unconfirmed_impact_scale=float(defaults_raw.get("unconfirmed_impact_scale", 0.4)),
        unconfirmed_uncertainty_scale=float(defaults_raw.get("unconfirmed_uncertainty_scale", 1.8)),
        half_life_confirmed_hours=float(decay.get("confirmed", 168)),
        half_life_unconfirmed_hours=float(decay.get("unconfirmed", 24)),
    )

    priors: dict[str, dict[str, PriorMeanSd]] = {}
    for event_type, fields in (data.get("priors") or {}).items():
        parsed: dict[str, PriorMeanSd] = {}
        for field, spec in (fields or {}).items():
            if field in PRIOR_FIELDS and isinstance(spec, dict) and "mean" in spec:
                parsed[field] = PriorMeanSd(mean=float(spec["mean"]), sd=float(spec.get("sd", 0)))
        if parsed:
            priors[event_type] = parsed

    return ImpactPriors(version=int(data.get("version", 0)), defaults=defaults, priors=priors)
