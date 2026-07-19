"""Contract pricing from a simulated race continuation.

Reads the Monte Carlo paths and estimates the probability each contract settles Yes: driver
win/podium/points/DNF/fastest-lap, positions-gained, pit-before-lap, pairwise head-to-head,
and the race-level safety-car contract. These are Monte Carlo estimates, not guarantees.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel, Field

from apexsignal.models.ranking import pairwise_ahead_matrix
from apexsignal.simulation.engine import SimulationResult

PODIUM = 3
POINTS = 10


class DriverContractPrices(BaseModel):
    driver_id: str
    win: float
    podium: float
    points: float
    dnf: float
    fastest_lap: float
    gains_positions: float  # P(gains >= threshold positions)
    pit_before_lap: float | None = None  # P(pits before the configured lap), if requested


class ContractPrices(BaseModel):
    driver_ids: list[str]
    n_paths: int
    laps_simulated: int
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    gains_threshold: int
    pit_before_lap: int | None
    safety_car: float  # race-level P(safety car in the remaining laps)
    drivers: dict[str, DriverContractPrices]
    pairwise_ahead: list[list[float]]

    def win_probs(self) -> dict[str, float]:
        return {d: p.win for d, p in self.drivers.items()}

    def p_ahead(self, a: str, b: str) -> float:
        ia, ib = self.driver_ids.index(a), self.driver_ids.index(b)
        return self.pairwise_ahead[ia][ib]


def price_contracts(
    result: SimulationResult,
    *,
    gains_threshold: int = 3,
    pit_before_lap: int | None = None,
) -> ContractPrices:
    positions = result.positions_array()  # (S, D), 1 = leader
    classified = result.classified_array()  # (S, D)
    pitted = np.asarray(result.pitted_lap, dtype=np.int64)
    fastest = np.asarray(result.fastest_lap_driver, dtype=np.int64)
    start = np.asarray(result.start_positions, dtype=np.int64)
    d = len(result.driver_ids)

    win = np.mean(classified & (positions == 1), axis=0)
    podium = np.mean(classified & (positions <= PODIUM), axis=0)
    points = np.mean(classified & (positions <= POINTS), axis=0)
    dnf = np.mean(~classified, axis=0)
    gained = start[None, :] - positions
    gains = np.mean(classified & (gained >= gains_threshold), axis=0)
    fastest_prob = np.array([np.mean(fastest == j) for j in range(d)])

    if pit_before_lap is not None:
        pit_before = np.mean((pitted >= 0) & (pitted < pit_before_lap), axis=0)
    else:
        pit_before = None

    drivers = {
        did: DriverContractPrices(
            driver_id=did,
            win=float(win[j]),
            podium=float(podium[j]),
            points=float(points[j]),
            dnf=float(dnf[j]),
            fastest_lap=float(fastest_prob[j]),
            gains_positions=float(gains[j]),
            pit_before_lap=None if pit_before is None else float(pit_before[j]),
        )
        for j, did in enumerate(result.driver_ids)
    }

    return ContractPrices(
        driver_ids=result.driver_ids,
        n_paths=result.n_paths,
        laps_simulated=result.laps_simulated,
        gains_threshold=gains_threshold,
        pit_before_lap=pit_before_lap,
        safety_car=float(np.mean(result.safety_car_occurred)),
        drivers=drivers,
        pairwise_ahead=pairwise_ahead_matrix(positions, classified).tolist(),
    )
