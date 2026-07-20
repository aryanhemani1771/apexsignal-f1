"""News domain: raw documents and the strict extracted-event schema.

Only metadata, permitted excerpts, timestamps, and structured extractions are retained — never
redistributed full copyrighted articles. ``ExtractedF1Event`` mirrors the build spec and carries
provenance (``first_seen_at`` is the authoritative availability timestamp for backtesting).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from apexsignal.intelligence.event_ontology import F1EventType


class SourceClass(StrEnum):
    FIA_DOCUMENT = "fia_document"
    OFFICIAL_TEAM = "official_team"
    OFFICIAL_CHAMPIONSHIP = "official_championship"
    NAMED_JOURNALIST = "named_journalist"
    SPECIALIST_PUB = "specialist_pub"
    GENERAL_PUB = "general_pub"
    AGGREGATOR = "aggregator"
    ANONYMOUS_SOCIAL = "anonymous_social"


class NewsDocument(BaseModel):
    """A raw news item — metadata + permitted text only."""

    doc_id: UUID = Field(default_factory=uuid4)
    title: str
    text: str  # permitted excerpt / summary, not a full copyrighted article
    source_url: str
    source_class: SourceClass
    published_at: datetime
    first_seen_at: datetime
    meeting_id: str | None = None


class ExtractedF1Event(BaseModel):
    """A structured, provenance-aware event extracted from a news document."""

    model_config = ConfigDict()

    event_id: UUID = Field(default_factory=uuid4)
    event_type: F1EventType
    drivers: list[str] = Field(default_factory=list)
    constructors: list[str] = Field(default_factory=list)
    meeting_id: str | None = None
    session_type: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    # Quantitative effect sizes (only set when supported by a configured prior).
    grid_position_delta: float | None = None
    pace_delta_seconds_per_lap: float | None = None
    pace_uncertainty_delta: float | None = None
    dnf_log_odds_delta: float | None = None
    pit_loss_delta_seconds: float | None = None
    wet_performance_delta: float | None = None

    source_type: SourceClass
    source_reliability: float
    extraction_confidence: float
    event_confidence: float

    factual_summary: str
    supporting_excerpt: str | None = None
    source_url: str
    published_at: datetime
    first_seen_at: datetime

    is_confirmed: bool = False
    contradicts_event_ids: list[UUID] = Field(default_factory=list)
    supersedes_event_ids: list[UUID] = Field(default_factory=list)

    def is_available_at(self, as_of: datetime) -> bool:
        """Point-in-time availability for backtesting (no future leakage)."""
        return as_of >= self.first_seen_at
