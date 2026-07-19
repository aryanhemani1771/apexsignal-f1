"""Append-only event store: ordering and JSONL round-trip."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from apexsignal.domain.events import DomainEvent, EventType
from apexsignal.storage.event_store import AppendOnlyEventStore

T0 = datetime(2024, 6, 9, 13, 0, tzinfo=UTC)


def _event(offset: int, driver: str) -> DomainEvent:
    t = T0 + timedelta(seconds=offset)
    return DomainEvent(
        event_type=EventType.LAP_COMPLETED,
        source="test",
        event_time=t,
        first_seen_at=t,
        ingested_at=t,
        meeting_id="m",
        session_id="m-R",
        driver_id=driver,
        payload={"lap": 1, "position": 1},
    )


def test_append_extend_len() -> None:
    store = AppendOnlyEventStore()
    store.append(_event(0, "A"))
    store.extend([_event(1, "B"), _event(2, "C")])
    assert len(store) == 3


def test_iteration_is_in_replay_order() -> None:
    store = AppendOnlyEventStore.from_events([_event(5, "A"), _event(1, "B"), _event(3, "C")])
    times = [e.event_time for e in store]
    assert times == sorted(times)


def test_jsonl_round_trip(tmp_path: Path) -> None:
    original = AppendOnlyEventStore.from_events([_event(2, "A"), _event(1, "B")])
    path = original.to_jsonl(tmp_path / "events.jsonl")
    restored = AppendOnlyEventStore.from_jsonl(path)
    assert [e.model_dump() for e in restored.events()] == [
        e.model_dump() for e in original.events()
    ]
