"""Leakage guard: point-in-time provenance invariants.

These tests protect the no-data-leakage rule: nothing may be *used* before its
``first_seen_at``, and causal ordering of provenance timestamps holds.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from apexsignal.domain.provenance import (
    Provenance,
    ProvenanceError,
    check_causal_order,
)

pytestmark = pytest.mark.leakage

T0 = datetime(2024, 6, 9, 13, 0, tzinfo=UTC)


def _prov(**overrides: object) -> Provenance:
    base: dict[str, object] = {
        "source": "fia_document",
        "event_time": T0,
        "first_seen_at": T0 + timedelta(minutes=1),
        "ingested_at": T0 + timedelta(minutes=2),
        "published_at": T0,
    }
    base.update(overrides)
    return Provenance(**base)  # type: ignore[arg-type]


def test_valid_provenance_availability() -> None:
    p = _prov()
    assert p.availability_time == p.first_seen_at
    assert p.is_available_at(p.first_seen_at) is True
    assert p.is_available_at(p.first_seen_at - timedelta(seconds=1)) is False


def test_cannot_be_seen_before_it_happens() -> None:
    # A ValueError subclass raised in a pydantic validator surfaces as ValidationError.
    with pytest.raises(ValidationError, match="first_seen_at"):
        _prov(first_seen_at=T0 - timedelta(seconds=1))


def test_cannot_be_ingested_before_seen() -> None:
    with pytest.raises(ValidationError, match="ingested_at"):
        _prov(first_seen_at=T0 + timedelta(minutes=5), ingested_at=T0 + timedelta(minutes=1))


def test_check_causal_order_raises_provenance_error_directly() -> None:
    # Called outside pydantic, the guard raises the specific domain error.
    with pytest.raises(ProvenanceError):
        check_causal_order(event_time=T0, first_seen_at=T0 - timedelta(seconds=1))


@given(
    offset_seen=st.integers(min_value=0, max_value=10_000),
    offset_ingest=st.integers(min_value=0, max_value=10_000),
    probe=st.integers(min_value=-10_000, max_value=20_000),
)
def test_availability_never_leaks_future(offset_seen: int, offset_ingest: int, probe: int) -> None:
    """For any valid record, it is available at ``t`` iff ``t >= first_seen_at``."""
    first_seen = T0 + timedelta(seconds=offset_seen)
    ingested = first_seen + timedelta(seconds=offset_ingest)
    p = _prov(event_time=T0, first_seen_at=first_seen, ingested_at=ingested)

    as_of = T0 + timedelta(seconds=probe)
    assert p.is_available_at(as_of) == (as_of >= first_seen)


@given(
    e=st.integers(min_value=0, max_value=1000),
    s=st.integers(min_value=0, max_value=1000),
)
def test_check_causal_order_matches_predicate(e: int, s: int) -> None:
    event_time = T0 + timedelta(seconds=e)
    first_seen = T0 + timedelta(seconds=s)
    if first_seen >= event_time:
        check_causal_order(event_time=event_time, first_seen_at=first_seen)
    else:
        with pytest.raises(ProvenanceError):
            check_causal_order(event_time=event_time, first_seen_at=first_seen)
