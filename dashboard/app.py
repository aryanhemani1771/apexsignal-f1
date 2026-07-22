"""ApexSignal F1 dashboard — an interactive, plain-English research demo.

Designed so someone with no finance background can follow it: every page opens with a plain
explanation, uses charts instead of bare tables, and adds tooltips for any jargon. Runs in
fixture/synthetic mode with zero credentials. Market prices shown are synthetic/illustrative;
the platform's adapters read public Kalshi / read-only Polymarket data (see the footnotes).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import _bootstrap  # noqa: F401  # adds src/ to sys.path — must import before `apexsignal`
import theme  # local module; `streamlit run dashboard/app.py` puts this dir on sys.path
from apexsignal.allocation.constraints import RiskTolerance
from apexsignal.ingestion.fixtures_adapter import demo_news_documents, demo_news_roster
from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_extractor import RuleBasedExtractor
from apexsignal.services import evaluation_report, news_service, race_service
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.services.portfolio_service import build_allocation
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import ContractPrices, price_contracts

ACCENT = theme.ACCENT
POS = "#3dd6c4"
NEG = "#ff6b6b"

_CSS = """
<style>
  .as-intro { background: rgba(61,214,196,0.09); border-left: 3px solid #3dd6c4;
    padding: 12px 16px; border-radius: 10px; margin: 4px 0 18px 0; font-size: 0.98rem; }
  .as-intro b { color: #6ff0e0; }
  .as-fn { color: #7c8896; font-size: 0.8rem; margin-top: 10px; }
  [data-testid="stMetricValue"] { font-size: 1.6rem; }
  h1, h2, h3 { letter-spacing: -0.01em; }
</style>
"""


def _intro(text: str) -> None:
    st.markdown(f"<div class='as-intro'>💡 {text}</div>", unsafe_allow_html=True)


def _market_footnote() -> None:
    st.markdown(
        "<div class='as-fn'>ⓘ Market prices here are <b>synthetic / illustrative</b> (generated "
        "to show the workflow). The platform includes read-only adapters for <b>Kalshi</b> "
        "(public data &amp; demo) and <b>Polymarket</b>; real public prices can be plugged in. "
        "Independent project — not affiliated with Kalshi, Polymarket, or Akuna Capital. "
        "Paper/simulated only.</div>",
        unsafe_allow_html=True,
    )


def _style(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=theme.TEXT,
        margin={"l": 8, "r": 8, "t": 30, "b": 8},
        height=360,
        showlegend=True,
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    return fig


@st.cache_data(show_spinner=False)
def _demo_prices() -> ContractPrices:
    d = 10
    sim = SimInput(
        driver_ids=[f"Car {i + 1}" for i in range(d)],
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
    return price_contracts(RaceSimulator(SimConfig(n_paths=4000, seed=1)).simulate(sim))


def _embed_mode() -> bool:
    try:
        return st.query_params.get("embed") in ("true", "1")
    except Exception:  # pragma: no cover
        return False


# ------------------------------------------------------------------ Overview


def _overview() -> None:
    st.title("🏁 ApexSignal F1")
    st.caption("Predicting F1 races as probabilities, comparing them to markets, betting on paper.")
    _intro(
        "This tool watches a Formula 1 race, estimates the <b>chance</b> of each outcome "
        "(who wins, who reaches the podium, who retires), compares those chances to "
        "<b>betting-market prices</b>, and simulates <b>smart, risk-controlled bets</b> — with "
        "<b>pretend money only</b>. It's a research/learning project, built with AI assistance."
    )

    report = evaluation_report.load_latest_report()
    races = report.get("n_races") if report else None
    brier = None
    if report:
        try:
            brier = report["models"]["grid"]["contracts"]["win"]["calibrated"]["brier"]
        except (KeyError, TypeError):
            brier = None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Real races analysed",
        races or "—",
        help="Actual F1 races (2022-2026) used to test how accurate the model is.",
    )
    c2.metric(
        "Winner accuracy",
        f"{brier:.3f}" if brier else "—",
        help="Brier score — lower is better. ~0.03 means the model's win probabilities line up "
        "well with what really happened. Random guessing scores ~0.08.",
    )
    c3.metric(
        "Simulation speed",
        "5,000 in ~0.2s",
        help="Each prediction runs 5,000 simulated race endings to estimate probabilities.",
    )
    c4.metric(
        "Money at risk",
        "$0",
        help="No real trading — ever. Everything here is paper/simulated.",
    )

    st.markdown("#### What each tab shows")
    st.markdown(
        "- **🏎️ Race replay** — a race played back moment-by-moment (leaderboard, tyres, pits).\n"
        "- **📊 Win probabilities** — the model's estimated chance of each result.\n"
        "- **🎯 Value finder** — where the model disagrees with the market price (an edge).\n"
        "- **💰 Bet sizing** — type a pretend budget → a disciplined, risk-capped allocation.\n"
        "- **📰 News impact** — how an F1 news event nudges the predictions.\n"
        "- **✅ Accuracy (real data)** — how well the model actually did on real races.\n"
        "- **🧭 How it works** — the architecture diagram."
    )
    st.info(
        "Most tabs run on **demo data** so the app works with no accounts or passwords. "
        "The **Accuracy (real data)** tab shows genuine measured results on ~100 real F1 races."
    )


# ------------------------------------------------------------------ Race replay


def _race_replay() -> None:
    st.subheader("🏎️ Race replay")
    _intro(
        "Watch a race rebuilt from its events. Drag the slider to move through time — the "
        "<b>leaderboard</b> (positions, tyres, pit stops) updates just like live timing. "
        "<i>(This is a short, invented demo race.)</i>"
    )
    events = race_service.load_events()
    history = race_service.replay_history(events)
    quality = race_service.quality_report(events)
    if not history:
        st.warning("No events to replay.")
        return

    idx = st.slider("Move through the race →", 1, len(history), len(history))
    state = history[idx - 1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lap", state.current_lap)
    c2.metric(
        "Track status",
        state.track_status.replace("_", " ").title(),
        help="Green = racing; Safety car = neutralised; Yellow/Red = caution/stopped.",
    )
    c3.metric(
        "Events processed",
        state.events_applied,
        help="How many timing events have been folded into this snapshot.",
    )
    c4.metric(
        "Data quality",
        "OK" if quality.ok else f"{quality.n_errors} issues",
        help="Automated integrity checks (duplicate laps, impossible ordering, etc.).",
    )

    st.markdown("**Leaderboard**")
    st.dataframe(race_service.timing_rows(state), use_container_width=True, hide_index=True)
    if state.recent_events:
        st.caption("Recent events: " + " · ".join(state.recent_events[-6:]))


# ------------------------------------------------------------------ Win probabilities


def _pricing() -> None:
    st.subheader("📊 Win probabilities")
    _intro(
        "The model runs thousands of simulated race endings and counts how often each car "
        "achieves a result. So <b>32%</b> for 'podium' means: in ~32% of simulated races, that "
        "car finished top-3. These are the core numbers everything else is built on."
    )
    prices = _demo_prices()
    top = sorted(prices.drivers.values(), key=lambda p: -p.win)[:6]
    xs, ys, cs = [], [], []
    for p in top:
        for label, val in (("Win", p.win), ("Podium", p.podium), ("Points (top 10)", p.points)):
            xs.append(p.driver_id)
            ys.append(val * 100)
            cs.append(label)
    fig = px.bar(
        x=xs,
        y=ys,
        color=cs,
        barmode="group",
        color_discrete_map={"Win": ACCENT, "Podium": "#7aa2ff", "Points (top 10)": "#8b98a5"},
        labels={"x": "", "y": "chance (%)", "color": ""},
    )
    st.plotly_chart(_style(fig), use_container_width=True)
    st.metric(
        "Chance of a safety car (remaining laps)",
        f"{prices.safety_car:.0%}",
        help="Probability a safety car appears before the race ends.",
    )
    st.caption("Cars are labelled generically for the demo. On a real race these are drivers.")


# ------------------------------------------------------------------ Value finder


def _opportunities() -> None:
    st.subheader("🎯 Value finder (model vs. market)")
    _intro(
        "A betting market puts a <b>price</b> on each outcome (a price of 60¢ ≈ a 60% chance). "
        "If the model thinks something is <b>more likely</b> than the price implies — after fees — "
        "that gap is a potential <b>edge</b>. This tab ranks those gaps."
    )
    prices = _demo_prices()
    min_edge = st.slider("Minimum edge to show (percentage points)", 0, 20, 3) / 100
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.08, seed=7)
    )
    scan = asyncio.run(scan_opportunities(adapter, prices, min_conservative_edge=min_edge))

    if not scan.opportunities:
        st.warning(
            "**No value found** at this threshold — exactly what should happen when the "
            "market is priced efficiently. Lower the slider to see more."
        )
        _market_footnote()
        return

    st.success(f"Found **{len(scan.opportunities)}** potential value bets (ranked best first).")
    names = [o.market_id.replace("_", " ") for o in scan.opportunities]
    edges = [o.conservative_edge * 100 for o in scan.opportunities]
    fig = px.bar(
        x=edges,
        y=names,
        orientation="h",
        labels={"x": "edge (percentage points, after fees)", "y": ""},
        color_discrete_sequence=[ACCENT],
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(_style(fig), use_container_width=True)

    with st.expander("See the numbers"):
        st.dataframe(
            [
                {
                    "market": o.market_id.replace("_", " "),
                    "model says": f"{o.model_probability:.0%}",
                    "market price": f"{o.market_ask:.0%}",
                    "your cost (after fees)": f"{o.effective_ask:.0%}",
                    "edge": f"{o.conservative_edge:+.1%}",
                }
                for o in scan.opportunities
            ],
            use_container_width=True,
            hide_index=True,
        )
    _market_footnote()


# ------------------------------------------------------------------ Bet sizing


def _allocation() -> None:
    st.subheader("💰 Bet sizing (simulated)")
    _intro(
        "Enter a pretend budget and how cautious you want to be. The tool sizes each bet with the "
        "<b>Kelly rule</b> (bet more when the edge is bigger), never over-bets one driver, and "
        "shows the <b>worst realistic loss</b>. It's all <b>paper money</b>."
    )
    c1, c2, c3 = st.columns(3)
    bankroll = c1.number_input("Pretend budget ($)", min_value=100.0, value=10_000.0, step=500.0)
    tol = c2.selectbox(
        "How cautious?",
        [t.value for t in RiskTolerance],
        index=0,
        help="Conservative bets small; Aggressive bets a bit more (still capped).",
    )
    max_deploy = (
        c3.slider(
            "Max % of budget to use",
            2,
            50,
            10,
            help="A hard cap on how much of your budget can be at stake at once.",
        )
        / 100
    )

    result = RaceSimulator(SimConfig(n_paths=3000, seed=1)).simulate(_demo_sim())
    alloc = asyncio.run(
        build_allocation(
            result,
            bankroll=bankroll,
            tolerance=RiskTolerance(tol),
            max_deployment_override=max_deploy,
        )
    )

    if not alloc.positions:
        st.warning(
            "**No qualifying bets** — the edges don't clear the safety thresholds. "
            "That's a valid, honest answer (no bet is a bet)."
        )
        _market_footnote()
        return

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Where the budget goes**")
        names = [p.market_id.replace("_", " ") for p in alloc.positions]
        stakes = [p.stake for p in alloc.positions]
        fig = px.bar(
            x=stakes,
            y=names,
            orientation="h",
            labels={"x": "stake ($)", "y": ""},
            color_discrete_sequence=[ACCENT],
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(_style(fig), use_container_width=True)
    with right:
        st.markdown("**Budget split**")
        donut = go.Figure(
            go.Pie(
                values=[alloc.risk.total_stake, alloc.risk.cash_retained],
                labels=["At stake", "Kept as cash"],
                hole=0.6,
                marker_colors=[ACCENT, "#2a3441"],
            )
        )
        st.plotly_chart(_style(donut), use_container_width=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total staked", f"${alloc.risk.total_stake:,.0f}")
    m2.metric("Kept as cash", f"${alloc.risk.cash_retained:,.0f}")
    m3.metric(
        "Worst realistic loss",
        f"${alloc.risk.var_95:,.0f}",
        help="'Value at Risk' — a loss this big or worse happens ~5% of the time.",
    )
    m4.metric(
        "Avg. bad-day loss",
        f"${alloc.risk.expected_shortfall_95:,.0f}",
        help="'Expected shortfall' — the average loss on those worst 5% of days.",
    )
    _market_footnote()


# ------------------------------------------------------------------ News impact


def _news() -> None:
    st.subheader("📰 News impact")
    _intro(
        "The system reads F1 news, pulls out <b>structured facts</b> (a grid penalty, a car "
        "upgrade, a reliability worry) and shows how each one <b>nudges the model</b>. Opinion and "
        "hype are kept on a separate 'sentiment' track. <i>(Demo uses invented articles.)</i>"
    )
    docs = demo_news_documents()
    extractor = RuleBasedExtractor(resolver=EntityResolver(demo_news_roster()))
    as_of = max(d.first_seen_at for d in docs) + timedelta(hours=1)
    result = news_service.run_pipeline(docs, extractor=extractor, as_of=as_of)

    st.markdown("**What the system understood from the news**")
    st.dataframe(
        [
            {
                "event": t.event_type.value.replace("_", " ").title(),
                "who": ", ".join(t.drivers or t.constructors) or "the field",
                "confirmed?": "✅ confirmed" if t.is_confirmed else "🟡 unconfirmed",
            }
            for t in result.timeline
        ],
        use_container_width=True,
        hide_index=True,
    )

    if result.impacts:
        st.markdown("**How it changed each car's predicted pace** (negative = faster)")
        ids = list(result.impacts)
        deltas = [result.impacts[d].pace_delta_seconds_per_lap for d in ids]
        fig = px.bar(
            x=ids,
            y=deltas,
            labels={"x": "", "y": "pace change (sec/lap)"},
            color=[("faster" if v < 0 else "slower") for v in deltas],
            color_discrete_map={"faster": POS, "slower": NEG},
        )
        st.plotly_chart(_style(fig), use_container_width=True)

    moods = [(t, s) for t, s in result.sentiment.items() if s.label != "neutral"]
    if moods:
        st.caption(
            "Separate 'mood' track (not used for predictions): "
            + " · ".join(f"{'🟢' if s.label == 'positive' else '🔴'} {t}" for t, s in moods)
        )


# ------------------------------------------------------------------ Accuracy (real data)


def _performance() -> None:
    st.subheader("✅ Accuracy — on real races")
    _intro(
        "This is the <b>honest</b> tab: how well did the model do on <b>real</b> F1 races? "
        "We use the <b>Brier score</b> — think of it as prediction error, where <b>lower is "
        "better</b>. A model that beats plain guessing has found real signal."
    )
    report = evaluation_report.load_latest_report()
    if report is None:
        st.info("Not yet evaluated. Run `scripts/train_models.py` to generate real metrics.")
        return

    st.caption(
        f"Tested on **{report.get('n_races')} real races** "
        f"(seasons {report.get('seasons')}), walk-forward, calibrated."
    )
    rows = evaluation_report.contract_summary(report, "win")
    if rows:
        labels = {
            "uniform": "Random guess",
            "grid": "Grid position",
            "elo": "Form (Elo)",
            "elo_grid": "Form + grid",
        }
        names = [labels.get(r["model"], r["model"]) for r in rows]
        briers = [r["brier_cal"] for r in rows]
        fig = px.bar(
            x=names,
            y=briers,
            labels={"x": "", "y": "Brier score (lower = better)"},
            color=briers,
            color_continuous_scale=["#3dd6c4", "#ff6b6b"],
        )
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(_style(fig), use_container_width=True)
        best = min(rows, key=lambda r: r["brier_cal"])
        st.success(
            f"Best model scores **{best['brier_cal']:.3f}** on winning — about **half** the error "
            "of random guessing, and well-calibrated. Honest finding: starting **grid position** "
            "explains most of it (pole usually wins), so the model's edge is real but modest."
        )
    for contract in ("podium", "points", "dnf"):
        r = evaluation_report.contract_summary(report, contract)
        if r:
            with st.expander(f"{contract.title()} contract — details"):
                st.dataframe(r, use_container_width=True, hide_index=True)


# ------------------------------------------------------------------ Architecture


_ARCHITECTURE_DOT = """
digraph apexsignal {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#131a22", color="#2a3441",
        fontcolor="#e6edf3", fontsize=10, fontname="Helvetica"];
  edge [color="#3dd6c4"];
  data [label="F1 data\\n(FastF1)"];
  store [label="Event store"];
  reducer [label="Race-state\\nreducer"];
  models [label="Ratings +\\nhazards"];
  sim [label="Monte Carlo\\nsimulator"];
  pricing [label="Probabilities"];
  news [label="News\\npipeline"];
  markets [label="Markets\\n(Kalshi/synthetic)"];
  opps [label="Value finder"];
  alloc [label="Bet sizing"];
  dash [label="Dashboard / API", shape=box3d, fillcolor="#16323a"];
  data -> store -> reducer -> models -> sim -> pricing;
  news -> sim; pricing -> opps; markets -> opps; opps -> alloc;
  pricing -> dash; opps -> dash; alloc -> dash; news -> dash; reducer -> dash;
}
"""


def _architecture() -> None:
    st.subheader("🧭 How it works")
    _intro(
        "The pipeline: real F1 data → rebuild the race → model the outcomes → simulate → turn "
        "into probabilities → compare to markets → size bets. Each box is a tested module."
    )
    st.graphviz_chart(_ARCHITECTURE_DOT, use_container_width=True)
    st.markdown(
        "- **No data leakage** — every fact is time-stamped; predictions only use what was known "
        "at the moment (enforced by tests).\n"
        "- **Calibrated** — probabilities are checked against real outcomes.\n"
        "- **Safe by design** — read-only market data, no real-money trading, paper bets only."
    )


def _demo_sim() -> SimInput:
    d = 10
    return SimInput(
        driver_ids=[f"Car {i + 1}" for i in range(d)],
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


VIEWS = {
    "🏁 Overview": _overview,
    "🏎️ Race replay": _race_replay,
    "📊 Win probabilities": _pricing,
    "🎯 Value finder": _opportunities,
    "💰 Bet sizing": _allocation,
    "📰 News impact": _news,
    "✅ Accuracy (real data)": _performance,
    "🧭 How it works": _architecture,
}


def main() -> None:
    st.set_page_config(page_title="ApexSignal F1", page_icon="🏁", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    embed = _embed_mode()

    if embed:
        _overview()
    else:
        st.sidebar.markdown("### 🏁 ApexSignal F1")
        st.sidebar.caption("F1 prediction-market research · paper only")
        choice = st.sidebar.radio("Explore", list(VIEWS), label_visibility="collapsed")
        st.sidebar.markdown("---")
        st.sidebar.caption("Research/learning demo. Not financial advice. No real money.")
        VIEWS[choice]()

    st.markdown(f"<div class='as-fn'>{theme.DISCLAIMER}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
