"""Real mid-race pricing sanity check (network-gated).

Skipped unless ``RUN_FASTF1_TESTS=1`` and ``fastf1`` is installed. Downloads the 2023 Bahrain
GP, rewinds to lap 30, and checks the simulated continuation favours the actual leader/winner.

    RUN_FASTF1_TESTS=1 uv run --extra data pytest tests/integration/test_pricing_real.py
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_ENABLED = os.environ.get("RUN_FASTF1_TESTS") == "1"
if not _ENABLED:
    pytest.skip("set RUN_FASTF1_TESTS=1 to run the networked pricing test", allow_module_level=True)
pytest.importorskip("fastf1")


def test_bahrain_2023_midrace_favours_leader() -> None:
    from apexsignal.domain.events import EventType
    from apexsignal.domain.race_state import replay
    from apexsignal.ingestion.fastf1_adapter import FastF1Adapter
    from apexsignal.services.pricing_service import price_from_state
    from apexsignal.simulation.engine import SimConfig

    events = FastF1Adapter().load_session_events(2023, 1, "R")
    at_lap, total_laps = 30, 57
    cutoff = max(
        e.event_time
        for e in events
        if e.event_type is EventType.LAP_COMPLETED and int(e.payload.get("lap", 0)) <= at_lap
    )
    subset = [e for e in events if e.event_time <= cutoff]
    state = replay(subset)

    prices = price_from_state(
        state, subset, total_laps=total_laps, config=SimConfig(n_paths=3000, seed=42)
    )
    wins = prices.win_probs()
    # Verstappen led and won from here; he should be the clear favourite.
    assert wins["VER"] == max(wins.values())
    assert wins["VER"] > 0.4
    # A retired-early / lapped driver must not be pushed to the front (the fixed gap logic).
    assert prices.drivers["PIA"].win < 0.05
