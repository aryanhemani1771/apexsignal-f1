"""Event → model-parameter impact mapping and telemetry confirmation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apexsignal.domain.news import ExtractedF1Event, SourceClass
from apexsignal.intelligence.event_impact import EventImpactModel
from apexsignal.intelligence.event_ontology import F1EventType
from apexsignal.intelligence.telemetry_confirmation import confirm_with_telemetry

T0 = datetime(2099, 1, 1, tzinfo=UTC)


def _event(*, confirmed: bool, pace: float = -0.2, seen: datetime = T0) -> ExtractedF1Event:
    return ExtractedF1Event(
        event_type=F1EventType.AERODYNAMIC_UPGRADE,
        drivers=["BO4"],
        source_type=SourceClass.OFFICIAL_TEAM if confirmed else SourceClass.AGGREGATOR,
        source_reliability=0.9 if confirmed else 0.35,
        extraction_confidence=0.8,
        event_confidence=0.9 if confirmed else 0.2,
        is_confirmed=confirmed,
        factual_summary="upgrade",
        source_url="x",
        published_at=seen,
        first_seen_at=seen,
        pace_delta_seconds_per_lap=pace,
    )


def test_confirmed_impact_exceeds_unconfirmed() -> None:
    m = EventImpactModel()
    conf = m.impact_of(_event(confirmed=True), T0)
    rumour = m.impact_of(_event(confirmed=False), T0)
    assert abs(conf.pace_delta_seconds_per_lap) > abs(rumour.pace_delta_seconds_per_lap)
    # Unconfirmed carries wider pace uncertainty.
    assert rumour.pace_uncertainty_delta > 0


def test_impact_decays_over_time() -> None:
    m = EventImpactModel()
    fresh = m.impact_of(_event(confirmed=False), T0)
    stale = m.impact_of(_event(confirmed=False), T0 + timedelta(days=7))
    assert abs(stale.pace_delta_seconds_per_lap) < abs(fresh.pace_delta_seconds_per_lap)


def test_aggregate_sums_per_driver() -> None:
    m = EventImpactModel()
    events = [_event(confirmed=True, pace=-0.1), _event(confirmed=True, pace=-0.1)]
    agg = m.aggregate(events, T0)
    single = m.impact_of(_event(confirmed=True, pace=-0.1), T0)
    assert abs(agg["BO4"].pace_delta_seconds_per_lap - 2 * single.pace_delta_seconds_per_lap) < 1e-9


def test_availability_gates_impact() -> None:
    m = EventImpactModel()
    future = _event(confirmed=True, seen=T0 + timedelta(days=1))
    assert m.aggregate([future], T0) == {}  # not yet seen at as_of


def test_telemetry_confirms_reduces_reverses() -> None:
    confirmed = confirm_with_telemetry(-0.2, 0.15, -0.25)
    assert confirmed.verdict == "confirmed"
    assert confirmed.posterior_uncertainty < 0.15  # evidence tightens the estimate

    reduced = confirm_with_telemetry(-0.2, 0.15, -0.05)
    assert reduced.verdict == "reduced"

    reversed_ = confirm_with_telemetry(-0.2, 0.15, 0.2)
    assert reversed_.verdict == "reversed"
    assert reversed_.posterior_pace_delta > 0
