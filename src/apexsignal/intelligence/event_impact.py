"""Translate structured events into model-parameter adjustments (Bayesian shrinkage).

An event's raw prior effect is shrunk by confidence, scaled down when unconfirmed, and decayed
over time (unconfirmed news decays faster). Effects are never added directly to a probability —
they modify parameters (grid position, pace, DNF log-odds, wet performance) that the pre-race
and simulation models consume. Unconfirmed events carry lower impact and wider uncertainty.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from apexsignal.domain.news import ExtractedF1Event
from apexsignal.intelligence.impact_priors import ImpactPriors, load_impact_priors


class DriverImpact(BaseModel):
    grid_position_delta: float = 0.0
    pace_delta_seconds_per_lap: float = 0.0
    pace_uncertainty_delta: float = 0.0
    dnf_log_odds_delta: float = 0.0
    wet_performance_delta: float = 0.0

    def combine(self, other: DriverImpact) -> DriverImpact:
        return DriverImpact(
            grid_position_delta=self.grid_position_delta + other.grid_position_delta,
            pace_delta_seconds_per_lap=self.pace_delta_seconds_per_lap
            + other.pace_delta_seconds_per_lap,
            # Uncertainties add in quadrature.
            pace_uncertainty_delta=(
                self.pace_uncertainty_delta**2 + other.pace_uncertainty_delta**2
            )
            ** 0.5,
            dnf_log_odds_delta=self.dnf_log_odds_delta + other.dnf_log_odds_delta,
            wet_performance_delta=self.wet_performance_delta + other.wet_performance_delta,
        )


class EventImpactModel:
    def __init__(self, priors: ImpactPriors | None = None) -> None:
        self.priors = priors or load_impact_priors()

    def _weight(self, event: ExtractedF1Event, as_of: datetime) -> float:
        d = self.priors.defaults
        conf = event.event_confidence * event.extraction_confidence
        confirm_scale = 1.0 if event.is_confirmed else d.unconfirmed_impact_scale
        hours = max(0.0, (as_of - event.first_seen_at).total_seconds() / 3600.0)
        half_life = (
            d.half_life_confirmed_hours if event.is_confirmed else d.half_life_unconfirmed_hours
        )
        decay = 0.5 ** (hours / max(1e-6, half_life))
        return float(conf * confirm_scale * decay)

    def impact_of(self, event: ExtractedF1Event, as_of: datetime) -> DriverImpact:
        w = self._weight(event, as_of)
        unc_scale = (
            1.0 if event.is_confirmed else self.priors.defaults.unconfirmed_uncertainty_scale
        )
        pace = (event.pace_delta_seconds_per_lap or 0.0) * w
        base_unc = event.pace_uncertainty_delta
        if base_unc is None:
            base_unc = abs(event.pace_delta_seconds_per_lap or 0.0) * 0.5
        return DriverImpact(
            grid_position_delta=(event.grid_position_delta or 0.0) * w,
            pace_delta_seconds_per_lap=pace,
            pace_uncertainty_delta=base_unc * unc_scale * (0.5 + 0.5 * w),
            dnf_log_odds_delta=(event.dnf_log_odds_delta or 0.0) * w,
            wet_performance_delta=(event.wet_performance_delta or 0.0) * w,
        )

    def aggregate(self, events: list[ExtractedF1Event], as_of: datetime) -> dict[str, DriverImpact]:
        """Per-driver aggregated impact from all events available at ``as_of``."""
        out: dict[str, DriverImpact] = {}
        for event in events:
            if not event.is_available_at(as_of):
                continue
            impact = self.impact_of(event, as_of)
            for driver_id in event.drivers:
                out[driver_id] = out.get(driver_id, DriverImpact()).combine(impact)
        return out


class NewsAdjustedInputs(BaseModel):
    """Convenience container for feeding aggregated impacts into models."""

    grid_delta: dict[str, float] = Field(default_factory=dict)
    pace_delta: dict[str, float] = Field(default_factory=dict)
    dnf_log_odds_delta: dict[str, float] = Field(default_factory=dict)


def to_model_inputs(impacts: dict[str, DriverImpact]) -> NewsAdjustedInputs:
    return NewsAdjustedInputs(
        grid_delta={d: i.grid_position_delta for d, i in impacts.items()},
        pace_delta={d: i.pace_delta_seconds_per_lap for d, i in impacts.items()},
        dnf_log_odds_delta={d: i.dnf_log_odds_delta for d, i in impacts.items()},
    )
