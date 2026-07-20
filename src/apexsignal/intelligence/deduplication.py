"""Deduplicate extracted events that describe the same real-world event.

Reports are clustered by event type, affected entities, and meeting. One canonical event is
kept per cluster (the most authoritative/confirmed), with the number of corroborating reports
recorded as evidence.
"""

from __future__ import annotations

from pydantic import BaseModel

from apexsignal.domain.news import ExtractedF1Event


def _cluster_key(e: ExtractedF1Event) -> tuple[str, tuple[str, ...], str | None]:
    entities = tuple(sorted([*e.drivers, *e.constructors]))
    return (e.event_type.value, entities, e.meeting_id)


class CanonicalEvent(BaseModel):
    event: ExtractedF1Event
    evidence_count: int
    corroborating_urls: list[str]


def deduplicate(events: list[ExtractedF1Event]) -> list[CanonicalEvent]:
    """Cluster equivalent reports; keep the most authoritative as canonical."""
    clusters: dict[tuple[str, tuple[str, ...], str | None], list[ExtractedF1Event]] = {}
    for e in events:
        clusters.setdefault(_cluster_key(e), []).append(e)

    out: list[CanonicalEvent] = []
    for members in clusters.values():
        # Prefer confirmed, then higher event confidence, then earlier first-seen.
        canonical = max(
            members,
            key=lambda e: (e.is_confirmed, e.event_confidence, -e.first_seen_at.timestamp()),
        )
        out.append(
            CanonicalEvent(
                event=canonical,
                evidence_count=len(members),
                corroborating_urls=sorted({m.source_url for m in members}),
            )
        )
    out.sort(key=lambda c: c.event.first_seen_at)
    return out
