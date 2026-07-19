"""Deterministic race-state reducer.

The race state is a pure function of the ordered event log: ``replay(events)`` folds the
log through :func:`apply_event`, and replaying the same log always yields identical state.
This is the substrate every model and the dashboard replay page read from.

Only fields that current Phase 1 events populate are filled; the richer per-driver fields
described in the build spec (clean-air pace, hazards, uncertainty) arrive in Phases 2-4.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from apexsignal import __version__
from apexsignal.domain.events import DomainEvent, EventType, sort_key

_RECENT_EVENTS_KEPT = 12


class TrackStatus:
    CLEAR = "clear"
    YELLOW = "yellow"
    SAFETY_CAR = "safety_car"
    RED = "red"


class DriverState(BaseModel):
    """Per-driver running state at a point in time."""

    driver_id: str
    constructor_id: str | None = None
    position: int | None = None
    lap_number: int = 0
    tyre_compound: str | None = None
    tyre_age: int | None = None
    stint_number: int = 1
    pit_stop_count: int = 0
    last_lap_time: float | None = None
    retired: bool = False
    running: bool = True


class RaceState(BaseModel):
    """The full race state produced by folding the event log."""

    meeting_id: str
    session_id: str
    timestamp: datetime | None = None
    current_lap: int = 0
    total_laps: int | None = None
    track_status: str = TrackStatus.CLEAR
    session_status: str | None = None
    weather: dict[str, Any] = Field(default_factory=dict)
    drivers: dict[str, DriverState] = Field(default_factory=dict)
    recent_events: list[str] = Field(default_factory=list)
    events_applied: int = 0
    model_version: str = __version__
    data_snapshot_id: str | None = None


def initial_state(meeting_id: str, session_id: str) -> RaceState:
    """Return an empty state for a session."""
    return RaceState(meeting_id=meeting_id, session_id=session_id)


def _with_driver(state: RaceState, driver_id: str, **changes: Any) -> dict[str, DriverState]:
    """Return a new drivers mapping with ``driver_id`` upserted and updated."""
    drivers = dict(state.drivers)
    current = drivers.get(driver_id, DriverState(driver_id=driver_id))
    drivers[driver_id] = current.model_copy(update=changes)
    return drivers


def _record(state_events: list[str], event: DomainEvent) -> list[str]:
    label = event.event_type.value
    who = event.driver_id or event.constructor_id or ""
    entry = f"{label}:{who}".rstrip(":")
    return [*state_events[-(_RECENT_EVENTS_KEPT - 1) :], entry]


def apply_event(state: RaceState, event: DomainEvent) -> RaceState:
    """Fold a single event into the state, returning a new :class:`RaceState`."""
    payload = event.payload
    updates: dict[str, Any] = {
        "timestamp": event.event_time,
        "events_applied": state.events_applied + 1,
        "recent_events": _record(state.recent_events, event),
    }

    et = event.event_type
    did = event.driver_id

    if et is EventType.LAP_COMPLETED and did is not None:
        lap = int(payload.get("lap", state.drivers.get(did, DriverState(driver_id=did)).lap_number))
        updates["drivers"] = _with_driver(
            state,
            did,
            constructor_id=event.constructor_id,
            lap_number=lap,
            position=payload.get("position"),
            last_lap_time=payload.get("lap_time"),
            tyre_compound=payload.get("tyre"),
            tyre_age=payload.get("tyre_age"),
        )
        updates["current_lap"] = max(state.current_lap, lap)

    elif et is EventType.POSITION_CHANGED and did is not None:
        updates["drivers"] = _with_driver(state, did, position=payload.get("position"))

    elif et is EventType.PIT_STOP_COMPLETED and did is not None:
        current = state.drivers.get(did, DriverState(driver_id=did))
        updates["drivers"] = _with_driver(
            state,
            did,
            pit_stop_count=current.pit_stop_count + 1,
            stint_number=current.stint_number + 1,
            tyre_compound=payload.get("new_tyre", current.tyre_compound),
            tyre_age=0,
        )

    elif et is EventType.TYRE_COMPOUND_CHANGED and did is not None:
        updates["drivers"] = _with_driver(
            state, did, tyre_compound=payload.get("compound"), tyre_age=0
        )

    elif et in (EventType.DRIVER_RETIRED, EventType.DRIVER_STOPPED) and did is not None:
        updates["drivers"] = _with_driver(state, did, retired=True, running=False)

    elif et is EventType.SAFETY_CAR_DEPLOYED:
        updates["track_status"] = TrackStatus.SAFETY_CAR
    elif et is EventType.YELLOW_FLAG_STARTED:
        updates["track_status"] = TrackStatus.YELLOW
    elif et is EventType.RED_FLAG_STARTED:
        updates["track_status"] = TrackStatus.RED
        updates["session_status"] = "suspended"
    elif et is EventType.WEATHER_UPDATED:
        updates["weather"] = dict(payload)

    return state.model_copy(update=updates)


def _snapshot_id(event_ids: list[str]) -> str:
    digest = hashlib.sha256("|".join(event_ids).encode()).hexdigest()
    return digest[:16]


def replay(
    events: Iterable[DomainEvent],
    *,
    meeting_id: str | None = None,
    session_id: str | None = None,
) -> RaceState:
    """Replay an event log into a final :class:`RaceState` (deterministic)."""
    ordered = sorted(events, key=sort_key)
    if meeting_id is None or session_id is None:
        if not ordered:
            raise ValueError("replay() needs events or explicit meeting_id/session_id")
        meeting_id = meeting_id or ordered[0].meeting_id or "unknown"
        session_id = session_id or ordered[0].session_id or "unknown"

    state = initial_state(meeting_id, session_id)
    applied_ids: list[str] = []
    for event in ordered:
        state = apply_event(state, event)
        applied_ids.append(str(event.event_id))
    return state.model_copy(update={"data_snapshot_id": _snapshot_id(applied_ids)})


def replay_states(events: Iterable[DomainEvent]) -> list[RaceState]:
    """Return the state after each event, for stepping/replay UIs."""
    ordered = sorted(events, key=sort_key)
    if not ordered:
        return []
    meeting_id = ordered[0].meeting_id or "unknown"
    session_id = ordered[0].session_id or "unknown"
    state = initial_state(meeting_id, session_id)
    history: list[RaceState] = []
    for event in ordered:
        state = apply_event(state, event)
        history.append(state)
    return history
