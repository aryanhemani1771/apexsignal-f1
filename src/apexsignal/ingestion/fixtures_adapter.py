"""Load bundled fixture bundles into domain events (offline, deterministic).

Fixtures are small, synthetic, and credential-free — they keep CI and the public demo
running without any external calls. See ``data/fixtures/README.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

from apexsignal.domain.events import DomainEvent
from apexsignal.domain.news import NewsDocument
from apexsignal.intelligence.entity_resolution import Roster

# repo_root/src/apexsignal/ingestion/fixtures_adapter.py -> repo_root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = _REPO_ROOT / "data" / "fixtures"
DEMO_RACE_PATH = _FIXTURES_DIR / "demo_race" / "events.json"
DEMO_NEWS_PATH = _FIXTURES_DIR / "news" / "documents.json"
# A bundled REAL race: the 2026 British GP, normalized from FastF1 timing data (factual
# historical data). Real driver codes and real events (laps, safety car, pit stops).
REAL_RACE_PATH = _FIXTURES_DIR / "real_race" / "events.jsonl"
REAL_RACE_NAME = "2026 British Grand Prix"
REAL_RACE_TOTAL_LAPS = 52


def load_events_json(path: str | Path) -> list[DomainEvent]:
    """Load a fixture ``events.json`` (``{"meta": ..., "events": [...]}``) into events."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [DomainEvent.model_validate(e) for e in raw["events"]]


def demo_race_events() -> list[DomainEvent]:
    """The bundled synthetic 'Demo Grand Prix' event log."""
    return load_events_json(DEMO_RACE_PATH)


def real_race_events() -> list[DomainEvent]:
    """The bundled REAL 2023 Bahrain GP event log (real drivers and events)."""
    from apexsignal.storage.event_store import AppendOnlyEventStore

    return AppendOnlyEventStore.from_jsonl(REAL_RACE_PATH).events()


def demo_news_documents(path: str | Path | None = None) -> list[NewsDocument]:
    """The bundled synthetic news documents (invented drivers/teams)."""
    raw = json.loads(Path(path or DEMO_NEWS_PATH).read_text(encoding="utf-8"))
    return [NewsDocument.model_validate(d) for d in raw["documents"]]


def demo_news_roster(path: str | Path | None = None) -> Roster:
    """The invented-driver roster that matches the news fixtures."""
    raw = json.loads(Path(path or DEMO_NEWS_PATH).read_text(encoding="utf-8"))
    return Roster.model_validate(raw["meta"]["roster"])
