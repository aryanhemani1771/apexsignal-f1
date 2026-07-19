"""Load bundled fixture bundles into domain events (offline, deterministic).

Fixtures are small, synthetic, and credential-free — they keep CI and the public demo
running without any external calls. See ``data/fixtures/README.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

from apexsignal.domain.events import DomainEvent

# repo_root/src/apexsignal/ingestion/fixtures_adapter.py -> repo_root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = _REPO_ROOT / "data" / "fixtures"
DEMO_RACE_PATH = _FIXTURES_DIR / "demo_race" / "events.json"


def load_events_json(path: str | Path) -> list[DomainEvent]:
    """Load a fixture ``events.json`` (``{"meta": ..., "events": [...]}``) into events."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [DomainEvent.model_validate(e) for e in raw["events"]]


def demo_race_events() -> list[DomainEvent]:
    """The bundled synthetic 'Demo Grand Prix' event log."""
    return load_events_json(DEMO_RACE_PATH)
