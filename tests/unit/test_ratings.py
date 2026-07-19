"""Driver/constructor Elo ratings and reliability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apexsignal.domain.contracts import DriverEntry, RaceResult
from apexsignal.models.driver_ratings import DEFAULT_RATING, DriverRatings

T0 = datetime(2024, 1, 1, tzinfo=UTC)
FIELD = ["A", "B", "C", "D"]


def _race(order: list[str], round_no: int, dnf: set[str] | None = None) -> RaceResult:
    dnf = dnf or set()
    entries = []
    for pos, d in enumerate(order, start=1):
        entries.append(
            DriverEntry(
                driver_id=d,
                constructor_id=f"team_{d.lower()}",
                grid=pos,
                finish_position=None if d in dnf else pos,
                dnf=d in dnf,
                classified=d not in dnf,
            )
        )
    return RaceResult(
        meeting_id=f"m{round_no}",
        session_id=f"m{round_no}-R",
        date=T0 + timedelta(days=round_no),
        entries=entries,
    )


def test_consistent_winner_gains_rating() -> None:
    ratings = DriverRatings()
    for r in range(8):
        ratings.update(_race(["A", "B", "C", "D"], r))
    assert ratings.driver_rating("A") > DEFAULT_RATING
    assert ratings.driver_rating("A") > ratings.driver_rating("B")
    assert ratings.driver_rating("D") < DEFAULT_RATING


def test_dnf_rate_prior_and_update() -> None:
    ratings = DriverRatings()
    # No data → prior mean alpha/(alpha+beta) = 1/10.
    assert abs(ratings.dnf_rate("unknown_team") - 0.1) < 1e-9
    for r in range(5):
        ratings.update(_race(["A", "B", "C", "D"], r, dnf={"D"}))
    rate_d = ratings.dnf_rate("team_d")
    rate_a = ratings.dnf_rate("team_a")
    assert rate_d > rate_a
    assert 0.0 < rate_d < 1.0


def test_pace_rating_ignores_dnf_for_the_retiree() -> None:
    # A driver who retires is not ranked below on pace; only reliability records it.
    ratings = DriverRatings()
    before = ratings.driver_rating("C")
    ratings.update(_race(["A", "B", "C", "D"], 0, dnf={"C"}))
    # C did not appear in the finishing order, so its pace rating is untouched by ranking.
    assert ratings.driver_rating("C") == before
