"""ApexSignal F1 dashboard — 9 views: race replay, contract pricing, opportunity scanner,
simulated allocation, news intelligence, model performance, and architecture.

Runs in fixture/synthetic mode with zero credentials; every view degrades gracefully.

    uv run --extra dashboard streamlit run dashboard/app.py

``?embed=true`` hides the sidebar/header for portfolio embedding.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import streamlit as st

import theme  # local module; `streamlit run dashboard/app.py` puts this dir on sys.path
from apexsignal.allocation.constraints import RiskTolerance
from apexsignal.domain.events import EventType
from apexsignal.domain.race_state import replay
from apexsignal.ingestion.fixtures_adapter import demo_news_documents, demo_news_roster
from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_extractor import RuleBasedExtractor
from apexsignal.services import evaluation_report, news_service, pricing_service, race_service
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.services.portfolio_service import build_allocation
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import price_contracts


def _embed_mode() -> bool:
    try:
        return st.query_params.get("embed") in ("true", "1")
    except Exception:  # pragma: no cover - older Streamlit fallback
        return False


def _model_performance() -> None:
    st.subheader("Model performance")
    report = evaluation_report.load_latest_report()
    if report is None:
        st.info("Not yet evaluated. Run `scripts/train_models.py` to generate real metrics.")
        return
    st.caption(
        f"Walk-forward on {report.get('n_races', '?')} races "
        f"(seasons {report.get('seasons')}), {report.get('simulation_paths')} sim paths."
    )
    for contract in ("win", "podium", "points", "dnf"):
        rows = evaluation_report.contract_summary(report, contract)
        if rows:
            st.markdown(f"**{contract.title()} contract** — Brier / log-loss by model")
            st.dataframe(rows, use_container_width=True, hide_index=True)


_ARCHITECTURE_DOT = """
digraph apexsignal {
  rankdir=LR; node [shape=box, style=rounded, fontsize=10];
  data [label="FastF1 / OpenF1\\n(historical, no creds)"];
  store [label="Append-only\\nevent store"];
  reducer [label="Race-state\\nreducer (replay)"];
  models [label="Ratings + hazards\\n+ latent pace"];
  sim [label="Monte Carlo\\nsimulator"];
  pricing [label="Contract\\nprices"];
  news [label="News pipeline\\n(events → priors)"];
  markets [label="Kalshi / Polymarket /\\nsynthetic books"];
  opps [label="Opportunity\\nscanner"];
  alloc [label="Fractional-Kelly\\nallocation"];
  dash [label="Dashboard / API", shape=box3d];
  data -> store -> reducer -> models -> sim -> pricing;
  news -> sim;
  pricing -> opps; markets -> opps; opps -> alloc;
  pricing -> dash; opps -> dash; alloc -> dash; news -> dash; reducer -> dash;
}
"""


def _architecture() -> None:
    st.subheader("Architecture & methodology")
    st.graphviz_chart(_ARCHITECTURE_DOT, use_container_width=True)
    st.markdown(
        "- **Point-in-time**: every observation carries `first_seen_at`; backtests and news use "
        "only what was available at the decision moment (leakage tests enforce it).\n"
        "- **Models**: time-varying Elo + Plackett-Luce (pre-race); tyre/pit/DNF/safety-car "
        "hazards + latent pace feed a vectorized Monte Carlo (5k paths in ~0.2s).\n"
        "- **News**: rule-based extraction → Bayesian shrinkage → model parameters; telemetry "
        "confirms or reverses. Sentiment is a separate track.\n"
        "- **Markets**: read-only adapters; rule-aware mapping gate; conservative edge after "
        "fees/slippage; no live-money execution (paper/synthetic/Kalshi-demo only).\n"
        "- **Allocation**: fractional Kelly (no full Kelly) with correlation-aware caps; "
        "VaR/expected-shortfall from the payoff paths."
    )
    st.markdown(f"<div class='as-muted'>{theme.DISCLAIMER}</div>", unsafe_allow_html=True)


def _demo_prices_result() -> object:
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


def _simulated_allocation() -> None:
    st.subheader("Simulated allocation")
    st.caption(
        "Research/paper-trading only — a **model-ranked simulated allocation**, never advice. "
        "Fractional Kelly (no full Kelly), correlation-aware caps from configs/risk_limits.yaml."
    )
    c1, c2, c3 = st.columns(3)
    bankroll = c1.number_input("Research bankroll", min_value=100.0, value=10_000.0, step=100.0)
    tol = c2.selectbox("Risk tolerance", [t.value for t in RiskTolerance], index=0)
    max_deploy = c3.slider("Max total deployment", 0.02, 0.5, 0.10, 0.01)

    result = _demo_prices_result()
    alloc = asyncio.run(
        build_allocation(
            result,
            bankroll=bankroll,
            tolerance=RiskTolerance(tol),
            max_deployment_override=max_deploy,
        )
    )
    st.write(alloc.message)
    if alloc.positions:
        st.dataframe(
            [
                {
                    "market": p.market_id,
                    "contracts": p.contracts,
                    "eff_price": round(p.effective_price, 3),
                    "model": round(p.model_probability, 3),
                    "cons_edge": round(p.conservative_edge, 3),
                    "stake": round(p.stake, 2),
                    "max_loss": round(p.max_loss, 2),
                    "EV": round(p.expected_value, 2),
                }
                for p in alloc.positions
            ],
            use_container_width=True,
            hide_index=True,
        )
    r = alloc.risk
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Deployed", f"{r.total_stake:,.0f}")
    m2.metric("Cash retained", f"{r.cash_retained:,.0f}")
    m3.metric("VaR (95%)", f"{r.var_95:,.0f}")
    m4.metric("Expected shortfall", f"{r.expected_shortfall_95:,.0f}")


def _opportunity_scanner() -> None:
    st.subheader("Opportunity scanner (model vs. market)")
    st.caption(
        "Synthetic market books (seeded to misprice vs. the model). Kalshi public / Polymarket "
        "read-only data can be substituted with the `api` extra. Allocations are simulated only."
    )
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
    prices = price_contracts(RaceSimulator(SimConfig(n_paths=3000, seed=1)).simulate(sim))
    min_edge = st.slider("Minimum conservative edge", 0.0, 0.2, 0.03, 0.01)
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.08, seed=7)
    )
    scan = asyncio.run(
        scan_opportunities(adapter, prices, min_conservative_edge=min_edge, min_liquidity=100)
    )
    st.write(f"Scanned {scan.n_markets} markets · {scan.message}")
    st.dataframe(
        [
            {
                "market": o.market_id,
                "model": round(o.model_probability, 3),
                "conservative": round(o.conservative_probability, 3),
                "eff_ask": round(o.effective_ask, 3),
                "edge": round(o.conservative_edge, 3),
                "liquidity": o.liquidity,
                "score": round(o.score, 4),
            }
            for o in scan.opportunities
        ],
        use_container_width=True,
        hide_index=True,
    )


def _news_intelligence() -> None:
    st.subheader("News intelligence")
    docs = demo_news_documents()
    extractor = RuleBasedExtractor(resolver=EntityResolver(demo_news_roster()))
    as_of = max(d.first_seen_at for d in docs) + timedelta(hours=1)
    result = news_service.run_pipeline(docs, extractor=extractor, as_of=as_of)

    st.caption("Fundamental events move the fair-value model; sentiment is shown separately.")
    st.markdown("**Timeline (fundamental events)**")
    st.dataframe(
        [
            {
                "event": t.event_type.value,
                "who": ", ".join(t.drivers or t.constructors) or "field",
                "confirmed": t.is_confirmed,
                "evidence": t.evidence_count,
                "seen": t.first_seen_at.isoformat(),
            }
            for t in result.timeline
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Per-driver impact (parameter deltas)**")
    st.dataframe(
        [
            {
                "driver": d,
                "pace_delta_s": round(i.pace_delta_seconds_per_lap, 3),
                "grid_delta": round(i.grid_position_delta, 2),
                "dnf_log_odds": round(i.dnf_log_odds_delta, 2),
            }
            for d, i in result.impacts.items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Public sentiment (separate track — not fair value)**")
    st.dataframe(
        [
            {"headline": title, "sentiment": s.label, "score": round(s.score, 2)}
            for title, s in result.sentiment.items()
            if s.label != "neutral"
        ],
        use_container_width=True,
        hide_index=True,
    )


def _contract_pricing() -> None:
    st.subheader("Contract pricing (Monte Carlo)")
    events = race_service.load_events()
    laps = [
        int(e.payload["lap"])
        for e in events
        if e.event_type is EventType.LAP_COMPLETED and "lap" in e.payload
    ]
    max_lap = max(laps) if laps else 0
    if max_lap < 6:
        st.info(
            "The bundled demo race is too short to price a meaningful continuation. "
            "Download a race and use the CLI:\n\n"
            "`uv run --extra data python scripts/price_race.py --season 2023 --round 1 --at-lap 30`"
        )
        return

    at_lap = st.slider("Price after lap", 3, max_lap - 1, max_lap // 2)
    cutoff = max(
        e.event_time
        for e in events
        if e.event_type is EventType.LAP_COMPLETED and int(e.payload.get("lap", 0)) <= at_lap
    )
    subset = [e for e in events if e.event_time <= cutoff]
    prices = pricing_service.price_from_state(
        replay(subset), subset, total_laps=max_lap, config=SimConfig(n_paths=2000, seed=42)
    )
    rows = [
        {
            "driver": p.driver_id,
            "win": round(p.win, 3),
            "podium": round(p.podium, 3),
            "points": round(p.points, 3),
            "dnf": round(p.dnf, 3),
        }
        for p in sorted(prices.drivers.values(), key=lambda x: -x.win)
    ]
    st.metric("Safety car (remaining laps)", f"{prices.safety_car:.1%}")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _race_replay() -> None:
    events = race_service.load_events()
    history = race_service.replay_history(events)
    quality = race_service.quality_report(events)

    if not history:
        st.warning("No events to replay.")
        return

    st.subheader("Race replay")
    idx = st.slider("Event", min_value=1, max_value=len(history), value=len(history))
    state = history[idx - 1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lap", state.current_lap)
    c2.metric("Track status", state.track_status)
    c3.metric("Events applied", state.events_applied)
    c4.metric("Data quality", "OK" if quality.ok else f"{quality.n_errors} err")

    st.markdown("**Timing tower**")
    st.dataframe(race_service.timing_rows(state), use_container_width=True, hide_index=True)

    if state.recent_events:
        st.markdown("**Recent events**")
        st.write(" · ".join(state.recent_events[-6:]))

    with st.expander("Data-quality report"):
        st.write(quality.summary())
        st.dataframe([i.model_dump() for i in quality.issues], use_container_width=True)


def main() -> None:
    st.set_page_config(page_title=theme.BRAND, page_icon="🏁", layout="wide")
    st.markdown(theme.CSS, unsafe_allow_html=True)

    embed = _embed_mode()
    if not embed:
        st.title(f"🏁 {theme.BRAND}")
        st.caption(theme.TAGLINE)

    views = {
        "Race replay": _race_replay,
        "Contract pricing": _contract_pricing,
        "Opportunity scanner": _opportunity_scanner,
        "Simulated allocation": _simulated_allocation,
        "News intelligence": _news_intelligence,
        "Model performance": _model_performance,
        "Architecture": _architecture,
    }
    choice = "Race replay" if embed else st.sidebar.radio("View", list(views))
    views[choice]()

    st.markdown(f"<div class='as-muted'>{theme.DISCLAIMER}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
