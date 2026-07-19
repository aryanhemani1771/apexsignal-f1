"""End-to-end pricing from a race state + event log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apexsignal.domain.events import DomainEvent, EventType
from apexsignal.domain.race_state import replay
from apexsignal.services.pricing_service import price_from_state
from apexsignal.simulation.engine import SimConfig

T0 = datetime(2024, 1, 1, 14, 0, tzinfo=UTC)
# Base lap times: A fastest, then B, then C.
DRIVERS = {"A": 90.0, "B": 90.6, "C": 91.3}


def _events() -> list[DomainEvent]:
    events: list[DomainEvent] = []
    for lap in range(1, 16):
        for pos, (drv, base) in enumerate(sorted(DRIVERS.items(), key=lambda kv: kv[1]), 1):
            t = T0 + timedelta(seconds=lap * 95 + pos)
            events.append(
                DomainEvent(
                    event_type=EventType.LAP_COMPLETED,
                    source="test",
                    event_time=t,
                    first_seen_at=t,
                    ingested_at=t,
                    meeting_id="m",
                    session_id="m-R",
                    driver_id=drv,
                    constructor_id=f"t_{drv}",
                    payload={
                        "lap": lap,
                        "position": pos,
                        "lap_time": base + lap * 0.02,
                        "tyre": "medium",
                        "tyre_age": lap,
                    },
                )
            )
    return events


def test_price_from_state_leader_favoured() -> None:
    events = _events()
    state = replay(events)
    prices = price_from_state(state, events, total_laps=30, config=SimConfig(n_paths=1500, seed=3))
    wins = prices.win_probs()
    assert set(wins) == set(DRIVERS)
    assert wins["A"] == max(wins.values())  # fastest car most likely to win
    assert abs(sum(wins.values()) - 1.0) < 0.05
    assert prices.laps_simulated == 15  # laps 16..30
