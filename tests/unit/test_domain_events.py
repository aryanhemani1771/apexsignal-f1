"""Domain event envelope invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from apexsignal.domain.events import (
    SCHEMA_VERSION,
    DomainEvent,
    EventType,
    sort_key,
)

T0 = datetime(2024, 6, 9, 13, 0, tzinfo=UTC)


def _event(**overrides: object) -> DomainEvent:
    # Default provenance tracks event_time so callers can shift the world clock without
    # tripping the causal-order guard; explicit overrides still win (used by the guards below).
    event_time = overrides.pop("event_time", T0)
    assert isinstance(event_time, datetime)
    base: dict[str, object] = {
        "event_type": EventType.LAP_COMPLETED,
        "source": "fastf1",
        "event_time": event_time,
        "first_seen_at": event_time,
        "ingested_at": event_time + timedelta(seconds=1),
        "meeting_id": "2024-09",
        "session_id": "2024-09-R",
        "driver_id": "VER",
        "payload": {"lap": 12, "lap_time": 91.234},
    }
    base.update(overrides)
    return DomainEvent(**base)  # type: ignore[arg-type]


def test_valid_event_defaults() -> None:
    e = _event()
    assert e.schema_version == SCHEMA_VERSION
    assert e.event_id is not None
    assert e.availability_time == e.first_seen_at


def test_event_is_immutable() -> None:
    e = _event()
    with pytest.raises(ValidationError):
        e.driver_id = "NOR"  # type: ignore[misc]


def test_is_available_at() -> None:
    e = _event()
    assert e.is_available_at(T0) is True
    assert e.is_available_at(T0 + timedelta(minutes=5)) is True
    assert e.is_available_at(T0 - timedelta(seconds=1)) is False


def test_seen_before_happening_is_rejected() -> None:
    with pytest.raises(ValidationError, match="first_seen_at"):
        _event(first_seen_at=T0 - timedelta(seconds=1))


def test_ingested_before_seen_is_rejected() -> None:
    with pytest.raises(ValidationError, match="ingested_at"):
        _event(first_seen_at=T0, ingested_at=T0 - timedelta(seconds=1))


def test_sort_key_orders_by_world_then_observation_time() -> None:
    a = _event(event_time=T0)
    b = _event(event_time=T0 + timedelta(seconds=2))
    ordered = sorted([b, a], key=sort_key)
    assert ordered == [a, b]
