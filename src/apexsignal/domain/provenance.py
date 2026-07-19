"""Point-in-time provenance primitives.

Every observation the system ingests carries provenance timestamps so that historical
predictions can be reconstructed using only information available at the prediction moment.
``first_seen_at`` is the authoritative availability timestamp for backtesting unless a more
defensible timestamp exists.

See ``DATA_DICTIONARY.md`` for the field contract.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class ProvenanceError(ValueError):
    """Raised when provenance timestamps violate causal ordering (a leakage risk)."""


def check_causal_order(
    *,
    event_time: datetime,
    first_seen_at: datetime,
    ingested_at: datetime | None = None,
) -> None:
    """Validate the causal ordering that guards against data leakage.

    An observation cannot be *seen* before it *happens*, and cannot be *ingested* before it
    is seen. Violations mean a record could be used before it was actually available.
    """
    if first_seen_at < event_time:
        raise ProvenanceError(
            f"first_seen_at ({first_seen_at.isoformat()}) is before event_time "
            f"({event_time.isoformat()}): an observation cannot be seen before it happens."
        )
    if ingested_at is not None and ingested_at < first_seen_at:
        raise ProvenanceError(
            f"ingested_at ({ingested_at.isoformat()}) is before first_seen_at "
            f"({first_seen_at.isoformat()}): cannot ingest before first seeing."
        )


class Provenance(BaseModel):
    """Reusable provenance record for observations, documents, and news items."""

    model_config = ConfigDict(frozen=True)

    source: str
    source_event_id: str | None = None

    event_time: datetime
    first_seen_at: datetime
    ingested_at: datetime
    published_at: datetime | None = None
    effective_at: datetime | None = None

    @model_validator(mode="after")
    def _check_order(self) -> Provenance:
        check_causal_order(
            event_time=self.event_time,
            first_seen_at=self.first_seen_at,
            ingested_at=self.ingested_at,
        )
        return self

    @property
    def availability_time(self) -> datetime:
        """The timestamp at which this record may first be used (no-leakage rule)."""
        return self.first_seen_at

    def is_available_at(self, as_of: datetime) -> bool:
        """True if this record was already observable at ``as_of``."""
        return as_of >= self.first_seen_at
