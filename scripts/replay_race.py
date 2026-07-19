"""Replay a race event log deterministically in the terminal — no credentials required.

By default it replays the bundled synthetic demo race. Point it at a JSONL event log
(produced by ``download_history.py``) to replay a real race you have downloaded.

    uv run python scripts/replay_race.py
    uv run python scripts/replay_race.py --file data/raw/2024_10_R.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from apexsignal.domain.events import DomainEvent
from apexsignal.domain.race_state import RaceState, replay, replay_states
from apexsignal.ingestion.fixtures_adapter import demo_race_events
from apexsignal.ingestion.normalization import run_quality_checks
from apexsignal.storage.event_store import AppendOnlyEventStore


def _load(path: str | None) -> list[DomainEvent]:
    if path is None:
        return demo_race_events()
    return AppendOnlyEventStore.from_jsonl(Path(path)).events()


def _standings(state: RaceState) -> list[tuple[int, str]]:
    ranked = [
        (d.position, did)
        for did, d in state.drivers.items()
        if d.position is not None and not d.retired
    ]
    return sorted(ranked)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic race replay")
    parser.add_argument("--file", help="JSONL event log (defaults to the bundled demo race)")
    args = parser.parse_args()

    events = _load(args.file)
    if not events:
        print("No events to replay.")
        return 1

    quality = run_quality_checks(events)
    history = replay_states(events)
    final = replay(events)

    print(f"Replaying {len(events)} events across {final.current_lap} lap(s)...\n")
    last_lap = -1
    for state in history:
        if state.current_lap != last_lap:
            last_lap = state.current_lap
            leaders = ", ".join(f"P{p} {d}" for p, d in _standings(state)[:3])
            print(f"  lap {state.current_lap:>2} | track={state.track_status:<10} {leaders}")

    print("\nFinal classification:")
    for pos, did in _standings(final):
        drv = final.drivers[did]
        tyre = f"{drv.tyre_compound}/{drv.tyre_age}" if drv.tyre_compound else "-"
        print(f"  P{pos:<2} {did:<6} stops={drv.pit_stop_count} tyre={tyre}")
    retired = [did for did, d in final.drivers.items() if d.retired]
    if retired:
        print(f"  DNF: {', '.join(retired)}")

    print(f"\nData quality: {quality.summary()}")
    print(f"Snapshot id: {final.data_snapshot_id}")
    return 0 if quality.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
