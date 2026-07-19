"""Scenario engine: perturb the starting state and compare contract prices to the base case.

A scenario applies transparent, bounded modifications to the simulation input (a pace change,
a time penalty, altered retirement risk, elevated safety-car likelihood) and re-prices. The
comparison shows how each contract moves relative to the base case.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from apexsignal.simulation.engine import RaceSimulator, SimInput
from apexsignal.simulation.payoff_matrix import ContractPrices, price_contracts


class Scenario(BaseModel):
    name: str
    driver_pace_delta_s: dict[str, float] = Field(default_factory=dict)  # + = slower
    driver_penalty_s: dict[str, float] = Field(default_factory=dict)  # add to gap-to-leader
    driver_dnf_multiplier: dict[str, float] = Field(default_factory=dict)
    sc_multiplier: float = 1.0

    def apply(self, sim: SimInput) -> SimInput:
        data = sim.model_dump()
        ids = data["driver_ids"]
        pace = list(data["clean_air_pace"])
        gap = list(data["gap_to_leader"])
        dnf = list(data["race_dnf_prob"])
        for i, did in enumerate(ids):
            pace[i] += self.driver_pace_delta_s.get(did, 0.0)
            gap[i] += self.driver_penalty_s.get(did, 0.0)
            dnf[i] = min(1.0, dnf[i] * self.driver_dnf_multiplier.get(did, 1.0))
        data["clean_air_pace"] = pace
        data["gap_to_leader"] = gap
        data["race_dnf_prob"] = dnf
        data["circuit_sc_multiplier"] = sim.circuit_sc_multiplier * self.sc_multiplier
        return SimInput(**data)


class ScenarioComparison(BaseModel):
    scenario: str
    base: ContractPrices
    scenario_prices: ContractPrices
    win_delta: dict[str, float]
    podium_delta: dict[str, float]
    safety_car_delta: float


def compare_scenario(
    simulator: RaceSimulator,
    sim: SimInput,
    scenario: Scenario,
    *,
    base: ContractPrices | None = None,
) -> ScenarioComparison:
    """Price the base case and the scenario, returning the contract deltas."""
    if base is None:
        base = price_contracts(simulator.simulate(sim))
    scen_prices = price_contracts(simulator.simulate(scenario.apply(sim)))

    win_delta = {d: scen_prices.drivers[d].win - base.drivers[d].win for d in base.driver_ids}
    podium_delta = {
        d: scen_prices.drivers[d].podium - base.drivers[d].podium for d in base.driver_ids
    }
    return ScenarioComparison(
        scenario=scenario.name,
        base=base,
        scenario_prices=scen_prices,
        win_delta=win_delta,
        podium_delta=podium_delta,
        safety_car_delta=scen_prices.safety_car - base.safety_car,
    )
