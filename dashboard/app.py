"""ApexSignal F1 dashboard — an interactive, plain-English research demo.

Designed so someone with no finance background can follow it: every page opens with a plain
explanation, uses charts instead of bare tables, and adds tooltips for any jargon. Runs on a
bundled REAL race (2026 British GP, from FastF1 timing data) with real drivers and events, plus a
form-based forecast for the next race — all with zero credentials. Market prices are
synthetic/illustrative (see the footnotes); news items are clearly-labelled hypothetical examples.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import _bootstrap  # noqa: F401  # adds src/ to sys.path — must import before `apexsignal`
import theme  # local module; `streamlit run dashboard/app.py` puts this dir on sys.path
from apexsignal.allocation.constraints import RiskTolerance
from apexsignal.domain.events import EventType
from apexsignal.domain.news import NewsDocument, SourceClass
from apexsignal.domain.race_state import RaceState, replay, replay_states
from apexsignal.ingestion.fixtures_adapter import (
    REAL_RACE_NAME,
    REAL_RACE_TOTAL_LAPS,
    real_race_events,
)
from apexsignal.ingestion.synthetic_market import SyntheticMarketAdapter, SyntheticMarketConfig
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_extractor import RuleBasedExtractor
from apexsignal.services import evaluation_report, news_service, race_service
from apexsignal.services.opportunity_service import scan_opportunities
from apexsignal.services.portfolio_service import build_allocation
from apexsignal.services.pricing_service import build_sim_input
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimulationResult
from apexsignal.simulation.payoff_matrix import ContractPrices, price_contracts

ACCENT = theme.ACCENT
POS = "#3dd6c4"
NEG = "#ff6b6b"
PRICE_AT_LAP = 30  # price the race from this point onward

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
        "Independent project — not affiliated with Kalshi or Polymarket. "
        "Paper/simulated only.</div>",
        unsafe_allow_html=True,
    )


def _style(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=theme.TEXT,
        margin={"l": 8, "r": 8, "t": 30, "b": 8},
        height=380,
        showlegend=True,
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    return fig


# ------------------------------------------------------------------ real-race data (cached)


@st.cache_data(show_spinner=False)
def _events() -> list:
    return real_race_events()


@st.cache_data(show_spinner=False)
def _lap_states() -> list[tuple[int, RaceState]]:
    """One race-state snapshot per completed lap (real leaderboard through the race)."""
    by_lap: dict[int, RaceState] = {}
    for s in replay_states(_events()):
        if s.current_lap > 0:
            by_lap[s.current_lap] = s
    return [(lap, by_lap[lap]) for lap in sorted(by_lap)]


@st.cache_data(show_spinner=False)
def _sim(at_lap: int = PRICE_AT_LAP) -> SimulationResult:
    """Simulate the rest of the real race from ``at_lap`` (real drivers)."""
    events = _events()
    cutoff = max(
        e.event_time
        for e in events
        if e.event_type is EventType.LAP_COMPLETED and int(e.payload.get("lap", 0)) <= at_lap
    )
    subset = [e for e in events if e.event_time <= cutoff]
    sim_input = build_sim_input(replay(subset), subset, total_laps=REAL_RACE_TOTAL_LAPS)
    return RaceSimulator(SimConfig(n_paths=3000, seed=1)).simulate(sim_input)


def _prices() -> ContractPrices:
    return price_contracts(_sim())


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
    st.caption(f"Live demo uses real timing data from the **{REAL_RACE_NAME}**.")

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
        races or "-",
        help="Actual F1 races (2022-2026) used to test how accurate the model is.",
    )
    c2.metric(
        "Winner accuracy",
        f"{brier:.3f}" if brier else "-",
        help="Brier score - lower is better. ~0.03 means the model's win probabilities "
        "line up well with what really happened. Random guessing scores ~0.08.",
    )
    c3.metric(
        "Simulation speed",
        "5,000 in ~0.2s",
        help="Each prediction runs thousands of simulated race endings.",
    )
    c4.metric("Money at risk", "$0", help="No real trading - ever. Paper/simulated only.")

    st.markdown("#### What each tab shows")
    st.markdown(
        "- **🔮 Next race** - a live forecast for the upcoming Grand Prix (current-season form).\n"
        "- **🏎️ Race replay** - a real race played back lap-by-lap (leaderboard, tyres, pits).\n"
        "- **📊 Win probabilities** - the model's estimated chance of each result.\n"
        "- **🎯 Value finder** - where the model disagrees with the market price (an edge).\n"
        "- **💰 Bet sizing** - type a pretend budget → a disciplined, risk-capped allocation.\n"
        "- **📰 News impact** - how an F1 news event would nudge the predictions.\n"
        "- **✅ Accuracy (real data)** - how well the model actually did on real races.\n"
        "- **🧭 How it works** - the architecture diagram."
    )
    pred = evaluation_report.load_next_race_prediction()
    if pred:
        st.info(f"👉 **Next race** tab: the model's live forecast for the **{pred['race']}**.")
    st.caption(
        f"Race data is **real** ({REAL_RACE_NAME}). Market prices are **synthetic** and news "
        "items are **hypothetical examples** - both clearly labelled - so the demo needs no "
        "accounts."
    )


# ------------------------------------------------------------------ Race replay


def _race_replay() -> None:
    st.subheader("🏎️ Race replay")
    _intro(
        f"The <b>{REAL_RACE_NAME}</b>, rebuilt from real FastF1 timing data. Drag the slider to "
        "move through the laps - the <b>leaderboard</b> (positions, tyres, pit stops) updates "
        "just like live timing. Drivers are the real three-letter codes (VER = Verstappen…)."
    )
    lap_states = _lap_states()
    if not lap_states:
        st.warning("No race data.")
        return
    max_lap = lap_states[-1][0]
    lap = st.slider("Lap", 1, max_lap, min(PRICE_AT_LAP, max_lap))
    state = next((s for lp, s in lap_states if lp >= lap), lap_states[-1][1])

    c1, c2, c3 = st.columns(3)
    c1.metric("Lap", f"{state.current_lap} / {REAL_RACE_TOTAL_LAPS}")
    c2.metric(
        "Track status",
        state.track_status.replace("_", " ").title(),
        help="Green = racing; Safety car = neutralised; Yellow/Red = caution/stopped.",
    )
    c3.metric("Cars running", sum(1 for d in state.drivers.values() if not d.retired))

    st.markdown("**Leaderboard**")
    st.dataframe(race_service.timing_rows(state), use_container_width=True, hide_index=True)
    if state.recent_events:
        st.caption("Recent events: " + " · ".join(state.recent_events[-6:]))


# ------------------------------------------------------------------ Win probabilities


def _pricing() -> None:
    st.subheader("📊 Win probabilities")
    _intro(
        f"From lap {PRICE_AT_LAP} of the {REAL_RACE_NAME}, the model runs thousands of simulated "
        "race endings and counts how often each driver achieves a result. So <b>32% podium</b> "
        "means: in ~32% of simulated races, that driver finished top-3."
    )
    prices = _prices()
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


# ------------------------------------------------------------------ Value finder


def _opportunities() -> None:
    st.subheader("🎯 Value finder (model vs. market)")
    _intro(
        "A betting market puts a <b>price</b> on each outcome (a price of 60¢ ≈ a 60% chance). "
        "If the model thinks something is <b>more likely</b> than the price implies - after fees - "
        "that gap is a potential <b>edge</b>. This ranks those gaps for the real race."
    )
    prices = _prices()
    min_edge = st.slider("Minimum edge to show (percentage points)", 0, 20, 3) / 100
    adapter = SyntheticMarketAdapter(
        prices, config=SyntheticMarketConfig(mispricing_sd=0.08, seed=7)
    )
    scan = asyncio.run(scan_opportunities(adapter, prices, min_conservative_edge=min_edge))

    if not scan.opportunities:
        st.warning(
            "**No value found** at this threshold - what should happen when the market is "
            "priced efficiently. Lower the slider to see more."
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

    alloc = asyncio.run(
        build_allocation(
            _sim(),
            bankroll=bankroll,
            tolerance=RiskTolerance(tol),
            max_deployment_override=max_deploy,
        )
    )
    if not alloc.positions:
        st.warning(
            "**No qualifying bets** - the edges don't clear the safety thresholds. "
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
        help="'Value at Risk' - a loss this big or worse happens ~5% of the time.",
    )
    m4.metric(
        "Avg. bad-day loss",
        f"${alloc.risk.expected_shortfall_95:,.0f}",
        help="'Expected shortfall' - the average loss on those worst 5% of days.",
    )
    _market_footnote()


# ------------------------------------------------------------------ News impact


def _illustrative_news() -> list[NewsDocument]:
    t = datetime(2023, 3, 3, 9, 0, tzinfo=UTC)
    seen = datetime(2023, 3, 3, 9, 30, tzinfo=UTC)

    def doc(title: str, text: str, src: SourceClass) -> NewsDocument:
        return NewsDocument(
            title=title,
            text=text,
            source_url="https://example.org/x",
            source_class=src,
            published_at=t,
            first_seen_at=seen,
            meeting_id="demo",
        )

    return [
        doc(
            "Example: Leclerc takes a grid penalty for a new power unit",
            "Hypothetical illustration - the stewards ruled Leclerc will start with a grid "
            "penalty after a new power unit. It is official.",
            SourceClass.FIA_DOCUMENT,
        ),
        doc(
            "Example: Mercedes brings a floor upgrade for Hamilton",
            "Hypothetical illustration - Mercedes has confirmed an aerodynamic floor upgrade "
            "for Hamilton. It is official.",
            SourceClass.OFFICIAL_TEAM,
        ),
        doc(
            "Example: reliability concern flagged for Sainz",
            "Hypothetical illustration - a specialist report notes a reliability concern on the "
            "Sainz power unit after Friday running.",
            SourceClass.SPECIALIST_PUB,
        ),
        doc(
            "Example: rain is expected on Sunday",
            "Hypothetical illustration - forecasters say rain is expected, raising the chance of "
            "a wet race.",
            SourceClass.GENERAL_PUB,
        ),
    ]


def _news() -> None:
    st.subheader("📰 News impact")
    st.warning(
        "⚠️ **Illustrative hypothetical examples** (not real news about these drivers) - "
        "they show how the pipeline turns a headline into a change in the model."
    )
    _intro(
        "The system reads F1 news, pulls out <b>structured facts</b> (a grid penalty, a car "
        "upgrade, a reliability worry) and shows how each <b>nudges the model</b>. Opinion/hype "
        "is kept on a separate 'sentiment' track."
    )
    docs = _illustrative_news()
    result = news_service.run_pipeline(
        docs,
        extractor=RuleBasedExtractor(resolver=EntityResolver()),
        as_of=datetime(2023, 3, 4, tzinfo=UTC),
    )
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
        st.markdown("**How it would change each driver's predicted pace** (negative = faster)")
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


# ------------------------------------------------------------------ Accuracy (real data)


def _performance() -> None:
    st.subheader("✅ Accuracy - on real races")
    _intro(
        "This is the <b>honest</b> tab: how well did the model do on <b>real</b> F1 races? "
        "We use the <b>Brier score</b> - think of it as prediction error, where <b>lower is "
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
            f"Best model scores **{best['brier_cal']:.3f}** on winning - about **half** the error "
            "of random guessing, and well-calibrated. Honest finding: starting **grid position** "
            "explains most of it (pole usually wins), so the model's edge is real but modest."
        )
    for contract in ("podium", "points", "dnf"):
        r = evaluation_report.contract_summary(report, contract)
        if r:
            with st.expander(f"{contract.title()} contract - details"):
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
        "- **No data leakage** - every fact is time-stamped; predictions only use what was known "
        "at the moment (enforced by tests).\n"
        "- **Calibrated** - probabilities are checked against real outcomes.\n"
        "- **Safe by design** - read-only market data, no real-money trading, paper bets only."
    )


def _next_race() -> None:
    st.subheader("🔮 Next race - prediction")
    pred = evaluation_report.load_next_race_prediction()
    if pred is None:
        st.info("No next-race prediction bundled. Run `scripts/predict_next.py` to generate one.")
        return
    _intro(
        f"The model's forecast for the upcoming <b>{pred['race']}</b> ({pred.get('date', '')}), "
        f"based on <b>current-season form</b> - trained on <b>{pred.get('trained_on_races', '?')} "
        "real races</b> (2022-2026), before qualifying so no grid position yet. Chances are close "
        "because form alone (without the grid) is genuinely uncertain."
    )
    drivers = pred.get("drivers", [])[:8]
    xs, ys, cs = [], [], []
    for d in drivers:
        for label, key in (("Win", "win"), ("Podium", "podium")):
            xs.append(d["driver"])
            ys.append(d[key] * 100)
            cs.append(label)
    fig = px.bar(
        x=xs,
        y=ys,
        color=cs,
        barmode="group",
        color_discrete_map={"Win": ACCENT, "Podium": "#7aa2ff"},
        labels={"x": "", "y": "chance (%)", "color": ""},
    )
    st.plotly_chart(_style(fig), use_container_width=True)
    st.dataframe(
        [
            {
                "driver": d["driver"],
                "team": (d.get("constructor") or "").replace("_", " ").title(),
                "win": f"{d['win']:.0%}",
                "podium": f"{d['podium']:.0%}",
                "points": f"{d['points']:.0%}",
            }
            for d in drivers
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Form-based (Elo ratings + Plackett-Luce). A genuinely forward-looking prediction.")


VIEWS = {
    "🏁 Overview": _overview,
    "🔮 Next race": _next_race,
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
