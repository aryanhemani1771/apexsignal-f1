"""Vectorized Monte Carlo race-continuation simulator.

Starting from a point-in-time race state, simulate the remaining laps across many paths at once
(vectorized over paths). Each lap each running car gets a lap time = clean-air pace + tyre
degradation + fuel effect + dirty-air (track-position) penalty + noise; pit stops, retirements,
and safety cars are drawn from the hazard models. Final classifications and event flags feed the
contract payoff matrix.

Design choices favour a transparent, seeded, few-seconds-for-5k-paths baseline over full
telemetry fidelity. Positions come from cumulative race time (a faster car naturally advances),
with a dirty-air penalty giving realistic track-position stickiness.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel

from apexsignal.models.dnf_hazard import DNFHazardModel
from apexsignal.models.pit_hazard import TARGET_STINT, PitHazardModel
from apexsignal.models.safety_car_hazard import SafetyCarHazardModel
from apexsignal.models.tyres import TyreModel

_COMPOUND_CODES = {"soft": 0, "medium": 1, "hard": 2, "intermediate": 3, "wet": 4}
_CODE_COMPOUND = {v: k for k, v in _COMPOUND_CODES.items()}


class SimConfig(BaseModel):
    n_paths: int = 5000
    seed: int = 42
    lap_noise_sd: float = 0.5
    pit_loss_s: float = 22.0
    dirty_air_penalty_s: float = 0.3
    dirty_air_threshold_s: float = 1.0
    sc_gap_compression: float = 0.35  # gaps shrink to this fraction under safety car
    sc_lap_penalty_s: float = 30.0
    fuel_gain_per_lap: float = 0.055
    mandatory_stop: bool = True


class SimInput(BaseModel):
    driver_ids: list[str]
    total_laps: int
    current_lap: int
    clean_air_pace: list[float]
    tyre_compound: list[str | None]
    tyre_age: list[int]
    pit_count: list[int]
    gap_to_leader: list[float]
    retired: list[bool]
    race_dnf_prob: list[float]
    circuit_sc_multiplier: float = 1.0


class SimulationResult(BaseModel):
    driver_ids: list[str]
    n_paths: int
    laps_simulated: int
    start_positions: list[int]
    # arrays flattened to lists for portability; shape (n_paths, n_drivers) unless noted
    final_positions: list[list[int]]
    classified: list[list[bool]]
    pitted_lap: list[list[int]]  # first sim pit lap per driver, -1 if none
    fastest_lap_driver: list[int]  # driver index per path, -1 if none
    safety_car_occurred: list[bool]  # per path

    def positions_array(self) -> NDArray[np.int64]:
        return np.asarray(self.final_positions, dtype=np.int64)

    def classified_array(self) -> NDArray[np.bool_]:
        return np.asarray(self.classified, dtype=np.bool_)


class RaceSimulator:
    def __init__(
        self,
        config: SimConfig | None = None,
        *,
        tyre_model: TyreModel | None = None,
        dnf_model: DNFHazardModel | None = None,
        pit_model: PitHazardModel | None = None,
        sc_model: SafetyCarHazardModel | None = None,
    ) -> None:
        self.config = config or SimConfig()
        self.tyres = tyre_model or TyreModel()
        self.dnf = dnf_model or DNFHazardModel()
        self.pit = pit_model or PitHazardModel()
        self.sc = sc_model or SafetyCarHazardModel()

    def _compound_tables(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        grip = np.zeros(len(_COMPOUND_CODES))
        deg = np.zeros(len(_COMPOUND_CODES))
        for name, code in _COMPOUND_CODES.items():
            p = self.tyres.compound_params(name)
            grip[code] = p.grip_offset
            deg[code] = p.deg_per_lap
        return grip, deg

    def _next_compound_code(self, laps_remaining: int) -> int:
        if laps_remaining > TARGET_STINT["hard"] * 0.7:
            return _COMPOUND_CODES["hard"]
        if laps_remaining > TARGET_STINT["soft"] * 0.7:
            return _COMPOUND_CODES["medium"]
        return _COMPOUND_CODES["soft"]

    def simulate(self, sim: SimInput) -> SimulationResult:
        cfg = self.config
        rng = np.random.default_rng(cfg.seed)
        s, d = cfg.n_paths, len(sim.driver_ids)
        grip, deg = self._compound_tables()

        pace = np.asarray(sim.clean_air_pace, dtype=np.float64)
        code = np.array(
            [_COMPOUND_CODES.get((c or "medium").lower(), 1) for c in sim.tyre_compound]
        )
        age = np.tile(np.asarray(sim.tyre_age, dtype=np.float64), (s, 1))
        codes = np.tile(code, (s, 1))
        cum = np.tile(np.asarray(sim.gap_to_leader, dtype=np.float64), (s, 1))
        retired = np.tile(np.asarray(sim.retired, dtype=bool), (s, 1))
        pits_made = np.tile(np.asarray(sim.pit_count, dtype=np.int64), (s, 1))
        pitted_lap = np.full((s, d), -1, dtype=np.int64)

        start_positions = _rank(cum)
        fastest_time = np.full(s, np.inf)
        fastest_driver = np.full(s, -1, dtype=np.int64)
        sc_occurred = np.zeros(s, dtype=bool)

        race_dnf = np.asarray(sim.race_dnf_prob, dtype=np.float64)
        laps = list(range(sim.current_lap + 1, sim.total_laps + 1))
        # Constant per-lap DNF hazard calibrated once to the remaining stint, so accumulated
        # retirements match race_dnf_prob over the continuation (recomputing per lap oversums).
        laps_rem_total = max(1, sim.total_laps - sim.current_lap)
        base_haz = np.array([self.dnf.per_lap_hazard(q, laps_rem_total) for q in race_dnf])
        for lap in laps:
            laps_remaining = sim.total_laps - lap + 1
            running = ~retired

            # --- lap time components ---
            tyre_pace = grip[codes] + deg[codes] * age
            fuel = cfg.fuel_gain_per_lap * max(0, sim.total_laps - lap)
            noise = rng.normal(0.0, cfg.lap_noise_sd, size=(s, d))
            lap_time = pace[None, :] + tyre_pace + fuel + noise

            # dirty air: a car within threshold behind another loses time (hard to pass).
            gap_ahead = _gap_to_car_ahead(cum, running)
            dirty = (gap_ahead > 0) & (gap_ahead < cfg.dirty_air_threshold_s)
            lap_time += np.where(dirty, cfg.dirty_air_penalty_s, 0.0)

            # --- safety car (per path) ---
            p_sc = self.sc.per_lap_prob(
                lap - sim.current_lap - 1, circuit_multiplier=sim.circuit_sc_multiplier
            )
            sc_now = rng.uniform(size=s) < p_sc
            sc_occurred |= sc_now

            # --- pit decisions ---
            pit_prob = _pit_probs(
                self.pit, codes, age, laps_remaining, pits_made, sc_now, cfg.mandatory_stop
            )
            pit_now = (rng.uniform(size=(s, d)) < pit_prob) & running
            if laps_remaining <= self.pit.config.min_laps_left_to_pit:
                pit_now &= (pits_made == 0) & cfg.mandatory_stop

            # --- retirements (opening-lap incidents elevated when starting from the grid) ---
            haz = base_haz * self.dnf.config.first_lap_multiplier if lap == 1 else base_haz
            haz = np.minimum(haz, 1.0)
            retire_now = (rng.uniform(size=(s, d)) < haz[None, :]) & running & ~pit_now

            # --- apply pit loss & compound/age changes ---
            lap_time += np.where(pit_now, cfg.pit_loss_s, 0.0)
            next_code = self._next_compound_code(laps_remaining)
            codes = np.where(pit_now, next_code, codes)
            newly_pitted = pit_now & (pitted_lap < 0)
            pitted_lap = np.where(newly_pitted, lap, pitted_lap)
            pits_made = pits_made + pit_now.astype(np.int64)

            # --- safety car neutralises the lap & compresses gaps ---
            if np.any(sc_now):
                lap_time[sc_now] = pace[None, :] + cfg.sc_lap_penalty_s

            # --- fastest lap (green, running, no pit) ---
            green = running & ~pit_now & ~sc_now[:, None]
            masked = np.where(green, lap_time, np.inf)
            lap_min = masked.min(axis=1)
            lap_arg = masked.argmin(axis=1)
            improved = lap_min < fastest_time
            fastest_time = np.where(improved, lap_min, fastest_time)
            fastest_driver = np.where(improved, lap_arg, fastest_driver)

            # --- accumulate & update state ---
            cum = cum + np.where(running & ~retire_now, lap_time, 0.0)
            retired = retired | retire_now
            age = np.where(pit_now, 0.0, age + running)

            if np.any(sc_now):
                leader = cum.min(axis=1, keepdims=True)
                compressed = leader + (cum - leader) * cfg.sc_gap_compression
                cum = np.where(sc_now[:, None] & ~retired, compressed, cum)

        # retired cars sort last.
        cum_final = np.where(retired, np.inf, cum)
        final_positions = _rank(cum_final)

        return SimulationResult(
            driver_ids=sim.driver_ids,
            n_paths=s,
            laps_simulated=len(laps),
            start_positions=start_positions[0].tolist(),
            final_positions=final_positions.tolist(),
            classified=(~retired).tolist(),
            pitted_lap=pitted_lap.tolist(),
            fastest_lap_driver=fastest_driver.tolist(),
            safety_car_occurred=sc_occurred.tolist(),
        )


def _rank(cum: NDArray[np.float64]) -> NDArray[np.int64]:
    """Position (1 = leader) per path from cumulative times."""
    order = np.argsort(cum, axis=1, kind="stable")
    positions = np.empty_like(order)
    rows = np.arange(cum.shape[0])[:, None]
    positions[rows, order] = np.arange(cum.shape[1])[None, :] + 1
    return positions


def _gap_to_car_ahead(cum: NDArray[np.float64], running: NDArray[np.bool_]) -> NDArray[np.float64]:
    """Seconds from each car to the car directly ahead (0 for the leader / lone cars)."""
    s, d = cum.shape
    masked = np.where(running, cum, np.inf)
    order = np.argsort(masked, axis=1, kind="stable")
    sorted_times = np.take_along_axis(masked, order, axis=1)
    gaps_sorted = np.zeros((s, d))
    with np.errstate(invalid="ignore"):  # inf - inf for trailing non-running cars → nan
        gaps_sorted[:, 1:] = np.diff(sorted_times, axis=1)
    gaps = np.zeros((s, d))
    rows = np.arange(s)[:, None]
    gaps[rows, order] = gaps_sorted
    gaps[~np.isfinite(gaps)] = 0.0
    return gaps


_TARGET_BY_CODE = np.array(
    [TARGET_STINT.get(_CODE_COMPOUND[c], 24) for c in range(len(_CODE_COMPOUND))],
    dtype=np.float64,
)


def _pit_probs(
    pit_model: PitHazardModel,
    codes: NDArray[np.int64],
    age: NDArray[np.float64],
    laps_remaining: int,
    pits_made: NDArray[np.int64],
    sc_now: NDArray[np.bool_],
    mandatory: bool,
) -> NDArray[np.float64]:
    """Vectorized per-driver pit probability for the current lap (mirrors PitHazardModel)."""
    cfg = pit_model.config
    target = _TARGET_BY_CODE[codes]
    mandatory_pending = mandatory & (pits_made == 0)

    if laps_remaining <= cfg.min_laps_left_to_pit:
        return np.where(mandatory_pending, 0.5, 0.0)

    wear = cfg.base_max / (1.0 + np.exp(-cfg.steepness * (age - target)))
    prob = np.where(sc_now[:, None], np.minimum(1.0, wear + cfg.safety_car_bonus), wear)
    force = mandatory_pending & (laps_remaining < target)
    prob = np.where(force, np.maximum(prob, 0.4), prob)
    return np.minimum(1.0, prob)
