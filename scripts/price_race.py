"""Price contracts from a mid-race state — Monte Carlo race-continuation pricing.

Loads a race (a downloaded JSONL event log, or live via FastF1), rewinds to a chosen lap,
and prices win/podium/points/DNF/fastest-lap/safety-car contracts from simulated continuations.
No credentials required for the JSONL path.

    uv run --extra data python scripts/price_race.py --season 2023 --round 1 --at-lap 30
    uv run python scripts/price_race.py --file data/raw/2023_1_R.jsonl --at-lap 30
"""

from __future__ import annotations

import argparse

from apexsignal.domain.events import DomainEvent, EventType
from apexsignal.domain.race_state import replay
from apexsignal.services.pricing_service import price_from_state
from apexsignal.settings import load_settings
from apexsignal.simulation.engine import SimConfig
from apexsignal.storage.event_store import AppendOnlyEventStore


def _load_events(args: argparse.Namespace) -> list[DomainEvent]:
    if args.file:
        return AppendOnlyEventStore.from_jsonl(args.file).events()
    from apexsignal.ingestion.fastf1_adapter import FastF1Adapter

    settings = load_settings()
    adapter = FastF1Adapter(cache_dir=settings.fastf1_cache_dir)
    return adapter.load_session_events(args.season, args.round, "R")


def _max_lap(events: list[DomainEvent]) -> int:
    laps = [
        int(e.payload["lap"])
        for e in events
        if e.event_type is EventType.LAP_COMPLETED and "lap" in e.payload
    ]
    return max(laps) if laps else 0


def _events_through_lap(events: list[DomainEvent], at_lap: int) -> list[DomainEvent]:
    cutoff = max(
        (
            e.event_time
            for e in events
            if e.event_type is EventType.LAP_COMPLETED and int(e.payload.get("lap", 0)) <= at_lap
        ),
        default=None,
    )
    if cutoff is None:
        return events
    return [e for e in events if e.event_time <= cutoff]


def main() -> int:
    parser = argparse.ArgumentParser(description="Monte Carlo mid-race contract pricing")
    parser.add_argument("--file", help="JSONL event log")
    parser.add_argument("--season", type=int)
    parser.add_argument("--round", type=int)
    parser.add_argument("--at-lap", type=int, default=None)
    parser.add_argument("--total-laps", type=int, default=None)
    parser.add_argument("--paths", type=int, default=5000)
    args = parser.parse_args()

    if not args.file and not (args.season and args.round):
        parser.error("provide --file or both --season and --round")

    events = _load_events(args)
    total_laps = args.total_laps or _max_lap(events)
    at_lap = args.at_lap or total_laps // 2
    subset = _events_through_lap(events, at_lap)
    state = replay(subset)

    prices = price_from_state(
        state,
        subset,
        total_laps=total_laps,
        config=SimConfig(n_paths=args.paths, seed=42),
        pit_before_lap=at_lap + 10,
    )

    print(f"Pricing after lap {state.current_lap} of {total_laps} ({prices.n_paths} paths).\n")
    print(f"{'driver':<8}{'win':>8}{'podium':>9}{'points':>9}{'dnf':>8}{'fastest':>9}")
    ranked = sorted(prices.drivers.values(), key=lambda p: -p.win)
    for p in ranked[:10]:
        print(
            f"{p.driver_id:<8}{p.win:>8.3f}{p.podium:>9.3f}{p.points:>9.3f}"
            f"{p.dnf:>8.3f}{p.fastest_lap:>9.3f}"
        )
    print(f"\nSafety car (remaining laps): {prices.safety_car:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
