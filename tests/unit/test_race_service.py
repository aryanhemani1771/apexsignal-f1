"""Race-service display helpers."""

from __future__ import annotations

from apexsignal.services import race_service


def test_load_events_defaults_to_demo() -> None:
    events = race_service.load_events()
    assert len(events) == 4


def test_timing_rows_ordered_by_position() -> None:
    events = race_service.load_events()
    final = race_service.final_state(events)
    rows = race_service.timing_rows(final)
    positions = [r["P"] for r in rows if r["P"] != "DNF"]
    assert positions == sorted(p for p in positions if isinstance(p, int))
    drivers = {r["driver"] for r in rows}
    assert {"AX7", "BO4"} <= drivers


def test_replay_history_matches_event_count() -> None:
    events = race_service.load_events()
    assert len(race_service.replay_history(events)) == len(events)


def test_quality_report_clean_on_demo() -> None:
    report = race_service.quality_report(race_service.load_events())
    assert report.ok is True
