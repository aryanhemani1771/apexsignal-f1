"""Price contracts from a point-in-time race state.

Ties the reducer (Phase 1) to the simulator (Phase 3): reconstruct each driver's clean-air
pace and gaps from the lap history, build a :class:`SimInput`, run the Monte Carlo, and read
off contract prices. Works offline from an event log — no credentials required.
"""

from __future__ import annotations

from collections import defaultdict

from apexsignal.domain.events import DomainEvent, EventType
from apexsignal.domain.race_state import RaceState
from apexsignal.models.latent_pace import LapRecord, estimate_clean_air_pace
from apexsignal.models.tyres import TyreModel
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import ContractPrices, price_contracts

DEFAULT_RACE_DNF = 0.10


def build_lap_history(events: list[DomainEvent]) -> dict[str, list[LapRecord]]:
    """Group LAP_COMPLETED events into per-driver lap records."""
    history: dict[str, list[LapRecord]] = defaultdict(list)
    for e in events:
        if e.event_type is not EventType.LAP_COMPLETED or e.driver_id is None:
            continue
        lap_time = e.payload.get("lap_time")
        lap = e.payload.get("lap")
        if lap_time is None or lap is None:
            continue
        history[e.driver_id].append(
            LapRecord(
                lap=int(lap),
                lap_time=float(lap_time),
                compound=e.payload.get("tyre"),
                tyre_age=int(e.payload.get("tyre_age", 0) or 0),
            )
        )
    return history


def build_sim_input(
    state: RaceState,
    events: list[DomainEvent],
    *,
    total_laps: int,
    tyre_model: TyreModel | None = None,
    race_dnf_prob: float | dict[str, float] = DEFAULT_RACE_DNF,
    active_lap_tolerance: int = 3,
) -> SimInput:
    tyres = tyre_model or TyreModel()
    history = build_lap_history(events)
    driver_ids = list(state.drivers)
    current_lap = state.current_lap

    # A driver is "active" if the reducer has them running, on a plausible lap, and ranked.
    # We order from the reducer's tracked position (robust to unequal lap counts); a driver
    # who has stopped appearing on recent laps is treated as retired (adapters don't always
    # emit an explicit retirement event).
    def is_active(did: str) -> bool:
        ds = state.drivers[did]
        return (
            not ds.retired
            and ds.position is not None
            and ds.lap_number >= current_lap - active_lap_tolerance
        )

    active = {d: is_active(d) for d in driver_ids}
    active_positions = [state.drivers[d].position or 10**6 for d in driver_ids if active[d]]
    leader_pos = min(active_positions, default=1)

    pace: dict[str, float] = {
        d: estimate_clean_air_pace(history.get(d, []), tyres, total_laps, fallback=float("nan"))
        for d in driver_ids
    }
    finite = [p for p in pace.values() if p == p]  # drop NaN
    field_pace = sum(finite) / len(finite) if finite else 90.0

    def dnf_for(did: str) -> float:
        if isinstance(race_dnf_prob, dict):
            return race_dnf_prob.get(did, DEFAULT_RACE_DNF)
        return race_dnf_prob

    def gap(did: str) -> float:
        if not active[did]:
            return 300.0
        pos = state.drivers[did].position or leader_pos
        return float((pos - leader_pos) * 1.5)  # rough spacing; pace dominates over a stint

    return SimInput(
        driver_ids=driver_ids,
        total_laps=total_laps,
        current_lap=current_lap,
        clean_air_pace=[pace[d] if pace[d] == pace[d] else field_pace for d in driver_ids],
        tyre_compound=[state.drivers[d].tyre_compound for d in driver_ids],
        tyre_age=[state.drivers[d].tyre_age or 0 for d in driver_ids],
        pit_count=[state.drivers[d].pit_stop_count for d in driver_ids],
        gap_to_leader=[gap(d) for d in driver_ids],
        retired=[not active[d] for d in driver_ids],
        race_dnf_prob=[dnf_for(d) for d in driver_ids],
    )


def price_from_state(
    state: RaceState,
    events: list[DomainEvent],
    *,
    total_laps: int,
    config: SimConfig | None = None,
    tyre_model: TyreModel | None = None,
    race_dnf_prob: float | dict[str, float] = DEFAULT_RACE_DNF,
    gains_threshold: int = 3,
    pit_before_lap: int | None = None,
) -> ContractPrices:
    """Full pipeline: race state + lap history → simulated contract prices."""
    tyres = tyre_model or TyreModel()
    sim_input = build_sim_input(
        state, events, total_laps=total_laps, tyre_model=tyres, race_dnf_prob=race_dnf_prob
    )
    simulator = RaceSimulator(config or SimConfig(), tyre_model=tyres)
    result = simulator.simulate(sim_input)
    return price_contracts(result, gains_threshold=gains_threshold, pit_before_lap=pit_before_lap)
