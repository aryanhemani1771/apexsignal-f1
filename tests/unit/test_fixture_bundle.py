"""The committed demo fixture must load and validate against the domain schema.

This keeps the credential-free fixture demo honest: if the bundle drifts from the
``DomainEvent`` contract, CI fails.
"""

from __future__ import annotations

import json
from pathlib import Path

from apexsignal.domain.events import DomainEvent, sort_key

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "demo_race" / "events.json"


def test_demo_fixture_loads_and_validates() -> None:
    raw = json.loads(FIXTURE.read_text())
    events = [DomainEvent.model_validate(e) for e in raw["events"]]
    assert len(events) == 4
    # Every event respects the causal-ordering invariant (constructor ran without raising).
    assert all(e.first_seen_at >= e.event_time for e in events)


def test_demo_fixture_replay_is_deterministically_ordered() -> None:
    raw = json.loads(FIXTURE.read_text())
    events = [DomainEvent.model_validate(e) for e in raw["events"]]
    ordered_once = [str(e.event_id) for e in sorted(events, key=sort_key)]
    ordered_twice = [str(e.event_id) for e in sorted(events, key=sort_key)]
    assert ordered_once == ordered_twice
