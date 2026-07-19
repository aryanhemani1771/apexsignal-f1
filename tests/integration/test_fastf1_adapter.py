"""FastF1 adapter integration test.

Gated: it hits the network and needs the optional ``data`` extra, so it is skipped unless
``RUN_FASTF1_TESTS=1`` is set AND ``fastf1`` is importable. This keeps CI offline and green
while still allowing a real end-to-end verification on demand:

    RUN_FASTF1_TESTS=1 uv run --extra data pytest tests/integration/test_fastf1_adapter.py
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_ENABLED = os.environ.get("RUN_FASTF1_TESTS") == "1"
fastf1 = pytest.importorskip("fastf1") if _ENABLED else None

if not _ENABLED:
    pytest.skip("set RUN_FASTF1_TESTS=1 to run the networked FastF1 test", allow_module_level=True)


def test_download_and_replay_real_race(tmp_path: object) -> None:
    from apexsignal.domain.race_state import replay
    from apexsignal.ingestion.fastf1_adapter import FastF1Adapter
    from apexsignal.ingestion.normalization import run_quality_checks

    adapter = FastF1Adapter(cache_dir=str(tmp_path))
    events = adapter.load_session_events(2023, 1, "R")

    assert len(events) > 100
    report = run_quality_checks(events)
    # Real timing data may carry warnings, but should not fail hard integrity checks.
    assert report.n_errors == 0, report.summary()

    final = replay(events)
    assert final.current_lap > 40
    assert any(d.position == 1 for d in final.drivers.values())
