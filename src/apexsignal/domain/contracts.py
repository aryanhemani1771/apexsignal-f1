"""Contract domain: race results and the binary outcomes contracts settle on.

A :class:`RaceResult` is the ground truth for evaluation; :class:`RacePrediction` holds the
model's calibrated contract probabilities. Outcome helpers turn a result into the 0/1 labels
used to score predictions.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

POINTS_POSITIONS = 10
PODIUM_POSITIONS = 3


class DriverEntry(BaseModel):
    """One driver's grid and finishing outcome in a race."""

    driver_id: str
    constructor_id: str | None = None
    grid: int | None = None
    finish_position: int | None = None  # None when not classified
    dnf: bool = False
    classified: bool = True


class RaceResult(BaseModel):
    """Ground-truth result of a completed race."""

    meeting_id: str
    session_id: str
    date: datetime
    entries: list[DriverEntry]

    def drivers(self) -> list[str]:
        return [e.driver_id for e in self.entries]

    def finishing_order(self) -> list[str]:
        """Classified drivers ordered by finishing position (best first)."""
        classified = [e for e in self.entries if e.classified and e.finish_position is not None]
        classified.sort(key=lambda e: e.finish_position or 10**6)
        return [e.driver_id for e in classified]

    def winner(self) -> str | None:
        order = self.finishing_order()
        return order[0] if order else None

    def podium(self) -> list[str]:
        return self.finishing_order()[:PODIUM_POSITIONS]

    def points_finishers(self) -> list[str]:
        return self.finishing_order()[:POINTS_POSITIONS]

    def is_dnf(self, driver_id: str) -> bool:
        for e in self.entries:
            if e.driver_id == driver_id:
                return e.dnf or not e.classified
        return False

    def finished_ahead(self, a: str, b: str) -> bool | None:
        """True if ``a`` beat ``b``; None if the pair is not comparable."""
        order = self.finishing_order()
        if a in order and b in order:
            return order.index(a) < order.index(b)
        if a in order and b not in order:
            return True
        if b in order and a not in order:
            return False
        return None


# --- binary outcome extractors (used to score predictions) ---


def outcome_win(result: RaceResult, driver_id: str) -> int:
    return int(result.winner() == driver_id)


def outcome_podium(result: RaceResult, driver_id: str) -> int:
    return int(driver_id in result.podium())


def outcome_points(result: RaceResult, driver_id: str) -> int:
    return int(driver_id in result.points_finishers())


def outcome_dnf(result: RaceResult, driver_id: str) -> int:
    return int(result.is_dnf(driver_id))


class DriverContractProbs(BaseModel):
    """Calibrated contract probabilities for one driver in one race."""

    driver_id: str
    win: float = 0.0
    podium: float = 0.0
    points: float = 0.0
    dnf: float = 0.0


class RacePrediction(BaseModel):
    """A model's per-driver contract probabilities for a race."""

    meeting_id: str
    session_id: str
    drivers: dict[str, DriverContractProbs] = Field(default_factory=dict)

    def win_probs(self) -> dict[str, float]:
        return {d: p.win for d, p in self.drivers.items()}
