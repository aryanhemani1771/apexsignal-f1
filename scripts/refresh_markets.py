"""Compare model prices to market books and rank opportunities.

Runs fully offline against the synthetic market adapter (books derived from the simulator's
contract prices, seeded to misprice vs. the model so there are edges to find). Public Kalshi /
read-only Polymarket data can be substituted when the `api` extra and network are available.

    uv run python scripts/refresh_markets.py
"""

from __future__ import annotations

import asyncio

from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import price_contracts


def _demo_prices() -> object:
    d = 10
    sim = SimInput(
        driver_ids=[f"D{i}" for i in range(d)],
        total_laps=40,
        current_lap=15,
        clean_air_pace=[90.0 + i * 0.18 for i in range(d)],
        tyre_compound=["medium"] * d,
        tyre_age=[10] * d,
        pit_count=[0] * d,
        gap_to_leader=[i * 1.5 for i in range(d)],
        retired=[False] * d,
        race_dnf_prob=[0.09] * d,
    )
    return price_contracts(RaceSimulator(SimConfig(n_paths=5000, seed=1)).simulate(sim))


async def _run() -> int:
    prices = _demo_prices()
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.08, seed=7)
    )
    scan = await scan_opportunities(
        adapter, prices, min_conservative_edge=0.03, min_mapping_confidence=0.95, min_liquidity=100
    )

    print(f"Scanned {scan.n_markets} markets ({scan.n_reviewed_out} below mapping gate).")
    print(f"Result: {scan.message}\n")
    if scan.opportunities:
        print(f"{'market':<16}{'model':>8}{'cons':>8}{'eff_ask':>9}{'edge':>8}{'score':>8}")
        for o in scan.opportunities[:10]:
            print(
                f"{o.market_id:<16}{o.model_probability:>8.3f}{o.conservative_probability:>8.3f}"
                f"{o.effective_ask:>9.3f}{o.conservative_edge:>8.3f}{o.score:>8.4f}"
            )
        top = scan.opportunities[0]
        print(f"\nTop pick: {top.market_id}\n  {top.rationale}\n  Risk: {top.risk}")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
