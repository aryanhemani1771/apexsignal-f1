"""Immutable domain events — the append-only substrate the race state is reduced from.

Replaying the ordered event log reproduces race state deterministically (Phase 1). The
envelope mirrors ``DATA_DICTIONARY.md`` and carries the provenance timestamps required by
the no-leakage rule.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apexsignal.domain.provenance import check_causal_order

SCHEMA_VERSION = 1


class EventType(StrEnum):
    """Domain event types (initial set; extend as phases land)."""

    LAP_COMPLETED = "LapCompleted"
    SECTOR_COMPLETED = "SectorCompleted"
    POSITION_CHANGED = "PositionChanged"
    PIT_ENTRY = "PitEntry"
    PIT_EXIT = "PitExit"
    PIT_STOP_COMPLETED = "PitStopCompleted"
    TYRE_COMPOUND_CHANGED = "TyreCompoundChanged"
    YELLOW_FLAG_STARTED = "YellowFlagStarted"
    SAFETY_CAR_DEPLOYED = "SafetyCarDeployed"
    RED_FLAG_STARTED = "RedFlagStarted"
    RACE_CONTROL_MESSAGE_PUBLISHED = "RaceControlMessagePublished"
    WEATHER_UPDATED = "WeatherUpdated"
    DRIVER_STOPPED = "DriverStopped"
    DRIVER_RETIRED = "DriverRetired"
    PENALTY_ANNOUNCED = "PenaltyAnnounced"
    NEWS_EVENT_PUBLISHED = "NewsEventPublished"
    MARKET_BOOK_UPDATED = "MarketBookUpdated"
    TRADE_OBSERVED = "TradeObserved"


class DomainEvent(BaseModel):
    """An immutable, append-only domain event."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    source: str
    source_event_id: str | None = None

    event_time: datetime
    first_seen_at: datetime
    ingested_at: datetime

    meeting_id: str | None = None
    session_id: str | None = None
    driver_id: str | None = None
    constructor_id: str | None = None

    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @model_validator(mode="after")
    def _check_order(self) -> DomainEvent:
        check_causal_order(
            event_time=self.event_time,
            first_seen_at=self.first_seen_at,
            ingested_at=self.ingested_at,
        )
        return self

    @property
    def availability_time(self) -> datetime:
        """When this event may first be used by a point-in-time model."""
        return self.first_seen_at

    def is_available_at(self, as_of: datetime) -> bool:
        """True if the event was observable at ``as_of`` (no future leakage)."""
        return as_of >= self.first_seen_at


def sort_key(event: DomainEvent) -> tuple[datetime, datetime, str]:
    """Deterministic ordering key: by world time, then observation time, then id.

    Using ``event_id`` as the final tiebreak keeps replay stable and reproducible even when
    two events share both timestamps.
    """
    return (event.event_time, event.first_seen_at, str(event.event_id))
