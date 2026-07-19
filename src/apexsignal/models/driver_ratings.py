"""Time-varying driver and constructor ratings (multiplayer Elo).

Ratings update from each race's finishing order, decay toward the mean between races
(recency weighting), and pool partially: a first-seen driver inherits their constructor's
rating as a prior. Pace ratings use only classified finishers, so a driver is not penalised
for a mechanical retirement — that goes into a separate constructor reliability estimate,
matching the build-spec guidance not to blame drivers for constructor DNFs.
"""

from __future__ import annotations

from pydantic import BaseModel

from apexsignal.domain.contracts import RaceResult

DEFAULT_RATING = 1500.0


class RatingConfig(BaseModel):
    k: float = 24.0
    scale: float = 400.0
    decay: float = 0.03  # fraction regressed toward the mean before each race
    default_rating: float = DEFAULT_RATING
    # Beta-Bernoulli prior for constructor DNF reliability.
    dnf_prior_alpha: float = 1.0
    dnf_prior_beta: float = 9.0


class DriverRatings:
    """Maintains per-driver and per-constructor Elo plus constructor reliability."""

    def __init__(self, config: RatingConfig | None = None) -> None:
        self.config = config or RatingConfig()
        self.driver: dict[str, float] = {}
        self.constructor: dict[str, float] = {}
        self._driver_constructor: dict[str, str] = {}
        self._dnf_count: dict[str, float] = {}
        self._entry_count: dict[str, float] = {}
        self.races_seen = 0

    # --- accessors ---

    def driver_rating(self, driver_id: str, constructor_id: str | None = None) -> float:
        if driver_id in self.driver:
            return self.driver[driver_id]
        # Partial pooling: inherit the constructor prior, else the global default.
        if constructor_id and constructor_id in self.constructor:
            return self.constructor[constructor_id]
        return self.config.default_rating

    def constructor_rating(self, constructor_id: str | None) -> float:
        if constructor_id and constructor_id in self.constructor:
            return self.constructor[constructor_id]
        return self.config.default_rating

    def strength(self, driver_id: str, constructor_id: str | None = None) -> float:
        return self.driver_rating(driver_id, constructor_id)

    def dnf_rate(self, constructor_id: str | None) -> float:
        a = self.config.dnf_prior_alpha
        b = self.config.dnf_prior_beta
        dnf = self._dnf_count.get(constructor_id or "", 0.0)
        entries = self._entry_count.get(constructor_id or "", 0.0)
        return (dnf + a) / (entries + a + b)

    # --- updates ---

    def _decay(self) -> None:
        cfg = self.config
        if not self.driver:
            return
        mean = cfg.default_rating
        for d in self.driver:
            self.driver[d] = mean + (1.0 - cfg.decay) * (self.driver[d] - mean)
        for c in self.constructor:
            self.constructor[c] = mean + (1.0 - cfg.decay) * (self.constructor[c] - mean)

    def update(self, result: RaceResult) -> None:
        """Update ratings and reliability from a completed race."""
        self._decay()

        for e in result.entries:
            if e.constructor_id:
                self._driver_constructor[e.driver_id] = e.constructor_id
                self.constructor.setdefault(e.constructor_id, self.config.default_rating)
            if e.driver_id not in self.driver:
                self.driver[e.driver_id] = self.driver_rating(e.driver_id, e.constructor_id)
            # Reliability bookkeeping (constructor-level).
            key = e.constructor_id or ""
            self._entry_count[key] = self._entry_count.get(key, 0.0) + 1.0
            if e.dnf or not e.classified:
                self._dnf_count[key] = self._dnf_count.get(key, 0.0) + 1.0

        order = result.finishing_order()
        if len(order) >= 2:
            self._elo_update(order)
        self.races_seen += 1

    def _elo_update(self, order: list[str]) -> None:
        """Multiplayer Elo from a finishing order (best first)."""
        cfg = self.config
        n = len(order)
        ratings = {d: self.driver[d] for d in order}
        # actual_i = fraction of opponents beaten; expected_i = sum of pairwise expectations.
        actual = {d: (n - 1 - rank) / (n - 1) for rank, d in enumerate(order)}
        expected: dict[str, float] = {}
        for d in order:
            exp = 0.0
            for o in order:
                if o == d:
                    continue
                exp += 1.0 / (1.0 + 10.0 ** ((ratings[o] - ratings[d]) / cfg.scale))
            expected[d] = exp / (n - 1)

        for d in order:
            self.driver[d] = ratings[d] + cfg.k * (actual[d] - expected[d])

        self._update_constructors(order)

    def _update_constructors(self, order: list[str]) -> None:
        """Aggregate driver movements to the constructor level (reliability of pace)."""
        cfg = self.config
        by_constructor: dict[str, list[float]] = {}
        n = len(order)
        for rank, d in enumerate(order):
            c = self._driver_constructor.get(d)
            if not c:
                continue
            by_constructor.setdefault(c, []).append((n - 1 - rank) / (n - 1))
        # Nudge each constructor toward the mean finishing quality of its cars.
        for c, scores in by_constructor.items():
            mean_score = sum(scores) / len(scores)
            current = self.constructor.get(c, cfg.default_rating)
            self.constructor[c] = current + cfg.k * 0.5 * (mean_score - 0.5)
