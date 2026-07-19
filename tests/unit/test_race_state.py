"""Race-state reducer and deterministic replay."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from apexsignal.domain.events import DomainEvent, EventType
from apexsignal.domain.race_state import TrackStatus, replay, replay_states
from apexsignal.ingestion.fixtures_adapter import demo_race_events

T0 = datetime(2024, 6, 9, 13, 0, tzinfo=UTC)


def _lap(
    driver: str, lap: int, position: int, *, tyre: str = "medium", age: int = 1
) -> DomainEvent:
    t = T0 + timedelta(seconds=lap * 90 + position)
    return DomainEvent(
        event_type=EventType.LAP_COMPLETED,
        source="test",
        event_time=t,
        first_seen_at=t,
        ingested_at=t,
        meeting_id="m",
        session_id="m-R",
        driver_id=driver,
        payload={
            "lap": lap,
            "position": position,
            "lap_time": 90.0 + position,
            "tyre": tyre,
            "tyre_age": age,
        },
    )


def test_replay_demo_fixture_state() -> None:
    final = replay(demo_race_events())
    assert final.current_lap == 1
    assert final.track_status == TrackStatus.SAFETY_CAR
    assert final.drivers["AX7"].position == 1
    assert final.drivers["BO4"].position == 2
    # BO4 pitted onto hard tyres during the safety car.
    assert final.drivers["BO4"].pit_stop_count == 1
    assert final.drivers["BO4"].tyre_compound == "hard"
    assert final.drivers["BO4"].tyre_age == 0
    assert final.drivers["BO4"].stint_number == 2


def test_replay_is_order_independent_and_deterministic() -> None:
    events = demo_race_events()
    shuffled = events[:]
    random.Random(1).shuffle(shuffled)
    a = replay(events)
    b = replay(shuffled)
    assert a.model_dump() == b.model_dump()
    assert a.data_snapshot_id == b.data_snapshot_id


def test_replay_states_length_matches_events() -> None:
    events = demo_race_events()
    assert len(replay_states(events)) == len(events)


def test_pit_stop_resets_tyre_and_increments_stint() -> None:
    events = [
        _lap("VER", 1, 1, tyre="soft", age=1),
        _lap("VER", 2, 1, tyre="soft", age=2),
        DomainEvent(
            event_type=EventType.PIT_STOP_COMPLETED,
            source="test",
            event_time=T0 + timedelta(seconds=200),
            first_seen_at=T0 + timedelta(seconds=200),
            ingested_at=T0 + timedelta(seconds=200),
            meeting_id="m",
            session_id="m-R",
            driver_id="VER",
            payload={"new_tyre": "hard"},
        ),
        _lap("VER", 3, 1, tyre="hard", age=1),
    ]
    final = replay(events)
    drv = final.drivers["VER"]
    assert drv.pit_stop_count == 1
    assert drv.stint_number == 2
    assert drv.tyre_compound == "hard"
    assert drv.lap_number == 3


def test_retirement_marks_driver_not_running() -> None:
    events = [
        _lap("PER", 1, 5),
        DomainEvent(
            event_type=EventType.DRIVER_RETIRED,
            source="test",
            event_time=T0 + timedelta(seconds=300),
            first_seen_at=T0 + timedelta(seconds=300),
            ingested_at=T0 + timedelta(seconds=300),
            meeting_id="m",
            session_id="m-R",
            driver_id="PER",
            payload={},
        ),
    ]
    final = replay(events)
    assert final.drivers["PER"].retired is True
    assert final.drivers["PER"].running is False
