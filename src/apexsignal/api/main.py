"""FastAPI service for ApexSignal F1.

Read-only research endpoints plus health/version. Everything runs in fixture/synthetic mode
with no credentials; missing data degrades gracefully rather than erroring. No endpoint places a
real order — allocations are simulated.

    uv run uvicorn apexsignal.api.main:app --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from apexsignal import DISCLAIMER, __version__
from apexsignal.allocation.constraints import RiskTolerance
from apexsignal.domain.race_state import replay
from apexsignal.ingestion.fixtures_adapter import demo_race_events
from apexsignal.services import evaluation_report
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.services.portfolio_service import build_allocation
from apexsignal.settings import load_settings
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import price_contracts


def _demo_result() -> Any:
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
    return RaceSimulator(SimConfig(n_paths=3000, seed=1)).simulate(sim)


class AllocationRequest(BaseModel):
    bankroll: float = Field(gt=0)
    tolerance: RiskTolerance = RiskTolerance.CONSERVATIVE
    max_deployment: float | None = Field(default=None, gt=0, le=1)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ApexSignal F1",
        version=__version__,
        description="F1 prediction-market research API (read-only; simulated allocations only).",
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        settings = load_settings()
        return {
            "status": "ok",
            "app_mode": settings.app_mode.value,
            "execution_mode": settings.execution_mode.value,
            "enable_live_trading": settings.enable_live_trading,
            "data": {
                "fixture_race": bool(demo_race_events()),
                "evaluation_report": evaluation_report.load_latest_report() is not None,
            },
        }

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"version": __version__, "model_version": __version__}

    @app.get("/disclaimer")
    def disclaimer() -> dict[str, str]:
        return {"disclaimer": DISCLAIMER}

    @app.get("/races/demo/state")
    def demo_state() -> dict[str, Any]:
        state = replay(demo_race_events())
        return {
            "meeting_id": state.meeting_id,
            "current_lap": state.current_lap,
            "track_status": state.track_status,
            "drivers": {d: s.position for d, s in state.drivers.items()},
        }

    @app.get("/model-performance")
    def model_performance() -> dict[str, Any]:
        report = evaluation_report.load_latest_report()
        if report is None:
            return {"status": "Not yet evaluated"}
        return {"status": "ok", "win": evaluation_report.contract_summary(report, "win")}

    @app.get("/opportunities")
    async def opportunities() -> dict[str, Any]:
        result = _demo_result()
        prices = price_contracts(result)
        from apexsignal.ingestion.synthetic_market import (
            SyntheticMarketAdapter,
            SyntheticMarketConfig,
        )

        adapter = SyntheticMarketAdapter(prices, config=SyntheticMarketConfig(mispricing_sd=0.08))
        scan = await scan_opportunities(adapter, prices, min_conservative_edge=0.03)
        return {
            "message": scan.message,
            "opportunities": [o.model_dump() for o in scan.opportunities],
        }

    @app.post("/allocations")
    async def allocations(req: AllocationRequest) -> dict[str, Any]:
        result = _demo_result()
        alloc = await build_allocation(
            result,
            bankroll=req.bankroll,
            tolerance=req.tolerance,
            max_deployment_override=req.max_deployment,
        )
        return alloc.model_dump()

    return app


app = create_app()
