"""Contradiction detection and supersession.

Detects conflicting reports (e.g. a rumour later contradicted by a confirmation, or two
different grid penalties for the same driver) and applies supersession: a later confirmed event
replaces an earlier unconfirmed one of the same type/entities without deleting history.
"""

from __future__ import annotations

from pydantic import BaseModel

from apexsignal.domain.news import ExtractedF1Event

_GRID_DELTA_TOL = 2.0  # positions difference that counts as a conflicting penalty


class Contradiction(BaseModel):
    reason: str
    event_a_id: str
    event_b_id: str


def _entities(e: ExtractedF1Event) -> tuple[str, ...]:
    return tuple(sorted([*e.drivers, *e.constructors]))


def find_contradictions(events: list[ExtractedF1Event]) -> list[Contradiction]:
    """Pairwise contradictions among events touching the same type + entities."""
    out: list[Contradiction] = []
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            a, b = events[i], events[j]
            if a.event_type != b.event_type or _entities(a) != _entities(b):
                continue
            if a.is_confirmed != b.is_confirmed:
                out.append(
                    Contradiction(
                        reason="rumour vs confirmation",
                        event_a_id=str(a.event_id),
                        event_b_id=str(b.event_id),
                    )
                )
            elif (
                a.grid_position_delta is not None
                and b.grid_position_delta is not None
                and abs(a.grid_position_delta - b.grid_position_delta) > _GRID_DELTA_TOL
            ):
                out.append(
                    Contradiction(
                        reason="conflicting grid penalty",
                        event_a_id=str(a.event_id),
                        event_b_id=str(b.event_id),
                    )
                )
    return out


def apply_supersession(events: list[ExtractedF1Event]) -> list[ExtractedF1Event]:
    """Return the active events: a later confirmed event supersedes an earlier unconfirmed one.

    History is preserved (nothing deleted); the surviving event records ``supersedes_event_ids``.
    """
    ordered = sorted(events, key=lambda e: e.first_seen_at)
    superseded: set[str] = set()
    for i, later in enumerate(ordered):
        if not later.is_confirmed:
            continue
        for earlier in ordered[:i]:
            same = later.event_type == earlier.event_type and _entities(later) == _entities(earlier)
            if same and not earlier.is_confirmed and str(earlier.event_id) not in superseded:
                superseded.add(str(earlier.event_id))
                later.supersedes_event_ids.append(earlier.event_id)
    return [e for e in ordered if str(e.event_id) not in superseded]
