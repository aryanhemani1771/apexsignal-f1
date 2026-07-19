"""ApexSignal F1 dashboard — Phases 1-2: race replay + model performance.

Runs in fixture mode with zero credentials. Later phases add the remaining pages
(pricing, opportunities, allocation, news, architecture).

    uv run --extra dashboard streamlit run dashboard/app.py

``?embed=true`` hides the sidebar/header for portfolio embedding.
"""

from __future__ import annotations

import streamlit as st

import theme  # local module; `streamlit run dashboard/app.py` puts this dir on sys.path
from apexsignal.services import evaluation_report, race_service


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

    views = {"Race replay": _race_replay, "Model performance": _model_performance}
    choice = "Race replay" if embed else st.sidebar.radio("View", list(views))
    views[choice]()

    st.markdown(f"<div class='as-muted'>{theme.DISCLAIMER}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
