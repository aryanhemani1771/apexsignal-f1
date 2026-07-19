"""ApexSignal F1 dashboard — Phase 1: interactive race replay.

Runs in fixture mode with zero credentials. Later phases add the remaining pages
(pricing, opportunities, allocation, news, model performance, architecture).

    uv run --extra dashboard streamlit run dashboard/app.py

``?embed=true`` hides the sidebar/header for portfolio embedding.
"""

from __future__ import annotations

import streamlit as st

import theme  # local module; `streamlit run dashboard/app.py` puts this dir on sys.path
from apexsignal.services import race_service


def _embed_mode() -> bool:
    try:
        return st.query_params.get("embed") in ("true", "1")
    except Exception:  # pragma: no cover - older Streamlit fallback
        return False


def main() -> None:
    st.set_page_config(page_title=theme.BRAND, page_icon="🏁", layout="wide")
    st.markdown(theme.CSS, unsafe_allow_html=True)

    embed = _embed_mode()
    if not embed:
        st.title(f"🏁 {theme.BRAND}")
        st.caption(theme.TAGLINE)

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

    if not embed:
        with st.expander("Data-quality report"):
            st.write(quality.summary())
            st.dataframe([i.model_dump() for i in quality.issues], use_container_width=True)

    st.markdown(f"<div class='as-muted'>{theme.DISCLAIMER}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
