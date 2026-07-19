"""Data-quality checks over event logs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apexsignal.domain.events import DomainEvent, EventType
from apexsignal.ingestion.fixtures_adapter import demo_race_events
from apexsignal.ingestion.normalization import run_quality_checks

T0 = datetime(2024, 6, 9, 13, 0, tzinfo=UTC)


def _lap(driver: str, lap: int, offset: int, **payload: object) -> DomainEvent:
    t = T0 + timedelta(seconds=offset)
    base = {"lap": lap, "position": 1, "lap_time": 90.0, "tyre": "medium", "tyre_age": lap}
    base.update(payload)
    return DomainEvent(
        event_type=EventType.LAP_COMPLETED,
        source="test",
        event_time=t,
        first_seen_at=t,
        ingested_at=t,
        meeting_id="m",
        session_id="m-R",
        driver_id=driver,
        payload=base,
    )


def _codes(events: list[DomainEvent]) -> set[str]:
    return {i.code for i in run_quality_checks(events).issues}


def test_clean_fixture_has_no_errors() -> None:
    report = run_quality_checks(demo_race_events())
    assert report.ok is True
    assert report.n_errors == 0


def test_duplicate_lap_detected() -> None:
    assert "duplicate_lap" in _codes([_lap("A", 1, 1), _lap("A", 1, 2)])


def test_lap_out_of_order_detected() -> None:
    assert "lap_out_of_order" in _codes([_lap("A", 3, 1), _lap("A", 2, 2)])


def test_position_out_of_range_detected() -> None:
    assert "position_out_of_range" in _codes([_lap("A", 1, 1, position=99)])


def test_nonpositive_lap_time_detected() -> None:
    assert "nonpositive_lap_time" in _codes([_lap("A", 1, 1, lap_time=0.0)])


def test_tyre_age_decrease_without_change_warns() -> None:
    codes = _codes([_lap("A", 1, 1, tyre_age=5), _lap("A", 2, 2, tyre_age=2)])
    assert "tyre_age_decreased" in codes


def test_backward_timestamp_detected_on_raw_order() -> None:
    later = _lap("A", 1, 100)
    earlier = _lap("A", 2, 1)
    # As-given order goes backward in time between the two events.
    assert "timestamp_backward" in _codes([later, earlier])


def test_pit_exit_before_entry_detected() -> None:
    t = T0 + timedelta(seconds=5)
    exit_event = DomainEvent(
        event_type=EventType.PIT_EXIT,
        source="test",
        event_time=t,
        first_seen_at=t,
        ingested_at=t,
        meeting_id="m",
        session_id="m-R",
        driver_id="A",
        payload={},
    )
    assert "pit_exit_before_entry" in _codes([exit_event])


def test_implausible_weather_warns() -> None:
    t = T0 + timedelta(seconds=5)
    weather = DomainEvent(
        event_type=EventType.WEATHER_UPDATED,
        source="test",
        event_time=t,
        first_seen_at=t,
        ingested_at=t,
        meeting_id="m",
        session_id="m-R",
        payload={"track_temp": 300.0, "air_temp": 20.0},
    )
    assert "track_temp_implausible" in _codes([weather])
