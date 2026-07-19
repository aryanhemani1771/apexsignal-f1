"""Append-only event store.

Immutable domain events go in; nothing is ever mutated or deleted. Iteration always yields
events in deterministic replay order (:func:`apexsignal.domain.events.sort_key`). A simple
JSONL persistence format keeps fixtures and downloaded races portable and diff-friendly;
DuckDB/Parquet repositories (Phase 1+) can back the same interface for scale.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from apexsignal.domain.events import DomainEvent, sort_key


class AppendOnlyEventStore:
    """In-memory append-only store with JSONL load/save."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def append(self, event: DomainEvent) -> None:
        self._events.append(event)

    def extend(self, events: Iterable[DomainEvent]) -> None:
        self._events.extend(events)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[DomainEvent]:
        """Iterate in deterministic replay order (does not mutate insertion order)."""
        return iter(sorted(self._events, key=sort_key))

    def events(self) -> list[DomainEvent]:
        """Return all events in deterministic replay order."""
        return sorted(self._events, key=sort_key)

    def to_jsonl(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for event in self.events():
                fh.write(event.model_dump_json())
                fh.write("\n")
        return p

    @classmethod
    def from_jsonl(cls, path: str | Path) -> AppendOnlyEventStore:
        store = cls()
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    store.append(DomainEvent.model_validate_json(line))
        return store

    @classmethod
    def from_events(cls, events: Iterable[DomainEvent]) -> AppendOnlyEventStore:
        store = cls()
        store.extend(events)
        return store
