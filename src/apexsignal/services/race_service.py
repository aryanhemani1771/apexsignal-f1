"""Race service: load event logs and expose replay-friendly views.

Pure, dependency-light functions shared by the CLI replay script and the dashboard replay
page, so the display logic is unit-tested independently of Streamlit.
"""

from __future__ import annotations

from pathlib import Path

from apexsignal.domain.events import DomainEvent
from apexsignal.domain.race_state import RaceState, replay, replay_states
from apexsignal.ingestion.fixtures_adapter import demo_race_events
from apexsignal.ingestion.normalization import DataQualityReport, run_quality_checks
from apexsignal.storage.event_store import AppendOnlyEventStore


def load_events(source: str | Path | None = None) -> list[DomainEvent]:
    """Load events from a JSONL log, or the bundled demo race when ``source`` is None."""
    if source is None:
        return demo_race_events()
    return AppendOnlyEventStore.from_jsonl(Path(source)).events()


def standings(state: RaceState) -> list[tuple[int, str]]:
    """Running order (position, driver_id) for classified, still-running cars."""
    ranked = [
        (d.position, did)
        for did, d in state.drivers.items()
        if d.position is not None and not d.retired
    ]
    return sorted(ranked)


def timing_rows(state: RaceState) -> list[dict[str, object]]:
    """A timing-tower view of the current state, ordered by position."""
    rows: list[dict[str, object]] = []
    for pos, did in standings(state):
        d = state.drivers[did]
        rows.append(
            {
                "P": pos,
                "driver": did,
                "constructor": d.constructor_id or "",
                "lap": d.lap_number,
                "tyre": d.tyre_compound or "",
                "tyre_age": d.tyre_age if d.tyre_age is not None else "",
                "stops": d.pit_stop_count,
                "last_lap": d.last_lap_time if d.last_lap_time is not None else "",
            }
        )
    for did, d in state.drivers.items():
        if d.retired:
            rows.append({"P": "DNF", "driver": did, "constructor": d.constructor_id or ""})
    return rows


def replay_history(events: list[DomainEvent]) -> list[RaceState]:
    """State after each event, for stepping/replay UIs."""
    return replay_states(events)


def final_state(events: list[DomainEvent]) -> RaceState:
    return replay(events)


def quality_report(events: list[DomainEvent]) -> DataQualityReport:
    return run_quality_checks(events)
