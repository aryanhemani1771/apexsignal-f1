"""News intelligence pipeline: documents → structured, deduplicated, impact-mapped events.

Orchestrates extraction, supersession, deduplication, contradiction detection, impact mapping,
and sentiment. Produces a timeline that separates fundamental events (which move the model) from
public sentiment (which does not), plus a helper to apply impacts to a simulation input.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from pydantic import BaseModel

from apexsignal.domain.news import ExtractedF1Event, NewsDocument
from apexsignal.intelligence.contradiction import (
    Contradiction,
    apply_supersession,
    find_contradictions,
)
from apexsignal.intelligence.deduplication import CanonicalEvent, deduplicate
from apexsignal.intelligence.event_extractor import EventExtractor, RuleBasedExtractor
from apexsignal.intelligence.event_impact import DriverImpact, EventImpactModel
from apexsignal.intelligence.event_ontology import F1EventType, is_fundamental
from apexsignal.intelligence.sentiment import Sentiment, score_sentiment
from apexsignal.simulation.engine import SimInput


class TimelineItem(BaseModel):
    event_type: F1EventType
    fundamental: bool
    summary: str
    drivers: list[str]
    constructors: list[str]
    source_class: str
    published_at: datetime
    first_seen_at: datetime
    is_confirmed: bool
    evidence_count: int


class NewsPipelineResult(BaseModel):
    as_of: datetime
    active_events: list[ExtractedF1Event]
    canonical: list[CanonicalEvent]
    contradictions: list[Contradiction]
    impacts: dict[str, DriverImpact]
    sentiment: dict[str, Sentiment]  # keyed by document title
    timeline: list[TimelineItem]


def run_pipeline(
    documents: list[NewsDocument],
    *,
    extractor: EventExtractor | None = None,
    impact_model: EventImpactModel | None = None,
    as_of: datetime | None = None,
) -> NewsPipelineResult:
    extractor = extractor or RuleBasedExtractor()
    impact_model = impact_model or EventImpactModel()
    when = as_of or datetime.now(UTC)

    extracted: list[ExtractedF1Event] = []
    for doc in documents:
        extracted.extend(extractor.extract(doc))

    # Filter to what was observable at `when` BEFORE resolving supersession, so a future
    # confirmation can never retroactively supersede a rumour that was current at `when`.
    seen = [e for e in extracted if e.is_available_at(when)]
    available = apply_supersession(seen)
    canonical = deduplicate(available)
    contradictions = find_contradictions(available)
    impacts = impact_model.aggregate(available, when)
    sentiment = {doc.title: score_sentiment(f"{doc.title}. {doc.text}") for doc in documents}

    timeline = [
        TimelineItem(
            event_type=c.event.event_type,
            fundamental=is_fundamental(c.event.event_type),
            summary=c.event.factual_summary,
            drivers=c.event.drivers,
            constructors=c.event.constructors,
            source_class=c.event.source_type.value,
            published_at=c.event.published_at,
            first_seen_at=c.event.first_seen_at,
            is_confirmed=c.event.is_confirmed,
            evidence_count=c.evidence_count,
        )
        for c in canonical
    ]

    return NewsPipelineResult(
        as_of=when,
        active_events=available,
        canonical=canonical,
        contradictions=contradictions,
        impacts=impacts,
        sentiment=sentiment,
        timeline=timeline,
    )


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def apply_impacts_to_sim_input(sim: SimInput, impacts: dict[str, DriverImpact]) -> SimInput:
    """Fold aggregated news impacts into a simulation input (pace and DNF, per driver)."""
    data = sim.model_dump()
    ids = data["driver_ids"]
    pace = list(data["clean_air_pace"])
    dnf = list(data["race_dnf_prob"])
    for i, did in enumerate(ids):
        impact = impacts.get(did)
        if impact is None:
            continue
        pace[i] += impact.pace_delta_seconds_per_lap  # + = slower
        if impact.dnf_log_odds_delta:
            logit = math.log(max(1e-6, dnf[i]) / max(1e-6, 1 - dnf[i]))
            dnf[i] = min(0.95, _sigmoid(logit + impact.dnf_log_odds_delta))
    data["clean_air_pace"] = pace
    data["race_dnf_prob"] = dnf
    return SimInput(**data)
